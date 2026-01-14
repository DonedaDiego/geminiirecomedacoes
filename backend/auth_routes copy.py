#auth_routes
from flask import Blueprint, request, jsonify, render_template_string, redirect, url_for
import jwt
import hashlib
from datetime import datetime, timezone, timedelta
from database import get_db_connection  # ← APENAS ESTE IMPORT
from emails.email_service import email_service
from pag.trial_service import create_trial_user
from pag.control_pay_service import check_user_subscription_status
from pag.trial_service import downgrade_user_trial


# Blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

def hash_password(password):
    """Hash da senha"""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_jwt_token(user_id, email, secret_key):
    """Gerar JWT token"""
    payload = {
        'user_id': user_id,
        'email': email,
        'exp': datetime.now(timezone.utc) + timedelta(days=7)
    }
    return jwt.encode(payload, secret_key, algorithm='HS256')

# ===== ROTAS DE REGISTRO =====

@auth_bp.route('/register', methods=['POST'])
def register():
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados JSON necessários', 'error_code': 'MISSING_DATA'}), 400
        
        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        user_ip = request.remote_addr
        
        print(f"🔐 Tentativa de registro - Email: {email}, IP: {user_ip}")
        
        # Validações básicas
        if not name or not email or not password:
            return jsonify({'success': False, 'error': 'Nome, e-mail e senha são obrigatórios', 'error_code': 'MISSING_FIELDS'}), 400
        
        if len(password) < 6:
            return jsonify({'success': False, 'error': 'Senha deve ter pelo menos 6 caracteres', 'error_code': 'PASSWORD_TOO_SHORT'}), 400
        
        if '@' not in email or '.' not in email:
            return jsonify({'success': False, 'error': 'E-mail inválido', 'error_code': 'EMAIL_INVALID'}), 400
        
        # Conectar ao banco
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão com banco', 'error_code': 'DATABASE_ERROR'}), 500

        cursor = conn.cursor()
        
        #  VALIDAÇÃO INTELIGENTE - VERIFICAR EMAIL E IP
        cursor.execute("""
            SELECT id, email_confirmed, email,
                CASE WHEN email = %s THEN 'email' ELSE 'ip' END as conflict_type
            FROM users 
            WHERE email = %s OR ip_address = %s
        """, (email, email, user_ip))

        existing_user = cursor.fetchone()
        
        if existing_user:
            user_id, is_confirmed, existing_email, conflict_type = existing_user
            
            if conflict_type == 'email':
                # Email já existe
                if is_confirmed:
                    cursor.close()
                    conn.close()
                    return jsonify({
                        'success': False, 
                        'error': 'Este email já possui uma conta. Tente fazer login ou use outro email.',
                        'error_code': 'EMAIL_EXISTS'
                    }), 400
                else:
                    # Email existe mas não confirmado - reenviar confirmação
                    print(f"📧 Email {email} existe mas não confirmado - reenviando confirmação")
                    
                    token_result = email_service.generate_confirmation_token(user_id, email)
                    if token_result['success']:
                        email_sent = email_service.send_confirmation_email(name, email, token_result['token'])
                        if email_sent:
                            cursor.close()
                            conn.close()
                            return jsonify({
                                'success': True,
                                'message': 'Conta já existe! Enviamos um novo email de confirmação.',
                                'requires_confirmation': True
                            }), 200
                    
                    cursor.close()
                    conn.close()
                    return jsonify({'success': False, 'error': 'Erro ao reenviar confirmação', 'error_code': 'EMAIL_SEND_ERROR'}), 500
                    
            elif conflict_type == 'ip':
                #  VALIDAÇÃO INTELIGENTE POR IP
                print(f"🌐 Validando IP {user_ip} - usuário existente encontrado")
                
                # Verificar quantos usuários confirmados existem neste IP
                cursor.execute("""
                    SELECT COUNT(*) FROM users 
                    WHERE ip_address = %s AND email_confirmed = TRUE AND user_type != 'deleted'
                """, (user_ip,))
                
                confirmed_users_count = cursor.fetchone()[0]
                
                # Verificar registros recentes (anti-spam)
                cursor.execute("""
                    SELECT COUNT(*) FROM users 
                    WHERE ip_address = %s AND created_at > NOW() - INTERVAL '1 hour'
                """, (user_ip,))
                
                recent_registrations = cursor.fetchone()[0]
                
                print(f" IP {user_ip}: {confirmed_users_count} usuários confirmados, {recent_registrations} registros na última hora")
                
                # Regra 1: Máximo 3 usuários confirmados por IP
                if confirmed_users_count >= 10:
                    cursor.close()
                    conn.close()
                    return jsonify({
                        'success': False, 
                        'error': 'Limite de contas atingido para este local. Entre em contato conosco se precisar de mais contas.',
                        'error_code': 'IP_USER_LIMIT'
                    }), 400
                
                # Regra 2: Máximo 2 registros por hora (anti-spam)
                if recent_registrations >= 2:
                    cursor.close()
                    conn.close()
                    return jsonify({
                        'success': False,
                        'error': 'Muitas tentativas de registro. Aguarde 1 hora e tente novamente.',
                        'error_code': 'IP_RATE_LIMIT'
                    }), 400
                
                # Regra 3: Verificar se há usuários não confirmados muito antigos (limpeza)
                cursor.execute("""
                    SELECT COUNT(*) FROM users 
                    WHERE ip_address = %s 
                    AND email_confirmed = FALSE 
                    AND created_at < NOW() - INTERVAL '7 days'
                """, (user_ip,))
                
                old_unconfirmed = cursor.fetchone()[0]
                
                if old_unconfirmed >= 5:
                    cursor.close()
                    conn.close()
                    return jsonify({
                        'success': False,
                        'error': 'Este IP tem muitas contas não confirmadas antigas. Entre em contato conosco.',
                        'error_code': 'IP_SUSPICIOUS'
                    }), 400
                
                # Se passou em todas as validações, permitir o registro
                print(f" IP {user_ip} aprovado para novo registro")
        
        #  CRIAR USUÁRIO COM TRIAL USANDO O TRIAL SERVICE
        print(f"👤 Criando usuário: {name} ({email})")
        trial_result = create_trial_user(name, email, password, user_ip)
        
        if not trial_result['success']:
            cursor.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': trial_result['error'],
                'error_code': 'TRIAL_CREATION_ERROR'
            }), 400
        
        user_id = trial_result['user_id']
        print(f" Usuário criado com ID: {user_id}")
        
        #  ATUALIZAR PARA NÃO CONFIRMADO (trial service cria confirmado por padrão)
        cursor.execute("""
            UPDATE users 
            SET email_confirmed = FALSE, email_confirmed_at = NULL
            WHERE id = %s
        """, (user_id,))
        conn.commit()
        
        print(f"📧 Usuário marcado como não confirmado")
        
        # Gerar token de confirmação
        token_result = email_service.generate_confirmation_token(user_id, email)
        
        if not token_result['success']:
            cursor.close()
            conn.close()
            return jsonify({
                'success': False, 
                'error': 'Erro ao gerar token de confirmação',
                'error_code': 'TOKEN_GENERATION_ERROR'
            }), 500
        
        # Enviar email de confirmação
        email_sent = email_service.send_confirmation_email(name, email, token_result['token'])
        
        cursor.close()
        conn.close()
        
        if email_sent:
            print(f" Email de confirmação enviado para {email}")
            return jsonify({
                'success': True,
                'message': '🎉 Conta criada com TRIAL de 15 dias! Verifique seu email para ativar.',
                'requires_confirmation': True,
                'trial_info': {
                    'message': 'Você ganhou 15 dias de acesso GRATUITO!',
                    'plan_name': 'Comunidade',
                    'days_remaining': 15
                },
                'data': {
                    'user_id': user_id,
                    'name': name,
                    'email': email
                }
            }), 201
        else:
            print(f" Erro ao enviar email para {email}")
            return jsonify({
                'success': False, 
                'error': 'Conta criada, mas erro ao enviar email. Tente fazer login.',
                'error_code': 'EMAIL_SEND_ERROR'
            }), 500
        
    except Exception as e:
        print(f" Erro no registro: {e}")
        import traceback
        traceback.print_exc()
        
        # Fechar conexões se ainda estiverem abertas
        try:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
        except:
            pass
        
        return jsonify({
            'success': False, 
            'error': f'Erro interno: {str(e)}',
            'error_code': 'INTERNAL_ERROR'
        }), 500

# ===== ROTAS DE CONFIRMAÇÃO DE EMAIL =====

@auth_bp.route('/confirm-email')
def confirm_email_page():
    """ Página de confirmação de email"""
    token = request.args.get('token')
    
    if not token:
        return render_template_string("""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <title>Erro - Geminii Tech</title>
            <style>body{font-family:Arial;text-align:center;padding:50px;background:#f5f5f5}</style>
        </head>
        <body>
            <h1> Token não encontrado</h1>
            <p>Link de confirmação inválido.</p>
            <a href="/login">← Voltar ao Login</a>
        </body>
        </html>
        """), 400
    
    # Confirmar token - USANDO MÉTODO CORRETO
    result = email_service.confirm_email_token(token)
    
    if result['success']:
        return render_template_string(f"""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Email Confirmado - Geminii Tech</title>
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; background: linear-gradient(135deg, #ba39af, #d946ef); color: white; }}
                .container {{ background: rgba(255,255,255,0.1); padding: 40px; border-radius: 20px; max-width: 500px; margin: 0 auto; }}
                .success {{ font-size: 60px; margin-bottom: 20px; }}
                h1 {{ margin-bottom: 20px; }}
                .btn {{ display: inline-block; background: white; color: #ba39af; padding: 15px 30px; text-decoration: none; border-radius: 10px; font-weight: bold; margin: 20px 10px; }}
                .btn:hover {{ background: #f0f0f0; }}
                .trial-info {{ background: rgba(255,255,255,0.1); padding: 20px; border-radius: 10px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success"></div>
                <h1>Email Confirmado!</h1>
                <p>Olá, <strong>{result['user_name']}</strong>!</p>
                <p>Seu email foi confirmado com sucesso.</p>
                
                <div class="trial-info">
                    <h3>🎉 Trial de 15 dias ATIVADO!</h3>
                    <p>Você tem acesso completo às ferramentas da Comunidade por 15 dias!</p>
                </div>
                
                <a href="/login" class="btn">🔐 Fazer Login</a>
                <a href="/dashboard" class="btn"> Ir ao Dashboard</a>
            </div>
            
            <script>
                // Auto-redirecionar após 8 segundos
                setTimeout(() => {{
                    window.location.href = '/login';
                }}, 8000);
            </script>
        </body>
        </html>
        """), 200
    else:
        return render_template_string(f"""
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <title>Erro na Confirmação - Geminii Tech</title>
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f5f5f5; }}
                .container {{ background: white; padding: 40px; border-radius: 20px; max-width: 500px; margin: 0 auto; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }}
                .error {{ font-size: 60px; margin-bottom: 20px; }}
                .btn {{ display: inline-block; background: #ba39af; color: white; padding: 15px 30px; text-decoration: none; border-radius: 10px; font-weight: bold; margin: 20px 10px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="error"></div>
                <h1>Erro na Confirmação</h1>
                <p>{result['error']}</p>
                
                <a href="/login" class="btn">← Voltar ao Login</a>
                <a href="/register" class="btn">📝 Criar Nova Conta</a>
            </div>
        </body>
        </html>
        """), 400

@auth_bp.route('/resend-confirmation', methods=['POST'])
def resend_confirmation():
    """ Reenviar email de confirmação"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        
        if not email:
            return jsonify({'success': False, 'error': 'Email é obrigatório'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
        
        cursor = conn.cursor()
        
        # Buscar usuário não confirmado
        cursor.execute("SELECT id, name, email_confirmed FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not user:
            return jsonify({'success': False, 'error': 'Email não encontrado'}), 404
        
        user_id, name, is_confirmed = user
        
        if is_confirmed:
            return jsonify({'success': False, 'error': 'Email já confirmado'}), 400
        
        # Gerar novo token
        token_result = email_service.generate_confirmation_token(user_id, email)
        
        if not token_result['success']:
            return jsonify({'success': False, 'error': 'Erro ao gerar token'}), 500
        
        # Enviar email
        email_sent = email_service.send_confirmation_email(name, email, token_result['token'])
        
        if email_sent:
            return jsonify({
                'success': True,
                'message': 'Email de confirmação reenviado com sucesso!'
            }), 200
        else:
            return jsonify({'success': False, 'error': 'Erro ao enviar email'}), 500
        
    except Exception as e:
        print(f" Erro ao reenviar confirmação: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== FUNÇÃO PARA CONFIRMAR EMAIL E ATIVAR TRIAL =====

@auth_bp.route('/activate-user/<user_id>', methods=['POST'])
def activate_user_manually(user_id):
    """ FUNÇÃO TEMPORÁRIA - Ativar usuário manualmente"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
        
        cursor = conn.cursor()
        
        # Confirmar email e garantir que o trial está ativo
        cursor.execute("""
            UPDATE users 
            SET email_confirmed = TRUE, 
                email_confirmed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING name, email, trial_end_date
        """, (user_id,))
        
        result = cursor.fetchone()
        
        if result:
            conn.commit()
            name, email, trial_end_date = result
            
            cursor.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': f'Usuário {name} ativado com sucesso!',
                'data': {
                    'name': name,
                    'email': email,
                    'trial_end_date': trial_end_date.isoformat() if trial_end_date else None
                }
            }), 200
        else:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Usuário não encontrado'}), 404
        
    except Exception as e:
        print(f" Erro ao ativar usuário: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== ROTA TEMPORÁRIA PARA LISTAR USUÁRIOS NÃO CONFIRMADOS =====

@auth_bp.route('/list-unconfirmed', methods=['GET'])
def list_unconfirmed_users():
    """ FUNÇÃO TEMPORÁRIA - Listar usuários não confirmados"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
        
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, email, created_at, trial_end_date
            FROM users 
            WHERE email_confirmed = FALSE
            ORDER BY created_at DESC
            LIMIT 10
        """)
        
        users = cursor.fetchall()
        cursor.close()
        conn.close()
        
        user_list = []
        for user in users:
            user_id, name, email, created_at, trial_end_date = user
            user_list.append({
                'id': user_id,
                'name': name,
                'email': email,
                'created_at': created_at.isoformat() if created_at else None,
                'trial_end_date': trial_end_date.isoformat() if trial_end_date else None,
                'activate_url': f'/auth/activate-user/{user_id}'
            })
        
        return jsonify({
            'success': True,
            'message': f'Encontrados {len(user_list)} usuários não confirmados',
            'users': user_list
        }), 200
        
    except Exception as e:
        print(f" Erro ao listar usuários: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Substitua sua função login() por esta versão corrigida:

@auth_bp.route('/login', methods=['POST'])
def login():
 
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados JSON necessários'}), 400
        
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        
        if not email or not password:
            return jsonify({'success': False, 'error': 'E-mail e senha são obrigatórios'}), 400
        
        
        conn = get_db_connection()
        if not conn:
            print(" Erro de conexão com banco")
            return jsonify({'success': False, 'error': 'Erro de conexão com banco'}), 500
        
        cursor = conn.cursor()
        
        #  VERIFICAR SE COLUNA last_login EXISTE
        try:
            cursor.execute("""
                ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP;
            """)
            conn.commit()
        except:
            pass  # Coluna já existe
             
        cursor.execute("""
            SELECT id, name, email, password, plan_id, plan_name, user_type, email_confirmed,
                plan_expires_at, subscription_status, created_at, last_login
            FROM users WHERE email = %s
        """, (email,))
                
        user = cursor.fetchone()
        
        if not user:
            print(f" Usuário não encontrado: {email}")
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'E-mail não encontrado'}), 401
        
        user_id, name, user_email, stored_password, plan_id, plan_name, user_type, email_confirmed, plan_expires_at, subscription_status, created_at, last_login = user
        
        print(f" Usuário encontrado: {name} (ID: {user_id})")
        print(f"📧 Email confirmado: {email_confirmed}")
        print(f" Subscription status: {subscription_status}")
        print(f"🕐 Último login: {last_login}")
        
        # Verificar senha
        if hash_password(password) != stored_password:
            print(" Senha incorreta")
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Senha incorreta'}), 401
        
        print(" Senha correta")
        
        # Verificar se email foi confirmado
        if not email_confirmed:
            print("⚠️ Email não confirmado")
            cursor.close()
            conn.close()
            return jsonify({
                'success': False, 
                'error': 'Email não confirmado', 
                'requires_confirmation': True,
                'email': email,
                'user_id': user_id  # Para debug temporário
            }), 403
        
        print(" Email confirmado - procedendo com login")
        
        #  ATUALIZAR ÚLTIMO LOGIN ANTES DE VERIFICAR SUBSCRIPTION
        try:
            cursor.execute("""
                UPDATE users 
                SET last_login = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (user_id,))
            
            # Verificar quantas linhas foram afetadas
            affected_rows = cursor.rowcount
            conn.commit()
            
            # Verificar se realmente foi atualizado
            cursor.execute("SELECT last_login FROM users WHERE id = %s", (user_id,))
            updated_login = cursor.fetchone()[0]
            
            print(f" Último login atualizado - Rows: {affected_rows}, Novo valor: {updated_login}")
            
        except Exception as e:
            print(f"⚠️ Erro ao atualizar último login: {e}")
        
        
        cursor.close()
        conn.close()
        
        #  VERIFICAR STATUS DA SUBSCRIPTION/TRIAL
        subscription_status_result = check_user_subscription_status(user_id)
        print(f" Status da subscription: {subscription_status_result}")
        
        #  VERIFICAR SE A FUNÇÃO RETORNOU SUCESSO
        if not subscription_status_result.get('success', False):
            print(" Erro ao verificar status da subscription")
            return jsonify({'success': False, 'error': 'Erro ao verificar status da conta'}), 500
        
        # Gerar token JWT
        from flask import current_app
        token = generate_jwt_token(user_id, email, current_app.config['SECRET_KEY'])
        
        
        
        #  EXTRAIR DADOS DA SUBSCRIPTION
        subscription_data = subscription_status_result.get('subscription', {})
        user_data = subscription_status_result.get('user', {})
        
        #  PREPARAR RESPOSTA COM SUBSCRIPTION INFO
        login_response = {
            'success': True,
            'message': 'Login realizado com sucesso!',
            'data': {
                'user': {
                    'id': user_id,
                    'name': name,
                    'email': user_email,
                    'plan_id': user_data.get('plan_id', plan_id),
                    'plan_name': user_data.get('plan_name', plan_name),
                    'user_type': user_data.get('user_type', user_type),
                    'email_confirmed': email_confirmed,
                    'created_at': created_at.isoformat() if created_at else None,
                    'trial_end_date': plan_expires_at.isoformat() if plan_expires_at else None,
                    'last_login': datetime.now(timezone.utc).isoformat()  #  NOVO
                },
                'token': token
            }
        }
        
        #  ADICIONAR TRIAL/SUBSCRIPTION INFO (resto do seu código permanece igual)
        if subscription_data.get('is_trial', False):
            days_left = subscription_data.get('days_remaining', 0)
            
            login_response['trial_info'] = {
                'is_trial': True,
                'expires_at': subscription_data.get('expires_at'),
                'days_remaining': days_left,
                'hours_remaining': subscription_data.get('hours_remaining', 0),
                'urgency_level': 'high' if days_left <= 3 else 'medium' if days_left <= 7 else 'low'
            }
            
            # Mensagem personalizada baseada no tempo restante
            if days_left <= 1:
                login_response['message'] = '⚠️ Seu trial expira hoje! Não perca o acesso total.'
            elif days_left <= 3:
                login_response['message'] = f'⏰ Apenas {days_left} dias restantes do seu trial!'
            elif days_left <= 7:
                login_response['message'] = f'🚀 Você tem {days_left} dias de trial restantes!'
            else:
                login_response['message'] = f'🎉 Bem-vindo! {days_left} dias de trial restantes!'
        
        elif subscription_data.get('status') == 'trial_expired':
            login_response['trial_info'] = {
                'is_trial': False,
                'trial_expired': True,
                'message': 'Seu trial expirou. Que tal fazer upgrade?'
            }
            login_response['message'] = '💡 Seu trial expirou, mas você ainda pode acessar os recursos básicos!'
        
        elif subscription_data.get('status') == 'active':
            # Subscription paga ativa
            days_until_renewal = subscription_data.get('days_until_renewal', 0)
            
            login_response['subscription_info'] = {
                'is_paid': True,
                'status': 'active',
                'expires_at': subscription_data.get('expires_at'),
                'days_until_renewal': days_until_renewal,
                'plan_name': user_data.get('plan_name', plan_name)
            }
            
            if days_until_renewal <= 3:
                login_response['message'] = f'⚠️ Sua assinatura {user_data.get("plan_name", plan_name)} vence em {days_until_renewal} dias!'
            elif days_until_renewal <= 7:
                login_response['message'] = f'📅 Sua assinatura {user_data.get("plan_name", plan_name)} vence em {days_until_renewal} dias.'
            else:
                login_response['message'] = f'🎉 Bem-vindo! Assinatura {user_data.get("plan_name", plan_name)} ativa!'
        
        elif subscription_data.get('status') == 'expired':
            login_response['subscription_info'] = {
                'is_paid': False,
                'status': 'expired',
                'message': 'Sua assinatura expirou. Renove para continuar com acesso Premium!'
            }
            login_response['message'] = '💡 Sua assinatura expirou, mas você ainda pode acessar os recursos básicos!'
        
        print(f"🎉 Login bem-sucedido para: {name}")
        return jsonify(login_response), 200
        
    except Exception as e:
        print(f" Erro no login: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500


# ===== ROTAS DE RESET DE SENHA =====

@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """ Solicitar reset de senha"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados JSON necessários'}), 400
        
        email = data.get('email', '').strip().lower()
        
        if not email or '@' not in email:
            return jsonify({'success': False, 'error': 'E-mail é obrigatório'}), 400
        
        result = email_service.generate_password_reset_token(email)
        
        if result['success']:
            # Enviar email de reset
            email_sent = email_service.send_password_reset_email(
                result['user_name'], 
                result['user_email'], 
                result['token']
            )
            
            if email_sent:
                return jsonify({
                    'success': True,
                    'message': 'E-mail de recuperação enviado com sucesso!'
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': 'Erro ao enviar e-mail. Tente novamente.'
                }), 500
        else:
            return jsonify(result), 400
        
    except Exception as e:
        print(f" Erro no forgot-password: {e}")
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500

@auth_bp.route('/validate-reset-token', methods=['POST'])
def validate_reset_token():
    """ Validar token de reset"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados JSON necessários'}), 400
        
        token = data.get('token', '').strip()
        
        if not token:
            return jsonify({'success': False, 'error': 'Token é obrigatório'}), 400
        
        result = email_service.validate_password_reset_token(token)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'Token válido!',
                'data': {
                    'user_name': result['user_name'],
                    'email': result['email'],
                    'expires_at': result['expires_at']
                }
            }), 200
        else:
            return jsonify(result), 400
        
    except Exception as e:
        print(f" Erro na validação de token: {e}")
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500

@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """ Redefinir senha com token"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados JSON necessários'}), 400
        
        token = data.get('token', '').strip()
        new_password = data.get('new_password', '')
        
        if not token or not new_password:
            return jsonify({'success': False, 'error': 'Token e nova senha são obrigatórios'}), 400
        
        if len(new_password) < 6:
            return jsonify({'success': False, 'error': 'Nova senha deve ter pelo menos 6 caracteres'}), 400
        
        result = email_service.reset_password_with_token(token, new_password)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message'],
                'data': {
                    'user_name': result['user_name']
                }
            }), 200
        else:
            return jsonify(result), 400
        
    except Exception as e:
        print(f" Erro no reset de senha: {e}")
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500

# ===== ROTAS DE VERIFICAÇÃO =====

@auth_bp.route('/verify', methods=['GET'])
def verify_token():
    """Verificar token JWT + migração automática trial->free"""
    try:
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'error': 'Token não fornecido'}), 401
        
        token = auth_header.replace('Bearer ', '')
        
        try:
            from flask import current_app
            payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            user_id = payload['user_id']
            
            # BUSCAR DADOS DO USUÁRIO
            conn = get_db_connection()
            if not conn:
                return jsonify({'success': False, 'error': 'Erro de conexão com banco'}), 500
            
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, name, email, plan_id, plan_name, user_type, email_confirmed,
                    plan_expires_at, created_at
                FROM users WHERE id = %s
            """, (user_id,))
            
            user = cursor.fetchone()
            
            if not user:
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'error': 'Usuário não encontrado'}), 401
            
            user_id, name, email, plan_id, plan_name, user_type, email_confirmed, plan_expires_at, created_at = user
            
            # VERIFICAÇÃO SIMPLES: trial expirado? migra para free
            if user_type == 'trial' and plan_expires_at:
                now = datetime.now(timezone.utc)
                trial_end = plan_expires_at.replace(tzinfo=timezone.utc)
                
                if now > trial_end:
                    print(f"Trial expirado para {email} - migrando para Free")
                    
                    cursor.execute("""
                        UPDATE users 
                        SET plan_id = 3, plan_name = 'Free', user_type = 'regular',
                            plan_expires_at = NULL, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (user_id,))
                    conn.commit()
                    
                    # Atualizar variáveis
                    plan_id = 3
                    plan_name = 'Free'
                    user_type = 'regular'
                    plan_expires_at = None
            
            cursor.close()
            conn.close()
            
            # RESPOSTA SIMPLES
            user_data = {
                'id': user_id,
                'name': name,
                'email': email,
                'plan_id': plan_id,
                'plan_name': plan_name,
                'user_type': user_type,
                'email_confirmed': email_confirmed,
                'created_at': created_at.isoformat() if created_at else None,
                'trial_end_date': plan_expires_at.isoformat() if plan_expires_at else None
            }
            
            return jsonify({
                'success': True,
                'data': {
                    'user': user_data
                }
            }), 200
            
        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'error': 'Token expirado'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'success': False, 'error': 'Token inválido'}), 401
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """ Logout do usuário"""
    return jsonify({'success': True, 'message': 'Logout realizado com sucesso!'}), 200


@auth_bp.route('/test-smtp', methods=['GET'])
def test_smtp():
    """🧪 Testar conexão SMTP"""
    print("\n🧪 Iniciando teste SMTP via rota...")
    result = email_service.test_smtp_connection()
    
    return jsonify({
        'success': result,
        'message': 'SMTP funcionando!' if result else 'SMTP bloqueado/com erro',
        'tip': 'Veja os logs detalhados no console do Railway'
    }), 200 if result else 500

def get_auth_blueprint():
    return auth_bp


def get_auth_blueprint():
    """Retornar blueprint para registrar no Flask"""
    return auth_bp
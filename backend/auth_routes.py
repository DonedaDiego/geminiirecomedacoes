from flask import Blueprint, request, jsonify, render_template_string, redirect, url_for
import jwt
import hashlib
from datetime import datetime, timezone, timedelta
from database import get_db_connection
from emails.email_service import email_service
from pag.trial_service import create_trial_user
from pag.control_pay_service import check_user_subscription_status
from database import get_db_connection  # ← ADICIONAR ESTA LINHA
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
    """🔥 Registro com trial Premium de 15 dias + confirmação de email"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados JSON necessários'}), 400
        
        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        user_ip = request.remote_addr
        
        # Validações
        if not name or not email or not password:
            return jsonify({'success': False, 'error': 'Nome, e-mail e senha são obrigatórios'}), 400
        
        if len(password) < 6:
            return jsonify({'success': False, 'error': 'Senha deve ter pelo menos 6 caracteres'}), 400
        
        if '@' not in email or '.' not in email:
            return jsonify({'success': False, 'error': 'E-mail inválido'}), 400
        
        # Verificar se email já existe
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão com banco'}), 500

        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, email_confirmed, 
                CASE WHEN email = %s THEN 'email' ELSE 'ip' END as conflict_type
            FROM users 
            WHERE email = %s OR ip_address = %s
        """, (email, email, user_ip))

        existing_user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if existing_user:
            user_id, is_confirmed, conflict_type = existing_user
            if conflict_type == 'ip':
                return jsonify({'success': False, 'error': 'Este usuário já foi registrado com outro e-mail! Dúvidas entre em contato com os canais abaixo'}), 400
            else:
                # Email existe mas não confirmado - reenviar confirmação
                token_result = email_service.generate_confirmation_token(user_id, email)
                if token_result['success']:
                    email_sent = email_service.send_confirmation_email(name, email, token_result['token'])
                    if email_sent:
                        return jsonify({
                            'success': True,
                            'message': 'Conta já existe! Enviamos um novo email de confirmação.',
                            'requires_confirmation': True
                        }), 200
                
                return jsonify({'success': False, 'error': 'Erro ao reenviar confirmação'}), 500
        
        # 🔥 USAR O TRIAL SERVICE PARA CRIAR USUÁRIO COM TRIAL PREMIUM
        trial_result = create_trial_user(name, email, password, user_ip)
        
        if not trial_result['success']:
            return jsonify({
                'success': False,
                'error': trial_result['error']
            }), 400
        
        user_id = trial_result['user_id']
        
        # 🔥 AGORA PRECISAMOS ATUALIZAR O USUÁRIO PARA NÃO CONFIRMADO
        # (porque o trial_service cria confirmado, mas queremos confirmação de email)
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET email_confirmed = FALSE, email_confirmed_at = NULL
                WHERE id = %s
            """, (user_id,))
            conn.commit()
            cursor.close()
            conn.close()
        
        # Gerar token de confirmação
        token_result = email_service.generate_confirmation_token(user_id, email)
        
        if not token_result['success']:
            return jsonify({'success': False, 'error': 'Erro ao gerar token de confirmação'}), 500
        
        # Enviar email de confirmação
        email_sent = email_service.send_confirmation_email(name, email, token_result['token'])
        
        if email_sent:
            return jsonify({
                'success': True,
                'message': '🎉 Conta criada com TRIAL PREMIUM de 15 dias! Verifique seu email para ativar.',
                'requires_confirmation': True,
                'trial_info': {
                    'message': 'Você ganhou 15 dias de acesso Premium GRATUITO!',
                    'plan_name': 'Premium',
                    'days_remaining': 15
                },
                'data': {
                    'user_id': user_id,
                    'name': name,
                    'email': email
                }
            }), 201
        else:
            return jsonify({'success': False, 'error': 'Conta criada, mas erro ao enviar email. Tente fazer login.'}), 500
        
    except Exception as e:
        print(f"❌ Erro no registro: {e}")
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500

# ===== ROTAS DE CONFIRMAÇÃO DE EMAIL =====

@auth_bp.route('/confirm-email')
def confirm_email_page():
    """🔥 Página de confirmação de email"""
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
            <h1>❌ Token não encontrado</h1>
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
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✅</div>
                <h1>Email Confirmado!</h1>
                <p>Olá, <strong>{result['user_name']}</strong>!</p>
                <p>Seu email foi confirmado com sucesso. Agora você pode fazer login na plataforma.</p>
                
                <a href="/login" class="btn">🔐 Fazer Login</a>
                <a href="/dashboard" class="btn">📊 Ir ao Dashboard</a>
            </div>
            
            <script>
                // Auto-redirecionar após 5 segundos
                setTimeout(() => {{
                    window.location.href = '/login';
                }}, 5000);
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
                <div class="error">❌</div>
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
    """🔥 Reenviar email de confirmação"""
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
        print(f"❌ Erro ao reenviar confirmação: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== ROTAS DE LOGIN =====

@auth_bp.route('/login', methods=['POST'])
def login():
    """🔥 Login com verificação de subscription/trial"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados JSON necessários'}), 400
        
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'success': False, 'error': 'E-mail e senha são obrigatórios'}), 400
        
        print(f"🔐 Tentativa de login: {email}")
        
        conn = get_db_connection()
        if not conn:
            print("❌ Erro de conexão com banco")
            return jsonify({'success': False, 'error': 'Erro de conexão com banco'}), 500
        
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, email, password, plan_id, plan_name, user_type, email_confirmed
            FROM users WHERE email = %s
        """, (email,))
        
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user:
            print(f"❌ Usuário não encontrado: {email}")
            return jsonify({'success': False, 'error': 'E-mail não encontrado'}), 401
        
        user_id, name, user_email, stored_password, plan_id, plan_name, user_type, email_confirmed = user
        
        print(f"✅ Usuário encontrado: {name} (ID: {user_id})")
        print(f"📧 Email confirmado: {email_confirmed}")
        
        # Verificar senha
        if hash_password(password) != stored_password:
            print("❌ Senha incorreta")
            return jsonify({'success': False, 'error': 'Senha incorreta'}), 401
        
        print("✅ Senha correta")
        
        # Verificar se email foi confirmado
        if not email_confirmed:
            print("⚠️ Email não confirmado")
            return jsonify({
                'success': False, 
                'error': 'Email não confirmado', 
                'requires_confirmation': True,
                'email': email
            }), 403
        
        print("✅ Email confirmado - procedendo com login")
        
        # 🔥 VERIFICAR STATUS DA SUBSCRIPTION/TRIAL
        subscription_status = check_user_subscription_status(user_id)
        print(f"📊 Status da subscription: {subscription_status}")
        
        # 🔥 VERIFICAR SE A FUNÇÃO RETORNOU SUCESSO
        if not subscription_status.get('success', False):
            print("❌ Erro ao verificar status da subscription")
            return jsonify({'success': False, 'error': 'Erro ao verificar status da conta'}), 500
        
        # Gerar token JWT
        from flask import current_app
        token = generate_jwt_token(user_id, email, current_app.config['SECRET_KEY'])
        
        print(f"🎫 Token JWT gerado: {token[:50]}...")
        
        # 🔥 EXTRAIR DADOS DA SUBSCRIPTION
        subscription_data = subscription_status.get('subscription', {})
        user_data = subscription_status.get('user', {})
        
        # 🔥 PREPARAR RESPOSTA COM SUBSCRIPTION INFO
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
                    'email_confirmed': email_confirmed
                },
                'token': token
            }
        }
        
        # 🔥 ADICIONAR TRIAL/SUBSCRIPTION INFO
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
                login_response['message'] = '⚠️ Seu trial Premium expira hoje! Não perca o acesso total.'
            elif days_left <= 3:
                login_response['message'] = f'⏰ Apenas {days_left} dias restantes do seu trial Premium!'
            elif days_left <= 7:
                login_response['message'] = f'🚀 Você tem {days_left} dias de trial Premium restantes!'
            else:
                login_response['message'] = f'🎉 Bem-vindo! {days_left} dias de Premium restantes!'
        
        elif subscription_data.get('status') == 'trial_expired':
            login_response['trial_info'] = {
                'is_trial': False,
                'trial_expired': True,
                'message': 'Seu trial Premium expirou. Que tal fazer upgrade?'
            }
            login_response['message'] = '💡 Seu trial Premium expirou, mas você ainda pode acessar os recursos básicos!'
        
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
        print(f"❌ Erro no login: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500

# ===== ROTAS DE RESET DE SENHA =====

@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """🔥 Solicitar reset de senha"""
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
        print(f"❌ Erro no forgot-password: {e}")
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500

@auth_bp.route('/validate-reset-token', methods=['POST'])
def validate_reset_token():
    """🔥 Validar token de reset"""
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
        print(f"❌ Erro na validação de token: {e}")
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500

@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """🔥 Redefinir senha com token"""
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
        print(f"❌ Erro no reset de senha: {e}")
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500

# ===== ROTAS DE VERIFICAÇÃO =====


@auth_bp.route('/verify', methods=['GET'])
def verify_token():
    """🔥 Verificar token JWT com informações de subscription/trial + DOWNGRADE AUTOMÁTICO"""
    try:
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            print("❌ Token não fornecido ou formato inválido")
            return jsonify({'success': False, 'error': 'Token não fornecido'}), 401
        
        token = auth_header.replace('Bearer ', '')
        
        try:
            from flask import current_app
            payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            user_id = payload['user_id']
            
            # 🔥 VERIFICAR STATUS DA SUBSCRIPTION/TRIAL
            subscription_status = check_user_subscription_status(user_id)
            
            if not subscription_status.get('success', False):
                print(f"❌ Erro ao verificar subscription: {subscription_status}")
                return jsonify({'success': False, 'error': 'Erro ao verificar status da conta'}), 500
            
            # 🔥 DOWNGRADE AUTOMÁTICO - TRIAL EXPIRADO
            subscription_data = subscription_status.get('subscription', {})
            if subscription_data.get('status') == 'trial_expired':
                print(f"🔄 Trial expirado detectado para usuário {user_id} - fazendo downgrade automático...")
                
                try:
                    downgrade_result = downgrade_user_trial(user_id)
                    
                    if downgrade_result.get('success', False):
                        print(f"✅ Downgrade de trial realizado para usuário {user_id}")
                        # Re-verificar status após downgrade
                        subscription_status = check_user_subscription_status(user_id)
                    else:
                        print(f"❌ Erro no downgrade de trial: {downgrade_result.get('error')}")
                
                except Exception as downgrade_error:
                    print(f"❌ Erro na função de downgrade de trial: {downgrade_error}")
                    # Continuar mesmo se downgrade falhar
            
            # 🔥 NOVO: DOWNGRADE AUTOMÁTICO - PAGAMENTO EXPIRADO
            elif subscription_data.get('status') == 'paid_expired':
                print(f"🔄 Pagamento expirado detectado para usuário {user_id} - fazendo downgrade automático...")
                
                try:
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        
                        # Verificar se realmente está expirado
                        cursor.execute("""
                            SELECT plan_id, plan_name, plan_expires_at
                            FROM users 
                            WHERE id = %s 
                            AND plan_expires_at IS NOT NULL 
                            AND plan_expires_at < NOW()
                            AND user_type != 'trial'
                            AND plan_id IN (1, 2)
                        """, (user_id,))
                        
                        expired_user = cursor.fetchone()
                        
                        if expired_user:
                            # Fazer downgrade individual
                            cursor.execute("""
                                UPDATE users 
                                SET plan_id = 3, 
                                    plan_name = 'Básico',
                                    plan_expires_at = NULL,
                                    updated_at = CURRENT_TIMESTAMP
                                WHERE id = %s
                            """, (user_id,))
                            
                            conn.commit()
                            print(f"✅ Downgrade de pagamento realizado para usuário {user_id}")
                            
                            # Re-verificar status após downgrade
                            subscription_status = check_user_subscription_status(user_id)
                        
                        cursor.close()
                        conn.close()
                
                except Exception as downgrade_error:
                    print(f"❌ Erro na função de downgrade de pagamento: {downgrade_error}")
                    # Continuar mesmo se downgrade falhar
            
            # 🔥 BUSCAR DADOS ATUALIZADOS DO USUÁRIO
            conn = get_db_connection()
            if not conn:
                print("❌ Erro de conexão com banco")
                return jsonify({'success': False, 'error': 'Erro de conexão com banco'}), 500
            
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, email, plan_id, plan_name, user_type, email_confirmed
                FROM users WHERE id = %s
            """, (user_id,))
            
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not user:
                print(f"❌ Usuário não encontrado no banco: {user_id}")
                return jsonify({'success': False, 'error': 'Usuário não encontrado'}), 401
            
            user_id, name, email, plan_id, plan_name, user_type, email_confirmed = user
            
            # 🔥 EXTRAIR DADOS DA SUBSCRIPTION (atualizados após possível downgrade)
            subscription_data = subscription_status.get('subscription', {})
            user_data = subscription_status.get('user', {})
            
            # 🔥 PREPARAR RESPOSTA COM SUBSCRIPTION INFO
            response_data = {
                'success': True,
                'data': {
                    'user': {
                        'id': user_id,
                        'name': name,
                        'email': email,
                        'plan_id': user_data.get('plan_id', plan_id),
                        'plan_name': user_data.get('plan_name', plan_name),
                        'user_type': user_data.get('user_type', user_type),
                        'email_confirmed': email_confirmed
                    }
                }
            }
            
            # 🔥 ADICIONAR TRIAL/SUBSCRIPTION INFO
            if subscription_data.get('is_trial', False):
                response_data['trial_info'] = {
                    'is_trial': True,
                    'expires_at': subscription_data.get('expires_at'),
                    'days_remaining': subscription_data.get('days_remaining', 0),
                    'hours_remaining': subscription_data.get('hours_remaining', 0),
                    'urgency_level': 'high' if subscription_data.get('days_remaining', 0) <= 3 else 'medium' if subscription_data.get('days_remaining', 0) <= 7 else 'low',
                    'message': subscription_data.get('message', 'Trial ativo')
                }
            elif subscription_data.get('status') == 'trial_expired':
                response_data['trial_info'] = {
                    'is_trial': False,
                    'trial_expired': True,
                    'message': 'Trial expirado'
                }
            elif subscription_data.get('status') == 'paid_active':
                response_data['subscription_info'] = {
                    'is_paid': True,
                    'status': 'active',
                    'expires_at': subscription_data.get('expires_at'),
                    'days_until_renewal': subscription_data.get('days_remaining', 0),
                    'plan_name': user_data.get('plan_name', plan_name)
                }
            elif subscription_data.get('status') == 'paid_expired':
                response_data['subscription_info'] = {
                    'is_paid': False,
                    'status': 'expired',
                    'message': 'Assinatura expirada'
                }
            
            return jsonify(response_data), 200
            
        except jwt.ExpiredSignatureError:
            print("❌ Token expirado")
            return jsonify({'success': False, 'error': 'Token expirado'}), 401
        except jwt.InvalidTokenError as e:
            print(f"❌ Token inválido: {e}")
            return jsonify({'success': False, 'error': 'Token inválido'}), 401
        
    except Exception as e:
        print(f"❌ Erro na verificação de token: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500
    
@auth_bp.route('/logout', methods=['POST'])
def logout():
    """🔥 Logout do usuário"""
    return jsonify({'success': True, 'message': 'Logout realizado com sucesso!'}), 200

# ===== FUNÇÃO PARA RETORNAR BLUEPRINT =====

def get_auth_blueprint():
    """Retornar blueprint para registrar no Flask"""
    return auth_bp
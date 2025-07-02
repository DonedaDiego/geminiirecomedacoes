# auth_routes.py - ROTAS COMPLETAS DE AUTENTICAÇÃO - CORRIGIDO
# ==================================================

from flask import Blueprint, request, jsonify, render_template_string, redirect, url_for
import jwt
import hashlib
from datetime import datetime, timezone, timedelta
from database import get_db_connection
from email_service import email_service

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
    """🔥 Registro com confirmação de email"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados JSON necessários'}), 400
        
        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        # Validações
        if not name or not email or not password:
            return jsonify({'success': False, 'error': 'Nome, e-mail e senha são obrigatórios'}), 400
        
        if len(password) < 6:
            return jsonify({'success': False, 'error': 'Senha deve ter pelo menos 6 caracteres'}), 400
        
        if '@' not in email or '.' not in email:
            return jsonify({'success': False, 'error': 'E-mail inválido'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão com banco'}), 500
        
        cursor = conn.cursor()
        
        # Verificar se email já existe
        cursor.execute("SELECT id, email_confirmed FROM users WHERE email = %s", (email,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            user_id, is_confirmed = existing_user
            if is_confirmed:
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'error': 'E-mail já cadastrado e confirmado'}), 400
            else:
                # Email existe mas não confirmado - reenviar confirmação
                cursor.close()
                conn.close()
                
                # Gerar novo token
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
        
        # Criar novo usuário (NÃO CONFIRMADO)
        hashed_password = hash_password(password)
        cursor.execute("""
            INSERT INTO users (name, email, password, plan_id, plan_name, email_confirmed, created_at) 
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (name, email, hashed_password, 3, 'Básico', False, datetime.now(timezone.utc)))
        
        user_id = cursor.fetchone()[0]
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
                'message': 'Conta criada! Verifique seu email para confirmação.',
                'requires_confirmation': True,
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
    """🔥 Login com verificação de email confirmado - VERSÃO CORRIGIDA"""
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
        
        # Gerar token JWT
        from flask import current_app
        token = generate_jwt_token(user_id, email, current_app.config['SECRET_KEY'])
        
        print(f"🎫 Token JWT gerado: {token[:50]}...")
        
        login_response = {
            'success': True,
            'message': 'Login realizado com sucesso!',
            'data': {
                'user': {
                    'id': user_id,
                    'name': name,
                    'email': user_email,
                    'plan_id': plan_id,
                    'plan_name': plan_name,
                    'user_type': user_type,
                    'email_confirmed': email_confirmed
                },
                'token': token
            }
        }
        
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
        
        # Gerar token de reset
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
    """🔥 Verificar se token JWT é válido - VERSÃO CORRIGIDA"""
    try:
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            print("❌ Token não fornecido ou formato inválido")
            return jsonify({'success': False, 'error': 'Token não fornecido'}), 401
        
        token = auth_header.replace('Bearer ', '')
        print(f"🔍 Verificando token: {token[:50]}...")
        
        try:
            from flask import current_app
            payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            user_id = payload['user_id']
            
            print(f"✅ Token válido, user_id: {user_id}")
            
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
            
            print(f"✅ Usuário verificado: {name} ({email})")
            
            return jsonify({
                'success': True,
                'data': {
                    'user': {
                        'id': user_id,
                        'name': name,
                        'email': email,
                        'plan_id': plan_id,
                        'plan_name': plan_name,
                        'user_type': user_type,
                        'email_confirmed': email_confirmed
                    }
                }
            })
            
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

if __name__ == "__main__":
    print("🔐 Auth Routes - Sistema completo de autenticação CORRIGIDO")
    print("📧 Recursos incluídos:")
    print("  - Registro com confirmação de email")
    print("  - Login com verificação de email")
    print("  - Reset de senha com token") 
    print("  - Validação de tokens JWT")
    print("  - Reenvio de confirmação")
    print("  - Debug aprimorado")
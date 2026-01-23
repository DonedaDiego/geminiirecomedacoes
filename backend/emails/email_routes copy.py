# email_routes.py 

from flask import Blueprint, request, jsonify
from emails.email_service import email_service

# Criar blueprint
email_bp = Blueprint('email', __name__, url_prefix='/auth')

# ===== ROTAS DE RECUPERAÇÃO DE SENHA =====

@email_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """🔑 Solicitar recuperação de senha via email"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados JSON necessários'}), 400
        
        email = data.get('email', '').strip()
        
        if not email or '@' not in email:
            return jsonify({'success': False, 'error': 'E-mail é obrigatório'}), 400
        
        print(f"🔑 Solicitação de reset para: {email}")
        
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
        print(f" Erro no forgot-password: {e}")
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500

@email_bp.route('/validate-reset-token', methods=['POST'])
def validate_reset_token():
    """🔍 Validar token de recuperação de senha"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados JSON necessários'}), 400
        
        token = data.get('token', '').strip()
        
        if not token:
            return jsonify({'success': False, 'error': 'Token é obrigatório'}), 400
        
        print(f"🔍 Validando token: {token[:20]}...")
        
        # Validar token
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

@email_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """ Redefinir senha com token válido"""
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
        
        print(f" Redefinindo senha com token: {token[:20]}...")
        
        # Redefinir senha
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

# ===== ROTAS DE CONFIRMAÇÃO DE EMAIL =====

@email_bp.route('/resend-confirmation', methods=['POST'])
def resend_confirmation():
    """📧 Reenviar email de confirmação"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        
        if not email:
            return jsonify({'success': False, 'error': 'Email é obrigatório'}), 400
        
        print(f"📧 Reenviando confirmação para: {email}")
        
        from database import get_db_connection
        
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
        
        # Gerar novo token de confirmação
        token_result = email_service.generate_confirmation_token(user_id, email)
        
        if not token_result['success']:
            return jsonify({'success': False, 'error': 'Erro ao gerar token'}), 500
        
        # Enviar email de confirmação
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

@email_bp.route('/confirm-email')
def confirm_email():
    """ Confirmar email com token (página HTML)"""
    from flask import render_template_string
    
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
    
    print(f" Confirmando email com token: {token[:20]}...")
    
    # Confirmar token
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
                <div class="success"></div>
                <h1>Email Confirmado!</h1>
                <p>Olá, <strong>{result['user_name']}</strong>!</p>
                <p>Seu email foi confirmado com sucesso. Agora você pode fazer login na plataforma.</p>
                
                <a href="/login" class="btn"> Fazer Login</a>
                <a href="/dashboard" class="btn"> Ir ao Dashboard</a>
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
                <div class="error"></div>
                <h1>Erro na Confirmação</h1>
                <p>{result['error']}</p>
                
                <a href="/login" class="btn">← Voltar ao Login</a>
                <a href="/register" class="btn">📝 Criar Nova Conta</a>
            </div>
        </body>
        </html>
        """), 400

# ===== ROTA DE DEBUG =====

@email_bp.route('/debug-user', methods=['POST'])
def debug_user():
    """🔍 Debug de usuário (apenas para desenvolvimento)"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip()
        
        if not email:
            return jsonify({'success': False, 'error': 'Email é obrigatório'}), 400
        
        # Chamar função de debug
        email_service.debug_user(email)
        
        return jsonify({
            'success': True,
            'message': 'Debug realizado - verifique console do servidor'
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== FUNÇÃO PARA RETORNAR BLUEPRINT =====

def get_email_blueprint():
    """Retornar blueprint para registrar no Flask"""
    return email_bp

if __name__ == "__main__":
    print("📧 Email Routes - Sistema completo de email")
    print("🔗 Rotas disponíveis:")
    print("  - POST /auth/forgot-password")
    print("  - POST /auth/validate-reset-token")
    print("  - POST /auth/reset-password")
    print("  - POST /auth/resend-confirmation")
    print("  - GET  /auth/confirm-email")
    print("  - POST /auth/debug-user")
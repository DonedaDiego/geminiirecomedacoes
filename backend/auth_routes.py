#auth_routes
from flask import Blueprint, request, jsonify, render_template_string
import jwt
import hashlib
from datetime import datetime, timezone, timedelta
from database import get_db_connection
from emails.email_service import email_service

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
    """✅ Registro SIMPLES"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados necessários'}), 400
        
        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        user_ip = request.remote_addr
        
        print(f"🔐 Registro: {email}")
        
        # Validações
        if not name or not email or not password:
            return jsonify({'success': False, 'error': 'Campos obrigatórios'}), 400
        
        if len(password) < 6:
            return jsonify({'success': False, 'error': 'Senha muito curta'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500

        cursor = conn.cursor()
        
        # Verificar email
        cursor.execute("SELECT id, email_confirmed FROM users WHERE email = %s", (email,))
        existing = cursor.fetchone()
        
        if existing:
            user_id, is_confirmed = existing
            
            if is_confirmed:
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'error': 'Email já cadastrado'}), 400
            else:
                print(f"📧 Reenviando confirmação")
                token_result = email_service.generate_confirmation_token(user_id, email)
                
                cursor.close()
                conn.close()
                return jsonify({
                    'success': True,
                    'message': 'Email de confirmação reenviado!',
                    'requires_confirmation': True
                }), 200
        
        # CRIAR USUÁRIO
        hashed_password = hash_password(password)
        now = datetime.now(timezone.utc)
        trial_end = now + timedelta(days=15)
        
        cursor.execute("""
            INSERT INTO users (
                name, email, password, ip_address,
                plan_id, plan_name, user_type,
                email_confirmed, email_confirmed_at,
                plan_expires_at, subscription_status,
                created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s,
                4, 'Community', 'trial',
                FALSE, NULL,
                %s, 'trial',
                %s, %s
            ) RETURNING id
        """, (name, email, hashed_password, user_ip, trial_end, now, now))
        
        user_id = cursor.fetchone()[0]
        conn.commit()
        
        print(f"✅ Usuário criado: ID {user_id}")
        
        # Gerar token
        token_result = email_service.generate_confirmation_token(user_id, email)
        
        if not token_result['success']:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Erro ao gerar token'}), 500
        
        # Tentar enviar (não quebrar se falhar)
        try:
            email_service.send_confirmation_email(name, email, token_result['token'])
        except Exception as e:
            print(f"⚠️ Erro ao enviar email: {e}")
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Conta criada! Verifique seu email.',
            'requires_confirmation': True,
            'data': {
                'user_id': user_id,
                'name': name,
                'email': email
            }
        }), 201
        
    except Exception as e:
        print(f"❌ ERRO: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== LOGIN SIMPLIFICADO =====

@auth_bp.route('/login', methods=['POST'])
def login():
    """✅ Login SIMPLES sem verificação de subscription"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados necessários'}), 400
        
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'success': False, 'error': 'Email e senha obrigatórios'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
        
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, email, password, plan_id, plan_name, user_type, 
                   email_confirmed, plan_expires_at, created_at
            FROM users WHERE email = %s
        """, (email,))
        
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Email não encontrado'}), 401
        
        user_id, name, user_email, stored_password, plan_id, plan_name, user_type, email_confirmed, plan_expires_at, created_at = user
        
        # Verificar senha
        if hash_password(password) != stored_password:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Senha incorreta'}), 401
        
        # Verificar confirmação
        if not email_confirmed:
            cursor.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Email não confirmado',
                'requires_confirmation': True
            }), 403
        
        # Atualizar último login
        cursor.execute("""
            UPDATE users 
            SET last_login = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (user_id,))
        conn.commit()
        
        # Verificar se trial expirou
        now = datetime.now(timezone.utc)
        trial_expired = False
        days_remaining = 0
        
        if user_type == 'trial' and plan_expires_at:
            trial_end = plan_expires_at.replace(tzinfo=timezone.utc)
            if now > trial_end:
                # Migrar para Free
                cursor.execute("""
                    UPDATE users 
                    SET plan_id = 3, plan_name = 'Free', user_type = 'regular',
                        plan_expires_at = NULL
                    WHERE id = %s
                """, (user_id,))
                conn.commit()
                
                plan_id = 3
                plan_name = 'Free'
                user_type = 'regular'
                trial_expired = True
            else:
                days_remaining = (trial_end - now).days
        
        cursor.close()
        conn.close()
        
        # Gerar token
        from flask import current_app
        token = generate_jwt_token(user_id, email, current_app.config['SECRET_KEY'])
        
        response = {
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
                    'email_confirmed': email_confirmed,
                    'created_at': created_at.isoformat() if created_at else None,
                    'trial_end_date': plan_expires_at.isoformat() if plan_expires_at and user_type == 'trial' else None
                },
                'token': token
            }
        }
        
        # Adicionar info de trial
        if user_type == 'trial' and not trial_expired:
            response['trial_info'] = {
                'is_trial': True,
                'days_remaining': days_remaining
            }
            response['message'] = f'Bem-vindo! {days_remaining} dias de trial restantes!'
        elif trial_expired:
            response['message'] = 'Trial expirado. Você tem acesso aos recursos básicos.'
        
        return jsonify(response), 200
        
    except Exception as e:
        print(f"❌ Erro no login: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== CONFIRMAÇÃO DE EMAIL =====

@auth_bp.route('/confirm-email')
def confirm_email_page():
    token = request.args.get('token')
    
    if not token:
        return render_template_string("""
        <!DOCTYPE html>
        <html><head><meta charset="UTF-8"><title>Erro</title></head>
        <body style="font-family:Arial;text-align:center;padding:50px">
            <h1>❌ Token não encontrado</h1>
            <a href="/login">Voltar</a>
        </body></html>
        """), 400
    
    result = email_service.confirm_email_token(token)
    
    if result['success']:
        return render_template_string(f"""
        <!DOCTYPE html>
        <html><head><meta charset="UTF-8"><title>Email Confirmado</title></head>
        <body style="font-family:Arial;text-align:center;padding:50px;background:#ba39af;color:white">
            <h1>✅ Email Confirmado!</h1>
            <p>Olá, {result['user_name']}!</p>
            <p>🎉 Trial de 15 dias ativado!</p>
            <a href="/login" style="background:white;color:#ba39af;padding:15px 30px;text-decoration:none;border-radius:10px;display:inline-block;margin-top:20px">Fazer Login</a>
        </body></html>
        """), 200
    else:
        return render_template_string(f"""
        <!DOCTYPE html>
        <html><head><meta charset="UTF-8"><title>Erro</title></head>
        <body style="font-family:Arial;text-align:center;padding:50px">
            <h1>❌ Erro</h1>
            <p>{result['error']}</p>
            <a href="/login">Voltar</a>
        </body></html>
        """), 400

# ===== VERIFY TOKEN =====

@auth_bp.route('/verify', methods=['GET'])
def verify_token():
    try:
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'error': 'Token não fornecido'}), 401
        
        token = auth_header.replace('Bearer ', '')
        
        from flask import current_app
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload['user_id']
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
        
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, email, plan_id, plan_name, user_type, 
                   email_confirmed, plan_expires_at, created_at
            FROM users WHERE id = %s
        """, (user_id,))
        
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Usuário não encontrado'}), 401
        
        user_id, name, email, plan_id, plan_name, user_type, email_confirmed, plan_expires_at, created_at = user
        
        cursor.close()
        conn.close()
        
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
                    'email_confirmed': email_confirmed,
                    'created_at': created_at.isoformat() if created_at else None
                }
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
    return jsonify({'success': True, 'message': 'Logout realizado'}), 200

def get_auth_blueprint():
    return auth_bp
from flask import Flask, jsonify, send_from_directory, request
import hashlib
import jwt
from datetime import datetime, timedelta, timezone
import psycopg2
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import secrets
from yfinance_service import YFinanceService
from database import get_db_connection
import requests

from admin_routes import get_admin_blueprint
from beta_routes import beta_bp
from long_short_routes import long_short_bp
from rsl_routes import get_rsl_blueprint
from recommendations_routes import get_recommendations_blueprint
from mercadopago_routes import get_mercadopago_blueprint

from dotenv import load_dotenv

load_dotenv()

# ===== CONFIGURAÇÃO DO FLASK =====
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'geminii-secret-2024')

# Configuração de Email
app.config['MAIL_SERVER'] = 'smtp.titan.email'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = os.environ.get('EMAIL_USER', 'contato@geminii.com.br')
app.config['MAIL_PASSWORD'] = os.environ.get('EMAIL_PASSWORD', '#Giminii#')

# ===== CONFIGURAÇÃO MERCADO PAGO =====
MP_AVAILABLE = False
mercadopago_bp = None

try:
    mercadopago_bp = get_mercadopago_blueprint()
    MP_AVAILABLE = True
    print("✅ Blueprint Mercado Pago carregado com sucesso!")
except ImportError as e:
    print(f"⚠️ Mercado Pago não disponível: {e}")
except Exception as e:
    print(f"❌ Erro ao carregar Mercado Pago: {e}")

# REGISTRAR BLUEPRINTS
app.register_blueprint(beta_bp)
app.register_blueprint(long_short_bp)
rsl_bp = get_rsl_blueprint()
app.register_blueprint(rsl_bp)
admin_bp = get_admin_blueprint()
app.register_blueprint(admin_bp)
recommendations_bp = get_recommendations_blueprint()
app.register_blueprint(recommendations_bp)

# Registrar blueprint do Mercado Pago apenas se disponível
if MP_AVAILABLE and mercadopago_bp:
    app.register_blueprint(mercadopago_bp)
    print("✅ Blueprint Mercado Pago registrado!")

# ===== FUNÇÕES AUXILIARES =====

def hash_password(password):
    """Criptografar senha"""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_reset_token():
    """Gerar token seguro para reset"""
    return secrets.token_urlsafe(32)

def send_reset_email(user_email, user_name, reset_token):
    """Enviar email de reset de senha - SMTP nativo"""
    try:
        smtp_server = "smtp.titan.email"
        smtp_port = 465
        smtp_user = os.environ.get('EMAIL_USER')
        smtp_password = os.environ.get('EMAIL_PASSWORD')
        
        if not smtp_user or not smtp_password:
            print("Variáveis de email não configuradas")
            return False
        
        reset_url = f"https://geminii-tech.onrender.com/reset-password?token={reset_token}"
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = "Redefinir Senha - Geminii Tech"
        msg['From'] = smtp_user
        msg['To'] = user_email
        
        html_body = f"""
        <div style="font-family: Inter, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #ba39af, #d946ef); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0;">Geminii Tech</h1>
                <p style="color: white; margin: 10px 0 0 0;">Trading Automatizado</p>
            </div>
            <div style="padding: 30px; background: #f8f9fa;">
                <h2 style="color: #333;">Olá, {user_name}!</h2>
                <p style="color: #666; line-height: 1.6;">
                    Recebemos uma solicitação para redefinir a senha da sua conta Geminii Tech.
                </p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_url}" 
                       style="background: linear-gradient(135deg, #ba39af, #d946ef); 
                              color: white; padding: 15px 30px; text-decoration: none; 
                              border-radius: 8px; display: inline-block; font-weight: bold;">
                        Redefinir Senha
                    </a>
                </div>
                <p style="color: #666; font-size: 14px;">
                    <strong>Este link expira em 1 hora.</strong><br>
                    Se você não solicitou isso, ignore este email.
                </p>
            </div>
            <div style="padding: 20px; text-align: center; background: #333; color: white;">
                <p style="margin: 0;">© 2025 Geminii Research - Trading Automatizado</p>
            </div>
        </div>
        """
        
        msg.attach(MIMEText(html_body, 'html'))
        
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        
        print(f"Email enviado para: {user_email}")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao enviar email: {e}")
        return False

def generate_reset_token_db(email):
    """Gerar token de reset e salvar no banco"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            return {'success': False, 'error': 'E-mail não encontrado'}
        
        user_id, user_name = user
        token = generate_reset_token()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        cursor.execute("""
            UPDATE password_reset_tokens 
            SET used = TRUE 
            WHERE user_id = %s AND used = FALSE
        """, (user_id,))
        
        cursor.execute("""
            INSERT INTO password_reset_tokens (user_id, token, expires_at) 
            VALUES (%s, %s, %s)
        """, (user_id, token, expires_at))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'token': token,
            'user_name': user_name,
            'user_email': email,
            'expires_in': '1 hora'
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Erro interno: {str(e)}'}

def validate_reset_token_db(token):
    """Validar token de reset"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rt.user_id, rt.expires_at, u.name, u.email 
            FROM password_reset_tokens rt
            JOIN users u ON rt.user_id = u.id
            WHERE rt.token = %s AND rt.used = FALSE
        """, (token,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not result:
            return {'success': False, 'error': 'Token inválido ou já utilizado'}
        
        user_id, expires_at, user_name, user_email = result
        
        if datetime.now(timezone.utc) > expires_at.replace(tzinfo=timezone.utc):
            return {'success': False, 'error': 'Token expirado'}
        
        return {
            'success': True,
            'user_id': user_id,
            'user_name': user_name,
            'email': user_email,
            'expires_at': expires_at.isoformat()
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Erro interno: {str(e)}'}

def reset_password_db(token, new_password):
    """Redefinir senha com token"""
    try:
        validation = validate_reset_token_db(token)
        if not validation['success']:
            return validation
        
        user_id = validation['user_id']
        user_name = validation['user_name']
        
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        
        hashed_password = hash_password(new_password)
        cursor.execute("""
            UPDATE users 
            SET password = %s, updated_at = CURRENT_TIMESTAMP 
            WHERE id = %s
        """, (hashed_password, user_id))
        
        cursor.execute("""
            UPDATE password_reset_tokens 
            SET used = TRUE 
            WHERE token = %s
        """, (token,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'message': 'Senha redefinida com sucesso!',
            'user_name': user_name
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Erro interno: {str(e)}'}

def initialize_database():
    """Inicializar banco se necessário"""
    try:
        from database import setup_enhanced_database
        setup_enhanced_database()
        print("✅ Banco enhanced verificado/criado com sucesso!")
        
        # Inicializar Mercado Pago se disponível
        if MP_AVAILABLE:
            from mercadopago_routes import create_payments_table, add_plan_expires_field
            create_payments_table()
            add_plan_expires_field()
            
    except Exception as e:
        print(f"⚠️ Erro ao verificar banco: {e}")

# ===== ROTAS HTML =====

@app.route('/')
def home():
    return send_from_directory('../frontend', 'index.html')

@app.route('/dashboard')
@app.route('/dashboard.html')
def dashboard():
    return send_from_directory('../frontend', 'dashboard.html')

@app.route('/login')
@app.route('/login.html')
def login_page():
    return send_from_directory('../frontend', 'login.html')

@app.route('/register')
@app.route('/register.html')
def register_page():
    return send_from_directory('../frontend', 'register.html')

@app.route('/forgot-password')
@app.route('/forgot-password.html')
def forgot_password_page():
    return send_from_directory('../frontend', 'forgot-password.html')

@app.route('/reset-password')
@app.route('/reset-password.html')
def reset_password_page():
    return send_from_directory('../frontend', 'reset-password.html')

@app.route('/planos')
@app.route('/planos.html')
def planos():
    return send_from_directory('../frontend', 'planos.html')

@app.route('/sobre')
@app.route('/sobre.html')
def sobre():
    return send_from_directory('../frontend', 'sobre.html')

@app.route('/monitor-basico')
@app.route('/monitor-basico.html')
def monitor_basico():
    try:
        return send_from_directory('../frontend', 'monitor-basico.html')
    except:
        return "<h1>Monitor Básico - Em construção</h1>"

@app.route('/rsl')
@app.route('/rsl.html')
def rsl_page():
    return send_from_directory('../frontend', 'rsl.html')

@app.route('/Long-Short')
@app.route('/long-short.html')
def long_short():
    return send_from_directory('../frontend', 'long-short.html')

@app.route('/relatorios')
@app.route('/relatorios.html')
def relatorios():
    return send_from_directory('../frontend', 'relatorios.html') if os.path.exists('../frontend/relatorios.html') else "<h1>Relatórios - Em construção</h1>"

# Servir assets
@app.route('/logo.png')
def serve_logo():
    return send_from_directory('../frontend', 'logo.png')

@app.route('/assets/logo.png')
def serve_logo_assets():
    return send_from_directory('../frontend', 'logo.png')

@app.route('/admin-dashboard') 
@app.route('/admin-dashboard.html')
def admin_dashboard():
    return send_from_directory('../frontend', 'admin-dashboard.html')

# ===== PÁGINAS DE RETORNO DO PAGAMENTO =====

@app.route('/payment/success')
def payment_success():
    """Página de sucesso do pagamento"""
    payment_id = request.args.get('payment_id')
    status_param = request.args.get('status')
    external_reference = request.args.get('external_reference')
    
    print(f"✅ Pagamento aprovado - ID: {payment_id}")
    
    return f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Pagamento Aprovado - Geminii</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>body {{ font-family: 'Inter', sans-serif; }}</style>
    </head>
    <body class="bg-gray-900 text-white min-h-screen">
        <div class="min-h-screen flex items-center justify-center p-4">
            <div class="text-center p-8 bg-gray-800 rounded-lg max-w-md w-full border border-gray-700">
                <div class="text-6xl mb-6">✅</div>
                <h1 class="text-3xl font-bold mb-4 text-green-400">Pagamento Aprovado!</h1>
                
                <div id="status-check" class="mb-6">
                    <div class="text-yellow-400 mb-2">🔄 Ativando sua assinatura...</div>
                    <div class="w-full bg-gray-700 rounded-full h-2">
                        <div id="progress-bar" class="bg-green-600 h-2 rounded-full transition-all duration-1000" style="width: 0%"></div>
                    </div>
                </div>
                
                <p class="text-gray-300 mb-6 leading-relaxed">
                    Parabéns! Sua assinatura está sendo ativada.
                </p>
                
                <div class="space-y-3">
                    <button onclick="checkAndRedirect()" 
                            class="w-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 px-6 py-3 rounded-lg font-medium transition-colors">
                        Ir para Dashboard
                    </button>
                    <button onclick="window.location.href='/'" 
                            class="w-full bg-gray-600 hover:bg-gray-700 px-6 py-3 rounded-lg font-medium transition-colors">
                        Voltar ao Início
                    </button>
                </div>
            </div>
        </div>
        
        <script>
            let checkCount = 0;
            const maxChecks = 12;
            
            function updateProgress() {{
                const progress = (checkCount / maxChecks) * 100;
                document.getElementById('progress-bar').style.width = progress + '%';
            }}
            
            function checkPaymentStatus() {{
                if (checkCount >= maxChecks) {{
                    document.getElementById('status-check').innerHTML = 
                        '<div class="text-green-400">✅ Ativação concluída!</div>';
                    return;
                }}
                
                const paymentId = '{payment_id}';
                if (!paymentId) return;
                
                fetch(`/api/mercadopago/payment/status/${{paymentId}}`)
                    .then(response => response.json())
                    .then(data => {{
                        updateProgress();
                        
                        if (data.success && data.data.status === 'approved') {{
                            document.getElementById('status-check').innerHTML = 
                                '<div class="text-green-400">✅ Assinatura ativada com sucesso!</div>';
                            return;
                        }}
                        
                        checkCount++;
                        if (checkCount < maxChecks) {{
                            setTimeout(checkPaymentStatus, 5000);
                        }}
                    }})
                    .catch(error => {{
                        console.error('Erro:', error);
                        checkCount++;
                        if (checkCount < maxChecks) {{
                            setTimeout(checkPaymentStatus, 5000);
                        }}
                    }});
            }}
            
            function checkAndRedirect() {{
                setTimeout(() => {{
                    window.location.href = '/dashboard';
                }}, 1000);
            }}
            
            setTimeout(checkPaymentStatus, 2000);
        </script>
    </body>
    </html>
    """

@app.route('/payment/pending') 
def payment_pending():
    """Página de pagamento pendente"""
    return """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Pagamento Pendente - Geminii</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-900 text-white min-h-screen">
        <div class="min-h-screen flex items-center justify-center p-4">
            <div class="text-center p-8 bg-gray-800 rounded-lg max-w-md w-full border border-gray-700">
                <div class="text-6xl mb-6">⏳</div>
                <h1 class="text-3xl font-bold mb-4 text-yellow-400">Pagamento Pendente</h1>
                <p class="text-gray-300 mb-6">Seu pagamento está sendo processado.</p>
                <button onclick="window.location.href='/'" 
                        class="w-full bg-gray-600 hover:bg-gray-700 px-6 py-3 rounded-lg">
                    Voltar ao Início
                </button>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/payment/failure')
def payment_failure():
    """Página de falha no pagamento"""
    return """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Pagamento Falhou - Geminii</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-900 text-white min-h-screen">
        <div class="min-h-screen flex items-center justify-center p-4">
            <div class="text-center p-8 bg-gray-800 rounded-lg max-w-md w-full border border-gray-700">
                <div class="text-6xl mb-6">❌</div>
                <h1 class="text-3xl font-bold mb-4 text-red-400">Pagamento Falhou</h1>
                <p class="text-gray-300 mb-6">Houve um problema. Tente novamente.</p>
                <button onclick="window.location.href='/planos'" 
                        class="w-full bg-gradient-to-r from-purple-600 to-pink-600 px-6 py-3 rounded-lg">
                    Tentar Novamente
                </button>
            </div>
        </div>
    </body>
    </html>
    """

# ===== ROTAS API BÁSICAS =====

@app.route('/api/status')
def status():
    """Status da API com info do Mercado Pago"""
    mp_status = {"success": MP_AVAILABLE, "message": "Blueprint carregado" if MP_AVAILABLE else "Não disponível"}
    
    return jsonify({
        'message': 'API Flask Online!',
        'status': 'online',
        'database': 'Connected',
        'mercadopago': mp_status
    })

@app.route('/api/test-db')
def test_db():
    """Testar conexão com banco"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM plans")
            plans_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM users") 
            users_count = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': 'Banco conectado!',
                'data': {
                    'plans': plans_count,
                    'users': users_count
                }
            })
        else:
            return jsonify({'success': False, 'error': 'Falha na conexão'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== ROTAS DE COMPATIBILIDADE =====

@app.route('/api/plans')
def get_plans_compat():
    """Rota de compatibilidade para planos - redireciona para blueprint"""
    if MP_AVAILABLE:
        from mercadopago_routes import PLANS
        
        plans_list = []
        for plan_id, plan_data in PLANS.items():
            plans_list.append({
                "id": plan_data["id"],
                "name": plan_id,
                "display_name": plan_data["name"],
                "description": plan_data["description"],
                "price_monthly": plan_data["monthly_price"],
                "price_annual": plan_data["annual_price"],
                "features": plan_data["features"]
            })
        
        return jsonify({"success": True, "data": plans_list})
    else:
        return jsonify({"success": False, "error": "Mercado Pago não disponível"}), 500

@app.route('/api/checkout/create', methods=['POST'])
def create_checkout_compat():
    """Rota de compatibilidade para checkout - redireciona para blueprint"""
    if not MP_AVAILABLE:
        return jsonify({"success": False, "error": "Mercado Pago não disponível"}), 500
    
    try:
        from mercadopago_routes import create_checkout_function
        return create_checkout_function()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

# ===== WEBHOOK PRINCIPAL =====

@app.route('/webhook/mercadopago', methods=['POST'])
def mercadopago_webhook():
    """Webhook principal - redireciona para blueprint"""
    if not MP_AVAILABLE:
        return jsonify({"success": False, "error": "Mercado Pago não disponível"}), 500
    
    try:
        from mercadopago_routes import webhook
        return webhook()
        
    except Exception as e:
        print(f"❌ Erro no webhook principal: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ===== ROTAS DE AUTENTICAÇÃO =====

@app.route('/api/dashboard')
def dashboard_api():
    """API para dados do dashboard"""
    try:
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'error': 'Token não fornecido'}), 401
        
        token = auth_header.replace('Bearer ', '')
        
        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            user_id = payload['user_id']
            
            conn = get_db_connection()
            if not conn:
                return jsonify({'success': False, 'error': 'Erro de conexão com banco'}), 500
            
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, email, plan_id, plan_name, created_at
                FROM users WHERE id = %s
            """, (user_id,))
            
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not user:
                return jsonify({'success': False, 'error': 'Usuário não encontrado'}), 401
            
            user_id, name, email, plan_id, plan_name, created_at = user
            
            return jsonify({
                'success': True,
                'data': {
                    'user': {
                        'id': user_id,
                        'name': name,
                        'email': email,
                        'plan_id': plan_id,
                        'plan_name': plan_name,
                        'member_since': created_at.strftime('%d/%m/%Y') if created_at else 'Hoje'
                    },
                    'stats': {
                        'total_analysis': 0,
                        'active_alerts': 0,
                        'watchlist_items': 3
                    }
                }
            })
            
        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'error': 'Token expirado'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'success': False, 'error': 'Token inválido'}), 401
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Registrar novo usuário"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados JSON necessários'}), 400
        
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        if not name or not email or not password:
            return jsonify({'success': False, 'error': 'Nome, e-mail e senha são obrigatórios'}), 400
        
        if len(password) < 6:
            return jsonify({'success': False, 'error': 'Senha deve ter pelo menos 6 caracteres'}), 400
        
        if '@' not in email:
            return jsonify({'success': False, 'error': 'E-mail inválido'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão com banco'}), 500
        
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'E-mail já cadastrado'}), 400
        
        hashed_password = hash_password(password)
        cursor.execute("""
            INSERT INTO users (name, email, password, plan_id, plan_name, created_at) 
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        """, (name, email, hashed_password, 1, 'Básico', datetime.now(timezone.utc)))
        
        user_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Usuário criado com sucesso!',
            'data': {
                'user_id': user_id,
                'name': name,
                'email': email,
                'plan_name': 'Básico'
            }
        }), 201
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login do usuário"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados JSON necessários'}), 400
        
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'success': False, 'error': 'E-mail e senha são obrigatórios'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão com banco'}), 500
        
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, email, password, plan_id, plan_name, user_type 
            FROM users WHERE email = %s
        """, (email,))
        
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user:
            return jsonify({'success': False, 'error': 'E-mail não encontrado'}), 401
        
        user_id, name, email, stored_password, plan_id, plan_name, user_type = user
        
        if hash_password(password) != stored_password:
            return jsonify({'success': False, 'error': 'Senha incorreta'}), 401
        
        token_payload = {
            'user_id': user_id,
            'email': email,
            'exp': datetime.now(timezone.utc) + timedelta(days=7)
        }
        
        token = jwt.encode(token_payload, app.config['SECRET_KEY'], algorithm='HS256')
        
        return jsonify({
            'success': True,
            'message': 'Login realizado com sucesso!',
            'data': {
                'user': {
                    'id': user_id,
                    'name': name,
                    'email': email,
                    'plan_id': plan_id,
                    'plan_name': plan_name,
                    'user_type': user_type
                },
                'token': token
            }
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500

@app.route('/api/auth/verify', methods=['GET'])
def verify_token():
    """Verificar se token é válido"""
    try:
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'error': 'Token não fornecido'}), 401
        
        token = auth_header.replace('Bearer ', '')
        
        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            user_id = payload['user_id']
            
            conn = get_db_connection()
            if not conn:
                return jsonify({'success': False, 'error': 'Erro de conexão com banco'}), 500
            
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, name, email, plan_id, plan_name, user_type 
                FROM users WHERE id = %s
            """, (user_id,))
            
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not user:
                return jsonify({'success': False, 'error': 'Usuário não encontrado'}), 401
            
            user_id, name, email, plan_id, plan_name, user_type = user
            
            return jsonify({
                'success': True,
                'data': {
                    'user': {
                        'id': user_id,
                        'name': name,
                        'email': email,
                        'plan_id': plan_id,
                        'plan_name': plan_name,
                        'user_type': user_type
                    }
                }
            })
            
        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'error': 'Token expirado'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'success': False, 'error': 'Token inválido'}), 401
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Logout do usuário"""
    try:
        return jsonify({
            'success': True,
            'message': 'Logout realizado com sucesso!'
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500

@app.route('/api/force-admin')
def force_admin():
    """Temporário - forçar admin"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE users 
            SET user_type = 'admin', plan_id = 3, plan_name = 'Estratégico'
            WHERE email = 'diego@geminii.com.br'
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Admin forçado!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ===== ROTAS DE RECUPERAÇÃO DE SENHA =====

@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    """Solicitar recuperação de senha"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados JSON necessários'}), 400
        
        email = data.get('email', '').strip()
        
        if not email or '@' not in email:
            return jsonify({'success': False, 'error': 'E-mail é obrigatório'}), 400
        
        result = generate_reset_token_db(email)
        
        if result['success']:
            email_sent = send_reset_email(
                result['user_email'], 
                result['user_name'], 
                result['token']
            )
            
            if email_sent:
                return jsonify({
                    'success': True,
                    'message': 'E-mail de recuperação enviado!'
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': 'Erro ao enviar e-mail. Tente novamente.'
                }), 500
        else:
            return jsonify(result), 400
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500

@app.route('/api/auth/validate-reset-token', methods=['POST'])
def validate_reset():
    """Validar token de recuperação"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados JSON necessários'}), 400
        
        token = data.get('token', '').strip()
        
        if not token:
            return jsonify({'success': False, 'error': 'Token é obrigatório'}), 400
        
        result = validate_reset_token_db(token)
        
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
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500

@app.route('/api/auth/reset-password', methods=['POST'])
def reset_password_api():
    """Redefinir senha com token"""
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
        
        result = reset_password_db(token, new_password)
        
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
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500

@app.route('/api/dashboard/recommendations')
def get_portfolio_recommendations():
    """Buscar recomendações de carteira com dados do YFinance"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'error': 'Token não fornecido'}), 401
        
        token = auth_header.replace('Bearer ', '')
        
        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            user_id = payload['user_id']
        except jwt.InvalidTokenError:
            return jsonify({'success': False, 'error': 'Token inválido'}), 401
        
        # Parâmetros da requisição
        portfolio_name = request.args.get('portfolio', 'smart_bdr')
        limit = int(request.args.get('limit', 10))
        
        from database import get_portfolio_assets
        assets = get_portfolio_assets(portfolio_name)
        
        if not assets:
            return jsonify({
                'success': False,
                'error': f'Nenhum ativo encontrado na carteira {portfolio_name}'
            }), 404
        
        # Buscar dados dos ativos usando YFinance
        from yfinance_service import YFinanceService
        
        recommendations = []
        total_performance = 0
        signals = {'compras': 0, 'vendas': 0, 'manter': 0}
        
        for asset in assets[:limit]:
            try:
                # Buscar dados atuais do ativo
                stock_data = YFinanceService.get_stock_data(asset['ticker'])
                
                if stock_data['success']:
                    stock_info = stock_data['data']
                    
                    # Simular dados de entrada (preço de 30 dias atrás)
                    current_price = stock_info['current_price']
                    entry_price = current_price * 0.95  # Simular entrada 5% abaixo
                    
                    # Calcular performance
                    performance = ((current_price - entry_price) / entry_price) * 100
                    total_performance += performance * (asset['weight'] / 100)
                    
                    # Gerar recomendação baseada na performance
                    if performance > 5:
                        recommendation = "Venda"
                        signals['vendas'] += 1
                    elif performance < -3:
                        recommendation = "Compra Forte"
                        signals['compras'] += 1
                    elif performance < 0:
                        recommendation = "Compra"
                        signals['compras'] += 1
                    else:
                        recommendation = "Manter"
                        signals['manter'] += 1
                    
                    # Adicionar ícone baseado no setor
                    sector_icons = {
                        'Tecnologia': '💻',
                        'Financeiro': '🏦',
                        'Saúde': '🏥',
                        'Energia': '⚡',
                        'Consumo': '🛒',
                        'Industrial': '🏭',
                        'default': '📈'
                    }
                    
                    icon = sector_icons.get(asset['sector'], sector_icons['default'])
                    
                    recommendation_data = {
                        'ticker': asset['ticker'],
                        'setor': asset['sector'],
                        'icone': icon,
                        'recomendacao': recommendation,
                        'entrada': {
                            'preco': entry_price,
                            'data': (datetime.now() - timedelta(days=30)).strftime('%d/%m/%Y'),
                            'peso_percent': asset['weight']
                        },
                        'atual': {
                            'preco': current_price,
                            'data': datetime.now().strftime('%d/%m/%Y')
                        },
                        'performance': {
                            'valor': performance,
                            'dias': 30
                        },
                        'fundamentals': {
                            'sharpe': round(performance / 10, 2) if performance != 0 else 0,
                            'volatilidade': stock_info.get('beta', 1.0)
                        }
                    }
                    
                    recommendations.append(recommendation_data)
                    
            except Exception as e:
                print(f"Erro ao processar {asset['ticker']}: {e}")
                continue
        
        # Calcular estatísticas
        total_stocks = len(recommendations)
        avg_performance = total_performance / total_stocks if total_stocks > 0 else 0
        
        response_data = {
            'success': True,
            'data': {
                'recommendations': {
                    'recommendations': recommendations,
                    'last_update': datetime.now().strftime('%d/%m/%Y %H:%M'),
                    'portfolio': portfolio_name
                },
                'statistics': {
                    'total_stocks': total_stocks,
                    'avg_performance': round(avg_performance, 2),
                    'signals': signals
                }
            }
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Erro em get_portfolio_recommendations: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor'
        }), 500

# ===== ROTAS DE AÇÕES (YFINANCE) =====

@app.route('/api/stock/<symbol>')
def get_stock_data(symbol):
    """Buscar dados de uma ação"""
    result = YFinanceService.get_stock_data(symbol)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 404

@app.route('/api/stocks')
def get_multiple_stocks():
    """Buscar dados de múltiplas ações"""
    symbols_param = request.args.get('symbols', 'PETR4,VALE3,ITUB4,BBDC4')
    symbols = [s.strip().upper() for s in symbols_param.split(',')]
    
    result = YFinanceService.get_multiple_stocks(symbols)
    return jsonify(result)

@app.route('/api/stock/<symbol>/history')
def get_stock_history(symbol):
    """Buscar histórico de uma ação"""
    period = request.args.get('period', '1mo')
    
    result = YFinanceService.get_stock_history(symbol, period)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 404

@app.route('/api/stocks/search')
def search_stocks():
    """Buscar ações por nome ou símbolo"""
    query = request.args.get('q', '')
    limit = int(request.args.get('limit', 10))
    
    if not query:
        return jsonify({
            'success': False,
            'error': 'Parâmetro q (query) é obrigatório'
        }), 400
    
    result = YFinanceService.search_stocks(query, limit)
    return jsonify(result)

# ===== EXECUTAR EM PRODUÇÃO =====

# if __name__ == '__main__':
#     # FORÇAR MODO LOCAL
#     print("🏠 FORÇANDO MODO DESENVOLVIMENTO LOCAL...")
    
#     # Remover DATABASE_URL para forçar banco local
#     if 'DATABASE_URL' in os.environ:
#         del os.environ['DATABASE_URL']
#         print("✅ DATABASE_URL removida - usando banco local")
    
#     # Configurar ambiente local
#     os.environ['FLASK_ENV'] = 'development'
#     os.environ['DB_HOST'] = 'localhost'
#     os.environ['DB_NAME'] = 'postgres'
#     os.environ['DB_USER'] = 'postgres'
#     os.environ['DB_PASSWORD'] = '#geminii'
#     os.environ['DB_PORT'] = '5432'
    
#     port = int(os.environ.get('PORT', 5000))
    
#     # Só mostrar diagnóstico uma vez
#     if not os.environ.get('WERKZEUG_RUN_MAIN'):
#         print("🔍 DIAGNÓSTICO DE CONEXÃO:")
#         print(f"DATABASE_URL existe: {'✅' if os.environ.get('DATABASE_URL') else '❌'}")
#         print(f"Modo: {'RENDER' if os.environ.get('DATABASE_URL') else 'LOCAL'}")
#         print("🏠 Configurações locais:")
#         print(f"  Host: {os.environ.get('DB_HOST')}")
#         print(f"  Database: {os.environ.get('DB_NAME')}")
#         print(f"  User: {os.environ.get('DB_USER')}")
#         print(f"  Password: ***")
#         print(f"  Port: {os.environ.get('DB_PORT')}")
        
#         print("🚀 Iniciando Geminii API (DESENVOLVIMENTO)...")
#         print("📊 APIs disponíveis em http://localhost:5000")
#         print(f"🛒 Mercado Pago: {'✅ ATIVO' if MP_AVAILABLE else '❌ INATIVO'}")
    
#     # Inicializar banco apenas uma vez
#     if not os.environ.get('WERKZEUG_RUN_MAIN'):
#         initialize_database()

#     app.run(host='0.0.0.0', port=port, debug=True)


def create_app():
    """Factory para criar app - Railway"""
    if os.environ.get('RAILWAY_ENVIRONMENT'):
        print("🚄 Executando no Railway...")
        app.config['ENV'] = 'production'
        app.config['DEBUG'] = False
    
    initialize_database()
    return app
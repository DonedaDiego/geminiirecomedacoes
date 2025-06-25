# main.py - CORREÇÃO PARA O ERRO DO ADMIN BLUEPRINT

from flask import Flask, jsonify, send_from_directory, request
from flask import send_from_directory
import time
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

from beta_routes import beta_bp
from long_short_routes import long_short_bp
from rsl_routes import get_rsl_blueprint
from recommendations_routes import get_recommendations_blueprint
from mercadopago_routes import get_mercadopago_blueprint
from opcoes_routes import opcoes_bp
from swing_trade_ml_routes import swing_trade_ml_bp
from swing_trade_ml_routes import get_swing_trade_ml_blueprint
from beta_regression_routes import beta_regression_bp
from atsmom_routes import register_atsmom_routes
from chart_ativos_routes import chart_ativos_bp
from carrossel_yfinance_routes import get_carrossel_blueprint
from dotenv import load_dotenv

load_dotenv()
if not os.getenv('JWT_SECRET'):
    os.environ['JWT_SECRET'] = 'geminii-jwt-secret-key-2024'
    print("⚠️ JWT_SECRET forçado manualmente")

# Debug
print(f"JWT_SECRET final: {os.getenv('JWT_SECRET', 'AINDA NÃO ENCONTRADO')}")
print(f"OPLAB_TOKEN: {os.getenv('OPLAB_TOKEN', 'NÃO ENCONTRADO')}")

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

# ===== CONFIGURAÇÃO ADMIN BLUEPRINT - CORREÇÃO =====
ADMIN_AVAILABLE = False
admin_bp = None

try:
    from admin_routes import get_admin_blueprint
    admin_bp = get_admin_blueprint()
    ADMIN_AVAILABLE = True
    print("✅ Blueprint Admin carregado com sucesso!")
except ImportError as e:
    print(f"⚠️ Admin routes não disponível: {e}")
    print("📝 Criando funções admin básicas...")
    ADMIN_AVAILABLE = False
except Exception as e:
    print(f"❌ Erro ao carregar admin blueprint: {e}")
    print("📝 Continuando sem funcionalidades admin...")
    ADMIN_AVAILABLE = False

# REGISTRAR BLUEPRINTS BÁSICOS
app.register_blueprint(opcoes_bp)
app.register_blueprint(beta_bp)
app.register_blueprint(long_short_bp)
rsl_bp = get_rsl_blueprint()
app.register_blueprint(rsl_bp)
recommendations_bp = get_recommendations_blueprint()
app.register_blueprint(recommendations_bp)
app.register_blueprint(get_swing_trade_ml_blueprint())
app.register_blueprint(beta_regression_bp, url_prefix='/beta_regression')
app.register_blueprint(chart_ativos_bp)
register_atsmom_routes(app)

# Registrar blueprint do Mercado Pago apenas se disponível
if MP_AVAILABLE and mercadopago_bp:
    app.register_blueprint(mercadopago_bp)
    print("✅ Blueprint Mercado Pago registrado!")

# ✅ REGISTRAR ADMIN BLUEPRINT APENAS SE DISPONÍVEL E SEM CONFLITOS
if ADMIN_AVAILABLE and admin_bp:
    try:
        app.register_blueprint(admin_bp)
        print("✅ Blueprint Admin registrado com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao registrar admin blueprint: {e}")
        print("⚠️ Continuando sem painel admin...")
        ADMIN_AVAILABLE = False

CARROSSEL_AVAILABLE = False
carrossel_bp = None

try:
    carrossel_bp = get_carrossel_blueprint()
    CARROSSEL_AVAILABLE = True
    print("✅ Blueprint Carrossel YFinance carregado com sucesso!")
except ImportError as e:
    print(f"⚠️ Carrossel não disponível: {e}")
    CARROSSEL_AVAILABLE = False
except Exception as e:
    print(f"❌ Erro ao carregar Carrossel: {e}")
    CARROSSEL_AVAILABLE = False



if CARROSSEL_AVAILABLE and carrossel_bp:
    try:
        app.register_blueprint(carrossel_bp)
        print("✅ Blueprint Carrossel registrado com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao registrar carrossel blueprint: {e}")
        print("⚠️ Continuando sem carrossel...")
        CARROSSEL_AVAILABLE = False

# ===== RESTO DO CÓDIGO PERMANECE IGUAL =====

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

@app.route('/politica-de-privacidade')
@app.route('/politica-de-privacidade.html')
def politica_privacidade():
    return send_from_directory('../frontend', 'politica-de-privacidade.html')

@app.route('/termos-de-uso')
@app.route('/termos-de-uso.html')
def termos_uso():
    return send_from_directory('../frontend', 'termos-de-uso.html')

@app.route('/analises')
@app.route('/analises.html')
def analises():
    return send_from_directory('../frontend', 'analises.html')

@app.route('/relatorios')
@app.route('/relatorios.html')
def relatorios():
    try:
        return send_from_directory('../frontend', 'relatorios.html')
    except:
        return "<h1>Relatórios - Em construção</h1>"
    
@app.route('/opcoes')
@app.route('/opcoes.html')
def opcoes_page():
    return send_from_directory('../frontend', 'opcoes.html')   

@app.route('/swing-trade-machine-learning')
@app.route('/swing-trade-machine-learning.html')
def swing_trade_ml_page():
    return send_from_directory('../frontend', 'swing-trade-machine-learning.html')  

@app.route('/beta-regression')
@app.route('/beta-regression.html')
def beta_regression_page():
    return send_from_directory('../frontend', 'beta-regression.html')

@app.route('/atsmom.html')
def atsmom_page():
    return send_from_directory('../frontend', 'atsmom.html')

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
    """Status da API com info do Mercado Pago e Carrossel"""
    mp_status = {"success": MP_AVAILABLE, "message": "Blueprint carregado" if MP_AVAILABLE else "Não disponível"}
    admin_status = {"success": ADMIN_AVAILABLE, "message": "Blueprint carregado" if ADMIN_AVAILABLE else "Não disponível"}
    carrossel_status = {"success": CARROSSEL_AVAILABLE, "message": "Blueprint carregado" if CARROSSEL_AVAILABLE else "Não disponível"}
    
    return jsonify({
        'message': 'API Flask Online!',
        'status': 'online',
        'database': 'Connected',
        'mercadopago': mp_status,
        'admin': admin_status,
        'carrossel': carrossel_status  # ← NOVA LINHA
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

# @app.route('/webhook/mercadopago', methods=['POST'])
# def mercadopago_webhook():
#     """Webhook principal - redireciona para blueprint"""
#     if not MP_AVAILABLE:
#         return jsonify({"success": False, "error": "Mercado Pago não disponível"}), 500
    
#     try:
#         from mercadopago_routes import webhook
#         return webhook()
        
#     except Exception as e:
#         print(f"❌ Erro no webhook principal: {e}")
#         return jsonify({"success": False, "error": str(e)}), 500



@app.route('/webhook/mercadopago', methods=['POST'])
def mercadopago_webhook():
    """Webhook principal - redireciona para blueprint"""
    
    # 🔔 LOG INICIAL
    print(f"\n{'='*60}")
    print(f"🔔 WEBHOOK MERCADO PAGO CHAMADO! - {datetime.now()}")
    print(f"{'='*60}")
    
    # 📊 LOG DOS HEADERS
    print(f"📊 HEADERS RECEBIDOS:")
    for key, value in request.headers:
        print(f"   {key}: {value}")
    
    # 📦 LOG DOS DADOS
    try:
        data = request.get_json()
        print(f"📦 DADOS JSON RECEBIDOS:")
        print(f"   {data}")
    except Exception as e:
        print(f"❌ Erro ao ler JSON: {e}")
        print(f"📦 RAW DATA: {request.data}")
    
    # ✅ VERIFICAR MP_AVAILABLE
    print(f"🔧 MP_AVAILABLE: {MP_AVAILABLE}")
    
    if not MP_AVAILABLE:
        print(f"❌ Mercado Pago não disponível!")
        return jsonify({"success": False, "error": "Mercado Pago não disponível"}), 500
    
    try:
        print(f"🔄 Importando webhook do mercadopago_routes...")
        from mercadopago_routes import webhook
        
        print(f"🔄 Executando função webhook...")
        result = webhook()
        
        print(f"✅ WEBHOOK PROCESSADO COM SUCESSO!")
        print(f"📤 RESPOSTA: {result}")
        
        return result
        
    except Exception as e:
        print(f"❌ ERRO NO WEBHOOK PRINCIPAL: {e}")
        
        # 🔍 TRACEBACK COMPLETO
        import traceback
        print(f"🔍 TRACEBACK COMPLETO:")
        traceback.print_exc()
        
        return jsonify({"success": False, "error": str(e)}), 500

# 🧪 ENDPOINT DE TESTE
@app.route('/webhook/test', methods=['GET', 'POST'])
def webhook_test():
    """Endpoint para testar se webhook está acessível"""
    
    print(f"\n🧪 WEBHOOK TEST CHAMADO - {datetime.now()}")
    print(f"   Método: {request.method}")
    print(f"   Host: {request.host}")
    print(f"   URL: {request.url}")
    
    if request.method == 'POST':
        data = request.get_json()
        print(f"   Dados POST: {data}")
    
    return jsonify({
        'success': True,
        'message': 'Webhook está funcionando!',
        'method': request.method,
        'timestamp': datetime.now().isoformat(),
        'host': request.host,
        'mp_available': MP_AVAILABLE
    })

# 🔧 ENDPOINT PARA SIMULAR WEBHOOK
# Substitua o endpoint /webhook/simulate no seu main.py por este código corrigido:

@app.route('/webhook/simulate', methods=['POST', 'GET'])
def simulate_webhook():
    """Simular chamada do Mercado Pago para teste"""
    
    print(f"\n🎭 SIMULANDO WEBHOOK DO MERCADO PAGO - {datetime.now()}")
    print(f"   Método: {request.method}")
    
    # Se for GET, mostrar página de teste
    if request.method == 'GET':
        return '''
        <html>
        <head><title>Teste Webhook</title></head>
        <body>
            <h2>🧪 Teste do Webhook Mercado Pago</h2>
            <button onclick="testarWebhook()">Testar Webhook</button>
            <br><br>
            <button onclick="testarSimples()">Teste Simples</button>
            <div id="resultado"></div>
            
            <script>
            async function testarWebhook() {
                try {
                    document.getElementById('resultado').innerHTML = '🔄 Testando...';
                    
                    const response = await fetch('/webhook/simulate', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            "type": "payment",
                            "data": {"id": "123456789"}
                        })
                    });
                    
                    const result = await response.json();
                    document.getElementById('resultado').innerHTML = 
                        '<h3>Resultado:</h3><pre>' + JSON.stringify(result, null, 2) + '</pre>';
                } catch (error) {
                    document.getElementById('resultado').innerHTML = 
                        '<div style="color: red;">Erro: ' + error + '</div>';
                }
            }
            
            async function testarSimples() {
                try {
                    document.getElementById('resultado').innerHTML = '🔄 Teste simples...';
                    
                    const response = await fetch('/webhook/test-simple', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });
                    
                    const result = await response.json();
                    document.getElementById('resultado').innerHTML = 
                        '<h3>Teste Simples:</h3><pre>' + JSON.stringify(result, null, 2) + '</pre>';
                } catch (error) {
                    document.getElementById('resultado').innerHTML = 
                        '<div style="color: red;">Erro: ' + error + '</div>';
                }
            }
            </script>
        </body>
        </html>
        '''
    
    # POST - Executar simulação
    try:
        print(f"🔄 Iniciando simulação POST...")
        
        # Pegar dados do request ou usar dados fake
        data = request.get_json() or {
            "type": "payment",
            "data": {"id": "123456789"}
        }
        
        print(f"📦 Dados para simulação: {data}")
        
        if not MP_AVAILABLE:
            print(f"❌ MP_AVAILABLE é False")
            return jsonify({"error": "MP não disponível"}), 500
        
        print(f"✅ MP_AVAILABLE é True, processando...")
        
        # Verificar se é webhook de pagamento
        if data.get("type") == "payment":
            payment_id = data.get("data", {}).get("id")
            
            if payment_id:
                print(f"💳 Processando payment_id: {payment_id}")
                
                # Importar e executar função de processamento
                from mercadopago_routes import process_payment
                result = process_payment(payment_id)
                
                print(f"✅ PROCESSAMENTO CONCLUÍDO: {result}")
                
                return jsonify({
                    "success": True,
                    "message": "Simulação executada com sucesso",
                    "payment_id": payment_id,
                    "result": result
                })
            else:
                return jsonify({"error": "Payment ID não encontrado"}), 400
        else:
            return jsonify({"error": "Tipo de webhook não é payment"}), 400
            
    except Exception as e:
        print(f"❌ ERRO NA SIMULAÇÃO: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "error": str(e), 
            "details": "Veja os logs do Railway para mais detalhes"
        }), 500

# Também adicione este endpoint mais simples para teste
@app.route('/webhook/test-simple', methods=['POST'])
def test_simple_webhook():
    """Teste simples do webhook"""
    
    print(f"\n🔥 TESTE SIMPLES DO WEBHOOK - {datetime.now()}")
    
    try:
        # Testar se consegue importar e executar
        from mercadopago_routes import process_payment
        
        # Usar um payment_id fake
        result = process_payment("123456789")
        
        print(f"✅ TESTE SIMPLES CONCLUÍDO: {result}")
        
        return jsonify({
            "success": True,
            "test_result": result,
            "message": "Teste simples executado"
        })
        
    except Exception as e:
        print(f"❌ ERRO NO TESTE SIMPLES: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({"error": str(e)}), 500


@app.route('/test/create-payment', methods=['POST', 'GET'])
def create_test_payment():
    """Criar um pagamento real no sandbox usando Checkout Preferences"""
    
    if request.method == 'GET':
        return '''
        <html>
        <head><title>Criar Pagamento Teste</title></head>
        <body>
            <h2>🧪 Criar Pagamento Real no Sandbox</h2>
            
            <h3>Dados do Cliente:</h3>
            <input type="text" id="nome" placeholder="Nome do cliente" value="João Silva">
            <input type="email" id="email" placeholder="Email do cliente" value="joao@teste.com">
            <br><br>
            
            <h3>Plano:</h3>
            <select id="plano">
                <option value="basic">Básico - R$ 19,50</option>
                <option value="pro" selected>Pro - R$ 39,50</option>
            </select>
            <br><br>
            
            <input type="text" id="cupom" placeholder="Código do cupom (opcional)" value="">
            <br><br>
            
            <button onclick="criarCheckout()">🚀 Criar Checkout</button>
            <button onclick="mostrarCartoesFake()">💳 Ver Cartões Fake</button>
            
            <div id="cartoes" style="display:none; background:#f0f0f0; padding:10px; margin:10px 0;">
                <h4>📋 Cartões de Teste do Mercado Pago:</h4>
                <p><strong>VISA:</strong> 4013 5406 8274 6260 (CVV: 123)</p>
                <p><strong>Mastercard:</strong> 5031 7557 3453 0604 (CVV: 123)</p>
                <p><strong>American Express:</strong> 3711 803032 57522 (CVV: 1234)</p>
                <p><strong>Titular:</strong> APRO (aprovado) ou CONT (contestado)</p>
                <p><strong>Validade:</strong> 11/25 ou superior</p>
                <p><strong>CPF:</strong> 12345678909</p>
            </div>
            
            <div id="resultado"></div>
            
            <script>
            function mostrarCartoesFake() {
                const div = document.getElementById('cartoes');
                div.style.display = div.style.display === 'none' ? 'block' : 'none';
            }
            
            async function criarCheckout() {
                try {
                    document.getElementById('resultado').innerHTML = '🔄 Criando checkout...';
                    
                    const nome = document.getElementById('nome').value;
                    const email = document.getElementById('email').value;
                    const plano = document.getElementById('plano').value;
                    const cupom = document.getElementById('cupom').value;
                    
                    const response = await fetch('/test/create-payment', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            name: nome,
                            email: email,
                            plan: plano,
                            coupon: cupom
                        })
                    });
                    
                    const result = await response.json();
                    document.getElementById('resultado').innerHTML = 
                        '<h3>Checkout Criado:</h3><pre>' + JSON.stringify(result, null, 2) + '</pre>';
                        
                    if (result.init_point) {
                        document.getElementById('resultado').innerHTML += 
                            '<br><a href="' + result.init_point + '" target="_blank">🔗 Abrir Checkout no MP</a>';
                        document.getElementById('resultado').innerHTML += 
                            '<br><p><strong>Preference ID:</strong> ' + result.preference_id + '</p>';
                    }
                } catch (error) {
                    document.getElementById('resultado').innerHTML = 
                        '<div style="color: red;">Erro: ' + error + '</div>';
                }
            }
            </script>
        </body>
        </html>
        '''
    
    try:
        print(f"\n💳 CRIANDO CHECKOUT PREFERENCE - {datetime.now()}")
        
        mp_token = os.environ.get('MP_ACCESS_TOKEN')
        if not mp_token:
            return jsonify({'error': 'Token MP não configurado'}), 500
        
        # Dados do request
        data = request.get_json() or {}
        name = data.get('name', 'João Silva')
        email = data.get('email', 'joao@teste.com')
        plan = data.get('plan', 'pro')
        coupon = data.get('coupon', '')
        
        # Configurar plano
        plans = {
            'basic': {'price': 19.50, 'title': 'Plano Básico - Geminii'},
            'pro': {'price': 39.50, 'title': 'Plano Pro - Geminii'}
        }
        
        plan_info = plans.get(plan, plans['pro'])
        price = plan_info['price']
        
        # Aplicar cupom
        if coupon == '50OFF':
            price = price * 0.5
            plan_info['title'] += ' (50% OFF)'
        
        # Separar nome
        name_parts = name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else 'Silva'
        
        # Criar referência única
        external_reference = f"{email}_{plan}_{int(datetime.now().timestamp())}"
        
        # Dados da preferência
        preference_data = {
            "items": [
                {
                    "id": f"geminii_{plan}",
                    "title": plan_info['title'],
                    "description": f"Assinatura mensal do plano {plan.title()} da Geminii",
                    "category_id": "services",
                    "quantity": 1,
                    "currency_id": "BRL",  # ← CORRETO para preferences
                    "unit_price": price
                }
            ],
            "payer": {
                "name": first_name,
                "surname": last_name,
                "email": email,
                "phone": {
                    "area_code": "11",
                    "number": "999999999"
                },
                "identification": {
                    "type": "CPF",
                    "number": "12345678909"
                }
            },
            "back_urls": {
                "success": "https://app.geminii.com.br/payment/success",
                "pending": "https://app.geminii.com.br/payment/pending", 
                "failure": "https://app.geminii.com.br/payment/failure"
            },
            "notification_url": "https://app.geminii.com.br/webhook/mercadopago",
            "external_reference": external_reference,
            "auto_return": "approved",
            "payment_methods": {
                "excluded_payment_types": [
                    {"id": "ticket"}  # Excluir boleto para testes mais rápidos
                ],
                "installments": 12,
                "default_installments": 1
            },
            "metadata": {
                "plan": plan,
                "coupon": coupon,
                "user_email": email,
                "test": True
            }
        }
        
        print(f"📦 Dados da preferência: {preference_data}")
        
        # Criar preferência na API do MP
        headers = {
            'Authorization': f'Bearer {mp_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.post(
            'https://api.mercadopago.com/checkout/preferences',
            headers=headers,
            json=preference_data
        )
        
        print(f"📤 Resposta MP: {response.status_code}")
        print(f"📦 Dados resposta: {response.text}")
        
        if response.status_code == 201:
            preference_result = response.json()
            preference_id = preference_result.get('id')
            
            print(f"✅ PREFERÊNCIA CRIADA! ID: {preference_id}")
            
            return jsonify({
                'success': True,
                'preference_id': preference_id,
                'init_point': preference_result.get('init_point'),
                'sandbox_init_point': preference_result.get('sandbox_init_point'),
                'external_reference': external_reference,
                'plan': plan,
                'price': price,
                'coupon_applied': coupon,
                'message': f'Checkout criado! Use o link para pagar.',
                'instructions': 'Clique no link do checkout, faça o pagamento e monitore os logs!'
            })
        else:
            return jsonify({
                'error': f'Erro ao criar preferência: {response.status_code}',
                'details': response.text
            }), 400
            
    except Exception as e:
        print(f"❌ ERRO AO CRIAR PREFERÊNCIA: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({'error': str(e)}), 500

# Endpoint para testar webhook com payment_id real
@app.route('/test/webhook-real', methods=['POST'])
def test_webhook_real():
    """Testar webhook com payment_id real"""
    
    try:
        data = request.get_json()
        payment_id = data.get('payment_id')
        
        if not payment_id:
            return jsonify({'error': 'payment_id é obrigatório'}), 400
        
        print(f"\n🔔 TESTANDO WEBHOOK COM PAYMENT_ID REAL: {payment_id}")
        
        # Simular webhook do MP
        webhook_data = {
            "type": "payment",
            "data": {
                "id": payment_id
            }
        }
        
        # Processar como se fosse webhook real
        from mercadopago_routes import process_payment
        result = process_payment(payment_id)
        
        print(f"✅ TESTE CONCLUÍDO: {result}")
        
        return jsonify({
            'success': True,
            'payment_id': payment_id,
            'webhook_result': result,
            'message': 'Webhook testado com payment_id real'
        })
        
    except Exception as e:
        print(f"❌ ERRO NO TESTE: {e}")
        return jsonify({'error': str(e)}), 500

def process_payment(payment_id):
    """Processar pagamento aprovado do Checkout"""
    
    try:
        print(f"\n💳 PROCESSANDO PAGAMENTO: {payment_id}")
        
        # 1. Buscar dados do pagamento no MP
        mp_token = os.environ.get('MP_ACCESS_TOKEN')
        if not mp_token:
            return {'success': False, 'error': 'Token MP não configurado'}
        
        headers = {
            'Authorization': f'Bearer {mp_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f'https://api.mercadopago.com/v1/payments/{payment_id}',
            headers=headers
        )
        
        if response.status_code != 200:
            return {'success': False, 'error': f'Erro API MP: {response.status_code}'}
        
        payment_data = response.json()
        print(f"📦 Dados MP: status={payment_data.get('status')}, amount={payment_data.get('transaction_amount')}")
        
        # 2. Verificar se pagamento foi aprovado
        if payment_data.get('status') != 'approved':
            print(f"⏳ Pagamento não aprovado ainda: {payment_data.get('status')}")
            return {'success': True, 'message': f'Pagamento {payment_data.get("status")}, aguardando aprovação'}
        
        # 3. Extrair email do external_reference
        external_ref = payment_data.get('external_reference', '')
        
        # external_reference formato: "email_plano_timestamp"
        if external_ref and '_' in external_ref:
            user_email = external_ref.split('_')[0]
            plan = external_ref.split('_')[1]
        else:
            # Fallback para payer email
            user_email = payment_data.get('payer', {}).get('email', '')
            plan = 'pro'
        
        if not user_email:
            print(f"❌ Email não encontrado. external_ref: {external_ref}")
            return {'success': False, 'error': 'Email do usuário não encontrado'}
        
        print(f"👤 Buscando usuário: {user_email}")
        print(f"📋 Plano: {plan}")
        
        # 4. Conectar ao banco
        from app import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 5. Buscar ou criar usuário
        cursor.execute("SELECT id, email, subscription_status FROM users WHERE email = %s", (user_email,))
        user = cursor.fetchone()
        
        if not user:
            print(f"❌ Usuário não encontrado: {user_email}")
            conn.close()
            return {'success': False, 'error': f'Usuário não encontrado: {user_email}'}
        
        user_id = user[0]
        print(f"✅ Usuário encontrado: ID {user_id}")
        
        # 6. Verificar se pagamento já foi processado
        cursor.execute("SELECT id FROM payments WHERE payment_id = %s", (payment_id,))
        existing = cursor.fetchone()
        
        if existing:
            print(f"⚠️ Pagamento já processado anteriormente")
            conn.close()
            return {'success': True, 'message': 'Pagamento já foi processado'}
        
        # 7. Inserir na tabela payments
        cursor.execute("""
            INSERT INTO payments (user_id, payment_id, status, amount, plan_id, plan_name, external_reference, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """, (
            user_id,
            payment_id,
            'approved',
            payment_data.get('transaction_amount'),
            2 if plan == 'pro' else 1,  # plan_id
            plan,
            external_ref
        ))
        
        # 8. Ativar usuário
        cursor.execute("""
            UPDATE users 
            SET subscription_status = 'active', 
                subscription_plan = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (plan, user_id))
        
        conn.commit()
        conn.close()
        
        print(f"✅ PAGAMENTO PROCESSADO COM SUCESSO!")
        
        return {
            'success': True,
            'message': 'Pagamento processado e usuário ativado',
            'user_id': user_id,
            'payment_id': payment_id,
            'plan': plan,
            'amount': payment_data.get('transaction_amount')
        }
        
    except Exception as e:
        print(f"❌ ERRO NO PROCESSAMENTO: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}











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

@app.route('/api/validate-coupon', methods=['POST'])
def validate_coupon():
    """Validar cupom de desconto"""
    try:
        print(f"\n🎫 VALIDANDO CUPOM - {datetime.now()}")
        print("=" * 40)
        
        data = request.get_json()
        print(f"📊 Dados recebidos: {data}")
        
        if not data:
            print("❌ Nenhum dado JSON recebido")
            return jsonify({'success': False, 'error': 'Dados JSON necessários'}), 400
        
        code = data.get('code', '').strip().upper()
        plan_name = data.get('plan_name', '')
        user_id = data.get('user_id', 1)
        
        print(f"🔍 Cupom: '{code}'")
        print(f"📦 Plano: '{plan_name}'")
        print(f"👤 User ID: {user_id}")
        
        if not code:
            print("❌ Código do cupom vazio")
            return jsonify({'success': False, 'error': 'Código do cupom é obrigatório'}), 400
        
        print(f"🔄 Chamando validate_coupon_db...")
        from database import validate_coupon as validate_coupon_db
        result = validate_coupon_db(code, plan_name, user_id)
        
        print(f"📊 Resultado da validação: {result}")
        
        if result['valid']:
            print("✅ Cupom válido!")
            return jsonify({
                'success': True,
                'message': 'Cupom válido!',
                'data': {
                    'coupon_id': result['coupon_id'],
                    'discount_percent': result['discount_percent'],
                    'discount_type': result['discount_type'],
                    'applicable_plans': result.get('applicable_plans', [])
                }
            })
        else:
            print(f"❌ Cupom inválido: {result['error']}")
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
        
    except Exception as e:
        print(f"❌ ERRO na validação: {e}")
        import traceback
        traceback.print_exc()
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

# ===== ROTAS DE AUTENTICAÇÃO NO MAIN.PY =====

# ===== ADICIONAR ESTAS ROTAS APÓS A ROTA DE LOGIN E ANTES DO if __name__ =====

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
    return jsonify({'success': True, 'message': 'Logout realizado com sucesso!'}), 200

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

@app.route('/api/force-admin')
def force_admin():
    """Temporário - forçar admin"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE users 
            SET user_type = 'admin', plan_id = 3, plan_name = 'Premium'
            WHERE email = 'diego@geminii.com.br'
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Admin forçado!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ##===== FUNÇÃO CREATE_APP PARA RAILWAY =====
def create_app():
    """Factory para criar app - Railway"""
    if os.environ.get('RAILWAY_ENVIRONMENT'):
        print("🚄 Executando no Railway...")
        app.config['ENV'] = 'production'
        app.config['DEBUG'] = False
    
    initialize_database()
    return app

###===== SUBSTITUIR TODO O FINAL DO ARQUIVO POR ISSO =====
# if __name__ == '__main__':
#     # CONFIGURAÇÃO PARA MODO LOCAL
#     print("🏠 MODO DESENVOLVIMENTO LOCAL...")
    
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
    
#     app.run(host='0.0.0.0', port=port, debug=True)
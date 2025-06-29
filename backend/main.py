# main.py - VERSÃO LIMPA (sem duplicações)

from flask import Flask, jsonify, send_from_directory, request
import jwt
from datetime import datetime, timedelta, timezone
import os
from database import get_db_connection
import mercadopago_service

# Imports dos blueprints
from beta_routes import beta_bp
from long_short_routes import long_short_bp
from rsl_routes import get_rsl_blueprint
from recommendations_routes import get_recommendations_blueprint
from mercadopago_routes import get_mercadopago_blueprint
from opcoes_routes import opcoes_bp
from swing_trade_ml_routes import get_swing_trade_ml_blueprint
from beta_regression_routes import beta_regression_bp
from atsmom_routes import register_atsmom_routes
from chart_ativos_routes import chart_ativos_bp
from carrossel_yfinance_routes import get_carrossel_blueprint
from recommendations_routes_free import recommendations_free_bp
from dotenv import load_dotenv

load_dotenv()
if not os.getenv('JWT_SECRET'):
    os.environ['JWT_SECRET'] = 'geminii-jwt-secret-key-2024'

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

# ===== CONFIGURAÇÃO ADMIN BLUEPRINT =====
ADMIN_AVAILABLE = False
admin_bp = None

try:
    from admin_routes import get_admin_blueprint
    admin_bp = get_admin_blueprint()
    ADMIN_AVAILABLE = True
    print("✅ Blueprint Admin carregado com sucesso!")
except ImportError as e:
    print(f"⚠️ Admin routes não disponível: {e}")
    ADMIN_AVAILABLE = False
except Exception as e:
    print(f"❌ Erro ao carregar admin blueprint: {e}")
    ADMIN_AVAILABLE = False

# ===== CONFIGURAÇÃO CARROSSEL =====
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

# ===== REGISTRAR BLUEPRINTS =====
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
recommendations_free_bp()

# Registrar blueprints condicionais
if MP_AVAILABLE and mercadopago_bp:
    app.register_blueprint(mercadopago_bp)
    print("✅ Blueprint Mercado Pago registrado!")

if ADMIN_AVAILABLE and admin_bp:
    try:
        app.register_blueprint(admin_bp)
        print("✅ Blueprint Admin registrado com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao registrar admin blueprint: {e}")
        ADMIN_AVAILABLE = False

if CARROSSEL_AVAILABLE and carrossel_bp:
    try:
        app.register_blueprint(carrossel_bp)
        print("✅ Blueprint Carrossel registrado com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao registrar carrossel blueprint: {e}")
        CARROSSEL_AVAILABLE = False

try:
    from newsletter_routes import get_newsletter_blueprint
    newsletter_bp = get_newsletter_blueprint()
    app.register_blueprint(newsletter_bp)
    print("✅ Newsletter blueprint registrado!")
except Exception as e:
    print(f"❌ Erro newsletter: {e}")

# ===== INICIALIZAÇÃO =====
def initialize_database():
    """Inicializar banco se necessário"""
    try:
        from database import setup_enhanced_database
        setup_enhanced_database()
        
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

@app.route('/recomendacoes-free.html')
def Recomendation_free():
    return send_from_directory('../frontend', 'recomendacoes-free.html')

# ===== PÁGINAS DE RETORNO DO PAGAMENTO =====

@app.route('/payment/success')
def payment_success():
    """Página de sucesso do pagamento - VERSÃO CORRIGIDA"""
    payment_id = request.args.get('payment_id')
    status_param = request.args.get('status')
    external_reference = request.args.get('external_reference')
    
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
                    <div id="status-text" class="text-yellow-400 mb-2">🔄 Ativando sua assinatura...</div>
                    <div class="w-full bg-gray-700 rounded-full h-2">
                        <div id="progress-bar" class="bg-green-600 h-2 rounded-full transition-all duration-1000" style="width: 0%"></div>
                    </div>
                </div>
                
                <p class="text-gray-300 mb-6 leading-relaxed">
                    Parabéns! Sua assinatura está sendo ativada.
                </p>
                
                <div id="action-buttons" class="space-y-3" style="display: none;">
                    <button onclick="window.location.href='/dashboard'" 
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
            console.log('🎯 Página de sucesso carregada - VERSÃO CORRIGIDA');
            
            let progressValue = 0;
            let checkAttempts = 0;
            const maxAttempts = 8;  // Máximo 16 segundos
            
            // Animar barra de progresso
            function animateProgress() {{
                const progressBar = document.getElementById('progress-bar');
                progressValue += 12.5;  // 100% / 8 tentativas
                progressBar.style.width = progressValue + '%';
            }}
            
            // Verificar status do usuário
            async function checkUserStatus() {{
                checkAttempts++;
                animateProgress();
                
                console.log(`🔍 Verificação ${{checkAttempts}}/${{maxAttempts}}`);
                
                try {{
                    // Tentar buscar dados do usuário
                    const token = localStorage.getItem('jwt_token');
                    const headers = {{}};
                    
                    if (token) {{
                        headers['Authorization'] = `Bearer ${{token}}`;
                    }}
                    
                    const response = await fetch('/api/auth/verify', {{ headers }});
                    
                    if (response.ok) {{
                        const data = await response.json();
                        
                        if (data.success && data.data.user.plan_name !== 'Básico') {{
                            console.log('✅ Plano ativado:', data.data.user.plan_name);
                            showSuccess();
                            return;
                        }}
                    }}
                }} catch (error) {{
                    console.log('❌ Erro na verificação:', error);
                }}
                
                // Se chegou ao máximo de tentativas ou passou muito tempo
                if (checkAttempts >= maxAttempts) {{
                    console.log('⏰ Timeout - liberando botões');
                    showSuccess();
                    return;
                }}
                
                // Tentar novamente em 2 segundos
                setTimeout(checkUserStatus, 2000);
            }}
            
            // Mostrar botões e finalizar loading
            function showSuccess() {{
                document.getElementById('status-text').innerHTML = '✅ Assinatura ativada!';
                document.getElementById('status-text').className = 'text-green-400 mb-2';
                document.getElementById('progress-bar').style.width = '100%';
                document.getElementById('action-buttons').style.display = 'block';
                
                // Auto-redirecionar após 3 segundos
                setTimeout(() => {{
                    console.log('🔄 Auto-redirecionando para dashboard...');
                    window.location.href = '/dashboard';
                }}, 3000);
            }}
            
            // 🔥 TIMEOUT DE SEGURANÇA - 12 SEGUNDOS
            setTimeout(() => {{
                console.log('🚨 Timeout de segurança ativado');
                showSuccess();
            }}, 12000);
            
            // Iniciar verificação após 1 segundo
            setTimeout(checkUserStatus, 1000);
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
    """Status da API"""
    mp_status = {"success": MP_AVAILABLE, "message": "Blueprint carregado" if MP_AVAILABLE else "Não disponível"}
    admin_status = {"success": ADMIN_AVAILABLE, "message": "Blueprint carregado" if ADMIN_AVAILABLE else "Não disponível"}
    carrossel_status = {"success": CARROSSEL_AVAILABLE, "message": "Blueprint carregado" if CARROSSEL_AVAILABLE else "Não disponível"}
    
    return jsonify({
        'message': 'API Flask Online!',
        'status': 'online',
        'database': 'Connected',
        'mercadopago': mp_status,
        'admin': admin_status,
        'carrossel': carrossel_status
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
        
        hashed_password = mercadopago_service.hash_password(password)
        cursor.execute("""
            INSERT INTO users (name, email, password, plan_id, plan_name, created_at) 
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        """, (name, email, hashed_password, 3, 'Básico', datetime.now(timezone.utc)))
        
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
                'plan_name': 'Pro'
            }
        }), 201
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500

@app.route('/api/validate-coupon', methods=['POST'])
def validate_coupon():
    """Validar cupom de desconto"""
    try:
        data = request.get_json()
        print(f"🎫 CUPOM REQUEST: {data}")  # ✅ ADICIONAR ESTA LINHA
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados JSON necessários'}), 400
        
        code = data.get('code', '').strip().upper()
        plan_name = data.get('plan_name', '')
        user_id = data.get('user_id', 1)
        
        if not code:
            return jsonify({'success': False, 'error': 'Código do cupom é obrigatório'}), 400
        
        print("🔍 Chamando validate_coupon_db...")  # ✅ ADICIONAR
        from database import validate_coupon as validate_coupon_db
        result = validate_coupon_db(code, plan_name, user_id)
        print(f"📋 Resultado validate_coupon_db: {result}") 
        
        if result['valid']:
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
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
        
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
        
        if mercadopago_service.hash_password(password) != stored_password:
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
        
        result = mercadopago_service.generate_reset_token_service(email)
        
        if result['success']:
            email_sent = mercadopago_service.send_reset_email(
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
        
        result = mercadopago_service.validate_reset_token_service(token)
        
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
        
        result = mercadopago_service.reset_password_service(token, new_password)
        
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

# ===== FUNÇÃO CREATE_APP PARA RAILWAY =====
def create_app():
    """Factory para criar app - Railway"""
    if os.environ.get('RAILWAY_ENVIRONMENT'):
        print("🚄 Executando no Railway...")
        app.config['ENV'] = 'production'
        app.config['DEBUG'] = False
    
    initialize_database()
    return app

# if __name__ == "__main__":
   
#     # Inicializar banco
#     initialize_database()
    
#     # Configurar para desenvolvimento
#     app.config['ENV'] = 'development'
#     app.config['DEBUG'] = True
    
#     # Executar Flask
#     print("🚀 Iniciando servidor Flask local...")
#     app.run(
#         host='0.0.0.0',
#         port=5000,
#         debug=True
#     )
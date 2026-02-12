#main.py
from flask import Flask, jsonify, send_from_directory, request
import jwt
from flask_cors import CORS
from datetime import datetime, timedelta, timezone
import os

from database import get_db_connection

# ===== IMPORTS SOLICITADOS =====

# Gratis
from gratis.beta_routes import beta_bp
from gratis.rsl_routes import get_rsl_blueprint
from gratis.amplitude_routes import amplitude_bp
from gratis.rrg_routes import get_rrg_blueprint

# Pro
from pro.opcoes_routes import opcoes_bp
from pro.rank_routes import get_rank_blueprint
from pro.bandas_pro_routes import get_bandas_pro_blueprint
from pro.vi_routes import get_vi_blueprint
from pro.vol_regimes_routes import vol_regimes_bp
from pro.regimes_volatilidade_routes import regimes_bp
from pro.gamma_routes import get_gamma_blueprint
from pro.delta_routes import get_delta_blueprint
from pro.vega_routes import get_vega_blueprint
from pro.theta_routes import get_theta_blueprint
from pro.mm_temporal_routes import mm_temporal_bp
from pro.oplab_routes import oplab_bp
from pro.screening_routes import get_screening_blueprint
from pro.railway_sync_routes import railway_bp




# Premium
from premium.swing_trade_ml_routes import get_swing_trade_ml_blueprint
from premium.beta_regression_routes import beta_regression_bp
from premium.atsmom_routes import register_atsmom_routes
from premium.longshortroutes import longshort_bp  


# Trial
from pag.trial_routes import get_trial_blueprint

# Email
from emails.newsletter_routes import get_newsletter_blueprint
from emails.email_service import setup_email_system

# Auth
from auth_routes import get_auth_blueprint
from carteiras.recommendations_routes_free import get_recommendations_free_blueprint

# Config
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
app.config['MAIL_PASSWORD'] = os.environ.get('EMAIL_PASSWORD', '#Geminii20##')

# ===== CONFIGURAÇÃO DE BLUEPRINTS =====

# Auth Blueprint
AUTH_AVAILABLE = False
auth_bp = None

try:
    auth_bp = get_auth_blueprint()
    AUTH_AVAILABLE = True
    print(" Auth blueprint carregado!")
except ImportError as e:
    print(f" Auth routes não disponível: {e}")
    AUTH_AVAILABLE = False
except Exception as e:
    print(f" Erro ao carregar auth blueprint: {e}")
    AUTH_AVAILABLE = False

# Newsletter Blueprint
NEWSLETTER_AVAILABLE = False
newsletter_bp = None

try:
    newsletter_bp = get_newsletter_blueprint()
    NEWSLETTER_AVAILABLE = True
    print(" Newsletter blueprint carregado!")
except ImportError as e:
    print(f" Newsletter routes não disponível: {e}")
    NEWSLETTER_AVAILABLE = False
except Exception as e:
    print(f" Erro ao carregar newsletter blueprint: {e}")
    NEWSLETTER_AVAILABLE = False

# Admin Blueprint
ADMIN_AVAILABLE = False
admin_bp = None

try:
    from admin_routes import get_admin_blueprint
    admin_bp = get_admin_blueprint()
    ADMIN_AVAILABLE = True
    print(" Admin blueprint carregado!")
except ImportError as e:
    print(f" Admin routes não disponível: {e}")
    ADMIN_AVAILABLE = False
except Exception as e:
    print(f" Erro ao carregar admin blueprint: {e}")
    ADMIN_AVAILABLE = False

# ===== REGISTRAR BLUEPRINTS =====

# Blueprints principais
app.register_blueprint(beta_bp)
app.register_blueprint(opcoes_bp)
app.register_blueprint(oplab_bp)
app.register_blueprint(railway_bp)
app.register_blueprint(get_rrg_blueprint())


# market maker

try:
    from pro.historical_routes import get_historical_blueprint
    
    historical_bp = get_historical_blueprint()
    app.register_blueprint(historical_bp)
    print(" HISTORICAL blueprint registrado!")
except Exception as e:
    print(f" Erro ao registrar HISTORICAL blueprint: {e}")


# TEX
try:
    
    theta_bp = get_theta_blueprint()
    app.register_blueprint(theta_bp)
    print(" TEX blueprint registrado!")
except Exception as e:
    print(f" Erro ao registrar TEX blueprint: {e}")

try:
    vega_bp = get_vega_blueprint()
    app.register_blueprint(vega_bp)
    print(" VEX blueprint registrado!")
except Exception as e:
    print(f" Erro ao registrar VEX blueprint: {e}")

# DEX
try:
    
    delta_bp = get_delta_blueprint()
    app.register_blueprint(delta_bp)
    print(" DEX blueprint registrado!")
except Exception as e:
    print(f" Erro ao registrar DEX blueprint: {e}")

try:
    rsl_bp = get_rsl_blueprint()
    app.register_blueprint(rsl_bp)
    print(" RSL blueprint registrado!")
except Exception as e:
    print(f" Erro ao registrar RSL blueprint: {e}")
    

# Recommendations Free
try:
    recommendations_free_bp = get_recommendations_free_blueprint()
    app.register_blueprint(recommendations_free_bp)
    print(" Recommendations Free blueprint registrado!")
except Exception as e:
    print(f" Erro ao registrar recommendations free blueprint: {e}")


# Swing Trade ML
try:
    app.register_blueprint(get_swing_trade_ml_blueprint())
    print(" Swing Trade ML blueprint registrado!")
except Exception as e:
    print(f" Erro ao registrar swing trade ML blueprint: {e}")

# Beta Regression
try:
    app.register_blueprint(beta_regression_bp, url_prefix='/beta_regression')
    print(" Beta Regression blueprint registrado!")
except Exception as e:
    print(f" Erro ao registrar beta regression blueprint: {e}")

# ATSMOM
try:
    register_atsmom_routes(app)
    print(" ATSMOM routes registradas!")
except Exception as e:
    print(f" Erro ao registrar ATSMOM routes: {e}")


try:
    app.register_blueprint(longshort_bp)
    print(" Long Short blueprint registrado!")
except Exception as e:
    print(f" Erro ao registrar Long Short blueprint: {e}")    

# Trial
try:
    trial_bp = get_trial_blueprint()
    app.register_blueprint(trial_bp)
    print(" Trial blueprint registrado!")
except Exception as e:
    print(f" Erro ao registrar trial blueprint: {e}")

# Vol Regimes
try:
    app.register_blueprint(vol_regimes_bp)
    print(" Vol Regimes blueprint registrado!")
except Exception as e:
    print(f" Erro ao registrar vol regimes blueprint: {e}")

# Amplitude
try:
    app.register_blueprint(amplitude_bp)
    print(" Amplitude blueprint registrado!")
except Exception as e:
    print(f" Erro ao registrar amplitude blueprint: {e}")

# Rank
try:
    rank_bp = get_rank_blueprint()
    app.register_blueprint(rank_bp)
    print(" Rank blueprint registrado!")
except Exception as e:
    print(f" Erro ao registrar rank blueprint: {e}")

# Bandas Pro
try:
    app.register_blueprint(get_bandas_pro_blueprint())
    print(" Bandas Pro blueprint registrado!")
except Exception as e:
    print(f" Erro ao registrar bandas pro blueprint: {e}")

# VI
try:
    vi_bp = get_vi_blueprint()
    app.register_blueprint(vi_bp)
    print(" VI blueprint registrado!")
except Exception as e:
    print(f" Erro ao registrar VI blueprint: {e}")

# Regimes
try:
    app.register_blueprint(regimes_bp, url_prefix='/api/regimes')
    print(" Regimes blueprint registrado!")
except Exception as e:
    print(f" Erro ao registrar regimes blueprint: {e}")

#Screening

try:
    screening_bp = get_screening_blueprint()
    app.register_blueprint(screening_bp)
    print("✓ Screening blueprint registrado!")
except Exception as e:
    print(f"✗ Erro ao registrar screening blueprint: {e}")    

# ===== REGISTRAR BLUEPRINTS CONDICIONAIS =====

# Auth
if AUTH_AVAILABLE and auth_bp:
    try:
        app.register_blueprint(auth_bp)
        print(" Auth blueprint registrado - rotas /auth/* disponíveis!")
    except Exception as e:
        print(f" Erro ao registrar auth blueprint: {e}")
        AUTH_AVAILABLE = False
else:
    print(" Auth blueprint não disponível")

# Newsletter
if NEWSLETTER_AVAILABLE and newsletter_bp:
    try:
        app.register_blueprint(newsletter_bp)
        print(" Newsletter blueprint registrado - rota /api/newsletter disponível!")
    except Exception as e:
        print(f" Erro ao registrar newsletter blueprint: {e}")
        NEWSLETTER_AVAILABLE = False
else:
    print(" Newsletter blueprint não disponível")

# Admin
if ADMIN_AVAILABLE and admin_bp:
    try:
        app.register_blueprint(admin_bp)
        print(" Admin blueprint registrado - rotas /api/admin/* disponíveis!")
    except Exception as e:
        print(f" Erro ao registrar admin blueprint: {e}")
        ADMIN_AVAILABLE = False
else:
    print(" Admin blueprint não disponível")


try:
    gamma_bp = get_gamma_blueprint()
    app.register_blueprint(gamma_bp)
    print(" Gamma blueprint registrado!")
except Exception as e:
    print(f" Erro ao registrar gamma blueprint: {e}")


# ===== CORS =====
CORS(app, 
     origins=['*'],
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
     allow_headers=['Content-Type', 'Authorization'],
     supports_credentials=True)

# ===== INICIALIZAÇÃO =====
def initialize_database():
    """Inicializar banco e sistema de email"""
    try:
        from database import setup_enhanced_database
        setup_enhanced_database()
        
        if setup_email_system():
            print(" Sistema de email inicializado!")
        else:
            print(" Falha na inicialização do sistema de email")
        
    except Exception as e:
        print(f" Erro ao verificar banco: {e}")

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

@app.route('/logo.png')
def serve_logo():
    return send_from_directory('../frontend', 'logo.png')

@app.route('/assets/logo.png')
def serve_logo_assets():
    return send_from_directory('../frontend', 'logo.png')


@app.route('/recomendacoes-free.html')
def Recomendation_free():
    return send_from_directory('../frontend', 'recomendacoes-free.html')

##========== Fre ===============##

@app.route('/monitor-basico')
@app.route('/monitor-basico.html')
def monitor_basico():
        return send_from_directory('../frontend/', 'monitor-basico.html')
    
@app.route('/sup_res_vol.html')
def Sup_Res_volatility():
    return send_from_directory('../frontend', 'sup_res_vol.html')

@app.route('/amplitude.html')
def amplitude_page():
    return send_from_directory('../frontend', 'amplitude.html')    

@app.route('/rsl')
@app.route('/rsl.html')
def rsl_page():
    return send_from_directory('../frontend', 'rsl.html')

@app.route('/rrg')
@app.route('/rrg.html')
def rrg_page():
    return send_from_directory('../frontend', 'rrg.html')


##========== Opções ===============##

@app.route('/vi-pro')
@app.route('/vi-pro.html')
def vi_pro_page():
    return send_from_directory('../frontend', 'vi-pro.html')
    
@app.route('/rank-volatilidade')
@app.route('/rank-volatilidade.html')
def rank_volatilidade():
    return send_from_directory('../frontend', 'rank-volatilidade.html')

@app.route('/opcoes')
@app.route('/opcoes.html')
def opcoes_page():
    return send_from_directory('../frontend', 'opcoes.html')

@app.route('/regimes-pro.html')
@app.route('/regimes-pro.html')
def regimes():
    return send_from_directory('../frontend', 'regimes-pro.html')

@app.route('/gamma-levels')
@app.route('/gamma-levels.html')
def gamma_levels():
    return send_from_directory('../frontend', 'gamma-levels.html')

@app.route('/delta-levels')
@app.route('/delta-levels.html')
def delta_levels():
    return send_from_directory('../frontend', 'delta-levels.html')

@app.route('/vega-levels')
@app.route('/vega-levels.html')
def vega_levels():
    return send_from_directory('../frontend', 'vega-levels.html')

@app.route('/theta-level')
@app.route('/theta-levels.html')
def theta_levels():
    return send_from_directory('../frontend', 'theta-levels.html')


@app.route('/marketmaker')
@app.route('/marketmaker.html')
def mm_levels():
    return send_from_directory('../frontend', 'marketmaker.html')

@app.route('/historical-levels')
@app.route('/historical-levels.html')
def hisles_levels():
    return send_from_directory('../frontend', 'historical-levels.html')


@app.route('/greeks-micro')
@app.route('/greeks-micro.html')
def greeks_micro():
    return send_from_directory('../frontend', 'greeks-micro.html')

@app.route('/visaomacro')
@app.route('/visaomacro.html')
def visaomacro():
    return send_from_directory('../frontend', 'visaomacro.html')


@app.route('/screening')
@app.route('/screening.html')
def screening_page():
    return send_from_directory('../frontend', 'screening.html')

#historical-levels

##========== MAchine ===============##

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

@app.route('/longshort')
@app.route('/longshort.html')
def longshort_page():
    return send_from_directory('../frontend', 'longshort.html')

# ===== ROTAS API =====

@app.route('/api/status')
def status():
    """Status da API"""
    return jsonify({
        'message': 'API Flask Online!',
        'status': 'online',
        'database': 'Connected',
        'blueprints': {
            'auth': {"success": AUTH_AVAILABLE, "message": "Blueprint carregado" if AUTH_AVAILABLE else "Não disponível"},
            'newsletter': {"success": NEWSLETTER_AVAILABLE, "message": "Blueprint carregado" if NEWSLETTER_AVAILABLE else "Não disponível"},
            'admin': {"success": ADMIN_AVAILABLE, "message": "Blueprint carregado" if ADMIN_AVAILABLE else "Não disponível"}
        }
    })


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

@app.route('/auth/logout', methods=['POST'])
def logout():
    """Logout do usuário"""
    return jsonify({'success': True, 'message': 'Logout realizado com sucesso!'}), 200

# ===== FUNÇÃO CREATE_APP PARA RAILWAY =====
def create_app():
    """Factory para criar app - Railway"""
    if os.environ.get('RAILWAY_ENVIRONMENT'):
        print("Executando no Railway...")
        app.config['ENV'] = 'production'
        app.config['DEBUG'] = False
    
    initialize_database()
    return app

if __name__ == "__main__":
    # Inicializar banco
    initialize_database()
    
    # Configurar para desenvolvimento
    app.config['ENV'] = 'development'
    app.config['DEBUG'] = True
    
    # Executar Flask
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )
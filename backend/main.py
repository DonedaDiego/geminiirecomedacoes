from flask import Flask, jsonify, send_from_directory, request
import hashlib
import jwt
from datetime import datetime, timedelta, timezone
import psycopg2
import os
from password_reset import generate_reset_token, validate_reset_token, reset_password
from yfinance_service import YFinanceService

app = Flask(__name__)
app.config['SECRET_KEY'] = 'geminii-secret-2024'

def hash_password(password):
    """Criptografar senha"""
    return hashlib.sha256(password.encode()).hexdigest()

def get_db_connection():
    """Conectar com PostgreSQL (local ou Render)"""
    try:
        # Se estiver no Render, usar DATABASE_URL
        database_url = os.environ.get("DATABASE_URL")
        
        if database_url:
            # Produção (Render) - usa a URL completa
            conn = psycopg2.connect(database_url, sslmode='require')
        else:
            # Desenvolvimento local
            conn = psycopg2.connect(
                host=os.environ.get("DB_HOST", "localhost"),
                database=os.environ.get("DB_NAME", "postgres"),
                user=os.environ.get("DB_USER", "postgres"),
                password=os.environ.get("DB_PASSWORD", "#geminii"),
                port=os.environ.get("DB_PORT", "5432")
            )
        return conn
    except Exception as e:
        print(f"❌ Erro ao conectar no banco: {e}")
        return None

# ===== ROTAS HTML =====

@app.route('/')
def home():
    return send_from_directory('../frontend', 'index.html')

@app.route('/dashboard')
@app.route('/dashboard.html')
def dashboard():
    """🎯 NOVA ROTA - Dashboard"""
    return send_from_directory('../frontend', 'dashboard.html')

@app.route('/planos')
@app.route('/planos.html')
def planos():
    return send_from_directory('../frontend', 'planos.html')

@app.route('/sobre')
@app.route('/sobre.html')
def sobre():
    return "<h1>Página Sobre - Em construção</h1>"

@app.route('/conta')
@app.route('/conta.html')
def conta():
    return send_from_directory('../frontend', 'conta.html') if os.path.exists('../frontend/conta.html') else "<h1>Página Conta - Em construção</h1>"

@app.route('/monitor-basico')
@app.route('/monitor-basico.html')
def monitor_basico():
    """🎯 NOVA ROTA - Monitor Básico"""
    return send_from_directory('../frontend', 'monitor-basico.html') if os.path.exists('../frontend/monitor-basico.html') else "<h1>Monitor Básico - Em construção</h1>"

@app.route('/radar-setores')
@app.route('/radar-setores.html')
def radar_setores():
    """🎯 NOVA ROTA - Radar de Setores"""
    return send_from_directory('../frontend', 'radar-setores.html') if os.path.exists('../frontend/radar-setores.html') else "<h1>Radar de Setores - Em construção</h1>"

@app.route('/relatorios')
@app.route('/relatorios.html')
def relatorios():
    """🎯 NOVA ROTA - Relatórios"""
    return send_from_directory('../frontend', 'relatorios.html') if os.path.exists('../frontend/relatorios.html') else "<h1>Relatórios - Em construção</h1>"

@app.route('/login')
@app.route('/login.html')
def login_page():
    """Redirecionar login para página inicial"""
    return send_from_directory('../frontend', 'index.html')

# ===== ROTAS API BÁSICAS =====

@app.route('/api/status')
def status():
    return jsonify({
        'message': 'API Flask Online!',
        'status': 'online',
        'database': 'Connected'
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
            return jsonify({
                'success': False,
                'error': 'Falha na conexão'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# 🎯 NOVA ROTA - Dashboard API
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
            
            # Buscar dados do usuário
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

# ===== ROTAS DE AUTENTICAÇÃO =====

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
        
        # Validações
        if not name or not email or not password:
            return jsonify({'success': False, 'error': 'Nome, e-mail e senha são obrigatórios'}), 400
        
        if len(password) < 6:
            return jsonify({'success': False, 'error': 'Senha deve ter pelo menos 6 caracteres'}), 400
        
        if '@' not in email:
            return jsonify({'success': False, 'error': 'E-mail inválido'}), 400
        
        # Conectar no banco
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão com banco'}), 500
        
        cursor = conn.cursor()
        
        # Verificar se email já existe
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'E-mail já cadastrado'}), 400
        
        # Criar usuário
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
        
        # Conectar no banco
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão com banco'}), 500
        
        cursor = conn.cursor()
        
        # Buscar usuário
        cursor.execute("""
            SELECT id, name, email, password, plan_id, plan_name 
            FROM users WHERE email = %s
        """, (email,))
        
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user:
            return jsonify({'success': False, 'error': 'E-mail não encontrado'}), 401
        
        # Verificar senha
        user_id, name, email, stored_password, plan_id, plan_name = user
        
        if hash_password(password) != stored_password:
            return jsonify({'success': False, 'error': 'Senha incorreta'}), 401
        
        # Gerar token JWT
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
                    'plan_name': plan_name
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
        
        # Verificar token JWT
        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            user_id = payload['user_id']
            
            # Buscar dados atualizados do usuário
            conn = get_db_connection()
            if not conn:
                return jsonify({'success': False, 'error': 'Erro de conexão com banco'}), 500
            
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, email, plan_id, plan_name 
                FROM users WHERE id = %s
            """, (user_id,))
            
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not user:
                return jsonify({'success': False, 'error': 'Usuário não encontrado'}), 401
            
            user_id, name, email, plan_id, plan_name = user
            
            return jsonify({
                'success': True,
                'data': {
                    'user': {
                        'id': user_id,
                        'name': name,
                        'email': email,
                        'plan_id': plan_id,
                        'plan_name': plan_name
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
    """🎯 NOVA ROTA - Logout"""
    try:
        # Em um sistema mais complexo, você invalidaria o token aqui
        # Por enquanto, só retornamos sucesso
        return jsonify({
            'success': True,
            'message': 'Logout realizado com sucesso!'
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'}), 500

# ===== ROTAS DE RECUPERAÇÃO DE SENHA =====

@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    """Solicitar recuperação de senha"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados JSON necessários'}), 400
        
        email = data.get('email', '').strip()
        
        if not email:
            return jsonify({'success': False, 'error': 'E-mail é obrigatório'}), 400
        
        if '@' not in email:
            return jsonify({'success': False, 'error': 'E-mail inválido'}), 400
        
        # Gerar token de recuperação
        result = generate_reset_token(email)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'Token de recuperação gerado!',
                'data': {
                    'token': result['token'],  # Em produção, enviar por email
                    'user_name': result['user_name'],
                    'expires_in': result['expires_in']
                }
            }), 200
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
        
        # Validar token
        result = validate_reset_token(token)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'Token válido!',
                'data': {
                    'user_name': result['name'],
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
        
        # Redefinir senha
        result = reset_password(token, new_password)
        
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
    # Pegar símbolos da query string (ex: ?symbols=PETR4,VALE3,ITUB4)
    symbols_param = request.args.get('symbols', 'PETR4,VALE3,ITUB4,BBDC4')
    symbols = [s.strip().upper() for s in symbols_param.split(',')]
    
    result = YFinanceService.get_multiple_stocks(symbols)
    return jsonify(result)

@app.route('/api/stock/<symbol>/history')
def get_stock_history(symbol):
    """Buscar histórico de uma ação"""
    # Pegar período da query string (ex: ?period=1mo)
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

# ===== EXECUTAR SERVIDOR =====

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 10000))  # Render usa 10000 por padrão
    print("🚀 Iniciando Geminii API...")
    print("📊 APIs disponíveis:")
    print("  - /api/status")
    print("  - /api/test-db")
    print("  - /api/dashboard")
    print("  - /api/auth/login (POST)")
    print("  - /api/auth/register (POST)")
    print("  - /api/auth/verify (GET)")
    print("  - /api/auth/logout (POST)")
    print("  - /api/auth/forgot-password (POST)")
    print("  - /api/auth/reset-password (POST)")
    print("  - /api/stock/<symbol>")
    print("  - /api/stocks")
    print("  - /api/stock/<symbol>/history")
    print("  - /api/stocks/search")
    print("🔐 Sistema de autenticação ativado!")
    print("🎯 Rotas HTML:")
    print("  - / (index.html)")
    print("  - /dashboard.html")
    print("  - /planos.html")
    print("  - /monitor-basico.html")
    print("  - /radar-setores.html")
    print("  - /relatorios.html")
    
    # Debug False em produção
    debug_mode = os.environ.get("FLASK_ENV") != "production"
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
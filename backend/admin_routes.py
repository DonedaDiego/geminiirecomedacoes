from flask import Blueprint, request, jsonify
import jwt
from datetime import datetime, timedelta
from database import get_db_connection

# Criar blueprint admin
admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

def verify_admin_access(auth_header):
    """Verificar se usuário tem acesso admin"""
    try:
        if not auth_header or not auth_header.startswith('Bearer '):
            return False
        
        token = auth_header.replace('Bearer ', '')
        
        # Importar SECRET_KEY do app principal
        from flask import current_app
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload['user_id']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_type FROM users WHERE id = %s", (user_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return result and result[0] in ['admin', 'master']
        
    except:
        return False

# ===== ROTAS ADMIN DE ESTATÍSTICAS =====

@admin_bp.route('/stats')
def admin_stats():
    """Estatísticas para dashboard admin"""
    try:
        auth_header = request.headers.get('Authorization')
        if not verify_admin_access(auth_header):
            return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
        
        cursor = conn.cursor()
        
        # Total de usuários
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        # Usuários premium (plano_id > 1)
        cursor.execute("SELECT COUNT(*) FROM users WHERE plan_id > 1")
        premium_users = cursor.fetchone()[0]
        
        # Cupons ativos
        cursor.execute("SELECT COUNT(*) FROM coupons WHERE is_active = true")
        active_coupons = cursor.fetchone()[0]
        
        # Receita mensal estimada
        monthly_revenue = premium_users * 49.90
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'total_users': total_users,
                'premium_users': premium_users,
                'active_coupons': active_coupons,
                'monthly_revenue': f"{monthly_revenue:.2f}"
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== ROTAS ADMIN DE USUÁRIOS =====

@admin_bp.route('/list-users')
def list_all_users():
    """Listar todos os usuários - ADMIN ONLY"""
    try:
        auth_header = request.headers.get('Authorization')
        if not verify_admin_access(auth_header):
            return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, email, plan_name, user_type, created_at, updated_at
            FROM users 
            ORDER BY created_at DESC
        """)
        
        users = []
        for row in cursor.fetchall():
            users.append({
                'id': row[0],
                'name': row[1],
                'email': row[2],
                'plan': row[3],
                'type': row[4] or 'regular',
                'created_at': row[5].isoformat() if row[5] else None,
                'updated_at': row[6].isoformat() if row[6] else None
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'users': users,
            'total': len(users)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/manage-subscription', methods=['POST'])
def manage_subscription():
    """Dar ou remover assinatura manualmente"""
    try:
        auth_header = request.headers.get('Authorization')
        if not verify_admin_access(auth_header):
            return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
        data = request.get_json()
        user_email = data.get('user_email')
        action = data.get('action')  # 'grant' ou 'revoke'
        plan_id = data.get('plan_id', 2)
        
        if not user_email or action not in ['grant', 'revoke']:
            return jsonify({'success': False, 'error': 'Dados inválidos'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Buscar usuário
        cursor.execute("SELECT id, name, plan_name FROM users WHERE email = %s", (user_email,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'success': False, 'error': 'Usuário não encontrado'}), 404
        
        user_id, user_name, current_plan = user
        
        if action == 'grant':
            # Dar assinatura
            cursor.execute("SELECT name FROM plans WHERE id = %s", (plan_id,))
            plan_result = cursor.fetchone()
            
            if not plan_result:
                return jsonify({'success': False, 'error': 'Plano não encontrado'}), 404
            
            plan_name = plan_result[0]
            
            cursor.execute("""
                UPDATE users 
                SET plan_id = %s, plan_name = %s, updated_at = CURRENT_TIMESTAMP 
                WHERE id = %s
            """, (plan_id, plan_name, user_id))
            
            message = f"Assinatura {plan_name} concedida para {user_name}"
            
        else:  # revoke
            # Remover assinatura (voltar para básico)
            cursor.execute("""
                UPDATE users 
                SET plan_id = 1, plan_name = 'Básico', updated_at = CURRENT_TIMESTAMP 
                WHERE id = %s
            """, (user_id,))
            
            message = f"Assinatura removida de {user_name} - voltou ao plano Básico"
            plan_name = 'Básico'
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': message,
            'user': {
                'name': user_name,
                'email': user_email,
                'old_plan': current_plan,
                'new_plan': plan_name
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/promote-user', methods=['POST'])
def promote_user():
    """Promover usuário a admin"""
    try:
        auth_header = request.headers.get('Authorization')
        if not verify_admin_access(auth_header):
            return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
        data = request.get_json()
        user_email = data.get('user_email')
        user_type = data.get('user_type', 'admin')
        
        if not user_email:
            return jsonify({'success': False, 'error': 'Email obrigatório'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verificar se usuário existe
        cursor.execute("SELECT id, name FROM users WHERE email = %s", (user_email,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Usuário não encontrado'}), 404
        
        user_id, user_name = user
        
        # Promover usuário
        cursor.execute("""
            UPDATE users 
            SET user_type = %s, plan_id = 3, plan_name = 'Estratégico', updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (user_type, user_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'{user_name} promovido a {user_type} com sucesso!'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== ROTAS DE CUPONS =====

@admin_bp.route('/coupons', methods=['GET'])
def list_coupons():
    """Listar todos os cupons"""
    try:
        auth_header = request.headers.get('Authorization')
        if not verify_admin_access(auth_header):
            return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, code, discount_percent, discount_type, discount_value,
                   applicable_plans, max_uses, used_count, valid_until, is_active,
                   created_at
            FROM coupons 
            ORDER BY created_at DESC
        """)
        
        coupons = []
        for row in cursor.fetchall():
            coupons.append({
                'id': row[0],
                'code': row[1],
                'discount_percent': float(row[2]),
                'discount_type': row[3],
                'discount_value': float(row[4]) if row[4] else 0,
                'applicable_plans': row[5] or [],
                'max_uses': row[6],
                'used_count': row[7],
                'valid_until': row[8].isoformat() if row[8] else None,
                'is_active': row[9],
                'created_at': row[10].isoformat() if row[10] else None
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'coupons': coupons
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/coupons', methods=['POST'])
def create_coupon():
    """Criar novo cupom"""
    try:
        auth_header = request.headers.get('Authorization')
        if not verify_admin_access(auth_header):
            return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
        data = request.get_json()
        code = data.get('code', '').upper().strip()
        discount_percent = data.get('discount_percent')
        applicable_plans = data.get('applicable_plans', [])
        max_uses = data.get('max_uses')
        valid_until = data.get('valid_until')
        
        if not code or not discount_percent:
            return jsonify({'success': False, 'error': 'Código e desconto são obrigatórios'}), 400
        
        if discount_percent <= 0 or discount_percent > 100:
            return jsonify({'success': False, 'error': 'Desconto deve estar entre 1% e 100%'}), 400
        
        # Extrair user_id do token
        token = request.headers.get('Authorization').replace('Bearer ', '')
        from flask import current_app
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        admin_user_id = payload['user_id']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verificar se código já existe
        cursor.execute("SELECT id FROM coupons WHERE code = %s", (code,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Código já existe'}), 400
        
        # Inserir cupom
        cursor.execute("""
            INSERT INTO coupons (code, discount_percent, applicable_plans, max_uses, valid_until, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (code, discount_percent, applicable_plans, max_uses, valid_until, admin_user_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Cupom {code} criado com sucesso!'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/coupons/<coupon_code>/toggle', methods=['PATCH'])
def toggle_coupon(coupon_code):
    """Ativar/desativar cupom"""
    try:
        auth_header = request.headers.get('Authorization')
        if not verify_admin_access(auth_header):
            return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
        data = request.get_json()
        is_active = data.get('is_active', True)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE coupons 
            SET is_active = %s, updated_at = CURRENT_TIMESTAMP
            WHERE code = %s
        """, (is_active, coupon_code.upper()))
        
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Cupom não encontrado'}), 404
        
        conn.commit()
        cursor.close()
        conn.close()
        
        status = 'ativado' if is_active else 'desativado'
        return jsonify({
            'success': True,
            'message': f'Cupom {coupon_code} {status} com sucesso!'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== ROTAS DE CARTEIRAS =====

@admin_bp.route('/portfolio/<portfolio_name>/assets')
def get_portfolio_assets_api(portfolio_name):
    """Buscar ativos de uma carteira"""
    try:
        auth_header = request.headers.get('Authorization')
        if not verify_admin_access(auth_header):
            return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
        from database import get_portfolio_assets
        assets = get_portfolio_assets(portfolio_name)
        
        return jsonify({
            'success': True,
            'assets': assets,
            'portfolio': portfolio_name
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/portfolio/add-asset', methods=['POST'])
def add_portfolio_asset_api():
    """Adicionar ativo a carteira"""
    try:
        auth_header = request.headers.get('Authorization')
        if not verify_admin_access(auth_header):
            return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
        data = request.get_json()
        portfolio = data.get('portfolio')
        ticker = data.get('ticker', '').upper()
        weight = data.get('weight')
        sector = data.get('sector', '').strip()
        
        if not all([portfolio, ticker, weight, sector]):
            return jsonify({'success': False, 'error': 'Todos os campos são obrigatórios'}), 400
        
        if weight < 0 or weight > 100:
            return jsonify({'success': False, 'error': 'Peso deve estar entre 0 e 100'}), 400
        
        # Extrair user_id do token
        token = request.headers.get('Authorization').replace('Bearer ', '')
        from flask import current_app
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        admin_user_id = payload['user_id']
        
        from database import add_portfolio_asset
        result = add_portfolio_asset(portfolio, ticker, weight, sector, admin_user_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/portfolio/remove-asset', methods=['DELETE'])
def remove_portfolio_asset_api():
    """Remover ativo da carteira"""
    try:
        auth_header = request.headers.get('Authorization')
        if not verify_admin_access(auth_header):
            return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
        data = request.get_json()
        portfolio = data.get('portfolio')
        ticker = data.get('ticker', '').upper()
        
        if not portfolio or not ticker:
            return jsonify({'success': False, 'error': 'Portfolio e ticker são obrigatórios'}), 400
        
        from database import remove_portfolio_asset
        result = remove_portfolio_asset(portfolio, ticker)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== FUNÇÃO PARA EXPORTAR O BLUEPRINT =====

def get_admin_blueprint():
    """Retornar blueprint admin para registrar no Flask"""
    return admin_bp
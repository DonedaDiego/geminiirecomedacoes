# admin_routes.py - VERSÃO COMPLETA SEM CONFLITOS

from flask import Blueprint, request, jsonify
import os
import jwt
from datetime import datetime, timezone, timedelta
from database import get_db_connection

# ===== BLUEPRINT ADMIN =====
admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# ===== VERIFICAÇÃO DE ADMIN =====
def verify_admin_token(token):
    """Verificar se token é de admin"""
    try:
        from flask import current_app
        
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload['user_id']
        
        conn = get_db_connection()
        if not conn:
            return None
            
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_type FROM users 
            WHERE id = %s AND user_type IN ('admin', 'master')
        """, (user_id,))
        
        admin = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return admin[0] if admin else None
        
    except Exception as e:
        print(f"❌ Erro na verificação admin: {e}")
        return None

def require_admin():
    """Decorator para verificar se usuário é admin"""
    def decorator(f):
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({'success': False, 'error': 'Token não fornecido'}), 401
            
            token = auth_header.replace('Bearer ', '')
            admin_id = verify_admin_token(token)
            
            if not admin_id:
                return jsonify({'success': False, 'error': 'Acesso negado'}), 403
            
            return f(admin_id, *args, **kwargs)
        
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

# ===== ESTATÍSTICAS =====

@admin_bp.route('/stats')
@require_admin()
def get_admin_stats(admin_id):
    """Estatísticas do painel admin"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Total de usuários
        cursor.execute("SELECT COUNT(*) FROM users WHERE user_type != 'deleted'")
        total_users = cursor.fetchone()[0]
        
        # Usuários premium (plan_id >= 2)
        cursor.execute("SELECT COUNT(*) FROM users WHERE plan_id >= 2 AND user_type != 'deleted'")
        premium_users = cursor.fetchone()[0]
        
        # Cupons ativos
        try:
            cursor.execute("SELECT COUNT(*) FROM coupons WHERE is_active = true")
            active_coupons = cursor.fetchone()[0]
        except:
            active_coupons = 0
        
        # Receita mensal (simulada)
        monthly_revenue = premium_users * 79  # Média de preço
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'total_users': total_users,
                'premium_users': premium_users,
                'active_coupons': active_coupons,
                'monthly_revenue': monthly_revenue
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== GERENCIAMENTO DE USUÁRIOS =====

@admin_bp.route('/list-users')
@require_admin()
def list_users(admin_id):
    """Listar todos os usuários"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT u.id, u.name, u.email, u.plan_id, u.plan_name, u.user_type, u.created_at,
                   EXTRACT(days FROM (NOW() - u.created_at)) as days_old
            FROM users u
            WHERE u.user_type != 'deleted'
            ORDER BY u.created_at DESC
            LIMIT 100
        """)
        
        users = []
        for row in cursor.fetchall():
            user_id, name, email, plan_id, plan_name, user_type, created_at, days_old = row
            
            users.append({
                'id': user_id,
                'name': name,
                'email': email,
                'plan_id': plan_id,
                'plan': plan_name or 'Básico',
                'type': user_type or 'regular',
                'created_at': created_at.isoformat() if created_at else None,
                'formatted_date': created_at.strftime('%d/%m/%Y') if created_at else 'N/A',
                'days_old': int(days_old) if days_old else 0
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'users': users
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/manage-subscription', methods=['POST'])
@require_admin()
def manage_subscription(admin_id):
    """Gerenciar assinatura de usuário"""
    try:
        data = request.get_json()
        user_email = data.get('user_email')
        action = data.get('action')  # 'grant' ou 'revoke'
        plan_id = data.get('plan_id', 2)
        
        if not user_email or not action:
            return jsonify({'success': False, 'error': 'Email e ação são obrigatórios'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Buscar usuário
        cursor.execute("SELECT id, name FROM users WHERE email = %s", (user_email,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Usuário não encontrado'}), 404
        
        user_id, user_name = user
        
        if action == 'grant':
            # Mapear plan_id para plan_name
            plan_names = {1: 'Básico', 2: 'Pro', 3: 'Premium'}
            plan_name = plan_names.get(plan_id, 'Pro')
            
            # Calcular expiração (30 dias para teste)
            expires_at = datetime.now(timezone.utc) + timedelta(days=30)
            
            cursor.execute("""
                UPDATE users 
                SET plan_id = %s, plan_name = %s, plan_expires_at = %s, updated_at = CURRENT_TIMESTAMP
                WHERE email = %s
            """, (plan_id, plan_name, expires_at, user_email))
            
            message = f'Assinatura {plan_name} concedida para {user_name}'
            
        elif action == 'revoke':
            cursor.execute("""
                UPDATE users 
                SET plan_id = 1, plan_name = 'Básico', plan_expires_at = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE email = %s
            """, (user_email,))
            
            message = f'Assinatura removida de {user_name}'
        
        else:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Ação inválida'}), 400
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/promote-user', methods=['POST'])
@require_admin()
def promote_user(admin_id):
    """Promover usuário a admin"""
    try:
        data = request.get_json()
        user_email = data.get('user_email')
        user_type = data.get('user_type', 'admin')
        
        if not user_email:
            return jsonify({'success': False, 'error': 'Email é obrigatório'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Buscar usuário
        cursor.execute("SELECT id, name FROM users WHERE email = %s", (user_email,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Usuário não encontrado'}), 404
        
        user_id, user_name = user
        
        cursor.execute("""
            UPDATE users 
            SET user_type = %s, plan_id = 3, plan_name = 'Premium', updated_at = CURRENT_TIMESTAMP
            WHERE email = %s
        """, (user_type, user_email))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'{user_name} promovido a {user_type}'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/users/delete', methods=['DELETE'])
@require_admin()
def delete_user(admin_id):
    """Marcar usuário como deletado"""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({'success': False, 'error': 'Email é obrigatório'}), 400
        
        # Proteção contra remoção do admin principal
        if email == 'diego@geminii.com.br':
            return jsonify({'success': False, 'error': 'Não é possível remover este usuário'}), 403
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Buscar usuário
        cursor.execute("SELECT id, name FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Usuário não encontrado'}), 404
        
        user_id, user_name = user
        
        # Marcar como deletado ao invés de deletar fisicamente
        cursor.execute("""
            UPDATE users 
            SET user_type = 'deleted', 
                plan_id = 1, 
                plan_name = 'Removido',
                updated_at = CURRENT_TIMESTAMP
            WHERE email = %s
        """, (email,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Usuário {user_name} foi marcado como removido'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== GERENCIAMENTO DE CUPONS =====

@admin_bp.route('/coupons', methods=['GET'])
@require_admin()
def get_coupons(admin_id):
    """Listar cupons"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT code, discount_percent, discount_type, discount_value, 
                       applicable_plans, max_uses, used_count, valid_until, is_active, created_at
                FROM coupons
                ORDER BY created_at DESC
            """)
            
            coupons = []
            for row in cursor.fetchall():
                code, discount_percent, discount_type, discount_value, applicable_plans, max_uses, used_count, valid_until, is_active, created_at = row
                
                coupons.append({
                    'code': code,
                    'discount_percent': float(discount_percent) if discount_percent else 0,
                    'discount_type': discount_type,
                    'discount_value': float(discount_value) if discount_value else 0,
                    'applicable_plans': applicable_plans or [],
                    'max_uses': max_uses,
                    'used_count': used_count or 0,
                    'valid_until': valid_until.isoformat() if valid_until else None,
                    'is_active': is_active,
                    'created_at': created_at.isoformat() if created_at else None
                })
            
        except Exception as e:
            print(f"⚠️ Erro ao buscar cupons (tabela pode não existir): {e}")
            coupons = []
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'coupons': coupons
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/coupons', methods=['POST'])
@require_admin()
def create_coupon(admin_id):
    """Criar cupom"""
    try:
        data = request.get_json()
        
        code = data.get('code', '').upper()
        discount_percent = data.get('discount_percent')
        applicable_plans = data.get('applicable_plans', [])
        max_uses = data.get('max_uses')
        valid_until = data.get('valid_until')
        
        if not code or not discount_percent:
            return jsonify({'success': False, 'error': 'Código e desconto são obrigatórios'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        try:
            # Verificar se código já existe
            cursor.execute("SELECT id FROM coupons WHERE code = %s", (code,))
            if cursor.fetchone():
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'error': 'Código já existe'}), 400
            
            # Inserir cupom
            cursor.execute("""
                INSERT INTO coupons (
                    code, discount_percent, discount_type, applicable_plans, 
                    max_uses, valid_until, created_by, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                code, 
                discount_percent, 
                'percent',
                applicable_plans,
                max_uses,
                valid_until if valid_until else None,
                admin_id,
                datetime.now(timezone.utc)
            ))
            
            conn.commit()
            message = f'Cupom {code} criado com sucesso'
            
        except Exception as e:
            print(f"⚠️ Erro ao criar cupom (tabela pode não existir): {e}")
            message = f'Erro: tabela de cupons não existe'
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/coupons/<coupon_code>/toggle', methods=['PATCH'])
@require_admin()
def toggle_coupon_active(admin_id, coupon_code):
    """Ativar/desativar cupom"""
    try:
        data = request.get_json()
        is_active = data.get('is_active', True)
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        try:
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
            status_text = 'ativado' if is_active else 'desativado'
            message = f'Cupom {coupon_code} {status_text} com sucesso'
            
        except Exception as e:
            print(f"⚠️ Erro ao alterar cupom: {e}")
            message = f'Erro: não foi possível alterar cupom'
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== GERENCIAMENTO DE PORTFOLIOS =====

@admin_bp.route('/portfolio/<portfolio_name>/assets')
@require_admin()
def get_portfolio_assets(admin_id, portfolio_name):
    """Buscar ativos de uma carteira"""
    try:
        from database import get_portfolio_assets
        assets = get_portfolio_assets(portfolio_name)
        
        # Calcular peso total
        total_weight = sum(asset.get('weight', 0) for asset in assets)
        
        return jsonify({
            'success': True,
            'assets': assets,
            'total_weight': total_weight
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/portfolio/add-asset', methods=['POST'])
@require_admin()
def add_portfolio_asset(admin_id):
    """Adicionar ativo a carteira"""
    try:
        data = request.get_json()
        
        portfolio = data.get('portfolio')
        ticker = data.get('ticker', '').upper()
        weight = data.get('weight')
        sector = data.get('sector')
        entry_price = data.get('entry_price')
        current_price = data.get('current_price')
        target_price = data.get('target_price')
        entry_date = data.get('entry_date')
        
        if not all([portfolio, ticker, weight, sector, entry_price, target_price]):
            return jsonify({'success': False, 'error': 'Dados obrigatórios faltando'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        try:
            # Inserir ou atualizar ativo
            cursor.execute("""
                INSERT INTO portfolio_assets (
                    portfolio_name, ticker, weight, sector, entry_price, 
                    current_price, target_price, entry_date
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (portfolio_name, ticker) 
                DO UPDATE SET 
                    weight = EXCLUDED.weight,
                    sector = EXCLUDED.sector,
                    entry_price = EXCLUDED.entry_price,
                    current_price = EXCLUDED.current_price,
                    target_price = EXCLUDED.target_price,
                    entry_date = EXCLUDED.entry_date,
                    updated_at = CURRENT_TIMESTAMP
            """, (portfolio, ticker, weight, sector, entry_price, current_price, target_price, entry_date))
            
            conn.commit()
            message = f'Ativo {ticker} adicionado à carteira {portfolio}'
            
        except Exception as e:
            print(f"⚠️ Erro ao adicionar ativo: {e}")
            message = f'Erro: não foi possível adicionar ativo'
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/portfolio/remove-asset', methods=['DELETE'])
@require_admin()
def remove_portfolio_asset(admin_id):
    """Remover ativo da carteira"""
    try:
        data = request.get_json()
        asset_id = data.get('id')
        
        if not asset_id:
            return jsonify({'success': False, 'error': 'ID do ativo é obrigatório'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM portfolio_assets WHERE id = %s", (asset_id,))
            
            if cursor.rowcount == 0:
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'error': 'Ativo não encontrado'}), 404
            
            conn.commit()
            message = 'Ativo removido com sucesso'
            
        except Exception as e:
            print(f"⚠️ Erro ao remover ativo: {e}")
            message = f'Erro: não foi possível remover ativo'
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/portfolio/clear-assets', methods=['DELETE'])
@require_admin()
def clear_portfolio_assets(admin_id):
    """Limpar todos os ativos de uma carteira"""
    try:
        data = request.get_json()
        portfolio = data.get('portfolio')
        
        if not portfolio:
            return jsonify({'success': False, 'error': 'Nome da carteira é obrigatório'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM portfolio_assets WHERE portfolio_name = %s", (portfolio,))
            assets_removed = cursor.rowcount
            conn.commit()
            
            message = f'{assets_removed} ativos removidos da carteira {portfolio}'
            
        except Exception as e:
            print(f"⚠️ Erro ao limpar ativos: {e}")
            message = f'Erro: não foi possível limpar ativos'
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== GERENCIAMENTO DE RECOMENDAÇÕES =====

@admin_bp.route('/portfolio/<portfolio_name>/recommendations')
@require_admin()
def get_portfolio_recommendations(admin_id, portfolio_name):
    """Buscar recomendações de uma carteira"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, ticker, action_type, target_weight, recommendation_date,
                       reason, price_target, current_price, is_active,
                       entry_price, market_price
                FROM portfolio_recommendations 
                WHERE portfolio_name = %s AND is_active = true
                ORDER BY recommendation_date DESC
            """, (portfolio_name,))
            
            recommendations = []
            for row in cursor.fetchall():
                rec_id, ticker, action_type, target_weight, rec_date, reason, price_target, current_price, is_active, entry_price, market_price = row
                
                recommendations.append({
                    'id': rec_id,
                    'ticker': ticker,
                    'action_type': action_type,
                    'target_weight': float(target_weight) if target_weight else None,
                    'recommendation_date': rec_date.isoformat() if rec_date else None,
                    'reason': reason,
                    'price_target': float(price_target) if price_target else None,
                    'current_price': float(current_price) if current_price else None,
                    'entry_price': float(entry_price) if entry_price else None,
                    'market_price': float(market_price) if market_price else None,
                    'is_active': is_active
                })
                
        except Exception as e:
            print(f"⚠️ Erro ao buscar recomendações: {e}")
            recommendations = []
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'recommendations': recommendations
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/portfolio/add-recommendation', methods=['POST'])
@require_admin()
def add_portfolio_recommendation(admin_id):
    """Criar nova recomendação"""
    try:
        data = request.get_json()
        
        portfolio = data.get('portfolio')
        ticker = data.get('ticker', '').upper()
        action_type = data.get('action_type')
        entry_price = data.get('entry_price')
        market_price = data.get('market_price')
        target_weight = data.get('target_weight')
        recommendation_date = data.get('recommendation_date')
        price_target = data.get('price_target')
        reason = data.get('reason')
        
        if not all([portfolio, ticker, action_type, recommendation_date]):
            return jsonify({'success': False, 'error': 'Dados obrigatórios faltando'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO portfolio_recommendations (
                    portfolio_name, ticker, action_type, target_weight, 
                    recommendation_date, reason, price_target, current_price,
                    entry_price, market_price, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                portfolio, ticker, action_type, target_weight,
                recommendation_date, reason, price_target, market_price,
                entry_price, market_price, admin_id
            ))
            
            conn.commit()
            message = f'Recomendação {action_type} para {ticker} criada'
            
        except Exception as e:
            print(f"⚠️ Erro ao criar recomendação: {e}")
            message = f'Erro: não foi possível criar recomendação'
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/portfolio/delete-recommendation', methods=['DELETE'])
@require_admin()
def delete_portfolio_recommendation(admin_id):
    """Deletar recomendação"""
    try:
        data = request.get_json()
        rec_id = data.get('id')
        
        if not rec_id:
            return jsonify({'success': False, 'error': 'ID da recomendação é obrigatório'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        try:
            cursor.execute("DELETE FROM portfolio_recommendations WHERE id = %s", (rec_id,))
            
            if cursor.rowcount == 0:
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'error': 'Recomendação não encontrada'}), 404
            
            conn.commit()
            message = 'Recomendação removida com sucesso'
            
        except Exception as e:
            print(f"⚠️ Erro ao remover recomendação: {e}")
            message = f'Erro: não foi possível remover recomendação'
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/portfolio/generate-rebalance', methods=['POST'])
@require_admin()
def generate_rebalance_recommendations(admin_id):
    """Gerar recomendações de rebalanceamento automático"""
    try:
        data = request.get_json()
        portfolio = data.get('portfolio')
        reason = data.get('reason', 'Rebalanceamento automático')
        
        if not portfolio:
            return jsonify({'success': False, 'error': 'Nome da carteira é obrigatório'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        try:
            # Buscar ativos atuais da carteira
            cursor.execute("""
                SELECT ticker, current_price, target_price 
                FROM portfolio_assets 
                WHERE portfolio_name = %s AND is_active = true
            """, (portfolio,))
            
            assets = cursor.fetchall()
            
            if not assets:
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'error': 'Nenhum ativo encontrado na carteira'}), 404
            
            recommendations_created = 0
            today = datetime.now().date()
            
            # Criar recomendação SELL para cada ativo
            for ticker, current_price, target_price in assets:
                cursor.execute("""
                    INSERT INTO portfolio_recommendations (
                        portfolio_name, ticker, action_type, target_weight,
                        recommendation_date, reason, price_target, current_price,
                        created_by
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    portfolio, ticker, 'SELL', 0.0,
                    today, reason, target_price, current_price,
                    admin_id
                ))
                recommendations_created += 1
            
            conn.commit()
            
        except Exception as e:
            print(f"⚠️ Erro ao gerar rebalanceamento: {e}")
            recommendations_created = 0
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'{recommendations_created} recomendações de rebalanceamento criadas',
            'recommendations_created': recommendations_created
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== FUNÇÃO EXPORT =====
def get_admin_blueprint():
    """Retornar blueprint para registrar no Flask"""
    return admin_bp
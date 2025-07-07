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
            cursor.execute("SELECT COUNT(*) FROM coupons WHERE active = true")
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
            plan_names = {3: 'Básico', 1: 'Pro', 2: 'Premium'}
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
                SET plan_id = 3, plan_name = 'Básico', plan_expires_at = NULL, updated_at = CURRENT_TIMESTAMP
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


@require_admin()
def add_portfolio_asset_admin(admin_id):
    """Adicionar ativo a carteira (ROTA CORRIGIDA)"""
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
        
        # Validações básicas
        if not all([portfolio, ticker, weight, sector, entry_price, target_price]):
            return jsonify({'success': False, 'error': 'Dados obrigatórios faltando'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Verificar se portfolio existe
        cursor.execute("SELECT name FROM portfolios WHERE name = %s", (portfolio,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': f'Portfolio {portfolio} não encontrado'}), 404
        
        try:
            # Inserir ou atualizar ativo (ON CONFLICT para evitar duplicatas)
            cursor.execute("""
                INSERT INTO portfolio_assets (
                    portfolio_name, ticker, weight, sector, entry_price, 
                    current_price, target_price, entry_date, is_active,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (portfolio_name, ticker) 
                DO UPDATE SET 
                    weight = EXCLUDED.weight,
                    sector = EXCLUDED.sector,
                    entry_price = EXCLUDED.entry_price,
                    current_price = EXCLUDED.current_price,
                    target_price = EXCLUDED.target_price,
                    entry_date = EXCLUDED.entry_date,
                    is_active = true,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
            """, (
                portfolio, ticker, weight, sector, entry_price, 
                current_price, target_price, entry_date, True
            ))
            
            result = cursor.fetchone()
            asset_id = result[0] if result else None
            
            conn.commit()
            
            message = f'Ativo {ticker} adicionado à carteira {portfolio} com sucesso!'
            
            cursor.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': message,
                'asset_id': asset_id
            })
            
        except Exception as e:
            conn.rollback()
            cursor.close()
            conn.close()
            print(f"❌ Erro SQL ao inserir ativo: {e}")
            return jsonify({'success': False, 'error': f'Erro no banco de dados: {str(e)}'}), 500
        
    except Exception as e:
        print(f"❌ Erro geral ao adicionar ativo: {e}")
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

@admin_bp.route('/portfolio/update-asset', methods=['PUT'])
@require_admin()
def update_portfolio_asset(admin_id):
    try:
        data = request.get_json()
        asset_id = data.get('id')
        
        if not asset_id:
            return jsonify({'success': False, 'error': 'ID do ativo é obrigatório'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE portfolio_assets 
            SET ticker = %s, weight = %s, sector = %s, 
                entry_price = %s, current_price = %s, target_price = %s, 
                entry_date = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            data.get('ticker'), data.get('weight'), data.get('sector'),
            data.get('entry_price'), data.get('current_price'), data.get('target_price'),
            data.get('entry_date'), asset_id
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Ativo atualizado com sucesso!'})
        
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
    
    
# ===== ADICIONAR ESTA ROTA NO SEU admin_routes.py =====

@admin_bp.route('/user/<user_email>/portfolios', methods=['GET'])
@require_admin()
def get_user_portfolios_admin(admin_id, user_email):
    """Buscar carteiras de um usuário específico (para admin)"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Buscar usuário primeiro
        cursor.execute("SELECT id, name FROM users WHERE email = %s", (user_email,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Usuário não encontrado'}), 404
        
        user_id, user_name = user
        
        # Buscar carteiras do usuário
        cursor.execute("""
            SELECT up.portfolio_name, p.display_name, up.granted_at
            FROM user_portfolios up
            JOIN portfolios p ON up.portfolio_name = p.name
            WHERE up.user_id = %s AND up.is_active = true
            ORDER BY p.display_name
        """, (user_id,))
        
        portfolios = []
        for row in cursor.fetchall():
            portfolios.append({
                'name': row[0],
                'display_name': row[1],
                'granted_at': row[2].isoformat() if row[2] else None
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'user': {
                'id': user_id,
                'name': user_name,
                'email': user_email
            },
            'portfolios': portfolios
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/user-portfolios', methods=['POST'])
@require_admin()
def manage_user_portfolios(admin_id):
    """Gerenciar carteiras de usuário (conceder/remover acesso)"""
    try:
        data = request.get_json()
        action = data.get('action')  # 'grant' ou 'revoke'
        user_email = data.get('user_email')
        portfolio_name = data.get('portfolio_name')
        
        if not all([action, user_email, portfolio_name]):
            return jsonify({'success': False, 'error': 'Dados obrigatórios faltando'}), 400
        
        if action not in ['grant', 'revoke']:
            return jsonify({'success': False, 'error': 'Ação deve ser grant ou revoke'}), 400
        
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
        
        # Verificar se carteira existe
        cursor.execute("SELECT display_name FROM portfolios WHERE name = %s", (portfolio_name,))
        portfolio = cursor.fetchone()
        
        if not portfolio:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Carteira não encontrada'}), 404
        
        portfolio_display_name = portfolio[0]
        
        if action == 'grant':
            # Conceder acesso
            cursor.execute("""
                INSERT INTO user_portfolios (user_id, portfolio_name, granted_by, is_active)
                VALUES (%s, %s, %s, true)
                ON CONFLICT (user_id, portfolio_name) 
                DO UPDATE SET 
                    is_active = true,
                    granted_by = EXCLUDED.granted_by,
                    granted_at = CURRENT_TIMESTAMP
            """, (user_id, portfolio_name, admin_id))
            
            message = f'Acesso à carteira {portfolio_display_name} concedido para {user_name}'
            
        elif action == 'revoke':
            # Remover acesso
            cursor.execute("""
                UPDATE user_portfolios 
                SET is_active = false 
                WHERE user_id = %s AND portfolio_name = %s
            """, (user_id, portfolio_name))
            
            if cursor.rowcount == 0:
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'error': 'Usuário não tem acesso a esta carteira'}), 404
            
            message = f'Acesso à carteira {portfolio_display_name} removido de {user_name}'
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500    




# ===== ADICIONAR ESTAS ROTAS NO FINAL DO admin_routes.py =====

@admin_bp.route('/payments', methods=['GET'])
@require_admin()
def get_payments_history(admin_id):
    """Listar histórico de pagamentos para o admin"""
    try:
        # Parâmetros de filtro
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        status_filter = request.args.get('status', 'all')
        user_email = request.args.get('user_email', '').strip()
        
        offset = (page - 1) * limit
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Query base
        base_query = """
            SELECT p.id, p.payment_id, p.status, p.amount, p.plan_id, p.plan_name,
                   p.cycle, p.external_reference, p.created_at, p.updated_at,
                   u.name as user_name, u.email as user_email
            FROM payments p
            LEFT JOIN users u ON p.user_id = u.id
        """
        
        # Filtros
        where_conditions = []
        params = []
        
        if status_filter != 'all':
            where_conditions.append("p.status = %s")
            params.append(status_filter)
        
        if user_email:
            where_conditions.append("u.email ILIKE %s")
            params.append(f"%{user_email}%")
        
        # Montar query final
        if where_conditions:
            base_query += " WHERE " + " AND ".join(where_conditions)
        
        base_query += " ORDER BY p.created_at DESC"
        
        # Buscar total de registros (para paginação)
        count_query = f"SELECT COUNT(*) FROM ({base_query}) as total"
        cursor.execute(count_query, params)
        total_records = cursor.fetchone()[0]
        
        # Buscar registros paginados
        paginated_query = base_query + f" LIMIT %s OFFSET %s"
        cursor.execute(paginated_query, params + [limit, offset])
        
        payments = []
        for row in cursor.fetchall():
            payment_id, mp_payment_id, status, amount, plan_id, plan_name, cycle, external_ref, created_at, updated_at, user_name, user_email = row
            
            payments.append({
                'id': payment_id,
                'payment_id': mp_payment_id,
                'status': status,
                'amount': float(amount) if amount else 0.0,
                'plan_id': plan_id,
                'plan_name': plan_name,
                'cycle': cycle,
                'external_reference': external_ref,
                'created_at': created_at.isoformat() if created_at else None,
                'updated_at': updated_at.isoformat() if updated_at else None,
                'user_name': user_name,
                'user_email': user_email,
                'formatted_date': created_at.strftime('%d/%m/%Y %H:%M') if created_at else 'N/A',
                'formatted_amount': f"R$ {float(amount):,.2f}" if amount else "R$ 0,00"
            })
        
        cursor.close()
        conn.close()
        
        # Calcular estatísticas
        total_pages = (total_records + limit - 1) // limit
        
        return jsonify({
            'success': True,
            'payments': payments,
            'pagination': {
                'current_page': page,
                'total_pages': total_pages,
                'total_records': total_records,
                'limit': limit
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/payments/stats', methods=['GET'])
@require_admin()
def get_payments_stats(admin_id):
    """Estatísticas de pagamentos para o dashboard admin"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Total de pagamentos
        cursor.execute("SELECT COUNT(*) FROM payments")
        total_payments = cursor.fetchone()[0]
        
        # Pagamentos aprovados
        cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'approved'")
        approved_payments = cursor.fetchone()[0]
        
        # Pagamentos pendentes
        cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
        pending_payments = cursor.fetchone()[0]
        
        # Receita total (apenas approved)
        cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'approved'")
        total_revenue = cursor.fetchone()[0]
        
        # Receita do mês atual
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM payments 
            WHERE status = 'approved' 
            AND EXTRACT(MONTH FROM created_at) = EXTRACT(MONTH FROM CURRENT_DATE)
            AND EXTRACT(YEAR FROM created_at) = EXTRACT(YEAR FROM CURRENT_DATE)
        """)
        monthly_revenue = cursor.fetchone()[0]
        
        # Últimos pagamentos (5 mais recentes)
        cursor.execute("""
            SELECT p.payment_id, p.amount, p.status, p.plan_name, p.created_at,
                   u.name as user_name, u.email as user_email
            FROM payments p
            LEFT JOIN users u ON p.user_id = u.id
            ORDER BY p.created_at DESC
            LIMIT 5
        """)
        
        recent_payments = []
        for row in cursor.fetchall():
            payment_id, amount, status, plan_name, created_at, user_name, user_email = row
            
            recent_payments.append({
                'payment_id': payment_id,
                'amount': float(amount) if amount else 0.0,
                'formatted_amount': f"R$ {float(amount):,.2f}" if amount else "R$ 0,00",
                'status': status,
                'plan_name': plan_name,
                'user_name': user_name,
                'user_email': user_email,
                'created_at': created_at.isoformat() if created_at else None,
                'formatted_date': created_at.strftime('%d/%m/%Y %H:%M') if created_at else 'N/A'
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_payments': total_payments,
                'approved_payments': approved_payments,
                'pending_payments': pending_payments,
                'failed_payments': total_payments - approved_payments - pending_payments,
                'total_revenue': float(total_revenue),
                'monthly_revenue': float(monthly_revenue),
                'formatted_total_revenue': f"R$ {float(total_revenue):,.2f}",
                'formatted_monthly_revenue': f"R$ {float(monthly_revenue):,.2f}"
            },
            'recent_payments': recent_payments
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/payments/<payment_id>/details', methods=['GET'])
@require_admin()
def get_payment_details(admin_id, payment_id):
    """Detalhes específicos de um pagamento"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT p.id, p.payment_id, p.status, p.amount, p.plan_id, p.plan_name,
                   p.cycle, p.external_reference, p.device_id, p.created_at, p.updated_at,
                   u.id as user_id, u.name as user_name, u.email as user_email,
                   u.plan_id as current_plan_id, u.plan_name as current_plan_name
            FROM payments p
            LEFT JOIN users u ON p.user_id = u.id
            WHERE p.payment_id = %s
        """, (payment_id,))
        
        payment = cursor.fetchone()
        
        if not payment:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Pagamento não encontrado'}), 404
        
        # Extrair dados
        p_id, mp_payment_id, status, amount, plan_id, plan_name, cycle, external_ref, device_id, created_at, updated_at, user_id, user_name, user_email, current_plan_id, current_plan_name = payment
        
        payment_details = {
            'id': p_id,
            'payment_id': mp_payment_id,
            'status': status,
            'amount': float(amount) if amount else 0.0,
            'formatted_amount': f"R$ {float(amount):,.2f}" if amount else "R$ 0,00",
            'plan_id': plan_id,
            'plan_name': plan_name,
            'cycle': cycle,
            'external_reference': external_ref,
            'device_id': device_id,
            'created_at': created_at.isoformat() if created_at else None,
            'updated_at': updated_at.isoformat() if updated_at else None,
            'formatted_created': created_at.strftime('%d/%m/%Y %H:%M:%S') if created_at else 'N/A',
            'formatted_updated': updated_at.strftime('%d/%m/%Y %H:%M:%S') if updated_at else 'N/A',
            'user': {
                'id': user_id,
                'name': user_name,
                'email': user_email,
                'current_plan_id': current_plan_id,
                'current_plan_name': current_plan_name
            }
        }
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'payment': payment_details
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


#======= rotas banco de dados recomentações free=============

@admin_bp.route('/enhanced-stats')
@require_admin()
def get_enhanced_admin_stats(admin_id):
    """Estatísticas aprimoradas do admin"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
        
        cursor = conn.cursor()
        
        # Usuários
        cursor.execute("SELECT COUNT(*) FROM users WHERE user_type != 'deleted'")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE plan_id IN (1, 2) AND user_type != 'deleted'")
        premium_users = cursor.fetchone()[0]
        
        # Cupons ativos - CORRIGIDO
        try:
            cursor.execute("SELECT COUNT(*) FROM coupons WHERE active = true")
            active_coupons = cursor.fetchone()[0]
        except:
            active_coupons = 0
        
        # Receita estimada
        cursor.execute("""
            SELECT COALESCE(SUM(
                CASE 
                    WHEN plan_id = 1 THEN 79 
                    WHEN plan_id = 2 THEN 149 
                    ELSE 0 
                END
            ), 0) FROM users WHERE plan_id IN (1, 2) AND user_type != 'deleted'
        """)
        estimated_revenue = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'total_users': total_users,
                'premium_users': premium_users,
                'active_coupons': active_coupons,
                'estimated_monthly_revenue': estimated_revenue
            }
        })
        
    except Exception as e:
        print(f"Erro nas estatísticas aprimoradas: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/recent-activity')
@require_admin()  
def get_recent_activity(admin_id):
    """Atividade recente do sistema"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
        
        cursor = conn.cursor()
        
        activities = []
        
        # Usuários recentes (último dia)
        try:
            cursor.execute("""
                SELECT name, email, created_at 
                FROM users 
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                AND user_type != 'deleted'
                ORDER BY created_at DESC 
                LIMIT 3
            """)
            recent_users = cursor.fetchall()
            
            for user in recent_users:
                activities.append({
                    'type': 'new_user',
                    'message': f'Novo usuário: {user[0]}',
                    'time': 'Hoje',
                    'icon': 'fas fa-user-plus',
                    'color': 'text-green-400'
                })
        except Exception as e:
            print(f"Erro ao buscar usuários recentes: {e}")
        
        # Recomendações recentes (última semana)
        try:
            cursor.execute("""
                SELECT ticker, action, created_at
                FROM recommendations_free 
                WHERE created_at >= NOW() - INTERVAL '7 days'
                ORDER BY created_at DESC 
                LIMIT 2
            """)
            recent_recs = cursor.fetchall()
            
            for rec in recent_recs:
                activities.append({
                    'type': 'recommendation',
                    'message': f'Nova recomendação: {rec[0]} ({rec[1]})',
                    'time': 'Esta semana',
                    'icon': 'fas fa-chart-line',
                    'color': 'text-blue-400'
                })
        except Exception as e:
            print(f"Erro ao buscar recomendações recentes: {e}")
        
        # Se não há atividades reais, mostrar atividades do sistema
        if not activities:
            activities = [
                {
                    'type': 'system',
                    'message': 'Sistema funcionando normalmente',
                    'time': 'Agora',
                    'icon': 'fas fa-check-circle',
                    'color': 'text-green-400'
                },
                {
                    'type': 'database',
                    'message': 'Banco de dados conectado e operacional',
                    'time': '1 minuto atrás',
                    'icon': 'fas fa-database',
                    'color': 'text-blue-400'
                },
                {
                    'type': 'admin_access',
                    'message': 'Painel administrativo acessado',
                    'time': '2 minutos atrás',
                    'icon': 'fas fa-shield-alt',
                    'color': 'text-purple-400'
                }
            ]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'activities': activities
        })
        
    except Exception as e:
        print(f"Erro na atividade recente: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== ADICIONE ESTA ROTA NO SEU admin_routes.py =====
# Coloque no final do arquivo, antes da linha "def get_admin_blueprint():"

@admin_bp.route('/portfolio/add-asset', methods=['POST'])
@require_admin()
def add_portfolio_asset_missing_route(admin_id):
    """Adicionar ativo à carteira - ROTA QUE ESTAVA FALTANDO"""
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
        
        # Validações
        if not all([portfolio, ticker, weight, sector, entry_price, target_price]):
            return jsonify({'success': False, 'error': 'Dados obrigatórios faltando'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        try:
            # Inserir ativo
            cursor.execute("""
                INSERT INTO portfolio_assets (
                    portfolio_name, ticker, weight, sector, entry_price, 
                    current_price, target_price, entry_date, is_active,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (portfolio_name, ticker) 
                DO UPDATE SET 
                    weight = EXCLUDED.weight,
                    sector = EXCLUDED.sector,
                    entry_price = EXCLUDED.entry_price,
                    current_price = EXCLUDED.current_price,
                    target_price = EXCLUDED.target_price,
                    entry_date = EXCLUDED.entry_date,
                    is_active = true,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
            """, (
                portfolio, ticker, weight, sector, entry_price, 
                current_price, target_price, entry_date, True
            ))
            
            result = cursor.fetchone()
            asset_id = result[0] if result else None
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': f'Ativo {ticker} adicionado à carteira {portfolio} com sucesso!',
                'asset_id': asset_id
            })
            
        except Exception as e:
            conn.rollback()
            cursor.close()
            conn.close()
            print(f"❌ Erro SQL: {e}")
            return jsonify({'success': False, 'error': f'Erro no banco: {str(e)}'}), 500
        
    except Exception as e:
        print(f"❌ Erro geral: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== FUNÇÃO EXPORT =====
def get_admin_blueprint():
    """Retornar blueprint para registrar no Flask"""
    return admin_bp
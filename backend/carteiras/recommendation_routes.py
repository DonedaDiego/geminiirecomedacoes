from flask import Blueprint, jsonify, request
import jwt
from functools import wraps
from database import get_db_connection
import os

# ===== IMPORTAR SERVIÇOS =====
from carteiras.recommendation_service import (
    verify_token,
    get_company_info,
    get_admin_portfolio_recommendations_service,
    add_portfolio_recommendation_service,
    update_portfolio_recommendation_service,
    delete_portfolio_recommendation_service,
    get_user_portfolio_recommendations_service,
    generate_rebalance_recommendations_service,
    get_user_portfolios_service,
    get_user_portfolio_recommendations_detailed_service,
    get_user_portfolio_assets_service,
    get_admin_stats_service
)

# Criar blueprint
recommendations_bp = Blueprint('recommendations', __name__, url_prefix='/api')

# ===== DECORATORS =====

def require_admin(f):
    """Decorator para verificar se usuário é admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'error': 'Token não fornecido'}), 401
        
        token = auth_header.replace('Bearer ', '')
        user_data = verify_token(token)
        
        if not user_data:
            return jsonify({'success': False, 'error': 'Token inválido'}), 401
        
        # Verificar se é admin
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT user_type FROM users WHERE id = %s", (user_data['user_id'],))
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not result or result[0] not in ['admin', 'master']:
                return jsonify({'success': False, 'error': 'Acesso negado'}), 403
                
        except Exception as e:
            return jsonify({'success': False, 'error': 'Erro de verificação'}), 500
        
        return f(*args, **kwargs)
    return decorated_function

def require_token(f):
    """Decorator para verificar token válido"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'error': 'Token não fornecido'}), 401
        
        token = auth_header.replace('Bearer ', '')
        user_data = verify_token(token)
        
        if not user_data:
            return jsonify({'success': False, 'error': 'Token inválido'}), 401
        
        return f(*args, **kwargs)
    return decorated_function

# ===== ROTAS DE RECOMENDAÇÕES =====

@recommendations_bp.route('/admin/portfolio/<portfolio_name>/recommendations', methods=['GET'])
@require_admin
def get_admin_portfolio_recommendations(portfolio_name):
    """Buscar recomendações de uma carteira (Admin)"""
    result = get_admin_portfolio_recommendations_service(portfolio_name)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 500

@recommendations_bp.route('/admin/portfolio/add-recommendation', methods=['POST'])
@require_admin
def add_portfolio_recommendation():
    """Adicionar nova recomendação"""
    try:
        data = request.get_json()
        
        # Buscar ID do usuário admin atual
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user_data = verify_token(token)
        admin_id = user_data.get('user_id') if user_data else None
        
        result = add_portfolio_recommendation_service(data, admin_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
        
    except Exception as e:
        print(f"Error adding recommendation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@recommendations_bp.route('/admin/portfolio/update-recommendation', methods=['PUT'])
@require_admin
def update_portfolio_recommendation():
    """Atualizar recomendação existente"""
    try:
        data = request.get_json()
        result = update_portfolio_recommendation_service(data)
        
        if result['success']:
            return jsonify(result)
        else:
            status_code = 404 if 'não encontrada' in result['error'] else 400
            return jsonify(result), status_code
        
    except Exception as e:
        print(f"Error updating recommendation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@recommendations_bp.route('/admin/portfolio/delete-recommendation', methods=['DELETE'])
@require_admin
def delete_portfolio_recommendation():
    """Deletar recomendação"""
    try:
        data = request.get_json()
        recommendation_id = data.get('id')
        
        result = delete_portfolio_recommendation_service(recommendation_id)
        
        if result['success']:
            return jsonify(result)
        else:
            status_code = 404 if 'não encontrada' in result['error'] else 400
            return jsonify(result), status_code
        
    except Exception as e:
        print(f"Error deleting recommendation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@recommendations_bp.route('/admin/portfolio/generate-rebalance', methods=['POST'])
@require_admin
def generate_rebalance_recommendations():
    """Gerar recomendações de VENDA automáticas para rebalanceamento"""
    try:
        data = request.get_json()
        portfolio = data.get('portfolio')
        reason = data.get('reason', 'Rebalanceamento automático - Ajuste de portfólio conforme nova estratégia')
        
        # Extrair user_id do token
        token = request.headers.get('Authorization').replace('Bearer ', '')
        user_data = verify_token(token)
        admin_user_id = user_data['user_id'] if user_data else None
        
        result = generate_rebalance_recommendations_service(portfolio, reason, admin_user_id)
        
        if result['success']:
            return jsonify(result)
        else:
            status_code = 404 if 'não encontrado' in result['error'] else 400
            return jsonify(result), status_code
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== ROTAS DE ATIVOS =====

@recommendations_bp.route('/admin/portfolio/add-asset', methods=['POST'])
@require_admin
def add_portfolio_asset():
    """Adicionar ativo a uma carteira"""
    try:
        data = request.get_json()
        
        # Validar dados obrigatórios
        required_fields = ['portfolio', 'ticker', 'weight', 'sector', 'entry_price', 'target_price', 'entry_date']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Campo {field} é obrigatório'}), 400
        
        # Verificar se peso está dentro dos limites
        if data['weight'] <= 0 or data['weight'] > 100:
            return jsonify({'success': False, 'error': 'Peso deve estar entre 0 e 100'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Verificar se ativo já existe na carteira
        cursor.execute("""
            SELECT id FROM portfolio_assets 
            WHERE portfolio_name = %s AND ticker = %s AND is_active = true
        """, (data['portfolio'], data['ticker'].upper()))
        
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': f'Ativo {data["ticker"]} já existe nesta carteira'}), 400
        
        # Inserir novo ativo
        cursor.execute("""
            INSERT INTO portfolio_assets 
            (portfolio_name, ticker, weight, sector, entry_price, current_price, target_price, entry_date, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, true)
        """, (
            data['portfolio'],
            data['ticker'].upper(),
            data['weight'],
            data['sector'],
            data['entry_price'],
            data.get('current_price', data['entry_price']),
            data['target_price'],
            data['entry_date']
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Ativo {data["ticker"]} adicionado com sucesso à carteira {data["portfolio"]}!'
        })
        
    except Exception as e:
        print(f"Error adding asset: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@recommendations_bp.route('/admin/portfolio/<portfolio_name>/assets', methods=['GET'])
@require_admin
def get_portfolio_assets(portfolio_name):
    """Buscar ativos de uma carteira"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, ticker, weight, sector, entry_price, current_price, target_price, entry_date, created_at
            FROM portfolio_assets 
            WHERE portfolio_name = %s AND is_active = true
            ORDER BY weight DESC
        """, (portfolio_name,))
        
        assets = []
        total_weight = 0
        
        for row in cursor.fetchall():
            asset = {
                'id': row[0],
                'ticker': row[1],
                'weight': float(row[2]) if row[2] else 0,
                'sector': row[3],
                'entry_price': float(row[4]) if row[4] else 0,
                'current_price': float(row[5]) if row[5] else 0,
                'target_price': float(row[6]) if row[6] else 0,
                'entry_date': row[7].isoformat() if row[7] else None,
                'created_at': row[8].isoformat() if row[8] else None
            }
            assets.append(asset)
            total_weight += asset['weight']
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'assets': assets,
            'total_weight': total_weight,
            'portfolio_name': portfolio_name
        })
        
    except Exception as e:
        print(f"Error getting assets: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@recommendations_bp.route('/admin/portfolio/remove-asset', methods=['DELETE'])
@require_admin
def remove_portfolio_asset():
    """Remover ativo de uma carteira"""
    try:
        data = request.get_json()
        
        if 'id' not in data:
            return jsonify({'success': False, 'error': 'ID do ativo é obrigatório'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Verificar se ativo existe
        cursor.execute("SELECT ticker FROM portfolio_assets WHERE id = %s", (data['id'],))
        asset = cursor.fetchone()
        
        if not asset:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Ativo não encontrado'}), 404
        
        # Marcar como inativo
        cursor.execute("""
            UPDATE portfolio_assets 
            SET is_active = false, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (data['id'],))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Ativo {asset[0]} removido com sucesso!'
        })
        
    except Exception as e:
        print(f"Error removing asset: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@recommendations_bp.route('/admin/portfolio/update-asset', methods=['PUT'])
@require_admin
def update_portfolio_asset():
    """Atualizar ativo de uma carteira"""
    try:
        data = request.get_json()
        
        if 'id' not in data:
            return jsonify({'success': False, 'error': 'ID do ativo é obrigatório'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Construir query dinâmica
        update_fields = []
        update_values = []
        
        updatable_fields = ['weight', 'sector', 'entry_price', 'current_price', 'target_price', 'entry_date']
        for field in updatable_fields:
            if field in data:
                update_fields.append(f"{field} = %s")
                update_values.append(data[field])
        
        if not update_fields:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Nenhum campo para atualizar'}), 400
        
        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        update_values.append(data['id'])
        
        query = f"""
            UPDATE portfolio_assets 
            SET {', '.join(update_fields)}
            WHERE id = %s
        """
        
        cursor.execute(query, update_values)
        conn.commit()
        
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Ativo não encontrado'}), 404
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Ativo atualizado com sucesso!'
        })
        
    except Exception as e:
        print(f"Error updating asset: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@recommendations_bp.route('/admin/portfolio/clear-assets', methods=['DELETE'])
@require_admin
def clear_portfolio_assets():
    """Limpar todos os ativos de uma carteira"""
    try:
        data = request.get_json()
        
        if 'portfolio' not in data:
            return jsonify({'success': False, 'error': 'Nome da carteira é obrigatório'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Contar ativos antes de remover
        cursor.execute("""
            SELECT COUNT(*) FROM portfolio_assets 
            WHERE portfolio_name = %s AND is_active = true
        """, (data['portfolio'],))
        
        count = cursor.fetchone()[0]
        
        if count == 0:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Nenhum ativo encontrado nesta carteira'}), 400
        
        # Marcar todos como inativos
        cursor.execute("""
            UPDATE portfolio_assets 
            SET is_active = false, updated_at = CURRENT_TIMESTAMP
            WHERE portfolio_name = %s AND is_active = true
        """, (data['portfolio'],))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'{count} ativos removidos da carteira {data["portfolio"]}!'
        })
        
    except Exception as e:
        print(f"Error clearing assets: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== ROTAS DE USUÁRIO =====

@recommendations_bp.route('/portfolio/<portfolio_name>/recommendations', methods=['GET'])
@require_token
def get_user_portfolio_recommendations(portfolio_name):
    """Endpoint público para usuários verem recomendações"""
    result = get_user_portfolio_recommendations_service(portfolio_name)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 500

@recommendations_bp.route('/user/my-portfolios', methods=['GET'])
@require_token
def get_user_portfolios():
    """Buscar carteiras que o usuário tem acesso"""
    try:
        auth_header = request.headers.get('Authorization')
        token = auth_header.replace('Bearer ', '')
        user_data = verify_token(token)
        user_id = user_data['user_id']
        
        result = get_user_portfolios_service(user_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 500
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@recommendations_bp.route('/user/portfolio/<portfolio_name>/recommendations', methods=['GET'])
@require_token
def get_user_portfolio_recommendations_detailed(portfolio_name):
    """Buscar recomendações detalhadas de uma carteira para o usuário"""
    try:
        auth_header = request.headers.get('Authorization')
        token = auth_header.replace('Bearer ', '')
        user_data = verify_token(token)
        user_id = user_data['user_id']
        
        result = get_user_portfolio_recommendations_detailed_service(portfolio_name, user_id)
        
        if result['success']:
            return jsonify(result)
        else:
            status_code = 403 if 'Acesso negado' in result['error'] else 500
            return jsonify(result), status_code
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@recommendations_bp.route('/user/portfolio/<portfolio_name>/assets', methods=['GET'])
@require_token  
def get_user_portfolio_assets(portfolio_name):
    """Buscar ativos de uma carteira para o usuário"""
    try:
        auth_header = request.headers.get('Authorization')
        token = auth_header.replace('Bearer ', '')
        user_data = verify_token(token)
        user_id = user_data['user_id']
        
        result = get_user_portfolio_assets_service(portfolio_name, user_id)
        
        if result['success']:
            return jsonify(result)
        else:
            status_code = 403 if 'Acesso negado' in result['error'] else 500
            return jsonify(result), status_code
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== ROTAS AUXILIARES =====

@recommendations_bp.route('/company-info/<ticker>', methods=['GET'])
@require_token
def get_company_info_endpoint(ticker):
    """Buscar informações de uma empresa específica"""
    try:
        company_info = get_company_info(ticker.upper())
        
        return jsonify({
            'success': True,
            'ticker': ticker.upper(),
            'company': company_info
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@recommendations_bp.route('/admin/stats', methods=['GET'])
@require_admin
def get_admin_stats():
    """Buscar estatísticas do admin dashboard"""
    result = get_admin_stats_service()
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 500

def get_recommendations_blueprint():
    """Retorna o blueprint configurado"""
    return recommendations_bp
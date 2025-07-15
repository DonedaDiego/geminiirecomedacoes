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

# ===== ADMIN ENDPOINTS =====

@recommendations_bp.route('/admin/portfolio/<portfolio_name>/recommendations', methods=['GET'])
@require_admin
def get_admin_portfolio_recommendations(portfolio_name):
    """Buscar recomendações de uma carteira (Admin) - COM INFO DAS EMPRESAS"""
    result = get_admin_portfolio_recommendations_service(portfolio_name)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 500
    
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

# ===== USER ENDPOINTS =====

@recommendations_bp.route('/portfolio/<portfolio_name>/recommendations', methods=['GET'])
@require_token
def get_user_portfolio_recommendations(portfolio_name):
    """Endpoint público para usuários verem recomendações"""
    result = get_user_portfolio_recommendations_service(portfolio_name)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 500

# ===== ADMIN STATS =====

@recommendations_bp.route('/admin/stats', methods=['GET'])
@require_admin
def get_admin_stats():
    """Buscar estatísticas do admin dashboard"""
    result = get_admin_stats_service()
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 500

# ===== ROTAS DE PORTFOLIO =====

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

# ===== ENDPOINTS PARA USUÁRIOS FINAIS =====

@recommendations_bp.route('/user/my-portfolios', methods=['GET'])
@require_token
def get_user_portfolios():
    """Buscar carteiras que o usuário tem acesso (ADMIN TEM ACESSO TOTAL)"""
    try:
        # Extrair user_id do token
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

def get_recommendations_blueprint():
    """Retorna o blueprint configurado"""
    return recommendations_bp
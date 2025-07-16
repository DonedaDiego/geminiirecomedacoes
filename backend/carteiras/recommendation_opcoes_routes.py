from flask import Blueprint, jsonify, request
import jwt
from functools import wraps
from database import get_db_connection
import os

# ===== IMPORTAR SERVIÇOS =====
from carteiras.recommendation_opcoes_service import (
    verify_token,
    create_opcoes_recommendation_service,
    get_all_opcoes_recommendations_service,
    update_opcoes_recommendation_service,
    delete_opcoes_recommendation_service,
    close_opcoes_recommendation_service,
    get_opcoes_stats_service
)

# Criar blueprint
opcoes_recommendations_bp = Blueprint('opcoes_recommendations', __name__, url_prefix='/api/opcoes')

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

# ===== ROTAS ADMINISTRATIVAS =====

@opcoes_recommendations_bp.route('/admin/create', methods=['POST'])
@require_admin
def create_opcoes_recommendation():
    """Criar nova recomendação de opção"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados JSON necessários'}), 400
        
        # Buscar ID do usuário admin atual
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user_data = verify_token(token)
        admin_id = user_data.get('user_id') if user_data else None
        
        result = create_opcoes_recommendation_service(data, admin_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
        
    except Exception as e:
        print(f"Error creating opcoes recommendation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@opcoes_recommendations_bp.route('/admin/all', methods=['GET'])
@require_admin
def get_all_opcoes_recommendations():
    """Buscar todas as recomendações de opções (Admin)"""
    result = get_all_opcoes_recommendations_service()
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 500

@opcoes_recommendations_bp.route('/admin/update', methods=['PUT'])
@require_admin
def update_opcoes_recommendation():
    """Atualizar recomendação de opção"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados JSON necessários'}), 400
        
        result = update_opcoes_recommendation_service(data)
        
        if result['success']:
            return jsonify(result)
        else:
            status_code = 404 if 'não encontrada' in result['error'] else 400
            return jsonify(result), status_code
        
    except Exception as e:
        print(f"Error updating opcoes recommendation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@opcoes_recommendations_bp.route('/admin/delete/<int:recommendation_id>', methods=['DELETE'])
@require_admin
def delete_opcoes_recommendation(recommendation_id):
    """Deletar recomendação de opção"""
    try:
        result = delete_opcoes_recommendation_service(recommendation_id)
        
        if result['success']:
            return jsonify(result)
        else:
            status_code = 404 if 'não encontrada' in result['error'] else 400
            return jsonify(result), status_code
        
    except Exception as e:
        print(f"Error deleting opcoes recommendation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@opcoes_recommendations_bp.route('/admin/close/<int:recommendation_id>', methods=['POST'])
@require_admin
def close_opcoes_recommendation(recommendation_id):
    """Fechar recomendação de opção com resultado"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados JSON necessários'}), 400
        
        status = data.get('status')
        resultado_final = data.get('resultado_final')
        
        if not status:
            return jsonify({'success': False, 'error': 'Status é obrigatório'}), 400
        
        result = close_opcoes_recommendation_service(recommendation_id, status, resultado_final)
        
        if result['success']:
            return jsonify(result)
        else:
            status_code = 404 if 'não encontrada' in result['error'] else 400
            return jsonify(result), status_code
        
    except Exception as e:
        print(f"Error closing opcoes recommendation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@opcoes_recommendations_bp.route('/admin/stats', methods=['GET'])
@require_admin
def get_opcoes_stats():
    """Buscar estatísticas das recomendações de opções"""
    result = get_opcoes_stats_service()
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 500

# ===== ROTAS PÚBLICAS PARA USUÁRIOS =====

@opcoes_recommendations_bp.route('/public/active', methods=['GET'])
@require_token
def get_active_opcoes_recommendations():
    """Buscar recomendações ativas de opções para usuários"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # ✅ CORRIGIR: ADICIONAR CAMPO STATUS
        cursor.execute('''
            SELECT 
                ativo_spot, ticker_opcao, strike, valor_entrada, 
                vencimento, data_recomendacao, stop, gain, gain_parcial, status
            FROM opcoes_recommendations 
            WHERE status = 'ATIVA' AND is_active = true
            ORDER BY data_recomendacao DESC
            LIMIT 20
        ''')
        
        recommendations = []
        for row in cursor.fetchall():
            recommendations.append({
                'ativo_spot': row[0],
                'ticker_opcao': row[1],
                'strike': float(row[2]) if row[2] else 0,
                'valor_entrada': float(row[3]) if row[3] else 0,
                'vencimento': row[4].isoformat() if row[4] else None,
                'data_recomendacao': row[5].isoformat() if row[5] else None,
                'stop': float(row[6]) if row[6] else 0,
                'gain': float(row[7]) if row[7] else 0,
                'gain_parcial': float(row[8]) if row[8] else None,
                'status': row[9]  
            })
    
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'recommendations': recommendations
        })
        
    except Exception as e:
        print(f"Error getting active opcoes recommendations: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@opcoes_recommendations_bp.route('/public/recent', methods=['GET'])
@require_token
def get_recent_opcoes_recommendations():
    """Buscar recomendações recentes de opções (incluindo finalizadas)"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                ativo_spot, ticker_opcao, strike, valor_entrada, 
                vencimento, data_recomendacao, stop, gain, gain_parcial,
                status, performance, resultado_final
            FROM opcoes_recommendations 
            WHERE is_active = true
            ORDER BY data_recomendacao DESC
            LIMIT 10
        ''')
        
        recommendations = []
        for row in cursor.fetchall():
            recommendations.append({
                'ativo_spot': row[0],
                'ticker_opcao': row[1],
                'strike': float(row[2]) if row[2] else 0,
                'valor_entrada': float(row[3]) if row[3] else 0,
                'vencimento': row[4].isoformat() if row[4] else None,
                'data_recomendacao': row[5].isoformat() if row[5] else None,
                'stop': float(row[6]) if row[6] else 0,
                'gain': float(row[7]) if row[7] else 0,
                'gain_parcial': float(row[8]) if row[8] else None,
                'status': row[9],
                'performance': float(row[10]) if row[10] else None,
                'resultado_final': float(row[11]) if row[11] else None
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'recommendations': recommendations
        })
        
    except Exception as e:
        print(f"Error getting recent opcoes recommendations: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== FUNÇÃO PARA RETORNAR BLUEPRINT =====

def get_opcoes_recommendations_blueprint():
    """Retorna o blueprint configurado"""
    return opcoes_recommendations_bp
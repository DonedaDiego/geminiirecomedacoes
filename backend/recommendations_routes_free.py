# recommendations_routes_free.py

from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
import jwt
from recommendations_service_free import RecommendationsServiceFree, create_recommendations_table
from functools import wraps

# Criar Blueprint
recommendations_free_bp = Blueprint('recommendations_free', __name__, url_prefix='/api/recommendations')

# Decorator para verificar autenticação
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'error': 'Token não fornecido'}), 401
        
        token = auth_header.replace('Bearer ', '')
        
        try:
            from flask import current_app
            payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            request.user_id = payload['user_id']
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'error': 'Token expirado'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'success': False, 'error': 'Token inválido'}), 401
    
    return decorated_function

# ===== ROTAS PÚBLICAS (REQUEREM AUTENTICAÇÃO) =====

@recommendations_free_bp.route('/free/active', methods=['GET'])
@require_auth
def get_active_recommendations():
    """Buscar recomendações ativas"""
    try:
        # Atualizar preços antes de retornar
        RecommendationsServiceFree.update_current_prices()
        
        # Buscar recomendações
        recommendations = RecommendationsServiceFree.get_active_recommendations()
        
        return jsonify({
            'success': True,
            'recommendations': recommendations,
            'count': len(recommendations)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao buscar recomendações: {str(e)}'
        }), 500

@recommendations_free_bp.route('/free/statistics', methods=['GET'])
@require_auth
def get_statistics():
    """Buscar estatísticas de performance"""
    try:
        stats = RecommendationsServiceFree.get_statistics()
        
        if stats:
            return jsonify({
                'success': True,
                'statistics': stats
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Erro ao calcular estatísticas'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao buscar estatísticas: {str(e)}'
        }), 500

@recommendations_free_bp.route('/free/<int:rec_id>/chart-data', methods=['GET'])
@require_auth
def get_recommendation_chart(rec_id):
    """Buscar dados para gráfico de uma recomendação"""
    try:
        # Buscar ticker da recomendação
        from database import get_db_connection
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        cursor.execute("SELECT ticker FROM recommendations_free WHERE id = %s", (rec_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not result:
            return jsonify({'success': False, 'error': 'Recomendação não encontrada'}), 404
            
        ticker = result[0]
        
        # Buscar dados do gráfico
        chart_data = RecommendationsServiceFree.get_chart_data(ticker, days=30)
        
        if chart_data:
            return jsonify({
                'success': True,
                'data': chart_data
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Erro ao buscar dados do gráfico'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao buscar gráfico: {str(e)}'
        }), 500

@recommendations_free_bp.route('/free/performance-history', methods=['GET'])
@require_auth
def get_performance_history():
    """Buscar histórico de performance"""
    try:
        history = RecommendationsServiceFree.get_performance_history()
        
        return jsonify({
            'success': True,
            'history': history
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao buscar histórico: {str(e)}'
        }), 500

# ===== ROTAS ADMIN =====

def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'error': 'Token não fornecido'}), 401
        
        token = auth_header.replace('Bearer ', '')
        
        try:
            from flask import current_app
            payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            user_id = payload['user_id']
            
            # Verificar se é admin
            from database import get_db_connection
            conn = get_db_connection()
            if not conn:
                return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
                
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_type FROM users 
                WHERE id = %s AND user_type IN ('admin', 'master')
            """, (user_id,))
            
            admin = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not admin:
                return jsonify({'success': False, 'error': 'Acesso negado'}), 403
                
            request.admin_id = user_id
            return f(*args, **kwargs)
            
        except Exception as e:
            return jsonify({'success': False, 'error': 'Token inválido'}), 401
    
    return decorated_function

@recommendations_free_bp.route('/admin/generate', methods=['POST'])
@require_admin
def generate_recommendations():
    """Gerar novas recomendações mensais (Admin)"""
    try:
        # Verificar se já existem recomendações ativas este mês
        from database import get_db_connection
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM recommendations_free 
            WHERE status = 'ATIVA' 
            AND created_at >= DATE_TRUNC('month', CURRENT_DATE)
        """)
        
        active_count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        
        if active_count > 0:
            return jsonify({
                'success': False,
                'error': f'Já existem {active_count} recomendações ativas este mês'
            }), 400
        
        # Gerar novas recomendações
        recommendations = RecommendationsServiceFree.generate_monthly_recommendations()
        
        if not recommendations:
            return jsonify({
                'success': False,
                'error': 'Nenhuma recomendação gerada'
            }), 400
        
        # Salvar no banco
        result = RecommendationsServiceFree.save_recommendations(recommendations)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': f'{result["saved_count"]} recomendações geradas com sucesso',
                'recommendations': recommendations
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao gerar recomendações: {str(e)}'
        }), 500

@recommendations_free_bp.route('/admin/close/<int:rec_id>', methods=['POST'])
@require_admin
def close_recommendation(rec_id):
    """Encerrar uma recomendação manualmente"""
    try:
        data = request.get_json()
        status = data.get('status', 'FINALIZADA_MANUAL')
        final_price = data.get('final_price')
        
        from database import get_db_connection
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Buscar recomendação
        cursor.execute("""
            SELECT entry_price, action FROM recommendations_free 
            WHERE id = %s AND status = 'ATIVA'
        """, (rec_id,))
        
        rec = cursor.fetchone()
        if not rec:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Recomendação não encontrada ou já finalizada'}), 404
        
        entry_price, action = rec
        
        # Calcular performance final
        if final_price:
            performance = ((final_price - entry_price) / entry_price * 100)
            if action == 'VENDA':
                performance = -performance
        else:
            performance = 0
        
        # Atualizar recomendação
        cursor.execute("""
            UPDATE recommendations_free
            SET status = %s, 
                current_price = %s,
                performance = %s,
                closed_at = %s,
                updated_at = %s
            WHERE id = %s
        """, (
            status,
            final_price or entry_price,
            performance,
            datetime.now(timezone.utc),
            datetime.now(timezone.utc),
            rec_id
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Recomendação encerrada com sucesso',
            'performance': performance
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao encerrar recomendação: {str(e)}'
        }), 500

@recommendations_free_bp.route('/admin/update-prices', methods=['POST'])
@require_admin
def update_prices():
    """Atualizar preços manualmente"""
    try:
        success = RecommendationsServiceFree.update_current_prices()
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Preços atualizados com sucesso'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Erro ao atualizar preços'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao atualizar preços: {str(e)}'
        }), 500

@recommendations_free_bp.route('/admin/create-single', methods=['POST'])
@require_admin
def create_single_recommendation():
    """Criar uma recomendação individual"""
    try:
        data = request.get_json()
        
        # Validar dados
        required_fields = ['ticker', 'action', 'entry_price', 'stop_loss', 'target_price']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Campo {field} é obrigatório'}), 400
        
        # Buscar nome da empresa
        stock_data = RecommendationsServiceFree.get_stock_data(data['ticker'])
        company_name = stock_data['company_name'] if stock_data else data['ticker']
        
        # Criar recomendação
        recommendation = {
            'ticker': data['ticker'].upper(),
            'company_name': company_name,
            'action': data['action'].upper(),
            'entry_price': float(data['entry_price']),
            'stop_loss': float(data['stop_loss']),
            'target_price': float(data['target_price']),
            'current_price': float(data.get('current_price', data['entry_price'])),
            'confidence': float(data.get('confidence', 85)),
            'risk_reward': abs((data['target_price'] - data['entry_price']) / (data['entry_price'] - data['stop_loss'])),
            'technical_data': data.get('technical_data', {})
        }
        
        # Salvar
        result = RecommendationsServiceFree.save_recommendations([recommendation])
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'Recomendação criada com sucesso'
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao criar recomendação: {str(e)}'
        }), 500

@recommendations_free_bp.route('/admin/all', methods=['GET'])
@require_admin
def get_all_recommendations():
    """Buscar todas as recomendações (admin)"""
    try:
        from database import get_db_connection
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, ticker, company_name, action, entry_price, stop_loss,
                   target_price, current_price, confidence, risk_reward,
                   technical_data, status, created_at, performance, closed_at
            FROM recommendations_free
            ORDER BY created_at DESC
            LIMIT 100
        """)
        
        recommendations = []
        for row in cursor.fetchall():
            recommendations.append({
                'id': row[0],
                'ticker': row[1],
                'company_name': row[2],
                'action': row[3],
                'entry_price': float(row[4]),
                'stop_loss': float(row[5]),
                'target_price': float(row[6]),
                'current_price': float(row[7]),
                'confidence': float(row[8]),
                'risk_reward': float(row[9]),
                'technical_data': row[10],
                'status': row[11],
                'created_at': row[12].isoformat() if row[12] else None,
                'performance': float(row[13]) if row[13] else 0,
                'closed_at': row[14].isoformat() if row[14] else None
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'recommendations': recommendations,
            'count': len(recommendations)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao buscar recomendações: {str(e)}'
        }), 500

# Função para obter o blueprint
def get_recommendations_free_blueprint():
    """Retornar blueprint para registrar no Flask"""
    # Criar tabela se não existir
    create_recommendations_table()
    return recommendations_free_bp
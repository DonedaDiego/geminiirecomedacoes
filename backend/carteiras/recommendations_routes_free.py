# recommendations_routes_free.py - VERSÃO ATUALIZADA COM ENDPOINTS PÚBLICOS

from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
import jwt
from carteiras.recommendations_service_free import RecommendationsServiceFree, create_recommendations_table
from functools import wraps

# Criar Blueprint
recommendations_free_bp = Blueprint('recommendations_free', __name__, url_prefix='/api/recommendations')

# Decorator para verificar autenticação (USUÁRIOS COMUNS)
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

# ===== ROTAS PÚBLICAS PARA USUÁRIOS COMUNS =====

@recommendations_free_bp.route('/free/active', methods=['GET'])
@require_auth
def get_active_recommendations():
    """ PÚBLICO: Buscar recomendações ativas"""
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

@recommendations_free_bp.route('/free/all', methods=['GET'])
@require_auth
def get_all_recommendations_public():
    """ PÚBLICO: Buscar todas as recomendações (ativas + fechadas) COM AUTO-UPDATE"""
    try:
        #  AUTO-UPDATE: Atualizar preços automaticamente
        try:
            
            RecommendationsServiceFree.update_current_prices()
            
        except Exception as update_error:
            print(f"⚠️ Erro no auto-update (continuando): {update_error}")
        
        # Buscar recomendações
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
            'count': len(recommendations),
            'last_update': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao buscar recomendações: {str(e)}'
        }), 500

@recommendations_free_bp.route('/free/statistics', methods=['GET'])
@require_auth
def get_statistics_public():
    """ PÚBLICO: Buscar estatísticas de performance"""
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
def get_recommendation_chart_public(rec_id):
    """ PÚBLICO: Buscar dados para gráfico de uma recomendação"""
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
def get_performance_history_public():
    """ PÚBLICO: Buscar histórico de performance"""
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

@recommendations_free_bp.route('/free/update-prices', methods=['POST'])
@require_auth
def update_prices_public():
    """ PÚBLICO: Atualizar preços atuais via Yahoo Finance"""
    try:
        print("🔄 Iniciando atualização de preços (endpoint público)...")
        
        # Chamar função de atualização
        success = RecommendationsServiceFree.update_current_prices()
        
        if success:
            # Buscar recomendações atualizadas
            recommendations = RecommendationsServiceFree.get_active_recommendations()
            
            print(f" Preços atualizados para {len(recommendations)} recomendações")
            
            return jsonify({
                'success': True,
                'message': f'Preços atualizados com sucesso! {len(recommendations)} recomendações processadas.',
                'recommendations': recommendations,
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'count': len(recommendations)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Erro ao atualizar preços via Yahoo Finance'
            }), 500
            
    except Exception as e:
        print(f" Erro ao atualizar preços: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro ao atualizar preços: {str(e)}'
        }), 500

@recommendations_free_bp.route('/free/refresh', methods=['POST'])
@require_auth
def refresh_all_data():
    """ PÚBLICO: Refresh completo - atualiza preços e retorna dados atualizados"""
    try:
        print("🔄 Refresh completo iniciado...")
        
        # 1. Atualizar preços primeiro
        price_update_success = RecommendationsServiceFree.update_current_prices()
        
        # 2. Buscar todas as recomendações (ativas + fechadas)
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
        
        all_recommendations = []
        for row in cursor.fetchall():
            all_recommendations.append({
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
        
        # 3. Buscar estatísticas atualizadas
        stats = RecommendationsServiceFree.get_statistics()
        
        print(f" Refresh completo: {len(all_recommendations)} recomendações, preços {'atualizados' if price_update_success else 'com erro'}")
        
        return jsonify({
            'success': True,
            'message': f'Dados atualizados! {len(all_recommendations)} recomendações processadas.',
            'recommendations': all_recommendations,
            'statistics': stats,
            'price_update_success': price_update_success,
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'count': len(all_recommendations)
        })
        
    except Exception as e:
        print(f" Erro no refresh completo: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro no refresh: {str(e)}'
        }), 500


# ===== ROTAS ADMIN (MANTIDAS COMO ESTAVAM) =====

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
    """Encerrar uma recomendação manualmente - VERSÃO CORRIGIDA"""
    try:
        data = request.get_json()
        status = data.get('status', 'FINALIZADA_MANUAL')
        final_price = data.get('final_price')
        
        print(f"🔄 Encerrando recomendação {rec_id}")
        print(f" Status: {status}")
        print(f"💰 Preço final: {final_price} (tipo: {type(final_price)})")
        
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
        
        #  CONVERSÃO EXPLÍCITA PARA EVITAR CONFLITO DE TIPOS
        entry_price_float = float(entry_price)
        final_price_float = float(final_price) if final_price else entry_price_float
        
        print(f"🔢 Entry price (convertido): {entry_price_float}")
        print(f"🔢 Final price (convertido): {final_price_float}")
        
        # Calcular performance - USANDO APENAS FLOAT
        if action == 'COMPRA':
            performance = ((final_price_float - entry_price_float) / entry_price_float * 100)
        else:  # VENDA
            performance = ((entry_price_float - final_price_float) / entry_price_float * 100)
        
        print(f" Performance calculada: {performance}%")
        
        # Atualizar recomendação - USANDO VALORES CONVERTIDOS
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
            final_price_float,  #  Usar float convertido
            round(performance, 2),  #  Arredondar para evitar problemas
            datetime.now(timezone.utc),
            datetime.now(timezone.utc),
            rec_id
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f" Recomendação {rec_id} encerrada com sucesso")
        
        return jsonify({
            'success': True,
            'message': 'Recomendação encerrada com sucesso',
            'performance': round(performance, 2)
        })
        
    except Exception as e:
        print(f" Erro ao encerrar recomendação {rec_id}: {e}")
        import traceback
        traceback.print_exc()
        
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


# ===== ADICIONAR ESTE ENDPOINT NO recommendations_routes_free.py =====

@recommendations_free_bp.route('/free/dashboard-stats', methods=['GET'])
@require_auth
def get_dashboard_stats():
    """ PÚBLICO: Estatísticas simplificadas para o dashboard"""
    try:
        from database import get_db_connection
        conn = get_db_connection()
        if not conn:
            return jsonify({
                'success': True,
                'stats': {
                    'active_count': 0,
                    'success_rate': 0,
                    'days_to_next_update': 30
                }
            })
            
        cursor = conn.cursor()
        
        # Contar recomendações ativas
        cursor.execute("""
            SELECT COUNT(*) FROM recommendations_free 
            WHERE status = 'ATIVA'
        """)
        active_count = cursor.fetchone()[0] or 0
        
        # Calcular taxa de sucesso
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN status = 'FINALIZADA_GANHO' THEN 1 END) as wins,
                COUNT(CASE WHEN status LIKE 'FINALIZADA%' THEN 1 END) as total_closed
            FROM recommendations_free
            WHERE created_at >= NOW() - INTERVAL '90 days'
        """)
        
        result = cursor.fetchone()
        wins = result[0] or 0
        total_closed = result[1] or 0
        success_rate = (wins / total_closed * 100) if total_closed > 0 else 0
        
        cursor.close()
        conn.close()
        
        # Calcular próxima atualização (primeira sexta do próximo mês)
        from datetime import datetime
        now = datetime.now()
        next_month = datetime(now.year, now.month + 1, 1) if now.month < 12 else datetime(now.year + 1, 1, 1)
        first_friday = next_month
        while first_friday.weekday() != 4:  # 4 = sexta-feira
            first_friday = datetime(first_friday.year, first_friday.month, first_friday.day + 1)
        
        days_to_next_update = (first_friday - now).days
        
        return jsonify({
            'success': True,
            'stats': {
                'active_count': active_count,
                'success_rate': round(success_rate, 1),
                'days_to_next_update': max(1, days_to_next_update)
            }
        })
        
    except Exception as e:
        print(f"Erro ao buscar estatísticas do dashboard: {e}")
        # Retornar valores padrão em caso de erro
        return jsonify({
            'success': True,
            'stats': {
                'active_count': 0,
                'success_rate': 0,
                'days_to_next_update': 30
            }
        })

# Função para obter o blueprint
def get_recommendations_free_blueprint():
    create_recommendations_table()
    return recommendations_free_bp
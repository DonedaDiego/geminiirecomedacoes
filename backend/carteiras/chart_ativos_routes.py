from flask import Blueprint, request, jsonify, current_app
from carteiras.chart_ativos_service import ChartAtivosService
import logging
import jwt
from datetime import datetime
from database import get_db_connection

logger = logging.getLogger(__name__)

chart_ativos_bp = Blueprint('chart_ativos', __name__, url_prefix='/chart_ativos')
chart_service = ChartAtivosService()

def verify_user_access(auth_header):
    """Verificar se usuário tem acesso via JWT token"""
    try:
        if not auth_header or not auth_header.startswith('Bearer '):
            return False
        
        token = auth_header.replace('Bearer ', '')
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload['user_id']
        
        return user_id
        
    except Exception as e:
        logger.error(f"Erro na verificação do token: {e}")
        return False

@chart_ativos_bp.route('/portfolio/<portfolio_id>/analytics', methods=['GET'])
def get_portfolio_analytics(portfolio_id):
    """Endpoint principal para análise de carteiras com auto-atualização"""
    try:
        logger.info(f" Analytics solicitado para: {portfolio_id}")
        
        # Verificar autenticação
        auth_header = request.headers.get('Authorization')
        current_user_id = verify_user_access(auth_header)
        
        if not current_user_id:
            logger.error(" Usuário não autenticado")
            return jsonify({
                'success': False,
                'error': 'Usuário não autenticado'
            }), 401

        # Verificar se usuário tem acesso à carteira
        if not check_user_portfolio_access(current_user_id, portfolio_id):
            logger.error(f" Usuário {current_user_id} sem acesso à carteira {portfolio_id}")
            return jsonify({
                'success': False,
                'error': 'Acesso negado à esta carteira'
            }), 403

        # Verificar parâmetro de refresh forçado
        force_refresh = request.args.get('refresh', 'false').lower() == 'true'
        
        if force_refresh:
            logger.info(" Refresh forçado solicitado")

        # Executar análise com auto-atualização
        result = chart_service.analyze_portfolio(portfolio_id, force_refresh)
        
        if result['success']:
            logger.info(" Análise concluída com sucesso!")
            
            return jsonify({
                'success': True,
                'data': {
                    'portfolio_id': result['portfolio_id'],
                    'portfolio_name': result['portfolio_name'],
                    'analysis_date': result['analysis_date'],
                    'metrics': result['metrics'],
                    'assets_count': result['assets_count'],
                    'update_info': result['update_info']
                }
            })
        else:
            logger.error(f" Erro na análise: {result['error']}")
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500

    except Exception as e:
        logger.error(f" Erro interno: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'error': f'Erro interno do servidor: {str(e)}'
        }), 500

@chart_ativos_bp.route('/portfolio/<portfolio_id>/refresh', methods=['POST'])
def refresh_portfolio_prices(portfolio_id):
    """Endpoint específico para forçar atualização de preços"""
    try:
        logger.info(f" Refresh forçado para carteira: {portfolio_id}")
        
        # Verificar autenticação
        auth_header = request.headers.get('Authorization')
        current_user_id = verify_user_access(auth_header)
        
        if not current_user_id:
            return jsonify({
                'success': False,
                'error': 'Usuário não autenticado'
            }), 401

        # Verificar acesso
        if not check_user_portfolio_access(current_user_id, portfolio_id):
            return jsonify({
                'success': False,
                'error': 'Acesso negado à esta carteira'
            }), 403

        # Forçar atualização de preços
        update_result = chart_service.update_portfolio_prices(portfolio_id, force_update=True)
        
        if update_result['success']:
            return jsonify({
                'success': True,
                'message': update_result['message'],
                'updated_count': update_result.get('updated_count', 0),
                'prices': update_result.get('prices', {}),
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': update_result['error']
            }), 500

    except Exception as e:
        logger.error(f" Erro no refresh: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chart_ativos_bp.route('/user/portfolios', methods=['GET'])
def get_user_portfolios():
    """Lista carteiras disponíveis para o usuário"""
    try:
        # Verificar autenticação
        auth_header = request.headers.get('Authorization')
        current_user_id = verify_user_access(auth_header)
        
        if not current_user_id:
            return jsonify({
                'success': False,
                'error': 'Usuário não autenticado'
            }), 401

        # Buscar carteiras do usuário
        portfolios = get_user_available_portfolios(current_user_id)

        return jsonify({
            'success': True,
            'portfolios': portfolios,
            'total': len(portfolios),
            'user_id': current_user_id
        })

    except Exception as e:
        logger.error(f" Erro ao listar portfolios: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chart_ativos_bp.route('/health', methods=['GET'])
def health_check():
    """Health check do serviço"""
    try:
        # Testar conexão com banco
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM portfolios")
            portfolio_count = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            db_status = f"{portfolio_count} carteiras disponíveis"
        else:
            db_status = "Erro de conexão"
        
        # Testar API do Yahoo Finance
        test_price = chart_service.fetch_single_price('PETR4')
        api_status = "Operacional" if test_price else "Com problemas"
        
        return jsonify({
            'success': True,
            'service': 'Chart Ativos Service',
            'status': 'operational',
            'database': db_status,
            'yahoo_finance_api': api_status,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'service': 'Chart Ativos Service',
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

def check_user_portfolio_access(user_id: int, portfolio_name: str) -> bool:
    """Verifica se usuário tem acesso à carteira"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Verificar acesso na tabela user_portfolios
        cursor.execute("""
            SELECT 1 FROM user_portfolios 
            WHERE user_id = %s AND portfolio_name = %s AND is_active = true
        """, (user_id, portfolio_name))
        
        has_access = cursor.fetchone() is not None
        
        cursor.close()
        conn.close()
        
        return has_access
        
    except Exception as e:
        logger.error(f" Erro ao verificar acesso: {e}")
        return False

def get_user_available_portfolios(user_id: int) -> list:
    """Busca carteiras disponíveis para o usuário"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
            
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT up.portfolio_name, p.display_name, p.description,
                   (SELECT COUNT(*) FROM portfolio_assets pa 
                    WHERE pa.portfolio_name = up.portfolio_name AND pa.is_active = true) as asset_count
            FROM user_portfolios up
            JOIN portfolios p ON up.portfolio_name = p.name
            WHERE up.user_id = %s AND up.is_active = true
            ORDER BY p.display_name
        """, (user_id,))
        
        portfolios = []
        for row in cursor.fetchall():
            portfolios.append({
                'id': row[0],
                'name': row[1],
                'description': row[2] or '',
                'asset_count': row[3] or 0
            })
        
        cursor.close()
        conn.close()
        
        return portfolios
        
    except Exception as e:
        logger.error(f" Erro ao buscar portfolios: {e}")
        return []

# Função para registrar o blueprint
def get_chart_ativos_blueprint():
    """Retorna o blueprint para registrar no Flask"""
    return chart_ativos_bp
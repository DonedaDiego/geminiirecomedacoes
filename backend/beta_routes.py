from flask import Blueprint, jsonify, request
from monitor_service import MonitorService

# Criar Blueprint para rotas Beta
beta_bp = Blueprint('beta', __name__, url_prefix='/api/beta')

# Instância do serviço
monitor_service = MonitorService()

@beta_bp.route('/analyze/<string:symbol>', methods=['GET'])
def analyze_beta(symbol):
    """Análise completa de Beta para uma ação"""
    try:
        result = monitor_service.analyze_stock_beta(symbol.upper())
        
        if result['success']:
            return jsonify({
                'success': True,
                'data': result['data']
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@beta_bp.route('/ranking', methods=['GET'])
def beta_ranking():
    """Ranking de ações por Beta"""
    try:
        result = monitor_service.get_popular_stocks_beta()
        
        if result['success']:
            return jsonify({
                'success': True,
                'data': result['data'],
                'analysis_date': result['analysis_date']
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Erro ao calcular ranking'
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@beta_bp.route('/ibov-data', methods=['GET'])
def ibov_data():
    """Dados atuais do IBOVESPA"""
    try:
        period = request.args.get('period', '252', type=int)
        
        ibov_data = monitor_service.get_ibov_data(period)
        
        if ibov_data:
            return jsonify({
                'success': True,
                'data': ibov_data
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Erro ao buscar dados do IBOVESPA'
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@beta_bp.route('/compare', methods=['POST'])
def compare_betas():
    """Comparar Beta de múltiplas ações"""
    try:
        data = request.get_json()
        symbols = data.get('symbols', [])
        period = data.get('period', 'long')  # short, medium, long
        
        if not symbols:
            return jsonify({
                'success': False,
                'error': 'Lista de símbolos é obrigatória'
            }), 400
        
        results = []
        
        for symbol in symbols:
            analysis = monitor_service.analyze_stock_beta(symbol.upper())
            if analysis['success']:
                period_data = analysis['data']['periods'].get(period, {})
                if period_data:
                    results.append({
                        'symbol': symbol.upper(),
                        'beta': period_data['beta'],
                        'r_squared': period_data['r_squared'],
                        'correlation': period_data['correlation'],
                        'stock_return': period_data['stock_return'],
                        'market_return': period_data['market_return'],
                        'interpretation': period_data['interpretation'],
                        'current_price': analysis['data'].get('current_data', {}).get('current_price', 0)
                    })
        
        # Ordenar por Beta
        results.sort(key=lambda x: x['beta'], reverse=True)
        
        return jsonify({
            'success': True,
            'data': results,
            'period': period,
            'total_analyzed': len(results)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500
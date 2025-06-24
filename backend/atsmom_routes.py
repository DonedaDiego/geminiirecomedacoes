"""
Rotas para o serviço ATSMOM
"""

from flask import Blueprint, request, jsonify, render_template
from atsmom_service import ATSMOMService
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Criar blueprint
atsmom_bp = Blueprint('atsmom', __name__, url_prefix='/atsmom')

# Instanciar serviço
atsmom_service = ATSMOMService()

@atsmom_bp.route('/health', methods=['GET'])
def health_check():
    """Endpoint para verificar saúde do serviço"""
    try:
        return jsonify({
            'status': 'OK',
            'message': 'Serviço ATSMOM funcionando corretamente',
            'timestamp': atsmom_service.get_available_symbols()[:5]  # Teste básico
        })
    except Exception as e:
        logger.error(f"Erro no health check: {e}")
        return jsonify({
            'status': 'ERROR',
            'message': f'Erro no serviço: {str(e)}'
        }), 500

@atsmom_bp.route('/symbols', methods=['GET'])
def get_symbols():
    """Retorna lista de símbolos disponíveis"""
    try:
        symbols = atsmom_service.get_available_symbols()
        return jsonify({
            'success': True,
            'symbols': symbols,
            'total': len(symbols)
        })
    except Exception as e:
        logger.error(f"Erro ao obter símbolos: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@atsmom_bp.route('/analyze', methods=['POST'])
def analyze_asset():
    """
    Analisa um ativo usando ATSMOM
    
    Payload esperado:
    {
        "symbol": "PETR4",
        "period": "2y",
        "strike": 25.50  // opcional
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Dados não fornecidos'
            }), 400
        
        symbol = data.get('symbol', '').upper().strip()
        if not symbol:
            return jsonify({
                'success': False,
                'error': 'Símbolo é obrigatório'
            }), 400
        
        period = data.get('period', '2y')
        strike = data.get('strike')
        
        # Validar strike se fornecido
        if strike is not None:
            try:
                strike = float(strike)
                if strike <= 0:
                    return jsonify({
                        'success': False,
                        'error': 'Strike deve ser maior que zero'
                    }), 400
            except (ValueError, TypeError):
                return jsonify({
                    'success': False,
                    'error': 'Strike deve ser um número válido'
                }), 400
        
        # Validar período
        valid_periods = ['1y', '2y', '5y', 'max']
        if period not in valid_periods:
            return jsonify({
                'success': False,
                'error': f'Período deve ser um de: {", ".join(valid_periods)}'
            }), 400
        
        logger.info(f"Analisando {symbol} com período {period}")
        
        # Executar análise
        result = atsmom_service.analyze_single_asset(symbol, period, strike)
        
        if result['success']:
            logger.info(f"Análise de {symbol} concluída com sucesso")
        else:
            logger.warning(f"Erro na análise de {symbol}: {result.get('error')}")
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Erro no endpoint de análise: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@atsmom_bp.route('/bulk_analyze', methods=['POST'])
def bulk_analyze():
    """
    Analisa múltiplos ativos em lote
    
    Payload esperado:
    {
        "symbols": ["PETR4", "VALE3", "ITUB4"],
        "period": "2y"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Dados não fornecidos'
            }), 400
        
        symbols = data.get('symbols', [])
        if not symbols or not isinstance(symbols, list):
            # Se não fornecidos, usar símbolos padrão
            symbols = atsmom_service.get_available_symbols()[:10]  # Primeiros 10
        
        period = data.get('period', '2y')
        
        # Validar período
        valid_periods = ['1y', '2y', '5y', 'max']
        if period not in valid_periods:
            return jsonify({
                'success': False,
                'error': f'Período deve ser um de: {", ".join(valid_periods)}'
            }), 400
        
        logger.info(f"Análise em lote iniciada para {len(symbols)} símbolos")
        
        results = []
        errors = []
        
        for symbol in symbols:
            try:
                symbol = symbol.upper().strip()
                result = atsmom_service.analyze_single_asset(symbol, period)
                
                if result['success']:
                    # Adiciona apenas dados essenciais para a tabela
                    analysis = result['analysis_data']
                    results.append({
                        'symbol': analysis['symbol'],
                        'current_price': analysis['current_price'],
                        'signal_status': analysis['signal_status'],
                        'current_signal': analysis['current_signal'],
                        'current_trend': analysis['current_trend'],
                        'current_volatility': analysis['current_volatility'],
                        'beta': analysis['beta']
                    })
                else:
                    errors.append(f"{symbol}: {result['error']}")
                    
            except Exception as e:
                errors.append(f"{symbol}: {str(e)}")
                logger.error(f"Erro ao analisar {symbol}: {e}")
        
        logger.info(f"Análise em lote concluída: {len(results)} sucessos, {len(errors)} erros")
        
        return jsonify({
            'success': True,
            'results': results,
            'errors': errors,
            'total_analyzed': len(results),
            'total_errors': len(errors),
            'period': period
        })
        
    except Exception as e:
        logger.error(f"Erro no endpoint de análise em lote: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@atsmom_bp.route('/compare', methods=['POST'])
def compare_assets():
    """
    Compara dois ativos usando ATSMOM
    
    Payload esperado:
    {
        "symbol1": "PETR4",
        "symbol2": "VALE3",
        "period": "2y"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Dados não fornecidos'
            }), 400
        
        symbol1 = data.get('symbol1', '').upper().strip()
        symbol2 = data.get('symbol2', '').upper().strip()
        
        if not symbol1 or not symbol2:
            return jsonify({
                'success': False,
                'error': 'Ambos os símbolos são obrigatórios'
            }), 400
        
        if symbol1 == symbol2:
            return jsonify({
                'success': False,
                'error': 'Os símbolos devem ser diferentes'
            }), 400
        
        period = data.get('period', '2y')
        
        logger.info(f"Comparando {symbol1} vs {symbol2}")
        
        # Analisar ambos os ativos
        result1 = atsmom_service.analyze_single_asset(symbol1, period)
        result2 = atsmom_service.analyze_single_asset(symbol2, period)
        
        if not result1['success']:
            return jsonify({
                'success': False,
                'error': f'Erro ao analisar {symbol1}: {result1["error"]}'
            })
        
        if not result2['success']:
            return jsonify({
                'success': False,
                'error': f'Erro ao analisar {symbol2}: {result2["error"]}'
            })
        
        # Compilar comparação
        comparison = {
            'symbol1': {
                'symbol': symbol1,
                'data': result1['analysis_data']
            },
            'symbol2': {
                'symbol': symbol2,
                'data': result2['analysis_data']
            },
            'comparison_summary': {
                'stronger_signal': symbol1 if abs(result1['analysis_data']['current_signal']) > abs(result2['analysis_data']['current_signal']) else symbol2,
                'higher_volatility': symbol1 if result1['analysis_data']['current_volatility'] > result2['analysis_data']['current_volatility'] else symbol2,
                'higher_beta': symbol1 if result1['analysis_data']['beta'] > result2['analysis_data']['beta'] else symbol2
            }
        }
        
        logger.info(f"Comparação {symbol1} vs {symbol2} concluída")
        
        return jsonify({
            'success': True,
            'comparison': comparison,
            'period': period
        })
        
    except Exception as e:
        logger.error(f"Erro no endpoint de comparação: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@atsmom_bp.route('/market_overview', methods=['GET'])
def market_overview():
    """
    Visão geral do mercado com principais ativos
    """
    try:
        period = request.args.get('period', '2y')
        
        # Analisar principais ativos
        main_symbols = ['PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3']
        
        results = []
        for symbol in main_symbols:
            try:
                result = atsmom_service.analyze_single_asset(symbol, period)
                if result['success']:
                    results.append({
                        'symbol': symbol,
                        'price': result['analysis_data']['current_price'],
                        'signal': result['analysis_data']['signal_status'],
                        'signal_strength': result['analysis_data']['current_signal'],
                        'volatility': result['analysis_data']['current_volatility'],
                        'beta': result['analysis_data']['beta']
                    })
            except Exception as e:
                logger.error(f"Erro ao analisar {symbol} no overview: {e}")
                continue
        
        # Calcular estatísticas gerais
        if results:
            total_buy = sum(1 for r in results if r['signal'] == 'COMPRA')
            total_sell = sum(1 for r in results if r['signal'] == 'VENDA')
            total_neutral = sum(1 for r in results if r['signal'] == 'NEUTRO')
            avg_volatility = sum(r['volatility'] for r in results) / len(results)
            
            overview = {
                'total_assets': len(results),
                'buy_signals': total_buy,
                'sell_signals': total_sell,
                'neutral_signals': total_neutral,
                'average_volatility': round(avg_volatility, 2),
                'market_sentiment': 'POSITIVO' if total_buy > total_sell else 'NEGATIVO' if total_sell > total_buy else 'NEUTRO'
            }
        else:
            overview = {
                'total_assets': 0,
                'buy_signals': 0,
                'sell_signals': 0,
                'neutral_signals': 0,
                'average_volatility': 0,
                'market_sentiment': 'INDISPONÍVEL'
            }
        
        return jsonify({
            'success': True,
            'overview': overview,
            'assets': results,
            'period': period
        })
        
    except Exception as e:
        logger.error(f"Erro no market overview: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

# Função para registrar o blueprint
def register_atsmom_routes(app):
    """Registra as rotas ATSMOM na aplicação Flask"""
    app.register_blueprint(atsmom_bp)
    logger.info("Rotas ATSMOM registradas com sucesso")
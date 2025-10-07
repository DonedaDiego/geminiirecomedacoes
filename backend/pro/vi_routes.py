from flask import Blueprint, request, jsonify
from datetime import datetime
import traceback

# Importar o serviço
from pro.vi_service import VolatilityImpliedService

# Blueprint
vi_bp = Blueprint('vi', __name__, url_prefix='/api/vi')

# Instância global do serviço
vi_service = VolatilityImpliedService()

@vi_bp.route('/health', methods=['GET'])
def health_check():
    """Health check da API de VI"""
    return jsonify({
        'status': 'OK',
        'message': 'Volatilidade Implícita funcionando',
        'timestamp': datetime.now().isoformat(),
        'service': 'VolatilityImpliedService',
        'token_configurado': bool(vi_service.token)
    })

@vi_bp.route('/analyze/<ticker>', methods=['GET'])
def analyze_ticker(ticker):
    """Análise completa de volatilidade implícita para um ticker"""
    try:
        # Parâmetros
        period_days = int(request.args.get('period_days', 252))
        
        # Limpar ticker
        clean_ticker = ticker.upper().replace('.SA', '')
        
        print(f" Análise VI solicitada: {clean_ticker}, período: {period_days} dias")
        
        # Executar análise usando o serviço
        result = vi_service.create_analysis(clean_ticker, period_days)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': f'Parâmetro inválido: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 400
    except Exception as e:
        print(f" Erro na análise VI: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@vi_bp.route('/signal/<ticker>', methods=['GET'])
def get_signal(ticker):
    """Obter apenas o sinal atual de uma ação"""
    try:
        # Parâmetros
        period_days = int(request.args.get('period_days', 126))
        
        # Limpar ticker
        clean_ticker = ticker.upper().replace('.SA', '')
        
        print(f" Sinal VI solicitado: {clean_ticker}")
        
        # Executar análise usando o serviço
        result = vi_service.create_analysis(clean_ticker, period_days)
        
        if result['success']:
            # Retornar apenas dados essenciais do sinal
            signal_data = {
                'success': True,
                'ticker': result['ticker'],
                'current_price': result['current_price'],
                'current_signal': result['current_signal'],
                'signal_interpretation': result['signal_interpretation'],
                'vol_hist_mean': result['vol_hist_mean'],
                'iv_mean': result['iv_mean'],
                'timestamp': result['timestamp']
            }
            return jsonify(signal_data)
        else:
            return jsonify(result), 400
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': f'Parâmetro inválido: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 400
    except Exception as e:
        print(f" Erro ao obter sinal VI: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# Screener removido - muito lento para produção

@vi_bp.route('/chart-data/<ticker>', methods=['GET'])
def get_chart_data(ticker):
    """Obter dados específicos para gráficos"""
    try:
        # Parâmetros
        period_days = int(request.args.get('period_days', 252))
        
        # Limpar ticker
        clean_ticker = ticker.upper().replace('.SA', '')
        
        print(f" Dados de gráfico solicitados: {clean_ticker}")
        
        # Executar análise usando o serviço
        result = vi_service.create_analysis(clean_ticker, period_days)
        
        if result['success']:
            # Retornar apenas dados do gráfico
            chart_response = {
                'success': True,
                'ticker': result['ticker'],
                'chart_data': result['chart_data'],
                'current_price': result['current_price'],
                'current_signal': result['current_signal'],
                'timestamp': result['timestamp']
            }
            return jsonify(chart_response)
        else:
            return jsonify(result), 400
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': f'Parâmetro inválido: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 400
    except Exception as e:
        print(f" Erro ao obter dados do gráfico: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@vi_bp.route('/compare', methods=['POST'])
def compare_tickers():
    """Comparar múltiplos tickers de uma vez"""
    try:
        data = request.get_json()
        
        if not data or 'tickers' not in data:
            return jsonify({
                'success': False,
                'error': 'Lista de tickers é obrigatória'
            }), 400
        
        tickers = data['tickers']
        period_days = data.get('period_days', 126)
        
        if not isinstance(tickers, list) or len(tickers) == 0:
            return jsonify({
                'success': False,
                'error': 'Forneça uma lista válida de tickers'
            }), 400
        
        if len(tickers) > 10:
            return jsonify({
                'success': False,
                'error': 'Máximo de 10 tickers por comparação'
            }), 400
        
        print(f"🔀 Comparação solicitada: {tickers}, período: {period_days} dias")
        
        comparison_results = []
        
        for ticker in tickers:
            try:
                clean_ticker = ticker.upper().replace('.SA', '')
                print(f" Analisando {clean_ticker} para comparação...")
                
                result = vi_service.create_analysis(clean_ticker, period_days)
                
                if result['success']:
                    comparison_results.append({
                        'ticker': clean_ticker,
                        'current_price': result['current_price'],
                        'current_signal': result['current_signal'],
                        'signal_interpretation': result['signal_interpretation'],
                        'vol_hist_mean': result['vol_hist_mean'],
                        'iv_mean': result['iv_mean']
                    })
                    print(f" {clean_ticker}: Sucesso")
                else:
                    comparison_results.append({
                        'ticker': clean_ticker,
                        'error': result['error']
                    })
                    print(f" {clean_ticker}: {result['error']}")
                
            except Exception as e:
                comparison_results.append({
                    'ticker': ticker,
                    'error': str(e)
                })
                print(f" Erro em {ticker}: {e}")
        
        return jsonify({
            'success': True,
            'total_requested': len(tickers),
            'period_days': period_days,
            'comparison_results': comparison_results,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f" Erro na comparação: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@vi_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """Estatísticas gerais do sistema de VI"""
    try:
        print(" Estatísticas gerais solicitadas")
        
        # Lista de principais ações para estatísticas
        sample_tickers = ['PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3']
        period_days = int(request.args.get('period_days', 126))
        
        stats = {
            'high_signal_count': 0,
            'medium_signal_count': 0,
            'low_signal_count': 0,
            'total_analyzed': 0,
            'avg_signal': 0,
            'best_opportunities': [],
            'worst_opportunities': []
        }
        
        all_signals = []
        
        for ticker in sample_tickers:
            try:
                result = vi_service.create_analysis(ticker, period_days)
                
                if result['success']:
                    signal = result['current_signal']
                    all_signals.append({
                        'ticker': ticker,
                        'signal': signal,
                        'status': result['signal_interpretation']['status']
                    })
                    
                    # Contadores
                    if signal >= 30:
                        stats['high_signal_count'] += 1
                    elif signal >= -10:
                        stats['medium_signal_count'] += 1
                    else:
                        stats['low_signal_count'] += 1
                    
                    stats['total_analyzed'] += 1
                
            except Exception as e:
                print(f" Erro em estatística para {ticker}: {e}")
                continue
        
        if all_signals:
            # Calcular estatísticas
            signals_values = [s['signal'] for s in all_signals]
            stats['avg_signal'] = sum(signals_values) / len(signals_values)
            
            # Melhores e piores oportunidades
            sorted_signals = sorted(all_signals, key=lambda x: x['signal'], reverse=True)
            stats['best_opportunities'] = sorted_signals[:3]
            stats['worst_opportunities'] = sorted_signals[-3:]
        
        return jsonify({
            'success': True,
            'period_days': period_days,
            'statistics': stats,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f" Erro nas estatísticas: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# Error handlers
@vi_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint não encontrado',
        'timestamp': datetime.now().isoformat()
    }), 404

@vi_bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Erro interno do servidor',
        'timestamp': datetime.now().isoformat()
    }), 500

# Função para retornar blueprint
def get_vi_blueprint():
    """Retorna blueprint para registrar no Flask"""
    return vi_bp
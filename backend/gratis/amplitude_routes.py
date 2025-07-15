from flask import Blueprint, request, jsonify
from gratis.amplitude_service import AmplitudeService
import json

# Criar blueprint
amplitude_bp = Blueprint('amplitude', __name__, url_prefix='/api/amplitude')

@amplitude_bp.route('/analyze/<ticker>', methods=['GET'])
def analyze_stock_amplitude(ticker):
    """Analisar amplitude de variação de um ativo específico"""
    try:
        # Validar ticker
        if not ticker or len(ticker) < 4:
            return jsonify({
                'success': False,
                'error': 'Ticker inválido. Exemplo: PETR4, VALE3'
            }), 400
        
        # Fazer análise
        analysis = AmplitudeService.analyze_amplitude_patterns(ticker.upper())
        
        if not analysis:
            return jsonify({
                'success': False,
                'error': f'Não foi possível analisar o ativo {ticker.upper()}. Verifique se o ticker está correto.'
            }), 404
        
        return jsonify({
            'success': True,
            'data': analysis
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@amplitude_bp.route('/compare', methods=['POST'])
def compare_multiple_stocks():
    """Comparar amplitude de múltiplos ativos"""
    try:
        data = request.get_json()
        
        if not data or 'tickers' not in data:
            return jsonify({
                'success': False,
                'error': 'Lista de tickers é obrigatória'
            }), 400
        
        tickers = data.get('tickers', [])
        
        if not tickers or len(tickers) == 0:
            return jsonify({
                'success': False,
                'error': 'Pelo menos um ticker deve ser informado'
            }), 400
        
        if len(tickers) > 10:
            return jsonify({
                'success': False,
                'error': 'Máximo de 10 ativos por comparação'
            }), 400
        
        # Limpar e validar tickers
        clean_tickers = []
        for ticker in tickers:
            if isinstance(ticker, str) and len(ticker.strip()) >= 4:
                clean_tickers.append(ticker.strip().upper())
        
        if not clean_tickers:
            return jsonify({
                'success': False,
                'error': 'Nenhum ticker válido encontrado'
            }), 400
        
        print(f"🔄 Iniciando comparação de: {clean_tickers}")  # Debug
        
        # Fazer análise comparativa
        comparison = AmplitudeService.get_multiple_stocks_analysis(clean_tickers)
        
        # ✅ VERIFICAR SE HOUVE RESULTADOS
        if not comparison or len(comparison) == 0:
            return jsonify({
                'success': False,
                'error': 'Nenhum ativo pôde ser analisado. Verifique se os códigos estão corretos.'
            }), 404
        
        # ✅ PEGAR ANALYSIS_DATE DO PRIMEIRO RESULTADO
        analysis_date = comparison[0].get('analysis_date') if comparison else None
        
        return jsonify({
            'success': True,
            'data': {
                'comparison': comparison,
                'total_analyzed': len(comparison),
                'requested_tickers': clean_tickers,
                'analysis_date': analysis_date  # ✅ GARANTIR QUE EXISTE
            }
        })
        
    except Exception as e:
        print(f"❌ Erro na comparação: {str(e)}")  # Debug detalhado
        import traceback
        traceback.print_exc()  # Print do stack trace completo
        
        return jsonify({
            'success': False,
            'error': f'Erro interno do servidor: {str(e)}'
        }), 500

@amplitude_bp.route('/quick/<ticker>', methods=['GET'])
def quick_amplitude_info(ticker):
    """Informação rápida de amplitude (apenas estatísticas principais)"""
    try:
        if not ticker or len(ticker) < 4:
            return jsonify({
                'success': False,
                'error': 'Ticker inválido'
            }), 400
        
        # Fazer análise completa
        analysis = AmplitudeService.analyze_amplitude_patterns(ticker.upper())
        
        if not analysis:
            return jsonify({
                'success': False,
                'error': f'Ativo {ticker.upper()} não encontrado'
            }), 404
        
        # Extrair apenas informações principais
        quick_info = {
            'ticker': analysis['ticker'],
            'company_name': analysis['company_name'],
            'current_price': analysis['current_price'],
            'volatility_level': analysis['summary']['volatility_level'],
            'volatility_description': analysis['summary']['volatility_description'],
            'avg_daily_amplitude': analysis['summary']['avg_daily_amplitude'],
            'trend': analysis['summary']['trend'],
            'recommendations': analysis['summary']['recommendation']
        }
        
        return jsonify({
            'success': True,
            'data': quick_info
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@amplitude_bp.route('/detailed/<ticker>', methods=['GET'])
def detailed_amplitude_analysis(ticker):
    """Análise detalhada com todos os períodos e distribuições"""
    try:
        if not ticker or len(ticker) < 4:
            return jsonify({
                'success': False,
                'error': 'Ticker inválido'
            }), 400
        
        # Fazer análise completa
        analysis = AmplitudeService.analyze_amplitude_patterns(ticker.upper())
        
        if not analysis:
            return jsonify({
                'success': False,
                'error': f'Ativo {ticker.upper()} não encontrado'
            }), 404
        
        # Formatar para apresentação mais didática
        formatted_analysis = {
            'basic_info': {
                'ticker': analysis['ticker'],
                'company_name': analysis['company_name'],
                'sector': analysis['sector'],
                'current_price': analysis['current_price'],
                'analysis_date': analysis['analysis_date']
            },
            'daily_patterns': {
                'summary': analysis['daily_analysis']['statistics'],
                'amplitude_distribution': analysis['daily_analysis']['amplitude_distribution'],
                'variation_distribution': analysis['daily_analysis']['variation_distribution']
            },
            'period_patterns': analysis['periods_analysis'],
            'executive_summary': analysis['summary']
        }
        
        return jsonify({
            'success': True,
            'data': formatted_analysis
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@amplitude_bp.route('/popular-stocks', methods=['GET'])
def get_popular_stocks_amplitude():
    """Análise de amplitude dos ativos mais populares"""
    try:
        # Lista de ativos populares
        popular_tickers = [
            'PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3', 
            'WEGE3', 'MGLU3', 'B3SA3', 'RENT3', 'LREN3'
        ]
        
        # Fazer análise comparativa
        comparison = AmplitudeService.get_multiple_stocks_analysis(popular_tickers)
        
        # Agrupar por nível de volatilidade
        grouped = {
            'BAIXA': [],
            'MÉDIA': [],
            'ALTA': [],
            'MUITO ALTA': []
        }
        
        for stock in comparison:
            volatility = stock['volatility_level']
            if volatility in grouped:
                grouped[volatility].append(stock)
        
        return jsonify({
            'success': True,
            'data': {
                'grouped_by_volatility': grouped,
                'full_comparison': comparison,
                'total_analyzed': len(comparison),
                'analysis_info': 'Análise baseada nos últimos 252 dias úteis'
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@amplitude_bp.route('/period-analysis/<ticker>/<int:period_days>', methods=['GET'])
def get_specific_period_analysis(ticker, period_days):
    """Análise específica para um período (2, 3, 4, 5, 12, 30 dias)"""
    try:
        # Validar período
        valid_periods = [2, 3, 4, 5, 12, 30]
        if period_days not in valid_periods:
            return jsonify({
                'success': False,
                'error': f'Período inválido. Períodos válidos: {valid_periods}'
            }), 400
        
        if not ticker or len(ticker) < 4:
            return jsonify({
                'success': False,
                'error': 'Ticker inválido'
            }), 400
        
        # Fazer análise completa
        analysis = AmplitudeService.analyze_amplitude_patterns(ticker.upper())
        
        if not analysis:
            return jsonify({
                'success': False,
                'error': f'Ativo {ticker.upper()} não encontrado'
            }), 404
        
        # Extrair análise do período específico
        period_key = f'{period_days}_days'
        period_analysis = analysis['periods_analysis'].get(period_key)
        
        if not period_analysis:
            return jsonify({
                'success': False,
                'error': f'Análise para período de {period_days} dias não disponível'
            }), 404
        
        return jsonify({
            'success': True,
            'data': {
                'ticker': analysis['ticker'],
                'company_name': analysis['company_name'],
                'period_days': period_days,
                'analysis': period_analysis,
                'interpretation': {
                    'success_rate': f"{period_analysis['statistics']['success_rate']}% dos períodos foram positivos",
                    'avg_variation': f"Variação média de {period_analysis['statistics']['avg_variation']}% em {period_days} dias",
                    'volatility': f"Volatilidade de {period_analysis['statistics']['volatility']}%",
                    'recommendation': _get_period_recommendation(period_analysis['statistics'])
                }
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

def _get_period_recommendation(stats):
    """Gerar recomendação baseada nas estatísticas do período"""
    success_rate = stats['success_rate']
    avg_variation = stats['avg_variation']
    
    if success_rate >= 60 and avg_variation > 1:
        return "Período favorável para operações de compra"
    elif success_rate <= 40 and avg_variation < -1:
        return "Período com tendência de baixa"
    elif success_rate >= 55:
        return "Período com leve viés de alta"
    elif success_rate <= 45:
        return "Período com leve viés de baixa"
    else:
        return "Período neutro, sem tendência clara"

@amplitude_bp.route('/health', methods=['GET'])
def health_check():
    """Health check da API de amplitude"""
    return jsonify({
        'success': True,
        'service': 'Amplitude Analysis API',
        'status': 'healthy',
        'endpoints': [
            'GET /api/amplitude/analyze/<ticker>',
            'POST /api/amplitude/compare',
            'GET /api/amplitude/quick/<ticker>',
            'GET /api/amplitude/detailed/<ticker>',
            'GET /api/amplitude/popular-stocks',
            'GET /api/amplitude/period-analysis/<ticker>/<period_days>'
        ]
    })

# Middleware para tratar erros
@amplitude_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint não encontrado'
    }), 404

@amplitude_bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Erro interno do servidor'
    }), 500
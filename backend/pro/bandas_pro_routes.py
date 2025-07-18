# bandas_pro_routes.py - Hybrid Volatility Bands Pro Routes
from flask import Blueprint, request, jsonify
import numpy as np
import pandas as pd
from datetime import datetime
import logging
from pro.bandas_pro_service import BandasProService

# Criar blueprint
bandas_pro_bp = Blueprint('bandas_pro', __name__, url_prefix='/api/bandas-pro')

# Inicializar serviço
bandas_service = BandasProService()

# Logger
logger = logging.getLogger(__name__)

def ensure_json_safe(data):
    """
    Função adicional para garantir que TODOS os dados sejam JSON-safe
    """
    if isinstance(data, dict):
        return {key: ensure_json_safe(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [ensure_json_safe(item) for item in data]
    elif isinstance(data, (np.integer, np.int8, np.int16, np.int32, np.int64)):
        return int(data)
    elif isinstance(data, (np.floating, np.float16, np.float32, np.float64)):
        if np.isnan(data) or np.isinf(data):
            return 0.0
        return float(data)
    elif isinstance(data, np.bool_):
        return bool(data)
    elif isinstance(data, pd.Timestamp):
        return data.strftime('%Y-%m-%d %H:%M:%S')
    elif pd.isna(data):
        return None
    else:
        return data

@bandas_pro_bp.route('/health', methods=['GET'])
def health_check():
    """Check de saúde da API Pro"""
    return jsonify({
        'status': 'OK',
        'service': 'Hybrid Volatility Bands Pro API',
        'timestamp': datetime.now().isoformat(),
        'version': '3.0.0',
        'features': ['GARCH', 'XGBoost', 'IV_Validation', 'OpLab_Integration']
    })

@bandas_pro_bp.route('/analyze/<ticker>', methods=['GET'])
def analyze_ticker_pro(ticker):
    """
    Analisar um ticker específico com Bandas de Volatilidade Híbridas Pro + IV Validation
    
    Parâmetros:
    - ticker: Código da ação (ex: PETR4 ou PETR4.SA)
    - period: Período de análise (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
    """
    try:
        # Parâmetros da query
        period = request.args.get('period', '6mo')
        
        logger.info(f"Analisando {ticker} Pro - período: {period}")
        
        # Validar ticker
        if not ticker or len(ticker.strip()) == 0:
            return jsonify({
                'error': 'Ticker é obrigatório',
                'success': False
            }), 400
        
        # Limpar ticker
        ticker = ticker.strip().upper()
        
        # Validar período
        valid_periods = ['1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max']
        if period not in valid_periods:
            return jsonify({
                'error': f'Período inválido. Use: {", ".join(valid_periods)}',
                'success': False
            }), 400
        
        # Executar análise Pro
        analysis = bandas_service.get_analysis_summary(ticker, period)
        
        if not analysis.get('success', False):
            logger.error(f"Análise Pro falhou para {ticker}: {analysis.get('error', 'Erro desconhecido')}")
            return jsonify(analysis), 400
        
        # CORREÇÃO CRÍTICA: Garantir que TODOS os dados sejam JSON-safe
        safe_analysis = ensure_json_safe(analysis)
        
        logger.info(f"Análise Pro bem-sucedida para {ticker}")
        return jsonify(safe_analysis)
        
    except ValueError as e:
        logger.error(f"Erro de validação para {ticker}: {e}")
        return jsonify({
            'error': f'Parâmetros inválidos: {str(e)}',
            'success': False
        }), 400
    except Exception as e:
        logger.error(f"Erro interno na análise Pro de {ticker}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': 'Erro interno do servidor',
            'success': False
        }), 500

@bandas_pro_bp.route('/compare', methods=['POST'])
def compare_tickers_pro():
    """
    Comparar múltiplos tickers com análise Pro
    
    Body JSON:
    {
        "tickers": ["PETR4", "VALE3", "ITUB4"],
        "period": "6mo"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'tickers' not in data:
            return jsonify({
                'error': 'Lista de tickers é obrigatória',
                'success': False
            }), 400
        
        tickers = data['tickers']
        period = data.get('period', '6mo')
        
        if not isinstance(tickers, list) or len(tickers) == 0:
            return jsonify({
                'error': 'Tickers deve ser uma lista não vazia',
                'success': False
            }), 400
        
        if len(tickers) > 10:
            return jsonify({
                'error': 'Máximo 10 tickers por request',
                'success': False
            }), 400
        
        # Analisar cada ticker
        results = {}
        for ticker in tickers:
            logger.info(f"Analisando {ticker} para comparação Pro")
            analysis = bandas_service.get_analysis_summary(ticker, period)
            
            if analysis.get('success', False):
                # Resumir para comparação e garantir JSON-safe
                results[ticker] = ensure_json_safe({
                    'current_price': analysis['current_price'],
                    'volatility': analysis['metrics']['volatility'],
                    'bands': analysis['metrics']['bands'],
                    'position': analysis['metrics']['position'],
                    'iv_validation': {
                        'score': analysis['iv_validation']['score'],
                        'status': analysis['iv_validation']['status'],
                        'recommendation': analysis['iv_validation']['recommendation']
                    },
                    'trading_signal': {
                        'signal': analysis['trading_signal']['signal'],
                        'confidence': analysis['trading_signal']['confidence'],
                        'iv_adjusted_confidence': analysis['trading_signal']['iv_adjusted_confidence'],
                        'strategy': analysis['trading_signal']['strategy']
                    }
                })
            else:
                results[ticker] = {
                    'error': analysis.get('error', 'Erro desconhecido')
                }
        
        return jsonify(ensure_json_safe({
            'comparison': results,
            'period': period,
            'timestamp': datetime.now().isoformat(),
            'success': True
        }))
        
    except Exception as e:
        logger.error(f"Erro na comparação Pro: {e}")
        return jsonify({
            'error': 'Erro interno do servidor',
            'success': False
        }), 500

@bandas_pro_bp.route('/signals/<ticker>', methods=['GET'])
def get_signals_pro(ticker):
    """
    Retornar apenas sinais de trading Pro com validação IV (endpoint mais rápido)
    """
    try:
        period = request.args.get('period', '3mo')
        
        logger.info(f"Buscando sinais Pro para {ticker}")
        
        # Análise simplificada
        analysis = bandas_service.get_analysis_summary(ticker, period)
        
        if not analysis.get('success', False):
            return jsonify(analysis), 400
        
        # Retornar apenas sinais e métricas essenciais
        signals_only = ensure_json_safe({
            'ticker': analysis['ticker'],
            'current_price': analysis['current_price'],
            'last_update': analysis['last_update'],
            'trading_signal': analysis['trading_signal'],
            'iv_validation': {
                'score': analysis['iv_validation']['score'],
                'status': analysis['iv_validation']['status'],
                'recommendation': analysis['iv_validation']['recommendation']
            },
            'quick_metrics': {
                'volatility_regime': analysis['metrics']['volatility']['regime'],
                'position': analysis['metrics']['position']['description'],
                'trend_regime': analysis['metrics']['position']['trend_regime']
            },
            'bands': {
                'superior_2sigma': analysis['metrics']['bands']['superior_2sigma'],
                'inferior_2sigma': analysis['metrics']['bands']['inferior_2sigma'],
                'linha_central': analysis['metrics']['bands']['linha_central']
            },
            'success': True
        })
        
        return jsonify(signals_only)
        
    except Exception as e:
        logger.error(f"Erro ao buscar sinais Pro para {ticker}: {e}")
        return jsonify({
            'error': 'Erro interno do servidor',
            'success': False
        }), 500

@bandas_pro_bp.route('/screener', methods=['GET'])
def volatility_screener_pro():
    """
    Screener de volatilidade Pro para múltiplos ativos brasileiros com validação IV
    
    Query params:
        - signal_type: Filtrar por tipo de sinal (BUY_VOLATILITY, SELL_VOLATILITY, PUT_BIAS, CALL_BIAS)
        - min_confidence: Confiança mínima (0-100)
        - min_iv_score: Score IV mínimo (0-100)
        - iv_status: Filtrar por status IV (CONFIÁVEL, NEUTRO, SUSPEITO)
    """
    try:
        # Ativos brasileiros mais líquidos
        default_tickers = [
            'PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3',
            'SUZB3', 'WEGE3', 'RENT3', 'LREN3', 'MGLU3',
            'B3SA3', 'HAPV3', 'RADL3', 'ELET3', 'JBSS3'
        ]
        
        signal_filter = request.args.get('signal_type')
        min_confidence = float(request.args.get('min_confidence', 0))
        min_iv_score = float(request.args.get('min_iv_score', 0))
        iv_status_filter = request.args.get('iv_status')
        period = request.args.get('period', '3mo')
        
        logger.info(f"Executando screener Pro - filtros: signal={signal_filter}, confidence={min_confidence}, iv_score={min_iv_score}")
        
        screener_results = []
        
        for ticker in default_tickers:
            try:
                analysis = bandas_service.get_analysis_summary(ticker, period)
                
                if analysis.get('success', False):
                    signal_data = analysis['trading_signal']
                    iv_data = analysis['iv_validation']
                    
                    # Aplicar filtros
                    if signal_filter and signal_data['signal'] != signal_filter:
                        continue
                    
                    if signal_data['confidence'] < min_confidence:
                        continue
                    
                    if iv_data['score'] < min_iv_score:
                        continue
                    
                    if iv_status_filter and iv_data['status'] != iv_status_filter:
                        continue
                    
                    screener_results.append(ensure_json_safe({
                        'ticker': analysis['ticker'],
                        'current_price': analysis['current_price'],
                        'signal': signal_data['signal'],
                        'confidence': signal_data['confidence'],
                        'iv_adjusted_confidence': signal_data['iv_adjusted_confidence'],
                        'strategy': signal_data['strategy'],
                        'iv_validation': {
                            'score': iv_data['score'],
                            'status': iv_data['status'],
                            'recommendation': iv_data['recommendation']
                        },
                        'volatility_regime': analysis['metrics']['volatility']['regime'],
                        'position': analysis['metrics']['position']['description'],
                        'trend_regime': analysis['metrics']['position']['trend_regime']
                    }))
                    
            except Exception as e:
                logger.warning(f"Erro ao analisar {ticker} no screener Pro: {e}")
                continue
        
        # Ordenar por confiança ajustada por IV
        screener_results.sort(key=lambda x: x['iv_adjusted_confidence'], reverse=True)
        
        return jsonify(ensure_json_safe({
            'screener_results': screener_results,
            'filters_applied': {
                'signal_type': signal_filter,
                'min_confidence': min_confidence,
                'min_iv_score': min_iv_score,
                'iv_status': iv_status_filter,
                'period': period
            },
            'total_found': len(screener_results),
            'timestamp': datetime.now().isoformat(),
            'success': True
        }))
        
    except Exception as e:
        logger.error(f"Erro no screener Pro: {e}")
        return jsonify({
            'error': 'Erro interno do servidor',
            'success': False
        }), 500

@bandas_pro_bp.route('/iv-analysis/<ticker>', methods=['GET'])
def get_iv_analysis(ticker):
    """
    Análise detalhada de volatilidade implícita para um ticker específico
    """
    try:
        logger.info(f"Buscando análise IV detalhada para {ticker}")
        
        # Buscar apenas análise IV
        from backend.pro.bandas_pro_service import VolatilityValidatorPro
        iv_validator = VolatilityValidatorPro()
        
        # Dados IV
        iv_data = iv_validator.get_iv_data(ticker)
        
        if not iv_data:
            return jsonify({
                'error': 'Dados IV não disponíveis para este ticker',
                'success': False
            }), 400
        
        # Análise de confiança
        confidence_analysis = iv_validator.calculate_confidence_score(iv_data)
        
        # Dados detalhados
        iv_analysis = ensure_json_safe({
            'ticker': ticker.replace('.SA', '').upper(),
            'iv_data': {
                'iv_current': iv_data.get('iv_current'),
                'iv_1y_percentile': iv_data.get('iv_1y_percentile'),
                'ewma_current': iv_data.get('ewma_current'),
                'stdv_5d': iv_data.get('stdv_5d'),
                'stdv_20d': iv_data.get('stdv_20d'),
                'hv_iv_ratio': iv_data.get('hv_iv_ratio')
            },
            'confidence_analysis': confidence_analysis,
            'recommendations': {
                'general': confidence_analysis['recommendation'],
                'strategy_bias': 'Favor volatility strategies' if confidence_analysis['score'] > 60 else 'Caution with volatility plays',
                'timing': 'Good entry point' if confidence_analysis['score'] > 70 else 'Wait for better setup'
            },
            'timestamp': datetime.now().isoformat(),
            'success': True
        })
        
        return jsonify(iv_analysis)
        
    except Exception as e:
        logger.error(f"Erro na análise IV para {ticker}: {e}")
        return jsonify({
            'error': 'Erro interno do servidor',
            'success': False
        }), 500

@bandas_pro_bp.route('/bands-stats/<ticker>', methods=['GET'])
def get_bands_statistics_pro(ticker):
    """
    Estatísticas detalhadas das bandas de volatilidade Pro
    """
    try:
        period = request.args.get('period', '1y')
        
        logger.info(f"Buscando estatísticas de bandas Pro para {ticker}")
        
        # Buscar dados históricos mais longos para estatísticas
        search_ticker = ticker if ticker.endswith('.SA') or ticker.startswith('^') else ticker + '.SA'
        data = bandas_service.get_stock_data(search_ticker, period)
        if data is None:
            return jsonify({
                'error': 'Dados não encontrados',
                'success': False
            }), 400
        
        # Calcular todos os indicadores
        data = bandas_service.calculate_base_volatility(data)
        data = bandas_service.engineer_features(data)
        data = bandas_service.train_xgboost(data)
        data = bandas_service.create_hybrid_model(data)
        data = bandas_service.create_bands(data)
        
        # Estatísticas das bandas
        current_price = data['Close'].iloc[-1]
        
        # Toques nas bandas
        touches_superior_2sigma = len(data[data['Close'] > data['banda_superior_2sigma']])
        touches_inferior_2sigma = len(data[data['Close'] < data['banda_inferior_2sigma']])
        touches_superior_4sigma = len(data[data['Close'] > data['banda_superior_4sigma']])
        touches_inferior_4sigma = len(data[data['Close'] < data['banda_inferior_4sigma']])
        
        # Eficiência das bandas
        total_points = len(data)
        efficiency_2sigma = ((total_points - touches_superior_2sigma - touches_inferior_2sigma) / total_points) * 100
        efficiency_4sigma = ((total_points - touches_superior_4sigma - touches_inferior_4sigma) / total_points) * 100
        
        # Análise IV atual
        from backend.pro.bandas_pro_service import VolatilityValidatorPro
        iv_validator = VolatilityValidatorPro()
        current_iv_analysis = iv_validator.calculate_confidence_score(iv_validator.get_iv_data(ticker))
        
        bands_stats = ensure_json_safe({
            'ticker': ticker,
            'period': period,
            'data_points': total_points,
            'current_analysis': {
                'current_price': current_price,
                'superior_2sigma': data['banda_superior_2sigma'].iloc[-1],
                'inferior_2sigma': data['banda_inferior_2sigma'].iloc[-1],
                'superior_4sigma': data['banda_superior_4sigma'].iloc[-1],
                'inferior_4sigma': data['banda_inferior_4sigma'].iloc[-1],
                'linha_central': data['linha_central'].iloc[-1],
                'hybrid_volatility': data['hybrid_vol'].iloc[-1]
            },
            'band_efficiency': {
                'efficiency_2sigma_pct': round(efficiency_2sigma, 1),
                'efficiency_4sigma_pct': round(efficiency_4sigma, 1),
                'touches_superior_2sigma': touches_superior_2sigma,
                'touches_inferior_2sigma': touches_inferior_2sigma,
                'touches_superior_4sigma': touches_superior_4sigma,
                'touches_inferior_4sigma': touches_inferior_4sigma
            },
            'volatility_analysis': {
                'avg_garch_vol': round(data['garch_vol'].mean(), 4),
                'avg_xgb_vol': round(data['xgb_vol'].mean(), 4),
                'avg_hybrid_vol': round(data['hybrid_vol'].mean(), 4),
                'vol_std': round(data['hybrid_vol'].std(), 4),
                'vol_regime_distribution': {
                    'high_vol_days': len(data[data['vol_regime'] == 1]),
                    'low_vol_days': len(data[data['vol_regime'] == 0])
                }
            },
            'trend_analysis': {
                'bull_market_days': len(data[data['trend_regime'] == 1]),
                'bear_market_days': len(data[data['trend_regime'] == 0]),
                'avg_daily_return_pct': round(data['Returns'].mean() * 100, 3),
                'volatility_annual_pct': round(data['Returns'].std() * np.sqrt(252) * 100, 1)
            },
            'iv_validation_current': {
                'score': current_iv_analysis['score'],
                'status': current_iv_analysis['status'],
                'recommendation': current_iv_analysis['recommendation']
            },
            'success': True
        })
        
        return jsonify(bands_stats)
        
    except Exception as e:
        logger.error(f"Erro ao buscar estatísticas Pro para {ticker}: {e}")
        return jsonify({
            'error': 'Erro interno do servidor',
            'success': False
        }), 500

@bandas_pro_bp.route('/chart/<ticker>', methods=['GET'])
def get_chart_html_pro(ticker):
    """
    Retornar apenas o HTML do gráfico Pro
    """
    try:
        period = request.args.get('period', '6mo')
        days_back = int(request.args.get('days', 180))
        
        logger.info(f"Gerando gráfico Pro para {ticker}")
        
        # Análise completa para obter dados
        analysis = bandas_service.get_analysis_summary(ticker, period)
        
        if not analysis.get('success', False):
            return jsonify(analysis), 400
        
        # Retornar apenas o HTML do gráfico
        return jsonify({
            'ticker': analysis['ticker'],
            'chart_html': analysis['chart_html'],
            'iv_score': analysis['iv_validation']['score'],
            'success': True
        })
        
    except Exception as e:
        logger.error(f"Erro ao gerar gráfico Pro para {ticker}: {e}")
        return jsonify({
            'error': 'Erro interno do servidor',
            'success': False
        }), 500

@bandas_pro_bp.route('/documentation', methods=['GET'])
def get_api_documentation_pro():
    """Documentação da API Pro"""
    documentation = {
        'api_name': 'Hybrid Volatility Bands Pro API',
        'version': '3.0.0',
        'description': 'API avançada para análise de bandas de volatilidade híbridas com validação IV via OpLab',
        'endpoints': {
            'GET /api/bandas-pro/health': 'Check de saúde da API Pro',
            'GET /api/bandas-pro/analyze/<ticker>': 'Análise completa com bandas híbridas + validação IV',
            'POST /api/bandas-pro/compare': 'Comparar múltiplos ativos com métricas IV',
            'GET /api/bandas-pro/signals/<ticker>': 'Sinais de trading com confiança ajustada por IV',
            'GET /api/bandas-pro/screener': 'Screener avançado com filtros IV',
            'GET /api/bandas-pro/iv-analysis/<ticker>': 'Análise detalhada de volatilidade implícita',
            'GET /api/bandas-pro/bands-stats/<ticker>': 'Estatísticas das bandas com validação IV',
            'GET /api/bandas-pro/chart/<ticker>': 'HTML do gráfico Pro'
        },
        'pro_features': {
            'iv_validation': 'Validação de rompimentos via volatilidade implícita OpLab',
            'confidence_adjustment': 'Confiança dos sinais ajustada por score IV',
            'advanced_screener': 'Filtros por status IV e score de confiança',
            'detailed_iv_analysis': 'Métricas completas de IV: rank, spread, HV/IV ratio'
        },
        'iv_metrics': {
            'iv_rank_1y': 'Percentil da IV atual vs últimos 12 meses',
            'iv_ewma_spread': 'Diferença entre IV atual e média móvel exponencial',
            'hv_iv_ratio': 'Ratio entre volatilidade histórica e implícita',
            'confidence_score': 'Score 0-100 baseado em múltiplas métricas IV'
        },
        'signals_enhanced': {
            'BUY_VOLATILITY': 'Comprar volatilidade - validado por IV baixa',
            'SELL_VOLATILITY': 'Vender volatilidade - validado por IV alta',
            'PUT_BIAS': 'Estratégia bearish - com validação de skew',
            'CALL_BIAS': 'Estratégia bullish - com validação de momentum'
        }
    }
    
    return jsonify(documentation)

# Error handlers
@bandas_pro_bp.errorhandler(404)
def not_found_pro(error):
    return jsonify({
        'error': 'Endpoint Pro não encontrado',
        'success': False
    }), 404

@bandas_pro_bp.errorhandler(500)
def internal_error_pro(error):
    return jsonify({
        'error': 'Erro interno do servidor Pro',
        'success': False
    }), 500
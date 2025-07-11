# vol_regimes_routes.py - Hybrid Volatility Bands Routes
from flask import Blueprint, request, jsonify
import numpy as np
import pandas as pd
from datetime import datetime
import logging
from vol_regimes_service import VolatilityRegimesService

# Criar blueprint
vol_regimes_bp = Blueprint('vol_regimes', __name__, url_prefix='/api/volatility')

# Inicializar serviço
vol_service = VolatilityRegimesService()

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

@vol_regimes_bp.route('/health', methods=['GET'])
def health_check():
    """Check de saúde da API"""
    return jsonify({
        'status': 'OK',
        'service': 'Hybrid Volatility Bands API',
        'timestamp': datetime.now().isoformat(),
        'version': '2.0.0'
    })

@vol_regimes_bp.route('/analyze/<ticker>', methods=['GET'])
def analyze_ticker(ticker):
    """
    Analisar um ticker específico com Bandas de Volatilidade Híbridas
    
    Parâmetros:
    - ticker: Código da ação (ex: PETR4 ou PETR4.SA)
    - period: Período de análise (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
    """
    try:
        # Parâmetros da query
        period = request.args.get('period', '6mo')
        
        logger.info(f"Analisando {ticker} - período: {period}")
        
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
        
        # Executar análise
        analysis = vol_service.get_analysis_summary(ticker, period)
        
        if not analysis.get('success', False):
            logger.error(f"Análise falhou para {ticker}: {analysis.get('error', 'Erro desconhecido')}")
            return jsonify(analysis), 400
        
        # CORREÇÃO CRÍTICA: Garantir que TODOS os dados sejam JSON-safe
        safe_analysis = ensure_json_safe(analysis)
        
        logger.info(f"Análise bem-sucedida para {ticker}")
        return jsonify(safe_analysis)
        
    except ValueError as e:
        logger.error(f"Erro de validação para {ticker}: {e}")
        return jsonify({
            'error': f'Parâmetros inválidos: {str(e)}',
            'success': False
        }), 400
    except Exception as e:
        logger.error(f"Erro interno na análise de {ticker}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': 'Erro interno do servidor',
            'success': False
        }), 500

@vol_regimes_bp.route('/compare', methods=['POST'])
def compare_tickers():
    """
    Comparar múltiplos tickers
    
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
            logger.info(f"Analisando {ticker} para comparação")
            analysis = vol_service.get_analysis_summary(ticker, period)
            
            if analysis.get('success', False):
                # Resumir para comparação e garantir JSON-safe
                results[ticker] = ensure_json_safe({
                    'current_price': analysis['current_price'],
                    'volatility': analysis['metrics']['volatility'],
                    'bands': analysis['metrics']['bands'],
                    'position': analysis['metrics']['position'],
                    'trading_signal': {
                        'signal': analysis['trading_signal']['signal'],
                        'confidence': analysis['trading_signal']['confidence'],
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
        logger.error(f"Erro na comparação: {e}")
        return jsonify({
            'error': 'Erro interno do servidor',
            'success': False
        }), 500

@vol_regimes_bp.route('/signals/<ticker>', methods=['GET'])
def get_signals_only(ticker):
    """
    Retornar apenas sinais de trading (endpoint mais rápido)
    """
    try:
        period = request.args.get('period', '3mo')
        
        logger.info(f"Buscando sinais para {ticker}")
        
        # Análise simplificada
        analysis = vol_service.get_analysis_summary(ticker, period)
        
        if not analysis.get('success', False):
            return jsonify(analysis), 400
        
        # Retornar apenas sinais e métricas essenciais
        signals_only = ensure_json_safe({
            'ticker': analysis['ticker'],
            'current_price': analysis['current_price'],
            'last_update': analysis['last_update'],
            'trading_signal': analysis['trading_signal'],
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
        logger.error(f"Erro ao buscar sinais para {ticker}: {e}")
        return jsonify({
            'error': 'Erro interno do servidor',
            'success': False
        }), 500

@vol_regimes_bp.route('/screener', methods=['GET'])
def volatility_screener():
    """
    Screener de volatilidade para múltiplos ativos brasileiros
    
    Query params:
        - signal_type: Filtrar por tipo de sinal (BUY_VOLATILITY, SELL_VOLATILITY, PUT_BIAS, CALL_BIAS)
        - min_confidence: Confiança mínima (0-100)
    """
    try:
        # Ativos brasileiros mais líquidos
        default_tickers = [
            'PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3',
            'SUZB3', 'WEGE3', 'RENT3', 'LREN3', 'MGLU3'
        ]
        
        signal_filter = request.args.get('signal_type')
        min_confidence = float(request.args.get('min_confidence', 0))
        period = request.args.get('period', '3mo')
        
        logger.info(f"Executando screener - filtro: {signal_filter}, min_confidence: {min_confidence}")
        
        screener_results = []
        
        for ticker in default_tickers:
            try:
                analysis = vol_service.get_analysis_summary(ticker, period)
                
                if analysis.get('success', False):
                    signal_data = analysis['trading_signal']
                    
                    # Aplicar filtros
                    if signal_filter and signal_data['signal'] != signal_filter:
                        continue
                    
                    if signal_data['confidence'] < min_confidence:
                        continue
                    
                    screener_results.append(ensure_json_safe({
                        'ticker': analysis['ticker'],
                        'current_price': analysis['current_price'],
                        'signal': signal_data['signal'],
                        'confidence': signal_data['confidence'],
                        'strategy': signal_data['strategy'],
                        'volatility_regime': analysis['metrics']['volatility']['regime'],
                        'position': analysis['metrics']['position']['description'],
                        'trend_regime': analysis['metrics']['position']['trend_regime']
                    }))
                    
            except Exception as e:
                logger.warning(f"Erro ao analisar {ticker} no screener: {e}")
                continue
        
        # Ordenar por confiança
        screener_results.sort(key=lambda x: x['confidence'], reverse=True)
        
        return jsonify(ensure_json_safe({
            'screener_results': screener_results,
            'filters_applied': {
                'signal_type': signal_filter,
                'min_confidence': min_confidence,
                'period': period
            },
            'total_found': len(screener_results),
            'timestamp': datetime.now().isoformat(),
            'success': True
        }))
        
    except Exception as e:
        logger.error(f"Erro no screener: {e}")
        return jsonify({
            'error': 'Erro interno do servidor',
            'success': False
        }), 500

@vol_regimes_bp.route('/bands-stats/<ticker>', methods=['GET'])
def get_bands_statistics(ticker):
    """
    Estatísticas detalhadas das bandas de volatilidade
    """
    try:
        period = request.args.get('period', '1y')
        
        logger.info(f"Buscando estatísticas de bandas para {ticker}")
        
        # Buscar dados históricos mais longos para estatísticas
        search_ticker = ticker if ticker.endswith('.SA') or ticker.startswith('^') else ticker + '.SA'
        data = vol_service.get_stock_data(search_ticker, period)
        if data is None:
            return jsonify({
                'error': 'Dados não encontrados',
                'success': False
            }), 400
        
        # Calcular todos os indicadores
        data = vol_service.calculate_base_volatility(data)
        data = vol_service.engineer_features(data)
        data = vol_service.train_xgboost(data)
        data = vol_service.create_hybrid_model(data)
        data = vol_service.create_bands(data)
        
        # Estatísticas das bandas
        bands_stats = {}
        
        # Estatísticas gerais
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
            'success': True
        })
        
        return jsonify(bands_stats)
        
    except Exception as e:
        logger.error(f"Erro ao buscar estatísticas para {ticker}: {e}")
        return jsonify({
            'error': 'Erro interno do servidor',
            'success': False
        }), 500

@vol_regimes_bp.route('/chart/<ticker>', methods=['GET'])
def get_chart_html(ticker):
    """
    Retornar apenas o HTML do gráfico
    """
    try:
        period = request.args.get('period', '6mo')
        days_back = int(request.args.get('days', 180))
        
        logger.info(f"Gerando gráfico para {ticker}")
        
        # Análise completa para obter dados
        analysis = vol_service.get_analysis_summary(ticker, period)
        
        if not analysis.get('success', False):
            return jsonify(analysis), 400
        
        # Retornar apenas o HTML do gráfico
        return jsonify({
            'ticker': analysis['ticker'],
            'chart_html': analysis['chart_html'],
            'success': True
        })
        
    except Exception as e:
        logger.error(f"Erro ao gerar gráfico para {ticker}: {e}")
        return jsonify({
            'error': 'Erro interno do servidor',
            'success': False
        }), 500

@vol_regimes_bp.route('/tickers/popular', methods=['GET'])
def get_popular_tickers():
    """Retornar lista de tickers populares brasileiros"""
    popular_tickers = {
        'large_caps': [
            {'ticker': 'PETR4', 'name': 'Petrobras', 'sector': 'Energia'},
            {'ticker': 'VALE3', 'name': 'Vale', 'sector': 'Mineração'},
            {'ticker': 'ITUB4', 'name': 'Itaú', 'sector': 'Bancos'},
            {'ticker': 'BBDC4', 'name': 'Bradesco', 'sector': 'Bancos'},
            {'ticker': 'ABEV3', 'name': 'Ambev', 'sector': 'Bebidas'},
        ],
        'mid_caps': [
            {'ticker': 'WEGE3', 'name': 'WEG', 'sector': 'Máquinas'},
            {'ticker': 'RENT3', 'name': 'Localiza', 'sector': 'Aluguel'},
            {'ticker': 'LREN3', 'name': 'Lojas Renner', 'sector': 'Varejo'},
            {'ticker': 'SUZB3', 'name': 'Suzano', 'sector': 'Papel'},
            {'ticker': 'MGLU3', 'name': 'Magazine Luiza', 'sector': 'E-commerce'},
        ],
        'indices': [
            {'ticker': '^BVSP', 'name': 'Ibovespa', 'sector': 'Índice'},
        ]
    }
    
    return jsonify({
        'popular_tickers': popular_tickers,
        'total_count': sum(len(category) for category in popular_tickers.values()),
        'success': True
    })

@vol_regimes_bp.route('/documentation', methods=['GET'])
def get_api_documentation():
    """Documentação da API"""
    documentation = {
        'api_name': 'Hybrid Volatility Bands API',
        'version': '2.0.0',
        'description': 'API para análise de bandas de volatilidade híbridas usando GARCH + XGBoost',
        'endpoints': {
            'GET /api/volatility/health': 'Check de saúde da API',
            'GET /api/volatility/analyze/<ticker>': 'Análise completa com bandas híbridas',
            'POST /api/volatility/compare': 'Comparar múltiplos ativos',
            'GET /api/volatility/signals/<ticker>': 'Apenas sinais de trading',
            'GET /api/volatility/screener': 'Screener de volatilidade',
            'GET /api/volatility/bands-stats/<ticker>': 'Estatísticas das bandas',
            'GET /api/volatility/chart/<ticker>': 'HTML do gráfico Plotly',
            'GET /api/volatility/tickers/popular': 'Tickers populares'
        },
        'indicators': {
            'garch_volatility': 'Modelo GARCH(1,1) para volatilidade condicional',
            'xgboost_volatility': 'XGBoost para predição de volatilidade com features engineered',
            'hybrid_model': 'Combinação adaptativa GARCH + XGBoost baseada em regime',
            'volatility_bands': 'Bandas 2σ e 4σ com referência mensal'
        },
        'signals': {
            'BUY_VOLATILITY': 'Comprar volatilidade - preço próximo das bandas inferiores',
            'SELL_VOLATILITY': 'Vender volatilidade - preço acima da banda superior',
            'PUT_BIAS': 'Estratégia bearish - metade inferior das bandas',
            'CALL_BIAS': 'Estratégia bullish - metade superior das bandas'
        },
        'features': {
            'plotly_charts': 'Gráficos interativos com candlestick e bandas',
            'real_time_price': 'Preços em tempo real via yfinance intraday',
            'adaptive_weighting': 'Pesos dinâmicos entre GARCH e XGBoost',
            'monthly_references': 'Bandas baseadas em referências mensais'
        }
    }
    
    return jsonify(documentation)

# Error handlers
@vol_regimes_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Endpoint não encontrado',
        'success': False
    }), 404

@vol_regimes_bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        'error': 'Erro interno do servidor',
        'success': False
    }), 500
# vol_regimes_routes.py (VERSÃO CORRIGIDA)
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
        'service': 'Volatility Regimes API',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

@vol_regimes_bp.route('/analyze/<ticker>', methods=['GET'])
def analyze_ticker(ticker):
    """
    Analisar um ticker específico
    
    Parâmetros:
    - ticker: Código da ação (ex: PETR4 ou PETR4.SA)
    - period: Período de análise (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
    - clusters: Número de clusters para regimes (padrão: 3)
    - window: Janela para cálculos direcionais (padrão: 20)
    """
    try:
        # Parâmetros da query
        period = request.args.get('period', '6mo')
        n_clusters = int(request.args.get('clusters', 3))
        window = int(request.args.get('window', 20))
        
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
        
        # Validar clusters
        if n_clusters < 2 or n_clusters > 5:
            return jsonify({
                'error': 'Número de clusters deve estar entre 2 e 5',
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
                    'regime': analysis['metrics']['regime'],
                    'directional': analysis['metrics']['directional'],
                    'squeeze': analysis['metrics']['squeeze'],
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
                'regime_name': analysis['metrics']['regime']['name'],
                'squeeze_signal': analysis['metrics']['squeeze']['signal'],
                'directional_signal': analysis['metrics']['directional']['signal']
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
                        'regime': analysis['metrics']['regime']['name'],
                        'squeeze_signal': analysis['metrics']['squeeze']['signal'],
                        'directional_signal': analysis['metrics']['directional']['signal']
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

@vol_regimes_bp.route('/regime-stats/<ticker>', methods=['GET'])
def get_regime_statistics(ticker):
    """
    Estatísticas detalhadas dos regimes de volatilidade
    """
    try:
        period = request.args.get('period', '1y')
        
        logger.info(f"Buscando estatísticas de regime para {ticker}")
        
        # Buscar dados históricos mais longos para estatísticas
        data = vol_service.get_stock_data(ticker, period)
        if data is None:
            return jsonify({
                'error': 'Dados não encontrados',
                'success': False
            }), 400
        
        # Calcular indicadores
        data = vol_service.calculate_regime_clustering(data)
        data = vol_service.calculate_directional_flow(data)
        data = vol_service.calculate_squeeze_score(data)
        
        # Estatísticas por regime
        regime_stats = {}
        for regime in data['regime'].unique():
            regime_data = data[data['regime'] == regime]
            if len(regime_data) > 0:
                regime_stats[int(regime)] = ensure_json_safe({
                    'regime_name': regime_data['regime_name'].iloc[0],
                    'frequency_pct': round(len(regime_data) / len(data) * 100, 1),
                    'avg_return': round(regime_data['return'].mean() * 100, 3),
                    'volatility': round(regime_data['return'].std() * np.sqrt(252) * 100, 1),
                    'avg_duration_days': round(regime_data['regime_persistence'].mean(), 1),
                    'max_duration_days': int(regime_data['regime_persistence'].max()),
                    'avg_squeeze_score': round(regime_data['squeeze_smooth'].mean(), 3),
                    'avg_asymmetry': round(regime_data['dir_asymmetry_ratio'].mean(), 2)
                })
        
        # Transições entre regimes
        regime_transitions = data['regime'].diff()
        transition_count = len(regime_transitions[regime_transitions != 0])
        avg_regime_duration = len(data) / max(transition_count, 1)
        
        return jsonify(ensure_json_safe({
            'ticker': ticker,
            'period': period,
            'data_points': len(data),
            'regime_statistics': regime_stats,
            'transition_analysis': {
                'total_transitions': transition_count,
                'avg_regime_duration_days': round(avg_regime_duration, 1),
                'transition_frequency_pct': round(transition_count / len(data) * 100, 2)
            },
            'current_regime': {
                'regime': int(data['regime'].iloc[-1]),
                'name': data['regime_name'].iloc[-1],
                'duration_days': int(data['regime_persistence'].iloc[-1])
            },
            'success': True
        }))
        
    except Exception as e:
        logger.error(f"Erro ao buscar estatísticas para {ticker}: {e}")
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
        'api_name': 'Volatility Regimes API',
        'version': '1.0.0',
        'description': 'API para análise de regimes de volatilidade usando indicadores não convencionais',
        'endpoints': {
            'GET /api/volatility/health': 'Check de saúde da API',
            'GET /api/volatility/analyze/<ticker>': 'Análise completa de um ativo',
            'POST /api/volatility/compare': 'Comparar múltiplos ativos',
            'GET /api/volatility/signals/<ticker>': 'Apenas sinais de trading',
            'GET /api/volatility/screener': 'Screener de volatilidade',
            'GET /api/volatility/regime-stats/<ticker>': 'Estatísticas detalhadas',
            'GET /api/volatility/tickers/popular': 'Tickers populares'
        },
        'indicators': {
            'regime_clustering': 'K-means clustering para identificar regimes de volatilidade',
            'directional_flow': 'Assimetria de volatilidade (up vs down movements)',
            'squeeze_score': 'Bollinger Bands vs Keltner Channels para compressão/expansão'
        },
        'signals': {
            'BUY_VOLATILITY': 'Comprar volatilidade (Long Straddle)',
            'SELL_VOLATILITY': 'Vender volatilidade (Iron Condor)',
            'PUT_BIAS': 'Estratégia bearish (Put Spread)',
            'CALL_BIAS': 'Estratégia bullish (Call Spread)',
            'HOLD': 'Aguardar'
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
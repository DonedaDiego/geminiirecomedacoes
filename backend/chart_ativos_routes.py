# chart_ativos_routes.py
"""
Rotas para o serviço Chart Ativos
"""

from flask import Blueprint, request, jsonify
from chart_ativos_service import ChartAtivosService
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Criar blueprint
chart_ativos_bp = Blueprint('chart_ativos', __name__, url_prefix='/chart_ativos')

# Instanciar serviço
chart_service = ChartAtivosService()

@chart_ativos_bp.route('/health', methods=['GET'])
def health_check():
    """Endpoint para verificar saúde do serviço"""
    try:
        # Teste básico do serviço
        test_tickers = ['PETR4', 'VALE3']
        prices = chart_service.get_current_prices(test_tickers)
        
        return jsonify({
            'status': 'OK',
            'message': 'Serviço Chart Ativos funcionando corretamente',
            'timestamp': None,
            'test_prices': len(prices)
        })
    except Exception as e:
        logger.error(f"Erro no health check: {e}")
        return jsonify({
            'status': 'ERROR',
            'message': f'Erro no serviço: {str(e)}'
        }), 500

@chart_ativos_bp.route('/portfolio/<portfolio_name>/analytics', methods=['GET'])
def get_portfolio_analytics(portfolio_name):
    """
    Analisa performance completa de uma carteira
    
    GET /chart_ativos/portfolio/{portfolio_name}/analytics
    
    Returns:
        JSON com métricas de performance, dados para gráficos e comparação com benchmark
    """
    try:
        logger.info(f"📊 Solicitação de analytics da carteira: {portfolio_name}")
        
        # TODO: Buscar carteira e ativos do seu banco de dados
        # portfolio = sua_função_buscar_carteira(portfolio_name)
        # assets = sua_função_buscar_ativos(portfolio_name)
        
        # Por enquanto, exemplo estático para testar
        mock_assets = [
            {'ticker': 'PETR4', 'weight': 25.0, 'created_at': '2024-01-01'},
            {'ticker': 'VALE3', 'weight': 25.0, 'created_at': '2024-01-01'}
        ]
        
        # Executar análise usando o serviço
        analytics_data = chart_service.analyze_portfolio(mock_assets, portfolio_name)
        
        logger.info(f"✅ Analytics gerado para {portfolio_name}")
        
        return jsonify({
            'success': True,
            'analytics_data': analytics_data
        })

    except Exception as e:
        logger.error(f"❌ Erro geral no endpoint analytics: {e}")
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor'
        }), 500

@chart_ativos_bp.route('/portfolio/<portfolio_name>/prices', methods=['GET'])
def get_portfolio_current_prices(portfolio_name):

    try:
        logger.info(f"💰 Solicitação de preços da carteira: {portfolio_name}")
        
        # TODO: Buscar ativos da carteira do seu banco
        # assets = sua_função_buscar_ativos(portfolio_name)
        
        # Mock para teste
        mock_tickers = ['PETR4', 'VALE3', 'ITUB4']
        
        # Buscar preços atuais
        current_prices = chart_service.get_current_prices(mock_tickers)
        
        # Montar resposta
        assets_data = []
        for ticker in mock_tickers:
            current_price = current_prices.get(ticker, 0)
            assets_data.append({
                'ticker': ticker,
                'current_price': current_price
            })
        
        logger.info(f"✅ Preços atualizados para {len(assets_data)} ativos da carteira {portfolio_name}")
        
        return jsonify({
            'success': True,
            'prices_data': {
                'portfolio_name': portfolio_name,
                'assets': assets_data,
                'total_assets': len(assets_data),
                'updated_prices': len([p for p in current_prices.values() if p > 0])
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar preços: {e}")
        return jsonify({
            'success': False,
            'error': 'Erro ao buscar preços atuais'
        }), 500

@chart_ativos_bp.route('/ticker/<ticker>/price', methods=['GET'])
def get_ticker_price(ticker):
    """
    Busca preço atual de um ticker específico
    
    GET /chart_ativos/ticker/{ticker}/price
    
    Returns:
        JSON com preço atual do ticker
    """
    try:
        logger.info(f"💰 Buscando preço do ticker: {ticker}")
        
        ticker = ticker.upper().strip()
        
        # Buscar preço atual
        prices = chart_service.get_current_prices([ticker])
        current_price = prices.get(ticker, 0)
        
        if current_price == 0:
            return jsonify({
                'success': False,
                'error': f'Preço não encontrado para {ticker}'
            }), 404
        
        return jsonify({
            'success': True,
            'price_data': {
                'ticker': ticker,
                'current_price': current_price,
                'timestamp': None  # Pode adicionar timestamp se necessário
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar preço do ticker {ticker}: {e}")
        return jsonify({
            'success': False,
            'error': 'Erro ao buscar preço'
        }), 500

@chart_ativos_bp.route('/bulk_prices', methods=['POST'])
def bulk_get_prices():
    """
    Busca preços de múltiplos tickers em lote
    
    POST /chart_ativos/bulk_prices
    
    Payload esperado:
    {
        "tickers": ["PETR4", "VALE3", "ITUB4"]
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Dados não fornecidos'
            }), 400
        
        tickers = data.get('tickers', [])
        if not tickers or not isinstance(tickers, list):
            return jsonify({
                'success': False,
                'error': 'Lista de tickers é obrigatória'
            }), 400
        
        # Limpar e normalizar tickers
        clean_tickers = [ticker.upper().strip() for ticker in tickers if ticker.strip()]
        
        if not clean_tickers:
            return jsonify({
                'success': False,
                'error': 'Nenhum ticker válido fornecido'
            }), 400
        
        logger.info(f"📊 Buscando preços em lote para {len(clean_tickers)} tickers")
        
        # Buscar preços
        current_prices = chart_service.get_current_prices(clean_tickers)
        
        # Montar resposta
        results = []
        errors = []
        
        for ticker in clean_tickers:
            price = current_prices.get(ticker, 0)
            if price > 0:
                results.append({
                    'ticker': ticker,
                    'current_price': price
                })
            else:
                errors.append(f"Preço não encontrado para {ticker}")
        
        logger.info(f"✅ Preços em lote: {len(results)} sucessos, {len(errors)} erros")
        
        return jsonify({
            'success': True,
            'bulk_prices_data': {
                'results': results,
                'errors': errors,
                'total_found': len(results),
                'total_errors': len(errors),
                'requested_tickers': len(clean_tickers)
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Erro na busca em lote: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@chart_ativos_bp.route('/benchmark/performance', methods=['GET'])
def get_benchmark_performance():
    """
    Busca performance do benchmark (IBOVESPA)
    
    GET /chart_ativos/benchmark/performance?period=30d
    
    Query Parameters:
        period: Período em dias (padrão: 30d)
    
    Returns:
        JSON com dados de performance do IBOVESPA
    """
    try:
        # Pegar período dos query parameters
        period_str = request.args.get('period', '30d')
        
        # Converter período para dias
        if period_str.endswith('d'):
            days = int(period_str[:-1])
        elif period_str.endswith('m'):
            days = int(period_str[:-1]) * 30
        elif period_str.endswith('y'):
            days = int(period_str[:-1]) * 365
        else:
            days = 30
        
        # Limitar período máximo
        days = min(days, 1095)  # Máximo 3 anos
        
        logger.info(f"📊 Buscando performance do IBOVESPA para {days} dias")
        
        from datetime import datetime, timedelta
        
        # Definir período
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Buscar dados do IBOVESPA
        benchmark_data = chart_service._fetch_historical_data(
            [chart_service.benchmark_ticker], 
            start_date, 
            end_date
        )
        
        if benchmark_data.empty:
            return jsonify({
                'success': False,
                'error': 'Dados do benchmark não encontrados'
            }), 404
        
        # Normalizar e calcular performance
        normalized = benchmark_data / benchmark_data.iloc[0]
        total_return = (normalized.iloc[-1].iloc[0] - 1) * 100
        
        # Calcular volatilidade
        daily_returns = benchmark_data.pct_change().dropna()
        volatility = daily_returns.std().iloc[0] * np.sqrt(252) * 100
        
        # Preparar dados para gráfico (últimos 30 pontos)
        chart_data = normalized.tail(30)
        
        return jsonify({
            'success': True,
            'benchmark_data': {
                'benchmark_name': 'IBOVESPA',
                'period_days': days,
                'total_return': round(total_return, 2),
                'volatility': round(volatility, 2),
                'chart_data': {
                    'dates': chart_data.index.strftime('%Y-%m-%d').tolist(),
                    'values': chart_data.iloc[:, 0].tolist()
                }
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar performance do benchmark: {e}")
        return jsonify({
            'success': False,
            'error': 'Erro ao buscar dados do benchmark'
        }), 500

@chart_ativos_bp.route('/compare_portfolios', methods=['POST'])
def compare_portfolios():
    """
    Compara performance entre duas carteiras
    
    POST /chart_ativos/compare_portfolios
    
    Payload esperado:
    {
        "portfolio1": "bluechips",
        "portfolio2": "growth"
    }
    """
    try:
        # TODO: Implementar seu sistema de autenticação aqui
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Dados não fornecidos'
            }), 400
        
        portfolio1_name = data.get('portfolio1', '').strip()
        portfolio2_name = data.get('portfolio2', '').strip()
        
        if not portfolio1_name or not portfolio2_name:
            return jsonify({
                'success': False,
                'error': 'Ambas as carteiras são obrigatórias'
            }), 400
        
        if portfolio1_name == portfolio2_name:
            return jsonify({
                'success': False,
                'error': 'As carteiras devem ser diferentes'
            }), 400
        
        logger.info(f"🔍 Comparando carteiras {portfolio1_name} vs {portfolio2_name}")
        
        # TODO: Integrar com seu banco de dados
        # Por enquanto, retorna erro informativo
        return jsonify({
            'success': False,
            'error': 'Funcionalidade em desenvolvimento - aguarde integração com banco de dados'
        }), 501
        
    except Exception as e:
        logger.error(f"❌ Erro na comparação de carteiras: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

# Função para registrar o blueprint
def register_chart_ativos_routes(app):
    """Registra as rotas Chart Ativos na aplicação Flask"""
    app.register_blueprint(chart_ativos_bp)
    logger.info("Rotas Chart Ativos registradas com sucesso")
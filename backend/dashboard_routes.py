# dashboard_routes.py
from flask import Blueprint, request, jsonify
from yfinance_service import YFinanceService
from database import get_db_connection
from psycopg2.extras import RealDictCursor
from datetime import datetime
import traceback

# Criar blueprint para rotas do dashboard
dashboard_bp = Blueprint('dashboard', __name__)

def get_portfolio_recommendations_data(portfolio_name='carteira_bdr', limit=10):
    """Buscar recomendações de uma carteira específica"""
    try:
        conn = get_db_connection()
        if not conn:
            return {
                'success': False,
                'error': 'Falha na conexão com banco de dados'
            }
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Buscar dados mais recentes da carteira
        cursor.execute(f"""
            SELECT 
                ticker,
                setor,
                peso,
                peso_percent,
                preco_atual as preco_entrada,
                data_geracao,
                retorno_anualizado_percent,
                risco_anualizado_percent,
                sharpe,
                beta
            FROM {portfolio_name}
            WHERE data_geracao = (
                SELECT MAX(data_geracao) FROM {portfolio_name}
            )
            ORDER BY peso_percent DESC
            LIMIT %s;
        """, (limit,))
        
        portfolio_data = cursor.fetchall()
        
        if not portfolio_data:
            cursor.close()
            conn.close()
            return {
                'success': False,
                'error': f'Nenhum dado encontrado na carteira {portfolio_name}'
            }
        
        # Buscar preços atuais no yfinance
        symbols = [row['ticker'] for row in portfolio_data]
        current_prices = YFinanceService.get_multiple_stocks(symbols)
        
        recommendations = []
        
        for stock in portfolio_data:
            ticker = stock['ticker']
            
            # Dados da carteira (imutáveis)
            entrada = {
                'preco': float(stock['preco_entrada']),
                'data': stock['data_geracao'].strftime('%d/%m/%Y'),
                'peso_percent': float(stock['peso_percent'])
            }
            
            # Dados atuais do yfinance
            current_data = current_prices['data'].get(ticker, {})
            
            if current_data.get('status') == 'success':
                preco_atual = current_data['current_price']
                
                # Calcular performance desde a entrada
                performance = ((preco_atual - entrada['preco']) / entrada['preco']) * 100
                
                # Determinar recomendação
                if performance >= 10:
                    recomendacao = 'VENDA'
                    cor = 'green'
                    icone = '📈'
                elif performance <= -5:
                    recomendacao = 'COMPRA FORTE'
                    cor = 'blue'
                    icone = '🔥'
                elif performance <= 0:
                    recomendacao = 'COMPRA'
                    cor = 'orange'
                    icone = '⚡'
                else:
                    recomendacao = 'MANTER'
                    cor = 'gray'
                    icone = '✋'
                
                recommendations.append({
                    'ticker': ticker,
                    'setor': stock['setor'],
                    'recomendacao': recomendacao,
                    'cor': cor,
                    'icone': icone,
                    'entrada': entrada,
                    'atual': {
                        'preco': preco_atual,
                        'data': current_data.get('last_update', 'Agora'),
                        'volume': current_data.get('volume', 0)
                    },
                    'performance': {
                        'valor': round(performance, 2),
                        'absoluto': round(preco_atual - entrada['preco'], 2),
                        'dias': (datetime.now().date() - stock['data_geracao']).days
                    },
                    'fundamentals': {
                        'sharpe': float(stock['sharpe']) if stock['sharpe'] else None,
                        'beta': float(stock['beta']) if stock['beta'] else None,
                        'retorno_anualizado': float(stock['retorno_anualizado_percent']) if stock['retorno_anualizado_percent'] else None,
                        'risco_anualizado': float(stock['risco_anualizado_percent']) if stock['risco_anualizado_percent'] else None
                    }
                })
            
            else:
                # Se não conseguir dados do yfinance, marcar como indisponível
                recommendations.append({
                    'ticker': ticker,
                    'setor': stock['setor'],
                    'recomendacao': 'DADOS INDISPONÍVEIS',
                    'cor': 'red',
                    'icone': '❌',
                    'entrada': entrada,
                    'atual': {
                        'preco': 0,
                        'data': 'N/A',
                        'volume': 0
                    },
                    'performance': {
                        'valor': 0,
                        'absoluto': 0,
                        'dias': (datetime.now().date() - stock['data_geracao']).days
                    },
                    'fundamentals': {
                        'sharpe': float(stock['sharpe']) if stock['sharpe'] else None,
                        'beta': float(stock['beta']) if stock['beta'] else None,
                        'retorno_anualizado': float(stock['retorno_anualizado_percent']) if stock['retorno_anualizado_percent'] else None,
                        'risco_anualizado': float(stock['risco_anualizado_percent']) if stock['risco_anualizado_percent'] else None
                    },
                    'error': current_data.get('error', 'Dados não disponíveis')
                })
        
        cursor.close()
        conn.close()
        
        # Estatísticas do portfólio
        valid_recommendations = [r for r in recommendations if r['recomendacao'] != 'DADOS INDISPONÍVEIS']
        
        if valid_recommendations:
            total_performance = sum(r['performance']['valor'] for r in valid_recommendations)
            avg_performance = total_performance / len(valid_recommendations)
            
            compras = len([r for r in valid_recommendations if 'COMPRA' in r['recomendacao']])
            vendas = len([r for r in valid_recommendations if r['recomendacao'] == 'VENDA'])
            manter = len([r for r in valid_recommendations if r['recomendacao'] == 'MANTER'])
        else:
            avg_performance = 0
            compras = vendas = manter = 0
        
        return {
            'success': True,
            'data': {
                'portfolio_name': portfolio_name,
                'recommendations': recommendations,
                'statistics': {
                    'total_stocks': len(recommendations),
                    'valid_data': len(valid_recommendations),
                    'avg_performance': round(avg_performance, 2),
                    'signals': {
                        'compras': compras,
                        'vendas': vendas,
                        'manter': manter
                    }
                },
                'last_update': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'data_source': 'Portfolio DB + Yahoo Finance'
            }
        }
        
    except Exception as e:
        print(f"❌ Erro ao buscar recomendações: {e}")
        return {
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }

def get_portfolio_summary_data():
    """Resumo geral de todas as carteiras"""
    try:
        conn = get_db_connection()
        if not conn:
            return {
                'success': False,
                'error': 'Falha na conexão com banco de dados'
            }
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        carteiras = ['carteira_bdr', 'carteira_growth', 'carteira_bluechips', 'carteira_smallcaps']
        summary = {}
        
        for carteira in carteiras:
            try:
                # Verificar se tabela existe
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = %s
                    );
                """, (carteira,))
                
                exists = cursor.fetchone()[0]
                
                if exists:
                    # Contar registros
                    cursor.execute(f"SELECT COUNT(*) as total FROM {carteira};")
                    total = cursor.fetchone()['total']
                    
                    # Data mais recente
                    cursor.execute(f"""
                        SELECT MAX(data_geracao) as ultima_data 
                        FROM {carteira};
                    """)
                    ultima_data = cursor.fetchone()['ultima_data']
                    
                    summary[carteira] = {
                        'exists': True,
                        'total_stocks': total,
                        'last_update': ultima_data.strftime('%d/%m/%Y') if ultima_data else 'N/A'
                    }
                else:
                    summary[carteira] = {
                        'exists': False,
                        'total_stocks': 0,
                        'last_update': 'N/A'
                    }
                    
            except Exception as e:
                summary[carteira] = {
                    'exists': False,
                    'total_stocks': 0,
                    'last_update': 'Erro',
                    'error': str(e)
                }
        
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'data': summary
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f'Erro ao buscar resumo: {str(e)}'
        }

# ===== ROTAS DO DASHBOARD COM RECOMENDAÇÕES =====

@dashboard_bp.route('/api/dashboard/recommendations', methods=['GET'])
def get_dashboard_recommendations():
    """Endpoint principal para recomendações do dashboard"""
    try:
        # Buscar recomendações da carteira BDR (padrão)
        portfolio_name = request.args.get('portfolio', 'carteira_bdr')
        limit = int(request.args.get('limit', 8))
        
        recommendations_result = get_portfolio_recommendations_data(portfolio_name, limit)
        
        if not recommendations_result['success']:
            return jsonify({
                'success': False,
                'error': f'Erro ao buscar recomendações: {recommendations_result["error"]}'
            }), 500
        
        # Buscar resumo das carteiras
        portfolio_summary = get_portfolio_summary_data()
        
        # Buscar dados do mercado
        market_stocks = ['BVSP', 'PETR4', 'VALE3', 'ITUB4', 'BBDC4']
        market_data = YFinanceService.get_multiple_stocks(market_stocks)
        
        return jsonify({
            'success': True,
            'data': {
                'recommendations': recommendations_result['data'],
                'portfolio_summary': portfolio_summary['data'] if portfolio_summary['success'] else {},
                'market_overview': {
                    'stocks': market_data['data'] if market_data['success'] else {},
                    'last_update': market_data.get('last_update', 'N/A')
                },
                'user_stats': {
                    'total_analysis': len(recommendations_result['data']['recommendations']),
                    'active_alerts': recommendations_result['data']['statistics']['signals']['compras'],
                    'portfolio_performance': recommendations_result['data']['statistics']['avg_performance']
                }
            },
            'meta': {
                'portfolio_used': portfolio_name,
                'last_update': recommendations_result['data']['last_update'],
                'data_sources': ['PostgreSQL', 'Yahoo Finance']
            }
        })
        
    except Exception as e:
        print(f"❌ Erro no dashboard: {e}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor',
            'details': str(e)
        }), 500

@dashboard_bp.route('/api/portfolio/<portfolio_name>/recommendations', methods=['GET'])
def get_portfolio_recommendations_route(portfolio_name):
    """Endpoint para recomendações de carteira específica"""
    try:
        limit = int(request.args.get('limit', 10))
        
        result = get_portfolio_recommendations_data(portfolio_name, limit)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao buscar recomendações da {portfolio_name}: {str(e)}'
        }), 500

@dashboard_bp.route('/api/portfolio/summary', methods=['GET'])
def get_portfolio_summary_route():
    """Endpoint para resumo de todas as carteiras"""
    try:
        result = get_portfolio_summary_data()
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao buscar resumo das carteiras: {str(e)}'
        }), 500

@dashboard_bp.route('/api/market/overview', methods=['GET'])
def get_market_overview():
    """Endpoint para visão geral do mercado"""
    try:
        # Principais ações do mercado brasileiro
        main_stocks = ['BVSP', 'PETR4', 'VALE3', 'ITUB4', 'BBDC4']
        
        market_data = YFinanceService.get_multiple_stocks(main_stocks)
        
        if market_data['success']:
            return jsonify({
                'success': True,
                'data': {
                    'stocks': market_data['data'],
                    'last_update': market_data['last_update']
                }
            })
        else:
            return jsonify(market_data), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro na visão do mercado: {str(e)}'
        }), 500

# ===== ROTAS EXTRAS PARA YFINANCE =====

@dashboard_bp.route('/api/stocks/<symbol>', methods=['GET'])
def get_stock_data(symbol):
    """Endpoint para dados de ação específica"""
    try:
        result = YFinanceService.get_stock_data(symbol)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao buscar dados de {symbol}: {str(e)}'
        }), 500

@dashboard_bp.route('/api/stocks', methods=['GET'])
def get_multiple_stocks():
    """Endpoint para múltiplas ações"""
    try:
        symbols_param = request.args.get('symbols', '')
        
        if not symbols_param:
            return jsonify({
                'success': False,
                'error': 'Parâmetro symbols é obrigatório'
            }), 400
        
        symbols = [s.strip().upper() for s in symbols_param.split(',')]
        
        result = YFinanceService.get_multiple_stocks(symbols)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao buscar múltiplas ações: {str(e)}'
        }), 500

@dashboard_bp.route('/api/stocks/<symbol>/history', methods=['GET'])
def get_stock_history(symbol):
    """Endpoint para histórico de ação"""
    try:
        period = request.args.get('period', '1mo')
        
        result = YFinanceService.get_stock_history(symbol, period)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao buscar histórico de {symbol}: {str(e)}'
        }), 500

@dashboard_bp.route('/api/search/stocks', methods=['GET'])
def search_stocks():
    """Endpoint para buscar ações"""
    try:
        query = request.args.get('q', '')
        limit = int(request.args.get('limit', 10))
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'Parâmetro q (query) é obrigatório'
            }), 400
        
        result = YFinanceService.search_stocks(query, limit)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro na busca: {str(e)}'
        }), 500

# ===== ENDPOINT DE TESTE =====

@dashboard_bp.route('/api/test/portfolio', methods=['GET'])
def test_portfolio_connection():
    """Endpoint de teste para conexão com portfolio"""
    try:
        # Testar conexão com banco
        conn = get_db_connection()
        
        if conn:
            conn.close()
            db_status = "✅ Conectado"
        else:
            db_status = "❌ Falha na conexão"
        
        # Testar yfinance
        test_stock = YFinanceService.get_stock_data('PETR4')
        yf_status = "✅ Funcionando" if test_stock['success'] else "❌ Falha"
        
        # Testar carteira BDR
        test_portfolio = get_portfolio_recommendations_data('carteira_bdr', 3)
        portfolio_status = "✅ Funcionando" if test_portfolio['success'] else f"❌ {test_portfolio['error']}"
        
        return jsonify({
            'success': True,
            'tests': {
                'database_connection': db_status,
                'yfinance_service': yf_status,
                'portfolio_service': portfolio_status
            },
            'message': 'Teste de integração concluído'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro no teste: {str(e)}'
        }), 500
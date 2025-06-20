# portfolio_service.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, date
from yfinance_service import YFinanceService

class PortfolioService:
    """Serviço para gerenciar carteiras e recomendações"""
    
    @staticmethod
    def get_db_connection():
        """Conectar com PostgreSQL (local ou Render via .env)"""
        try:
            # Se estiver no Render, usar DATABASE_URL
            database_url = os.environ.get("DATABASE_URL")
            
            if database_url:
                # Produção (Render) - usa a URL completa
                conn = psycopg2.connect(database_url, sslmode='require')
                print("🌐 Conectado ao Render PostgreSQL")
            else:
                # Desenvolvimento local - usa variáveis do .env
                conn = psycopg2.connect(
                    host=os.environ.get("DB_HOST", "localhost"),
                    database=os.environ.get("DB_NAME", "postgres"),
                    user=os.environ.get("DB_USER", "postgres"),
                    password=os.environ.get("DB_PASSWORD", "#geminii"),
                    port=os.environ.get("DB_PORT", "5432")
                )
                print("🏠 Conectado ao PostgreSQL local")
            
            return conn
            
        except Exception as e:
            print(f"❌ Erro ao conectar no banco: {e}")
            return None
    
    @staticmethod
    def get_portfolio_recommendations(portfolio_name='carteira_bdr', limit=10):
        """Buscar recomendações de uma carteira específica"""
        try:
            conn = PortfolioService.get_db_connection()
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
            print(f"❌ Erro no PortfolioService: {e}")
            return {
                'success': False,
                'error': f'Erro interno: {str(e)}'
            }
    
    @staticmethod
    def get_portfolio_summary():
        """Resumo geral de todas as carteiras"""
        try:
            conn = PortfolioService.get_db_connection()
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
    
    @staticmethod
    def get_market_overview():
        """Visão geral do mercado com principais indicadores"""
        try:
            # Principais ações do mercado brasileiro
            main_stocks = ['BVSP'"A1DM34", "A1MD34", "A1MT34", "A1ZN34", "AALL34", "AAPL34", "ADBE34", 
                       "AIRB34", "AMZO34", "ASML34", "ATTB34", "AVGO34", "AXPB34",
                       "B1IL34", "B1SA34", "B1TI34", "B2YN34", "BABA34", "BCSA34", "BIDU34", "BKNG34", 
                       "BLAK34", "BOAC34", "CATP34", "CHVX34", "C2OI34", "C2RW34", "COCA34", "COLG34", 
                       "COPH34", "COWC34", "CSCO34", "CTGP34", "DHER34", "DEEC34", "DISB34",
                       "E1CO34", "E1QN34", "EQIX34", "EXXO34", "FSLR34", "GEOO34", "GMCO34", "GOGL34", 
                       "GOGL35", "GSGI34", "HOME34", "HPQB34", "ITLC34", "JDCO34", "JNJB34", "JPMC34",
                       "K2CG34", "KHCB34", "L1MN34", "LILY34", "M1RN34", "M1TA34", "M2ST34", "MCDC34", 
                       "MELI34", "MRCK34", "MSBR34", "MSCD34", "MSFT34", "MUTC34", "N1DA34", "N1EM34", 
                       "N1OW34", "N1VO34", "NEXT34", "NFLX34", "NIKE34", "NVDC34", "ORCL34", "OXYP34",
                       "P1DD34", "P1LD34", "P2AN34", "P2LT34", "PAGS34", "PEPB34", "PFIZ34", "PGCO34", 
                       "PYPL34", "QCOM34", "R1IN34", "R2BL34", "RIGG34", "RIOT34", "S1PO34", "S2EA34", 
                       "S2HO34", "S2UI34", "SIMN34", "SNEC34", "SSFO34", "T1OW34", "T1TW34", "T2DH34", 
                       "T2TD34", "TMCO34", "TSLA34", "TSMC34", "U1BE34", "U2ST34", "ULEV34", "UNHH34",
                       "VERZ34", "VISA34", "WALM34", "WFCO34", "Z1TS34"]
            
            market_data = YFinanceService.get_multiple_stocks(main_stocks)
            
            if market_data['success']:
                return {
                    'success': True,
                    'data': {
                        'stocks': market_data['data'],
                        'last_update': market_data['last_update']
                    }
                }
            else:
                return market_data
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Erro na visão do mercado: {str(e)}'
            }

# Função para testar o serviço
if __name__ == "__main__":
    print("🧪 Testando PortfolioService...")
    
    # Teste 1: Recomendações da carteira BDR
    print("\n1️⃣ Testando recomendações carteira BDR:")
    result = PortfolioService.get_portfolio_recommendations('carteira_bdr', 5)
    
    if result['success']:
        data = result['data']
        print(f"✅ Carteira: {data['portfolio_name']}")
        print(f"📊 {data['statistics']['total_stocks']} ações, performance média: {data['statistics']['avg_performance']}%")
        print(f"🎯 Sinais: {data['statistics']['signals']['compras']} compras, {data['statistics']['signals']['vendas']} vendas")
        
        print("\nTop 3 recomendações:")
        for i, rec in enumerate(data['recommendations'][:3], 1):
            print(f"{i}. {rec['ticker']} - {rec['recomendacao']} {rec['icone']}")
            print(f"   Performance: {rec['performance']['valor']:+.2f}% em {rec['performance']['dias']} dias")
    else:
        print(f"❌ {result['error']}")
    
    # Teste 2: Resumo das carteiras
    print("\n2️⃣ Testando resumo das carteiras:")
    result = PortfolioService.get_portfolio_summary()
    
    if result['success']:
        for carteira, info in result['data'].items():
            status = "✅" if info['exists'] else "❌"
            print(f"{status} {carteira}: {info['total_stocks']} ações (última: {info['last_update']})")
    else:
        print(f"❌ {result['error']}")
    
    print("\n🎉 Testes concluídos!")
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from yfinance_service import YFinanceService

class MonitorService:
    """Serviço para análise de Beta e correlação com IBOVESPA"""
    
    def __init__(self):
        self.ibov_symbol = '^BVSP'  # Símbolo do IBOVESPA no Yahoo Finance
        
    def get_ibov_data(self, period_days=252):
        """Buscar dados históricos do IBOVESPA"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period_days + 50)  # Margem extra
            
            ibov = yf.Ticker(self.ibov_symbol)
            hist = ibov.history(start=start_date, end=end_date)
            
            if hist.empty:
                return None
                
            # Calcular retornos diários
            hist['Returns'] = hist['Close'].pct_change().dropna()
            
            return {
                'prices': hist['Close'].tolist(),
                'returns': hist['Returns'].dropna().tolist(),
                'dates': [date.strftime('%Y-%m-%d') for date in hist.index],
                'last_price': float(hist['Close'].iloc[-1]),
                'period_return': float((hist['Close'].iloc[-1] / hist['Close'].iloc[0] - 1) * 100)
            }
            
        except Exception as e:
            print(f"Erro ao buscar IBOV: {e}")
            return None
    
    def get_stock_data_for_beta(self, symbol, period_days=252):
        """Buscar dados históricos de uma ação para cálculo de Beta"""
        try:
            # Garantir que tem .SA
            if not symbol.endswith('.SA'):
                symbol += '.SA'
                
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period_days + 50)  # Margem extra
            
            stock = yf.Ticker(symbol)
            hist = stock.history(start=start_date, end=end_date)
            
            if hist.empty:
                return None
                
            # Calcular retornos diários
            hist['Returns'] = hist['Close'].pct_change().dropna()
            
            return {
                'symbol': symbol.replace('.SA', ''),
                'prices': hist['Close'].tolist(),
                'returns': hist['Returns'].dropna().tolist(),
                'dates': [date.strftime('%Y-%m-%d') for date in hist.index],
                'last_price': float(hist['Close'].iloc[-1]),
                'period_return': float((hist['Close'].iloc[-1] / hist['Close'].iloc[0] - 1) * 100)
            }
            
        except Exception as e:
            print(f"Erro ao buscar dados de {symbol}: {e}")
            return None
    
    def calculate_beta(self, stock_returns, market_returns):
        """Calcular Beta usando regressão linear"""
        try:
            # Alinhar os arrays (mesmo tamanho)
            min_length = min(len(stock_returns), len(market_returns))
            stock_returns = stock_returns[-min_length:]
            market_returns = market_returns[-min_length:]
            
            # Converter para numpy arrays
            stock_returns = np.array(stock_returns)
            market_returns = np.array(market_returns)
            
            # Remover NaN
            mask = ~(np.isnan(stock_returns) | np.isnan(market_returns))
            stock_returns = stock_returns[mask]
            market_returns = market_returns[mask]
            
            if len(stock_returns) < 10:  # Mínimo de dados
                return None
                
            # Calcular Beta (Covariance / Variance)
            covariance = np.cov(stock_returns, market_returns)[0, 1]
            market_variance = np.var(market_returns)
            
            if market_variance == 0:
                return None
                
            beta = covariance / market_variance
            
            # Calcular R² (correlação²)
            correlation = np.corrcoef(stock_returns, market_returns)[0, 1]
            r_squared = correlation ** 2 if not np.isnan(correlation) else 0
            
            # Calcular Alpha (Jensen's Alpha)
            stock_mean_return = np.mean(stock_returns)
            market_mean_return = np.mean(market_returns)
            alpha = stock_mean_return - (beta * market_mean_return)
            
            return {
                'beta': float(beta),
                'r_squared': float(r_squared),
                'correlation': float(correlation),
                'alpha': float(alpha),
                'volatility_stock': float(np.std(stock_returns)),
                'volatility_market': float(np.std(market_returns))
            }
            
        except Exception as e:
            print(f"Erro no cálculo de Beta: {e}")
            return None
    
    def analyze_stock_beta(self, symbol):
        """Análise completa de Beta para uma ação em diferentes períodos"""
        try:
            periods = {
                'short': 30,    # Curto prazo
                'medium': 180,  # Médio prazo  
                'long': 252     # Longo prazo (1 ano útil)
            }
            
            results = {
                'symbol': symbol,
                'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'periods': {},
                'current_data': None
            }
            
            # Buscar dados atuais da ação
            current_stock = YFinanceService.get_stock_data(symbol)
            if current_stock['success']:
                results['current_data'] = current_stock['data']
            
            # Analisar cada período
            for period_name, days in periods.items():
                print(f"Analisando período {period_name} ({days} dias)...")
                
                # Buscar dados do IBOV
                ibov_data = self.get_ibov_data(days)
                if not ibov_data:
                    continue
                    
                # Buscar dados da ação
                stock_data = self.get_stock_data_for_beta(symbol, days)
                if not stock_data:
                    continue
                
                # Calcular Beta
                beta_analysis = self.calculate_beta(
                    stock_data['returns'], 
                    ibov_data['returns']
                )
                
                if beta_analysis:
                    results['periods'][period_name] = {
                        'days': days,
                        'beta': beta_analysis['beta'],
                        'r_squared': beta_analysis['r_squared'],
                        'correlation': beta_analysis['correlation'],
                        'alpha': beta_analysis['alpha'],
                        'stock_volatility': beta_analysis['volatility_stock'],
                        'market_volatility': beta_analysis['volatility_market'],
                        'stock_return': stock_data['period_return'],
                        'market_return': ibov_data['period_return'],
                        'interpretation': self.interpret_beta(beta_analysis['beta']),
                        'chart_data': {
                            'stock_prices': stock_data['prices'][-days:],
                            'market_prices': ibov_data['prices'][-days:],
                            'dates': stock_data['dates'][-days:]
                        }
                    }
            
            return {
                'success': True,
                'data': results
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Erro na análise de {symbol}: {str(e)}'
            }
    
    def interpret_beta(self, beta):
        """Interpretação do valor de Beta"""
        if beta < 0:
            return {
                'classification': 'Negativo',
                'description': 'Move-se inversamente ao mercado',
                'risk_level': 'Defensivo',
                'color': '#3b82f6'  # Azul
            }
        elif beta < 0.5:
            return {
                'classification': 'Muito Baixo',
                'description': 'Muito menos volátil que o mercado',
                'risk_level': 'Conservador',
                'color': '#10b981'  # Verde claro
            }
        elif beta < 1.0:
            return {
                'classification': 'Baixo',
                'description': 'Menos volátil que o mercado',
                'risk_level': 'Moderado',
                'color': '#22c55e'  # Verde
            }
        elif beta == 1.0:
            return {
                'classification': 'Neutro',
                'description': 'Move-se junto com o mercado',
                'risk_level': 'Neutro',
                'color': '#f59e0b'  # Amarelo
            }
        elif beta < 1.5:
            return {
                'classification': 'Alto',
                'description': 'Mais volátil que o mercado',
                'risk_level': 'Agressivo',
                'color': '#f97316'  # Laranja
            }
        else:
            return {
                'classification': 'Muito Alto',
                'description': 'Muito mais volátil que o mercado',
                'risk_level': 'Especulativo',
                'color': '#ef4444'  # Vermelho
            }
    
    def get_popular_stocks_beta(self):
        """Análise de Beta para ações populares brasileiras"""
        popular_stocks = [
            'PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3', 
            'MGLU3', 'B3SA3', 'WEGE3', 'RENT3', 'LREN3'
        ]
        
        results = []
        
        for symbol in popular_stocks:
            analysis = self.analyze_stock_beta(symbol)
            if analysis['success']:
                # Pegar apenas o Beta de longo prazo para comparação
                long_beta = analysis['data']['periods'].get('long', {}).get('beta', 0)
                results.append({
                    'symbol': symbol,
                    'beta': long_beta,
                    'interpretation': self.interpret_beta(long_beta)
                })
        
        # Ordenar por Beta
        results.sort(key=lambda x: x['beta'], reverse=True)
        
        return {
            'success': True,
            'data': results,
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M')
        }

# Função para testar o serviço
if __name__ == "__main__":
    print("🧪 Testando Monitor Service - Análise Beta...")
    
    monitor = MonitorService()
    
    # Teste 1: Análise individual
    print("\n1️⃣ Testando análise Beta PETR4:")
    result = monitor.analyze_stock_beta('PETR4')
    
    if result['success']:
        data = result['data']
        print(f" Análise de {data['symbol']}:")
        
        for period, analysis in data['periods'].items():
            beta = analysis['beta']
            interpretation = analysis['interpretation']
            print(f"   {period.upper()} ({analysis['days']} dias):")
            print(f"     Beta: {beta:.3f} ({interpretation['classification']})")
            print(f"     R²: {analysis['r_squared']:.3f}")
            print(f"     Retorno Ação: {analysis['stock_return']:.2f}%")
            print(f"     Retorno IBOV: {analysis['market_return']:.2f}%")
    else:
        print(f" {result['error']}")
    
    # Teste 2: Ranking de Betas
    print("\n2️⃣ Testando ranking de Betas:")
    ranking = monitor.get_popular_stocks_beta()
    
    if ranking['success']:
        print(" Top ações por Beta (longo prazo):")
        for i, stock in enumerate(ranking['data'][:5], 1):
            print(f"  {i}. {stock['symbol']}: {stock['beta']:.3f} ({stock['interpretation']['classification']})")
    else:
        print(" Erro no ranking")
    
    print("\n🎉 Testes concluídos!")
"""
Serviço de Carrossel com dados do YFinance
Busca dados de múltiplas ações para exibir no carrossel da página inicial
"""

import yfinance as yf
from datetime import datetime
import asyncio
import concurrent.futures
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class CarrosselYFinanceService:
    """Serviço especializado em buscar dados para o carrossel"""
    
    # Tickers principais para o carrossel
    MAIN_TICKERS = [
        'PETR4.SA',   # Petrobras
        'VALE3.SA',   # Vale
        'ITUB4.SA',   # Itaú
        'BBDC4.SA',   # Bradesco
        'ABEV3.SA',   # Ambev
        'MGLU3.SA',   # Magazine Luiza
        'WEGE3.SA',   # WEG
        'B3SA3.SA',   # B3
        'RENT3.SA',   # Localiza
        'LREN3.SA',   # Lojas Renner
        'BOVA11.SA',  # BOVA11 ETF
        'SMAL11.SA'   # Small Caps ETF
    ]
    
    @staticmethod
    def get_stock_data_quick(symbol: str) -> Optional[Dict]:
        """
        Busca dados rápidos de uma ação específica
        Otimizado para velocidade no carrossel
        """
        try:
            # Adicionar .SA se não tiver
            if not symbol.endswith('.SA'):
                symbol += '.SA'
            
            # Buscar dados com período mínimo para velocidade
            stock = yf.Ticker(symbol)
            
            # Buscar histórico de 2 dias para calcular variação
            hist = stock.history(period='2d')
            
            if hist.empty or len(hist) < 1:
                return None
            
            # Dados do último dia
            current_data = hist.iloc[-1]
            current_price = float(current_data['Close'])
            
            # Calcular variação se tiver dados de ontem
            if len(hist) >= 2:
                previous_data = hist.iloc[-2]
                previous_close = float(previous_data['Close'])
                change = current_price - previous_close
                change_percent = (change / previous_close) * 100
            else:
                # Se só tiver um dia, usar open vs close
                open_price = float(current_data['Open'])
                change = current_price - open_price
                change_percent = (change / open_price) * 100 if open_price > 0 else 0
            
            # Buscar informações básicas (cache do yfinance)
            try:
                info = stock.info
                company_name = info.get('longName', symbol.replace('.SA', ''))
            except:
                company_name = symbol.replace('.SA', '')
            
            return {
                'symbol': symbol.replace('.SA', ''),
                'name': company_name,
                'price': round(current_price, 2),
                'change': round(change, 2),
                'change_percent': round(change_percent, 2),
                'volume': int(current_data.get('Volume', 0)),
                'last_update': datetime.now().strftime('%H:%M')
            }
            
        except Exception as e:
            logger.error(f"Erro ao buscar dados de {symbol}: {e}")
            return None
    
    @staticmethod
    def get_multiple_stocks_parallel(symbols: List[str], max_workers: int = 6) -> Dict[str, Dict]:
        """
        Busca dados de múltiplas ações em paralelo
        Otimizado para performance do carrossel
        """
        results = {}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Criar futures para cada símbolo
            future_to_symbol = {
                executor.submit(CarrosselYFinanceService.get_stock_data_quick, symbol): symbol 
                for symbol in symbols
            }
            
            # Coletar resultados conforme completam
            for future in concurrent.futures.as_completed(future_to_symbol, timeout=10):
                symbol = future_to_symbol[future]
                try:
                    data = future.result()
                    if data:
                        results[symbol] = data
                        results[symbol]['status'] = 'success'
                    else:
                        results[symbol] = {
                            'symbol': symbol.replace('.SA', ''),
                            'status': 'error',
                            'error': 'Dados não encontrados'
                        }
                except Exception as e:
                    results[symbol] = {
                        'symbol': symbol.replace('.SA', ''),
                        'status': 'error',
                        'error': str(e)
                    }
        
        return results
    
    @staticmethod
    def get_carrossel_data() -> Dict:
        """
        Função principal para obter dados do carrossel
        Retorna dados formatados e prontos para o frontend
        """
        try:
            logger.info("🎠 Iniciando busca de dados do carrossel...")
            
            # Buscar dados de todas as ações em paralelo
            stocks_data = CarrosselYFinanceService.get_multiple_stocks_parallel(
                CarrosselYFinanceService.MAIN_TICKERS
            )
            
            # Filtrar apenas sucessos e organizar
            successful_stocks = []
            failed_stocks = []
            
            for symbol, data in stocks_data.items():
                if data.get('status') == 'success':
                    successful_stocks.append(data)
                else:
                    failed_stocks.append(data)
            
            # Ordenar por relevância (Petrobras, Vale, Bancos primeiro)
            priority_order = ['PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'BOVA11', 'SMAL11']
            
            def get_priority(stock):
                symbol = stock.get('symbol', '')
                if symbol in priority_order:
                    return priority_order.index(symbol)
                return len(priority_order)
            
            successful_stocks.sort(key=get_priority)
            
            # Estatísticas do mercado
            market_stats = CarrosselYFinanceService.calculate_market_stats(successful_stocks)
            
            logger.info(f" Carrossel: {len(successful_stocks)} ações carregadas, {len(failed_stocks)} falharam")
            
            return {
                'success': True,
                'data': {
                    'stocks': successful_stocks,
                    'market_stats': market_stats,
                    'total_stocks': len(successful_stocks),
                    'failed_count': len(failed_stocks),
                    'last_update': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                    'update_time': datetime.now().strftime('%H:%M')
                }
            }
            
        except Exception as e:
            logger.error(f" Erro no serviço do carrossel: {e}")
            return {
                'success': False,
                'error': str(e),
                'data': {
                    'stocks': [],
                    'market_stats': {'positive': 0, 'negative': 0, 'neutral': 0},
                    'total_stocks': 0,
                    'last_update': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                }
            }
    
    @staticmethod
    def calculate_market_stats(stocks: List[Dict]) -> Dict:
        """
        Calcula estatísticas gerais do mercado baseado nas ações do carrossel
        """
        if not stocks:
            return {'positive': 0, 'negative': 0, 'neutral': 0, 'average_change': 0}
        
        positive = 0
        negative = 0
        neutral = 0
        total_change = 0
        
        for stock in stocks:
            change_percent = stock.get('change_percent', 0)
            total_change += change_percent
            
            if change_percent > 0.1:
                positive += 1
            elif change_percent < -0.1:
                negative += 1
            else:
                neutral += 1
        
        average_change = total_change / len(stocks) if stocks else 0
        
        return {
            'positive': positive,
            'negative': negative,
            'neutral': neutral,
            'total': len(stocks),
            'average_change': round(average_change, 2),
            'positive_percent': round((positive / len(stocks)) * 100, 1) if stocks else 0,
            'negative_percent': round((negative / len(stocks)) * 100, 1) if stocks else 0
        }
    
    @staticmethod
    def get_stock_by_symbol(symbol: str) -> Optional[Dict]:
        """
        Busca dados de uma ação específica (para uso individual)
        """
        return CarrosselYFinanceService.get_stock_data_quick(symbol)

# Função de teste para verificar o serviço
if __name__ == "__main__":
    print("🧪 Testando Carrossel YFinance Service...")
    
    # Teste 1: Uma ação específica
    print("\n1️⃣ Teste: Uma ação específica (PETR4)")
    result = CarrosselYFinanceService.get_stock_by_symbol('PETR4')
    if result:
        print(f" {result['name']} ({result['symbol']})")
        print(f" Preço: R$ {result['price']} ({result['change_percent']:+.2f}%)")
    else:
        print(" Falha ao buscar PETR4")
    
    # Teste 2: Dados completos do carrossel
    print("\n2️⃣ Teste: Dados completos do carrossel")
    carrossel_data = CarrosselYFinanceService.get_carrossel_data()
    
    if carrossel_data['success']:
        data = carrossel_data['data']
        print(f" {data['total_stocks']} ações carregadas")
        print(f" Mercado: {data['market_stats']['positive']} ↗️  {data['market_stats']['negative']} ↘️")
        print(f" Última atualização: {data['last_update']}")
        
        # Mostrar primeiras 3 ações
        print("\n Primeiras ações:")
        for i, stock in enumerate(data['stocks'][:3]):
            status = "" if stock['change_percent'] > 0 else "" if stock['change_percent'] < 0 else "➡️"
            print(f"   {status} {stock['symbol']}: R$ {stock['price']} ({stock['change_percent']:+.2f}%)")
    else:
        print(f" Erro: {carrossel_data['error']}")
    
    print("\n Testes concluídos!")
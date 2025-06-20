import yfinance as yf
from datetime import datetime

class YFinanceService:
    """Serviço para integração com Yahoo Finance"""
    
    @staticmethod
    def get_stock_data(symbol):
        """Buscar dados de uma ação"""
        try:
            # Adicionar .SA para ações brasileiras se não tiver
            if not symbol.endswith('.SA'):
                symbol += '.SA'
            
            # Buscar dados no yfinance
            stock = yf.Ticker(symbol)
            hist = stock.history(period='1d')
            info = stock.info
            
            if hist.empty:
                return {
                    'success': False,
                    'error': f'Ação {symbol} não encontrada'
                }
            
            # Dados básicos
            current_price = hist['Close'].iloc[-1]
            open_price = hist['Open'].iloc[-1]
            high_price = hist['High'].iloc[-1]
            low_price = hist['Low'].iloc[-1]
            volume = int(hist['Volume'].iloc[-1])
            
            # Variação do dia
            change = current_price - open_price
            change_percent = (change / open_price) * 100
            
            return {
                'success': True,
                'data': {
                    'symbol': symbol.replace('.SA', ''),
                    'name': info.get('longName', symbol),
                    'current_price': round(float(current_price), 2),
                    'open_price': round(float(open_price), 2),
                    'high_price': round(float(high_price), 2),
                    'low_price': round(float(low_price), 2),
                    'volume': volume,
                    'change': round(float(change), 2),
                    'change_percent': round(float(change_percent), 2),
                    'currency': info.get('currency', 'BRL'),
                    'market_cap': info.get('marketCap', None),
                    'sector': info.get('sector', 'N/A'),
                    'last_update': datetime.now().strftime('%d/%m/%Y %H:%M')
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Erro ao buscar dados de {symbol}: {str(e)}'
            }
    
    @staticmethod
    def get_multiple_stocks(symbols_list):
        """Buscar dados de múltiplas ações"""
        try:
            results = {}
            
            for symbol in symbols_list:
                try:
                    # Adicionar .SA se necessário
                    yahoo_symbol = symbol if symbol.endswith('.SA') else symbol + '.SA'
                    
                    stock = yf.Ticker(yahoo_symbol)
                    hist = stock.history(period='1d')
                    info = stock.info
                    
                    if not hist.empty:
                        current_price = hist['Close'].iloc[-1]
                        open_price = hist['Open'].iloc[-1]
                        change = current_price - open_price
                        change_percent = (change / open_price) * 100
                        
                        results[symbol] = {
                            'symbol': symbol,
                            'name': info.get('longName', symbol),
                            'current_price': round(float(current_price), 2),
                            'change': round(float(change), 2),
                            'change_percent': round(float(change_percent), 2),
                            'volume': int(hist['Volume'].iloc[-1]),
                            'status': 'success'
                        }
                    else:
                        results[symbol] = {
                            'symbol': symbol,
                            'status': 'not_found',
                            'error': 'Ação não encontrada'
                        }
                        
                except Exception as e:
                    results[symbol] = {
                        'symbol': symbol,
                        'status': 'error',
                        'error': str(e)
                    }
            
            return {
                'success': True,
                'data': results,
                'total_symbols': len(symbols_list),
                'last_update': datetime.now().strftime('%d/%m/%Y %H:%M')
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Erro ao buscar múltiplas ações: {str(e)}'
            }
    
    @staticmethod
    def get_stock_history(symbol, period='1mo'):
        """Buscar histórico de uma ação"""
        try:
            # Adicionar .SA se necessário
            if not symbol.endswith('.SA'):
                symbol += '.SA'
            
            stock = yf.Ticker(symbol)
            hist = stock.history(period=period)
            
            if hist.empty:
                return {
                    'success': False,
                    'error': f'Histórico de {symbol} não encontrado'
                }
            
            # Converter para formato JSON
            history_data = []
            for date, row in hist.iterrows():
                history_data.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'open': round(float(row['Open']), 2),
                    'high': round(float(row['High']), 2),
                    'low': round(float(row['Low']), 2),
                    'close': round(float(row['Close']), 2),
                    'volume': int(row['Volume'])
                })
            
            return {
                'success': True,
                'data': {
                    'symbol': symbol.replace('.SA', ''),
                    'period': period,
                    'history': history_data,
                    'total_days': len(history_data)
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Erro ao buscar histórico de {symbol}: {str(e)}'
            }
    
    @staticmethod
    def search_stocks(query, limit=10):
        """Buscar ações por nome ou símbolo"""
        try:
            # Lista de ações brasileiras populares para busca
            brazilian_stocks = [
                'PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3', 'MGLU3', 'B3SA3',
                'WEGE3', 'RENT3', 'LREN3', 'GGBR4', 'SUZB3', 'RAIL3', 'USIM5',
                'CSNA3', 'CSAN3', 'NTCO3', 'VIVT3', 'TIMP3', 'ELET3', 'CMIG4','BVSP'
            ]
            
            # Filtrar por query
            query = query.upper()
            matches = []
            
            for symbol in brazilian_stocks:
                if query in symbol:
                    try:
                        result = YFinanceService.get_stock_data(symbol)
                        if result['success']:
                            matches.append(result['data'])
                        
                        if len(matches) >= limit:
                            break
                    except:
                        continue
            
            return {
                'success': True,
                'data': matches,
                'query': query,
                'total_found': len(matches)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Erro na busca: {str(e)}'
            }

# Função para testar o serviço
if __name__ == "__main__":
    print("🧪 Testando YFinance Service...")
    
    # Teste 1: Uma ação
    print("\n1️⃣ Testando PETR4:")
    result = YFinanceService.get_stock_data('PETR4')
    if result['success']:
        data = result['data']
        print(f"✅ {data['name']} ({data['symbol']})")
        print(f"💰 Preço: R$ {data['current_price']} ({data['change_percent']:+.2f}%)")
    else:
        print(f"❌ {result['error']}")
    
    # Teste 2: Múltiplas ações
    print("\n2️⃣ Testando múltiplas ações:")
    symbols = ['PETR4', 'VALE3', 'ITUB4']
    result = YFinanceService.get_multiple_stocks(symbols)
    if result['success']:
        for symbol, data in result['data'].items():
            if data['status'] == 'success':
                print(f"✅ {symbol}: R$ {data['current_price']} ({data['change_percent']:+.2f}%)")
            else:
                print(f"❌ {symbol}: {data['error']}")
    else:
        print(f"❌ {result['error']}")
    
    # Teste 3: Histórico
    print("\n3️⃣ Testando histórico VALE3 (5 dias):")
    result = YFinanceService.get_stock_history('VALE3', '5d')
    if result['success']:
        history = result['data']['history']
        print(f"✅ {len(history)} dias de dados")
        print(f"Último dia: {history[-1]['date']} - Close: R$ {history[-1]['close']}")
    else:
        print(f"❌ {result['error']}")
    
    print("\n🎉 Testes concluídos!")
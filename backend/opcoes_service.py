import yfinance as yf
import pandas as pd
import json
from datetime import datetime, timedelta
import re
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

class OpcoesService:
    def __init__(self):
        self.token = None  # Token OpLab se necessário no futuro
    
    def get_ticker_basic_info(self, ticker: str) -> Dict:
        """Obtém informações básicas do ticker via yfinance"""
        try:
            stock = yf.Ticker(f"{ticker}.SA")
            info = stock.info
            hist = stock.history(period="5d")
            
            if hist.empty:
                return None
            
            current_price = float(hist['Close'].iloc[-1])
            prev_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current_price
            change = current_price - prev_close
            change_pct = (change / prev_close * 100) if prev_close != 0 else 0
            
            return {
                'ticker': ticker,
                'name': info.get('longName', ticker),
                'current_price': round(current_price, 2),
                'change': round(change, 2),
                'change_percent': round(change_pct, 2),
                'volume': int(hist['Volume'].iloc[-1]) if 'Volume' in hist.columns else 0,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Erro ao obter info básica de {ticker}: {e}")
            return None
    
    def get_options_data(self, ticker: str) -> Optional[Dict]:
        """Obtém dados de opções via yfinance"""
        try:
            # Tentar com diferentes sufixos
            tickers_to_try = [
                f"{ticker}.SA",  # Padrão brasileiro
                ticker,          # Sem sufixo
                f"{ticker}3.SA", # Para preferencias
                f"{ticker}4.SA"  # Para ON
            ]
            
            options_found = False
            stock = None
            
            for ticker_test in tickers_to_try:
                try:
                    print(f"🔍 Testando ticker: {ticker_test}")
                    stock = yf.Ticker(ticker_test)
                    exp_dates = stock.options
                    
                    if exp_dates and len(exp_dates) > 0:
                        print(f"✅ Opções encontradas para {ticker_test}: {len(exp_dates)} vencimentos")
                        options_found = True
                        break
                    else:
                        print(f"❌ Nenhuma opção para {ticker_test}")
                        
                except Exception as e:
                    print(f"⚠️ Erro ao testar {ticker_test}: {e}")
                    continue
            
            if not options_found or not stock:
                print(f"❌ Nenhuma opção encontrada para {ticker} em nenhum formato")
                return None
            
            # Obter datas de expiração
            exp_dates = stock.options
            print(f"📅 Datas de expiração encontradas: {exp_dates}")
            
            all_options = []
            
            for exp_date in exp_dates[:6]:  # Limitar a 6 vencimentos
                try:
                    print(f"📊 Processando vencimento: {exp_date}")
                    options_chain = stock.option_chain(exp_date)
                    
                    # Processar CALLS
                    calls = options_chain.calls
                    if not calls.empty:
                        calls['category'] = 'CALL'
                        calls['expiration'] = exp_date
                        calls['letra_vencimento'] = self.extract_month_letter(exp_date)
                        all_options.append(calls)
                        print(f"  ✅ {len(calls)} CALLS processadas")
                    
                    # Processar PUTS
                    puts = options_chain.puts
                    if not puts.empty:
                        puts['category'] = 'PUT'
                        puts['expiration'] = exp_date
                        puts['letra_vencimento'] = self.extract_month_letter(exp_date)
                        all_options.append(puts)
                        print(f"  ✅ {len(puts)} PUTS processadas")
                        
                except Exception as e:
                    print(f"⚠️ Erro ao processar expiração {exp_date}: {e}")
                    continue
            
            if not all_options:
                print("❌ Nenhuma opção processada com sucesso")
                return None
            
            # Combinar todos os dados
            combined_options = pd.concat(all_options, ignore_index=True)
            print(f"📊 Total de registros combinados: {len(combined_options)}")
            
            # Converter para formato esperado
            options_list = []
            for _, row in combined_options.iterrows():
                volume = int(row.get('volume', 0)) if pd.notna(row.get('volume')) else 0
                
                # Filtrar apenas opções com volume > 0
                if volume > 0:
                    option_data = {
                        'symbol': row.get('contractSymbol', ''),
                        'strike': float(row.get('strike', 0)),
                        'volume': volume,
                        'category': row.get('category', ''),
                        'expiration': row.get('expiration', ''),
                        'letra_vencimento': row.get('letra_vencimento', ''),
                        'lastPrice': float(row.get('lastPrice', 0)) if pd.notna(row.get('lastPrice')) else 0,
                        'bid': float(row.get('bid', 0)) if pd.notna(row.get('bid')) else 0,
                        'ask': float(row.get('ask', 0)) if pd.notna(row.get('ask')) else 0,
                        'openInterest': int(row.get('openInterest', 0)) if pd.notna(row.get('openInterest')) else 0
                    }
                    options_list.append(option_data)
            
            print(f"✅ {len(options_list)} opções com volume > 0 processadas")
            
            if len(options_list) == 0:
                print("⚠️ Nenhuma opção com volume encontrada")
                return None
                
            return options_list
            
        except Exception as e:
            print(f"❌ Erro geral ao obter dados de opções para {ticker}: {e}")
            return None
    
    def extract_month_letter(self, exp_date: str) -> str:
        """Extrai letra do mês baseada na data de expiração"""
        try:
            # Converter string de data para datetime
            if isinstance(exp_date, str):
                date_obj = datetime.strptime(exp_date, '%Y-%m-%d')
            else:
                date_obj = exp_date
            
            # Mapear mês para letra (padrão brasileiro)
            month_letters = {
                1: 'A', 2: 'B', 3: 'C', 4: 'D', 5: 'E', 6: 'F',
                7: 'G', 8: 'H', 9: 'I', 10: 'J', 11: 'K', 12: 'L'
            }
            
            return month_letters.get(date_obj.month, 'X')
            
        except Exception as e:
            print(f"Erro ao extrair letra do mês: {e}")
            return 'X'
    
    def filter_options_by_letters(self, options_data: List[Dict], letters: List[str]) -> Tuple[List[Dict], List[Dict]]:
        """Filtra opções pelas letras de vencimento"""
        calls_data = []
        puts_data = []
        
        for option in options_data:
            volume = option.get('volume', 0)
            categoria = option.get('category', '').upper()
            strike = option.get('strike', 0)
            letra = option.get('letra_vencimento', '')
            
            # Filtrar por volume > 0, strike > 0 e letra nos grupos especificados
            if volume > 0 and strike > 0 and letra in letters:
                if categoria == 'CALL':
                    calls_data.append(option)
                elif categoria == 'PUT':
                    puts_data.append(option)
        
        return calls_data, puts_data
    
    def prepare_strikes_data(self, calls_data: List[Dict], puts_data: List[Dict]) -> Dict:
        """Prepara dados agrupados por strike"""
        strikes_data = {}
        
        for item in calls_data + puts_data:
            strike = item['strike']
            if strike not in strikes_data:
                strikes_data[strike] = {'calls_volume': 0, 'puts_volume': 0}
            
            if item['category'] == 'CALL':
                strikes_data[strike]['calls_volume'] += item['volume']
            else:
                strikes_data[strike]['puts_volume'] += item['volume']
        
        return strikes_data
    
    def hunter_walls_analysis(self, ticker: str, grupos_vencimentos: List[List[str]]) -> Optional[Dict]:
        """Executa análise Hunter Walls para múltiplos grupos de vencimentos"""
        try:
            # Obter informações básicas do ticker
            ticker_info = self.get_ticker_basic_info(ticker)
            if not ticker_info:
                return None
            
            current_price = ticker_info['current_price']
            
            # Obter dados de opções
            options_data = self.get_options_data(ticker)
            if not options_data:
                return None
            
            # Processar cada grupo de vencimentos
            grupos_processados = {}
            
            for i, grupo in enumerate(grupos_vencimentos):
                nome_grupo = f"Grupo {i+1} ({','.join(grupo)})"
                
                # Filtrar opções para este grupo
                calls_grupo, puts_grupo = self.filter_options_by_letters(options_data, grupo)
                
                if not calls_grupo and not puts_grupo:
                    continue
                
                # Agrupar por strike
                strikes_data = self.prepare_strikes_data(calls_grupo, puts_grupo)
                
                # Filtrar strikes com volume significativo
                volume_threshold = 10  # Ajustado para yfinance
                strikes_filtrados = {k: v for k, v in strikes_data.items() 
                                   if v['calls_volume'] + v['puts_volume'] >= volume_threshold}
                
                if not strikes_filtrados:
                    continue
                
                # Top strikes por volume
                top_strikes = sorted(strikes_filtrados.items(), 
                                   key=lambda x: x[1]['calls_volume'] + x[1]['puts_volume'], 
                                   reverse=True)[:25]
                
                strikes_ordenados = sorted([item[0] for item in top_strikes])
                
                # Calcular estatísticas
                total_calls = sum(item['volume'] for item in calls_grupo)
                total_puts = sum(item['volume'] for item in puts_grupo)
                
                grupos_processados[nome_grupo] = {
                    'strikes': strikes_ordenados,
                    'strikes_data': strikes_data,
                    'calls_data': calls_grupo,
                    'puts_data': puts_grupo,
                    'total_calls': total_calls,
                    'total_puts': total_puts,
                    'num_opcoes': len(calls_grupo) + len(puts_grupo),
                    'grupo_letras': grupo
                }
            
            if not grupos_processados:
                return None
            
            # Preparar dados para frontend
            chart_data = self.prepare_chart_data(grupos_processados, current_price)
            summary_data = self.prepare_summary_data(grupos_processados, ticker_info)
            
            return {
                'ticker_info': ticker_info,
                'grupos': grupos_processados,
                'chart_data': chart_data,
                'summary': summary_data,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Erro na análise Hunter Walls: {e}")
            return None
    
    def prepare_chart_data(self, grupos_processados: Dict, current_price: float) -> Dict:
        """Prepara dados formatados para gráficos"""
        chart_data = {}
        
        for nome_grupo, dados in grupos_processados.items():
            strikes_ordenados = dados['strikes']
            strikes_data = dados['strikes_data']
            
            # Dados para gráfico horizontal
            chart_data[nome_grupo] = {
                'labels': [f"R$ {s:.2f}" for s in strikes_ordenados],
                'calls_volumes': [-strikes_data[s]['calls_volume'] for s in strikes_ordenados],
                'puts_volumes': [strikes_data[s]['puts_volume'] for s in strikes_ordenados],
                'strikes_values': strikes_ordenados,
                'current_price_index': self.find_closest_strike_index(strikes_ordenados, current_price)
            }
        
        return chart_data
    
    def find_closest_strike_index(self, strikes: List[float], price: float) -> int:
        """Encontra o índice do strike mais próximo ao preço atual"""
        if not strikes:
            return 0
        
        diferencias = [abs(s - price) for s in strikes]
        return diferencias.index(min(diferencias))
    
    def prepare_summary_data(self, grupos_processados: Dict, ticker_info: Dict) -> Dict:
        """Prepara dados de resumo"""
        total_calls = sum(dados['total_calls'] for dados in grupos_processados.values())
        total_puts = sum(dados['total_puts'] for dados in grupos_processados.values())
        total_volume = total_calls + total_puts
        
        grupos_summary = []
        for nome_grupo, dados in grupos_processados.items():
            put_call_ratio = dados['total_puts'] / dados['total_calls'] if dados['total_calls'] > 0 else 0
            pct_total = (dados['total_calls'] + dados['total_puts']) / total_volume * 100 if total_volume > 0 else 0
            
            # Top 3 calls e puts
            top_calls = sorted(dados['calls_data'], key=lambda x: x['volume'], reverse=True)[:3]
            top_puts = sorted(dados['puts_data'], key=lambda x: x['volume'], reverse=True)[:3]
            
            grupos_summary.append({
                'nome': nome_grupo,
                'letras': dados['grupo_letras'],
                'total_calls': dados['total_calls'],
                'total_puts': dados['total_puts'],
                'total_volume': dados['total_calls'] + dados['total_puts'],
                'put_call_ratio': round(put_call_ratio, 2),
                'percent_of_total': round(pct_total, 1),
                'num_opcoes': dados['num_opcoes'],
                'top_calls': top_calls,
                'top_puts': top_puts
            })
        
        return {
            'ticker_info': ticker_info,
            'total_calls': total_calls,
            'total_puts': total_puts,
            'total_volume': total_volume,
            'put_call_ratio_geral': round(total_puts / total_calls, 2) if total_calls > 0 else 0,
            'percent_calls': round(total_calls / total_volume * 100, 1) if total_volume > 0 else 0,
            'percent_puts': round(total_puts / total_volume * 100, 1) if total_volume > 0 else 0,
            'grupos': grupos_summary
        }
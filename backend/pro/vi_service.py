import requests
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import plotly.subplots as sp
from datetime import datetime, timedelta
import numpy as np
import json
import os
import warnings
warnings.filterwarnings('ignore')

class VolatilityImpliedService:
    def __init__(self):
        self.token = self._load_token()
        self.base_url = "https://api.oplab.com.br/v3/market/historical/options"
        self.headers = {
            "Access-Token": self.token,
            "Content-Type": "application/json"
        }
        self._cache = {}
        self._cache_timeout = 300

    def _load_token(self):
        token = os.environ.get('OPLAB_TOKEN')
        if token:
            print("✅ Token OpLab carregado da variável de ambiente")
            return token
        
        config_paths = ['config.json', 'backend/config.json', '../config.json']
        
        for config_path in config_paths:
            try:
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    token = config.get('token') or config.get('oplab_token')
                    if token:
                        print(f"✅ Token OpLab carregado de {config_path}")
                        return token
            except Exception as e:
                print(f"⚠️ Erro ao ler {config_path}: {e}")
                continue
        
        default_token = "7gMd+LaFRJ6u6bmjgv9gxeGd5fAc6EHtpM4UoQ41tLivobEa4YTd5dA9xi00s/yd--NJ1uhr4hX+m6KeMsjdVfog==--ZTMyNzIyMjM3OGIxYThmN2YzNzdmZmYzOTZjY2RhYzc="
        return default_token
    
    def get_historical_data(self, ticker, from_date, to_date, symbol=None):
        """Busca dados históricos das opções"""
        url = f"{self.base_url}/{ticker}/{from_date}/{to_date}"
        
        params = {}
        if symbol:
            params['symbol'] = symbol
        
        print(f"🔍 Buscando dados das opções: {ticker} ({from_date} a {to_date})")
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Dados das opções obtidos: {len(data)} registros")
                return data
            else:
                print(f"❌ Erro na API: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Erro na requisição: {e}")
            return None
    
    def get_spot_price(self, ticker, from_date, to_date):
        """Busca preço do ativo via yfinance"""
        try:
            ticker_yf = f"{ticker}.SA" if not ticker.endswith('.SA') else ticker
            
            print(f" Buscando preço do ativo: {ticker_yf}")
            stock = yf.Ticker(ticker_yf)
            hist = stock.history(start=from_date, end=to_date)
            
            if not hist.empty:
                print(f"✅ Preços obtidos: {len(hist)} registros")
                return hist
            else:
                print("❌ Nenhum dado de preço encontrado")
                return None
                
        except Exception as e:
            print(f"❌ Erro ao buscar preços: {e}")
            return None
    
    def process_options_data(self, data):
        """Processa dados das opções com foco em ATM e liquidez"""
        if not data:
            return pd.DataFrame()
        
        print(" Processando dados das opções...")
        df = pd.DataFrame(data)
        
        print(f"Colunas disponíveis: {df.columns.tolist()}")
        
        df['time'] = pd.to_datetime(df['time'])
        df['due_date'] = pd.to_datetime(df['due_date'])
        
        if 'spot' in df.columns:
            spot_sample = df['spot'].iloc[0] if not df.empty else {}
            if isinstance(spot_sample, dict) and spot_sample:
                try:
                    spot_expanded = pd.json_normalize(df['spot'])
                    spot_expanded.columns = [f'spot_{col}' for col in spot_expanded.columns]
                    df = pd.concat([df.drop('spot', axis=1), spot_expanded], axis=1)
                    print(f"Spot expandido: {spot_expanded.columns.tolist()}")
                except Exception as e:
                    print(f"⚠️ Erro ao expandir spot: {e}")
                    df = df.drop('spot', axis=1)
        
        initial_count = len(df)
        
        df = df[df['premium'] > 0]
        
        required_cols = ['premium', 'strike', 'volatility', 'type', 'moneyness']
        for col in required_cols:
            if col in df.columns:
                df = df.dropna(subset=[col])
        
        if 'moneyness' in df.columns:
            df_filtered = df[df['moneyness'].isin(['ATM', 'OTM'])].copy()
            if len(df_filtered) > 0:
                df = df_filtered
                print(f"Filtrado para ATM + OTM: {len(df)} registros")
            else:
                print(f"Mantendo todos os registros: {len(df)}")
        
        print(f"✅ Após filtros: {len(df)} registros (era {initial_count})")
        
        return df
    
    def calculate_historical_volatility(self, price_data, window=30):
        """Calcula volatilidade histórica e sua média"""
        if price_data is None or price_data.empty:
            return pd.Series(), None
        
        print(f" Calculando volatilidade histórica (janela: {window} dias)")
        
        returns = np.log(price_data['Close'] / price_data['Close'].shift(1))
        vol_hist = returns.rolling(window=window).std() * np.sqrt(252) * 100
        vol_hist_mean = vol_hist.tail(126).mean()
        
        return vol_hist, vol_hist_mean
    
    def aggregate_daily_metrics(self, df):
        """Agrega métricas diárias com foco em ATM"""
        if df.empty:
            return pd.DataFrame()
        
        print(" Agregando métricas diárias...")
        
        agg_dict = {}
        
        if 'volatility' in df.columns:
            agg_dict['volatility'] = 'mean'
        if 'premium' in df.columns:
            agg_dict['premium'] = 'mean'
        if 'symbol' in df.columns:
            agg_dict['symbol'] = 'count'
        
        print(f"Agregações a serem aplicadas: {agg_dict}")
        
        daily_agg = df.groupby(['time', 'type']).agg(agg_dict).round(4)
        daily_agg = daily_agg.reset_index()
        
        daily_data = []
        for date in daily_agg['time'].unique():
            date_data = daily_agg[daily_agg['time'] == date]
            
            row = {'date': date}
            
            calls = date_data[date_data['type'] == 'CALL']
            if not calls.empty:
                if 'volatility' in agg_dict:
                    row['iv_call'] = calls['volatility'].iloc[0]
                if 'premium' in agg_dict:
                    row['premium_call'] = calls['premium'].iloc[0]
                if 'symbol' in agg_dict:
                    row['count_call'] = calls['symbol'].iloc[0]
            
            puts = date_data[date_data['type'] == 'PUT']
            if not puts.empty:
                if 'volatility' in agg_dict:
                    row['iv_put'] = puts['volatility'].iloc[0]
                if 'premium' in agg_dict:
                    row['premium_put'] = puts['premium'].iloc[0]
                if 'symbol' in agg_dict:
                    row['count_put'] = puts['symbol'].iloc[0]
            
            if 'iv_call' in row and 'iv_put' in row:
                weight_call = row.get('count_call', 1)
                weight_put = row.get('count_put', 1)
                total_weight = weight_call + weight_put
                
                row['iv_avg'] = (
                    row['iv_call'] * weight_call + 
                    row['iv_put'] * weight_put
                ) / total_weight
            elif 'iv_call' in row:
                row['iv_avg'] = row['iv_call']
            elif 'iv_put' in row:
                row['iv_avg'] = row['iv_put']
            
            daily_data.append(row)
        
        result = pd.DataFrame(daily_data)
        print(f"✅ Métricas diárias agregadas: {len(result)} dias")
        
        if not result.empty:
            print(f"Colunas finais: {result.columns.tolist()}")
        
        return result
    
    def calculate_iv_quartile_signal(self, daily_metrics):
        """Calcula sinal baseado nos quartis da volatilidade implícita"""
        if daily_metrics.empty or 'iv_avg' not in daily_metrics.columns:
            return daily_metrics
        
        print(" Calculando IV Quartile Signal...")
        
        try:
            # Remover valores nulos
            iv_values = daily_metrics['iv_avg'].dropna()
            
            if len(iv_values) < 10:  # Mínimo de dados para calcular quartis
                print("⚠️ Dados insuficientes para calcular quartis")
                daily_metrics['options_signal'] = 0
                return daily_metrics
            
            # Calcular quartis da volatilidade implícita
            q1 = iv_values.quantile(0.25)
            q2 = iv_values.quantile(0.50)  # Mediana
            q3 = iv_values.quantile(0.75)
            
            print(f" Quartis IV: Q1={q1:.1f}%, Q2={q2:.1f}%, Q3={q3:.1f}%")
            
            # Calcular sinal baseado na posição da VI atual nos quartis
            signal_list = []
            
            for i, row in daily_metrics.iterrows():
                iv_current = row.get('iv_avg', np.nan)
                
                if pd.isna(iv_current):
                    signal_list.append(0)
                    continue
                
                # Sinal baseado nos quartis
                if iv_current >= q3:
                    # Q4 - IV muito alta (favorável para vender volatilidade)
                    signal = 75
                elif iv_current >= q2:
                    # Q3 - IV alta
                    signal = 25
                elif iv_current >= q1:
                    # Q2 - IV normal
                    signal = -25
                else:
                    # Q1 - IV baixa (cuidado para vender volatilidade)
                    signal = -75
                
                signal_list.append(signal)
            
            daily_metrics['options_signal'] = signal_list
            
            # Salvar quartis para interpretação
            daily_metrics.attrs['q1'] = q1
            daily_metrics.attrs['q2'] = q2
            daily_metrics.attrs['q3'] = q3
            
            print(f"✅ IV Quartile Signal calculado para {len(signal_list)} registros")
            
            return daily_metrics
            
        except Exception as e:
            print(f"❌ Erro ao calcular IV Quartile Signal: {e}")
            daily_metrics['options_signal'] = 0
            return daily_metrics
    
    def create_analysis(self, ticker, period_days=252):
          
        try:
            to_date = datetime.now()
            from_date = to_date - timedelta(days=period_days + 50)
            
            to_date_str = to_date.strftime('%Y-%m-%d')
            from_date_str = from_date.strftime('%Y-%m-%d')
            
            options_data = self.get_historical_data(ticker, from_date_str, to_date_str)
            if not options_data:
                return {
                    'success': False,
                    'error': 'Não foi possível obter dados das opções'
                }
            
            price_data = self.get_spot_price(ticker, from_date_str, to_date_str)
            if price_data is None:
                return {
                    'success': False,
                    'error': 'Não foi possível obter preços do ativo'
                }
            
            df_options = self.process_options_data(options_data)
            if df_options.empty:
                return {
                    'success': False,
                    'error': 'Não há dados de opções após processamento'
                }
            
            daily_metrics = self.aggregate_daily_metrics(df_options)
            if daily_metrics.empty:
                return {
                    'success': False,
                    'error': 'Não foi possível agregar métricas diárias'
                }
            
            vol_hist, vol_hist_mean = self.calculate_historical_volatility(price_data, window=30)
            
            # Calcular sinal baseado em quartis da VI
            daily_metrics = self.calculate_iv_quartile_signal(daily_metrics)
            
            chart_data = self.prepare_chart_data(price_data, daily_metrics, vol_hist)
            
            current_price = float(price_data['Close'].iloc[-1])
            
            if not daily_metrics.empty and 'options_signal' in daily_metrics.columns:
                last_signal = daily_metrics['options_signal'].iloc[-1]
                current_signal = float(last_signal) if not pd.isna(last_signal) else 0.0
            else:
                current_signal = 0.0
            
            signal_interpretation = self.interpret_signal(current_signal, daily_metrics)
            
            # ===== NOVIDADE: CALCULAR MÉDIAS SEPARADAS CALLS/PUTS =====
            iv_mean = None
            iv_call_mean = None
            iv_put_mean = None
            
            if not daily_metrics.empty:
                # VI geral (média ponderada)
                if 'iv_avg' in daily_metrics.columns:
                    iv_mean_val = daily_metrics['iv_avg'].mean()
                    if not pd.isna(iv_mean_val):
                        iv_mean = float(iv_mean_val)
                
                # VI das Calls
                if 'iv_call' in daily_metrics.columns:
                    call_values = daily_metrics['iv_call'].dropna()
                    if len(call_values) > 0:
                        iv_call_mean = float(call_values.mean())
                        print(f"📞 VI Calls média: {iv_call_mean:.1f}%")
                
                # VI das Puts  
                if 'iv_put' in daily_metrics.columns:
                    put_values = daily_metrics['iv_put'].dropna()
                    if len(put_values) > 0:
                        iv_put_mean = float(put_values.mean())
                        print(f" VI Puts média: {iv_put_mean:.1f}%")
            
            # Análise do sentimento baseada na diferença calls/puts
            sentiment_analysis = self.analyze_calls_puts_sentiment(iv_call_mean, iv_put_mean)
            
            vol_hist_mean_safe = None
            if vol_hist_mean is not None and not pd.isna(vol_hist_mean):
                vol_hist_mean_safe = float(vol_hist_mean)
            
            result = {
                'success': True,
                'ticker': ticker,
                'period_days': period_days,
                'current_price': current_price,
                'current_signal': current_signal,
                'signal_interpretation': signal_interpretation,
                'vol_hist_mean': vol_hist_mean_safe,
                'iv_mean': iv_mean,
                'iv_call_mean': iv_call_mean,      # NOVO!
                'iv_put_mean': iv_put_mean,        # NOVO!
                'sentiment_analysis': sentiment_analysis,  # NOVO!
                'chart_data': chart_data,
                'timestamp': datetime.now().isoformat()
            }
            
            
            print(f" Resumo: VI Calls {iv_call_mean:.1f}% vs VI Puts {iv_put_mean:.1f}%")
            
            return result
            
        except Exception as e:
            print(f"❌ Erro durante análise: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def analyze_calls_puts_sentiment(self, iv_call_mean, iv_put_mean):
        """Análise SIMPLIFICADA focando apenas na relação calls vs puts"""
        if not iv_call_mean or not iv_put_mean:
            return {
                'sentiment': 'unknown',
                'description': 'Dados insuficientes para análise',
                'ratio': None,
                'spread': None
            }
        
        ratio = iv_call_mean / iv_put_mean
        spread = iv_call_mean - iv_put_mean
        
        # LÓGICA SIMPLES: só compara calls vs puts
        if ratio > 1.15:  # Calls 15% mais caras
            sentiment = 'bullish'
            description = f'Calls mais caras - VI {spread:.1f}% maior que puts (otimismo)'
            strategy = 'Oportunidade: Vender calls - estão inflacionadas pelo otimismo'
        elif ratio < 0.85:  # Puts 15% mais caras  
            sentiment = 'bearish'
            description = f'Puts mais caras - VI {abs(spread):.1f}% maior que calls (medo/proteção)'
            strategy = 'Oportunidade: Vender puts - estão inflacionadas pelo medo'
        elif ratio > 1.05:  # Calls ligeiramente mais caras
            sentiment = 'mild_bullish'
            description = f'Calls ligeiramente mais caras - VI {spread:.1f}% maior (leve otimismo)'
            strategy = 'Estratégia: Considerar venda de calls ou estruturas neutras'
        elif ratio < 0.95:  # Puts ligeiramente mais caras
            sentiment = 'mild_bearish' 
            description = f'Puts ligeiramente mais caras - VI {abs(spread):.1f}% maior (leve cautela)'
            strategy = 'Estratégia: Considerar venda de puts ou compra de calls'
        else:
            sentiment = 'neutral'
            description = f'VI equilibrada entre calls e puts - diferença mínima ({abs(spread):.1f}%)'
            strategy = 'Neutro: Aguardar divergência maior para identificar oportunidades'
        
        return {
            'sentiment': sentiment,
            'description': description,
            'strategy': strategy,
            'ratio': round(ratio, 3),
            'spread': round(spread, 2)
        }
    
    def prepare_chart_data(self, price_data, daily_metrics, vol_hist):
        """Prepara dados para gráficos"""
        try:
            chart_data = {}
            
            if price_data is not None and not price_data.empty:
                chart_data['prices'] = {
                    'dates': price_data.index.strftime('%Y-%m-%d').tolist(),
                    'values': [float(x) for x in price_data['Close'].tolist()]
                }
            
            if vol_hist is not None and not vol_hist.empty:
                chart_data['vol_hist'] = {
                    'dates': vol_hist.index.strftime('%Y-%m-%d').tolist(),
                    'values': [float(x) if not pd.isna(x) else 0 for x in vol_hist.tolist()]
                }
            
            if not daily_metrics.empty:
                records = []
                for _, row in daily_metrics.iterrows():
                    record = {}
                    for col in daily_metrics.columns:
                        value = row[col]
                        if pd.isna(value):
                            record[col] = None
                        elif col == 'date':
                            record[col] = value.strftime('%Y-%m-%d') if hasattr(value, 'strftime') else str(value)
                        elif isinstance(value, (int, float)):
                            record[col] = float(value)
                        else:
                            record[col] = str(value)
                    records.append(record)
                chart_data['daily_metrics'] = records
            else:
                chart_data['daily_metrics'] = []
            
            return chart_data
            
        except Exception as e:
            print(f"❌ Erro ao preparar dados do gráfico: {e}")
            import traceback
            traceback.print_exc()
            return {
                'prices': {'dates': [], 'values': []},
                'vol_hist': {'dates': [], 'values': []},
                'daily_metrics': []
            }
    
    def interpret_signal(self, signal, daily_metrics=None):
        """Interpreta o sinal baseado nos quartis da IV"""
        # Informações dos quartis se disponíveis
        quartile_info = ""
        if daily_metrics is not None and hasattr(daily_metrics, 'attrs'):
            q1 = getattr(daily_metrics.attrs, 'q1', None)
            q2 = getattr(daily_metrics.attrs, 'q2', None)
            q3 = getattr(daily_metrics.attrs, 'q3', None)
            
            if q1 and q2 and q3:
                quartile_info = f" (Q1: {q1:.1f}%, Q2: {q2:.1f}%, Q3: {q3:.1f}%)"
        
        if signal >= 60:
            return {
                'status': 'IV MUITO ALTA (Q4)',
                'description': f'Volatilidade implícita no quartil superior{quartile_info} - Excelente para vender volatilidade',
                'recommendation': 'Aproveite para vender volatilidade: venda coberta de opções, venda de opções com garantia em caixa, estratégias com ganho limitado e perda controlada (como condor de ferro).',
                'color': 'green',
                'confidence': 'Muito Alta'
            }
        elif signal >= 20:
            return {
                'status': 'IV ALTA (Q3)',
                'description': f'Volatilidade implícita acima da mediana{quartile_info} - Favorável para vender',
                'recommendation': 'Bom momento para operar vendendo: montar estruturas com opções em que o ganho ocorre se o ativo não variar muito, como spreads de compra ou de venda.',
                'color': 'lightgreen',
                'confidence': 'Alta'
            }
        elif signal >= -20:
            return {
                'status': 'IV NORMAL (Q2)',
                'description': f'Volatilidade implícita próxima da mediana{quartile_info} - Condições neutras',
                'recommendation': 'Mercado neutro: aguarde novas oportunidades ou monte estratégias equilibradas que ganham em faixas de preço.',
                'color': 'gray',
                'confidence': 'Média'
            }
        else:
            return {
                'status': 'IV BAIXA (Q1)',
                'description': f'Volatilidade implícita no quartil inferior{quartile_info} - Cuidado para vender',
                'recommendation': 'Melhor momento para comprar volatilidade: operar esperando grandes movimentos, com estratégias como trava de alta/baixa ou compra de opções dos dois lados (como straddle ou strangle).',
                'color': 'red',
                'confidence': 'Alta'
            }

    def aggregate_daily_metrics(self, df):
        """Agrega métricas diárias com foco em ATM e separação de calls/puts"""
        if df.empty:
            return pd.DataFrame()
        
        print(" Agregando métricas diárias...")
        
        agg_dict = {}
        
        if 'volatility' in df.columns:
            agg_dict['volatility'] = 'mean'
        if 'premium' in df.columns:
            agg_dict['premium'] = 'mean'
        if 'symbol' in df.columns:
            agg_dict['symbol'] = 'count'
        
        print(f"Agregações a serem aplicadas: {agg_dict}")
        
        daily_agg = df.groupby(['time', 'type']).agg(agg_dict).round(4)
        daily_agg = daily_agg.reset_index()
        
        daily_data = []
        for date in daily_agg['time'].unique():
            date_data = daily_agg[daily_agg['time'] == date]
            
            row = {'date': date}
            
            calls = date_data[date_data['type'] == 'CALL']
            if not calls.empty:
                if 'volatility' in agg_dict:
                    row['iv_call'] = calls['volatility'].iloc[0]
                if 'premium' in agg_dict:
                    row['premium_call'] = calls['premium'].iloc[0]
                if 'symbol' in agg_dict:
                    row['count_call'] = calls['symbol'].iloc[0]
            
            puts = date_data[date_data['type'] == 'PUT']
            if not puts.empty:
                if 'volatility' in agg_dict:
                    row['iv_put'] = puts['volatility'].iloc[0]
                if 'premium' in agg_dict:
                    row['premium_put'] = puts['premium'].iloc[0]
                if 'symbol' in agg_dict:
                    row['count_put'] = puts['symbol'].iloc[0]
            
            # Calcular média ponderada para o sinal principal
            if 'iv_call' in row and 'iv_put' in row:
                weight_call = row.get('count_call', 1)
                weight_put = row.get('count_put', 1)
                total_weight = weight_call + weight_put
                
                row['iv_avg'] = (
                    row['iv_call'] * weight_call + 
                    row['iv_put'] * weight_put
                ) / total_weight
            elif 'iv_call' in row:
                row['iv_avg'] = row['iv_call']
            elif 'iv_put' in row:
                row['iv_avg'] = row['iv_put']
            
            daily_data.append(row)
        
        result = pd.DataFrame(daily_data)
        print(f"✅ Métricas diárias agregadas: {len(result)} dias")
        
        if not result.empty:
            print(f"Colunas finais: {result.columns.tolist()}")
        
        return result

# Função standalone para uso direto
def analyze_volatility_implied(ticker, period_days=252):
    """Função standalone para análise de VI"""
    service = VolatilityImpliedService()
    return service.create_analysis(ticker, period_days)

if __name__ == "__main__":
    # Teste rápido
    result = analyze_volatility_implied("PETR4", 252)  # Fixo em 1 ano
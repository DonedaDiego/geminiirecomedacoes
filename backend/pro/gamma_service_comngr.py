# """
# gamma_service.py
# Serviço para análise de Gamma Exposure e identificação de Gamma Walls
# Versão CORRIGIDA e simplificada
# """

# import numpy as np
# import pandas as pd
# import yfinance as yf
# import requests
# from datetime import datetime, timedelta
# import warnings
# import logging
# from scipy.interpolate import UnivariateSpline
# from scipy.ndimage import gaussian_filter1d
# from scipy.signal import find_peaks
# import random

# warnings.filterwarnings('ignore')
# logging.basicConfig(level=logging.INFO)

# def convert_to_json_serializable(obj):
#     """Converte tipos numpy/pandas para tipos Python nativos"""
#     if obj is None:
#         return None
#     elif hasattr(obj, 'item'):  # numpy scalar
#         return obj.item()
#     elif hasattr(obj, 'tolist'):  # numpy array
#         return obj.tolist()
#     elif isinstance(obj, (np.integer, np.int64, np.int32)):
#         return int(obj)
#     elif isinstance(obj, (np.floating, np.float64, np.float32)):
#         return float(obj)
#     elif isinstance(obj, dict):
#         return {key: convert_to_json_serializable(value) for key, value in obj.items()}
#     elif isinstance(obj, list):
#         return [convert_to_json_serializable(item) for item in obj]
#     elif isinstance(obj, tuple):
#         return tuple(convert_to_json_serializable(item) for item in obj)
#     elif pd.isna(obj):  # Pandas NaN
#         return None
#     else:
#         return obj
    
# class GammaExposureAnalyzer:
#     """Analisador de Exposição Gamma SIMPLIFICADO"""
    
#     def __init__(self):
#         self.token = "jeOTw9JanmDhlxReKlF2QwHM4Q3mNVlU3SpNENZUNIxTk24drRqdordyijyeNlfZ--bbybBgsEprbusre2drjwfA==--M2M3ZGFiNDk5ZTRhNzU3M2MxNWE3ZmJkMjcwZjQyNGE="
#         self.base_url = "https://api.oplab.com.br/v3/market/historical/options"
#         self.headers = {
#             "Access-Token": self.token,
#             "Content-Type": "application/json"
#         }
    
#     def get_options_data(self, ticker, days_back=60):
#         """Busca dados de opções usando a API OpLab"""
#         try:
#             ticker_clean = ticker.replace('.SA', '').upper()
            
#             to_date = datetime.now().strftime('%Y-%m-%d')
#             from_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
            
#             url = f"{self.base_url}/{ticker_clean}/{from_date}/{to_date}"
            
#             response = requests.get(url, headers=self.headers, timeout=30)
            
#             if response.status_code == 200:
#                 data = response.json()
#                 logging.info(f"✅ Dados obtidos: {len(data)} registros para {ticker_clean}")
#                 return data
#             else:
#                 logging.warning(f"❌ Erro na API OpLab: {response.status_code}")
#                 return None
                
#         except Exception as e:
#             logging.error(f"❌ Erro na requisição: {e}")
#             return None
    
#     def get_current_spot_price(self, ticker):
#         """Obtém preço atual via Yahoo Finance"""
#         try:
#             if not ticker.endswith('.SA'):
#                 ticker_yf = f"{ticker}.SA"
#             else:
#                 ticker_yf = ticker
                
#             stock = yf.Ticker(ticker_yf)
#             hist = stock.history(period='1d')
            
#             if not hist.empty:
#                 current_price = float(hist['Close'].iloc[-1])
#                 logging.info(f"✅ Preço atual {ticker}: R$ {current_price:.2f}")
#                 return current_price
                
#         except Exception as e:
#             logging.error(f"❌ Erro ao obter preço: {e}")
            
#         return None
    
#     def process_options_data(self, data, spot_price):
#         """Processa dados de opções"""
#         if not data:
#             return pd.DataFrame()
        
#         df = pd.DataFrame(data)
        
#         # Validações básicas
#         required_cols = ['time', 'type', 'strike', 'days_to_maturity']
#         if not all(col in df.columns for col in required_cols):
#             logging.error("❌ Colunas necessárias não encontradas")
#             return pd.DataFrame()
        
#         # Filtrar dados mais recentes
#         if 'time' in df.columns:
#             df['time'] = pd.to_datetime(df['time'])
#             recent_date = df['time'].max() - timedelta(days=3)
#             df = df[df['time'] >= recent_date]
        
#         # Filtros de qualidade
#         df = df[
#             (df['days_to_maturity'] > 1) & 
#             (df['days_to_maturity'] < 365) &
#             (df['strike'] > spot_price * 0.8) & 
#             (df['strike'] < spot_price * 1.2)
#         ]
        
#         if df.empty:
#             logging.warning("⚠️ Nenhuma opção válida após filtros")
#             return pd.DataFrame()
        
#         # Garantir valores válidos - CORRIGIDO
#         df['spot_price'] = float(spot_price)
        
#         # Corrigir volume
#         if 'volume' not in df.columns:
#             df['volume'] = 100
#         else:
#             df['volume'] = df['volume'].fillna(100)  # fillna() no Series, não no resultado do get()
        
#         # Corrigir gamma
#         if 'gamma' not in df.columns:
#             df['gamma'] = 0.0
#         else:
#             df['gamma'] = df['gamma'].fillna(0.0)
        
#         logging.info(f"✅ Processadas {len(df)} opções válidas")
#         return df
    
#     def calculate_gamma_exposure(self, df):
#         """Calcula exposição gamma CORRIGIDA"""
#         if df.empty:
#             return df
        
#         logging.info(f"🔄 Calculando gamma para {len(df)} opções")
        
#         for idx, row in df.iterrows():
#             gamma = float(row.get('gamma', 0))
#             volume = float(row.get('volume', 100))
#             option_type = str(row.get('type', 'CALL')).upper()
            
#             # Usar volume diretamente sem multiplicação excessiva
#             open_interest_proxy = volume
            
#             # ===== FÓRMULA SIMPLIFICADA =====
#             # Gamma Exposure = Gamma × Open Interest (sem multiplicadores)
#             gamma_exposure = gamma * open_interest_proxy
            
#             # Perspective dos Market Makers (inverta o sinal)
#             # MMs vendem opções, então têm gamma negativo
#             dealer_gamma = -gamma_exposure * 0.8  # 80% dos MMs short
            
#             df.loc[idx, 'dealer_gamma_exposure'] = float(dealer_gamma)
#             df.loc[idx, 'gamma_exposure_abs'] = float(abs(gamma_exposure))
        
#         total_nge = df['dealer_gamma_exposure'].sum()
#         logging.info(f"📊 NGE Total calculado: {total_nge:.2f}")
        
#         return df
    
#     def calculate_gamma_levels_by_strike(self, df):
#         """Calcula níveis de gamma por strike"""
#         if df.empty:
#             return pd.DataFrame()
        
#         # Agrupar por strikes próximos (buckets de R$ 0.50)
#         df['strike_bucket'] = (df['strike'] / 0.5).round() * 0.5
        
#         gamma_by_strike = df.groupby('strike_bucket').agg({
#             'dealer_gamma_exposure': 'sum',
#             'gamma_exposure_abs': 'sum',
#             'volume': 'sum',
#             'strike': 'mean'
#         }).reset_index()
        
#         gamma_by_strike = gamma_by_strike.rename(columns={
#             'dealer_gamma_exposure': 'net_gamma'
#         })
        
#         gamma_by_strike = gamma_by_strike.sort_values('strike')
        
#         # Remover zeros
#         gamma_by_strike = gamma_by_strike[gamma_by_strike['net_gamma'].abs() > 0.001]
        
#         logging.info(f"📈 Calculados {len(gamma_by_strike)} níveis de gamma")
#         return gamma_by_strike[['strike', 'net_gamma']].reset_index(drop=True)
    
#     def identify_gamma_walls(self, gamma_levels, spot_price):
#         """Identifica gamma walls próximos ao preço atual"""
#         if gamma_levels.empty:
#             return []
        
#         # Região próxima ao spot (15% para cada lado)
#         price_range = spot_price * 0.15
#         nearby = gamma_levels[
#             (gamma_levels['strike'] >= spot_price - price_range) &
#             (gamma_levels['strike'] <= spot_price + price_range)
#         ].copy()
        
#         if len(nearby) < 5:
#             return []
        
#         # Calcular intensidade relativa
#         max_abs_gamma = nearby['net_gamma'].abs().max()
#         if max_abs_gamma > 0:
#             nearby['intensity'] = nearby['net_gamma'].abs() / max_abs_gamma
#         else:
#             return []
        
#         walls = []
        
#         try:
#             gamma_values = nearby['net_gamma'].values
#             min_distance = max(2, len(nearby) // 8)
#             min_height = max_abs_gamma * 0.3
            
#             # Encontrar picos positivos e negativos
#             pos_peaks, _ = find_peaks(gamma_values, height=min_height, distance=min_distance)
#             neg_peaks, _ = find_peaks(-gamma_values, height=min_height, distance=min_distance)
            
#             # Processar picos positivos (Support Walls)
#             for peak_idx in pos_peaks:
#                 if peak_idx < len(nearby):
#                     row = nearby.iloc[peak_idx]
#                     walls.append({
#                         'strike': float(row['strike']),  # SEM arredondamento
#                         'gamma': float(row['net_gamma']),  # SEM arredondamento  
#                         'intensity': float(row['intensity']),  # SEM arredondamento
#                         'type': 'Support',
#                         'distance_pct': float(abs(row['strike'] - spot_price) / spot_price * 100)  # SEM arredondamento
#                     })
            
#             # Processar picos negativos (Resistance Walls)
#             for peak_idx in neg_peaks:
#                 if peak_idx < len(nearby):
#                     row = nearby.iloc[peak_idx]
#                     walls.append({
#                         'strike': float(row['strike']),  # SEM arredondamento
#                         'gamma': float(row['net_gamma']),  # SEM arredondamento
#                         'intensity': float(row['intensity']),  # SEM arredondamento
#                         'type': 'Resistance',
#                         'distance_pct': float(abs(row['strike'] - spot_price) / spot_price * 100)  # SEM arredondamento
#                     })
                    
#         except Exception as e:
#             logging.warning(f"Detecção de picos falhou: {e}")
            
#             # Fallback: usar threshold simples
#             threshold = nearby['intensity'].quantile(0.7)
#             significant = nearby[nearby['intensity'] >= threshold]
            
#             for idx, row in significant.iterrows():
#                 wall_type = "Support" if row['net_gamma'] > 0 else "Resistance"
#                 walls.append({
#                     'strike': float(row['strike']),  # SEM arredondamento
#                     'gamma': float(row['net_gamma']),  # SEM arredondamento
#                     'intensity': float(row['intensity']),  # SEM arredondamento
#                     'type': wall_type,
#                     'distance_pct': float(abs(row['strike'] - spot_price) / spot_price * 100)  # SEM arredondamento
#                 })
        
#         # Ordenar por intensidade e limitar resultados
#         walls.sort(key=lambda x: x['intensity'], reverse=True)
#         return walls[:6]
    
#     def calculate_metrics(self, df, gamma_levels, spot_price):
#         """Calcula métricas principais"""
#         if df.empty:
#             return {}
        
#         metrics = {}
        
#         # Net Gamma Exposure total
#         nge = df['dealer_gamma_exposure'].sum()
#         metrics['net_gamma_exposure'] = float(nge)
        
#         # Determinar regime
#         if nge > 0:
#             metrics['gamma_regime'] = 'Long Gamma'
#             metrics['volatility_expectation'] = 'Low'
#             metrics['market_behavior'] = 'Mean Reverting'
#         else:
#             metrics['gamma_regime'] = 'Short Gamma'
#             metrics['volatility_expectation'] = 'High'
#             metrics['market_behavior'] = 'Momentum'
        
#         # Estatísticas calls/puts
#         calls = df[df['type'].str.upper() == 'CALL']
#         puts = df[df['type'].str.upper() == 'PUT']
        
#         metrics['total_calls'] = int(len(calls))
#         metrics['total_puts'] = int(len(puts))
#         metrics['call_put_ratio'] = float(len(calls) / max(len(puts), 1))
        
#         # Volumes
#         metrics['total_volume'] = int(df['volume'].sum())
#         metrics['call_volume'] = int(calls['volume'].sum() if not calls.empty else 0)
#         metrics['put_volume'] = int(puts['volume'].sum() if not puts.empty else 0)
        
#         # Gamma skew
#         call_gamma = calls['dealer_gamma_exposure'].sum() if not calls.empty else 0
#         put_gamma = puts['dealer_gamma_exposure'].sum() if not puts.empty else 0
#         total_abs = abs(call_gamma) + abs(put_gamma)
        
#         if total_abs > 0:
#             metrics['gamma_skew'] = float((call_gamma - put_gamma) / total_abs)
#         else:
#             metrics['gamma_skew'] = 0.0
        
#         logging.info(f"📊 Métricas calculadas - NGE: {nge:.2f}, Regime: {metrics['gamma_regime']}")
#         return metrics
    
#     def get_plot_data(self, gamma_levels, spot_price, ticker):
#         """Prepara dados para o gráfico frontend"""
#         if gamma_levels.empty:
#             return None
        
#         currency = "R$" if ".SA" in ticker else "$"
#         ticker_display = ticker.replace('.SA', '')
        
#         plot_data = {
#             'ticker': ticker_display,
#             'currency': currency,
#             'spot_price': float(spot_price),
#             'strikes': [float(x) for x in gamma_levels['strike'].tolist()],  # SEM .round(2)
#             'net_gamma': [float(x) for x in gamma_levels['net_gamma'].tolist()]  # SEM .round(6)
#         }
        
#         return plot_data

# class NGEOscillator:
#     """Termômetro de Pressão NGE SIMPLIFICADO"""
    
#     def calculate_nge_pressure(self, current_nge):
#         """Calcula pressão NGE baseada no valor atual (simulação)"""
#         try:
#             # Simular range histórico baseado no NGE atual
#             if current_nge == 0:
#                 return {
#                     'pressure_score': 50.0,
#                     'nge_current': 0.0,
#                     'nge_min': -1000.0,
#                     'nge_max': 1000.0,
#                     'nge_avg': 0.0,
#                     'historical_count': 252
#                 }
            
#             # Criar range simulado
#             magnitude = abs(current_nge)
#             nge_min = -magnitude * 3  # Mais negativo = mais pressão
#             nge_max = magnitude * 2   # Menos negativo = menos pressão
#             nge_avg = (nge_min + nge_max) / 2
            
#             # Normalizar (0-100)
#             if nge_max != nge_min:
#                 normalized = ((current_nge - nge_min) / (nge_max - nge_min)) * 100
#                 pressure_score = 100 - normalized  # Inverter
#             else:
#                 pressure_score = 50
            
#             pressure_score = max(0, min(100, pressure_score))
            
#             return {
#                 'pressure_score': float(pressure_score),
#                 'nge_current': float(current_nge),
#                 'nge_min': float(nge_min),
#                 'nge_max': float(nge_max),
#                 'nge_avg': float(nge_avg),
#                 'historical_count': 252
#             }
            
#         except Exception as e:
#             logging.error(f"❌ Erro no cálculo NGE pressure: {e}")
#             return None
    
#     def get_pressure_interpretation(self, pressure_score):
#         """Interpreta o score de pressão"""
#         if pressure_score is None:
#             return {
#                 'level': 'INDISPONÍVEL',
#                 'description': 'Dados insuficientes',
#                 'color': 'gray',
#                 'emoji': '⚪',
#                 'barrier_strength': 'Desconhecida'
#             }
        
#         if pressure_score <= 20:
#             return {
#                 'level': 'MUITO BAIXA',
#                 'description': 'Barreiras fracas - Movimentos livres',
#                 'color': 'green',
#                 'emoji': '🟢',
#                 'barrier_strength': 'Papel'
#             }
#         elif pressure_score <= 40:
#             return {
#                 'level': 'BAIXA', 
#                 'description': 'Resistência leve - Breakouts prováveis',
#                 'color': 'lightgreen',
#                 'emoji': '🟡',
#                 'barrier_strength': 'Leve'
#             }
#         elif pressure_score <= 60:
#             return {
#                 'level': 'MODERADA',
#                 'description': 'Barreiras normais - Volume necessário',
#                 'color': 'yellow',
#                 'emoji': '🟠',
#                 'barrier_strength': 'Normal'
#             }
#         elif pressure_score <= 80:
#             return {
#                 'level': 'ALTA',
#                 'description': 'Resistência forte - Reversões prováveis',
#                 'color': 'orange',
#                 'emoji': '🔴',
#                 'barrier_strength': 'Forte'
#             }
#         else:
#             return {
#                 'level': 'EXTREMA',
#                 'description': 'Barreiras rígidas - Muro de concreto',
#                 'color': 'red',
#                 'emoji': '🔥',
#                 'barrier_strength': 'Concreto'
#             }
    
#     def calculate_wall_strength(self, wall_intensity, pressure_score):
#         """Calcula força ajustada da wall"""
#         if pressure_score is None or wall_intensity is None:
#             return wall_intensity
        
#         strength_factor = pressure_score / 100
#         wall_strength = wall_intensity * strength_factor
        
#         return min(1.0, max(0.0, wall_strength))

# class GammaService:
#     """Serviço principal SIMPLIFICADO"""
    
#     def __init__(self):
#         self.analyzer = GammaExposureAnalyzer()
    
#     def analyze_gamma_complete(self, ticker, days_back=60):
#         """Análise completa SIMPLIFICADA"""
#         try:
#             logging.info(f"🚀 Iniciando análise para {ticker}")
            
#             # 1. Preço atual
#             spot_price = self.analyzer.get_current_spot_price(ticker)
#             if not spot_price:
#                 raise ValueError(f"Preço não encontrado para {ticker}")
            
#             # 2. Dados de opções
#             options_data = self.analyzer.get_options_data(ticker, days_back)
#             if not options_data:
#                 raise ValueError(f"Dados de opções indisponíveis para {ticker}")
            
#             # 3. Processar
#             df = self.analyzer.process_options_data(options_data, spot_price)
#             if df.empty:
#                 raise ValueError("Nenhuma opção válida")
            
#             # 4. Calcular gamma
#             df = self.analyzer.calculate_gamma_exposure(df)
            
#             # 5. Níveis por strike
#             gamma_levels = self.analyzer.calculate_gamma_levels_by_strike(df)
#             if gamma_levels.empty:
#                 raise ValueError("Níveis de gamma não calculados")
            
#             # 6. Identificar walls
#             walls = self.analyzer.identify_gamma_walls(gamma_levels, spot_price)
            
#             # 7. Métricas
#             metrics = self.analyzer.calculate_metrics(df, gamma_levels, spot_price)
            
#             # 8. Plot data
#             plot_data = self.analyzer.get_plot_data(gamma_levels, spot_price, ticker)
            
#             # 9. NGE Oscillator
#             current_nge = metrics.get('net_gamma_exposure', 0)
#             oscillator = NGEOscillator()
            
#             nge_pressure_data = oscillator.calculate_nge_pressure(current_nge)
            
#             if nge_pressure_data:
#                 pressure_score = nge_pressure_data['pressure_score']
#                 pressure_interpretation = oscillator.get_pressure_interpretation(pressure_score)
                
#                 # Ajustar walls
#                 for wall in walls:
#                     original_intensity = wall.get('intensity', 0)
#                     adjusted_strength = oscillator.calculate_wall_strength(original_intensity, pressure_score)
#                     wall['adjusted_strength'] = adjusted_strength
#                     wall['strength_factor'] = pressure_score / 100
#             else:
#                 pressure_interpretation = oscillator.get_pressure_interpretation(None)
            
#             # Resultado final
#             result = {
#                 'ticker': str(ticker.replace('.SA', '')),
#                 'spot_price': float(spot_price),
#                 'metrics': convert_to_json_serializable(metrics),
#                 'walls': convert_to_json_serializable(walls),
#                 'plot_data': convert_to_json_serializable(plot_data),
#                 'options_count': int(len(df)),
#                 'nge_oscillator': convert_to_json_serializable({
#                     'pressure_score': pressure_score if nge_pressure_data else None,
#                     'pressure_interpretation': pressure_interpretation,
#                     'historical_data': nge_pressure_data
#                 }),
#                 'success': True
#             }
            
#             logging.info("✅ Análise concluída com sucesso")
#             return result
            
#         except Exception as e:
#             logging.error(f"❌ Erro na análise: {e}")
#             raise
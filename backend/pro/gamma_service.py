"""
gamma_service.py
Serviço para análise de Gamma Exposure e identificação de Gamma Walls
Versão otimizada baseada no código original
"""

import numpy as np
import pandas as pd
import yfinance as yf
import requests
from datetime import datetime, timedelta
import warnings
import logging
from scipy.interpolate import UnivariateSpline
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)

def convert_to_json_serializable(obj):
    """Converte tipos numpy/pandas para tipos Python nativos"""
    if hasattr(obj, 'item'):  # numpy scalar
        return obj.item()
    elif hasattr(obj, 'tolist'):  # numpy array
        return obj.tolist()
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, dict):
        return {key: convert_to_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_json_serializable(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_to_json_serializable(item) for item in obj)
    else:
        return obj

class GammaExposureAnalyzer:
    """Analisador de Exposição Gamma otimizado"""
    
    def __init__(self):
        self.token = "jeOTw9JanmDhlxReKlF2QwHM4Q3mNVlU3SpNENZUNIxTk24drRqdordyijyeNlfZ--bbybBgsEprbusre2drjwfA==--M2M3ZGFiNDk5ZTRhNzU3M2MxNWE3ZmJkMjcwZjQyNGE="
        self.base_url = "https://api.oplab.com.br/v3/market/historical/options"
        self.headers = {
            "Access-Token": self.token,
            "Content-Type": "application/json"
        }
        
        self.colors = {
            'background': '#0f0f0f',
            'paper': '#1a1a1a',
            'text': '#ffffff',
            'grid': '#333333',
            'positive_gamma': '#00ff88',
            'negative_gamma': '#ff4757',
            'spot_line': '#ffd700',
            'zero_line': '#666666',
            'wall_strong': '#8b5cf6',
            'wall_medium': '#06b6d4'
        }
    
    def get_options_data(self, ticker, days_back=60):
        """Busca dados de opções usando a API OpLab"""
        try:
            # Limpar ticker
            ticker_clean = ticker.replace('.SA', '').upper()
            
            to_date = datetime.now().strftime('%Y-%m-%d')
            from_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
            
            url = f"{self.base_url}/{ticker_clean}/{from_date}/{to_date}"
            
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                logging.info(f"Dados obtidos: {len(data)} registros de opções para {ticker_clean}")
                return data
            else:
                logging.warning(f"Erro na API OpLab: {response.status_code}")
                return None
                
        except Exception as e:
            logging.error(f"Erro na requisição: {e}")
            return None
    
    def get_current_spot_price(self, ticker):
        """Obtém preço atual via Yahoo Finance"""
        try:
            # Normalizar ticker para Yahoo Finance
            if not ticker.endswith('.SA') and not ticker.startswith('^'):
                ticker_yf = f"{ticker}.SA"
            else:
                ticker_yf = ticker
                
            stock = yf.Ticker(ticker_yf)
            hist = stock.history(period='1d')
            
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
                logging.info(f"Preço atual {ticker}: R$ {current_price:.2f}")
                return current_price
                
        except Exception as e:
            logging.error(f"Erro ao obter preço: {e}")
            
        return None
    
    def process_options_data(self, data, spot_price):
        """Processa dados de opções e calcula exposição gamma"""
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        
        # Validações básicas
        required_cols = ['time', 'type', 'strike', 'days_to_maturity']
        if not all(col in df.columns for col in required_cols):
            logging.error("Colunas necessárias não encontradas")
            return pd.DataFrame()
        
        # Filtrar dados mais recentes
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])
            recent_date = df['time'].max() - timedelta(days=2)
            df = df[df['time'] >= recent_date]
        
        # Filtros de qualidade
        df = df[
            (df['days_to_maturity'] > 1) & 
            (df['days_to_maturity'] < 365) &
            (df['strike'] > spot_price * 0.7) & 
            (df['strike'] < spot_price * 1.3)
        ]
        
        if df.empty:
            logging.warning("Nenhuma opção válida após filtros")
            return pd.DataFrame()
        
        # Adicionar preço spot
        df['spot_price'] = spot_price
        
        # Usar volume como proxy para open interest se não disponível
        if 'volume' not in df.columns:
            df['volume'] = 100
        df['volume'] = df['volume'].fillna(100)
        
        logging.info(f"Processadas {len(df)} opções válidas")
        return df
    
    def calculate_gamma_exposure(self, df):
        """Calcula exposição gamma usando dados da API"""
        if df.empty:
            return df
        
        for idx, row in df.iterrows():
            spot = row['spot_price']
            strike = row['strike']
            gamma = row.get('gamma', 0)  # Gamma já vem da API
            volume = row.get('volume', 100)
            option_type = row.get('type', 'CALL').upper()
            moneyness_api = row.get('moneyness', 'ATM')
            
            # Usar volume como proxy para open interest
            oi_proxy = volume * 2
            
            # Fórmula: Gamma Exposure = Gamma * "Open Interest" * Spot² * 0.01
            gamma_exposure = gamma * oi_proxy * spot * spot * 0.0001
            
            # Lógica de Market Maker baseada na moneyness
            if moneyness_api == 'OTM':
                mm_short_prob = 0.9
            elif moneyness_api == 'ATM':
                mm_short_prob = 0.85
            else:  # ITM
                mm_short_prob = 0.7
            
            # Direção do gamma (perspectiva dos MMs)
            dealer_gamma = -gamma_exposure * mm_short_prob + gamma_exposure * (1 - mm_short_prob)
            
            df.loc[idx, 'dealer_gamma_exposure'] = dealer_gamma
            df.loc[idx, 'gamma_exposure_abs'] = abs(gamma_exposure)
            df.loc[idx, 'mm_short_probability'] = mm_short_prob
        
        return df
    
    def calculate_gamma_levels_by_strike(self, df):
        """Calcula níveis de gamma por strike com suavização"""
        if df.empty:
            return pd.DataFrame()
        
        # Agrupar por faixas de strike (clustering)
        df['strike_bucket'] = (df['strike'] / 0.5).round() * 0.5
        
        gamma_by_strike = df.groupby('strike_bucket').agg({
            'dealer_gamma_exposure': 'sum',
            'gamma_exposure_abs': 'sum',
            'volume': 'sum',
            'strike': 'mean'
        }).reset_index()
        
        gamma_by_strike = gamma_by_strike.rename(columns={
            'dealer_gamma_exposure': 'net_gamma'
        })
        
        gamma_by_strike = gamma_by_strike.sort_values('strike')
        
        # Suavização avançada se temos dados suficientes
        if len(gamma_by_strike) >= 8:
            try:
                strikes = gamma_by_strike['strike'].values
                net_gammas = gamma_by_strike['net_gamma'].values
                
                strike_range = np.linspace(strikes.min(), strikes.max(), 
                                         min(150, len(strikes) * 3))
                
                spline = UnivariateSpline(strikes, net_gammas, s=len(strikes) * 0.1)
                gamma_smooth = spline(strike_range)
                gamma_smooth = gaussian_filter1d(gamma_smooth, sigma=0.8)
                
                return pd.DataFrame({
                    'strike': strike_range,
                    'net_gamma': gamma_smooth
                })
                
            except Exception as e:
                logging.warning(f"Suavização falhou: {e}")
        
        return gamma_by_strike[['strike', 'net_gamma']]
    
    def identify_gamma_walls(self, gamma_levels, spot_price):
        """Identifica gamma walls próximos ao preço atual"""
        if gamma_levels.empty:
            return []
        
        # Região próxima ao spot (15% para cada lado)
        price_range = spot_price * 0.15
        nearby = gamma_levels[
            (gamma_levels['strike'] >= spot_price - price_range) &
            (gamma_levels['strike'] <= spot_price + price_range)
        ].copy()
        
        if len(nearby) < 5:
            return []
        
        # Calcular intensidade relativa
        max_abs_gamma = nearby['net_gamma'].abs().max()
        if max_abs_gamma > 0:
            nearby['intensity'] = nearby['net_gamma'].abs() / max_abs_gamma
        else:
            return []
        
        walls = []
        
        try:
            gamma_values = nearby['net_gamma'].values
            min_distance = max(2, len(nearby) // 8)
            min_height = max_abs_gamma * 0.3
            
            # Encontrar picos positivos e negativos
            pos_peaks, _ = find_peaks(gamma_values, height=min_height, distance=min_distance)
            neg_peaks, _ = find_peaks(-gamma_values, height=min_height, distance=min_distance)
            
            # Processar picos positivos (Support Walls)
            for peak_idx in pos_peaks:
                if peak_idx < len(nearby):
                    row = nearby.iloc[peak_idx]
                    walls.append({
                        'strike': row['strike'],
                        'gamma': row['net_gamma'],
                        'intensity': row['intensity'],
                        'type': 'Support',
                        'distance_pct': abs(row['strike'] - spot_price) / spot_price * 100
                    })
            
            # Processar picos negativos (Resistance Walls)
            for peak_idx in neg_peaks:
                if peak_idx < len(nearby):
                    row = nearby.iloc[peak_idx]
                    walls.append({
                        'strike': row['strike'],
                        'gamma': row['net_gamma'],
                        'intensity': row['intensity'],
                        'type': 'Resistance',
                        'distance_pct': abs(row['strike'] - spot_price) / spot_price * 100
                    })
                    
        except Exception as e:
            logging.warning(f"Detecção de picos falhou: {e}")
            
            # Fallback: usar threshold simples
            threshold = nearby['intensity'].quantile(0.7)
            significant = nearby[nearby['intensity'] >= threshold]
            
            for idx, row in significant.iterrows():
                wall_type = "Support" if row['net_gamma'] > 0 else "Resistance"
                walls.append({
                    'strike': row['strike'],
                    'gamma': row['net_gamma'],
                    'intensity': row['intensity'],
                    'type': wall_type,
                    'distance_pct': abs(row['strike'] - spot_price) / spot_price * 100
                })
        
        # Ordenar por intensidade e limitar resultados
        walls.sort(key=lambda x: x['intensity'], reverse=True)
        return walls[:6]
    
    def calculate_metrics(self, df, gamma_levels, spot_price):
        """Calcula métricas principais do gamma"""
        if df.empty:
            return {}
        
        metrics = {}
        
        # Net Gamma Exposure total
        metrics['net_gamma_exposure'] = gamma_levels['net_gamma'].sum()
        
        # Determinar regime de gamma
        if metrics['net_gamma_exposure'] > 0:
            metrics['gamma_regime'] = 'Long Gamma'
            metrics['volatility_expectation'] = 'Low'
            metrics['market_behavior'] = 'Mean Reverting'
        else:
            metrics['gamma_regime'] = 'Short Gamma'
            metrics['volatility_expectation'] = 'High'
            metrics['market_behavior'] = 'Momentum'
        
        # Estatísticas de calls e puts
        calls = df[df['type'].str.upper() == 'CALL']
        puts = df[df['type'].str.upper() == 'PUT']
        
        metrics['total_calls'] = len(calls)
        metrics['total_puts'] = len(puts)
        metrics['call_put_ratio'] = len(calls) / max(len(puts), 1)
        
        # Volume total
        metrics['total_volume'] = df['volume'].sum()
        metrics['call_volume'] = calls['volume'].sum() if not calls.empty else 0
        metrics['put_volume'] = puts['volume'].sum() if not puts.empty else 0
        
        # Gamma skew (viés)
        call_gamma = calls['dealer_gamma_exposure'].sum() if not calls.empty else 0
        put_gamma = puts['dealer_gamma_exposure'].sum() if not puts.empty else 0
        total_abs = abs(call_gamma) + abs(put_gamma)
        
        if total_abs > 0:
            metrics['gamma_skew'] = (call_gamma - put_gamma) / total_abs
        else:
            metrics['gamma_skew'] = 0
        
        return metrics

    def get_gamma_thermometer_data(self, ticker, days_back=252):
        """Busca dados históricos para o termômetro de gamma"""
        try:
            logging.info(f"Buscando dados históricos de gamma para termômetro: {ticker}")
            
            # Buscar dados históricos (252 dias)
            historical_data = self.analyzer.get_options_data(ticker, days_back)
            if not historical_data:
                raise ValueError(f"Dados históricos não disponíveis para {ticker}")
            
            # Processar dados históricos por data
            df_historical = pd.DataFrame(historical_data)
            df_historical['time'] = pd.to_datetime(df_historical['time'])
            df_historical['date'] = df_historical['time'].dt.date
            
            # Obter preço atual para referência
            spot_price = self.analyzer.get_current_spot_price(ticker)
            if not spot_price:
                raise ValueError(f"Não foi possível obter preço atual para {ticker}")
            
            daily_net_gammas = []
            
            # Calcular Net Gamma para cada dia
            for date in df_historical['date'].unique():
                daily_df = df_historical[df_historical['date'] == date].copy()
                
                if len(daily_df) < 5:  # Mínimo de opções por dia
                    continue
                    
                # Filtrar e processar dados do dia
                daily_df = daily_df[
                    (daily_df['days_to_maturity'] > 1) & 
                    (daily_df['days_to_maturity'] < 365) &
                    (daily_df['strike'] > spot_price * 0.7) & 
                    (daily_df['strike'] < spot_price * 1.3)
                ]
                
                if daily_df.empty:
                    continue
                    
                daily_df['spot_price'] = spot_price  # Usar preço atual como referência
                
                # Calcular gamma exposure para o dia
                daily_df = self.analyzer.calculate_gamma_exposure(daily_df)
                
                # Net Gamma do dia
                net_gamma_day = daily_df['dealer_gamma_exposure'].sum()
                daily_net_gammas.append({
                    'date': date,
                    'net_gamma': float(net_gamma_day)
                })
            
            if len(daily_net_gammas) < 10:  # Mínimo de dias válidos
                raise ValueError("Dados históricos insuficientes para análise")
            
            # Calcular estatísticas
            net_gammas = [d['net_gamma'] for d in daily_net_gammas]
            
            # Buscar Net Gamma atual
            current_analysis = self.analyze_gamma_complete(ticker, days_back=60)
            current_net_gamma = current_analysis['metrics']['net_gamma_exposure']
            
            # Calcular posição relativa (0-100%)
            min_gamma = min(net_gammas)
            max_gamma = max(net_gammas)
            
            if max_gamma != min_gamma:
                position_pct = ((current_net_gamma - min_gamma) / (max_gamma - min_gamma)) * 100
            else:
                position_pct = 50  # Se todos iguais, meio termo
            
            # Garantir que está entre 0-100%
            position_pct = max(0, min(100, position_pct))
            
            result = {
                'ticker': ticker.replace('.SA', ''),
                'current_net_gamma': float(current_net_gamma),
                'historical_stats': {
                    'min_gamma': float(min(net_gammas)),
                    'max_gamma': float(max(net_gammas)),
                    'avg_gamma': float(np.mean(net_gammas)),
                    'median_gamma': float(np.median(net_gammas)),
                    'std_gamma': float(np.std(net_gammas))
                },
                'position_percentile': float(position_pct),
                'days_analyzed': len(daily_net_gammas),
                'success': True
            }
            
            return convert_to_json_serializable(result)
            
        except Exception as e:
            logging.error(f"Erro na análise do termômetro: {e}")
            raise

    def get_plot_data(self, gamma_levels, spot_price, ticker):
        """Prepara dados para o gráfico frontend"""
        if gamma_levels.empty:
            return None
        
        currency = "R$" if ".SA" in ticker else "$"
        ticker_display = ticker.replace('.SA', '')
        
        plot_data = {
            'ticker': ticker_display,
            'currency': currency,
            'spot_price': float(spot_price),  # CONVERSÃO
            'strikes': [float(x) for x in gamma_levels['strike'].round(2).tolist()],  # CONVERSÃO
            'net_gamma': [float(x) for x in gamma_levels['net_gamma'].round(2).tolist()]  # CONVERSÃO
        }
        
        return plot_data

class GammaService:
    """Serviço principal para análise de Gamma"""
    
    def __init__(self):
        self.analyzer = GammaExposureAnalyzer()
    
    def analyze_gamma_complete(self, ticker, days_back=60):
        """Executa análise completa de gamma exposure"""
        try:
            logging.info(f"Iniciando análise de gamma para {ticker}")
            
            # 1. Obter preço atual
            spot_price = self.analyzer.get_current_spot_price(ticker)
            if not spot_price:
                raise ValueError(f"Não foi possível obter preço para {ticker}")
            
            # 2. Buscar dados de opções
            options_data = self.analyzer.get_options_data(ticker, days_back)
            if not options_data:
                raise ValueError(f"Dados de opções não disponíveis para {ticker}")
            
            # 3. Processar dados
            df = self.analyzer.process_options_data(options_data, spot_price)
            if df.empty:
                raise ValueError("Nenhuma opção válida encontrada")
            
            # 4. Calcular exposição gamma
            df = self.analyzer.calculate_gamma_exposure(df)
            
            # 5. Calcular níveis por strike
            gamma_levels = self.analyzer.calculate_gamma_levels_by_strike(df)
            if gamma_levels.empty:
                raise ValueError("Não foi possível calcular níveis de gamma")
            
            # 6. Identificar gamma walls
            walls = self.analyzer.identify_gamma_walls(gamma_levels, spot_price)
            
            # 7. Calcular métricas
            metrics = self.analyzer.calculate_metrics(df, gamma_levels, spot_price)
            
            # 8. Preparar dados para o gráfico
            plot_data = self.analyzer.get_plot_data(gamma_levels, spot_price, ticker)
            
            # ===== CONVERSÃO PARA JSON SERIALIZABLE =====
            result = {
                'ticker': ticker.replace('.SA', ''),
                'spot_price': float(spot_price),
                'metrics': convert_to_json_serializable(metrics),
                'walls': convert_to_json_serializable(walls),
                'plot_data': convert_to_json_serializable(plot_data),
                'options_count': int(len(df)),
                'success': True
            }
            
            return result
            
        except Exception as e:
            logging.error(f"Erro na análise de gamma: {e}")
            raise
    
    def get_gamma_summary(self, analysis_result):
        """Gera resumo executivo da análise"""
        if not analysis_result or not analysis_result.get('success'):
            return None
        
        metrics = analysis_result.get('metrics', {})
        walls = analysis_result.get('walls', [])
        
        summary = {
            'regime': metrics.get('gamma_regime', 'Unknown'),
            'net_exposure': float(metrics.get('net_gamma_exposure', 0)),  # CONVERSÃO
            'volatility_forecast': metrics.get('volatility_expectation', 'Unknown'),
            'market_behavior': metrics.get('market_behavior', 'Unknown'),
            'total_walls': int(len(walls)),  # CONVERSÃO
            'strongest_support': None,
            'strongest_resistance': None
        }
        
        # Encontrar walls mais fortes
        if walls:
            supports = [w for w in walls if w['type'] == 'Support']
            resistances = [w for w in walls if w['type'] == 'Resistance']
            
            if supports:
                summary['strongest_support'] = convert_to_json_serializable(max(supports, key=lambda x: x['intensity']))
            
            if resistances:
                summary['strongest_resistance'] = convert_to_json_serializable(max(resistances, key=lambda x: x['intensity']))
        
        return convert_to_json_serializable(summary)
import numpy as np
import pandas as pd
import yfinance as yf
from arch import arch_model
import xgboost as xgb
from sklearn.preprocessing import RobustScaler
import requests
from datetime import datetime, timedelta
import warnings
import logging

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)

class VolatilityValidator:
    """Validador de rompimentos baseado em volatilidade implícita da API OpLab"""
    
    def __init__(self, api_token=None):
        self.api_token = api_token or "beczK/4WCP1n9eOkIqVi4cR+qIlvNST0mq7DfBvKzU1kBRF0rakIb/wnspMQ9qSx--FiV9LR+39n8REDQPYVGc6A==--N2E2OGM3M2YzYmQwMzM0MzE0MWRjNzU4ZThhMDJkMGE="
        self.base_url = "https://api.oplab.com.br/v3/market/stocks"
        self.headers = {
            "Access-Token": self.api_token,
            "Content-Type": "application/json"
        }
        
    def get_iv_data(self, ticker):
        """Busca dados de volatilidade implícita da API OpLab"""
        try:
            ticker_clean = ticker.replace('.SA', '')
            
            params = {
                'symbol': ticker_clean,
                'limit': 1
            }
            
            response = requests.get(self.base_url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    return data[0]
            
            logging.warning(f"Dados IV não disponíveis para {ticker_clean}")
            return None
            
        except Exception as e:
            logging.error(f"Erro ao buscar dados IV: {e}")
            return None
    
    def calculate_confidence_score(self, iv_data, current_price=None):
        """Calcula score de confiança do rompimento (0-100)"""
        if not iv_data:
            return {'score': 50, 'status': 'NEUTRO', 'details': ['Dados IV indisponíveis']}
        
        score = 50
        details = []
        
        # IV Rank Analysis
        iv_rank_1y = iv_data.get('iv_1y_percentile')
        if iv_rank_1y is not None:
            if iv_rank_1y < 0.2:
                score += 30
                details.append(f"✅ IV Rank Baixo ({iv_rank_1y:.1%}) - Movimento genuíno")
            elif iv_rank_1y < 0.5:
                score += 15
                details.append(f"🟡 IV Rank Médio ({iv_rank_1y:.1%}) - Neutro")
            elif iv_rank_1y < 0.8:
                score -= 10
                details.append(f"⚠️ IV Rank Alto ({iv_rank_1y:.1%}) - Cuidado")
            else:
                score -= 25
                details.append(f"🔴 IV Rank Muito Alto ({iv_rank_1y:.1%}) - Movimento suspeito")
        
        # IV vs EWMA Spread
        iv_current = iv_data.get('iv_current')
        ewma_current = iv_data.get('ewma_current')
        
        if iv_current and ewma_current:
            iv_spread = (iv_current - ewma_current) / ewma_current
            
            if iv_spread < -0.1:
                score += 25
                details.append(f"✅ IV Subestimada ({iv_spread:.1%}) - Movimento não precificado")
            elif iv_spread < 0.1:
                score += 10
                details.append(f"🟡 IV vs EWMA Neutro ({iv_spread:.1%})")
            elif iv_spread < 0.3:
                score -= 10
                details.append(f"⚠️ IV Superestimada ({iv_spread:.1%})")
            else:
                score -= 20
                details.append(f"🔴 IV Muito Superestimada ({iv_spread:.1%}) - Movimento exagerado")
        
        # Volatilidade Realizada vs IV
        stdv_5d = iv_data.get('stdv_5d')
        if stdv_5d and iv_current:
            vol_ratio = stdv_5d / iv_current if iv_current > 0 else 1
            
            if vol_ratio < 0.7:
                score += 15
                details.append(f"✅ Vol Realizada Baixa vs IV ({vol_ratio:.2f}) - Espaço para movimento")
            elif vol_ratio > 1.3:
                score -= 15
                details.append(f"🔴 Vol Realizada Alta vs IV ({vol_ratio:.2f}) - Movimento já aconteceu")
        
        score = max(0, min(100, score))
        
        if score >= 70:
            status = "CONFIÁVEL"
            status_emoji = "🟢"
        elif score >= 40:
            status = "NEUTRO"
            status_emoji = "🟡"
        else:
            status = "SUSPEITO"
            status_emoji = "🔴"
        
        return {
            'score': score,
            'status': status,
            'status_emoji': status_emoji,
            'details': details,
            'raw_data': {
                'iv_current': iv_current,
                'iv_rank_1y': iv_rank_1y,
                'ewma_current': ewma_current,
                'stdv_5d': stdv_5d
            }
        }
    
    def validate_breakout(self, ticker, current_signals):
        """Valida rompimento das bandas usando IV"""
        iv_data = self.get_iv_data(ticker)
        confidence = self.calculate_confidence_score(iv_data, current_signals.get('price'))
        
        position = current_signals.get('position', '')
        
        if 'Acima Banda Superior' in position or 'Abaixo Banda Inferior' in position:
            if confidence['score'] >= 70:
                recommendation = "Movimento confiável - Continue posição"
            elif confidence['score'] >= 40:
                recommendation = "Movimento neutro - Reduza exposição"
            else:
                recommendation = "Movimento suspeito - Considere reversão"
        else:
            if confidence['score'] >= 70:
                recommendation = "Preparar para movimento genuíno"
            elif confidence['score'] >= 40:
                recommendation = "Aguardar sinais mais claros"
            else:
                recommendation = "Ambiente de alta incerteza"
        
        confidence['recommendation'] = recommendation
        return confidence

class HybridVolatilityBands:
    """Sistema de Bandas de Volatilidade Híbridas com Validação IV"""
    
    def __init__(self, ticker, period='2y'):
        # ===== USAR LÓGICA IDÊNTICA DO VOL_REGIMES_SERVICE.PY =====
        # Processar ticker IGUAL ao vol_regimes
        if not ticker.endswith('.SA') and not ticker.startswith('^'):
            ticker = ticker + '.SA'
            
        self.ticker = ticker
        self.ticker_display = ticker.replace('.SA', '')
        self.period = period
        self.df = None
        self.xgb_model = None
        self.scaler = RobustScaler()
        self.iv_validator = VolatilityValidator()
            
    def load_data(self):      
        try:
            # ===== USAR LÓGICA IDÊNTICA DO VOL_REGIMES_SERVICE.PY =====
            ticker = self.ticker
            
            # MESMA lógica de processamento
            if not ticker.endswith('.SA') and not ticker.startswith('^'):
                ticker = ticker + '.SA'
            
            # MESMO método de download com period fixo
            self.df = yf.download(ticker, start=None, end=None, period='2y', interval='1d')
            
            # MESMO tratamento de colunas multinível
            if hasattr(self.df.columns, 'get_level_values') and ticker in self.df.columns.get_level_values(1):
                self.df = self.df.xs(ticker, axis=1, level=1)
            
            if self.df.empty:
                self.logger.error(f"Nenhum dado encontrado para {ticker}")
                return None
            
            # MESMA ordem de operações
            self.df.reset_index(inplace=True)
            self.df['Returns'] = self.df['Close'].pct_change()
            self.df['Log_Returns'] = np.log(self.df['Close'] / self.df['Close'].shift(1))
            self.df.dropna(inplace=True)
            
            logging.info(f"Dados carregados: {len(self.df)} registros de {self.df['Date'].iloc[0]} até {self.df['Date'].iloc[-1]}")
            return self
            
        except Exception as e:
            logging.error(f"Erro ao carregar dados: {e}")
        raise
    
    def calculate_base_volatility(self):
        try:
            garch_model = arch_model(self.df['Log_Returns'] * 100, vol='Garch', p=1, q=1, dist='Normal')
            garch_result = garch_model.fit(disp='off')
            self.df['garch_vol'] = garch_result.conditional_volatility / 100
        except:
            # Fallback se GARCH falhar
            self.df['garch_vol'] = self.df['Returns'].rolling(20).std()
        
        for window in [3, 5, 10, 20]:
            self.df[f'realized_vol_{window}d'] = (
                self.df['Returns'].rolling(window=window)
                .apply(lambda x: np.sqrt(np.sum(x**2)))
            )
        return self
    
    def engineer_features(self):
        df = self.df
        
        for window in [5, 10, 20, 60]:
            df[f'vol_std_{window}d'] = df['Returns'].rolling(window).std()
        
        for lag in [1, 2, 5]:
            df[f'garch_lag_{lag}'] = df['garch_vol'].shift(lag)
            df[f'returns_lag_{lag}'] = df['Returns'].shift(lag)
        
        df['daily_range'] = (df['High'] - df['Low']) / df['Close']
        df['price_momentum_5d'] = df['Close'] / df['Close'].shift(5) - 1
        
        if 'Volume' in df.columns:
            df['volume_ma_20'] = df['Volume'].rolling(20).mean()
            df['volume_ratio'] = df['Volume'] / df['volume_ma_20']
        else:
            df['volume_ratio'] = 1
        
        df['sma_50'] = df['Close'].rolling(50).mean()
        df['sma_200'] = df['Close'].rolling(200).mean()
        df['trend_regime'] = np.where(df['sma_50'] > df['sma_200'], 1, 0)
        df['vol_regime'] = np.where(df['garch_vol'] > df['garch_vol'].rolling(60).mean(), 1, 0)
        df['vol_percentile'] = df['garch_vol'].rolling(252).rank(pct=True)
        
        return self
    
    def train_xgboost(self):
        feature_cols = [
            'garch_lag_1', 'garch_lag_2', 'garch_lag_5',
            'realized_vol_10d', 'realized_vol_20d', 'realized_vol_3d',
            'vol_std_10d', 'vol_std_20d', 'vol_std_5d',
            'vol_percentile', 'vol_regime', 'returns_lag_1',
            'daily_range', 'price_momentum_5d', 'volume_ratio', 'trend_regime'
        ]
        
        df_ml = self.df[feature_cols + ['garch_vol']].copy()
        df_ml.dropna(inplace=True)
        
        if len(df_ml) < 100:
            # Fallback se dados insuficientes
            self.df['xgb_vol'] = self.df['garch_vol']
            return self
        
        X = df_ml[feature_cols]
        y = df_ml['garch_vol']
        
        X_scaled = self.scaler.fit_transform(X)
        X_scaled = pd.DataFrame(X_scaled, columns=feature_cols, index=X.index)
        
        train_size = int(len(X_scaled) * 0.8)
        X_train, X_test = X_scaled[:train_size], X_scaled[train_size:]
        y_train, y_test = y[:train_size], y[train_size:]
        
        self.xgb_model = xgb.XGBRegressor(
            n_estimators=200, max_depth=8, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, reg_alpha=0.1,
            reg_lambda=0.1, random_state=42, verbosity=0
        )
        
        self.xgb_model.fit(X_train, y_train)
        xgb_pred = self.xgb_model.predict(X_test)
        
        self.df['xgb_vol'] = np.nan
        test_indices = df_ml.index[train_size:]
        self.df.loc[test_indices, 'xgb_vol'] = xgb_pred
        self.df['xgb_vol'].fillna(self.df['garch_vol'], inplace=True)
        
        return self
    
    def create_hybrid_model(self):
        df = self.df
        
        df['vol_regime_adaptive'] = df['garch_vol'].rolling(30).std()
        df['vol_regime_normalized'] = (
            df['vol_regime_adaptive'] / df['vol_regime_adaptive'].rolling(252).mean()
        )
        df['vol_regime_normalized'].fillna(1.0, inplace=True)
        
        df['weight_garch'] = np.clip(0.3 + 0.4 * df['vol_regime_normalized'], 0.3, 0.7)
        df['weight_xgb'] = 1 - df['weight_garch']
        
        df['hybrid_vol'] = (
            df['weight_garch'] * df['garch_vol'] + 
            df['weight_xgb'] * df['xgb_vol']
        )
        
        df['hybrid_vol'].fillna(df['garch_vol'], inplace=True)
        df['hybrid_vol'].fillna(method='ffill', inplace=True)
        df['hybrid_vol'].fillna(0.02, inplace=True)
        
        return self
    
    def create_bands(self):
        df_temp = self.df.copy()
        df_temp['Month'] = df_temp['Date'].dt.to_period('M')
        
        monthly_ref = df_temp.groupby('Month').agg(
            reference_price=('Close', 'last'),
            monthly_vol=('hybrid_vol', 'last')
        ).reset_index()
        
        monthly_ref['Next_Month'] = monthly_ref['Month'] + 1
        df_temp = df_temp.merge(
            monthly_ref[['Next_Month', 'reference_price', 'monthly_vol']],
            left_on='Month', right_on='Next_Month', how='left'
        )
        
        df_temp['monthly_vol'].fillna(method='ffill', inplace=True)
        df_temp['reference_price'].fillna(method='ffill', inplace=True)
        df_temp['monthly_vol'].fillna(self.df['garch_vol'], inplace=True)
        df_temp['reference_price'].fillna(self.df['Close'], inplace=True)
        
        for d in [2, 4]:
            self.df[f'banda_superior_{d}sigma'] = (
                (1 + d * df_temp['monthly_vol']) * df_temp['reference_price']
            )
            self.df[f'banda_inferior_{d}sigma'] = (
                (1 - d * df_temp['monthly_vol']) * df_temp['reference_price']
            )
        
        self.df['linha_central'] = (self.df['banda_superior_2sigma'] + self.df['banda_inferior_2sigma']) / 2
        
        for col in ['banda_superior_2sigma', 'banda_inferior_2sigma', 'linha_central', 'banda_superior_4sigma', 'banda_inferior_4sigma']:
            if self.df[col].isna().any():
                self.df[col].fillna(method='ffill', inplace=True)
                self.df[col].fillna(method='bfill', inplace=True)
        
        return self
    
    def get_current_signals(self):
        """Sinais atuais de trading COM validação IV"""
        latest = self.df.iloc[-1]
        current_price = latest['Close']
        
        def safe_get(col_name, fallback_value):
            value = latest[col_name] if not pd.isna(latest[col_name]) else fallback_value
            return value
        
        vol_fallback = latest['garch_vol'] if not pd.isna(latest['garch_vol']) else 0.02
        
        signals = {
            'price': float(current_price),
            'volatility': float(latest['hybrid_vol'] if not pd.isna(latest['hybrid_vol']) else vol_fallback),
            'trend_regime': 'Bull' if latest['trend_regime'] == 1 else 'Bear',
            'vol_regime': 'High' if latest['vol_regime'] == 1 else 'Low',
            'bandas': {
                'superior_2σ': float(safe_get('banda_superior_2sigma', current_price * (1 + 2 * vol_fallback))),
                'inferior_2σ': float(safe_get('banda_inferior_2sigma', current_price * (1 - 2 * vol_fallback))),
                'superior_4σ': float(safe_get('banda_superior_4sigma', current_price * (1 + 4 * vol_fallback))),
                'inferior_4σ': float(safe_get('banda_inferior_4sigma', current_price * (1 - 4 * vol_fallback))),
                'linha_central': float(safe_get('linha_central', current_price))
            }
        }
        
        sup_2sigma = signals['bandas']['superior_2σ']
        inf_2sigma = signals['bandas']['inferior_2σ']
        central = signals['bandas']['linha_central']
        
        if current_price > sup_2sigma:
            signals['position'] = 'Acima Banda Superior 2σ - Sobrecomprado'
        elif current_price < inf_2sigma:
            signals['position'] = 'Abaixo Banda Inferior 2σ - Sobrevendido'
        elif current_price > central:
            signals['position'] = 'Metade Superior - Bullish'
        else:
            signals['position'] = 'Metade Inferior - Bearish'
        
        # Validação IV
        try:
            iv_analysis = self.iv_validator.validate_breakout(self.ticker, signals)
            signals['iv_validation'] = iv_analysis
        except Exception as e:
            logging.error(f"Erro na validação IV: {e}")
            signals['iv_validation'] = {
                'score': 50, 'status': 'INDISPONÍVEL', 'status_emoji': '⚪',
                'recommendation': 'Use apenas análise técnica',
                'details': ['Dados IV indisponíveis']
            }
        
        return signals
    
    def get_plot_data(self, days_back=180):
        """Preparar dados para o gráfico frontend"""
        df_plot = self.df.tail(days_back).copy()
        
        currency = "R$" if ".SA" in self.ticker else "$"
        
        plot_data = {
            'ticker': self.ticker_display,
            'currency': currency,
            'dates': df_plot['Date'].dt.strftime('%Y-%m-%d').tolist(),
            'ohlc': {
                'open': df_plot['Open'].round(2).tolist(),
                'high': df_plot['High'].round(2).tolist(),
                'low': df_plot['Low'].round(2).tolist(),
                'close': df_plot['Close'].round(2).tolist()
            },
            'bands': {
                'superior_2sigma': df_plot['banda_superior_2sigma'].round(2).tolist(),
                'inferior_2sigma': df_plot['banda_inferior_2sigma'].round(2).tolist(),
                'superior_4sigma': df_plot['banda_superior_4sigma'].round(2).tolist(),
                'inferior_4sigma': df_plot['banda_inferior_4sigma'].round(2).tolist(),
                'linha_central': df_plot['linha_central'].round(2).tolist()
            }
        }
        
        return plot_data

class GeminiiFlowTracker:
    """Sistema de Análise de Fluxo de Opções"""
    
    def __init__(self):
        self.token = "beczK/4WCP1n9eOkIqVi4cR+qIlvNST0mq7DfBvKzU1kBRF0rakIb/wnspMQ9qSx--FiV9LR+39n8REDQPYVGc6A==--N2E2OGM3M2YzYmQwMzM0MzE0MWRjNzU4ZThhMDJkMGE="
        self.base_url = "https://api.oplab.com.br/v3/market/historical/options"
        self.headers = {
            "Access-Token": self.token,
            "Content-Type": "application/json"
        }
    
    def get_options_data(self, ticker, from_date, to_date):
        """Busca dados de opções da OpLab"""
        url = f"{self.base_url}/{ticker}/{from_date}/{to_date}"
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                return response.json()
            logging.warning(f"Dados de opções indisponíveis para {ticker}: {response.status_code}")
            return None
        except Exception as e:
            logging.error(f"Erro ao buscar dados de opções: {e}")
            return None
    
    def get_stock_data(self, ticker, from_date, to_date):
        """Busca dados do ativo com yfinance"""
        try:
            stock_ticker = f"{ticker}.SA" if not ticker.endswith('.SA') else ticker
            stock = yf.Ticker(stock_ticker)
            hist = stock.history(start=from_date, end=to_date)
            return hist if not hist.empty else None
        except Exception as e:
            logging.error(f"Erro ao buscar dados do ativo: {e}")
            return None
    
    def calculate_moneyness(self, strike, spot_price):
        """Calcula moneyness da opção"""
        if spot_price <= 0:
            return "ATM"
        
        ratio = strike / spot_price
        if ratio < 0.95:
            return "OTM" if strike < spot_price else "ITM"
        elif ratio > 1.05:
            return "ITM" if strike < spot_price else "OTM"
        else:
            return "ATM"
    
    def process_flow_data(self, options_data, stock_data):
        """Processamento de dados do flow - DIÁRIO"""
        if not options_data or stock_data is None or stock_data.empty:
            return pd.DataFrame()
        
        df = pd.DataFrame(options_data)
        required = ['time', 'type', 'premium', 'strike']
        missing = [col for col in required if col not in df.columns]
        if missing:
            logging.error(f"Colunas faltando: {missing}")
            return pd.DataFrame()
        
        df['time'] = pd.to_datetime(df['time'])
        df = df.dropna(subset=required)
        df = df[df['premium'] > 0]
        
        # Mapear preços diários diretamente
        df['date'] = df['time'].dt.date
        
        # Criar mapeamento de preços por data
        price_map = {}
        for date, row in stock_data.iterrows():
            date_key = date.date() if hasattr(date, 'date') else date
            price_map[date_key] = row['Close']
        
        df['spot_price'] = df['date'].map(price_map)
        df = df.dropna(subset=['spot_price'])
        
        if df.empty:
            return pd.DataFrame()
        
        df['moneyness'] = df.apply(lambda row: self.calculate_moneyness(row['strike'], row['spot_price']), axis=1)
        df = df[df['moneyness'].isin(['OTM', 'ATM'])]
        
        if 'volume' in df.columns:
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(1)
        else:
            df['volume'] = 1
        
        if 'open_interest' in df.columns:
            df['oi'] = pd.to_numeric(df['open_interest'], errors='coerce').fillna(1)
            df['weight'] = df['premium'] * np.sqrt(df['volume'] * df['oi'])
        else:
            df['weight'] = df['premium'] * np.sqrt(df['volume'])
        
        df['option_type'] = df['type'].str.upper()
        
        # Agrupar por data (daily)
        flow_results = []
        for date in sorted(df['date'].unique()):
            daily_data = df[df['date'] == date]
            
            calls = daily_data[daily_data['option_type'] == 'CALL']
            puts = daily_data[daily_data['option_type'] == 'PUT']
            
            call_flow = calls['weight'].sum()
            put_flow = puts['weight'].sum()
            total_flow = call_flow + put_flow
            spot = daily_data['spot_price'].iloc[0]
            
            flow_results.append({
                'datetime': pd.Timestamp(date),
                'call_flow': call_flow,
                'put_flow': put_flow,
                'net_flow': call_flow - put_flow,
                'total_flow': total_flow,
                'spot_price': spot,
                'call_count': len(calls),
                'put_count': len(puts),
                'intensity': np.log1p(total_flow) if total_flow > 0 else 0,
                'bias': (call_flow - put_flow) / (total_flow + 1) if total_flow > 0 else 0
            })
        
        result = pd.DataFrame(flow_results)
        result = result.sort_values('datetime')
        
        # Suavização para dados diários
        window = max(2, len(result) // 10)
        result['call_smooth'] = result['call_flow'].rolling(window, center=True, min_periods=1).mean()
        result['put_smooth'] = result['put_flow'].rolling(window, center=True, min_periods=1).mean()
        
        return result
    
    def analyze_sentiment(self, data):
        """Análise de sentimento"""
        if data.empty:
            return {}
        
        total_call = data['call_flow'].sum()
        total_put = data['put_flow'].sum()
        net_flow = total_call - total_put
        cp_ratio = total_call / (total_put + 1)
        avg_intensity = data['intensity'].mean()
        max_intensity = data['intensity'].max()
        
        if net_flow > 0:
            if cp_ratio > 3:
                sentiment = "EXTREMELY BULLISH"
            elif cp_ratio > 2:
                sentiment = "STRONGLY BULLISH"
            elif cp_ratio > 1.5:
                sentiment = "BULLISH"
            else:
                sentiment = "MILDLY BULLISH"
        else:
            if cp_ratio < 0.33:
                sentiment = "EXTREMELY BEARISH"
            elif cp_ratio < 0.5:
                sentiment = "STRONGLY BEARISH"
            elif cp_ratio < 0.8:
                sentiment = "BEARISH"
            else:
                sentiment = "MILDLY BEARISH"
        
        recent = data.tail(min(7, len(data)))
        recent_bias = recent['bias'].mean()
        trend = "ACCELERATING" if abs(recent_bias) > 0.3 else "STABLE"
        signal_strength = "HIGH" if max_intensity > avg_intensity * 2 else "MEDIUM"
        
        return {
            'total_call_flow': float(total_call),
            'total_put_flow': float(total_put),
            'net_flow': float(net_flow),
            'cp_ratio': float(cp_ratio),
            'sentiment': sentiment,
            'trend': trend,
            'avg_intensity': float(avg_intensity),
            'max_intensity': float(max_intensity),
            'signal_strength': signal_strength,
            'periods': len(data)
        }
    
    def get_plot_data(self, data, ticker):
        """Preparar dados para o gráfico frontend"""
        if data.empty:
            return None
        
        plot_data = {
            'ticker': ticker,
            'period': {
                'start': data['datetime'].min().strftime('%d/%m/%Y'),
                'end': data['datetime'].max().strftime('%d/%m/%Y')
            },
            'dates': data['datetime'].dt.strftime('%Y-%m-%d').tolist(),
            'spot_prices': data['spot_price'].round(2).tolist(),
            'call_flow': data['call_smooth'].round(0).tolist(),
            'put_flow': data['put_smooth'].round(0).tolist(),
            'intensity': data['intensity'].round(3).tolist(),
            'bias': data['bias'].round(3).tolist()
        }
        
        return plot_data

class BandasProService:
    """Serviço principal que orquestra todas as análises"""
    
    def __init__(self):
        self.bands_system = None
        self.flow_system = GeminiiFlowTracker()
    
    def analyze_bands(self, ticker, period='2y'):
        """Executa análise de bandas de volatilidade"""
        logging.info(f"Iniciando análise de bandas para {ticker}")
        
        self.bands_system = HybridVolatilityBands(ticker, period)
        self.bands_system.load_data()
        
        if self.bands_system.df.empty:
            raise ValueError(f'Dados não encontrados para {ticker}')
        
        (self.bands_system
         .calculate_base_volatility()
         .engineer_features()
         .train_xgboost()
         .create_hybrid_model()
         .create_bands())
        
        signals = self.bands_system.get_current_signals()
        plot_data = self.bands_system.get_plot_data()
        
        return {
            'signals': signals,
            'plot_data': plot_data
        }
    
    def analyze_flow(self, ticker, flow_days=30):
        """Executa análise de flow de opções"""
        logging.info(f"Iniciando análise de flow para {ticker}")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=flow_days)
        from_date = start_date.strftime('%Y-%m-%d')
        to_date = end_date.strftime('%Y-%m-%d')
        
        ticker_clean = ticker.replace('.SA', '')
        
        options_data = self.flow_system.get_options_data(ticker_clean, from_date, to_date)
        stock_data = self.flow_system.get_stock_data(ticker_clean, from_date, to_date)
        
        if not options_data or stock_data is None:
            raise ValueError('Dados de opções não disponíveis para este ticker')
        
        flow_data = self.flow_system.process_flow_data(options_data, stock_data)
        
        if flow_data.empty:
            raise ValueError('Não foi possível processar dados de flow')
        
        analysis = self.flow_system.analyze_sentiment(flow_data)
        plot_data = self.flow_system.get_plot_data(flow_data, ticker_clean)
        
        return {
            'analysis': analysis,
            'plot_data': plot_data
        }
    
    def analyze_complete(self, ticker, period='2y', flow_days=30):
        """Executa análise completa: Bandas + Flow"""
        logging.info(f"Iniciando análise completa para {ticker}")
        
        # Análise das Bandas
        bands_result = self.analyze_bands(ticker, period)
        
        # Análise do Flow
        flow_result = None
        try:
            flow_result = self.analyze_flow(ticker, flow_days)
        except Exception as e:
            logging.warning(f"Flow analysis falhou: {e}")
        
        # Recomendação Combinada
        combined_recommendation = self.generate_combined_recommendation(
            bands_result['signals'], 
            flow_result['analysis'] if flow_result else None
        )
        
        return {
            'ticker': ticker.replace('.SA', ''),
            'bands': bands_result,
            'flow': flow_result,
            'combined': combined_recommendation
        }
    
    def generate_combined_recommendation(self, bands_signals, flow_analysis):
        """Gera recomendação combinada baseada em bandas e flow"""
        if not bands_signals:
            return None
        
        bands_position = bands_signals.get('position', '')
        iv_score = bands_signals.get('iv_validation', {}).get('score', 50)
        
        flow_sentiment = 'NEUTRAL'
        cp_ratio = 1.0
        
        if flow_analysis:
            flow_sentiment = flow_analysis.get('sentiment', 'NEUTRAL')
            cp_ratio = flow_analysis.get('cp_ratio', 1.0)
        
        # Lógica de recomendação combinada
        if 'Acima Banda Superior' in bands_position or 'Abaixo Banda Inferior' in bands_position:
            if iv_score >= 70:
                if ('BULLISH' in flow_sentiment and 'Superior' in bands_position) or \
                   ('BEARISH' in flow_sentiment and 'Inferior' in bands_position):
                    recommendation = "🚀 SINAL FORTE: Rompimento confiável confirmado pelo flow"
                else:
                    recommendation = "📊 MOVIMENTO CONFIÁVEL: IV confirma rompimento genuíno"
            elif iv_score < 40:
                if ('BEARISH' in flow_sentiment and 'Superior' in bands_position) or \
                   ('BULLISH' in flow_sentiment and 'Inferior' in bands_position):
                    recommendation = "🔴 SINAL REVERSAL: IV suspeita + flow contrário"
                else:
                    recommendation = "⚠️ MOVIMENTO SUSPEITO: IV indica falso rompimento"
            else:
                recommendation = "🟡 SINAL NEUTRO: Sinais mistos, aguarde confirmação"
        else:
            if iv_score >= 70 and abs(cp_ratio - 1) > 0.5:
                recommendation = "🎯 PREPARAR: Movimento forte se aproximando"
            elif iv_score >= 40:
                recommendation = "⏳ AGUARDAR: Sinais ainda não claros"
            else:
                recommendation = "🌫️ INCERTEZA: Ambiente de alta volatilidade"
        
        return {
            'bands_position': bands_position,
            'iv_score': iv_score,
            'flow_sentiment': flow_sentiment,
            'cp_ratio': cp_ratio,
            'recommendation': recommendation
        }
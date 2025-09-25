import numpy as np
import pandas as pd
import yfinance as yf
from arch import arch_model
import json
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
        self.api_token = api_token or "7gMd+LaFRJ6u6bmjgv9gxeGd5fAc6EHtpM4UoQ41tLivobEa4YTd5dA9xi00s/yd--NJ1uhr4hX+m6KeMsjdVfog==--ZTMyNzIyMjM3OGIxYThmN2YzNzdmZmYzOTZjY2RhYzc="
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
   
   def __init__(self, ticker, period='2y', regime="M"): 
       if not ticker.endswith('.SA') and not ticker.startswith('^'):
           ticker = ticker + '.SA'
           
       self.ticker = ticker
       self.ticker_display = ticker.replace('.SA', '')
       self.period = period
       self.regime = regime  
       self.data = None  
       self.df = None    
       self.xgb_model = None
       self.scaler = RobustScaler()
       self.iv_validator = VolatilityValidator()
           
   def load_data(self):      
       try:
           ticker = self.ticker
           
           if not ticker.endswith('.SA') and not ticker.startswith('^'):
               ticker = ticker + '.SA'
           
           # MESMO método de download com period fixo
           self.df = yf.download(ticker, start=None, end=None, period='2y', interval='1d')
           
           # MESMO tratamento de colunas multinível
           if hasattr(self.df.columns, 'get_level_values') and ticker in self.df.columns.get_level_values(1):
               self.df = self.df.xs(ticker, axis=1, level=1)
           
           if self.df.empty:
               logging.error(f"Nenhum dado encontrado para {ticker}")
               return None
           
           self.df = self.df[(self.df['Open'] > 0) & 
                       (self.df['High'] > 0) & 
                       (self.df['Low'] > 0) & 
                       (self.df['Close'] > 0)]
       
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
           # Verificar se temos dados válidos para GARCH
           returns_data = self.df['Log_Returns'].dropna() * 100
           if len(returns_data) < 50:
               raise ValueError("Dados insuficientes para modelo GARCH")
           
           garch_model = arch_model(returns_data, vol='Garch', p=1, q=1, dist='Normal')
           garch_result = garch_model.fit(disp='off')
           
           # Ajustar o tamanho dos dados de volatilidade condicional
           garch_vol = garch_result.conditional_volatility / 100
           
           # Garantir que o tamanho seja correto
           if len(garch_vol) < len(self.df):
               # Preencher valores iniciais com média
               vol_mean = garch_vol.mean()
               missing_count = len(self.df) - len(garch_vol)
               garch_vol = np.concatenate([np.full(missing_count, vol_mean), garch_vol])
           
           self.df['garch_vol'] = garch_vol[:len(self.df)]
           
       except Exception as e:
           logging.warning(f"GARCH falhou: {e}. Usando fallback com rolling std.")
           # Fallback se GARCH falhar
           self.df['garch_vol'] = self.df['Returns'].rolling(20, min_periods=5).std().fillna(0.02)
       
       # Calcular volatilidades realizadas
       for window in [3, 5, 10, 20]:
           self.df[f'realized_vol_{window}d'] = (
               self.df['Returns'].rolling(window=window, min_periods=1)
               .apply(lambda x: np.sqrt(np.sum(x**2)) if len(x) > 0 else 0.02)
           )
       return self
   
   def engineer_features(self):
       df = self.df
       
       # Volatilidades de diferentes janelas
       for window in [5, 10, 20, 60]:
           df[f'vol_std_{window}d'] = df['Returns'].rolling(window, min_periods=1).std()
       
       # Features com lags
       for lag in [1, 2, 5]:
           df[f'garch_lag_{lag}'] = df['garch_vol'].shift(lag)
           df[f'returns_lag_{lag}'] = df['Returns'].shift(lag)
       
       # Range diário
       df['daily_range'] = (df['High'] - df['Low']) / df['Close']
       df['price_momentum_5d'] = df['Close'] / df['Close'].shift(5) - 1
       
       # Volume
       if 'Volume' in df.columns:
           df['volume_ma_20'] = df['Volume'].rolling(20, min_periods=1).mean()
           df['volume_ratio'] = df['Volume'] / df['volume_ma_20']
           df['volume_ratio'].fillna(1, inplace=True)
       else:
           df['volume_ratio'] = 1
       
       # Regimes de tendência e volatilidade
       df['sma_50'] = df['Close'].rolling(50, min_periods=1).mean()
       df['sma_200'] = df['Close'].rolling(200, min_periods=1).mean()
       df['trend_regime'] = np.where(df['sma_50'] > df['sma_200'], 1, 0)
       df['vol_regime'] = np.where(df['garch_vol'] > df['garch_vol'].rolling(60, min_periods=1).mean(), 1, 0)
       df['vol_percentile'] = df['garch_vol'].rolling(252, min_periods=20).rank(pct=True)
       
       # Preencher NaNs com métodos apropriados
       numeric_columns = df.select_dtypes(include=[np.number]).columns
       for col in numeric_columns:
           if col in df.columns:
               df[col].fillna(method='ffill', inplace=True)
               df[col].fillna(method='bfill', inplace=True)
               df[col].fillna(0, inplace=True)
       
       return self
   
   def train_xgboost(self):
       feature_cols = [
           'garch_lag_1', 'garch_lag_2', 'garch_lag_5',
           'realized_vol_10d', 'realized_vol_20d', 'realized_vol_3d',
           'vol_std_10d', 'vol_std_20d', 'vol_std_5d',
           'vol_percentile', 'vol_regime', 'returns_lag_1',
           'daily_range', 'price_momentum_5d', 'volume_ratio', 'trend_regime'
       ]
       
       # Verificar se todas as features existem
       available_features = [col for col in feature_cols if col in self.df.columns]
       if len(available_features) < len(feature_cols) * 0.7:  # Pelo menos 70% das features
           logging.warning(f"Poucas features disponíveis para XGBoost. Usando apenas volatilidade GARCH.")
           self.df['xgb_vol'] = self.df['garch_vol']
           return self
       
       df_ml = self.df[available_features + ['garch_vol']].copy()
       df_ml.dropna(inplace=True)
       
       if len(df_ml) < 50:  # Reduzir requisito mínimo
           logging.warning("Dados insuficientes para XGBoost. Usando apenas volatilidade GARCH.")
           self.df['xgb_vol'] = self.df['garch_vol']
           return self
       
       X = df_ml[available_features]
       y = df_ml['garch_vol']
       
       X_scaled = self.scaler.fit_transform(X)
       X_scaled = pd.DataFrame(X_scaled, columns=available_features, index=X.index)
       
       train_size = int(len(X_scaled) * 0.8)
       X_train, X_test = X_scaled[:train_size], X_scaled[train_size:]
       y_train, y_test = y[:train_size], y[train_size:]
       
       self.xgb_model = xgb.XGBRegressor(
           n_estimators=100,  # Reduzir para datasets menores
           max_depth=6,
           learning_rate=0.1,
           subsample=0.8,
           colsample_bytree=0.8,
           reg_alpha=0.1,
           reg_lambda=0.1,
           random_state=42,
           verbosity=0
       )
       
       self.xgb_model.fit(X_train, y_train)
       xgb_pred = self.xgb_model.predict(X_test)
       
       self.df['xgb_vol'] = self.df['garch_vol']  # Inicializar com garch
       test_indices = df_ml.index[train_size:]
       self.df.loc[test_indices, 'xgb_vol'] = xgb_pred
       
       return self
   
   def create_hybrid_model(self):
       df = self.df
       
       # Configurar janelas baseado no regime
       if self.regime == 'D':
           adaptive_window = 5
           mean_window = 21
       elif self.regime == 'W':
           adaptive_window = 10
           mean_window = 50
       elif self.regime == 'M':
           adaptive_window = 30
           mean_window = 252
       else:  # 'Y'
           adaptive_window = 60
           mean_window = 504
       
       df['vol_regime_adaptive'] = df['garch_vol'].rolling(adaptive_window, min_periods=5).std()
       df['vol_regime_normalized'] = (
           df['vol_regime_adaptive'] / df['vol_regime_adaptive'].rolling(mean_window, min_periods=20).mean()
       )
       df['vol_regime_normalized'].fillna(1.0, inplace=True)
       
       # ===== PESOS ESPECÍFICOS POR REGIME =====
       if self.regime == 'D':
           # DIÁRIO: Mais peso no GARCH (reação rápida)
           base_garch = 0.7
           variacao = 0.2
           df['weight_garch'] = np.clip(
               base_garch + variacao * (df['vol_regime_normalized'] - 1), 
               0.5, 0.8
           )
           
       elif self.regime == 'W':
           # SEMANAL: Equilibrado entre GARCH e XGB
           base_garch = 0.5
           variacao = 0.3
           df['weight_garch'] = np.clip(
               base_garch + variacao * (df['vol_regime_normalized'] - 1), 
               0.3, 0.7
           )
           
       elif self.regime == 'M':
           # MENSAL: Mais peso no XGB (padrões de longo prazo)
           base_garch = 0.4
           variacao = 0.3
           df['weight_garch'] = np.clip(
               base_garch + variacao * (df['vol_regime_normalized'] - 1), 
               0.2, 0.6
           )
           
       else:  # 'Y' - ANUAL
           # ANUAL: Muito mais peso no XGB (machine learning para longo prazo)
           base_garch = 0.3
           variacao = 0.2
           df['weight_garch'] = np.clip(
               base_garch + variacao * (df['vol_regime_normalized'] - 1), 
               0.2, 0.5
           )
       
       df['weight_xgb'] = 1 - df['weight_garch']
       
       # Criar modelo híbrido com pesos específicos do regime
       df['hybrid_vol'] = (
           df['weight_garch'] * df['garch_vol'] + 
           df['weight_xgb'] * df['xgb_vol']
       )
       
       # Garantir que não temos valores nulos ou muito pequenos
       df['hybrid_vol'].fillna(df['garch_vol'], inplace=True)
       df['hybrid_vol'].fillna(0.02, inplace=True)
       df['hybrid_vol'] = np.maximum(df['hybrid_vol'], 0.001)  # Mínimo de 0.1%
       
       return self
   
   def create_bands(self):
        df_temp = self.df.copy()
        df_temp['reference_price'] = np.nan
        df_temp['period_vol'] = np.nan
        
        # Garantir que Date é datetime
        if 'Date' not in df_temp.columns:
            df_temp.reset_index(inplace=True)
        df_temp['Date'] = pd.to_datetime(df_temp['Date'])
        
        # LÓGICA CORRETA: SEMPRE USAR DADOS DO PERÍODO ANTERIOR
        if self.regime == 'D':  # DIÁRIO
            # DIÁRIO: Preço de ONTEM, volatilidade de ONTEM
            df_temp['reference_price'] = df_temp['Close'].shift(1)  # PREÇO DE ONTEM
            df_temp['period_vol'] = df_temp['hybrid_vol'].shift(1)  # VOL DE ONTEM
            
        elif self.regime == 'W':  # SEMANAL
            df_temp['Week'] = df_temp['Date'].dt.to_period('W-MON')
            
            # Preço E volatilidade da SEXTA-FEIRA de cada semana
            weekly_ref = df_temp.groupby('Week').agg({
                'Close': 'last',      # Sexta-feira
                'hybrid_vol': 'last'  # Sexta-feira
            }).reset_index()
            weekly_ref.columns = ['Week', 'week_price', 'week_vol']
            
            # Shiftar para semana ANTERIOR
            weekly_ref['week_price_previous'] = weekly_ref['week_price'].shift(1)
            weekly_ref['week_vol_previous'] = weekly_ref['week_vol'].shift(1)
            
            df_temp = df_temp.merge(weekly_ref[['Week', 'week_price_previous', 'week_vol_previous']], on='Week')
            df_temp['reference_price'] = df_temp['week_price_previous']  # SEXTA DA SEMANA PASSADA
            df_temp['period_vol'] = df_temp['week_vol_previous']  # SEXTA DA SEMANA PASSADA
            
        elif self.regime == 'M':  # MENSAL
            # MENSAL: Preço E volatilidade do ÚLTIMO dia do mês PASSADO
            df_temp['Month'] = df_temp['Date'].dt.to_period('M')
            
            # Preço E volatilidade do ÚLTIMO dia de cada mês
            monthly_ref = df_temp.groupby('Month').agg({
                'Close': 'last',      # ÚLTIMO dia do mês
                'hybrid_vol': 'last'  # ÚLTIMO dia do mês
            }).reset_index()
            monthly_ref.columns = ['Month', 'month_price', 'month_vol']
            
            # Shiftar para pegar mês ANTERIOR
            monthly_ref['month_price_previous'] = monthly_ref['month_price'].shift(1)
            monthly_ref['month_vol_previous'] = monthly_ref['month_vol'].shift(1)
            
            # Merge
            df_temp = df_temp.merge(monthly_ref[['Month', 'month_price_previous', 'month_vol_previous']], on='Month')
            df_temp['reference_price'] = df_temp['month_price_previous']  # ÚLTIMO DIA MÊS PASSADO
            df_temp['period_vol'] = df_temp['month_vol_previous']   # ÚLTIMO DIA MÊS PASSADO
            
        elif self.regime == 'Q':  # TRIMESTRAL
            # TRIMESTRAL: Preço do 1º dia do trimestre PASSADO, vol do último dia do trimestre PASSADO
            df_temp['Quarter'] = df_temp['Date'].dt.to_period('Q')
            
            # Preço do primeiro dia de cada trimestre
            quarterly_price = df_temp.groupby('Quarter')['Close'].first().reset_index()
            quarterly_price.columns = ['Quarter', 'quarter_price']
            quarterly_price['quarter_price_previous'] = quarterly_price['quarter_price'].shift(1)
            
            # Volatilidade do último dia de cada trimestre
            quarterly_vol = df_temp.groupby('Quarter')['hybrid_vol'].last().reset_index()
            quarterly_vol.columns = ['Quarter', 'quarter_vol']
            quarterly_vol['quarter_vol_previous'] = quarterly_vol['quarter_vol'].shift(1)
            
            # Merge
            quarterly_ref = quarterly_price.merge(quarterly_vol[['Quarter', 'quarter_vol_previous']], on='Quarter')
            quarterly_ref = quarterly_ref[['Quarter', 'quarter_price_previous', 'quarter_vol_previous']]
            quarterly_ref.columns = ['Quarter', 'quarter_price', 'quarter_vol']
            
            df_temp = df_temp.merge(quarterly_ref, on='Quarter', how='left')
            df_temp['reference_price'] = df_temp['quarter_price']  # 1º DIA TRIMESTRE PASSADO
            df_temp['period_vol'] = df_temp['quarter_vol']  # ÚLTIMO DIA TRIMESTRE PASSADO
            
        elif self.regime == 'Y' or self.regime == 'A':  # ANUAL
            # ANUAL: Preço do 1º dia do ano PASSADO, vol do último dia do ano PASSADO
            df_temp['Year'] = df_temp['Date'].dt.year
            
            # Preço do primeiro dia de cada ano
            yearly_price = df_temp.groupby('Year')['Close'].first().reset_index()
            yearly_price.columns = ['Year', 'year_price']
            yearly_price['year_price_previous'] = yearly_price['year_price'].shift(1)
            
            # Volatilidade do último dia de cada ano
            yearly_vol = df_temp.groupby('Year')['hybrid_vol'].last().reset_index()
            yearly_vol.columns = ['Year', 'year_vol']
            yearly_vol['year_vol_previous'] = yearly_vol['year_vol'].shift(1)
            
            # Merge
            yearly_ref = yearly_price.merge(yearly_vol[['Year', 'year_vol_previous']], on='Year')
            yearly_ref = yearly_ref[['Year', 'year_price_previous', 'year_vol_previous']]
            yearly_ref.columns = ['Year', 'year_price', 'year_vol']
            
            df_temp = df_temp.merge(yearly_ref, on='Year', how='left')
            df_temp['reference_price'] = df_temp['year_price']  # 1º DIA ANO PASSADO
            df_temp['period_vol'] = df_temp['year_vol']  # ÚLTIMO DIA ANO PASSADO
        
        else:
            # Fallback para regime 'M' (mensal) - CORRIGIDO
            df_temp['Month'] = df_temp['Date'].dt.to_period('M')
            
            # Preço E volatilidade do ÚLTIMO dia de cada mês
            monthly_ref = df_temp.groupby('Month').agg({
                'Close': 'last',      # ÚLTIMO dia do mês
                'hybrid_vol': 'last'  # ÚLTIMO dia do mês
            }).reset_index()
            monthly_ref.columns = ['Month', 'month_price', 'month_vol']
            
            # Shiftar para pegar mês ANTERIOR
            monthly_ref['month_price_previous'] = monthly_ref['month_price'].shift(1)
            monthly_ref['month_vol_previous'] = monthly_ref['month_vol'].shift(1)
            
            # Merge
            df_temp = df_temp.merge(monthly_ref[['Month', 'month_price_previous', 'month_vol_previous']], on='Month')
            df_temp['reference_price'] = df_temp['month_price_previous']
            df_temp['period_vol'] = df_temp['month_vol_previous']
        
        # Preencher valores ausentes (fallback)
        df_temp['period_vol'].fillna(method='ffill', inplace=True)
        df_temp['reference_price'].fillna(method='ffill', inplace=True)
        df_temp['period_vol'].fillna(self.df['hybrid_vol'].mean(), inplace=True)
        df_temp['reference_price'].fillna(self.df['Close'], inplace=True)
        
        # Multiplicadores para diferenciação visual das bandas
        regime_multiplier = {
            'D': 0.5,    # Bandas mais estreitas (muda todo dia)
            'W': 0.75,   # Bandas intermediárias (muda toda semana)
            'M': 1.0,    # Bandas padrão (muda todo mês)
            'Q': 1.25,   # Bandas mais largas (muda todo trimestre)
            'Y': 1.5,    # Bandas mais largas (muda todo ano)
            'A': 1.5     # Anual (mesmo que Y)
        }
        
        multiplier = regime_multiplier.get(self.regime, 1.0)
        
        # Criar bandas com base na linha central e volatilidade do PERÍODO ANTERIOR
        for d in [2, 4]:
            self.df[f'banda_superior_{d}sigma'] = (
                df_temp['reference_price'] * (1 + d * df_temp['period_vol'] * multiplier)
            )
            self.df[f'banda_inferior_{d}sigma'] = (
                df_temp['reference_price'] * (1 - d * df_temp['period_vol'] * multiplier)
            )
        
        self.df['linha_central'] = df_temp['reference_price']
        
        # Preencher valores ausentes nas bandas
        band_columns = ['banda_superior_2sigma', 'banda_inferior_2sigma', 'linha_central', 
                    'banda_superior_4sigma', 'banda_inferior_4sigma']
        
        for col in band_columns:
            if col in self.df.columns:
                self.df[col].fillna(method='ffill', inplace=True)
                self.df[col].fillna(method='bfill', inplace=True)
                if self.df[col].isna().any():
                    vol_fallback = 0.02
                    multiplier_calc = 2 if '2sigma' in col else 4 if '4sigma' in col else 1
                    if 'superior' in col:
                        self.df[col].fillna(self.df['Close'] * (1 + multiplier_calc * vol_fallback), inplace=True)
                    elif 'inferior' in col:
                        self.df[col].fillna(self.df['Close'] * (1 - multiplier_calc * vol_fallback), inplace=True)
                    else:  # linha_central
                        self.df[col].fillna(self.df['Close'], inplace=True)
        
        return self
   
   def get_current_signals(self):
       """Sinais atuais de trading COM validação IV e lógica expandida de 4σ"""
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
       
       # ===== LÓGICA EXPANDIDA COM 4 DESVIOS =====
       sup_4sigma = signals['bandas']['superior_4σ']
       sup_2sigma = signals['bandas']['superior_2σ']
       central = signals['bandas']['linha_central']
       inf_2sigma = signals['bandas']['inferior_2σ']
       inf_4sigma = signals['bandas']['inferior_4σ']
       
       # Calcular distâncias percentuais para melhor análise
       dist_4sup = ((current_price - sup_4sigma) / sup_4sigma) * 100 if sup_4sigma > 0 else 0
       dist_2sup = ((current_price - sup_2sigma) / sup_2sigma) * 100 if sup_2sigma > 0 else 0
       dist_central = ((current_price - central) / central) * 100 if central > 0 else 0
       dist_2inf = ((current_price - inf_2sigma) / inf_2sigma) * 100 if inf_2sigma > 0 else 0
       dist_4inf = ((current_price - inf_4sigma) / inf_4sigma) * 100 if inf_4sigma > 0 else 0
       
       # CLASSIFICAÇÃO DETALHADA
       if current_price > sup_4sigma:
           # ===== ZONA EXTREMA SUPERIOR (>4σ) =====
           signals['position'] = '🔴 ZONA EXTREMA - Acima Banda 4σ'
           signals['position_detail'] = 'SOBRECOMPRADO EXTREMO'
           signals['risk_level'] = 'MUITO ALTO'
           signals['action_suggestion'] = 'VENDA IMEDIATA ou HEDGE URGENTE'
           signals['probability_reversal'] = 'MUITO ALTA (>80%)'
           signals['zone_color'] = '🔴'
           signals['zone_name'] = 'DANGER ZONE'
           
       elif current_price > sup_2sigma:
           # ===== ZONA SUPERIOR (2σ - 4σ) =====
           signals['position'] = '🟠 ZONA ALTA - Acima Banda 2σ'
           signals['position_detail'] = 'SOBRECOMPRADO FORTE'
           signals['risk_level'] = 'ALTO'
           signals['action_suggestion'] = 'REALIZAR LUCROS ou REDUZIR POSIÇÃO'
           signals['probability_reversal'] = 'ALTA (60-80%)'
           signals['zone_color'] = '🟠'
           signals['zone_name'] = 'OVERBOUGHT ZONE'
           
       elif current_price > central:
           # ===== ZONA SUPERIOR NEUTRA (Central - 2σ) =====
           signals['position'] = '🟡 METADE SUPERIOR - Bullish'
           signals['position_detail'] = 'TENDÊNCIA ALTA SAUDÁVEL'
           signals['risk_level'] = 'MODERADO'
           signals['action_suggestion'] = 'MANTER POSIÇÃO ou COMPRA PARCIAL'
           signals['probability_reversal'] = 'BAIXA (20-40%)'
           signals['zone_color'] = '🟡'
           signals['zone_name'] = 'BULLISH ZONE'
           
       elif current_price > inf_2sigma:
           # ===== ZONA INFERIOR NEUTRA (2σ inf - Central) =====
           signals['position'] = '🟡 METADE INFERIOR - Bearish'
           signals['position_detail'] = 'TENDÊNCIA BAIXA CONTROLADA'
           signals['risk_level'] = 'MODERADO'
           signals['action_suggestion'] = 'AGUARDAR ou COMPRA GRADUAL'
           signals['probability_reversal'] = 'BAIXA (20-40%)'
           signals['zone_color'] = '🟡'
           signals['zone_name'] = 'BEARISH ZONE'
           
       elif current_price > inf_4sigma:
           # ===== ZONA INFERIOR (4σ inf - 2σ inf) =====
           signals['position'] = '🟢 ZONA BAIXA - Abaixo Banda 2σ'
           signals['position_detail'] = 'SOBREVENDIDO FORTE'
           signals['risk_level'] = 'ALTO'
           signals['action_suggestion'] = 'OPORTUNIDADE DE COMPRA'
           signals['probability_reversal'] = 'ALTA (60-80%)'
           signals['zone_color'] = '🟢'
           signals['zone_name'] = 'OVERSOLD ZONE'
           
       else:
           # ===== ZONA EXTREMA INFERIOR (<4σ) =====
           signals['position'] = '🟢 ZONA EXTREMA - Abaixo Banda 4σ'
           signals['position_detail'] = 'SOBREVENDIDO EXTREMO'
           signals['risk_level'] = 'MUITO ALTO'
           signals['action_suggestion'] = 'COMPRA AGRESSIVA ou CONTRARIAN PLAY'
           signals['probability_reversal'] = 'MUITO ALTA (>80%)'
           signals['zone_color'] = '🟢'
           signals['zone_name'] = 'FIRE SALE ZONE'
       
       # ===== MÉTRICAS ADICIONAIS =====
       signals['distance_metrics'] = {
           'dist_4sigma_sup': round(dist_4sup, 2),
           'dist_2sigma_sup': round(dist_2sup, 2),
           'dist_central': round(dist_central, 2),
           'dist_2sigma_inf': round(dist_2inf, 2),
           'dist_4sigma_inf': round(dist_4inf, 2)
       }
       
       # ===== ALERTAS ESPECIAIS =====
       alerts = []
       
       # Alertas para zona extrema
       if abs(dist_4sup) < 2 and current_price < sup_4sigma:
           alerts.append("PRÓXIMO DA BANDA 4σ SUPERIOR - Prepare para reversão")
       elif abs(dist_4inf) < 2 and current_price > inf_4sigma:
           alerts.append("PRÓXIMO DA BANDA 4σ INFERIOR - Oportunidade se aproximando")
       
       # Alertas de momentum
       if current_price > sup_4sigma and signals['vol_regime'] == 'High':
           alerts.append("RISCO EXTREMO: Preço >4σ + Alta Volatilidade")
       elif current_price < inf_4sigma and signals['vol_regime'] == 'High':
           alerts.append("OPORTUNIDADE EXTREMA: Preço <4σ + Alta Volatilidade")
       
       # Alertas de tendência vs posição
       if current_price > sup_2sigma and signals['trend_regime'] == 'Bear':
           alerts.append("DIVERGÊNCIA: Preço alto mas tendência baixista")
       elif current_price < inf_2sigma and signals['trend_regime'] == 'Bull':
           alerts.append("DIVERGÊNCIA: Preço baixo mas tendência altista")
       
       signals['alerts'] = alerts
       
       # ===== SCORE DE OPORTUNIDADE (0-100) =====
       opportunity_score = 50  # Base neutra
       
       # Ajustar baseado na zona
       if current_price > sup_4sigma:
           opportunity_score = 10  # Muito baixo - venda
       elif current_price > sup_2sigma:
           opportunity_score = 25  # Baixo - realizar lucros
       elif current_price < inf_4sigma:
           opportunity_score = 90  # Muito alto - compra
       elif current_price < inf_2sigma:
           opportunity_score = 75  # Alto - oportunidade
       elif current_price > central:
           opportunity_score = 40  # Ligeiramente baixo
       else:
           opportunity_score = 60  # Ligeiramente alto
       
       # Ajustar por volatilidade
       if signals['vol_regime'] == 'High':
           if opportunity_score > 50:
               opportunity_score += 10  # Mais oportunidade em alta vol
           else:
               opportunity_score -= 10  # Mais risco em alta vol
       
       signals['opportunity_score'] = max(0, min(100, opportunity_score))
       
       # ===== VALIDAÇÃO IV (mantida) =====
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
        
        # Garantir que temos a coluna Date configurada corretamente
        if 'Date' not in df_plot.columns:
            df_plot.reset_index(inplace=True)
            # Se ainda não tem Date, usar o índice como data
            if 'Date' not in df_plot.columns:
                df_plot['Date'] = pd.date_range(start=pd.Timestamp.now() - pd.Timedelta(days=len(df_plot)), 
                                              periods=len(df_plot), freq='D')
        
        # Garantir que Date é datetime
        try:
            dates_formatted = pd.to_datetime(df_plot['Date']).dt.strftime('%Y-%m-%d').tolist()
        except Exception:
            # Se falhar, criar datas sequenciais
            dates_formatted = pd.date_range(start=pd.Timestamp.now() - pd.Timedelta(days=len(df_plot)), 
                                          periods=len(df_plot), freq='D').strftime('%Y-%m-%d').tolist()
        
        plot_data = {
            'ticker': self.ticker_display,
            'currency': currency,
            'dates': dates_formatted,
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
        self.token = "7gMd+LaFRJ6u6bmjgv9gxeGd5fAc6EHtpM4UoQ41tLivobEa4YTd5dA9xi00s/yd--NJ1uhr4hX+m6KeMsjdVfog==--ZTMyNzIyMjM3OGIxYThmN2YzNzdmZmYzOTZjY2RhYzc="
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
    
class TickerDetailsService:
    """Serviço para buscar detalhes específicos do ticker da API OpLab - VERSÃO FINAL"""
    
    def __init__(self):
        self.api_token = "7gMd+LaFRJ6u6bmjgv9gxeGd5fAc6EHtpM4UoQ41tLivobEa4YTd5dA9xi00s/yd--NJ1uhr4hX+m6KeMsjdVfog==--ZTMyNzIyMjM3OGIxYThmN2YzNzdmZmYzOTZjY2RhYzc="
        self.base_url = "https://api.oplab.com.br/v3/market/stocks"
        self.headers = {
            "Access-Token": self.api_token,
            "Content-Type": "application/json"
        }
    
    def get_ticker_details(self, ticker):
        try:
            # Limpar ticker (remover .SA se existir)
            ticker_clean = ticker.replace('.SA', '').upper()
            
            logging.info(f"Buscando detalhes para {ticker_clean} na API OpLab")
            
            # USAR MÉTODO IDÊNTICO AO CÓDIGO QUE FUNCIONA
            url = f"{self.base_url}/{ticker_clean}"
            
            # Headers idênticos
            headers = {
                "Access-Token": self.api_token,
                "Content-Type": "application/json"
            }
            
            # Parâmetros vazios (como no código que funciona)
            params = {}
            
            try:
                logging.info(f"Fazendo requisição para: {url}")
                
                # Requisição IDÊNTICA ao código que funciona
                response = requests.get(url, headers=headers, params=params)
                
                # Usar raise_for_status como no código que funciona
                response.raise_for_status()
                
                # Parse JSON
                stock_data = response.json()
                
                logging.info(f"✅ Resposta recebida com sucesso para {ticker_clean}")
                logging.info(f"   Symbol: {stock_data.get('symbol')}")
                logging.info(f"   IV Current: {stock_data.get('iv_current')}")
                
                return self._extract_ticker_data(stock_data, ticker_clean)
                
            except requests.exceptions.RequestException as e:
                logging.warning(f"Erro na requisição para {ticker_clean}: {e}")
                return self._create_fallback_data(ticker_clean)
                
            except json.JSONDecodeError as e:
                logging.warning(f"Erro ao decodificar JSON para {ticker_clean}: {e}")
                return self._create_fallback_data(ticker_clean)
            
        except Exception as e:
            logging.error(f"Erro geral ao buscar detalhes do ticker {ticker}: {e}")
            return self._create_fallback_data(ticker.replace('.SA', '').upper())
    
    def _extract_ticker_data(self, stock, ticker_clean):
        """
        Extrai dados específicos do stock usando a MESMA estrutura do código que funciona
        """
        try:
            # EXTRAIR DADOS EXATAMENTE COMO NO CÓDIGO QUE FUNCIONA
            ticker_data = {
                # Identificação básica
                'symbol': stock.get('symbol'),
                'name': stock.get('name'),
                'type': stock.get('type'),
                'category': stock.get('category'),
                'updated_at': stock.get('updated_at'),
                
                # Volume e negócios (EXATAMENTE como no código que funciona)
                'volume': stock.get('volume'),
                'financial_volume': stock.get('financial_volume'),
                'trades': stock.get('trades'),
                
                # Bid/Ask (EXATAMENTE como no código que funciona)
                'bid': stock.get('bid'),
                'ask': stock.get('ask'),
                
                # Dados de preço adicionais
                'open': stock.get('open'),
                'high': stock.get('high'),
                'low': stock.get('low'),
                'close': stock.get('close'),
                'variation': stock.get('variation', 0),
                
                # Volatilidade Implícita COMPLETA (EXATAMENTE como no código que funciona)
                'iv_current': stock.get('iv_current'),
                'iv_1y_rank': stock.get('iv_1y_rank'),
                'iv_1y_percentile': stock.get('iv_1y_percentile'),
                'iv_1y_max': stock.get('iv_1y_max'),
                'iv_1y_min': stock.get('iv_1y_min'),
                'iv_6m_max': stock.get('iv_6m_max'),
                'iv_6m_min': stock.get('iv_6m_min'),
                'iv_6m_percentile': stock.get('iv_6m_percentile'),
                'iv_6m_rank': stock.get('iv_6m_rank'),
                
                # Volatilidade EWMA COMPLETA (EXATAMENTE como no código que funciona)
                'ewma_current': stock.get('ewma_current'),
                'ewma_1y_percentile': stock.get('ewma_1y_percentile'),
                'ewma_1y_rank': stock.get('ewma_1y_rank'),
                'ewma_1y_max': stock.get('ewma_1y_max'),
                'ewma_1y_min': stock.get('ewma_1y_min'),
                'ewma_6m_percentile': stock.get('ewma_6m_percentile'),
                'ewma_6m_rank': stock.get('ewma_6m_rank'),
                
                # Mercado (EXATAMENTE como no código que funciona)
                'correl_ibov': stock.get('correl_ibov'),
                'beta_ibov': stock.get('beta_ibov'),
                'has_options': stock.get('has_options', False),
                
                # Técnicos (EXATAMENTE como no código que funciona)
                'short_term_trend': stock.get('short_term_trend'),
                'middle_term_trend': stock.get('middle_term_trend'),
                'stdv_5d': stock.get('stdv_5d'),
                'stdv_1y': stock.get('stdv_1y'),
                'semi_return_1y': stock.get('semi_return_1y'),
                'garch11_1y': stock.get('garch11_1y'),
                
                # Campos adicionais
                'isin': stock.get('isin'),
                'cnpj': stock.get('cnpj'),
                'contract_size': stock.get('contract_size'),
                'created_at': stock.get('created_at'),
                'entropy': stock.get('entropy'),
                'oplab_score': stock.get('oplab_score'),
                'm9_m21': stock.get('m9_m21'),
                
                # Indicadores de sucesso
                'is_fallback': False,
                'data_source': 'oplab_api_success'
            }
            
            logging.info(f"✅ Dados extraídos com sucesso para {ticker_clean}")
            logging.info(f"   IV Current: {ticker_data.get('iv_current')}")
            logging.info(f"   IV Rank 1Y: {ticker_data.get('iv_1y_rank')}")
            logging.info(f"   IV Percentile 1Y: {ticker_data.get('iv_1y_percentile')}")
            logging.info(f"   Volume: {ticker_data.get('volume')}")
            logging.info(f"   Has Options: {ticker_data.get('has_options')}")
            
            return ticker_data
            
        except Exception as e:
            logging.error(f"Erro ao extrair dados do ticker {ticker_clean}: {e}")
            return self._create_fallback_data(ticker_clean)
    
    def _create_fallback_data(self, ticker_clean):
        """
        Cria dados básicos quando a API falha
        """
        logging.info(f"Criando dados fallback para {ticker_clean}")
        
        return {
            'symbol': ticker_clean,
            'name': f'{ticker_clean} - API Temporariamente Indisponível',
            'type': 'STOCK',
            'category': 'VISTA',
            'updated_at': datetime.now().isoformat(),
            
            # Todos os campos como None para manter consistência
            'volume': None,
            'financial_volume': None,
            'trades': None,
            'bid': None,
            'ask': None,
            'open': None,
            'high': None,
            'low': None,
            'close': None,
            'variation': None,
            
            # Volatilidade Implícita
            'iv_current': None,
            'iv_1y_rank': None,
            'iv_1y_percentile': None,
            'iv_1y_max': None,
            'iv_1y_min': None,
            'iv_6m_max': None,
            'iv_6m_min': None,
            'iv_6m_percentile': None,
            'iv_6m_rank': None,
            
            # Volatilidade EWMA
            'ewma_current': None,
            'ewma_1y_percentile': None,
            'ewma_1y_rank': None,
            'ewma_1y_max': None,
            'ewma_1y_min': None,
            'ewma_6m_percentile': None,
            'ewma_6m_rank': None,
            
            # Mercado
            'correl_ibov': None,
            'beta_ibov': None,
            'has_options': False,
            
            # Técnicos
            'short_term_trend': None,
            'middle_term_trend': None,
            'stdv_5d': None,
            'stdv_1y': None,
            'semi_return_1y': None,
            'garch11_1y': None,
            
            # Campos adicionais
            'isin': None,
            'cnpj': None,
            'contract_size': None,
            'created_at': None,
            'entropy': None,
            'oplab_score': None,
            'm9_m21': None,
            
            # Indicadores de fallback
            'is_fallback': True,
            'fallback_reason': 'API OpLab temporariamente indisponível',
            'data_source': 'fallback'
        }
    
    def format_ticker_summary(self, ticker_data):
        """
        Formata os dados do ticker em um resumo organizado
        """
        if not ticker_data:
            return None
        
        try:
            def format_percentage(value, decimals=2):
                if value is None:
                    return None
                try:
                    # A API OpLab retorna valores já em formato correto
                    # IV Current vem como 0.2926 (que é 29.26%)
                    # IV Rank vem como 30.4 (que é 30.4%)
                    
                    float_val = float(value)
                    
                    # Se o valor está entre 0 e 1, assumir que é decimal e converter para %
                    if 0 <= float_val <= 1:
                        return round(float_val * 100, decimals)
                    # Se maior que 1, assumir que já está em %
                    else:
                        return round(float_val, decimals)
                except:
                    return None
            
            def format_currency(value):
                if value is None:
                    return None
                try:
                    return round(float(value), 2)
                except:
                    return None
            
            # Verificar se é fallback
            is_fallback = ticker_data.get('is_fallback', False)
            fallback_reason = ticker_data.get('fallback_reason', '')
            
            # Interpretar IV Rank para status
            iv_rank = ticker_data.get('iv_1y_rank')
            if iv_rank is not None:
                try:
                    iv_rank_val = float(iv_rank)
                    # Se IV Rank está entre 0-1, converter para %
                    if 0 <= iv_rank_val <= 1:
                        iv_rank_pct = iv_rank_val * 100
                    else:
                        iv_rank_pct = iv_rank_val
                    
                    if iv_rank_pct < 20:
                        iv_status = "MUITO BAIXA"
                        iv_color = "🟢"
                    elif iv_rank_pct < 50:
                        iv_status = "BAIXA"
                        iv_color = "🟡"
                    elif iv_rank_pct < 80:
                        iv_status = "ALTA"
                        iv_color = "🟠"
                    else:
                        iv_status = "MUITO ALTA"
                        iv_color = "🔴"
                except:
                    iv_status = "INVÁLIDA"
                    iv_color = "⚪"
            else:
                iv_status = "INDISPONÍVEL" if is_fallback else "N/A"
                iv_color = "⚪"
            
            # Interpretar correlação
            correl = ticker_data.get('correl_ibov')
            if correl is not None:
                try:
                    correl_val = float(correl)
                    if abs(correl_val) < 0.3:
                        correl_status = "BAIXA"
                    elif abs(correl_val) < 0.7:
                        correl_status = "MODERADA"
                    else:
                        correl_status = "ALTA"
                except:
                    correl_status = "INVÁLIDA"
            else:
                correl_status = "INDISPONÍVEL" if is_fallback else "N/A"
            
            summary = {
                'basic_info': {
                    'symbol': ticker_data.get('symbol'),
                    'name': ticker_data.get('name'),
                    'type': ticker_data.get('type'),
                    'has_options': ticker_data.get('has_options', False),
                    'last_update': ticker_data.get('updated_at'),
                    'is_fallback': is_fallback,
                    'fallback_reason': fallback_reason,
                    'data_source': ticker_data.get('data_source', 'unknown')
                },
                
                'price_data': {
                    'open': format_currency(ticker_data.get('open')),
                    'high': format_currency(ticker_data.get('high')),
                    'low': format_currency(ticker_data.get('low')),
                    'close': format_currency(ticker_data.get('close')),
                    'variation': format_percentage(ticker_data.get('variation')),
                    'volume': ticker_data.get('volume'),
                    'financial_volume': format_currency(ticker_data.get('financial_volume')),
                    'trades': ticker_data.get('trades'),
                    'bid': format_currency(ticker_data.get('bid')),
                    'ask': format_currency(ticker_data.get('ask'))
                },
                
                'volatility_iv': {
                    'iv_current': format_percentage(ticker_data.get('iv_current')),
                    'iv_1y_rank': format_percentage(ticker_data.get('iv_1y_rank')),
                    'iv_1y_percentile': format_percentage(ticker_data.get('iv_1y_percentile')),
                    'iv_status': iv_status,
                    'iv_color': iv_color,
                    'iv_1y_range': {
                        'min': format_percentage(ticker_data.get('iv_1y_min')),
                        'max': format_percentage(ticker_data.get('iv_1y_max'))
                    },
                    'iv_6m_range': {
                        'min': format_percentage(ticker_data.get('iv_6m_min')),
                        'max': format_percentage(ticker_data.get('iv_6m_max'))
                    },
                    'iv_6m_percentile': format_percentage(ticker_data.get('iv_6m_percentile')),
                    'iv_6m_rank': format_percentage(ticker_data.get('iv_6m_rank'))
                },
                
                'market_metrics': {
                    'correl_ibov': format_percentage(ticker_data.get('correl_ibov')) if ticker_data.get('correl_ibov') else None,
                    'correl_status': correl_status,
                    'beta_ibov': format_currency(ticker_data.get('beta_ibov')),
                    'ewma_current': format_percentage(ticker_data.get('ewma_current')),
                    'ewma_1y_percentile': format_percentage(ticker_data.get('ewma_1y_percentile')),
                    'ewma_1y_rank': format_percentage(ticker_data.get('ewma_1y_rank')),
                    'stdv_5d': format_percentage(ticker_data.get('stdv_5d')),
                    'stdv_1y': format_percentage(ticker_data.get('stdv_1y')),
                    'entropy': ticker_data.get('entropy')
                },
                
                'technical_indicators': {
                    'short_term_trend': ticker_data.get('short_term_trend'),
                    'middle_term_trend': ticker_data.get('middle_term_trend'),
                    'semi_return_1y': format_percentage(ticker_data.get('semi_return_1y')),
                    'garch11_1y': format_percentage(ticker_data.get('garch11_1y')),
                    'oplab_score': ticker_data.get('oplab_score'),
                    'm9_m21': ticker_data.get('m9_m21')
                }
            }
            
            return summary
            
        except Exception as e:
            logging.error(f"Erro ao formatar resumo do ticker: {e}")
            return None

class BandasProService:
    """Serviço principal que orquestra todas as análises"""
    
    def __init__(self):
        self.bands_system = None
        self.flow_system = GeminiiFlowTracker()
        self.ticker_details_service = TickerDetailsService() 
    
    def analyze_bands(self, ticker, period='2y', regime='M'):
        
        logging.info(f"Iniciando análise de bandas para {ticker}")
        
        self.bands_system = HybridVolatilityBands(ticker, period, regime)
        self.bands_system.load_data()
        
        # CORREÇÃO: Verificar se self.bands_system.df existe e não está vazio
        if self.bands_system.df is None or self.bands_system.df.empty:
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
    
    def analyze_complete(self, ticker, period='2y', flow_days=30, regime='M'):
        """Executa análise completa: Bandas + Flow"""
        logging.info(f"Iniciando análise completa para {ticker}")
        
        # Análise das Bandas
        bands_result = self.analyze_bands(ticker, period, regime)
        
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
                    recommendation = " MOVIMENTO CONFIÁVEL: IV confirma rompimento genuíno"
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
                recommendation = " PREPARAR: Movimento forte se aproximando"
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

    def get_ticker_details(self, ticker):
        logging.info(f"Buscando detalhes completos para {ticker}")
        
        try:
            # Buscar dados brutos
            raw_data = self.ticker_details_service.get_ticker_details(ticker)
            
            if not raw_data:
                raise ValueError(f'Ticker {ticker} não encontrado ou dados indisponíveis')
            
            # Formatar dados
            formatted_data = self.ticker_details_service.format_ticker_summary(raw_data)
            
            if not formatted_data:
                raise ValueError(f'Erro ao processar dados do ticker {ticker}')
            
            return {
                'ticker': ticker.replace('.SA', ''),
                'data': formatted_data,
                'raw_data': raw_data  # Incluir dados brutos para debug se necessário
            }
            
        except Exception as e:
            logging.error(f"Erro ao buscar detalhes do ticker {ticker}: {e}")
            raise    
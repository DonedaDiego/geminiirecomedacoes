# vol_regimes_service.py - Hybrid Volatility Bands (GARCH + XGBoost)

import numpy as np
import pandas as pd
import yfinance as yf
from arch import arch_model
import xgboost as xgb
from sklearn.preprocessing import RobustScaler
import plotly.graph_objects as go
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, time, timedelta
import warnings

warnings.filterwarnings('ignore')


class VolatilityRegimesService:
    def __init__(self, timeframe=3):  # NOVO: timeframe padrão = 3 (MENSAL)
        self.setup_logging()
        self.scaler = RobustScaler()
        self.xgb_model = None
        self.timeframe = timeframe  # NOVO
        self.use_shift = False  # NOVO
        
        # NOVO: Configs idênticos ao MetaTrader
        self.configs = {
            1: {
                'name': 'DIARIO',
                'regime': 'D',
                'garch_window': 5,
                'vol_windows': [3, 5, 10, 15],
                'feature_windows': [5, 10, 15, 30],
                'lags': [1, 2, 3],
                'regime_window': 20,
                'regime_long': 60,
                'period_col': 'Date',
                'period_freq': 'D',
                'multiplier': 0.5
            },
            2: {
                'name': 'SEMANAL',
                'regime': 'W',
                'garch_window': 10,
                'vol_windows': [3, 5, 10, 20],
                'feature_windows': [5, 10, 20, 60],
                'lags': [1, 2, 5],
                'regime_window': 30,
                'regime_long': 252,
                'period_col': 'Week',
                'period_freq': 'W',
                'multiplier': 0.75
            },
            3: {
                'name': 'MENSAL',
                'regime': 'M',
                'garch_window': 22,
                'vol_windows': [10, 20, 40, 60],
                'feature_windows': [20, 40, 60, 120],
                'lags': [1, 3, 5],
                'regime_window': 60,
                'regime_long': 504,
                'period_col': 'Month',
                'period_freq': 'M',
                'multiplier': 1.0
            }
        }
        
        self.config = self.configs[self.timeframe]
        
    def setup_logging(self):
        """Configurar logging"""
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    # NOVO: Método idêntico ao MetaTrader
    def determine_reference_period(self, data: pd.DataFrame):
        """
        LOGICA IDENTICA AO METATRADER:
        DIARIO/SEMANAL: shift(1) DENTRO do pregao, sem shift FORA
        MENSAL: shift(1) SEMPRE, exceto ultimo dia util FORA do pregao
        """
        now = datetime.now()
        market_open = time(9, 0, 0)
        market_close = time(18, 0, 0)
        
        ultimo_candle_date = data['Date'].iloc[-1].date()
        hoje = now.date()
        is_weekday = now.weekday() < 5
        
        if self.timeframe == 1:
            esta_dentro_pregao = (is_weekday and 
                                ultimo_candle_date == hoje and 
                                market_open <= now.time() <= market_close)
            
            if esta_dentro_pregao:
                self.use_shift = True
                msg = "DIARIO: Dentro do pregao - usando shift(1)"
            else:
                self.use_shift = False
                msg = "DIARIO: Fora do pregao - usando candle completo (sem shift)"
        
        elif self.timeframe == 2:
            is_friday = now.weekday() == 4
            ultimo_is_friday = data['Date'].iloc[-1].weekday() == 4
            
            esta_dentro_pregao_semanal = (is_friday and 
                                        ultimo_candle_date == hoje and 
                                        market_open <= now.time() <= market_close)
            
            if esta_dentro_pregao_semanal:
                self.use_shift = True
                msg = "SEMANAL: Dentro do pregao sexta - usando shift(1)"
            else:
                self.use_shift = False
                msg = "SEMANAL: Fora do pregao - usando semana completa (sem shift)"
        
        elif self.timeframe == 3:
            ultimo_dia_util_mes = self.is_last_business_day_of_month(hoje)
            
            esta_fora_pregao_ultimo_dia = (ultimo_dia_util_mes and 
                                        ultimo_candle_date == hoje and 
                                        not (market_open <= now.time() <= market_close))
            
            if esta_fora_pregao_ultimo_dia:
                self.use_shift = False
                msg = "MENSAL: Ultimo dia util fora do pregao - usando mes atual completo (sem shift)"
            else:
                self.use_shift = True
                msg = "MENSAL: Sempre usar mes anterior completo (shift 1)"
        
        self.logger.info(msg)
        return self.use_shift
    
    # NOVO: Método idêntico ao MetaTrader
    def is_last_business_day_of_month(self, date):
        """Verifica se a data e o ultimo dia util do mes"""
        mes_atual = date.month
        ano_atual = date.year
        
        if mes_atual == 12:
            proximo_mes = 1
            proximo_ano = ano_atual + 1
        else:
            proximo_mes = mes_atual + 1
            proximo_ano = ano_atual
        
        primeiro_dia_proximo_mes = datetime(proximo_ano, proximo_mes, 1).date()
        
        dia_teste = date
        while dia_teste < primeiro_dia_proximo_mes:
            if dia_teste.weekday() < 5:
                ultimo_dia_util = dia_teste
            dia_teste += timedelta(days=1)
        
        return date == ultimo_dia_util
    
    def convert_to_json_safe(self, value):
        """Converter qualquer tipo para JSON-safe de forma robusta"""
        if value is None or pd.isna(value):
            return None
        
        if isinstance(value, (np.integer, np.int8, np.int16, np.int32, np.int64)):
            return int(value)
        elif isinstance(value, (np.floating, np.float16, np.float32, np.float64)):
            if np.isnan(value) or np.isinf(value):
                return 0.0
            return float(value)
        elif isinstance(value, np.bool_):
            return bool(value)
        elif isinstance(value, np.ndarray):
            return [self.convert_to_json_safe(item) for item in value.tolist()]
        elif isinstance(value, pd.Timestamp):
            return value.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(value, dict):
            return {k: self.convert_to_json_safe(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.convert_to_json_safe(item) for item in value]
        else:
            return value
    
    def get_stock_data(self, ticker: str, period: str = "2y") -> Optional[pd.DataFrame]:
        try:
            logging.info(f"Carregando dados para {ticker}")
            
            ticker_to_use = ticker
            if len(ticker) <= 6 and not ticker.endswith('.SA') and '-' not in ticker:
                ticker_to_use = ticker + '.SA'
            
            stock = yf.Ticker(ticker_to_use)
            data = stock.history(period=period)
            
            if data is None or data.empty:
                if ticker_to_use != ticker:
                    logging.warning(f"Tentando ticker original: {ticker}")
                    stock = yf.Ticker(ticker)
                    data = stock.history(period=period)
                
                if data is None or data.empty:
                    raise ValueError(f"Nenhum dado encontrado para {ticker}")
            
            if len(data) < 50:
                raise ValueError(f"Dados insuficientes para {ticker} (apenas {len(data)} registros)")
            
            required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            missing_columns = [col for col in required_columns if col not in data.columns]
            if missing_columns:
                raise ValueError(f"Colunas ausentes nos dados: {missing_columns}")
            
            data.reset_index(inplace=True)
            
            if 'Date' in data.columns:
                data['Date'] = pd.to_datetime(data['Date'])
            else:
                data['Date'] = data.index if hasattr(data.index, 'date') else pd.date_range(start=pd.Timestamp.now() - pd.Timedelta(days=len(data)), periods=len(data), freq='D')
            
            data['Returns'] = data['Close'].pct_change()
            data['Log_Returns'] = np.log(data['Close'] / data['Close'].shift(1))
            
            data = data[(data['Open'] > 0) & 
                        (data['High'] > 0) & 
                        (data['Low'] > 0) & 
                        (data['Close'] > 0)]
            
            initial_len = len(data)
            data = data.dropna()
            final_len = len(data)
            
            if final_len < 30:
                raise ValueError(f"Dados insuficientes após limpeza: {final_len} registros")
            
            if initial_len != final_len:
                logging.warning(f"Removidos {initial_len - final_len} registros com dados nulos")
            
            # NOVO: Determinar período de referência após carregar dados
            self.determine_reference_period(data)
            
            logging.info(f"Dados carregados com sucesso: {len(data)} registros para {ticker}")
            return data
            
        except ValueError as e:
            error_msg = f"Erro de validação ao carregar dados para {ticker}: {str(e)}"
            logging.error(error_msg)
            return None
            
        except Exception as e:
            error_msg = f"Erro inesperado ao carregar dados para {ticker}: {str(e)}"
            logging.error(error_msg)
            logging.error(f"Tipo do erro: {type(e).__name__}")
            return None
    
    def calculate_base_volatility(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calcular volatilidade base (GARCH e Realized)"""
        df = data.copy()
        
        try:
            returns_data = df['Log_Returns'].dropna() * 100
            if len(returns_data) < 50:
                raise ValueError("Dados insuficientes para modelo GARCH")
            
            garch_model = arch_model(returns_data, vol='Garch', p=1, q=1, dist='Normal')
            garch_result = garch_model.fit(disp='off')
            
            garch_vol = garch_result.conditional_volatility / 100
            
            if len(garch_vol) < len(df):
                vol_mean = garch_vol.mean()
                missing_count = len(df) - len(garch_vol)
                garch_vol = np.concatenate([np.full(missing_count, vol_mean), garch_vol])
            
            df['garch_vol'] = garch_vol[:len(df)]
            
        except Exception as e:
            self.logger.warning(f"GARCH falhou: {e}. Usando fallback com rolling std.")
            df['garch_vol'] = df['Returns'].rolling(20, min_periods=5).std().fillna(0.02)
        
        # CORRIGIDO: Usar vol_windows do config
        for window in self.config['vol_windows']:
            df[f'realized_vol_{window}d'] = (
                df['Returns'].rolling(window=window, min_periods=1)
                .apply(lambda x: np.sqrt(np.sum(x**2)) if len(x) > 0 else 0.02)
            )
        
        return df
    
    def engineer_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Engenharia de features para XGBoost"""
        try:
            df = data.copy()
            
            # CORRIGIDO: Usar feature_windows do config
            for window in self.config['feature_windows']:
                df[f'vol_std_{window}d'] = df['Returns'].rolling(window, min_periods=1).std()
            
            # CORRIGIDO: Usar lags do config
            for lag in self.config['lags']:
                df[f'garch_lag_{lag}'] = df['garch_vol'].shift(lag)
                df[f'returns_lag_{lag}'] = df['Returns'].shift(lag)
            
            df['daily_range'] = (df['High'] - df['Low']) / df['Close']
            df['price_momentum_5d'] = df['Close'] / df['Close'].shift(5) - 1
            
            if 'Volume' in df.columns and df['Volume'].sum() > 0:
                vol_ma = max(20, self.config['feature_windows'][0])
                df[f'volume_ma_{vol_ma}'] = df['Volume'].rolling(vol_ma, min_periods=1).mean()
                df['volume_ratio'] = df['Volume'] / df[f'volume_ma_{vol_ma}']
                df['volume_ratio'].fillna(1, inplace=True)
            else:
                df['volume_ratio'] = 1
            
            sma_short = max(50, self.config['feature_windows'][1])
            sma_long = max(200, self.config['feature_windows'][3])
            
            df[f'sma_{sma_short}'] = df['Close'].rolling(sma_short, min_periods=1).mean()
            df[f'sma_{sma_long}'] = df['Close'].rolling(sma_long, min_periods=1).mean()
            df['trend_regime'] = np.where(df[f'sma_{sma_short}'] > df[f'sma_{sma_long}'], 1, 0)
            
            # CORRIGIDO: Usar regime_window do config
            regime_window = self.config['regime_window']
            df['vol_regime'] = np.where(df['garch_vol'] > df['garch_vol'].rolling(regime_window, min_periods=1).mean(), 1, 0)
            
            # CORRIGIDO: Usar regime_long do config
            vol_percentile_window = max(252, self.config['regime_long'] // 2)
            df['vol_percentile'] = df['garch_vol'].rolling(vol_percentile_window, min_periods=20).rank(pct=True)
            
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = df[col].ffill()                              
                    df[col] = df[col].bfill()                                
                    df[col] = df[col].fillna(0)

            return df
        
        except Exception as e:
            self.logger.error(f"Erro na engenharia de features: {e}")
            return data
    
    def train_xgboost(self, data: pd.DataFrame) -> pd.DataFrame:
        """Treinar modelo XGBoost para volatilidade"""
        try:
            # CORRIGIDO: Construir features dinamicamente baseado no config
            vol_features = [f'realized_vol_{w}d' for w in self.config['vol_windows']]
            std_features = [f'vol_std_{w}d' for w in self.config['feature_windows']]
            lag_features = []
            
            for lag in self.config['lags']:
                lag_features.extend([f'garch_lag_{lag}', f'returns_lag_{lag}'])
            
            feature_cols = (lag_features + vol_features + std_features + 
                           ['vol_percentile', 'vol_regime', 'daily_range', 
                            'price_momentum_5d', 'volume_ratio', 'trend_regime'])
            
            available_features = [col for col in feature_cols if col in data.columns]
            if len(available_features) < len(feature_cols) * 0.7:
                self.logger.warning(f"Poucas features disponíveis para XGBoost. Usando apenas volatilidade GARCH.")
                data['xgb_vol'] = data['garch_vol']
                return data
            
            df_ml = data[available_features + ['garch_vol']].copy()
            df_ml.dropna(inplace=True)
            
            if len(df_ml) < 50:
                self.logger.warning("Dados insuficientes para XGBoost. Usando apenas volatilidade GARCH.")
                data['xgb_vol'] = data['garch_vol']
                return data
            
            X = df_ml[available_features]
            y = df_ml['garch_vol']
            
            X_scaled = self.scaler.fit_transform(X)
            X_scaled = pd.DataFrame(X_scaled, columns=available_features, index=X.index)
            
            train_size = int(len(X_scaled) * 0.8)
            X_train, X_test = X_scaled[:train_size], X_scaled[train_size:]
            y_train, y_test = y[:train_size], y[train_size:]
            
            self.xgb_model = xgb.XGBRegressor(
                n_estimators=100,
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
            
            data['xgb_vol'] = data['garch_vol']
            test_indices = df_ml.index[train_size:]
            data.loc[test_indices, 'xgb_vol'] = xgb_pred
            
            return data
        except Exception as e:
            self.logger.error(f"Erro no XGBoost: {e}")
            data['xgb_vol'] = data['garch_vol']
            return data
    
    def create_hybrid_model(self, data: pd.DataFrame) -> pd.DataFrame:
        """Criar modelo híbrido GARCH + XGBoost"""
        df = data.copy()
        
        # CORRIGIDO: Usar regime_window e regime_long do config
        regime_window = self.config['regime_window']
        regime_long = self.config['regime_long']
        
        df['vol_regime_adaptive'] = df['garch_vol'].rolling(regime_window, min_periods=5).std()
        df['vol_regime_normalized'] = (
            df['vol_regime_adaptive'] / df['vol_regime_adaptive'].rolling(regime_long, min_periods=20).mean()
        )
        df['vol_regime_normalized'].fillna(1.0, inplace=True)
        
        # CORRIGIDO: Pesos dinâmicos baseados no timeframe (igual ao MetaTrader)
        if self.timeframe == 1:
            base_garch = 0.7
            variacao = 0.2
            df['weight_garch'] = np.clip(
                base_garch + variacao * (df['vol_regime_normalized'] - 1), 
                0.5, 0.8
            )
            
        elif self.timeframe == 2:
            base_garch = 0.5
            variacao = 0.3
            df['weight_garch'] = np.clip(
                base_garch + variacao * (df['vol_regime_normalized'] - 1), 
                0.3, 0.7
            )
            
        elif self.timeframe == 3:
            base_garch = 0.4
            variacao = 0.3
            df['weight_garch'] = np.clip(
                base_garch + variacao * (df['vol_regime_normalized'] - 1), 
                0.2, 0.6
            )
        
        df['weight_xgb'] = 1 - df['weight_garch']
        
        df['hybrid_vol'] = (
            df['weight_garch'] * df['garch_vol'] + 
            df['weight_xgb'] * df['xgb_vol']
        )
        
        df['hybrid_vol'].fillna(df['garch_vol'], inplace=True)
        df['hybrid_vol'].fillna(0.02, inplace=True)
        df['hybrid_vol'] = np.maximum(df['hybrid_vol'], 0.001)
        
        return df
    
    def create_bands(self, data: pd.DataFrame) -> pd.DataFrame:
        """CORRIGIDO: Criar bandas com lógica idêntica ao MetaTrader"""
        df_temp = data.copy()
        df_temp['reference_price'] = np.nan
        df_temp['period_vol'] = np.nan
        
        if 'Date' not in df_temp.columns:
            df_temp.reset_index(inplace=True)
        df_temp['Date'] = pd.to_datetime(df_temp['Date'])
        
        # LOGICA IDENTICA AO METATRADER
        if self.timeframe == 1:
            if self.use_shift:
                df_temp['reference_price'] = df_temp['Close'].shift(1)
                df_temp['period_vol'] = df_temp['hybrid_vol'].shift(1)
            else:
                df_temp['reference_price'] = df_temp['Close']
                df_temp['period_vol'] = df_temp['hybrid_vol']
            
        elif self.timeframe == 2:
            df_temp = df_temp.sort_values('Date')
            df_temp['Week'] = df_temp['Date'].dt.to_period('W-FRI')
            
            weekly_ref = df_temp.groupby('Week').agg({
                'Close': 'last',
                'hybrid_vol': 'last',
                'Date': 'last'
            }).reset_index()
            weekly_ref.columns = ['Week', 'week_price', 'week_vol', 'week_date']
            
            weekly_ref['is_friday'] = weekly_ref['week_date'].dt.weekday == 4
            complete_weeks = weekly_ref[weekly_ref['is_friday']].copy()
            
            if self.use_shift:
                complete_weeks['week_price_ref'] = complete_weeks['week_price'].shift(1)
                complete_weeks['week_vol_ref'] = complete_weeks['week_vol'].shift(1)
            else:
                complete_weeks['week_price_ref'] = complete_weeks['week_price']
                complete_weeks['week_vol_ref'] = complete_weeks['week_vol']
            
            df_temp = df_temp.merge(
                complete_weeks[['Week', 'week_price_ref', 'week_vol_ref']], 
                on='Week', 
                how='left'
            )
            
            df_temp['week_price_ref'] = df_temp['week_price_ref'].ffill()
            df_temp['week_vol_ref'] = df_temp['week_vol_ref'].ffill()
            
            df_temp['reference_price'] = df_temp['week_price_ref']
            df_temp['period_vol'] = df_temp['week_vol_ref']
            
        elif self.timeframe == 3:
            df_temp['Month'] = df_temp['Date'].dt.to_period('M')
            
            monthly_ref = df_temp.groupby('Month').agg({
                'Close': 'last',
                'hybrid_vol': 'last'
            }).reset_index()
            monthly_ref.columns = ['Month', 'month_price', 'month_vol']
            
            if self.use_shift:
                monthly_ref['month_price_ref'] = monthly_ref['month_price'].shift(1)
                monthly_ref['month_vol_ref'] = monthly_ref['month_vol'].shift(1)
            else:
                monthly_ref['month_price_ref'] = monthly_ref['month_price']
                monthly_ref['month_vol_ref'] = monthly_ref['month_vol']
            
            df_temp = df_temp.merge(monthly_ref[['Month', 'month_price_ref', 'month_vol_ref']], on='Month', how='left')
            df_temp['reference_price'] = df_temp['month_price_ref']
            df_temp['period_vol'] = df_temp['month_vol_ref']
        
        df_temp['period_vol'] = df_temp['period_vol'].ffill()
        df_temp['reference_price'] = df_temp['reference_price'].ffill()
        df_temp['period_vol'] = df_temp['period_vol'].fillna(data['hybrid_vol'].mean())
        df_temp['reference_price'] = df_temp['reference_price'].fillna(data['Close'])
        
        # CORRIGIDO: Usar multiplier do config
        multiplier = self.config['multiplier']
        
        for d in [2, 4]:
            data[f'banda_superior_{d}sigma'] = (
                df_temp['reference_price'] * (1 + d * df_temp['period_vol'] * multiplier)
            )
            data[f'banda_inferior_{d}sigma'] = (
                df_temp['reference_price'] * (1 - d * df_temp['period_vol'] * multiplier)
            )
        
        data['linha_central'] = df_temp['reference_price']
        
        band_columns = ['banda_superior_2sigma', 'banda_inferior_2sigma', 'linha_central', 
                    'banda_superior_4sigma', 'banda_inferior_4sigma']
        
        for col in band_columns:
            if col in data.columns:
                data[col] = data[col].ffill()
                data[col] = data[col].bfill()
                if data[col].isna().any():
                    vol_fallback = 0.02
                    multiplier_calc = 2 if '2sigma' in col else 4 if '4sigma' in col else 1
                    if 'superior' in col:
                        data[col].fillna(data['Close'] * (1 + multiplier_calc * vol_fallback), inplace=True)
                    elif 'inferior' in col:
                        data[col].fillna(data['Close'] * (1 - multiplier_calc * vol_fallback), inplace=True)
                    else:
                        data[col].fillna(data['Close'], inplace=True)
        
        return data
    
    def get_current_signals(self, data: pd.DataFrame, ticker: str) -> Dict:
        """Gerar sinais atuais de trading"""
        latest = data.iloc[-1]
        current_price = latest['Close']
        
        vol_fallback = latest['hybrid_vol'] if not pd.isna(latest['hybrid_vol']) else 0.02
        
        def safe_get(col_name, fallback_value):
            value = latest[col_name] if not pd.isna(latest[col_name]) else fallback_value
            return value
        
        # CORRIGIDO: Nomes das bandas iguais ao MetaTrader
        bandas = {
            'linha_central': safe_get('linha_central', current_price),
            'resistencia_2sigma': safe_get('banda_superior_2sigma', current_price * (1 + 2 * vol_fallback)),
            'suporte_2sigma': safe_get('banda_inferior_2sigma', current_price * (1 - 2 * vol_fallback)),
            'resistencia_4sigma': safe_get('banda_superior_4sigma', current_price * (1 + 4 * vol_fallback)),
            'suporte_4sigma': safe_get('banda_inferior_4sigma', current_price * (1 - 4 * vol_fallback)),
        }
        
        # Posição do preço nas bandas
        sup_2sigma = bandas['resistencia_2sigma']
        inf_2sigma = bandas['suporte_2sigma']
        central = bandas['linha_central']
        
        if current_price > sup_2sigma:
            position = 'Acima Banda Superior 2σ - Sobrecomprado'
            signal = 'SELL_VOLATILITY'
            confidence = 80
            strategy = 'Iron Condor'
        elif current_price < inf_2sigma:
            position = 'Abaixo Banda Inferior 2σ - Sobrevendido'
            signal = 'BUY_VOLATILITY'
            confidence = 85
            strategy = 'Long Straddle'
        elif current_price > central:
            position = 'Metade Superior - Bullish'
            signal = 'CALL_BIAS'
            confidence = 65
            strategy = 'Call Spread'
        else:
            position = 'Metade Inferior - Bearish'
            signal = 'PUT_BIAS'
            confidence = 65
            strategy = 'Put Spread'
        
        # CORRIGIDO: Retornar estrutura igual ao MetaTrader
        return {
            'price': current_price,
            'volatility': latest['hybrid_vol'] if not pd.isna(latest['hybrid_vol']) else vol_fallback,
            'trend_regime': 'Bull' if latest['trend_regime'] == 1 else 'Bear',
            'vol_regime': 'High' if latest['vol_regime'] == 1 else 'Low',
            'bandas': bandas,
            'position': position,
            'signal': signal,
            'confidence': confidence,
            'strategy': strategy
        }
    
    def generate_plotly_chart(self, data: pd.DataFrame, ticker: str, days_back: int = 180) -> str:
        """Gerar gráfico Plotly em HTML"""
        try:
            df_plot = data.tail(days_back).copy()
            ticker_display = ticker.replace('.SA', '')
            
            fig = go.Figure()
            
            fig.add_trace(go.Candlestick(
                x=df_plot['Date'],
                open=df_plot['Open'],
                high=df_plot['High'],
                low=df_plot['Low'],
                close=df_plot['Close'],
                name='Preço',
                increasing_line_color='white',
                decreasing_line_color='red'
            ))
            
            fig.add_trace(go.Scatter(
                x=df_plot['Date'],
                y=df_plot['banda_superior_2sigma'],
                mode='lines',
                name='Banda Superior 2σ',
                line=dict(color='#FF6B6B', width=2),
                opacity=0.9
            ))
            
            fig.add_trace(go.Scatter(
                x=df_plot['Date'],
                y=df_plot['banda_inferior_2sigma'],
                mode='lines',
                name='Banda Inferior 2σ',
                line=dict(color='#4ECDC4', width=2),
                opacity=0.9
            ))
            
            fig.add_trace(go.Scatter(
                x=df_plot['Date'],
                y=df_plot['banda_superior_4sigma'],
                mode='lines',
                name='Banda Superior 4σ',
                line=dict(color='#FF4757', width=1.5, dash='dash'),
                opacity=0.7
            ))
            
            fig.add_trace(go.Scatter(
                x=df_plot['Date'],
                y=df_plot['banda_inferior_4sigma'],
                mode='lines',
                name='Banda Inferior 4σ',
                line=dict(color='#2ED573', width=1.5, dash='dash'),
                opacity=0.7
            ))
            
            fig.add_trace(go.Scatter(
                x=df_plot['Date'],
                y=df_plot['linha_central'],
                mode='lines',
                name='Linha Central',
                line=dict(color='black', width=2)
            ))
            
            fig.update_layout(
                title=f'{ticker_display} - Bandas de Volatilidade ({self.config["name"]})',
                xaxis_title='Data',
                yaxis_title='Preço (R$)' if '.SA' in ticker else 'Preço (USD)',
                width=None,                                 
                height=None,                                
                autosize=True,                              
                showlegend=False,
                xaxis=dict(
                    type='date',
                    rangeslider=dict(visible=False),
                    gridcolor='rgba(255,255,255,0.1)',
                    showgrid=True,
                    tickcolor='rgba(255,255,255,0.7)',
                    tickfont=dict(color='rgba(255,255,255,0.8)')
                ),
                yaxis=dict(
                    side='right',
                    gridcolor='rgba(255,255,255,0.1)',
                    showgrid=True,
                    tickcolor='rgba(255,255,255,0.7)',
                    tickfont=dict(color='rgba(255,255,255,0.8)')
                ),
                plot_bgcolor='rgba(255,255,255,0.05)',
                paper_bgcolor='rgba(34,34,34,0.2)',
                font=dict(color='rgba(255,255,255,0.9)'),
                margin=dict(l=50, r=50, t=80, b=50)        
            )
            
            return fig.to_html(include_plotlyjs='cdn')
            
        except Exception as e:
            self.logger.error(f"Erro ao gerar gráfico: {e}")
            return f"<p>Erro ao gerar gráfico: {e}</p>"
    
    def get_analysis_summary(self, ticker: str, period: str = "2y") -> Dict:
        """Análise completa do ticker"""
        try:
            search_ticker = ticker if ticker.endswith('.SA') or ticker.startswith('^') else ticker + '.SA'
            clean_ticker = ticker.replace('.SA', '').upper()
            
            self.logger.info(f"Analisando {search_ticker} (clean: {clean_ticker})")
            
            data = self.get_stock_data(search_ticker, period)
            if data is None:
                return {'error': f'Dados não encontrados para {search_ticker}', 'success': False}
            
            if len(data) < 50:
                return {'error': f'Dados insuficientes ({len(data)} registros). Mínimo 50.', 'success': False}
            
            # Buscar último preço mais recente
            try:
                import pytz
                sp_tz = pytz.timezone('America/Sao_Paulo')
                now_sp = datetime.now(sp_tz)
                
                self.logger.info(f"🕐 HORÁRIO SP: {now_sp.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                
                recent_data = yf.download(
                    search_ticker, 
                    period="5d",
                    interval='1d',
                    progress=False,
                    threads=False,
                    auto_adjust=True,
                    prepost=False,
                    repair=True
                )
                
                if hasattr(recent_data.columns, 'get_level_values') and search_ticker in recent_data.columns.get_level_values(1):
                    recent_data = recent_data.xs(search_ticker, axis=1, level=1)
                
                if not recent_data.empty:
                    recent_data.reset_index(inplace=True)
                    current_price = float(recent_data['Close'].iloc[-1])
                    last_date = recent_data['Date'].iloc[-1]
                    self.logger.info(f"✅ ÚLTIMO FECHAMENTO: R$ {current_price:.4f} em {last_date}")
                    
                    if last_date.date() >= (now_sp.date() - pd.Timedelta(days=1)):
                        self.logger.info("✅ DADOS ATUALIZADOS - Usando fechamento recente")
                        last_update_time = last_date
                    else:
                        self.logger.warning(f" DADOS ANTIGOS - Último: {last_date.date()}, Hoje: {now_sp.date()}")
                        last_update_time = last_date
                else:
                    current_price = float(data['Close'].iloc[-1])
                    last_update_time = data['Date'].iloc[-1]
                    self.logger.warning(f" USANDO DADOS HISTÓRICOS: R$ {current_price:.4f}")
                
            except Exception as e:
                current_price = float(data['Close'].iloc[-1])
                last_update_time = data['Date'].iloc[-1]
                self.logger.error(f" ERRO ao buscar dados recentes: {e}")
                self.logger.info(f"🔄 FALLBACK: R$ {current_price:.4f} (dados históricos)")
            
            # Processar dados através do pipeline
            data = self.calculate_base_volatility(data)
            data = self.engineer_features(data)
            data = self.train_xgboost(data)
            data = self.create_hybrid_model(data)
            data = self.create_bands(data)
            
            # Atualizar último preço
            if 'current_price' in locals():
                data.loc[data.index[-1], 'Close'] = current_price
                self.logger.info(f"🔄 PREÇO ATUALIZADO no DataFrame: R$ {current_price:.4f}")
            
            signals = self.get_current_signals(data, search_ticker)
            signals['price'] = current_price
            self.logger.info(f"✅ PREÇO FINAL nos SINAIS: R$ {signals['price']:.4f}")
            
            chart_html = self.generate_plotly_chart(data, search_ticker)
            
            latest = data.iloc[-1]
            
            summary = {
                'ticker': clean_ticker,
                'timeframe': self.config['name'],  # NOVO
                'period': period,
                'data_points': len(data),
                'last_update': last_update_time.strftime('%Y-%m-%d %H:%M:%S'),
                'current_price': self.convert_to_json_safe(current_price),
                'historical_close': self.convert_to_json_safe(latest['Close']),
                
                'metrics': {
                    'volatility': {
                        'garch': self.convert_to_json_safe(latest['garch_vol']),
                        'xgb': self.convert_to_json_safe(latest['xgb_vol']),
                        'hybrid': self.convert_to_json_safe(latest['hybrid_vol']),
                        'regime': signals['vol_regime']
                    },
                    'bands': {
                        'resistencia_2sigma': self.convert_to_json_safe(signals['bandas']['resistencia_2sigma']),
                        'suporte_2sigma': self.convert_to_json_safe(signals['bandas']['suporte_2sigma']),
                        'resistencia_4sigma': self.convert_to_json_safe(signals['bandas']['resistencia_4sigma']),
                        'suporte_4sigma': self.convert_to_json_safe(signals['bandas']['suporte_4sigma']),
                        'linha_central': self.convert_to_json_safe(signals['bandas']['linha_central'])
                    },
                    'position': {
                        'description': signals['position'],
                        'trend_regime': signals['trend_regime']
                    }
                },
                
                'trading_signal': {
                    'signal': signals['signal'],
                    'confidence': self.convert_to_json_safe(signals['confidence']),
                    'strategy': signals['strategy'],
                    'reasoning': [signals['position']],
                    'metrics': {
                        'volatility': self.convert_to_json_safe(signals['volatility']),
                        'price_vs_central': self.convert_to_json_safe(
                            (current_price - signals['bandas']['linha_central']) / signals['bandas']['linha_central'] * 100
                        )
                    }
                },
                
                'chart_data': [
                    {
                        'Date': row['Date'].strftime('%Y-%m-%d'),
                        'Close': self.convert_to_json_safe(row['Close']),
                        'banda_superior_2sigma': self.convert_to_json_safe(row['banda_superior_2sigma']),
                        'banda_inferior_2sigma': self.convert_to_json_safe(row['banda_inferior_2sigma']),
                        'linha_central': self.convert_to_json_safe(row['linha_central']),
                        'hybrid_vol': self.convert_to_json_safe(row['hybrid_vol'])
                    }
                    for _, row in data.tail(50).iterrows()
                ],
                
                'chart_html': chart_html,
                'success': True
            }
            
            self.logger.info(f"✅ Análise concluída para {clean_ticker}: {signals['signal']} - Preço: R$ {current_price:.2f}")
            return summary
            
        except Exception as e:
            self.logger.error(f"Erro na análise: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e), 'success': False}
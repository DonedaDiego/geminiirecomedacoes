# bandas_pro_service.py - Hybrid Volatility Bands Pro (GARCH + XGBoost + IV Validation)

import numpy as np
import pandas as pd
import yfinance as yf
from arch import arch_model
import xgboost as xgb
from sklearn.preprocessing import RobustScaler
import plotly.graph_objects as go
import requests
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings('ignore')


class VolatilityValidatorPro:
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
            
            response = requests.get(self.base_url, headers=self.headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    stock_data = data[0]
                    return stock_data
            
            print(f"Dados IV não disponíveis para {ticker_clean} via API")
            return None
            
        except Exception as e:
            print(f"Erro ao buscar dados IV: {e}")
            return None
    
    def calculate_confidence_score(self, iv_data, current_price=None):
        """Calcula score de confiança do rompimento (0-100)"""
        if not iv_data:
            return {'score': 50, 'status': 'NEUTRO', 'details': 'Dados IV indisponíveis'}
        
        score = 50
        details = []
        
        # IV Rank Analysis
        iv_rank_1y = iv_data.get('iv_1y_percentile')
        if iv_rank_1y is not None:
            if iv_rank_1y < 0.2:
                score += 30
                details.append(f"IV Rank Baixo ({iv_rank_1y:.1%}) - Movimento genuíno")
            elif iv_rank_1y < 0.5:
                score += 15
                details.append(f"IV Rank Médio ({iv_rank_1y:.1%}) - Neutro")
            elif iv_rank_1y < 0.8:
                score -= 10
                details.append(f"IV Rank Alto ({iv_rank_1y:.1%}) - Cuidado")
            else:
                score -= 25
                details.append(f"IV Rank Muito Alto ({iv_rank_1y:.1%}) - Movimento suspeito")
        
        # IV vs EWMA Spread
        iv_current = iv_data.get('iv_current')
        ewma_current = iv_data.get('ewma_current')
        
        if iv_current and ewma_current:
            iv_spread = (iv_current - ewma_current) / ewma_current
            
            if iv_spread < -0.1:
                score += 25
                details.append(f"IV Subestimada ({iv_spread:.1%}) - Movimento não precificado")
            elif iv_spread < 0.1:
                score += 10
                details.append(f"IV vs EWMA Neutro ({iv_spread:.1%})")
            elif iv_spread < 0.3:
                score -= 10
                details.append(f"IV Superestimada ({iv_spread:.1%})")
            else:
                score -= 20
                details.append(f"IV Muito Superestimada ({iv_spread:.1%}) - Movimento exagerado")
        
        # Volatilidade Realizada vs IV
        stdv_5d = iv_data.get('stdv_5d')
        if stdv_5d and iv_current:
            vol_ratio = stdv_5d / iv_current if iv_current > 0 else 1
            
            if vol_ratio < 0.7:
                score += 15
                details.append(f"Vol Realizada Baixa vs IV ({vol_ratio:.2f}) - Espaço para movimento")
            elif vol_ratio > 1.3:
                score -= 15
                details.append(f"Vol Realizada Alta vs IV ({vol_ratio:.2f}) - Movimento já aconteceu")
        
        score = max(0, min(100, score))
        
        if score >= 70:
            status = "CONFIÁVEL"
            status_emoji = "VERDE"
        elif score >= 40:
            status = "NEUTRO"
            status_emoji = "AMARELO"
        else:
            status = "SUSPEITO"
            status_emoji = "VERMELHO"
        
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


class BandasProService:
    def __init__(self):
        self.setup_logging()
        self.scaler = RobustScaler()
        self.xgb_model = None
        self.iv_validator = VolatilityValidatorPro()
        
    def setup_logging(self):
        """Configurar logging"""
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def convert_to_json_safe(self, value):
        """Converter qualquer tipo para JSON-safe de forma robusta"""
        if value is None or pd.isna(value):
            return None
        
        # Tipos numpy inteiros
        if isinstance(value, (np.integer, np.int8, np.int16, np.int32, np.int64)):
            return int(value)
        
        # Tipos numpy float
        elif isinstance(value, (np.floating, np.float16, np.float32, np.float64)):
            if np.isnan(value) or np.isinf(value):
                return 0.0
            return float(value)
        
        # Tipos numpy boolean
        elif isinstance(value, np.bool_):
            return bool(value)
        
        # Arrays numpy
        elif isinstance(value, np.ndarray):
            return [self.convert_to_json_safe(item) for item in value.tolist()]
        
        # Pandas Timestamp
        elif isinstance(value, pd.Timestamp):
            return value.strftime('%Y-%m-%d %H:%M:%S')
        
        # Dicionários - aplicar recursivamente
        elif isinstance(value, dict):
            return {k: self.convert_to_json_safe(v) for k, v in value.items()}
        
        # Listas - aplicar recursivamente
        elif isinstance(value, list):
            return [self.convert_to_json_safe(item) for item in value]
        
        # Strings e outros tipos primitivos
        else:
            return value
    
    def get_stock_data(self, ticker: str, period: str = "6mo") -> Optional[pd.DataFrame]:
        try:
            # Lógica de ticker melhorada
            if not ticker.endswith('.SA') and not ticker.startswith('^'):
                ticker = ticker + '.SA'
            
            self.logger.info(f"Buscando dados para {ticker} - período: {period}")
            
            # Baixar dados
            data = yf.download(ticker, start=None, end=None, period=period, interval='1d')
            if hasattr(data.columns, 'get_level_values') and ticker in data.columns.get_level_values(1):
                data = data.xs(ticker, axis=1, level=1)
            
            if data.empty:
                self.logger.error(f"Nenhum dado encontrado para {ticker}")
                return None
            
            # Reset index e calcular retornos
            data.reset_index(inplace=True)
            data['Returns'] = data['Close'].pct_change()
            data['Log_Returns'] = np.log(data['Close'] / data['Close'].shift(1))
            data.dropna(inplace=True)
            
            self.logger.info(f"Dados carregados: {len(data)} registros de {data['Date'].iloc[0]} até {data['Date'].iloc[-1]}")
            return data
            
        except Exception as e:
            self.logger.error(f"Erro ao buscar dados: {e}")
            return None
    
    def calculate_base_volatility(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calcular volatilidade base (GARCH e Realized)"""
        df = data.copy()
        
        try:
            # GARCH
            garch_model = arch_model(df['Log_Returns'] * 100, vol='Garch', p=1, q=1, dist='Normal')
            garch_result = garch_model.fit(disp='off')
            df['garch_vol'] = garch_result.conditional_volatility / 100
            
            # Realized Volatility (múltiplas janelas)
            for window in [3, 5, 10, 20]:
                df[f'realized_vol_{window}d'] = (
                    df['Returns'].rolling(window=window)
                    .apply(lambda x: np.sqrt(np.sum(x**2)))
                )
        except Exception as e:
            self.logger.warning(f"Erro no GARCH, usando volatilidade simples: {e}")
            df['garch_vol'] = df['Returns'].rolling(20).std()
            for window in [3, 5, 10, 20]:
                df[f'realized_vol_{window}d'] = df['Returns'].rolling(window).std()
        
        return df
    
    def engineer_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Engenharia de features para XGBoost"""
        df = data.copy()
        
        # Volatilidade histórica multi-timeframe
        for window in [5, 10, 20, 60]:
            df[f'vol_std_{window}d'] = df['Returns'].rolling(window).std()
        
        # Lags importantes
        for lag in [1, 2, 5]:
            df[f'garch_lag_{lag}'] = df['garch_vol'].shift(lag)
            df[f'returns_lag_{lag}'] = df['Returns'].shift(lag)
        
        # Market structure
        df['daily_range'] = (df['High'] - df['Low']) / df['Close']
        df['price_momentum_5d'] = df['Close'] / df['Close'].shift(5) - 1
        
        # Volume (se disponível)
        if 'Volume' in df.columns:
            df['volume_ma_20'] = df['Volume'].rolling(20).mean()
            df['volume_ratio'] = df['Volume'] / df['volume_ma_20']
        else:
            df['volume_ratio'] = 1
        
        # Regime detection
        df['sma_50'] = df['Close'].rolling(50).mean()
        df['sma_200'] = df['Close'].rolling(200).mean()
        df['trend_regime'] = np.where(df['sma_50'] > df['sma_200'], 1, 0)
        df['vol_regime'] = np.where(df['garch_vol'] > df['garch_vol'].rolling(60).mean(), 1, 0)
        df['vol_percentile'] = df['garch_vol'].rolling(252).rank(pct=True)
        
        return df
    
    def train_xgboost(self, data: pd.DataFrame) -> pd.DataFrame:
        """Treinar modelo XGBoost para volatilidade"""
        df = data.copy()
        
        feature_cols = [
            'garch_lag_1', 'garch_lag_2', 'garch_lag_5',
            'realized_vol_10d', 'realized_vol_20d', 'realized_vol_3d',
            'vol_std_10d', 'vol_std_20d', 'vol_std_5d',
            'vol_percentile', 'vol_regime', 'returns_lag_1',
            'daily_range', 'price_momentum_5d', 'volume_ratio', 'trend_regime'
        ]
        
        # Preparar dados
        df_ml = df[feature_cols + ['garch_vol']].copy()
        df_ml.dropna(inplace=True)
        
        if len(df_ml) < 50:
            self.logger.warning("Dados insuficientes para XGBoost, usando apenas GARCH")
            df['xgb_vol'] = df['garch_vol']
            return df
        
        X = df_ml[feature_cols]
        y = df_ml['garch_vol']
        
        # Scaling
        X_scaled = self.scaler.fit_transform(X)
        X_scaled = pd.DataFrame(X_scaled, columns=feature_cols, index=X.index)
        
        # Split temporal
        train_size = int(len(X_scaled) * 0.8)
        X_train, X_test = X_scaled[:train_size], X_scaled[train_size:]
        y_train, y_test = y[:train_size], y[train_size:]
        
        try:
            # XGBoost otimizado
            self.xgb_model = xgb.XGBRegressor(
                n_estimators=200,
                max_depth=8,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_alpha=0.1,
                reg_lambda=0.1,
                random_state=42,
                verbosity=0
            )
            
            self.xgb_model.fit(X_train, y_train)
            
            # Predições
            xgb_pred = self.xgb_model.predict(X_test)
            
            # Adicionar ao DataFrame
            df['xgb_vol'] = np.nan
            test_indices = df_ml.index[train_size:]
            df.loc[test_indices, 'xgb_vol'] = xgb_pred
            df['xgb_vol'].fillna(df['garch_vol'], inplace=True)
            
        except Exception as e:
            self.logger.warning(f"Erro no XGBoost: {e}, usando apenas GARCH")
            df['xgb_vol'] = df['garch_vol']
        
        return df
    
    def create_hybrid_model(self, data: pd.DataFrame) -> pd.DataFrame:
        """Criar modelo híbrido GARCH + XGBoost"""
        df = data.copy()
        
        # Regime adaptativo baseado em volatilidade
        df['vol_regime_adaptive'] = df['garch_vol'].rolling(30).std()
        df['vol_regime_normalized'] = (
            df['vol_regime_adaptive'] / df['vol_regime_adaptive'].rolling(252).mean()
        )
        
        # Preencher NaN com valores padrão
        df['vol_regime_normalized'].fillna(1.0, inplace=True)
        
        # Pesos dinâmicos: mais GARCH em alta vol, mais XGBoost em baixa vol
        df['weight_garch'] = np.clip(0.3 + 0.4 * df['vol_regime_normalized'], 0.3, 0.7)
        df['weight_xgb'] = 1 - df['weight_garch']
        
        # Híbrido final com proteção contra NaN
        df['hybrid_vol'] = (
            df['weight_garch'] * df['garch_vol'] + 
            df['weight_xgb'] * df['xgb_vol']
        )
        
        # Garantir que não há NaN na volatilidade híbrida
        df['hybrid_vol'].fillna(df['garch_vol'], inplace=True)
        df['hybrid_vol'].fillna(method='ffill', inplace=True)
        df['hybrid_vol'].fillna(0.02, inplace=True)  # Fallback final
        
        return df
    
    def create_bands(self, data: pd.DataFrame) -> pd.DataFrame:
        """Criar bandas de volatilidade"""
        df = data.copy()
        df_temp = df.copy()
        df_temp['Month'] = df_temp['Date'].dt.to_period('M')
        
        monthly_ref = df_temp.groupby('Month').agg(
            reference_price=('Close', 'last'),
            monthly_vol=('hybrid_vol', 'last')
        ).reset_index()
        
        monthly_ref['Next_Month'] = monthly_ref['Month'] + 1
        df_temp = df_temp.merge(
            monthly_ref[['Next_Month', 'reference_price', 'monthly_vol']],
            left_on='Month',
            right_on='Next_Month',
            how='left'
        )
        
        # Preencher NaN com forward fill para evitar bandas vazias
        df_temp['monthly_vol'].fillna(method='ffill', inplace=True)
        df_temp['reference_price'].fillna(method='ffill', inplace=True)
        
        # Se ainda houver NaN, usar volatilidade GARCH como fallback
        df_temp['monthly_vol'].fillna(df['garch_vol'], inplace=True)
        df_temp['reference_price'].fillna(df['Close'], inplace=True)
        
        # Bandas: 2σ e 4σ
        for d in [2, 4]:
            df[f'banda_superior_{d}sigma'] = (
                (1 + d * df_temp['monthly_vol']) * df_temp['reference_price']
            )
            df[f'banda_inferior_{d}sigma'] = (
                (1 - d * df_temp['monthly_vol']) * df_temp['reference_price']
            )
        
        # Linha central
        df['linha_central'] = (df['banda_superior_2sigma'] + df['banda_inferior_2sigma']) / 2
        
        # Verificar se ainda há NaN e corrigir
        for col in ['banda_superior_2sigma', 'banda_inferior_2sigma', 'linha_central', 'banda_superior_4sigma', 'banda_inferior_4sigma']:
            if col in df.columns and df[col].isna().any():
                df[col].fillna(method='ffill', inplace=True)
                df[col].fillna(method='bfill', inplace=True)
        
        return df
    
    def get_current_signals(self, data: pd.DataFrame, ticker: str) -> Dict:
        """Gerar sinais atuais de trading COM validação IV"""
        latest = data.iloc[-1]
        current_price = latest['Close']
        
        # Verificar se há NaN nas bandas e usar fallback
        def safe_get(col_name, fallback_value):
            value = latest[col_name] if not pd.isna(latest[col_name]) else fallback_value
            return value
        
        # Fallbacks baseados no preço atual e volatilidade
        vol_fallback = latest['garch_vol'] if not pd.isna(latest['garch_vol']) else 0.02
        
        signals = {
            'price': current_price,
            'volatility': latest['hybrid_vol'] if not pd.isna(latest['hybrid_vol']) else vol_fallback,
            'trend_regime': 'Bull' if latest['trend_regime'] == 1 else 'Bear',
            'vol_regime': 'High' if latest['vol_regime'] == 1 else 'Low',
            'bandas': {
                'superior_2σ': safe_get('banda_superior_2sigma', current_price * (1 + 2 * vol_fallback)),
                'inferior_2σ': safe_get('banda_inferior_2sigma', current_price * (1 - 2 * vol_fallback)),
                'superior_4σ': safe_get('banda_superior_4sigma', current_price * (1 + 4 * vol_fallback)),
                'inferior_4σ': safe_get('banda_inferior_4sigma', current_price * (1 - 4 * vol_fallback)),
                'linha_central': safe_get('linha_central', current_price)
            }
        }
        
        # Posição do preço nas bandas
        sup_2sigma = signals['bandas']['superior_2σ']
        inf_2sigma = signals['bandas']['inferior_2σ']
        central = signals['bandas']['linha_central']
        
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
        
        signals['position'] = position
        signals['signal'] = signal
        signals['confidence'] = confidence
        signals['strategy'] = strategy
        
        # Validação IV
        try:
            iv_analysis = self.iv_validator.validate_breakout(ticker, signals)
            signals['iv_validation'] = iv_analysis
        except Exception as e:
            signals['iv_validation'] = {
                'score': 50, 'status': 'INDISPONÍVEL', 'status_emoji': 'CINZA',
                'recommendation': 'Use apenas análise técnica',
                'details': ['Dados IV indisponíveis']
            }
        
        return signals
    
    def generate_plotly_chart(self, data: pd.DataFrame, ticker: str, days_back: int = 180) -> str:
        """Gerar gráfico Plotly em HTML"""
        try:
            # Filtrar dados recentes
            df_plot = data.tail(days_back).copy()
            ticker_display = ticker.replace('.SA', '')
            
            # Criar figura Plotly
            fig = go.Figure()
            
            # Candlestick
            fig.add_trace(go.Candlestick(
                x=df_plot['Date'],
                open=df_plot['Open'],
                high=df_plot['High'],
                low=df_plot['Low'],
                close=df_plot['Close'],
                name='Preço',
                increasing_line_color='green',
                decreasing_line_color='red'
            ))
            
            # Bandas de volatilidade
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
            
            # Linha central
            fig.add_trace(go.Scatter(
                x=df_plot['Date'],
                y=df_plot['linha_central'],
                mode='lines',
                name='Linha Central',
                line=dict(color='black', width=2)
            ))
            
            # Layout
            fig.update_layout(
                title=f'{ticker_display} - Bandas de Volatilidade Híbridas Pro (GARCH + XGBoost) + Validação IV',
                xaxis_title='Data',
                yaxis_title='Preço (R$)' if '.SA' in ticker else 'Preço (USD)',
                width=1200, height=700, showlegend=False,
                legend=dict(x=0, y=1),
                xaxis=dict(type='date', rangeslider=dict(visible=False)),
                yaxis=dict(side='right')
            )
            
            return fig.to_html(include_plotlyjs='cdn')
            
        except Exception as e:
            self.logger.error(f"Erro ao gerar gráfico: {e}")
            return f"<p>Erro ao gerar gráfico: {e}</p>"
    
    def get_analysis_summary(self, ticker: str, period: str = "6mo") -> Dict:
        """Análise completa do ticker COM validação IV"""
        try:
            # Processar ticker corretamente
            search_ticker = ticker if ticker.endswith('.SA') or ticker.startswith('^') else ticker + '.SA'
            clean_ticker = ticker.replace('.SA', '').upper()
            
            self.logger.info(f"Analisando {search_ticker} (clean: {clean_ticker})")
            
            # Buscar dados
            data = self.get_stock_data(search_ticker, period)
            if data is None:
                return {'error': f'Dados não encontrados para {search_ticker}', 'success': False}
            
            # Verificar se temos dados suficientes
            if len(data) < 50:
                return {'error': f'Dados insuficientes ({len(data)} registros). Mínimo 50.', 'success': False}
            
            # Buscar preço atual/corrente em tempo real
            try:
                stock = yf.Ticker(search_ticker)
                current_data = stock.history(period="1d", interval="1m")
                
                if not current_data.empty:
                    current_price = float(current_data['Close'].iloc[-1])
                    last_update_time = current_data.index[-1]
                    self.logger.info(f"Preço corrente obtido: {current_price} às {last_update_time}")
                else:
                    current_price = float(data['Close'].iloc[-1])
                    last_update_time = data['Date'].iloc[-1]
                    self.logger.warning(f"Usando último fechamento histórico: {current_price}")
                    
            except Exception as e:
                current_price = float(data['Close'].iloc[-1])
                last_update_time = data['Date'].iloc[-1]
                self.logger.warning(f"Erro ao buscar preço corrente, usando fechamento: {current_price} - {e}")
            
            # Processar dados através do pipeline
            data = self.calculate_base_volatility(data)
            data = self.engineer_features(data)
            data = self.train_xgboost(data)
            data = self.create_hybrid_model(data)
            data = self.create_bands(data)
            
            # Gerar sinais COM validação IV
            signals = self.get_current_signals(data, search_ticker)
            
            # Gerar gráfico HTML
            chart_html = self.generate_plotly_chart(data, search_ticker)
            
            # Estatísticas atuais
            latest = data.iloc[-1]
            
            # Aplicar convert_to_json_safe em TODOS os valores
            summary = {
                'ticker': clean_ticker,
                'period': period,
                'data_points': len(data),
                'last_update': last_update_time.strftime('%Y-%m-%d %H:%M:%S'),
                'current_price': self.convert_to_json_safe(current_price),
                'historical_close': self.convert_to_json_safe(latest['Close']),
                
                # Métricas atuais - Adaptadas para bandas de volatilidade
                'metrics': {
                    'volatility': {
                        'garch': self.convert_to_json_safe(latest['garch_vol']),
                        'xgb': self.convert_to_json_safe(latest['xgb_vol']),
                        'hybrid': self.convert_to_json_safe(latest['hybrid_vol']),
                        'regime': signals['vol_regime']
                    },
                    'bands': {
                        'superior_2sigma': self.convert_to_json_safe(signals['bandas']['superior_2σ']),
                        'inferior_2sigma': self.convert_to_json_safe(signals['bandas']['inferior_2σ']),
                        'superior_4sigma': self.convert_to_json_safe(signals['bandas']['superior_4σ']),
                        'inferior_4sigma': self.convert_to_json_safe(signals['bandas']['inferior_4σ']),
                        'linha_central': self.convert_to_json_safe(signals['bandas']['linha_central'])
                    },
                    'position': {
                        'description': signals['position'],
                        'trend_regime': signals['trend_regime']
                    }
                },
                
                # Validação IV (PRO)
                'iv_validation': {
                    'score': self.convert_to_json_safe(signals['iv_validation']['score']),
                    'status': signals['iv_validation']['status'],
                    'status_emoji': signals['iv_validation']['status_emoji'],
                    'recommendation': signals['iv_validation']['recommendation'],
                    'details': signals['iv_validation']['details'],
                    'raw_data': {
                        'iv_current': self.convert_to_json_safe(signals['iv_validation']['raw_data'].get('iv_current')),
                        'iv_rank_1y': self.convert_to_json_safe(signals['iv_validation']['raw_data'].get('iv_rank_1y')),
                        'ewma_current': self.convert_to_json_safe(signals['iv_validation']['raw_data'].get('ewma_current')),
                        'stdv_5d': self.convert_to_json_safe(signals['iv_validation']['raw_data'].get('stdv_5d'))
                    }
                },
                
                # Sinal de trading
                'trading_signal': {
                    'signal': signals['signal'],
                    'confidence': self.convert_to_json_safe(signals['confidence']),
                    'strategy': signals['strategy'],
                    'reasoning': [signals['position']],
                    'iv_adjusted_confidence': self.convert_to_json_safe(
                        min(100, signals['confidence'] * (signals['iv_validation']['score'] / 100))
                    ),
                    'metrics': {
                        'volatility': self.convert_to_json_safe(signals['volatility']),
                        'price_vs_central': self.convert_to_json_safe(
                            (current_price - signals['bandas']['linha_central']) / signals['bandas']['linha_central'] * 100
                        )
                    }
                },
                
                # Dados para gráficos (últimos 50 pontos)
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
                
                # Gráfico HTML
                'chart_html': chart_html,
                
                'success': True
            }
            
            self.logger.info(f"Análise concluída para {clean_ticker}: {signals['signal']} - IV Score: {signals['iv_validation']['score']}/100 - Preço corrente: R$ {current_price:.2f}")
            return summary
            
        except Exception as e:
            self.logger.error(f"Erro na análise: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e), 'success': False}
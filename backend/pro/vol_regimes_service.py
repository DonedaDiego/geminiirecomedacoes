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
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings('ignore')


class VolatilityRegimesService:
    def __init__(self):
        self.setup_logging()
        self.scaler = RobustScaler()
        self.xgb_model = None
        
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
    
    def get_stock_data(self, ticker: str, period: str = "2y") -> Optional[pd.DataFrame]:
        try:
            # ===== USAR LÓGICA IDÊNTICA AO BANDAS_PRO =====
            logging.info(f"Carregando dados para {ticker}")
            
            # Normalizar ticker se necessário
            ticker_to_use = ticker
            if len(ticker) <= 6 and not ticker.endswith('.SA') and '-' not in ticker:
                ticker_to_use = ticker + '.SA'
            
            # Baixar dados históricos - MESMO MÉTODO DO BANDAS_PRO
            stock = yf.Ticker(ticker_to_use)
            data = stock.history(period=period)
            
            # Verificações de dados
            if data is None or data.empty:
                # Tentar ticker original se o normalizado falhou
                if ticker_to_use != ticker:
                    logging.warning(f"Tentando ticker original: {ticker}")
                    stock = yf.Ticker(ticker)
                    data = stock.history(period=period)
                
                if data is None or data.empty:
                    raise ValueError(f"Nenhum dado encontrado para {ticker}")
            
            # Verificar quantidade de dados
            if len(data) < 50:
                raise ValueError(f"Dados insuficientes para {ticker} (apenas {len(data)} registros)")
            
            # Validar colunas necessárias
            required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            missing_columns = [col for col in required_columns if col not in data.columns]
            if missing_columns:
                raise ValueError(f"Colunas ausentes nos dados: {missing_columns}")
            
            # Reset index e configurar Date
            data.reset_index(inplace=True)
            
            # Configurar coluna Date corretamente
            if 'Date' in data.columns:
                data['Date'] = pd.to_datetime(data['Date'])
            else:
                # Se não tem Date, usar o índice do yfinance que são as datas
                data['Date'] = data.index if hasattr(data.index, 'date') else pd.date_range(start=pd.Timestamp.now() - pd.Timedelta(days=len(data)), periods=len(data), freq='D')
            
            # Calcular retornos
            data['Returns'] = data['Close'].pct_change()
            data['Log_Returns'] = np.log(data['Close'] / data['Close'].shift(1))
            
            # Remover dados nulos/inválidos - MESMO FILTRO DO BANDAS_PRO
            data = data[(data['Open'] > 0) & 
                        (data['High'] > 0) & 
                        (data['Low'] > 0) & 
                        (data['Close'] > 0)]
            
            # Remover NaNs
            initial_len = len(data)
            data = data.dropna()
            final_len = len(data)
            
            if final_len < 30:
                raise ValueError(f"Dados insuficientes após limpeza: {final_len} registros")
            
            if initial_len != final_len:
                logging.warning(f"Removidos {initial_len - final_len} registros com dados nulos")
            
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
        
        # Apenas 2 bandas principais: 2σ e 4σ
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
        """Gerar sinais atuais de trading"""
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
                increasing_line_color='white',
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
                title=f'{ticker_display} - Bandas de Volatilidade',
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
            
            # ===== FIX: BUSCAR ÚLTIMO PREÇO DE FORMA CONSISTENTE =====
            try:
                import pytz
                from datetime import datetime
                
                # Timezone de São Paulo
                sp_tz = pytz.timezone('America/Sao_Paulo')
                now_sp = datetime.now(sp_tz)
                
                self.logger.info(f"🕐 HORÁRIO SP: {now_sp.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                
                # 1. PRIMEIRO: Tentar dados mais recentes (1 dia)
                self.logger.info("📡 Buscando dados mais recentes...")
                recent_data = yf.download(
                    search_ticker, 
                    period="5d",  # Últimos 5 dias para garantir
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
                    
                    # Verificar se é o fechamento mais recente possível
                    if last_date.date() >= (now_sp.date() - pd.Timedelta(days=1)):
                        self.logger.info("✅ DADOS ATUALIZADOS - Usando fechamento recente")
                        last_update_time = last_date
                    else:
                        self.logger.warning(f"⚠️ DADOS ANTIGOS - Último: {last_date.date()}, Hoje: {now_sp.date()}")
                        last_update_time = last_date
                else:
                    # Fallback para dados históricos
                    current_price = float(data['Close'].iloc[-1])
                    last_update_time = data['Date'].iloc[-1]
                    self.logger.warning(f"⚠️ USANDO DADOS HISTÓRICOS: R$ {current_price:.4f}")
                
            except Exception as e:
                # Fallback final - usar dados históricos
                current_price = float(data['Close'].iloc[-1])
                last_update_time = data['Date'].iloc[-1]
                self.logger.error(f"❌ ERRO ao buscar dados recentes: {e}")
                self.logger.info(f"🔄 FALLBACK: R$ {current_price:.4f} (dados históricos)")
            
            # Processar dados através do pipeline
            data = self.calculate_base_volatility(data)
            data = self.engineer_features(data)
            data = self.train_xgboost(data)
            data = self.create_hybrid_model(data)
            data = self.create_bands(data)
            
            # ===== FIX: USAR O PREÇO MAIS RECENTE PARA SINAIS =====
            # Atualizar o último registro com o preço mais recente
            if 'current_price' in locals():
                data.loc[data.index[-1], 'Close'] = current_price
                self.logger.info(f"🔄 PREÇO ATUALIZADO no DataFrame: R$ {current_price:.4f}")
            
            # Gerar sinais
            signals = self.get_current_signals(data, search_ticker)
            
            # ===== FIX: GARANTIR QUE O PREÇO NO SINAL ESTÁ CORRETO =====
            signals['price'] = current_price
            self.logger.info(f" PREÇO FINAL nos SINAIS: R$ {signals['price']:.4f}")
            
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
                
                # Sinal de trading
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
            
            self.logger.info(f"✅ Análise concluída para {clean_ticker}: {signals['signal']} - Preço: R$ {current_price:.2f}")
            return summary
            
        except Exception as e:
            self.logger.error(f"Erro na análise: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e), 'success': False}
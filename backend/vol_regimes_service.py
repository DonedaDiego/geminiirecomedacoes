# vol_regimes_services.py (VERSÃO CORRIGIDA)

import yfinance as yf
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple
import warnings

warnings.filterwarnings('ignore')


class VolatilityRegimesService:
    def __init__(self):
        self.setup_logging()
        self.scaler = StandardScaler()
        
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
            # CORREÇÃO: Lógica de ticker melhorada
            if not ticker.endswith('.SA') and not ticker.startswith('^'):
                ticker = ticker + '.SA'
            
            self.logger.info(f"Buscando dados para {ticker} - período: {period}")
            
            # Baixar dados
            stock = yf.Ticker(ticker)
            data = stock.history(period=period)
            
            if data.empty:
                self.logger.error(f"Nenhum dado encontrado para {ticker}")
                return None
            
            # Calcular retornos
            data['return'] = data['Close'].pct_change()
            data['return_abs'] = data['return'].abs()
            data['log_return'] = np.log(data['Close'] / data['Close'].shift(1))
            
            # Remover NaN
            data = data.dropna()
            
            self.logger.info(f"Dados carregados: {len(data)} registros de {data.index[0]} até {data.index[-1]}")
            return data
            
        except Exception as e:
            self.logger.error(f"Erro ao buscar dados: {e}")
            return None
    
    def calculate_regime_clustering(self, data: pd.DataFrame, n_clusters: int = 3, lookback: int = 20) -> pd.DataFrame:
        df = data.copy()
        
        # Preparar features para clustering
        df['vol_realized'] = df['return'].rolling(lookback).std() * np.sqrt(252)
        df['vol_parkinson'] = np.sqrt((1/(4*np.log(2))) * (np.log(df['High']/df['Low']))**2).rolling(lookback).mean() * np.sqrt(252)
        df['vol_garman_klass'] = np.sqrt(
            0.5 * (np.log(df['High']/df['Low']))**2 - 
            (2*np.log(2)-1) * (np.log(df['Close']/df['Open']))**2
        ).rolling(lookback).mean() * np.sqrt(252)
        
        # Features adicionais
        df['return_skew'] = df['return'].rolling(lookback).skew()
        df['return_kurt'] = df['return'].rolling(lookback).kurt()
        df['volume_normalized'] = df['Volume'] / df['Volume'].rolling(lookback).mean()
        
        # Criar matriz de features (remover NaN)
        feature_cols = ['vol_realized', 'vol_parkinson', 'vol_garman_klass', 'return_skew', 'return_kurt', 'volume_normalized']
        features_df = df[feature_cols].dropna()
        
        if len(features_df) < n_clusters:
            self.logger.warning("Dados insuficientes para clustering")
            df['regime'] = 0
            df['regime_name'] = 'Low'
            return df
        
        # Normalizar features
        features_scaled = self.scaler.fit_transform(features_df)
        
        # K-means clustering
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(features_scaled)
        
        # Mapear clusters de volta para o DataFrame original
        df['regime'] = np.nan
        df.loc[features_df.index, 'regime'] = clusters
        
        # Forward fill para preencher NaN
        df['regime'] = df['regime'].ffill().fillna(0)
        
        # Ordenar regimes por volatilidade média (0=baixa, 1=média, 2=alta)
        regime_stats = []
        for regime in range(n_clusters):
            regime_data = df[df['regime'] == regime]
            if len(regime_data) > 0:
                avg_vol = regime_data['vol_realized'].mean()
                regime_stats.append((regime, avg_vol))
        
        # Reordenar regimes
        regime_stats.sort(key=lambda x: x[1])  # Ordenar por volatilidade
        regime_mapping = {old: new for new, (old, _) in enumerate(regime_stats)}
        df['regime'] = df['regime'].map(regime_mapping)
        
        # Nomear regimes
        regime_names = {0: 'Low', 1: 'Medium', 2: 'High'}
        if n_clusters == 4:
            regime_names = {0: 'Very Low', 1: 'Low', 2: 'Medium', 3: 'High'}
        
        df['regime_name'] = df['regime'].map(regime_names)
        
        # Estatísticas dos regimes
        df['regime_persistence'] = df.groupby((df['regime'] != df['regime'].shift()).cumsum())['regime'].transform('count')
        
        self.logger.info(f"Regimes identificados: {df['regime_name'].value_counts().to_dict()}")
        
        return df
    
    def calculate_directional_flow(self, data: pd.DataFrame, window: int = 20) -> pd.DataFrame:
        df = data.copy()
        
        def calculate_directional_metrics(returns_window):
            """Calcular métricas direcionais para uma janela"""
            up_returns = returns_window[returns_window > 0]
            down_returns = returns_window[returns_window < 0]
            
            # Volatilidades direcionais
            up_vol = np.sqrt(np.mean(up_returns**2)) if len(up_returns) > 0 else 0
            down_vol = np.sqrt(np.mean(down_returns**2)) if len(down_returns) > 0 else 0
            
            # Frequências
            up_freq = len(up_returns) / len(returns_window) if len(returns_window) > 0 else 0
            down_freq = len(down_returns) / len(returns_window) if len(returns_window) > 0 else 0
            
            # Métricas
            asymmetry_ratio = down_vol / (up_vol + 1e-8)  # Evitar divisão por zero
            direction_bias = up_freq - down_freq
            
            # Volatilidade condicional (upside vs downside)
            upside_volatility = up_vol * np.sqrt(252) if up_vol > 0 else 0
            downside_volatility = down_vol * np.sqrt(252) if down_vol > 0 else 0
            
            return {
                'up_vol': upside_volatility,
                'down_vol': downside_volatility,
                'up_freq': up_freq,
                'down_freq': down_freq,
                'asymmetry_ratio': asymmetry_ratio,
                'direction_bias': direction_bias
            }
        
        # Calcular métricas direcionais em janela móvel
        directional_metrics = []
        
        for i in range(len(df)):
            if i < window:
                # Valores iniciais
                metrics = {
                    'up_vol': 0, 'down_vol': 0, 'up_freq': 0.5, 'down_freq': 0.5,
                    'asymmetry_ratio': 1, 'direction_bias': 0
                }
            else:
                returns_window = df['return'].iloc[i-window:i]
                metrics = calculate_directional_metrics(returns_window)
            
            directional_metrics.append(metrics)
        
        # Adicionar métricas ao DataFrame
        metrics_df = pd.DataFrame(directional_metrics, index=df.index)
        for col in metrics_df.columns:
            df[f'dir_{col}'] = metrics_df[col]
        
        # Sinal direcional
        df['directional_signal'] = np.where(
            df['dir_asymmetry_ratio'] > 1.5, 'PUT_BIAS',
            np.where(df['dir_asymmetry_ratio'] < 0.7, 'CALL_BIAS', 'NEUTRAL')
        )
        
        # Força do sinal (0-100)
        df['directional_strength'] = np.where(
            df['directional_signal'] == 'PUT_BIAS',
            np.clip((df['dir_asymmetry_ratio'] - 1.5) * 50, 0, 100),
            np.where(
                df['directional_signal'] == 'CALL_BIAS',
                np.clip((0.7 - df['dir_asymmetry_ratio']) * 100, 0, 100),
                0
            )
        )
        
        self.logger.info(f"Sinais direcionais: {df['directional_signal'].value_counts().to_dict()}")
        
        return df
    
    def calculate_squeeze_score(self, data: pd.DataFrame, bb_period: int = 20, kc_period: int = 20) -> pd.DataFrame:
        df = data.copy()
        
        # Bollinger Bands
        df['bb_middle'] = df['Close'].rolling(bb_period).mean()
        df['bb_std'] = df['Close'].rolling(bb_period).std()
        df['bb_upper'] = df['bb_middle'] + (2 * df['bb_std'])
        df['bb_lower'] = df['bb_middle'] - (2 * df['bb_std'])
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        
        # Keltner Channels (usando ATR)
        df['hl'] = df['High'] - df['Low']
        df['hc'] = abs(df['High'] - df['Close'].shift(1))
        df['lc'] = abs(df['Low'] - df['Close'].shift(1))
        df['atr'] = df[['hl', 'hc', 'lc']].max(axis=1).rolling(kc_period).mean()
        
        df['kc_middle'] = df['Close'].rolling(kc_period).mean()
        df['kc_upper'] = df['kc_middle'] + (2 * df['atr'])
        df['kc_lower'] = df['kc_middle'] - (2 * df['atr'])
        df['kc_width'] = (df['kc_upper'] - df['kc_lower']) / df['kc_middle']
        
        # Squeeze Score
        df['squeeze_score'] = df['bb_width'] / (df['kc_width'] + 1e-8)
        
        # Squeeze Score suavizado
        df['squeeze_smooth'] = df['squeeze_score'].rolling(5).mean()
        
        # Squeeze Signal
        df['squeeze_signal'] = np.where(
            df['squeeze_smooth'] < 0.8, 'COMPRESSION',
            np.where(df['squeeze_smooth'] > 1.5, 'EXPANSION', 'NEUTRAL')
        )
        
        # Força do squeeze (0-100)
        df['squeeze_strength'] = np.where(
            df['squeeze_signal'] == 'COMPRESSION',
            np.clip((0.8 - df['squeeze_smooth']) * 100, 0, 100),
            np.where(
                df['squeeze_signal'] == 'EXPANSION',
                np.clip((df['squeeze_smooth'] - 1.5) * 50, 0, 100),
                0
            )
        )
        
        # Detectar breakouts
        df['squeeze_breakout'] = (
            (df['squeeze_signal'].shift(1) == 'COMPRESSION') & 
            (df['squeeze_signal'] == 'NEUTRAL')
        )
        
        self.logger.info(f"Sinais de squeeze: {df['squeeze_signal'].value_counts().to_dict()}")
        
        return df
    
    def generate_combined_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        
        # Lógica de combinação
        latest = df.tail(5)  # Últimos 5 períodos
        
        # Médias dos indicadores recentes
        avg_squeeze = latest['squeeze_smooth'].mean()
        avg_asymmetry = latest['dir_asymmetry_ratio'].mean()
        regime_current = df['regime'].iloc[-1]
        
        # Sinais combinados
        signal = 'HOLD'
        confidence = 0
        strategy = ''
        reasoning = []
        
        # COMPRA FORTE DE VOLATILIDADE
        if avg_squeeze < 0.8 and regime_current >= 1:
            signal = 'BUY_VOLATILITY'
            confidence = 85
            strategy = 'Long Straddle'
            reasoning = [
                f'Squeeze baixo ({avg_squeeze:.3f}) indica compressão',
                f'Regime {regime_current} sugere volatilidade crescente'
            ]
            
            # Ajuste direcional
            if avg_asymmetry > 1.5:
                strategy += ' + Put bias'
                reasoning.append('Fluxo direcional favorece puts')
            elif avg_asymmetry < 0.7:
                strategy += ' + Call bias'
                reasoning.append('Fluxo direcional favorece calls')
        
        # VENDA DE VOLATILIDADE
        elif avg_squeeze > 1.5 and regime_current == 0:
            signal = 'SELL_VOLATILITY'
            confidence = 75
            strategy = 'Iron Condor'
            reasoning = [
                f'Squeeze alto ({avg_squeeze:.3f}) indica expansão máxima',
                f'Regime {regime_current} sugere baixa volatilidade'
            ]
        
        # ESTRATÉGIAS DIRECIONAIS
        elif 0.8 <= avg_squeeze <= 1.5:
            if avg_asymmetry > 1.5:
                signal = 'PUT_BIAS'
                confidence = 70
                strategy = 'Put Spread'
                reasoning = [
                    f'Assimetria alta ({avg_asymmetry:.2f}) favorece quedas',
                    'Squeeze neutro permite estratégia direcional'
                ]
            elif avg_asymmetry < 0.7:
                signal = 'CALL_BIAS'
                confidence = 70
                strategy = 'Call Spread'
                reasoning = [
                    f'Assimetria baixa ({avg_asymmetry:.2f}) favorece altas',
                    'Squeeze neutro permite estratégia direcional'
                ]
        
        # Adicionar ao DataFrame
        df.loc[df.index[-1], 'combined_signal'] = signal
        df.loc[df.index[-1], 'signal_confidence'] = confidence
        df.loc[df.index[-1], 'recommended_strategy'] = strategy
        
        return df, {
            'signal': signal,
            'confidence': confidence,
            'strategy': strategy,
            'reasoning': reasoning,
            'metrics': {
                'squeeze_score': avg_squeeze,
                'asymmetry_ratio': avg_asymmetry,
                'current_regime': regime_current
            }
        }
    
    def get_analysis_summary(self, ticker: str, period: str = "6mo") -> Dict:
        try:
            # CORREÇÃO: Processar ticker corretamente
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
            
            # CORREÇÃO: Buscar preço atual/corrente em tempo real
            try:
                stock = yf.Ticker(search_ticker)
                # Tentar pegar dados intraday primeiro (1 minuto, último dia)
                current_data = stock.history(period="1d", interval="1m")
                
                if not current_data.empty:
                    # Preço mais recente (último tick)
                    current_price = float(current_data['Close'].iloc[-1])
                    last_update_time = current_data.index[-1]
                    self.logger.info(f"Preço corrente obtido: {current_price} às {last_update_time}")
                else:
                    # Fallback: usar último fechamento dos dados históricos
                    current_price = float(data['Close'].iloc[-1])
                    last_update_time = data.index[-1]
                    self.logger.warning(f"Usando último fechamento histórico: {current_price}")
                    
            except Exception as e:
                # Fallback final: último fechamento dos dados principais
                current_price = float(data['Close'].iloc[-1])
                last_update_time = data.index[-1]
                self.logger.warning(f"Erro ao buscar preço corrente, usando fechamento: {current_price} - {e}")
            
            # Calcular indicadores
            data = self.calculate_regime_clustering(data)
            data = self.calculate_directional_flow(data)
            data = self.calculate_squeeze_score(data)
            
            # Gerar sinais
            data, combined_signal = self.generate_combined_signals(data)
            
            # Estatísticas atuais
            latest = data.iloc[-1]
            
            # CORREÇÃO PRINCIPAL: Aplicar convert_to_json_safe em TODOS os valores
            summary = {
                'ticker': clean_ticker,
                'period': period,
                'data_points': len(data),
                'last_update': last_update_time.strftime('%Y-%m-%d %H:%M:%S'),
                'current_price': self.convert_to_json_safe(current_price),  # PREÇO CORRENTE
                'historical_close': self.convert_to_json_safe(latest['Close']),  # Último fechamento histórico
                
                # Métricas atuais - TODAS convertidas
                'metrics': {
                    'regime': {
                        'current': self.convert_to_json_safe(latest['regime']),
                        'name': str(latest['regime_name']),
                        'persistence': self.convert_to_json_safe(latest['regime_persistence'])
                    },
                    'directional': {
                        'asymmetry_ratio': self.convert_to_json_safe(latest['dir_asymmetry_ratio']),
                        'signal': str(latest['directional_signal']),
                        'strength': self.convert_to_json_safe(latest['directional_strength'])
                    },
                    'squeeze': {
                        'score': self.convert_to_json_safe(latest['squeeze_smooth']),
                        'signal': str(latest['squeeze_signal']),
                        'strength': self.convert_to_json_safe(latest['squeeze_strength'])
                    }
                },
                
                # Sinal combinado - TODOS convertidos
                'trading_signal': {
                    'signal': combined_signal['signal'],
                    'confidence': self.convert_to_json_safe(combined_signal['confidence']),
                    'strategy': combined_signal['strategy'],
                    'reasoning': combined_signal['reasoning'],
                    'metrics': {
                        'squeeze_score': self.convert_to_json_safe(combined_signal['metrics']['squeeze_score']),
                        'asymmetry_ratio': self.convert_to_json_safe(combined_signal['metrics']['asymmetry_ratio']),
                        'current_regime': self.convert_to_json_safe(combined_signal['metrics']['current_regime'])
                    }
                },
                
                # Dados para gráficos (últimos 50 pontos) - TODOS convertidos
                'chart_data': [
                    {
                        'Close': self.convert_to_json_safe(row['Close']),
                        'regime': self.convert_to_json_safe(row['regime']),
                        'squeeze_smooth': self.convert_to_json_safe(row['squeeze_smooth']),
                        'dir_asymmetry_ratio': self.convert_to_json_safe(row['dir_asymmetry_ratio'])
                    }
                    for _, row in data.tail(50).iterrows()
                ],
                
                'success': True
            }
            
            self.logger.info(f"Análise concluída para {clean_ticker}: {combined_signal['signal']} - Preço corrente: R$ {current_price:.2f}")
            return summary
            
        except Exception as e:
            self.logger.error(f"Erro na análise: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e), 'success': False}
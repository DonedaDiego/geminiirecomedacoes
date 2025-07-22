import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
import yfinance as yf
from datetime import datetime, timedelta

class RegimesVolatilidadeService:
    def __init__(self):
        pass
    
    def analisar_acao(self, symbol, period='6mo'):
        """Análise completa de regimes de volatilidade"""
        try:
            # Buscar dados
            ticker = f"{symbol}.SA" if not symbol.endswith('.SA') else symbol
            data = yf.download(ticker, period=period, interval='1d')
            
            if data.empty:
                return {"success": False, "error": "Dados não encontrados"}
            
            # Calcular indicadores
            data = self._calcular_indicadores(data)
            
            # K-means para regimes
            regimes = self._calcular_regimes(data)
            
            # Assimetria direcional
            assimetria = self._calcular_assimetria(data)
            
            # Squeeze score
            squeeze = self._calcular_squeeze(data)
            
            # Gerar sinal
            sinal = self._gerar_sinal(regimes, assimetria, squeeze)
            
            return {
                "success": True,
                "symbol": symbol,
                "current_price": float(data['Close'].iloc[-1]),
                "last_update": datetime.now().isoformat(),
                "trading_signal": sinal,
                "metrics": {
                    "regime": regimes,
                    "directional": assimetria,
                    "squeeze": squeeze
                },
                "chart_data": self._preparar_chart_data(data)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _calcular_indicadores(self, data):
        """Calcula indicadores técnicos manualmente"""
        # Volatilidade realizada
        data['returns'] = data['Close'].pct_change()
        data['volatility'] = data['returns'].rolling(20).std() * np.sqrt(252)
        
        # Bollinger Bands (manual) - CORRIGIDO
        sma_20 = data['Close'].rolling(20).mean()
        std_20 = data['Close'].rolling(20).std()
        data['bb_upper'] = sma_20 + (2 * std_20)
        data['bb_lower'] = sma_20 - (2 * std_20)
        data['bb_width'] = (data['bb_upper'] - data['bb_lower']) / data['Close']
        
        # Keltner Channels (manual) - CORRIGIDO
        ema_20 = data['Close'].ewm(span=20).mean()
        
        # True Range calculation - CORRIGIDO
        high_low = data['High'] - data['Low']
        high_close = abs(data['High'] - data['Close'].shift(1))
        low_close = abs(data['Low'] - data['Close'].shift(1))
        
        # Calcular True Range corretamente
        tr_df = pd.DataFrame({
            'hl': high_low,
            'hc': high_close, 
            'lc': low_close
        })
        true_range = tr_df.max(axis=1)
        atr_20 = true_range.rolling(20).mean()
        
        data['kc_upper'] = ema_20 + (2 * atr_20)
        data['kc_lower'] = ema_20 - (2 * atr_20)
        data['kc_width'] = (data['kc_upper'] - data['kc_lower']) / data['Close']
        
        # ATR
        data['atr'] = atr_20
        
        return data.dropna()
    
    def _calcular_regimes(self, data):
        """K-means clustering para regimes de volatilidade"""
        # Selecionar features válidas
        feature_cols = ['volatility', 'bb_width', 'atr']
        features = data[feature_cols].fillna(0)
        
        # Verificar se temos dados suficientes
        if len(features) < 10:
            return {
                "current": 1,
                "name": "Medium", 
                "persistence": 1,
                "history": [1] * len(features)
            }
        
        # Normalizar features
        features_norm = (features - features.mean()) / (features.std() + 1e-8)
        
        # K-means com 3 clusters
        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(features_norm)
        
        # Mapear clusters para regimes baseado na volatilidade média
        cluster_means = []
        for i in range(3):
            mask = clusters == i
            if mask.sum() > 0:
                avg_vol = features.loc[mask, 'volatility'].mean()
                cluster_means.append((i, avg_vol))
            else:
                cluster_means.append((i, 0))
        
        # Ordenar por volatilidade (0=Low, 1=Medium, 2=High)
        cluster_means.sort(key=lambda x: x[1])
        regime_mapping = {cluster_means[i][0]: i for i in range(3)}
        
        # Aplicar mapeamento
        regimes = [regime_mapping[c] for c in clusters]
        current_regime = regimes[-1]
        
        # Calcular persistência
        persistence = 1
        for i in range(len(regimes)-2, -1, -1):
            if regimes[i] == current_regime:
                persistence += 1
            else:
                break
        
        regime_names = ['Low', 'Medium', 'High']
        
        # Adicionar regimes ao DataFrame para os gráficos
        data['regime'] = regimes + [regimes[-1]] * (len(data) - len(regimes))
        
        return {
            "current": current_regime,
            "name": regime_names[current_regime],
            "persistence": persistence,
            "history": regimes
        }
    
    def _calcular_assimetria(self, data):
        """Calcula assimetria direcional (puts vs calls bias)"""
        returns = data['returns'].dropna()
        
        # Separar retornos positivos e negativos
        positive_returns = returns[returns > 0]
        negative_returns = returns[returns < 0]
        
        if len(positive_returns) == 0 or len(negative_returns) == 0:
            return {
                "signal": "NEUTRAL",
                "asymmetry_ratio": 1.0,
                "strength": 0,
                "put_bias": False,
                "call_bias": False
            }
        
        # Volatilidade dos movimentos
        vol_up = positive_returns.std()
        vol_down = abs(negative_returns.std())
        
        # Ratio de assimetria (>1 = quedas mais violentas, <1 = subidas mais violentas)
        asymmetry_ratio = vol_down / vol_up if vol_up > 0 else 1.0
        
        # Determinar sinal
        if asymmetry_ratio > 1.5:
            signal = "PUT_BIAS"
            strength = min((asymmetry_ratio - 1) * 50, 100)
        elif asymmetry_ratio < 0.7:
            signal = "CALL_BIAS" 
            strength = min((1 - asymmetry_ratio) * 50, 100)
        else:
            signal = "NEUTRAL"
            strength = 0
        
        return {
            "signal": signal,
            "asymmetry_ratio": float(asymmetry_ratio),
            "strength": float(strength),
            "put_bias": asymmetry_ratio > 1.5,
            "call_bias": asymmetry_ratio < 0.7
        }
    
    def _calcular_squeeze(self, data):
        """Calcula squeeze score (compressão vs expansão)"""
        # Bollinger vs Keltner squeeze
        bb_width = data['bb_width'].fillna(0)
        kc_width = data['kc_width'].fillna(0)
        
        # Squeeze score: BB dentro do Keltner = compressão
        squeeze_raw = bb_width / kc_width
        squeeze_smooth = squeeze_raw.rolling(5).mean().iloc[-1]
        
        # Determinar sinal
        if squeeze_smooth < 0.8:
            signal = "COMPRESSION"
            strength = (0.8 - squeeze_smooth) * 100
        elif squeeze_smooth > 1.5:
            signal = "EXPANSION"
            strength = (squeeze_smooth - 1.5) * 50
        else:
            signal = "NEUTRAL"
            strength = 0
        
        return {
            "signal": signal,
            "score": float(squeeze_smooth),
            "strength": float(min(strength, 100)),
            "compression": squeeze_smooth < 0.8,
            "expansion": squeeze_smooth > 1.5
        }
    
    def _gerar_sinal(self, regime, assimetria, squeeze):
        """Gera sinal de trading baseado nos 3 indicadores"""
        confidence = 50
        reasoning = []
        
        # Lógica principal
        if squeeze['compression'] and regime['current'] <= 1:
            signal = "BUY_VOLATILITY"
            strategy = "Long Straddle"
            confidence += 30
            reasoning.append("Compressão detectada + regime baixo/médio = explosão iminente")
            
        elif squeeze['expansion'] and regime['current'] == 0:
            signal = "SELL_VOLATILITY"
            strategy = "Iron Condor"
            confidence += 25
            reasoning.append("Expansão + regime baixo = venda de volatilidade")
            
        elif assimetria['put_bias']:
            signal = "PUT_BIAS"
            strategy = "Put Spread"
            confidence += 20
            reasoning.append("Quedas mais violentas que subidas detectadas")
            
        elif assimetria['call_bias']:
            signal = "CALL_BIAS"
            strategy = "Call Spread"
            confidence += 20
            reasoning.append("Subidas mais violentas que quedas detectadas")
            
        else:
            signal = "HOLD"
            strategy = "Aguardar"
            reasoning.append("Condições mistas - aguardar melhor oportunidade")
        
        # Ajustes de confiança
        if regime['persistence'] > 5:
            confidence += 10
            reasoning.append(f"Regime persistente há {regime['persistence']} dias")
        
        if squeeze['strength'] > 70:
            confidence += 15
            reasoning.append("Força do squeeze muito alta")
        
        return {
            "signal": signal,
            "strategy": strategy,
            "confidence": min(confidence, 95),
            "reasoning": reasoning
        }
    
    def _preparar_chart_data(self, data):
        """Prepara dados para os gráficos"""
        chart_data = []
        for i, (date, row) in enumerate(data.iterrows()):
            chart_data.append({
                "date": date.strftime('%Y-%m-%d'),
                "Close": float(row['Close']),
                "regime": 0,  # Simplificado
                "squeeze_smooth": float(row.get('bb_width', 0) / row.get('kc_width', 1)) if row.get('kc_width', 0) > 0 else 1,
                "dir_asymmetry_ratio": 1.0  # Simplificado
            })
        return chart_data[-60:]  # Últimos 60 dias
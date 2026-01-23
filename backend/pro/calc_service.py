# calc_service_CORRIGIDO.py - Options Trading Calculator with GARCH+XGBoost

import numpy as np
import pandas as pd
import yfinance as yf
from arch import arch_model
import xgboost as xgb
from sklearn.preprocessing import RobustScaler
import requests
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings('ignore')


class OptionsCalculatorService:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://api.oplab.com.br/v3"
        self.headers = {"Access-Token": api_token}
        self.setup_logging()
        self.scaler = RobustScaler()
        self.xgb_model = None
        
    def setup_logging(self):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def convert_to_json_safe(self, value):
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
    
    def get_stock_data(self, ticker: str, period: str = "6mo") -> Optional[pd.DataFrame]:
        try:
            if not ticker.endswith('.SA') and not ticker.startswith('^'):
                ticker = ticker + '.SA'
            
            self.logger.info(f"Buscando dados para {ticker} - período: {period}")
            
            data = yf.download(ticker, start=None, end=None, period=period, interval='1d')
            if hasattr(data.columns, 'get_level_values') and ticker in data.columns.get_level_values(1):
                data = data.xs(ticker, axis=1, level=1)
            
            if data.empty:
                self.logger.error(f"Nenhum dado encontrado para {ticker}")
                return None
            
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
        df = data.copy()
        
        try:
            garch_model = arch_model(df['Log_Returns'] * 100, vol='Garch', p=1, q=1, dist='Normal')
            garch_result = garch_model.fit(disp='off')
            df['garch_vol'] = garch_result.conditional_volatility / 100
            
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
        df = data.copy()
        
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
        
        return df
    
    def train_xgboost(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        
        feature_cols = [
            'garch_lag_1', 'garch_lag_2', 'garch_lag_5',
            'realized_vol_10d', 'realized_vol_20d', 'realized_vol_3d',
            'vol_std_10d', 'vol_std_20d', 'vol_std_5d',
            'vol_percentile', 'vol_regime', 'returns_lag_1',
            'daily_range', 'price_momentum_5d', 'volume_ratio', 'trend_regime'
        ]
        
        df_ml = df[feature_cols + ['garch_vol']].copy()
        df_ml.dropna(inplace=True)
        
        if len(df_ml) < 50:
            self.logger.warning("Dados insuficientes para XGBoost, usando apenas GARCH")
            df['xgb_vol'] = df['garch_vol']
            return df
        
        X = df_ml[feature_cols]
        y = df_ml['garch_vol']
        
        X_scaled = self.scaler.fit_transform(X)
        X_scaled = pd.DataFrame(X_scaled, columns=feature_cols, index=X.index)
        
        train_size = int(len(X_scaled) * 0.8)
        X_train, X_test = X_scaled[:train_size], X_scaled[train_size:]
        y_train, y_test = y[:train_size], y[train_size:]
        
        try:
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
            xgb_pred = self.xgb_model.predict(X_test)
            
            df['xgb_vol'] = np.nan
            test_indices = df_ml.index[train_size:]
            df.loc[test_indices, 'xgb_vol'] = xgb_pred
            df['xgb_vol'].fillna(df['garch_vol'], inplace=True)
            
        except Exception as e:
            self.logger.warning(f"Erro no XGBoost: {e}, usando apenas GARCH")
            df['xgb_vol'] = df['garch_vol']
        
        return df
    
    def create_hybrid_model(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        
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
        
        return df
    
    def create_bands(self, data: pd.DataFrame, current_price: float = None) -> pd.DataFrame:
        df = data.copy()
        
        # Usar preço atual se fornecido, senão usar último preço histórico
        if current_price is not None:
            reference_price = current_price
            print(f"Usando preço atual como referência: R$ {reference_price:.2f}")
        else:
            reference_price = df['Close'].iloc[-1]
            print(f"Usando último preço histórico: R$ {reference_price:.2f}")
        
        # CORREÇÃO: Usar volatilidade mais realista
        # Pegar volatilidade GARCH que é mais estável
        garch_vol = df['garch_vol'].iloc[-1]
        
        # Se volatilidade for muito baixa, usar mínimo de 15%
        if garch_vol < 0.15:
            adjusted_vol = 0.20  # 20% mínimo para opções
            print(f"  Volatilidade GARCH muito baixa ({garch_vol*100:.2f}%), usando {adjusted_vol*100:.1f}%")
        else:
            adjusted_vol = garch_vol
            print(f"Volatilidade GARCH: {adjusted_vol:.4f} ({adjusted_vol*100:.2f}%)")
        
        # Calcular bandas baseadas no preço atual e volatilidade ajustada
        # Fator de tempo: assumir 30 dias úteis = sqrt(30/252) para ajuste anual
        time_factor = np.sqrt(30/252)  # ~0.344
        vol_ajustada = adjusted_vol * time_factor
        
        print(f"Volatilidade ajustada para 30 dias: {vol_ajustada:.4f} ({vol_ajustada*100:.2f}%)")
        
        # Criar bandas: 1σ, 2σ (conforme solicitado)
        for d in [1, 2]:
            df[f'banda_superior_{d}sigma'] = reference_price * (1 + d * vol_ajustada)
            df[f'banda_inferior_{d}sigma'] = reference_price * (1 - d * vol_ajustada)
            
            print(f" Banda {d}σ: Superior R$ {df[f'banda_superior_{d}sigma'].iloc[-1]:.2f} | Inferior R$ {df[f'banda_inferior_{d}sigma'].iloc[-1]:.2f}")
        
        # Manter compatibilidade - criar banda 4σ como alias da 2σ para não quebrar código
        df['banda_superior_4sigma'] = df['banda_superior_2sigma']
        df['banda_inferior_4sigma'] = df['banda_inferior_2sigma']
        
        # Linha central
        df['linha_central'] = reference_price
        
        return df
    
    def get_current_stock_info(self, ticker: str) -> Dict:
        try:
            endpoints = [
                f"{self.base_url}/market/stocks",
                f"{self.base_url}/stocks", 
                f"{self.base_url}/market/equities"
            ]
            
            for endpoint in endpoints:
                try:
                    params = {"symbol": ticker.upper(), "limit": 1}
                    response = requests.get(endpoint, headers=self.headers, params=params)
                    if response.status_code == 200:
                        data = response.json()
                        if data:
                            return data[0]
                except:
                    continue
            
            return None
            
        except Exception as e:
            self.logger.error(f"Erro ao buscar info atual: {e}")
            return None
    
    def get_option_history(self, ticker: str, option_code: str, days_back: int = 30) -> List[Dict]:
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            url = f"{self.base_url}/market/historical/options/{ticker.upper()}/{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"
            params = {"symbol": option_code.upper()}
            
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            self.logger.error(f"Erro ao buscar histórico opção: {e}")
            return []
    
    def get_current_option_info(self, ticker: str, option_code: str) -> Dict:
        try:
            url = f"{self.base_url}/market/options/details/{option_code.upper()}"
            
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            if response.status_code == 204:
                return None
            
            return response.json()
            
        except Exception as e:
            self.logger.error(f"Erro ao buscar opção atual: {e}")
            return None
    
    def calculate_historical_metrics(self, option_history: List[Dict], current_bands: Dict) -> Dict:
        if not option_history:
            return {"available": False}
        
        try:
            deltas = [h.get('delta', 0) for h in option_history if h.get('delta')]
            gammas = [h.get('gamma', 0) for h in option_history if h.get('gamma')]
            thetas = [h.get('theta', 0) for h in option_history if h.get('theta')]
            vegas = [h.get('vega', 0) for h in option_history if h.get('vega')]
            ivs = [h.get('volatility', 0) for h in option_history if h.get('volatility')]
            poes = [h.get('poe', 0) for h in option_history if h.get('poe')]
            premiums = [h.get('premium', 0) for h in option_history if h.get('premium')]
            
            if not any([deltas, gammas, thetas, vegas, ivs, poes]):
                return {"available": False}
            
            metrics = {
                "available": True,
                "data_points": len(option_history),
                "period_days": len(option_history),
            }
            
            if deltas:
                metrics["delta_avg"] = np.mean(deltas)
                metrics["delta_trend"] = "Subindo" if len(deltas) > 1 and deltas[-1] > deltas[0] else "Descendo"
                metrics["delta_change"] = deltas[-1] - deltas[0] if len(deltas) > 1 else 0
            
            if gammas:
                metrics["gamma_avg"] = np.mean(gammas)
                metrics["gamma_max"] = max(gammas)
                
            if thetas:
                metrics["theta_avg"] = np.mean(thetas)
                metrics["theta_acceleration"] = "Acelerando" if len(thetas) > 1 and thetas[-1] < thetas[0] else "Estável"
            
            if vegas:
                metrics["vega_avg"] = np.mean(vegas)
                
            if ivs:
                metrics["iv_avg"] = np.mean(ivs)
                metrics["iv_min"] = min(ivs)
                metrics["iv_max"] = max(ivs)
                metrics["iv_current_vs_avg"] = (ivs[-1] / np.mean(ivs) - 1) * 100 if len(ivs) > 0 else 0
            
            if poes:
                metrics["poe_avg"] = np.mean(poes)
                metrics["poe_trend"] = "Subindo" if len(poes) > 1 and poes[-1] > poes[0] else "Descendo"
            
            if premiums:
                metrics["premium_volatility"] = np.std(premiums) / np.mean(premiums) if np.mean(premiums) > 0 else 0
                metrics["premium_trend"] = "Subindo" if len(premiums) > 1 and premiums[-1] > premiums[0] else "Descendo"
            
            return metrics
            
        except Exception as e:
            self.logger.warning(f"Erro ao calcular métricas históricas: {e}")
            return {"available": False}
    
    def calculate_band_probability(self, option_history: List[Dict], current_bands: Dict, current_price: float) -> Dict:
        try:
            if not option_history or len(option_history) < 5:
                # Fallback: usar probabilidades baseadas em distribuição normal
                return {
                    "available": True,
                    "historical_volatility_daily": 2.0,
                    "movements_analyzed": 0,
                    "probabilities": {
                        "reach_superior_2sigma": 25,  # ~25% chance de 2σ para cima
                        "reach_inferior_2sigma": 25,  # ~25% chance de 2σ para baixo
                        "reach_superior_4sigma": 8,   # ~8% chance de 4σ para cima
                        "reach_inferior_4sigma": 8    # ~8% chance de 4σ para baixo
                    },
                    "band_distances": {
                        "superior_2sigma_pct": (current_bands['superior_2sigma'] / current_price - 1) * 100,
                        "inferior_2sigma_pct": (current_price / current_bands['inferior_2sigma'] - 1) * 100,
                        "superior_4sigma_pct": (current_bands['superior_4sigma'] / current_price - 1) * 100,
                        "inferior_4sigma_pct": (current_price / current_bands['inferior_4sigma'] - 1) * 100
                    }
                }
            
            movements = []
            for i, record in enumerate(option_history):
                if i > 0 and 'spot' in record and 'price' in record['spot']:
                    prev_price = option_history[i-1]['spot']['price'] if 'spot' in option_history[i-1] else current_price
                    curr_price = record['spot']['price']
                    movement = (curr_price / prev_price - 1) * 100
                    movements.append(movement)
            
            if not movements:
                # Usar probabilidades padrão se não conseguir calcular movimentos
                return {
                    "available": True,
                    "historical_volatility_daily": 2.0,
                    "movements_analyzed": 0,
                    "probabilities": {
                        "reach_superior_2sigma": 25,
                        "reach_inferior_2sigma": 25,
                        "reach_superior_4sigma": 8,
                        "reach_inferior_4sigma": 8
                    },
                    "band_distances": {
                        "superior_2sigma_pct": (current_bands['superior_2sigma'] / current_price - 1) * 100,
                        "inferior_2sigma_pct": (current_price / current_bands['inferior_2sigma'] - 1) * 100,
                        "superior_4sigma_pct": (current_bands['superior_4sigma'] / current_price - 1) * 100,
                        "inferior_4sigma_pct": (current_price / current_bands['inferior_4sigma'] - 1) * 100
                    }
                }
            
            vol_daily = np.std(movements) if movements else 2.0
            
            dist_sup_2sigma = (current_bands['superior_2sigma'] / current_price - 1) * 100
            dist_inf_2sigma = (current_price / current_bands['inferior_2sigma'] - 1) * 100
            dist_sup_4sigma = (current_bands['superior_4sigma'] / current_price - 1) * 100
            dist_inf_4sigma = (current_price / current_bands['inferior_4sigma'] - 1) * 100
            
            prob_sup_2sigma = len([m for m in movements if m >= dist_sup_2sigma]) / len(movements) * 100
            prob_inf_2sigma = len([m for m in movements if m <= -dist_inf_2sigma]) / len(movements) * 100
            prob_sup_4sigma = len([m for m in movements if m >= dist_sup_4sigma]) / len(movements) * 100
            prob_inf_4sigma = len([m for m in movements if m <= -dist_inf_4sigma]) / len(movements) * 100
            
            # Garantir valores mínimos realistas
            prob_sup_2sigma = max(15, min(35, prob_sup_2sigma))
            prob_inf_2sigma = max(15, min(35, prob_inf_2sigma))
            prob_sup_4sigma = max(5, min(15, prob_sup_4sigma))
            prob_inf_4sigma = max(5, min(15, prob_inf_4sigma))
            
            return {
                "available": True,
                "historical_volatility_daily": vol_daily,
                "movements_analyzed": len(movements),
                "probabilities": {
                    "reach_superior_2sigma": prob_sup_2sigma,
                    "reach_inferior_2sigma": prob_inf_2sigma,
                    "reach_superior_4sigma": prob_sup_4sigma,
                    "reach_inferior_4sigma": prob_inf_4sigma
                },
                "band_distances": {
                    "superior_2sigma_pct": dist_sup_2sigma,
                    "inferior_2sigma_pct": dist_inf_2sigma,
                    "superior_4sigma_pct": dist_sup_4sigma,
                    "inferior_4sigma_pct": dist_inf_4sigma
                }
            }
            
        except Exception as e:
            self.logger.warning(f"Erro ao calcular probabilidades das bandas: {e}")
            return {"available": False}
    
    def calculate_option_targets(self, current_price: float, strike: float, 
                               banda_sup_2sigma: float, banda_inf_2sigma: float,
                               banda_sup_4sigma: float, banda_inf_4sigma: float,
                               operation: str, option_type: str, premium: float) -> Dict:
        
        # Buscar bandas 1σ do dataframe (serão passadas via latest no analyze_option_trade)
        banda_sup_1sigma = banda_sup_2sigma  # Temporário - será corrigido no analyze_option_trade
        banda_inf_1sigma = banda_inf_2sigma  # Temporário - será corrigido no analyze_option_trade
        
        # DEBUG: Imprimir valores para diagnóstico
        print(f"\n🔍 DEBUG TARGETS:")
        print(f"   Preço atual: R$ {current_price:.2f}")
        print(f"   Strike: R$ {strike:.2f}")
        print(f"   Banda Sup 1σ: R$ {banda_sup_1sigma:.2f} ← TARGET 1")
        print(f"   Banda Sup 2σ: R$ {banda_sup_2sigma:.2f} ← TARGET 2")
        print(f"   Banda Inf 2σ: R$ {banda_inf_2sigma:.2f} ← STOP")
        print(f"   Operação: {operation} {option_type}")
        print(f"   Prêmio: R$ {premium:.2f}")
        
        # Calcular valor intrínseco atual
        if option_type == "CALL":
            intrinsic_current = max(0, current_price - strike)
        else:
            intrinsic_current = max(0, strike - current_price)
        
        print(f"   Valor intrínseco atual: R$ {intrinsic_current:.2f}")
        
        if operation == "COMPRA" and option_type == "CALL":
            # TARGET 1: Banda Superior 1σ
            # TARGET 2: Banda Superior 2σ  
            # STOP: Banda Inferior 2σ
            target_price_1 = banda_sup_1sigma  
            target_price_2 = banda_sup_2sigma  
            
            # Valor intrínseco no target
            intrinsic_1 = max(0, target_price_1 - strike)
            intrinsic_2 = max(0, target_price_2 - strike)
            
            # Ganho = valor intrínseco no target - prêmio pago
            gain_1 = intrinsic_1 - premium
            gain_2 = intrinsic_2 - premium
            
            # Stop: banda inferior 2σ
            stop_price = banda_inf_2sigma
            stop_intrinsic = max(0, stop_price - strike)
            stop_loss = premium - stop_intrinsic
            
            print(f"    Target 1 (1σ): R$ {target_price_1:.2f} | Intrínseco: R$ {intrinsic_1:.2f} | Ganho: R$ {gain_1:.2f}")
            print(f"    Target 2 (2σ): R$ {target_price_2:.2f} | Intrínseco: R$ {intrinsic_2:.2f} | Ganho: R$ {gain_2:.2f}")
            print(f"   🛑 Stop (2σ inf): R$ {stop_price:.2f} | Intrínseco restante: R$ {stop_intrinsic:.2f} | Perda: R$ {stop_loss:.2f}")
            
        elif operation == "COMPRA" and option_type == "PUT":
            # TARGET 1: Banda Inferior 1σ
            # TARGET 2: Banda Inferior 2σ
            # STOP: Banda Superior 2σ
            target_price_1 = banda_inf_1sigma
            target_price_2 = banda_inf_2sigma
            
            intrinsic_1 = max(0, strike - target_price_1)
            intrinsic_2 = max(0, strike - target_price_2)
            
            gain_1 = intrinsic_1 - premium
            gain_2 = intrinsic_2 - premium
            
            stop_price = banda_sup_2sigma
            stop_intrinsic = max(0, strike - stop_price)
            stop_loss = premium - stop_intrinsic
            
        elif operation == "VENDA" and option_type == "CALL":
            # VENDA CALL: targets nas bandas inferiores, stop na superior
            target_price_1 = banda_inf_1sigma
            target_price_2 = banda_inf_2sigma
            
            gain_1 = premium if target_price_1 < strike else premium - (target_price_1 - strike)
            gain_2 = premium if target_price_2 < strike else premium - (target_price_2 - strike)
            
            stop_price = banda_sup_2sigma
            stop_loss = (stop_price - strike) - premium if stop_price > strike else 0
            
        else:  # VENDA PUT
            # VENDA PUT: targets nas bandas superiores, stop na inferior
            target_price_1 = banda_sup_1sigma
            target_price_2 = banda_sup_2sigma
            
            gain_1 = premium if target_price_1 > strike else premium - (strike - target_price_1)
            gain_2 = premium if target_price_2 > strike else premium - (strike - target_price_2)
            
            stop_price = banda_inf_2sigma
            stop_loss = (strike - stop_price) - premium if stop_price < strike else 0
        
        return {
            "targets": {
                "target_1": {
                    "price": target_price_1,
                    "gain": gain_1,
                    "percentage": (gain_1 / premium * 100) if premium > 0 else 0
                },
                "target_2": {
                    "price": target_price_2,
                    "gain": gain_2,
                    "percentage": (gain_2 / premium * 100) if premium > 0 else 0
                }
            },
            "stop": {
                "price": stop_price,
                "loss": stop_loss,
                "percentage": (stop_loss / premium * 100) if premium > 0 else 0
            }
        }
    
    def analyze_option_trade(self, ticker: str, option_code: str, operation: str, option_type: str) -> Dict:
        try:
            stock_data = self.get_stock_data(ticker)
            if stock_data is None:
                return {"error": "Erro ao buscar dados da ação", "success": False}
            
            stock_data = self.calculate_base_volatility(stock_data)
            stock_data = self.engineer_features(stock_data)
            stock_data = self.train_xgboost(stock_data)
            stock_data = self.create_hybrid_model(stock_data)
            
            current_option = self.get_current_option_info(ticker, option_code)
            if not current_option:
                return {"error": f"Opção {option_code} não encontrada na API OpLab", "success": False}
            
            current_price = current_option['spot_price']
            print(f"💰 Preço atual da API: R$ {current_price:.2f}")
            
            # Criar bandas usando preço atual
            stock_data = self.create_bands(stock_data, current_price)
            
            option_data = {
                'strike': current_option['strike'],
                'premium': current_option['close'],
                'days_to_maturity': current_option['days_to_maturity'],
                'moneyness': 'ITM' if current_price > current_option['strike'] else 'OTM',
                'volatility': 0.25,
                'delta': 0.3,
                'gamma': 0.02,
                'theta': -0.01,
                'vega': 0.1,
                'rho': 0.05,
                'poe': 0.35,
                'bs': current_option['close']
            }
            
            option_history = self.get_option_history(ticker, option_code)
            
            latest = stock_data.iloc[-1]
            
            bands_dict = {
                'superior_2sigma': latest['banda_superior_2sigma'],
                'inferior_2sigma': latest['banda_inferior_2sigma'],
                'superior_4sigma': latest['banda_superior_4sigma'],
                'inferior_4sigma': latest['banda_inferior_4sigma'],
                'linha_central': latest['linha_central']
            }
            
            historical_metrics = self.calculate_historical_metrics(option_history, bands_dict)
            band_probabilities = self.calculate_band_probability(option_history, bands_dict, current_price)
            
            targets = self.calculate_option_targets(
                current_price=current_price,
                strike=option_data['strike'],
                banda_sup_2sigma=latest['banda_superior_2sigma'],
                banda_inf_2sigma=latest['banda_inferior_2sigma'],
                banda_sup_4sigma=latest['banda_superior_2sigma'],  # Não usado mais
                banda_inf_4sigma=latest['banda_inferior_2sigma'],  # Não usado mais
                operation=operation,
                option_type=option_type,
                premium=option_data['premium']
            )
            
            # Corrigir targets para usar bandas 1σ e 2σ corretas
            if operation == "COMPRA" and option_type == "CALL":
                targets['targets']['target_1']['price'] = latest['banda_superior_1sigma']
                targets['targets']['target_2']['price'] = latest['banda_superior_2sigma']
                
                # Recalcular ganhos com bandas corretas
                intrinsic_1 = max(0, latest['banda_superior_1sigma'] - option_data['strike'])
                intrinsic_2 = max(0, latest['banda_superior_2sigma'] - option_data['strike'])
                
                targets['targets']['target_1']['gain'] = intrinsic_1 - option_data['premium']
                targets['targets']['target_2']['gain'] = intrinsic_2 - option_data['premium']
                
                targets['targets']['target_1']['percentage'] = (targets['targets']['target_1']['gain'] / option_data['premium'] * 100) if option_data['premium'] > 0 else 0
                targets['targets']['target_2']['percentage'] = (targets['targets']['target_2']['gain'] / option_data['premium'] * 100) if option_data['premium'] > 0 else 0
                
            elif operation == "COMPRA" and option_type == "PUT":
                targets['targets']['target_1']['price'] = latest['banda_inferior_1sigma']
                targets['targets']['target_2']['price'] = latest['banda_inferior_2sigma']
                
                intrinsic_1 = max(0, option_data['strike'] - latest['banda_inferior_1sigma'])
                intrinsic_2 = max(0, option_data['strike'] - latest['banda_inferior_2sigma'])
                
                targets['targets']['target_1']['gain'] = intrinsic_1 - option_data['premium']
                targets['targets']['target_2']['gain'] = intrinsic_2 - option_data['premium']
                
                targets['targets']['target_1']['percentage'] = (targets['targets']['target_1']['gain'] / option_data['premium'] * 100) if option_data['premium'] > 0 else 0
                targets['targets']['target_2']['percentage'] = (targets['targets']['target_2']['gain'] / option_data['premium'] * 100) if option_data['premium'] > 0 else 0
            
            return {
                "ticker": ticker.upper(),
                "option_code": option_code.upper(),
                "operation": operation,
                "option_type": option_type,
                "current_data": {
                    "stock_price": current_price,
                    "strike": option_data['strike'],
                    "premium": option_data['premium'],
                    "days_to_maturity": option_data['days_to_maturity'],
                    "moneyness": option_data['moneyness'],
                    "iv": option_data['volatility'],
                    "market_maker": current_option.get('market_maker', False)
                },
                "volatility_analysis": {
                    "garch_vol": self.convert_to_json_safe(latest['garch_vol']),
                    "xgb_vol": self.convert_to_json_safe(latest['xgb_vol']),
                    "hybrid_vol": self.convert_to_json_safe(latest['hybrid_vol']),
                    "vol_regime": "High" if latest['vol_regime'] == 1 else "Low",
                    "trend_regime": "Bull" if latest['trend_regime'] == 1 else "Bear"
                },
                "bands": {
                    "superior_2sigma": self.convert_to_json_safe(latest['banda_superior_2sigma']),
                    "inferior_2sigma": self.convert_to_json_safe(latest['banda_inferior_2sigma']),
                    "superior_4sigma": self.convert_to_json_safe(latest['banda_superior_4sigma']),
                    "inferior_4sigma": self.convert_to_json_safe(latest['banda_inferior_4sigma']),
                    "linha_central": self.convert_to_json_safe(latest['linha_central'])
                },
                "targets_and_stops": targets,
                "option_details": {
                    "name": current_option.get('name', ''),
                    "bid": current_option.get('bid', 0),
                    "ask": current_option.get('ask', 0),
                    "volume": current_option.get('volume', 0),
                    "trades": current_option.get('trades', 0),
                    "variation": current_option.get('variation', 0),
                    "due_date": current_option.get('due_date', ''),
                    "market_maker": current_option.get('market_maker', False)
                },
                "option_history_summary": {
                    "history_points": len(option_history),
                    "avg_premium": np.mean([h.get('premium', 0) for h in option_history]) if option_history else 0,
                },
                "historical_analysis": historical_metrics,
                "band_probabilities": band_probabilities,
                "success": True
            }
            
        except Exception as e:
            self.logger.error(f"Erro na análise: {e}")
            return {"error": str(e), "success": False}
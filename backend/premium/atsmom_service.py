import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings 
warnings.simplefilter('ignore')

class ATSMOMService:
    def __init__(self):
        pass
    
    def get_data(self, symbol, period="5y"):
        """Obtém dados do Yahoo Finance - IGUAL AO CÓDIGO ORIGINAL"""
        try:
            # Para símbolos brasileiros, adiciona .SA se não estiver presente
            if symbol == 'IBOV':
                ticker_symbol = '^BVSP'  # Índice Bovespa
            elif not symbol.endswith('.SA') and len(symbol) <= 6:
                ticker_symbol = f"{symbol}.SA"
            else:
                ticker_symbol = symbol
                
            ticker = yf.Ticker(ticker_symbol)
            data = ticker.history(period=period)
            
            if data.empty:
                print(f"Nenhum dado encontrado para {symbol}")
                return None
                
            # Converte para o formato esperado (similar ao MT5)
            df = pd.DataFrame()
            df['open'] = data['Open']
            df['high'] = data['High']
            df['low'] = data['Low']
            df['close'] = data['Close']
            df['volume'] = data['Volume']
            df['time'] = data.index
            df.set_index('time', inplace=True)
            
            return df
            
        except Exception as e:
            print(f"Erro ao obter dados para {symbol}: {e}")
            return None

    def calculate_beta(self, asset_returns, market_returns):
        """Calcula o beta do ativo em relação ao mercado - IGUAL AO CÓDIGO ORIGINAL"""
        covariance = np.cov(asset_returns, market_returns)[0,1]
        market_variance = np.var(market_returns)
        beta = covariance / market_variance
        return beta

    def calculate_atsmom(self, data, min_lookback=20, max_lookback=260,
                        vol_window=60, max_leverage=3):

        # Retornos diários
        returns = data['close'].pct_change()
        returns = returns.fillna(0)

        # Volatilidade EWMA anualizada
        volatility = returns.ewm(span=vol_window, min_periods=vol_window//2).std() * np.sqrt(252)

        # M1 — vol_target adaptativo pelo histórico do próprio ativo
        hist_vol = volatility.rolling(252, min_periods=60).mean().iloc[-1]
        hist_vol = hist_vol if not np.isnan(hist_vol) else 0.40
        vol_target = float(np.clip(hist_vol, 0.25, 0.60))

        # Ensemble de momentum multi-lookback
        signals = []
        weights = np.linspace(1.5, 1.0, max_lookback - min_lookback + 1)

        for lookback, weight in zip(range(min_lookback, max_lookback + 1), weights):
            period_return = data['close'].pct_change(lookback)
            vol_adj_return = period_return / (returns.rolling(lookback).std() * np.sqrt(lookback))
            signal = np.sign(vol_adj_return) * weight
            signals.append(signal)

        combined_signal = pd.concat(signals, axis=1).mean(axis=1)
        combined_signal = combined_signal / combined_signal.abs().max()

        # Sizing pelo vol-target — única penalização de vol (M3)
        position_size = (vol_target / np.sqrt(252)) / volatility
        position_size = position_size.clip(-max_leverage, max_leverage)

        final_signal = combined_signal * position_size

        # M2 — filtro MA200 com transição suave via tanh
        long_ma = data['close'].rolling(window=200).mean()
        dist_from_ma = (data['close'] - long_ma) / long_ma
        trend_filter = np.tanh(dist_from_ma * 10)
        trend_filter = trend_filter.fillna(0)

        final_signal = final_signal * trend_filter

        # M5 — suavização com span coerente ao horizonte do modelo
        final_signal = final_signal.ewm(span=15).mean()

        # M3 — vol_scale removido (position_size já escala por volatilidade)

        final_signal = final_signal.fillna(0)
        combined_signal = combined_signal.fillna(0)
        volatility = volatility.fillna(0)

        return final_signal, combined_signal, volatility, returns
   
    def analyze_single_asset(self, symbol):
        """Análise principal - CORRIGIDO para mostrar dados reais dos 5 anos"""
        print(f"Obtendo dados para {symbol}...")
        
        # Obtém dados do ativo e do IBOV
        data = self.get_data(symbol)
        ibov_data = self.get_data('IBOV')
        
        if data is None or ibov_data is None:
            return {
                'success': False,
                'error': f"Erro ao obter dados para {symbol} ou IBOV"
            }
        
        print(f"Dados obtidos com sucesso! Período: {data.index[0].strftime('%Y-%m-%d')} a {data.index[-1].strftime('%Y-%m-%d')}")
        
        # ATSMOM - mantém análise original
        final_signal, trend_strength, vol, returns = self.calculate_atsmom(data)
        ibov_signal, ibov_trend, ibov_vol, ibov_returns = self.calculate_atsmom(ibov_data)
                
        chart_html = None
        
        # Calcula métricas básicas
        current_price = float(data['close'].iloc[-1])
        current_signal = float(final_signal.iloc[-1]) if len(final_signal) > 0 else 0.0
        current_trend = float(trend_strength.iloc[-1]) if len(trend_strength) > 0 else 0.0
        current_vol = float(vol.iloc[-1]) if len(vol) > 0 else 0.0
        beta = self.calculate_beta(returns, ibov_returns)
        
        # Determina status do sinal (SEM limitadores artificiais)
        if current_signal > 0.3:
            signal_status = "COMPRA"
        elif current_signal > 0.1:
            signal_status = "VIÉS COMPRA"
        elif current_signal < -0.3:
            signal_status = "VENDA"
        elif current_signal < -0.1:
            signal_status = "VIÉS VENDA"
        else:
            signal_status = "NEUTRO"
        
        # Estatísticas dos 5 anos para contexto
        price_max = float(data['close'].max())
        price_min = float(data['close'].min())
        price_avg = float(data['close'].mean())
        
        # Variação percentual do período
        price_start = float(data['close'].iloc[0])
        price_change_pct = ((current_price - price_start) / price_start) * 100
        
        print("Análise concluída!")
        
        # Retorna dados estruturados para API - MELHORADO
        return {
            'success': True,
            'analysis_data': {
                'symbol': symbol.replace('.SA', ''),
                'current_price': round(current_price, 2),
                'current_signal': round(current_signal, 4),
                'current_trend': round(current_trend, 4),
                'current_volatility': round(current_vol * 100, 2),
                'signal_status': signal_status,
                'beta': round(beta, 2),
                'period_stats': {
                    'price_max': round(price_max, 2),
                    'price_min': round(price_min, 2),
                    'price_avg': round(price_avg, 2),
                    'price_change_pct': round(price_change_pct, 2),
                    'data_points': len(data),
                    'period': f"{data.index[0].strftime('%Y-%m-%d')} a {data.index[-1].strftime('%Y-%m-%d')}"
                },
                'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            },
            'chart_html': chart_html,
            'raw_data': {
                'dates':        [d.strftime('%Y-%m-%d') for d in data.index],
                'signals':      [round(float(x), 4) for x in final_signal],
                'trends':       [round(float(x), 4) for x in trend_strength],
                'ibov_signals': [round(float(x), 4) for x in ibov_signal],
                'ibov_trends':  [round(float(x), 4) for x in ibov_trend],
                'volatility':   [round(float(x) * 100, 2) for x in vol]
            }
        }

    def get_available_symbols(self):
        """Lista símbolos disponíveis"""
        return [
            'PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3',
            'MGLU3', 'WEGE3', 'RENT3', 'LREN3', 'JBSS3',
            'B3SA3', 'SUZB3', 'RAIL3', 'USIM5', 'CSNA3',
            'GOAU4', 'EMBJ3', 'CIEL3', 'JHSF3', 'TOTS3'
        ]

# Serviço pronto para uso com Flask
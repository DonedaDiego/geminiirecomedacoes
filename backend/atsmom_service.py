"""
ATSMOM - Adaptive Time Series Momentum Service
Adaptado do MetaTrader5 para yfinance
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
import json
from typing import Optional, Tuple, Dict, Any

warnings.simplefilter('ignore')

class ATSMOMService:
    def __init__(self):
        self.ibov_symbol = "^BVSP"
        
    def get_data(self, symbol: str, period: str = "2y") -> Optional[pd.DataFrame]:
        try:
            if not symbol.endswith('.SA') and not symbol.startswith('^'):
                symbol = f"{symbol}.SA"
            
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period)
            
            if data.empty:
                return None
            
            data.columns = [col.lower() for col in data.columns]
            
            if hasattr(data.index, 'tz') and data.index.tz is not None:
                data.index = data.index.tz_localize(None)
            
            return data
            
        except Exception as e:
            print(f"Erro ao obter dados para {symbol}: {e}")
            return None
    
    def calculate_beta(self, asset_returns: pd.Series, market_returns: pd.Series) -> float:
        try:
            aligned_data = pd.concat([asset_returns, market_returns], axis=1).dropna()
            if len(aligned_data) < 20:
                return 1.0
            
            asset_aligned = aligned_data.iloc[:, 0]
            market_aligned = aligned_data.iloc[:, 1]
            
            covariance = np.cov(asset_aligned, market_aligned)[0, 1]
            market_variance = np.var(market_aligned)
            
            if market_variance == 0:
                return 1.0
                
            beta = covariance / market_variance
            return beta
            
        except Exception as e:
            print(f"Erro ao calcular beta: {e}")
            return 1.0
    
    def calculate_atsmom(self, data: pd.DataFrame, min_lookback: int = 10, 
                        max_lookback: int = 260, vol_window: int = 60, 
                        vol_target: float = 0.4, max_leverage: float = 3) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
        try:
            returns = data['close'].pct_change()
            returns = returns.fillna(0)
            
            volatility = returns.ewm(span=vol_window, min_periods=vol_window//2).std() * np.sqrt(252)
            
            signals = []
            weights = np.linspace(1.5, 1.0, max_lookback - min_lookback + 1)
            
            for lookback, weight in zip(range(min_lookback, max_lookback + 1), weights):
                period_return = data['close'].pct_change(lookback)
                vol_adj_return = period_return / (returns.rolling(lookback).std() * np.sqrt(lookback))
                signal = np.sign(vol_adj_return) * weight
                signals.append(signal)
            
            combined_signal = pd.concat(signals, axis=1).mean(axis=1)
            combined_signal = combined_signal / combined_signal.abs().max()
            
            position_size = (vol_target/np.sqrt(252)) / volatility
            position_size = position_size.clip(-max_leverage, max_leverage)
            
            final_signal = combined_signal * position_size
            
            long_ma = data['close'].rolling(window=200).mean()
            trend_filter = (data['close'] > long_ma).astype(int) * 2 - 1
            
            final_signal = final_signal * trend_filter
            
            final_signal = final_signal.ewm(span=5).mean()
            
            vol_scale = (1 / (1 + (volatility / vol_target - 1).clip(0))).fillna(1)
            final_signal = final_signal * vol_scale
            
            final_signal = final_signal.replace([np.inf, -np.inf], 0).fillna(0)
            combined_signal = combined_signal.replace([np.inf, -np.inf], 0).fillna(0)
            volatility = volatility.replace([np.inf, -np.inf], 0.01).fillna(0.01)
            
            return final_signal, combined_signal, volatility, returns
            
        except Exception as e:
            print(f"Erro ao calcular ATSMOM: {e}")
            empty_series = pd.Series(index=data.index, data=0)
            return empty_series, empty_series, empty_series, empty_series
    
    def create_plotly_chart(self, data: pd.DataFrame, signal: pd.Series, trend: pd.Series, 
                           symbol: str, ibov_data: pd.DataFrame, ibov_signal: pd.Series, 
                           ibov_trend: pd.Series, strike: Optional[float] = None) -> str:
        try:
            fig = make_subplots(
                rows=3, cols=1,
                subplot_titles=(
                    f'{symbol} vs IBOV - Preço de Fechamento',
                    'Força da Tendência (ATSMOM)',
                    'Sinal Ajustado pela Volatilidade'
                ),
                vertical_spacing=0.1,
                row_heights=[0.4, 0.3, 0.3]
            )
            
            plot_bgcolor = '#11113a'
            paper_bgcolor = '#11113a'
            grid_color = 'rgba(255, 255, 255, 0.1)'
            
            fig.add_trace(
                go.Scatter(
                    x=data.index,
                    y=data['close'],
                    line=dict(color='#00FFAA', width=3),
                    name=symbol
                ),
                row=1, col=1
            )
            
            ibov_normalized = ibov_data['close'] / ibov_data['close'].iloc[0] * data['close'].iloc[0]
            fig.add_trace(
                go.Scatter(
                    x=ibov_data.index,
                    y=ibov_normalized,
                    line=dict(color='white', width=2, dash='solid'),
                    name='IBOV (normalizado)'
                ),
                row=1, col=1
            )
            
            if strike is not None:
                fig.add_hline(
                    y=strike,
                    line_dash="dash",
                    line_color="yellow",
                    annotation_text=f"Strike R$ {strike:.2f}",
                    row=1, col=1
                )
            
            if len(trend) >= 252:
                trend_mean_dev = trend.tail(252).abs().mean()
            else:
                trend_mean_dev = trend.abs().mean()

            if pd.isna(trend_mean_dev) or trend_mean_dev == 0:
                trend_mean_dev = 0.001
            
            fig.add_trace(
                go.Scatter(
                    x=trend.index,
                    y=trend,
                    line=dict(color='#00FFAA', width=2),
                    name=f'Tendência {symbol}'
                ),
                row=2, col=1
            )
            
            fig.add_hline(
                y=trend_mean_dev,
                line_dash="dot",
                line_color="gray",
                opacity=0.8,
                row=2, col=1,
                annotation_text=f"+{trend_mean_dev:.3f}"
            )
            fig.add_hline(
                y=-trend_mean_dev,
                line_dash="dot",
                line_color="gray",
                opacity=0.8,
                row=2, col=1,
                annotation_text=f"-{trend_mean_dev:.3f}"
            )
            
            fig.add_trace(
                go.Scatter(
                    x=ibov_trend.index,
                    y=ibov_trend,
                    line=dict(color='white', width=2, dash='solid'),
                    name='Tendência IBOV'
                ),
                row=2, col=1
            )
            
            fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5, row=2, col=1)
            
            fig.add_trace(
                go.Scatter(
                    x=signal.index,
                    y=signal,
                    line=dict(color='#00FFAA', width=2),
                    name=f'Sinal {symbol}'
                ),
                row=3, col=1
            )
            
            fig.add_trace(
                go.Scatter(
                    x=ibov_signal.index,
                    y=ibov_signal,
                    line=dict(color='white', width=1, dash='solid'),
                    name='Sinal IBOV'
                ),
                row=3, col=1
            )
            
            fig.add_hline(y=0, line_dash="solid", line_color="white", opacity=0.5, row=3, col=1)
            
            fig.update_layout(
                height=900,
                showlegend=True,
                paper_bgcolor=paper_bgcolor,
                plot_bgcolor=plot_bgcolor,
                font=dict(color='white'),
                legend=dict(
                    bgcolor=plot_bgcolor,
                    bordercolor='white',
                    borderwidth=1
                ),
                margin=dict(t=100)
            )
            
            fig.update_xaxes(
                showgrid=True,
                gridwidth=1,
                gridcolor=grid_color,
                linecolor='white',
                linewidth=1,
                showline=True,
                tickfont=dict(color='white')
            )
            
            fig.update_yaxes(
                showgrid=True,
                gridwidth=1,
                gridcolor=grid_color,
                linecolor='white',
                linewidth=1,
                showline=True,
                tickfont=dict(color='white')
            )
            
            return fig.to_html(include_plotlyjs='cdn')
            
        except Exception as e:
            print(f"Erro ao criar gráfico: {e}")
            return "<p>Erro ao gerar gráfico</p>"
    
    def analyze_single_asset(self, symbol: str, period: str = "2y", 
                           strike: Optional[float] = None) -> Dict[str, Any]:
        try:
            data = self.get_data(symbol, period)
            ibov_data = self.get_data(self.ibov_symbol, period)
            
            if data is None:
                return {
                    'success': False,
                    'error': f'Não foi possível obter dados para {symbol}'
                }
            
            if ibov_data is None:
                return {
                    'success': False,
                    'error': 'Não foi possível obter dados do IBOVESPA'
                }
            
            final_signal, trend_strength, volatility, returns = self.calculate_atsmom(data)
            
            ibov_signal, ibov_trend, ibov_vol, ibov_returns = self.calculate_atsmom(ibov_data)
            
            beta = self.calculate_beta(returns, ibov_returns)
            
            chart_html = self.create_plotly_chart(
                data, final_signal, trend_strength, symbol,
                ibov_data, ibov_signal, ibov_trend, strike
            )
            
            current_price = float(data['close'].iloc[-1])
            current_signal = float(final_signal.iloc[-1])
            current_trend = float(trend_strength.iloc[-1])
            current_vol = float(volatility.iloc[-1])
            
            if current_signal > 0.1:
                signal_status = "COMPRA"
            elif current_signal < -0.1:
                signal_status = "VENDA"
            else:
                signal_status = "NEUTRO"
            
            analysis_data = {
                'symbol': symbol,
                'current_price': round(current_price, 2),
                'current_signal': round(current_signal, 4),
                'current_trend': round(current_trend, 4),
                'current_volatility': round(current_vol * 100, 2),
                'signal_status': signal_status,
                'beta': round(beta, 2),
                'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            if strike is not None:
                distance_to_strike = (current_price - strike) / current_price * 100
                analysis_data.update({
                    'strike': strike,
                    'distance_to_strike': round(distance_to_strike, 2),
                    'strike_analysis': self._analyze_strike(current_price, strike, current_signal)
                })
            
            return {
                'success': True,
                'analysis_data': analysis_data,
                'chart_html': chart_html,
                'raw_data': {
                    'prices': [float(x) if not pd.isna(x) else 0.0 for x in data['close'].tail(60)],
                    'signals': [float(x) if not pd.isna(x) else 0.0 for x in final_signal.tail(60)],
                    'trends': [float(x) if not pd.isna(x) else 0.0 for x in trend_strength.tail(60)],
                    'dates': [d.strftime('%Y-%m-%d') for d in data.index[-60:]]  # ✅ CORRETO
                }
            }
            
        except Exception as e:
            print(f"Erro detalhado na análise: {e}")
            return {
                'success': False,
                'error': f'Erro na análise: {str(e)}'
            }
    
    def _analyze_strike(self, current_price: float, strike: float, signal: float) -> str:
        distance_pct = abs(current_price - strike) / current_price * 100
        
        if current_price > strike:
            if signal < -0.1 and distance_pct < 5:
                return "PUT: Sinal de venda próximo ao strike - Oportunidade interessante"
            elif signal > 0.1:
                return "PUT: Sinal de compra - Put pode perder valor"
            else:
                return "PUT: Sinal neutro - Aguardar definição"
        else:
            if signal < -0.1:
                return "PUT: Sinal de venda - Put pode ganhar mais valor"
            elif signal > 0.1:
                return "PUT: Sinal de compra - Put pode perder valor rapidamente"
            else:
                return "PUT: Sinal neutro - Monitorar closely"
    
    def get_available_symbols(self) -> list:
        return [
            'PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3',
            'MGLU3', 'WEGE3', 'RENT3', 'LREN3', 'JBSS3',
            'B3SA3', 'SUZB3', 'RAIL3', 'USIM5', 'CSNA3',
            'GOAU4', 'EMBR3', 'CIEL3', 'JHSF3', 'TOTS3'
        ]
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

    def calculate_atsmom(self, data, min_lookback=10, max_lookback=260, vol_window=60, vol_target=0.4, max_leverage=3):
        """Calcula ATSMOM - EXATAMENTE IGUAL AO CÓDIGO ORIGINAL"""
        # Calcula retornos diários
        returns = data['close'].pct_change()
        returns = returns.fillna(0)
        
        # Calcula volatilidade com EWMA
        volatility = returns.ewm(span=vol_window, min_periods=vol_window//2).std() * np.sqrt(252)
        
        signals = []
        weights = np.linspace(1.5, 1.0, max_lookback-min_lookback+1)
        
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
        
        final_signal = final_signal.fillna(0)
        combined_signal = combined_signal.fillna(0)
        volatility = volatility.fillna(0)
        
        return final_signal, combined_signal, volatility, returns

    def plot_signals_plotly(self, data, signal, trend, symbol, ibov_data, ibov_signal, ibov_trend):
        """Cria gráficos Plotly - CORRIGIDO para mostrar dados reais dos 5 anos"""
        fig = make_subplots(rows=3, cols=1, 
                           subplot_titles=(f'{symbol} - Preço De Fechamento (5 anos)', 
                                         'Força da Tendência (ATSMOM)',
                                         'Sinal ajustado pela volatilidade'),
                           vertical_spacing=0.08,
                           row_heights=[0.45, 0.275, 0.275])

        plot_bgcolor = '#11113a'
        paper_bgcolor = '#11113a'
        grid_color = 'rgba(255, 255, 255, 0.1)'
        
        # Gráfico de Preço (SEM normalização - preços reais)
        fig.add_trace(
            go.Scatter(x=data.index, y=data['close'],
                      line=dict(color='#00ff88', width=3),
                      name=symbol.replace('.SA', ''),
                      hovertemplate='<b>%{fullData.name}</b><br>Data: %{x}<br>Preço: R$ %{y:.2f}<extra></extra>'),
            row=1, col=1
        )
        
        # Gráfico de Força da Tendência (SEM limitadores artificiais)
        fig.add_trace(
            go.Scatter(x=trend.index, y=trend,
                      line=dict(color='#00ff88', width=2),
                      name=f'Tendência {symbol.replace(".SA", "")}',
                      hovertemplate='<b>Tendência</b><br>Data: %{x}<br>Valor: %{y:.4f}<extra></extra>'),
            row=2, col=1
        )
        
        fig.add_trace(
            go.Scatter(x=ibov_trend.index, y=ibov_trend,
                      line=dict(color='white', width=4),
                      name='Tendência IBOV',
                      hovertemplate='<b>Tendência IBOV</b><br>Data: %{x}<br>Valor: %{y:.4f}<extra></extra>'),
            row=2, col=1
        )
        
        # Linha zero para tendência
        fig.add_hline(y=0, line_dash="dash", line_color="white",
                     opacity=0.5, row=2, col=1)

        # Gráfico de Sinal Final (SEM limitadores - mostra variação real)
        fig.add_trace(
            go.Scatter(x=signal.index, y=signal,
                      line=dict(color='#00ff88', width=2),
                      name=f'Sinal {symbol.replace(".SA", "")}',
                      hovertemplate='<b>Sinal</b><br>Data: %{x}<br>Valor: %{y:.4f}<extra></extra>'),
            row=3, col=1
        )
        
        fig.add_trace(
            go.Scatter(x=ibov_signal.index, y=ibov_signal,
                      line=dict(color='white', width=1, dash='solid'),
                      name='Sinal IBOV',
                      hovertemplate='<b>Sinal IBOV</b><br>Data: %{x}<br>Valor: %{y:.4f}<extra></extra>'),
            row=3, col=1
        )
        
        # Linhas de referência para sinais (zonas de compra/venda)
        fig.add_hline(y=0, line_dash="solid", line_color="white",
                     opacity=0.5, row=3, col=1)
        fig.add_hline(y=0.1, line_dash="dot", line_color="#00ff88",
                     opacity=0.7, row=3, col=1)
        fig.add_hline(y=-0.1, line_dash="dot", line_color="#ff4444",
                     opacity=0.7, row=3, col=1)

        fig.update_layout(
            height=900,
            showlegend=True,
            paper_bgcolor=paper_bgcolor,
            plot_bgcolor=plot_bgcolor,
            font=dict(color='white', size=12),
            legend=dict(
                bgcolor=plot_bgcolor,
                bordercolor='white',
                borderwidth=1,
                x=0.01,
                y=0.99
            ),
            margin=dict(t=80, b=60, l=80, r=60),
            hovermode='x unified'
        )

        fig.update_xaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor=grid_color,
            linecolor='white',
            linewidth=1,
            showline=True,
            tickfont=dict(color='white'),
            type='date'
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

        # Adicionar anotações nas zonas de compra/venda
        try:
            if len(signal) > 100:
                fig.add_annotation(
                    x=signal.index[-100],
                    y=0.1,
                    xref='x3',
                    yref='y3',
                    text='Zona COMPRA',
                    showarrow=False,
                    font=dict(color='#00ff88', size=10),
                    bgcolor='rgba(0,255,136,0.1)',
                    bordercolor='#00ff88',
                    borderwidth=1
                )
                
                fig.add_annotation(
                    x=signal.index[-100],
                    y=-0.1,
                    xref='x3',
                    yref='y3',
                    text='Zona VENDA',
                    showarrow=False,
                    font=dict(color='#ff4444', size=10),
                    bgcolor='rgba(255,68,68,0.1)',
                    bordercolor='#ff4444',
                    borderwidth=1
                )
        except:
            pass

        # RETORNA O HTML com estilo melhorado
        html_string = fig.to_html(include_plotlyjs='cdn')
        
        # Adicionar CSS customizado para melhorar a aparência
        custom_css = """
        <style>
            body { 
                background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 20px;
            }
            .plotly-graph-div {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 15px;
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
        </style>
        """
        
        # Inserir CSS no HTML
        html_string = html_string.replace('<head>', f'<head>{custom_css}')
        
        return html_string

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
        
        # Gera gráfico HTML melhorado
        chart_html = self.plot_signals_plotly(data, final_signal, trend_strength, symbol, 
                                           ibov_data, ibov_signal, ibov_trend)
        
        # Calcula métricas básicas
        current_price = float(data['close'].iloc[-1])
        current_signal = float(final_signal.iloc[-1]) if len(final_signal) > 0 else 0.0
        current_trend = float(trend_strength.iloc[-1]) if len(trend_strength) > 0 else 0.0
        current_vol = float(vol.iloc[-1]) if len(vol) > 0 else 0.0
        beta = self.calculate_beta(returns, ibov_returns)
        
        # Determina status do sinal (SEM limitadores artificiais)
        if current_signal > 0.1:
            signal_status = "COMPRA"
        elif current_signal < -0.1:
            signal_status = "VENDA"
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
                'dates': [d.strftime('%Y-%m-%d') for d in data.index[-500:]],  # Último ano para gráficos menores
                'prices': [float(x) for x in data['close'].tail(500)],
                'signals': [float(x) for x in final_signal.tail(500)],
                'trends': [float(x) for x in trend_strength.tail(500)],
                'ibov_signals': [float(x) for x in ibov_signal.tail(500)],
                'ibov_trends': [float(x) for x in ibov_trend.tail(500)]
            }
        }

    def get_available_symbols(self):
        """Lista símbolos disponíveis"""
        return [
            'PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3',
            'MGLU3', 'WEGE3', 'RENT3', 'LREN3', 'JBSS3',
            'B3SA3', 'SUZB3', 'RAIL3', 'USIM5', 'CSNA3',
            'GOAU4', 'EMBR3', 'CIEL3', 'JHSF3', 'TOTS3'
        ]

# Serviço pronto para uso com Flask
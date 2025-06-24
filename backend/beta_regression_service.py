import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from statsmodels.regression.rolling import RollingOLS
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
import warnings
warnings.filterwarnings('ignore')

class BetaRegressionService:
    def __init__(self):
        self.cyberpunk_colors = {
            'neon_green': 'rgba(0, 255, 170, 0.8)',
            'neon_red': 'rgba(255, 50, 50, 0.8)',
            'neon_blue': 'rgba(0, 191, 255, 0.8)',
            'neon_purple': 'rgba(148, 0, 211, 0.8)',
            'neon_pink': 'rgba(255, 0, 127, 0.8)',
            'neon_orange': 'rgba(255, 165, 0, 0.8)',
            'gray': 'rgba(150, 150, 150, 0.4)'
        }
        
    def calculate_fees(self, volume):
        """Calcula taxas de corretagem baseadas no volume"""
        if volume <= 10_000_000:
            return 0.0230 / 100
        elif volume <= 50_000_000:
            return 0.0225 / 100
        elif volume <= 100_000_000:
            return 0.0210 / 100
        else:
            return 0.0110 / 100
    
    def get_yfinance_data(self, symbol, timeframe='1d', anos=1):
        """Obtém dados do Yahoo Finance"""
        try:
            # Adicionar .SA para ações brasileiras se necessário
            if not symbol.endswith('.SA') and len(symbol) <= 6:
                ticker = f"{symbol}.SA"
            else:
                ticker = symbol
            
            # Determinar período baseado nos anos - aumentar para mais dados
            if anos <= 1:
                period = "2y"  # Aumentado para ter mais dados
            elif anos <= 2:
                period = "3y"  # Aumentado para ter mais dados
            elif anos <= 5:
                period = "5y"
            else:
                period = "max"
            
            # Mapear timeframes
            interval_map = {
                '1h': '1h',
                '4h': '1h',  # Yahoo não tem 4h, usar 1h
                '1d': '1d',
                'D1': '1d',
                'H4': '1h'
            }
            
            interval = interval_map.get(timeframe, '1d')
            
            print(f"Buscando dados para {ticker}, período: {period}, intervalo: {interval}")
            
            # Baixar dados
            stock = yf.Ticker(ticker)
            df = stock.history(period=period, interval=interval)
            
            if df.empty:
                raise Exception(f"Sem dados disponíveis para {ticker}")
            
            # Converter colunas para minúsculas para compatibilidade
            df.columns = df.columns.str.lower()
            
            # Se for 4H, fazer resample dos dados de 1h
            if timeframe in ['4h', 'H4']:
                df = df.resample('4H').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum'
                }).dropna()
            
            # CORREÇÃO: Filtrar por anos usando timezone-aware comparison
            if anos < 5:  # Só filtrar se não for período máximo
                data_inicio = datetime.now()
                data_inicio = data_inicio.replace(tzinfo=df.index.tz) - timedelta(days=anos*365)
                df = df[df.index >= data_inicio]
            
            if df.empty:
                raise Exception("DataFrame vazio após filtro de data")
            
            print(f"Dados obtidos: {len(df)} registros de {df.index[0]} até {df.index[-1]}")
            return df
            
        except Exception as e:
            print(f"Erro ao obter dados Yahoo Finance: {e}")
            return None
    
    def calculate_beta_regression(self, df):
        """Calcula Beta Regressivo com RollingOLS"""
        try:
            # Preparação dos dados
            df = df.copy()  # Fazer cópia para evitar SettingWithCopyWarning
            df["Adj Close"] = df["close"]
            df["Returns"] = df["Adj Close"].pct_change()
            df["Price_Lag"] = df["Adj Close"].shift(1)
            df["Price_Lag2"] = df["Adj Close"].shift(2)
            df["const"] = 1
            
            # Remover NaNs para a regressão
            df_reg = df[["Adj Close", "const", "Price_Lag", "Price_Lag2"]].dropna()
            
            if len(df_reg) < 50:
                raise Exception("Dados insuficientes para regressão")
            
            # Regressão móvel - janela de 252 períodos (1 ano)
            window = min(252, len(df_reg))  # Usar 252 ou o máximo disponível
            
            print(f"Executando regressão móvel com janela de {window} períodos")
            
            reg = RollingOLS(
                endog=df_reg["Adj Close"],
                exog=df_reg[["const", "Price_Lag", "Price_Lag2"]],
                window=window
            ).fit()
            
            # Alinhar Beta0 com o DataFrame original
            df["Beta0"] = np.nan
            df.loc[df_reg.index, "Beta0"] = reg.params["const"]
            
            # Forward fill para preencher valores iniciais
            df["Beta0"] = df["Beta0"].fillna(method='bfill')
            
            # Normalização da Beta0
            df["Beta0_Norm"] = (
                df["Beta0"].rolling(20, min_periods=5).mean()
                          .rolling(20, min_periods=5)
                          .apply(lambda x: np.mean(x < x.iloc[-1]) if len(x) > 0 else 0.5)
            )
            
            # Preencher valores iniciais
            df["Beta0_Norm"] = df["Beta0_Norm"].fillna(0.5)
            
            # Coluna Beta0 anterior (para cruzamentos)
            df["Beta0_g"] = df["Beta0_Norm"].shift(1)
            df["MM"] = df["Adj Close"].rolling(20, min_periods=5).mean()
            df["MM_Pos"] = np.where(df["Adj Close"] > df["MM"], 1, 0)
            
            return df
            
        except Exception as e:
            print(f"Erro no cálculo da Beta Regressão: {e}")
            return None
    
    def calculate_proximity_status(self, df):
        """Calcula Status de Proximidade"""
        try:
            df = df.copy()
            df["Proximity_Status"] = np.where(
                (df["Beta0_Norm"] > 0.8) & (df["Beta0_g"] <= 0.8) & (df["MM_Pos"] == 1),
                "NOVA COMPRA",
                np.where(
                    (df["Beta0_Norm"] > 0.6) & (df["Beta0_g"] <= 0.6) & (df["MM_Pos"] == 1),
                    "PREPARANDO COMPRA",
                    np.where(
                        (df["Beta0_Norm"] < 0.2) & (df["Beta0_g"] >= 0.2) & (df["MM_Pos"] == 0),
                        "IMINENTE VENDA",
                        np.where(
                            (df["Beta0_Norm"] < 0.4) & (df["Beta0_g"] >= 0.4) & (df["MM_Pos"] == 0),
                            "PREPARANDO VENDA",
                            "NEUTRO"
                        )
                    )
                )
            )
            
            return df
            
        except Exception as e:
            print(f"Erro no cálculo do Status de Proximidade: {e}")
            return None
    
    def calculate_trading_signals(self, df):
        """Calcula sinais de trading e backtest"""
        try:
            df = df.copy()
            # Sinais de compra/venda
            long_signal = (df["Beta0_Norm"] > 0.5) & (df["MM_Pos"] == 1)
            short_signal = (df["Beta0_Norm"] < 0.5) & (df["MM_Pos"] == 0)
            df["trading"] = np.where(long_signal, 1,
                             np.where(short_signal, -1, 0))
            
            # Cálculo de retornos
            df["Trading"] = np.where(df["trading"] == 1, df["Returns"],
                             np.where(df["trading"] == -1, -df["Returns"], 0))
            
            # Stop loss em -5%
            df["Trading"] = np.where(df["Trading"] < -0.05, -0.05, df["Trading"])
            df["Acc_Returns"] = df["Trading"].cumsum()
            
            # Cálculo de taxas (assumindo volume padrão)
            df["Volume"] = df["close"] * 100  # Volume simulado
            df["Fees"] = df["Volume"].apply(self.calculate_fees)
            df["Trading_Fees"] = np.where(df["trading"] != 0, df["Volume"] * df["Fees"], 0)
            df["Trading_After_Fees"] = df["Trading"] - (df["Trading_Fees"] / df["Volume"])
            df["Acc_Returns_After_Fees"] = df["Trading_After_Fees"].cumsum()
            
            return df
            
        except Exception as e:
            print(f"Erro no cálculo dos sinais de trading: {e}")
            return None
    
    def get_trades_history(self, df):
        """Extrai histórico de trades"""
        try:
            df_copy = df.copy()
            df_copy["signal"] = df_copy["trading"].shift(1).fillna(0)
            
            trades = []
            current_signal = 0
            entry_index = None
            entry_price = None
            entry_date = None
            
            for i in range(len(df_copy)):
                row = df_copy.iloc[i]
                signal = row["signal"]
                price_close = row["close"]
                date = row.name
                
                if signal != current_signal:
                    if current_signal != 0 and entry_index is not None:
                        exit_date = date
                        exit_price = price_close
                        trade_return = (exit_price / entry_price) - 1
                        outcome = "STOP" if trade_return < 0 else "GAIN"
                        trade_type = "LONG" if current_signal == 1 else "SHORT"
                        trades.append({
                            "Entry Date": entry_date.strftime('%d/%m/%Y'),
                            "Entry Price": round(entry_price, 2),
                            "Exit Date": exit_date.strftime('%d/%m/%Y'),
                            "Exit Price": round(exit_price, 2),
                            "PnL (%)": round(trade_return * 100, 2),
                            "Outcome": outcome,
                            "Type": trade_type
                        })
                    
                    if signal != 0:
                        entry_index = i
                        entry_price = price_close
                        entry_date = date
                    current_signal = signal
            
            # Trade em aberto
            if current_signal != 0 and entry_price is not None:
                exit_date = df_copy.index[-1]
                exit_price = df_copy["close"].iloc[-1]
                trade_return = (exit_price / entry_price) - 1
                outcome = "STOP" if trade_return < 0 else "GAIN"
                trade_type = "LONG" if current_signal == 1 else "SHORT"
                trades.append({
                    "Entry Date": entry_date.strftime('%d/%m/%Y'),
                    "Entry Price": round(entry_price, 2),
                    "Exit Date": exit_date.strftime('%d/%m/%Y'),
                    "Exit Price": round(exit_price, 2),
                    "PnL (%)": round(trade_return * 100, 2),
                    "Outcome": outcome,
                    "Type": trade_type
                })
            
            return trades
            
        except Exception as e:
            print(f"Erro ao extrair histórico de trades: {e}")
            return []
    
    def create_cyberpunk_chart(self, df, symbol, timeframe):
        """Cria gráfico cyberpunk com 4 subplots"""
        try:
            # Template cyberpunk
            cyberpunk_template = dict(
                layout=dict(
                    plot_bgcolor='rgb(27, 27, 50)',
                    paper_bgcolor='rgb(27, 27, 50)',
                    font=dict(color='rgb(170, 170, 220)'),
                    title=dict(font=dict(color='rgb(200, 200, 250)')),
                    xaxis=dict(
                        gridcolor='rgba(70, 70, 120, 0.2)',
                        zerolinecolor='rgba(70, 70, 120, 0.2)',
                        showgrid=True,
                        gridwidth=1
                    ),
                    yaxis=dict(
                        gridcolor='rgba(70, 70, 120, 0.2)',
                        zerolinecolor='rgba(70, 70, 120, 0.2)',
                        showgrid=True,
                        gridwidth=1
                    )
                )
            )
            pio.templates['cyberpunk'] = cyberpunk_template
            pio.templates.default = 'cyberpunk'
            
            # Criar subplots
            fig = make_subplots(
                rows=4, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.05,
                subplot_titles=('Preço e Média Móvel',
                               'Beta0 Normalizado',
                               'Retornos por Operação',
                               'Retornos Acumulados'),
                row_heights=[0.4, 0.2, 0.2, 0.2]
            )
            
            # Subplot 1: Preço colorido por sinais
            for i in range(1, len(df)):
                if df['trading'].iloc[i] == 1:
                    color = self.cyberpunk_colors['neon_green']
                elif df['trading'].iloc[i] == -1:
                    color = self.cyberpunk_colors['neon_red']
                else:
                    color = self.cyberpunk_colors['gray']
                
                fig.add_trace(
                    go.Scatter(
                        x=df.index[i-1:i+1],
                        y=df['close'].iloc[i-1:i+1],
                        mode='lines',
                        line=dict(color=color, width=2),
                        showlegend=False
                    ),
                    row=1, col=1
                )
            
            # Média móvel
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["MM"],
                    name="Média Móvel",
                    line=dict(color=self.cyberpunk_colors['neon_orange'], width=2)
                ),
                row=1, col=1
            )
            
            # Subplot 2: Beta0 Normalizado
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["Beta0_Norm"],
                    name="Beta0 Normalizado",
                    line=dict(color=self.cyberpunk_colors['neon_blue'], width=2),
                    fill='tonexty',
                    fillcolor='rgba(0, 191, 255, 0.1)'
                ),
                row=2, col=1
            )
            
            # Linhas de referência
            colors = [self.cyberpunk_colors['neon_green'], self.cyberpunk_colors['gray'], self.cyberpunk_colors['neon_red']]
            for ref, c in zip([0.8, 0.5, 0.2], colors):
                fig.add_hline(y=ref, line=dict(color=c, width=1, dash='dash'), row=2, col=1)
            
            # Subplot 3: Retornos por operação
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=np.round(df["Trading_After_Fees"]*100, 2),
                    mode="markers",
                    name="Retornos por Op.",
                    marker=dict(
                        size=6,
                        color=df["Trading_After_Fees"]*100,
                        colorscale=[
                            [0, self.cyberpunk_colors['neon_red']],
                            [0.5, self.cyberpunk_colors['gray']],
                            [1, self.cyberpunk_colors['neon_green']]
                        ],
                        showscale=False,
                        line=dict(width=1, color='rgba(255,255,255,0.5)')
                    )
                ),
                row=3, col=1
            )
            
            # Subplot 4: Retornos acumulados
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=np.round(df["Acc_Returns"]*100, 2),
                    name="Retorno Bruto",
                    line=dict(color=self.cyberpunk_colors['neon_purple'], width=2),
                    fill='tonexty',
                    fillcolor='rgba(148, 0, 211, 0.1)'
                ),
                row=4, col=1
            )
            
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=np.round(df["Acc_Returns_After_Fees"]*100, 2),
                    name="Retorno Líquido",
                    line=dict(color=self.cyberpunk_colors['neon_pink'], width=2, dash='dash')
                ),
                row=4, col=1
            )
            
            # Layout
            fig.update_layout(
                height=1200,
                width=1200,
                title_text=f"Beta0 Intercept - {symbol} - {timeframe}",
                title_font=dict(size=24, color='rgb(200,200,250)'),
                showlegend=True,
                legend=dict(
                    bgcolor='rgba(27, 27, 50, 0.8)',
                    bordercolor='rgba(70, 70, 120, 0.8)',
                    borderwidth=1,
                    font=dict(color='rgb(170,170,220)')
                ),
                xaxis4_title="Data",
                yaxis_title="Preço",
                yaxis2_title="Beta0 Norm.",
                yaxis3_title="Retorno por Op. (%)",
                yaxis4_title="Retorno Acumulado (%)"
            )
            
            # Atualizar eixos
            for i in range(1, 5):
                fig.update_xaxes(
                    row=i,
                    gridcolor='rgba(70, 70, 120, 0.2)',
                    zerolinecolor='rgba(70, 70, 120, 0.2)',
                    tickfont=dict(color='rgb(170,170,220)')
                )
                fig.update_yaxes(
                    row=i,
                    gridcolor='rgba(70, 70, 120, 0.2)',
                    zerolinecolor='rgba(70, 70, 120, 0.2)',
                    tickfont=dict(color='rgb(170,170,220)'),
                    title_standoff=20
                )
            
            # Anotação com timestamp
            fig.add_annotation(
                text=f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
                xref="paper", yref="paper",
                x=0.98, y=0.02,
                showarrow=False,
                font=dict(size=10, color='rgba(170,170,220,0.7)'),
                opacity=0.7
            )
            
            return fig.to_html(include_plotlyjs=True, div_id="beta-chart")
            
        except Exception as e:
            print(f"Erro ao criar gráfico: {e}")
            return None
    
    def run_analysis(self, symbol, timeframe='1d', anos=1):
        """Executa análise completa"""
        try:
            print(f"=== INICIANDO ANÁLISE BETA REGRESSÃO ===")
            print(f"Símbolo: {symbol}, Timeframe: {timeframe}, Anos: {anos}")
            
            # 1. Obter dados
            df = self.get_yfinance_data(symbol, timeframe, anos)
            if df is None:
                return {'success': False, 'error': 'Erro ao obter dados do Yahoo Finance'}
            
            # 2. Calcular Beta Regressão
            df = self.calculate_beta_regression(df)
            if df is None:
                return {'success': False, 'error': 'Erro no cálculo da Beta Regressão'}
            
            # 3. Calcular Status de Proximidade
            df = self.calculate_proximity_status(df)
            if df is None:
                return {'success': False, 'error': 'Erro no cálculo do Status de Proximidade'}
            
            # 4. Calcular sinais de trading
            df = self.calculate_trading_signals(df)
            if df is None:
                return {'success': False, 'error': 'Erro no cálculo dos sinais de trading'}
            
            # 5. Extrair histórico de trades
            trades_history = self.get_trades_history(df)
            
            # 6. Criar gráfico
            chart_html = self.create_cyberpunk_chart(df, symbol, timeframe)
            
            # 7. Determinar status atual
            last_signal = df["trading"].iloc[-1]
            if last_signal == 1:
                status_str = "COMPRA"
            elif last_signal == -1:
                status_str = "VENDA"
            else:
                status_str = "NEUTRO"
            
            # 8. Preparar dados de análise
            analysis_data = {
                "symbol": symbol,
                "timeframe": timeframe,
                "status": status_str,
                "last_close": round(df["close"].iloc[-1], 2),
                "beta0_norm": round(df["Beta0_Norm"].iloc[-1], 4),
                "proximity_status": df["Proximity_Status"].iloc[-1],
                "acc_returns_final": round(df["Acc_Returns"].iloc[-1] * 100, 2),
                "acc_returns_after_fees_final": round(df["Acc_Returns_After_Fees"].iloc[-1] * 100, 2),
                "total_trades": len(trades_history),
                "timestamp": datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            }
            
            print(f"=== ANÁLISE CONCLUÍDA ===")
            print(f"Status: {status_str}, Preço: R$ {analysis_data['last_close']}")
            print(f"Beta0 Norm: {analysis_data['beta0_norm']}, Status Proximidade: {analysis_data['proximity_status']}")
            print(f"Total de trades: {analysis_data['total_trades']}")
            
            return {
                'success': True,
                'chart_html': chart_html,
                'analysis_data': analysis_data,
                'trades_history': trades_history,
                'dataframe': df
            }
            
        except Exception as e:
            print(f"Erro na análise: {e}")
            return {'success': False, 'error': f'Erro na análise: {str(e)}'}
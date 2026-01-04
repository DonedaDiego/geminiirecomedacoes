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
        """Calcula taxas de corretagem baseadas no volume (B3)"""
        if volume <= 10_000_000:
            return 0.0230 / 100
        elif volume <= 50_000_000:
            return 0.0225 / 100
        elif volume <= 100_000_000:
            return 0.0210 / 100
        else:
            return 0.0110 / 100
    
    def get_yfinance_data(self, symbol, anos=1):
        """Obtém dados do Yahoo Finance - APENAS DIÁRIO"""
        try:
            # Adicionar .SA para ações brasileiras se necessário
            if not symbol.endswith('.SA') and len(symbol) <= 6:
                ticker = f"{symbol}.SA"
            else:
                ticker = symbol
            
            # Determinar período baseado nos anos
            if anos <= 1:
                period = "2y"  # Aumentado para ter mais dados
            elif anos <= 2:
                period = "3y"
            elif anos <= 5:
                period = "5y"
            else:
                period = "max"
            
            print(f"Buscando dados para {ticker}, período: {period}, intervalo: 1d")
            
            # Baixar dados APENAS DIÁRIOS
            stock = yf.Ticker(ticker)
            df = stock.history(period=period, interval='1d')
            
            if df.empty:
                raise Exception(f"Sem dados disponíveis para {ticker}")
            
            # Converter colunas para minúsculas para compatibilidade
            df.columns = df.columns.str.lower()
            
            # Filtrar por anos usando timezone-aware comparison
            if anos < 5:
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
        """Calcula Beta Regressivo com RollingOLS - IGUAL AO METATRADER"""
        try:
            df = df.copy()
            
            # Prepara colunas EXATAMENTE como no MetaTrader
            df["Adj Close"] = df["close"]
            df["Returns"] = df["Adj Close"].pct_change()
            df["Price_Lag"] = df["Adj Close"].shift(1)
            df["Price_Lag2"] = df["Adj Close"].shift(2)
            df["const"] = 1  # Coluna de constante para intercepto
            
            # Remove NaNs para regressão
            df_clean = df[["Adj Close", "const", "Price_Lag", "Price_Lag2"]].dropna()
            
            if len(df_clean) < 50:
                raise Exception("Dados insuficientes para regressão")
            
            window = 30
            period = 20  # Para média móvel
            
            print(f"Executando regressão móvel com janela de {window} períodos")
            
            # Regressão RollingOLS FOCADA NO INTERCEPTO
            reg = RollingOLS(
                endog=df_clean["Adj Close"],
                exog=df_clean[["const", "Price_Lag", "Price_Lag2"]],
                window=window
            ).fit()
            
            # Extrai Beta0 = INTERCEPTO (como no MetaTrader)
            df["Beta0"] = np.nan
            df.loc[df_clean.index, "Beta0"] = reg.params["const"]
            
            # Normalização EXATA como no MetaTrader
            df["Beta0_Norm"] = (df["Beta0"]
                .rolling(20).mean()
                .rolling(20).apply(lambda x: np.mean(x < x.iloc[-1]) if len(x) > 0 else 0.5))
            
            # Beta0_g = valor defasado (como no MetaTrader)
            df["Beta0_g"] = df["Beta0_Norm"].shift(1)
            
            # Média móvel simples (como no MetaTrader)
            df["MM"] = df["Adj Close"].rolling(period).mean()
            df["MM_Pos"] = np.where(df["Adj Close"] > df["MM"], 1, 0)
            
            # ===== PREENCHER VALORES INICIAIS (MÉTODO MODERNO) =====
            df["Beta0"] = df["Beta0"].bfill().ffill()
            df["Beta0_Norm"] = df["Beta0_Norm"].fillna(0.5)
            df["Beta0_g"] = df["Beta0_g"].fillna(0.5)
            
            # IMPORTANTE: Preencher MM também
            df["MM"] = df["MM"].bfill().ffill()
            
            # Garantir que MM_Pos não tenha NaN
            df["MM_Pos"] = df["MM_Pos"].fillna(0)
            
            return df
            
        except Exception as e:
            print(f"Erro no cálculo da Beta Regressão: {e}")
            return None
    
    def calculate_trading_signals(self, df):
        """Calcula sinais de trading EXATAMENTE como no MetaTrader"""
        try:
            df = df.copy()
            
            # Sinais EXATOS do MetaTrader
            long_signal = (df["Beta0_Norm"] > 0.5) & (df["MM_Pos"] == 1)
            short_signal = (df["Beta0_Norm"] < 0.5) & (df["MM_Pos"] == 0)
            
            df["trading"] = np.where(long_signal, 1, 
                             np.where(short_signal, -1, 0))
            
            # Retornos por operação IGUAL ao MetaTrader
            df["Trading"] = np.where(df["trading"] == 1, df["Returns"],
                             np.where(df["trading"] == -1, -df["Returns"], 0))
            
            # Stop loss fixo em -5% (como no MetaTrader)
            df["Trading"] = np.where(df["Trading"] < -0.05, -0.05, df["Trading"])
            
            # Retornos acumulados (antes das taxas)
            df["Acc_Returns"] = df["Trading"].cumsum()
            
            # Volume financeiro e taxas (como no MetaTrader)
            df["Volume"] = df["close"] * 100  # Lote de 100 ações
            df["Fees"] = df["Volume"].apply(self.calculate_fees)
            df["Trading_Fees"] = np.where(df["trading"] != 0, df["Volume"] * df["Fees"], 0)
            
            # Ajusta retornos com taxas
            df["Trading_After_Fees"] = df["Trading"] - (df["Trading_Fees"] / df["Volume"])
            df["Acc_Returns_After_Fees"] = df["Trading_After_Fees"].cumsum()
            
            return df
            
        except Exception as e:
            print(f"Erro no cálculo dos sinais de trading: {e}")
            return None
    
    def calculate_statistics(self, df):
        """Calcula estatísticas COMPLETAS como no MetaTrader"""
        try:
            # Estatísticas básicas
            total_trades = len(df[df["trading"] != 0])
            winning_trades = len(df[df["Trading_After_Fees"] > 0])
            losing_trades = len(df[df["Trading_After_Fees"] < 0])
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            final_return = df["Acc_Returns_After_Fees"].iloc[-1] * 100
            
            # Drawdown
            rolling_max_af = df["Acc_Returns_After_Fees"].cummax()
            drawdown_af = (rolling_max_af - df["Acc_Returns_After_Fees"])
            max_drawdown = drawdown_af.max() * 100
            
            # Métricas adicionais - CORRIGIDO
            avg_return = df["Trading_After_Fees"].mean()  # Mantém em decimal
            volatility = df["Trading_After_Fees"].std()    # Mantém em decimal
            
            # Sharpe Ratio anualizado (assumindo ~252 dias de trading)
            sharpe_ratio = (avg_return / volatility * np.sqrt(252)) if volatility != 0 else 0
            
            # Converte para % apenas para exibição
            avg_return_pct = avg_return * 100
            volatility_pct = volatility * 100 * np.sqrt(252)  # anualizada
            
            total_fees = df["Trading_Fees"].sum()
            
            # Impacto das taxas
            tax_impact = (df['Acc_Returns'].iloc[-1]*100 - final_return)
            
            return {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': win_rate,
                'final_return': final_return,
                'max_drawdown': max_drawdown,
                'avg_return': avg_return_pct,
                'volatility': volatility_pct,
                'sharpe_ratio': sharpe_ratio,
                'total_fees': total_fees,
                'tax_impact': tax_impact,
                'return_bruto': df['Acc_Returns'].iloc[-1] * 100
            }
            
        except Exception as e:
            print(f"Erro no cálculo das estatísticas: {e}")
            return {}
    
    def get_trades_history(self, df):
        """Extrai histórico de trades COMPLETO"""
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
                        
                        # Calcula retorno considerando tipo de posição
                        if current_signal == 1:  # Long
                            trade_return = (exit_price / entry_price) - 1
                        else:  # Short
                            trade_return = (entry_price / exit_price) - 1
                        
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
                
                if current_signal == 1:  # Long
                    trade_return = (exit_price / entry_price) - 1
                else:  # Short
                    trade_return = (entry_price / exit_price) - 1
                
                outcome = "STOP" if trade_return < 0 else "GAIN"
                trade_type = "LONG" if current_signal == 1 else "SHORT"
                
                trades.append({
                    "Entry Date": entry_date.strftime('%d/%m/%Y'),
                    "Entry Price": round(entry_price, 2),
                    "Exit Date": f"{exit_date.strftime('%d/%m/%Y')} (Em aberto)",
                    "Exit Price": round(exit_price, 2),
                    "PnL (%)": round(trade_return * 100, 2),
                    "Outcome": outcome,
                    "Type": trade_type
                })
            
            return trades
            
        except Exception as e:
            print(f"Erro ao extrair histórico de trades: {e}")
            return []
    
    def create_cyberpunk_chart(self, df, symbol):
        """Cria gráfico cyberpunk IDÊNTICO ao MetaTrader"""
        try:
            # Template cyberpunk EXATO
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
            
            # Criar subplots IDÊNTICO ao MetaTrader
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
            
            # 1) GRÁFICO PREÇO COLORIDO POR SINAIS (como MetaTrader)
            for i in range(1, len(df)):
                if df['trading'].iloc[i] == 1:
                    color = self.cyberpunk_colors['neon_green']   # Verde neon
                elif df['trading'].iloc[i] == -1:
                    color = self.cyberpunk_colors['neon_red']     # Vermelho neon
                else:
                    color = self.cyberpunk_colors['gray']         # Cinza
                
                fig.add_trace(
                    go.Scatter(
                        x=df.index[i-1:i+1],
                        y=df['close'].iloc[i-1:i+1],
                        mode='lines',
                        line=dict(color=color, width=2, shape='spline'),
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
                    line=dict(color=self.cyberpunk_colors['neon_orange'], width=2, shape='spline')
                ),
                row=1, col=1
            )
            
            # 2) BETA0 NORMALIZADO (como MetaTrader)
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["Beta0_Norm"],
                    name="Beta0 Normalizado",
                    line=dict(color=self.cyberpunk_colors['neon_blue'], width=2, shape='spline'),
                    fill='tonexty',
                    fillcolor='rgba(0, 191, 255, 0.1)'
                ),
                row=2, col=1
            )
            
            # Linhas de referência (EXATAS do MetaTrader)
            colors = [self.cyberpunk_colors['neon_green'], self.cyberpunk_colors['gray'], self.cyberpunk_colors['neon_red']]
            for ref, c in zip([0.5, 0.0, -0.5], colors):
                fig.add_hline(y=ref, line=dict(color=c, width=1, dash='dash'), row=2, col=1)
            
            # 3) RETORNOS POR OPERAÇÃO (como MetaTrader)
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
            
            # 4) RETORNOS ACUMULADOS (como MetaTrader)
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=np.round(df["Acc_Returns"]*100, 2),
                    name="Retorno Bruto",
                    line=dict(color=self.cyberpunk_colors['neon_purple'], width=2, shape='spline'),
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
                    line=dict(color=self.cyberpunk_colors['neon_pink'], width=2, shape='spline', dash='dash')
                ),
                row=4, col=1
            )
            
            # Layout IDÊNTICO ao MetaTrader
            fig.update_layout(
                height=1200,
                width=1200,
                title_text=f"Análise de Trading (Beta0 Intercept) - {symbol} - Diário",
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
    
    def run_analysis(self, symbol, anos=1):
        """Executa análise completa IDÊNTICA ao MetaTrader"""
        try:
            print(f"=== INICIANDO ANÁLISE BETA REGRESSÃO ===")
            print(f"Símbolo: {symbol}, Timeframe: Diário, Anos: {anos}")
            
            # 1. Obter dados
            df = self.get_yfinance_data(symbol, anos)
            if df is None:
                return {'success': False, 'error': 'Erro ao obter dados do Yahoo Finance'}
            
            # 2. Calcular Beta Regressão
            df = self.calculate_beta_regression(df)
            if df is None:
                return {'success': False, 'error': 'Erro no cálculo da Beta Regressão'}
            
            # 3. Calcular sinais de trading
            df = self.calculate_trading_signals(df)
            if df is None:
                return {'success': False, 'error': 'Erro no cálculo dos sinais de trading'}
            
            # 4. Calcular estatísticas
            stats = self.calculate_statistics(df)
            
            # 5. Extrair histórico de trades
            trades_history = self.get_trades_history(df)
            
            # 6. Criar gráfico
            chart_html = self.create_cyberpunk_chart(df, symbol)
            
            # 7. Determinar status atual
            last_signal = df["trading"].iloc[-1]
            if last_signal == 1:
                status_str = "COMPRA"
            elif last_signal == -1:
                status_str = "VENDA"
            else:
                status_str = "NEUTRO"
            
            # 8. Preparar dados de análise COMPLETOS
            analysis_data = {
                "symbol": symbol,
                "timeframe": "Diário",
                "status": status_str,
                "last_close": round(df["close"].iloc[-1], 2),
                "beta0": round(df["Beta0"].iloc[-1], 4),
                "beta0_norm": round(df["Beta0_Norm"].iloc[-1], 4),
                "mm": round(df["MM"].iloc[-1], 2),
                "mm_pos": df["MM_Pos"].iloc[-1],
                
                # Estatísticas COMPLETAS
                "total_trades": stats.get('total_trades', 0),
                "winning_trades": stats.get('winning_trades', 0),
                "losing_trades": stats.get('losing_trades', 0),
                "win_rate": round(stats.get('win_rate', 0), 2),
                "final_return": round(stats.get('final_return', 0), 2),
                "return_bruto": round(stats.get('return_bruto', 0), 2),
                "max_drawdown": round(stats.get('max_drawdown', 0), 2),
                "avg_return": round(stats.get('avg_return', 0), 4),
                "volatility": round(stats.get('volatility', 0), 2),
                "sharpe_ratio": round(stats.get('sharpe_ratio', 0), 2),
                "total_fees": round(stats.get('total_fees', 0), 2),
                "tax_impact": round(stats.get('tax_impact', 0), 2),
                
                "periodo": f"{df.index[0].strftime('%d/%m/%Y')} até {df.index[-1].strftime('%d/%m/%Y')}",
                "timestamp": datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            }
            
            print(f"=== ANÁLISE CONCLUÍDA ===")
            print(f"Status: {status_str}, Preço: R$ {analysis_data['last_close']}")
            print(f"Beta0 Norm: {analysis_data['beta0_norm']}")
            print(f"Total de trades: {analysis_data['total_trades']}")
            print(f"Win Rate: {analysis_data['win_rate']}%")
            print(f"Retorno final: {analysis_data['final_return']}%")
            
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

import pandas as pd
import numpy as np
import yfinance as yf
import warnings
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from datetime import datetime
import logging
from typing import Optional, Tuple, Dict, Any

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suprimir warnings
warnings.filterwarnings("ignore")

class VolatilidadeService:
    """
    Serviço para análise de volatilidade de ações
    """
    
    def __init__(self):
        self.vol_p1 = 20  # Período para cálculo da volatilidade
        self.default_period = "2y"
        self.colors = {
            'plot_bgcolor': '#11113a',
            'paper_bgcolor': '#11113a', 
            'grid_color': 'rgba(255, 255, 255, 0.1)',
            'main_line': '#00FFAA',
            'text_color': 'white'
        }
    
    def get_data(self, symbol: str, start: str = None, end: str = None, period: str = None) -> Optional[pd.DataFrame]:
        """
        Obter dados do yfinance com tratamento robusto
        """
        try:
            if not symbol.endswith('.SA') and not symbol.startswith('^'):
                symbol = f"{symbol}.SA"
            
            ticker = yf.Ticker(symbol)
            
            if period:
                data = ticker.history(period=period)
            else:
                data = ticker.history(start=start, end=end)
            
            if data.empty:
                logger.warning(f"Nenhum dado encontrado para {symbol}")
                return None
            
            # Padronizar nomes das colunas
            data.columns = [col.lower() for col in data.columns]
            
            # Remover timezone se existir
            if hasattr(data.index, 'tz') and data.index.tz is not None:
                data.index = data.index.tz_localize(None)
            
            logger.info(f"Dados obtidos com sucesso para {symbol}: {len(data)} registros")
            return data
            
        except Exception as e:
            logger.error(f"Erro ao obter dados para {symbol}: {str(e)}")
            return None
    
    def processar_dados(self, data: pd.DataFrame) -> Optional[pd.DataFrame]:
        """
        Processar dados para cálculo de volatilidade
        """
        try:
            df = data.copy()
            
            # Calcular retornos e volatilidade
            df["returns"] = df["close"].pct_change(1)
            df["adj_low"] = df["low"] - (df["close"] - df["close"])
            df["adj_high"] = df["high"] - (df["close"] - df["close"])
            df["adj_open"] = df["open"] - (df["close"] - df["close"])
            df["target"] = df["returns"].shift(-1)
            
            # Volatilidade anualizada
            df["vol"] = np.round(df["returns"].rolling(self.vol_p1).std() * np.sqrt(252), 4)
            
            # Identificação do dia da semana
            df["date"] = df.index
            df["weekday"] = df["date"].dt.dayofweek  # Segunda-feira é dia 0
            df = df.dropna(axis=0)
            
            # Volatilidade semanal
            weekly_vol = df["vol"] / np.sqrt(52)
            ref_price = df["close"]
            df["weekly_vol"] = df["vol"] / np.sqrt(52)
            df["ref_price"] = df["close"]
            
            # Loop para ajustar volatilidade semanal
            for i in range(1, len(df)):
                if df["weekday"].iloc[i] == 0:
                    df["weekly_vol"].iloc[i] = weekly_vol.iloc[i-1]
                    df["ref_price"].iloc[i] = ref_price.iloc[i-1]
                else:
                    df["weekly_vol"].iloc[i] = df["weekly_vol"].iloc[i-1]
                    df["ref_price"].iloc[i] = df["ref_price"].iloc[i-1]
            
            # Bandas de suporte e resistência semanais
            df["supply_band_1d"] = np.round(df["weekly_vol"] * df["ref_price"] + df["ref_price"], 2)
            df["demand_band_1d"] = np.round(df["ref_price"] - df["weekly_vol"] * df["ref_price"], 2)
            df["supply_band_2d"] = np.round(2 * df["weekly_vol"] * df["ref_price"] + df["ref_price"], 2)
            df["demand_band_2d"] = np.round(df["ref_price"] - 2 * df["weekly_vol"] * df["ref_price"], 2)
            
            # Limpar valores infinitos e NaN
            df = df.replace([np.inf, -np.inf], np.nan)
            df = df.fillna(method='ffill').fillna(0)
            
            logger.info("Dados processados com sucesso")
            return df
            
        except Exception as e:
            logger.error(f"Erro ao processar dados: {str(e)}")
            return None
    
    def calcular_niveis_anuais(self, data: pd.DataFrame, year: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Calcular níveis de suporte e resistência anuais
        """
        try:
            # Verificar se o ano existe nos dados
            available_years = data.index.year.unique()
            if int(year) not in available_years:
                return None, f"Dados para o ano {year} não encontrados. Anos disponíveis: {sorted(available_years)}"
            
            year_data = data[data.index.year == int(year)]
            
            if len(year_data) == 0:
                return None, f"Nenhum dado encontrado para o ano {year}."
            
            preco_atual = float(year_data["close"].iloc[-1])
            vol_atual = float(year_data["vol"].iloc[-1])
            
            # Verificar se volatilidade é válida
            if pd.isna(vol_atual) or vol_atual <= 0:
                vol_atual = 0.2  # Valor padrão conservador
                logger.warning(f"Volatilidade inválida detectada, usando valor padrão: {vol_atual}")
            
            # Calcular níveis
            niveis = {
                'preco_atual': round(preco_atual, 2),
                'volatilidade_anual': round(vol_atual, 4),
                'upper_05d': round(0.5 * vol_atual * preco_atual + preco_atual, 2),
                'lower_05d': round(preco_atual - 0.5 * vol_atual * preco_atual, 2),
                'upper_1d': round(vol_atual * preco_atual + preco_atual, 2),
                'lower_1d': round(preco_atual - vol_atual * preco_atual, 2),
                'upper_2d': round(2 * vol_atual * preco_atual + preco_atual, 2),
                'lower_2d': round(preco_atual - 2 * vol_atual * preco_atual, 2),
                'upper_3d': round(3 * vol_atual * preco_atual + preco_atual, 2),
                'lower_3d': round(preco_atual - 3 * vol_atual * preco_atual, 2)
            }
            
            # Calcular variações percentuais
            variacoes = {
                'upper_3d_pct': round(((niveis['upper_3d'] / preco_atual - 1) * 100), 1),
                'upper_2d_pct': round(((niveis['upper_2d'] / preco_atual - 1) * 100), 1),
                'upper_1d_pct': round(((niveis['upper_1d'] / preco_atual - 1) * 100), 1),
                'upper_05d_pct': round(((niveis['upper_05d'] / preco_atual - 1) * 100), 1),
                'lower_05d_pct': round(((niveis['lower_05d'] / preco_atual - 1) * 100), 1),
                'lower_1d_pct': round(((niveis['lower_1d'] / preco_atual - 1) * 100), 1),
                'lower_2d_pct': round(((niveis['lower_2d'] / preco_atual - 1) * 100), 1),
                'lower_3d_pct': round(((niveis['lower_3d'] / preco_atual - 1) * 100), 1)
            }
            
            niveis.update(variacoes)
            
            logger.info(f"Níveis calculados com sucesso para {year}")
            return niveis, None
            
        except Exception as e:
            logger.error(f"Erro ao calcular níveis anuais: {str(e)}")
            return None, f"Erro ao calcular níveis anuais: {str(e)}"
    
    def create_annual_chart(self, data: pd.DataFrame, ticker: str, year: str, niveis: Dict) -> Optional[str]:
        """
        Gerar gráfico de volatilidade anual usando o padrão do ATSMOMService
        """
        try:
            next_year = str(int(year) + 1)
            
            # Verificar se o próximo ano existe
            if int(next_year) not in data.index.year:
                logger.warning(f"Dados para o ano {next_year} não encontrados para o gráfico.")
                return None
            
            next_year_data = data[data.index.year == int(next_year)]
            
            if len(next_year_data) == 0:
                return None
            
            fig = make_subplots(
                rows=1, cols=1,
                subplot_titles=(f'Análise de Volatilidade Anual {next_year} - {ticker.replace(".SA", "")}',),
                vertical_spacing=0.08
            )
            
            # Candlestick com cores do padrão
            fig.add_trace(go.Candlestick(
                x=next_year_data.index,
                open=next_year_data["adj_open"],
                high=next_year_data["adj_high"],
                low=next_year_data["adj_low"],
                close=next_year_data["close"],
                name="Preço",
                increasing_line_color="#00C851",
                decreasing_line_color="#FF4444",
                increasing_fillcolor="#00C851",
                decreasing_fillcolor="#FF4444"
            ))
            
            # Linhas de suporte e resistência
            fig.add_hline(y=niveis['upper_05d'], line_width=1, line_dash="dot", line_color="#9E9E9E",
                         annotation_text="0.5σ Superior", annotation_position="right")
            fig.add_hline(y=niveis['lower_05d'], line_width=1, line_dash="dot", line_color="#9E9E9E",
                         annotation_text="0.5σ Inferior", annotation_position="right")
            fig.add_hline(y=niveis['upper_1d'], line_width=2, line_dash="dash", line_color="#4CAF50",
                         annotation_text="1σ Superior", annotation_position="right")
            fig.add_hline(y=niveis['lower_1d'], line_width=2, line_dash="dash", line_color="#F44336",
                         annotation_text="1σ Inferior", annotation_position="right")
            fig.add_hline(y=niveis['upper_2d'], line_width=2, line_dash="dash", line_color="#2E7D32",
                         annotation_text="2σ Superior", annotation_position="right")
            fig.add_hline(y=niveis['lower_2d'], line_width=2, line_dash="dash", line_color="#C62828",
                         annotation_text="2σ Inferior", annotation_position="right")
            fig.add_hline(y=niveis['upper_3d'], line_width=3, line_dash="solid", line_color="#1B5E20",
                         annotation_text="3σ Superior", annotation_position="right")
            fig.add_hline(y=niveis['lower_3d'], line_width=3, line_dash="solid", line_color="#B71C1C",
                         annotation_text="3σ Inferior", annotation_position="right")
            
            # Layout com padrão do ATSMOMService
            fig.update_layout(
                height=700,
                showlegend=True,
                paper_bgcolor='rgba(0,0,0,0)',  # Fundo transparente
                plot_bgcolor='rgba(0,0,0,0)',   # Fundo do plot transparente
                font=dict(color=self.colors['text_color']),
                xaxis_title="Período",
                yaxis_title="Preço (R$)",
                legend=dict(
                    bgcolor='rgba(0,0,0,0)',  # Fundo da legenda transparente
                    bordercolor=self.colors['text_color'],
                    borderwidth=1
                ),
                xaxis_rangeslider_visible=False,
                hovermode="x unified"
            )
            
            # Configurar eixos
            fig.update_xaxes(
                showgrid=True,
                gridwidth=1,
                gridcolor=self.colors['grid_color'],
                linecolor=self.colors['text_color'],
                linewidth=1,
                showline=True,
                tickfont=dict(color=self.colors['text_color'])
            )
            
            fig.update_yaxes(
                showgrid=True,
                gridwidth=1,
                gridcolor=self.colors['grid_color'],
                linecolor=self.colors['text_color'],
                linewidth=1,
                showline=True,
                tickfont=dict(color=self.colors['text_color'])
            )
            
            # Excluir datas vazias do gráfico
            dt_all = pd.date_range(start=data.index[0], end=data.index[-1], freq="M")
            dt_all_py = [d.to_pydatetime() for d in dt_all]
            dt_obs_py = [d.to_pydatetime() for d in data.index]
            dt_breaks = [d for d in dt_all_py if d not in dt_obs_py]
            
            fig.update_xaxes(rangebreaks=[dict(values=dt_breaks)])
            
            return fig.to_html(include_plotlyjs='cdn')
            
        except Exception as e:
            logger.error(f"Erro ao gerar gráfico anual: {str(e)}")
            return None
    
    def create_weekly_chart(self, data: pd.DataFrame, ticker: str, year: str) -> Optional[str]:
        """
        Gerar gráfico de volatilidade semanal usando o padrão do ATSMOMService
        """
        try:
            fig = make_subplots(
                rows=1, cols=1,
                subplot_titles=(f'Análise de Volatilidade Semanal {str(int(year)+1)} - {ticker.replace(".SA", "")}',),
                vertical_spacing=0.08
            )
            
            # Candlestick
            fig.add_trace(go.Candlestick(
                x=data.index,
                open=data["adj_open"],
                high=data["adj_high"],
                low=data["adj_low"],
                close=data["close"],
                name="Preço",
                increasing_line_color="#00C851",
                decreasing_line_color="#FF4444",
                increasing_fillcolor="#00C851",
                decreasing_fillcolor="#FF4444"
            ))
            
            # Bandas de volatilidade
            fig.add_trace(go.Scatter(
                x=data.index, y=data["supply_band_1d"],
                name="🔼 Resistência 1σ",
                line=dict(color="#4CAF50", width=2, dash="dash")
            ))
            
            fig.add_trace(go.Scatter(
                x=data.index, y=data["demand_band_1d"],
                name="🔽 Suporte 1σ",
                line=dict(color="#F44336", width=2, dash="dash")
            ))
            
            fig.add_trace(go.Scatter(
                x=data.index, y=data["supply_band_2d"],
                name="🔼 Resistência 2σ",
                line=dict(color="#2E7D32", width=2, dash="solid")
            ))
            
            fig.add_trace(go.Scatter(
                x=data.index, y=data["demand_band_2d"],
                name="🔽 Suporte 2σ",
                line=dict(color="#C62828", width=2, dash="solid")
            ))
            
            # Layout com padrão do ATSMOMService
            fig.update_layout(
                height=700,
                showlegend=True,
                paper_bgcolor='rgba(0,0,0,0)',  # Fundo transparente
                plot_bgcolor='rgba(0,0,0,0)',   # Fundo do plot transparente
                font=dict(color=self.colors['text_color']),
                xaxis_title="Período",
                yaxis_title="Preço (R$)",
                legend=dict(
                    bgcolor='rgba(0,0,0,0)',  # Fundo da legenda transparente
                    bordercolor=self.colors['text_color'],
                    borderwidth=1
                ),
                xaxis_rangeslider_visible=False,
                hovermode="x unified"
            )
            
            # Configurar eixos
            fig.update_xaxes(
                showgrid=True,
                gridwidth=1,
                gridcolor=self.colors['grid_color'],
                linecolor=self.colors['text_color'],
                linewidth=1,
                showline=True,
                tickfont=dict(color=self.colors['text_color'])
            )
            
            fig.update_yaxes(
                showgrid=True,
                gridwidth=1,
                gridcolor=self.colors['grid_color'],
                linecolor=self.colors['text_color'],
                linewidth=1,
                showline=True,
                tickfont=dict(color=self.colors['text_color'])
            )
            
            # Excluir datas vazias do gráfico
            dt_all = pd.date_range(start=data.index[0], end=data.index[-1], freq="D")
            dt_all_py = [d.to_pydatetime() for d in dt_all]
            dt_obs_py = [d.to_pydatetime() for d in data.index]
            dt_breaks = [d for d in dt_all_py if d not in dt_obs_py]
            
            fig.update_xaxes(rangebreaks=[dict(values=dt_breaks)])
            
            return fig.to_html(include_plotlyjs='cdn')
            
        except Exception as e:
            logger.error(f"Erro ao gerar gráfico semanal: {str(e)}")
            return None
    
    def analyze_volatility(self, ticker: str, year: str = "2024", 
                          inicio: str = "2020-01-01", fim: str = "2025-12-31") -> Dict[str, Any]:
        """
        Método principal para análise completa de volatilidade seguindo padrão do ATSMOMService
        """
        try:
            logger.info(f"Iniciando análise de volatilidade para {ticker} - Ano: {year}")
            
            # Obter dados usando o método padronizado
            data = self.get_data(ticker, start=inicio, end=fim)
            
            if data is None:
                return {
                    'success': False,
                    'error': f'Não foi possível obter dados para {ticker}'
                }
            
            # Processar dados
            processed_data = self.processar_dados(data)
            
            if processed_data is None:
                return {
                    'success': False,
                    'error': 'Erro ao processar dados'
                }
            
            # Calcular níveis anuais
            niveis, error_msg = self.calcular_niveis_anuais(processed_data, year)
            
            if niveis is None:
                return {
                    'success': False,
                    'error': error_msg
                }
            
            # Gerar gráficos
            chart_annual = self.create_annual_chart(processed_data, ticker, year, niveis)
            chart_weekly = self.create_weekly_chart(processed_data, ticker, year)
            
            # Análise atual
            current_price = float(processed_data['close'].iloc[-1])
            current_vol = float(processed_data['vol'].iloc[-1])
            
            # Status baseado na posição atual vs níveis
            price_position = self._analyze_price_position(current_price, niveis)
            
            # Dados da análise seguindo padrão do ATSMOMService
            analysis_data = {
                'symbol': ticker,
                'year': year,
                'current_price': round(current_price, 2),
                'current_volatility': round(current_vol * 100, 2),
                'price_position': price_position,
                'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'niveis': niveis
            }
            
            # Dados brutos para gráficos (últimos 60 registros)
            raw_data = {
                'prices': [float(x) if not pd.isna(x) else 0.0 for x in processed_data['close'].tail(60)],
                'upper_1d': [float(x) if not pd.isna(x) else 0.0 for x in processed_data['supply_band_1d'].tail(60)],
                'lower_1d': [float(x) if not pd.isna(x) else 0.0 for x in processed_data['demand_band_1d'].tail(60)],
                'upper_2d': [float(x) if not pd.isna(x) else 0.0 for x in processed_data['supply_band_2d'].tail(60)],
                'lower_2d': [float(x) if not pd.isna(x) else 0.0 for x in processed_data['demand_band_2d'].tail(60)],
                'dates': [d.strftime('%Y-%m-%d') for d in processed_data.index[-60:]]
            }
            
            resultado = {
                'success': True,
                'analysis_data': analysis_data,
                'chart_annual': chart_annual,
                'chart_weekly': chart_weekly,
                'raw_data': raw_data
            }
            
            logger.info(f"Análise de volatilidade concluída com sucesso para {ticker}")
            return resultado
            
        except Exception as e:
            logger.error(f"Erro na análise de volatilidade: {str(e)}")
            return {
                'success': False,
                'error': f'Erro na análise: {str(e)}'
            }
    
    def _analyze_price_position(self, current_price: float, niveis: Dict) -> str:
        """
        Analisar posição do preço atual em relação aos níveis de volatilidade
        """
        try:
            if current_price > niveis['upper_2d']:
                return "SOBRECOMPRADO - Acima do 2º desvio superior"
            elif current_price > niveis['upper_1d']:
                return "RESISTÊNCIA - Entre 1º e 2º desvio superior"
            elif current_price > niveis['upper_05d']:
                return "LEVEMENTE ALTO - Acima do preço médio"
            elif current_price < niveis['lower_2d']:
                return "SOBREVENDIDO - Abaixo do 2º desvio inferior"
            elif current_price < niveis['lower_1d']:
                return "SUPORTE - Entre 1º e 2º desvio inferior"
            elif current_price < niveis['lower_05d']:
                return "LEVEMENTE BAIXO - Abaixo do preço médio"
            else:
                return "NEUTRO - Dentro da faixa normal"
                
        except Exception as e:
            logger.error(f"Erro ao analisar posição do preço: {str(e)}")
            return "INDEFINIDO - Erro na análise"
    
    def get_available_symbols(self) -> list:
        """
        Retornar lista de símbolos disponíveis
        """
        return [
            'PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3',
            'MGLU3', 'WEGE3', 'RENT3', 'LREN3', 'JBSS3',
            'B3SA3', 'SUZB3', 'RAIL3', 'USIM5', 'CSNA3',
            'GOAU4', 'EMBR3', 'CIEL3', 'JHSF3', 'TOTS3',
            'GGBR4', 'CSAN3', 'PRIO3', 'RADL3', 'HAPV3'
        ]
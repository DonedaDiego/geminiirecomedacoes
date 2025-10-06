"""
historical_service.py - Análise Histórica Market Makers com dados Floqui CORRIGIDO
"""

import numpy as np
import pandas as pd
import yfinance as yf
import requests
from datetime import datetime, timedelta
import warnings
import logging
import os
from dotenv import load_dotenv
from plotly.subplots import make_subplots
import plotly.graph_objects as go

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
load_dotenv()

def convert_to_json_serializable(obj):
    """Converte tipos numpy/pandas para Python nativo"""
    try:
        if obj is None or pd.isna(obj):
            return None
        elif isinstance(obj, (bool, np.bool_)):
            return bool(obj)
        elif isinstance(obj, (int, np.integer)):
            return int(obj)
        elif isinstance(obj, (float, np.floating)):
            return float(obj)
        elif isinstance(obj, (datetime, pd.Timestamp)):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {key: convert_to_json_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [convert_to_json_serializable(item) for item in obj]
        elif hasattr(obj, 'item'):
            return obj.item()
        elif hasattr(obj, 'tolist'):
            return obj.tolist()
        else:
            return str(obj)
    except:
        return None

class HistoricalDataProvider:
    def __init__(self):
        self.token = os.getenv('OPLAB_TOKEN')
        if not self.token:
            logging.warning("OPLAB_TOKEN não encontrado no .env")
            self.token = "seu_token_aqui"
        
        self.oplab_url = "https://api.oplab.com.br/v3"
        self.headers = {
            'Access-Token': self.token,
            'Content-Type': 'application/json'
        }
    
    def get_business_days(self, days_back=5):
        """Gera lista de dias úteis D-1, D-2, etc"""
        dates = []
        current_date = datetime.now() - timedelta(days=1)  # Sempre D-1
        
        while len(dates) < days_back:
            if current_date.weekday() < 5:  # 0-4 são dias úteis
                dates.append(current_date.strftime('%Y%m%d'))
            current_date -= timedelta(days=1)
        
        return dates[::-1]  # Ordem cronológica
    
    def get_spot_price(self, symbol):
        try:
            url = f"{self.oplab_url}/market/instruments/{symbol}"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data and 'close' in data:
                    return float(data['close'])
            
            ticker_yf = f"{symbol}.SA" if not symbol.endswith('.SA') else symbol
            stock = yf.Ticker(ticker_yf)
            hist = stock.history(period='1d')
            
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
                
            logging.error(f"Não foi possível obter cotação para {symbol}")
            return None
            
        except Exception as e:
            logging.error(f"Erro ao buscar cotação: {e}")
            return None
    
    def get_floqui_historical(self, ticker, vencimento, dt_referencia):
        """Busca dados do Floqui com DATA DE REFERENCIA"""
        try:
            # URL COM dt_referencia no formato YYYYMMDD
            url = f"https://floqui.com.br/api/posicoes_em_aberto/{ticker.lower()}/{vencimento}/{dt_referencia}"
            
            logging.info(f"URL Floqui: {url}")
            
            response = requests.get(url, timeout=15)
            
            if response.status_code != 200:
                logging.error(f"Erro API Floqui: {response.status_code} - Data: {dt_referencia}")
                return pd.DataFrame()
            
            data = response.json()
            
            if not data:
                logging.warning(f"Nenhum dado encontrado - Data: {dt_referencia}")
                return pd.DataFrame()
            
            df = pd.DataFrame(data)
            
            # Conversões seguras
            df['qtd_total'] = pd.to_numeric(df['qtd_total'], errors='coerce').fillna(0)
            df['qtd_descoberto'] = pd.to_numeric(df['qtd_descoberto'], errors='coerce').fillna(0)
            df['qtd_coberto'] = pd.to_numeric(df['qtd_coberto'], errors='coerce').fillna(0)
            df['qtd_trava'] = pd.to_numeric(df['qtd_trava'], errors='coerce').fillna(0)
            df['preco_exercicio'] = pd.to_numeric(df['preco_exercicio'], errors='coerce').fillna(0)
            
            # Filtros
            valid_data = df[
                (df['qtd_total'] > 0) &
                (df['preco_exercicio'] > 0)
            ].copy()
            
            logging.info(f"Dados Floqui: {len(valid_data)} registros para {dt_referencia}")
            return valid_data
            
        except Exception as e:
            logging.error(f"Erro ao buscar dados Floqui: {e}")
            return pd.DataFrame()
    
    def get_available_expirations(self, ticker):
        """Lista vencimentos disponíveis"""
        available_expirations = {
            "20250919": "19 Set 25 - M",
            "20251017": "17 Out 25 - M", 
            "20251121": "21 Nov 25 - M",
            "20251219": "19 Dez 25 - M",
            "20260116": "16 Jan 26 - M",
        }
        
        expirations = []
        # Testar com data D-1
        test_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
        
        for code, desc in available_expirations.items():
            test_df = self.get_floqui_historical(ticker, code, test_date)
            data_count = len(test_df)
            
            expirations.append({
                'code': code,
                'desc': desc,
                'data_count': data_count,
                'available': data_count > 0
            })
        
        return expirations

class HistoricalAnalyzer:
    def __init__(self):
        self.data_provider = HistoricalDataProvider()
    
    def calculate_gex_historical(self, df_day, spot_price):
        """Calcula GEX para um dia específico usando dados reais Floqui"""
        if df_day.empty:
            return pd.DataFrame()
        
        gex_data = []
        strikes = df_day['preco_exercicio'].unique()
        
        for strike in strikes:
            strike_data = df_day[df_day['preco_exercicio'] == strike]
            
            calls = strike_data[strike_data['tipo_opcao'] == 'CALL']
            puts = strike_data[strike_data['tipo_opcao'] == 'PUT']
            
            # GEX usando OI descoberto real
            call_gex = 0
            put_gex = 0
            call_oi_descoberto = 0
            put_oi_descoberto = 0
            
            if not calls.empty:
                call_oi_descoberto = int(calls['qtd_descoberto'].sum())
                # GEX simplificado: OI_descoberto * 0.01 (estimativa gamma)
                call_gex = call_oi_descoberto * 0.01 * spot_price
            
            if not puts.empty:
                put_oi_descoberto = int(puts['qtd_descoberto'].sum())
                put_gex = -(put_oi_descoberto * 0.01 * spot_price)
            
            total_gex = call_gex + put_gex
            
            gex_data.append({
                'strike': float(strike),
                'call_gex': call_gex,
                'put_gex': put_gex,
                'total_gex': total_gex,
                'call_oi_descoberto': call_oi_descoberto,
                'put_oi_descoberto': put_oi_descoberto,
                'total_oi_descoberto': call_oi_descoberto + put_oi_descoberto
            })
        
        return pd.DataFrame(gex_data).sort_values('strike')
    
    def create_gex_charts(self, historical_gex_data, ticker, vencimento, spot_price):
        """Cria 4 gráficos GEX estilo gamma-levels"""
        if not historical_gex_data:
            return None
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=[
                'GEX Descoberto', 'GEX Total',
                'GEX Cumulativo', 'OI Descoberto'
            ],
            vertical_spacing=0.15,
            horizontal_spacing=0.12
        )
        
        dates = list(historical_gex_data.keys())
        colors = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#06b6d4']
        
        # GRÁFICO 1: GEX Descoberto por dia (barras)
        for i, date in enumerate(dates):
            gex_df = historical_gex_data[date]
            if gex_df is not None and not gex_df.empty:
                strikes = gex_df['strike'].tolist()
                total_gex = gex_df['total_gex'].tolist()
                
                fig.add_trace(
                    go.Bar(
                        x=strikes,
                        y=total_gex,
                        name=f'{date[-4:]}',
                        marker_color=colors[i % len(colors)],
                        opacity=0.7,
                        showlegend=True
                    ),
                    row=1, col=1
                )
        
        # GRÁFICO 2: GEX Total (último dia - barras coloridas)
        if dates:
            last_gex = historical_gex_data[dates[-1]]
            if last_gex is not None and not last_gex.empty:
                strikes = last_gex['strike'].tolist()
                total_gex = last_gex['total_gex'].tolist()
                colors_gex = ['#ef4444' if x < 0 else '#22c55e' for x in total_gex]
                
                fig.add_trace(
                    go.Bar(
                        x=strikes,
                        y=total_gex,
                        marker_color=colors_gex,
                        showlegend=False
                    ),
                    row=1, col=2
                )
        
        # GRÁFICO 3: GEX Cumulativo (último dia - linha)
        if dates:
            last_gex = historical_gex_data[dates[-1]]
            if last_gex is not None and not last_gex.empty:
                strikes = last_gex['strike'].tolist()
                total_gex = last_gex['total_gex'].tolist()
                cumulative = np.cumsum(total_gex).tolist()
                
                fig.add_trace(
                    go.Scatter(
                        x=strikes,
                        y=cumulative,
                        mode='lines+markers',
                        line=dict(color='#06b6d4', width=4),
                        marker=dict(color='#06b6d4', size=6),
                        showlegend=False
                    ),
                    row=2, col=1
                )
        
        # GRÁFICO 4: OI Descoberto (último dia - barras)
        if dates:
            last_gex = historical_gex_data[dates[-1]]
            if last_gex is not None and not last_gex.empty:
                strikes = last_gex['strike'].tolist()
                oi_descoberto = last_gex['total_oi_descoberto'].tolist()
                
                fig.add_trace(
                    go.Bar(
                        x=strikes,
                        y=oi_descoberto,
                        marker_color='#a855f7',
                        showlegend=False
                    ),
                    row=2, col=2
                )
        
        # Linha do spot price
        for row in range(1, 3):
            for col in range(1, 3):
                fig.add_vline(
                    x=spot_price,
                    line=dict(color='#fbbf24', width=3, dash='dash'),
                    row=row, col=col
                )
        
        fig.update_layout(
            title={
                'text': f'Análise GEX Histórica - {ticker} ({vencimento})',
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 20, 'color': '#ffffff'}
            },
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#ffffff'),
            height=800,
            showlegend=True
        )
        
        fig.update_xaxes(gridcolor='rgba(255,255,255,0.1)', color='#ffffff')
        fig.update_yaxes(gridcolor='rgba(255,255,255,0.1)', color='#ffffff')
        
        return fig.to_json()
    
    def analyze_historical(self, ticker, vencimento, days_back=5):
        """Análise histórica GEX usando dados reais Floqui"""
        logging.info(f"INICIANDO ANÁLISE HISTÓRICA GEX - {ticker}")
        
        spot_price = self.data_provider.get_spot_price(ticker)
        if not spot_price:
            raise ValueError("Erro: não foi possível obter cotação")
        
        # Obter datas de negócio D-1, D-2, etc
        business_dates = self.data_provider.get_business_days(days_back)
        logging.info(f"Datas analisadas: {business_dates}")
        
        # Processar cada data
        historical_gex_data = {}
        valid_dates = []
        
        for date_str in business_dates:
            daily_data = self.data_provider.get_floqui_historical(ticker, vencimento, date_str)
            
            if not daily_data.empty:
                gex_df = self.calculate_gex_historical(daily_data, spot_price)
                historical_gex_data[date_str] = gex_df
                valid_dates.append(date_str)
                logging.info(f"GEX calculado para {date_str}: {len(gex_df)} strikes")
            else:
                historical_gex_data[date_str] = None
        
        if not valid_dates:
            raise ValueError("Nenhum dado histórico encontrado")
        
        plot_json = self.create_gex_charts(historical_gex_data, ticker, vencimento, spot_price)
        
        total_records = sum(len(df) if df is not None else 0 for df in historical_gex_data.values())
        
        return {
            'ticker': ticker,
            'vencimento': vencimento,
            'spot_price': spot_price,
            'dates_analyzed': valid_dates,
            'total_records': total_records,
            'plot_json': plot_json,
            'success': True
        }

class HistoricalService:
    def __init__(self):
        self.analyzer = HistoricalAnalyzer()
    
    def get_available_expirations(self, ticker):
        return self.analyzer.data_provider.get_available_expirations(ticker)
    
    def analyze_historical_complete(self, ticker, vencimento, days_back=5):
        try:
            result = self.analyzer.analyze_historical(ticker, vencimento, days_back)
            
            api_result = {
                'ticker': ticker.replace('.SA', ''),
                'vencimento': vencimento,
                'spot_price': result['spot_price'],
                'dates_analyzed': result['dates_analyzed'],
                'total_records': result['total_records'],
                'plot_json': result['plot_json'],
                'success': True
            }
            
            return convert_to_json_serializable(api_result)
            
        except Exception as e:
            logging.error(f"Erro na análise histórica: {e}")
            raise
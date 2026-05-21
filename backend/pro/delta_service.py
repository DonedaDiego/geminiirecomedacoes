"""
delta_service.py - DEX Analysis COM DADOS DO BANCO POSTGRESQL
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
from sqlalchemy import create_engine, text

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
load_dotenv()

def convert_to_json_serializable(obj):
    """Converte tipos numpy/pandas para Python nativo"""
    try:
        if obj is None:
            return None
        if isinstance(obj, (list, tuple)):
            return [convert_to_json_serializable(i) for i in obj]
        if isinstance(obj, dict):
            return {k: convert_to_json_serializable(v) for k, v in obj.items()}
        if isinstance(obj, (bool, np.bool_)):
            return bool(obj)
        if isinstance(obj, (int, np.integer)):
            return int(obj)
        if isinstance(obj, (float, np.floating)):
            return None if np.isnan(obj) else float(obj)
        if isinstance(obj, (datetime, pd.Timestamp)):
            return obj.isoformat()
        if hasattr(obj, 'item'):
            return obj.item()
        if hasattr(obj, 'tolist'):
            return obj.tolist()
        return str(obj)
    except:
        return None


class ExpirationManager:
    def __init__(self, db_engine):
        self.db_engine = db_engine
        self.available_expirations = {
            "20260424": {"date": datetime(2026, 4, 24), "desc": "24 Abr 26 - W4"},
            "20260430": {"date": datetime(2026, 4, 30), "desc": "30 Abr 26 - W5"},
            "20260508": {"date": datetime(2026, 5, 8),  "desc": "08 Mai 26 - W2"},
            "20260515": {"date": datetime(2026, 5, 15), "desc": "15 Mai 26 - M"},
            "20260522": {"date": datetime(2026, 5, 22), "desc": "22 Mai 26 - W4"},
            "20260529": {"date": datetime(2026, 5, 29), "desc": "29 Mai 26 - W5"},
            "20260605": {"date": datetime(2026, 6, 5),  "desc": "05 Jun 26 - W1"},
            "20260612": {"date": datetime(2026, 6, 12), "desc": "12 Jun 26 - W2"},
            "20260619": {"date": datetime(2026, 6, 19), "desc": "19 Jun 26 - M"},
            "20260717": {"date": datetime(2026, 7, 17), "desc": "17 Jul 26 - M"},
            "20260821": {"date": datetime(2026, 8, 21), "desc": "21 Ago 26 - M"},
            "20260918": {"date": datetime(2026, 9, 18), "desc": "18 Set 26 - M"},
            "20261016": {"date": datetime(2026, 10, 16), "desc": "16 Out 26 - M"},
            "20261119": {"date": datetime(2026, 11, 19), "desc": "19 Nov 26 - M"},
            "20261218": {"date": datetime(2026, 12, 18), "desc": "18 Dez 26 - M"},
            "20270115": {"date": datetime(2027, 1, 15), "desc": "15 Jan 27 - M"},
            "20270219": {"date": datetime(2027, 2, 19), "desc": "19 Fev 27 - M"},
            "20270319": {"date": datetime(2027, 3, 19), "desc": "19 Mar 27 - M"},
            "20270416": {"date": datetime(2027, 4, 16), "desc": "16 Abr 27 - M"},
            "20270521": {"date": datetime(2027, 5, 21), "desc": "21 Mai 27 - M"},
            "20270618": {"date": datetime(2027, 6, 18), "desc": "18 Jun 27 - M"},
            "20270716": {"date": datetime(2027, 7, 16), "desc": "16 Jul 27 - M"},
            "20270820": {"date": datetime(2027, 8, 20), "desc": "20 Ago 27 - M"},
            "20270917": {"date": datetime(2027, 9, 17), "desc": "17 Set 27 - M"},
            "20271015": {"date": datetime(2027, 10, 15), "desc": "15 Out 27 - M"},
            "20271119": {"date": datetime(2027, 11, 19), "desc": "19 Nov 27 - M"},
            "20271217": {"date": datetime(2027, 12, 17), "desc": "17 Dez 27 - M"},
            "20280121": {"date": datetime(2028, 1, 21), "desc": "21 Jan 28 - M"},
            "20280218": {"date": datetime(2028, 2, 18), "desc": "18 Fev 28 - M"},
        }

    def test_data_availability(self, symbol, expiration_code):
        """Testa disponibilidade no BANCO DE DADOS"""
        try:
            exp_date = datetime.strptime(expiration_code, '%Y%m%d')
            query = text("""
                SELECT COUNT(*) as total
                FROM opcoes_b3
                WHERE ticker = :symbol
                AND vencimento = :vencimento
                AND data_referencia = (SELECT MAX(data_referencia) FROM opcoes_b3)
            """)
            with self.db_engine.connect() as conn:
                result = conn.execute(query, {'symbol': symbol, 'vencimento': exp_date})
                row = result.fetchone()
                return row[0] if row else 0
        except Exception as e:
            logging.error(f"Erro ao testar disponibilidade: {e}")
            return 0

    def get_available_expirations_list(self, symbol):
        today = datetime.now().date()
        available = []
        for code, data in self.available_expirations.items():
            if data["date"].date() >= today:
                days = (data["date"].date() - today).days
                data_count = self.test_data_availability(symbol, code)
                available.append({
                    "code": code,
                    "desc": data["desc"],
                    "days": days,
                    "data_count": data_count,
                    "available": data_count > 0,
                    "window": "SEMANAL" if "- W" in data["desc"] else "MENSAL"
                })
        return sorted(available, key=lambda x: x["days"])

    def get_best_available_expiration(self, symbol):
        today = datetime.now().date()
        for code, data in self.available_expirations.items():
            if data["date"].date() >= today:
                data_count = self.test_data_availability(symbol, code)
                if data_count > 0:
                    return {
                        "code": code,
                        "desc": data["desc"],
                        "window": "SEMANAL" if "- W" in data["desc"] else "MENSAL"
                    }
        return None


class DataProvider:
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

        DATABASE_URL = os.getenv('DATABASE_URL')
        if not DATABASE_URL:
            DB_HOST     = os.getenv('PGHOST') or os.getenv('DB_HOST', 'localhost')
            DB_NAME     = os.getenv('PGDATABASE') or os.getenv('DB_NAME', 'railway')
            DB_USER     = os.getenv('PGUSER') or os.getenv('DB_USER', 'postgres')
            DB_PASSWORD = os.getenv('PGPASSWORD') or os.getenv('DB_PASSWORD', '')
            DB_PORT     = os.getenv('PGPORT') or os.getenv('DB_PORT', '5432')
            try:
                DB_PORT = str(int(DB_PORT))
            except (ValueError, TypeError):
                logging.error(f"DB_PORT inválido: '{DB_PORT}' - usando 5432")
                DB_PORT = '5432'
            DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

        logging.info("Conectando ao banco PostgreSQL (DEX)...")
        try:
            self.db_engine = create_engine(DATABASE_URL)
            with self.db_engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM opcoes_b3"))
                count = result.fetchone()[0]
                logging.info(f"Conexão OK (DEX) - {count:,} registros na opcoes_b3")
        except Exception as e:
            logging.error(f"Erro ao conectar (DEX): {e}")
            raise

        self.expiration_manager = ExpirationManager(self.db_engine)

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
            return None
        except Exception as e:
            logging.error(f"Erro cotação: {e}")
            return None

    def get_oplab_historical_data(self, symbol):
        try:
            to_date   = datetime.now().strftime('%Y-%m-%d')
            from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            url = f"{self.oplab_url}/market/historical/options/{symbol}/{from_date}/{to_date}"
            response = requests.get(url, headers=self.headers, timeout=15)
            if response.status_code != 200:
                logging.error(f"Erro na API Oplab: {response.status_code}")
                return pd.DataFrame()
            data = response.json()
            if not data:
                logging.warning("Nenhum dado retornado da Oplab")
                return pd.DataFrame()
            df = pd.DataFrame(data)
            df['time'] = pd.to_datetime(df['time'])
            latest_date = df['time'].max().date()
            latest_data = df[df['time'].dt.date == latest_date].copy()
            valid_data = latest_data[
                (latest_data['delta'] != 0) &
                (latest_data['premium'] > 0) &
                (latest_data['strike'] > 0) &
                (latest_data['days_to_maturity'] > 0) &
                (latest_data['days_to_maturity'] <= 180)
            ].copy()
            logging.info(f"Dados Delta Oplab: {len(valid_data)} opções")
            return valid_data
        except Exception as e:
            logging.error(f"Erro dados Oplab: {e}")
            return pd.DataFrame()

    def get_floqui_oi_breakdown(self, symbol, expiration_code=None):
        """BUSCA DO BANCO DE DADOS POSTGRESQL"""
        try:
            if expiration_code:
                expiration = {
                    "code": expiration_code,
                    "desc": self.expiration_manager.available_expirations.get(expiration_code, {}).get("desc", expiration_code),
                    "window": "SEMANAL" if "- W" in self.expiration_manager.available_expirations.get(expiration_code, {}).get("desc", "") else "MENSAL"
                }
            else:
                expiration = self.expiration_manager.get_best_available_expiration(symbol)

            if not expiration:
                logging.warning("Nenhum vencimento disponível")
                return {}, None

            exp_date = datetime.strptime(expiration['code'], '%Y%m%d')
            query = text("""
                SELECT
                    preco_exercicio,
                    tipo_opcao,
                    SUM(qtd_total)      AS qtd_total,
                    SUM(qtd_descoberto) AS qtd_descoberto,
                    SUM(qtd_trava)      AS qtd_trava,
                    SUM(qtd_coberto)    AS qtd_coberto
                FROM opcoes_b3
                WHERE ticker = :symbol
                AND vencimento = :vencimento
                AND data_referencia = (
                    SELECT MAX(data_referencia)
                    FROM opcoes_b3
                    WHERE ticker = :symbol
                )
                GROUP BY preco_exercicio, tipo_opcao
                ORDER BY preco_exercicio
            """)
            df = pd.read_sql(query, self.db_engine, params={
                'symbol': symbol, 'vencimento': exp_date
            })
            if df.empty:
                logging.warning(f"Nenhum dado encontrado no banco para {symbol}")
                return {}, expiration

            oi_breakdown = {}
            for _, row in df.iterrows():
                strike      = float(row['preco_exercicio'])
                option_type = str(row['tipo_opcao']).upper()
                oi_total    = int(row['qtd_total'])
                oi_desc     = int(row['qtd_descoberto'])
                if strike > 0 and oi_total > 0:
                    key = f"{strike}_{option_type}"
                    oi_breakdown[key] = {
                        'strike':     strike,
                        'type':       option_type,
                        'total':      oi_total,
                        'descoberto': oi_desc,
                        'travado':    int(row['qtd_trava']),
                        'coberto':    int(row['qtd_coberto'])
                    }
            logging.info(f"OI breakdown DEX: {len(oi_breakdown)} strikes (vencimento: {expiration['desc']})")
            return oi_breakdown, expiration
        except Exception as e:
            logging.error(f"Erro Floqui: {e}")
            return {}, None


class DEXCalculator:

    def calculate_dex(self, oplab_df, oi_breakdown, spot_price):
        """Calcula DEX = Delta × Open Interest × 100"""
        if oplab_df.empty:
            return pd.DataFrame()

        price_range   = spot_price * 0.25
        valid_options = oplab_df[
            (oplab_df['strike'] >= spot_price - price_range) &
            (oplab_df['strike'] <= spot_price + price_range)
        ].copy()

        if valid_options.empty:
            return pd.DataFrame()

        dex_data = []
        for strike in valid_options['strike'].unique():
            strike_options = valid_options[valid_options['strike'] == strike]
            calls = strike_options[strike_options['type'] == 'CALL']
            puts  = strike_options[strike_options['type'] == 'PUT']

            call_data      = None
            put_data       = None
            has_real_call  = False
            has_real_put   = False

            if len(calls) > 0:
                call_key = f"{float(strike)}_CALL"
                if call_key in oi_breakdown:
                    call_data     = oi_breakdown[call_key]
                    has_real_call = True

            if len(puts) > 0:
                put_key = f"{float(strike)}_PUT"
                if put_key in oi_breakdown:
                    put_data     = oi_breakdown[put_key]
                    has_real_put = True

            if not (has_real_call or has_real_put):
                continue

            call_dex = call_dex_descoberto = 0.0
            if call_data and len(calls) > 0:
                avg_delta          = float(calls['delta'].mean())
                call_dex           = avg_delta * call_data['total']      * 100
                call_dex_descoberto = avg_delta * call_data['descoberto'] * 100

            put_dex = put_dex_descoberto = 0.0
            if put_data and len(puts) > 0:
                avg_delta         = float(puts['delta'].mean())
                put_dex           = avg_delta * put_data['total']      * 100
                put_dex_descoberto = avg_delta * put_data['descoberto'] * 100

            dex_data.append({
                'strike':               float(strike),
                'call_dex':             float(call_dex),
                'put_dex':              float(put_dex),
                'total_dex':            float(call_dex + put_dex),
                'call_dex_descoberto':  float(call_dex_descoberto),
                'put_dex_descoberto':   float(put_dex_descoberto),
                'total_dex_descoberto': float(call_dex_descoberto + put_dex_descoberto),
                'call_oi_total':        int(call_data['total']      if call_data else 0),
                'put_oi_total':         int(put_data['total']       if put_data  else 0),
                'call_oi_descoberto':   int(call_data['descoberto'] if call_data else 0),
                'put_oi_descoberto':    int(put_data['descoberto']  if put_data  else 0),
                'has_real_data':        has_real_call or has_real_put
            })

        result_df = pd.DataFrame(dex_data).sort_values('strike')
        logging.info(f"DEX calculado para {len(result_df)} strikes com dados reais")
        return result_df


class DirectionalPressureDetector:
    """Detector de pressão direcional baseada em DEX"""

    def find_max_pressure_levels(self, dex_df, spot_price):
        if dex_df.empty:
            return None

        max_bullish_idx = dex_df['total_dex'].idxmax()
        max_bearish_idx = dex_df['total_dex'].idxmin()
        net_pressure    = dex_df['total_dex'].sum()
        total_abs       = dex_df['total_dex'].abs().sum()

        return {
            'bullish_target':         float(dex_df.loc[max_bullish_idx, 'strike']),
            'bullish_pressure':       float(dex_df.loc[max_bullish_idx, 'total_dex']),
            'bearish_target':         float(dex_df.loc[max_bearish_idx, 'strike']),
            'bearish_pressure':       float(dex_df.loc[max_bearish_idx, 'total_dex']),
            'net_pressure':           float(net_pressure),
            'net_pressure_descoberto': float(dex_df['total_dex_descoberto'].sum()),
            'concentration_ratio':    float(abs(net_pressure) / total_abs) if total_abs > 0 else 0.0,
            'market_bias':            'BULLISH' if net_pressure > 1000 else 'BEARISH' if net_pressure < -1000 else 'NEUTRAL'
        }


class DEXAnalyzer:
    def __init__(self):
        self.data_provider  = DataProvider()
        self.dex_calculator = DEXCalculator()

    def find_targets(self, dex_df, spot_price):
        """Encontra maiores concentrações de calls e puts COM DADOS REAIS"""
        if dex_df.empty:
            return None, None

        dex_real = dex_df[dex_df['has_real_data'] == True].copy()
        if len(dex_real) < 2:
            logging.warning("Menos de 2 strikes com dados reais do banco (DEX)")
            return None, None

        logging.info(f"DEX Targets: {len(dex_real)} strikes reais de {len(dex_df)}")

        max_calls_strike = None
        calls_with_oi = dex_real[dex_real['call_oi_descoberto'] > 0]
        if not calls_with_oi.empty:
            max_calls_strike = float(calls_with_oi.loc[calls_with_oi['call_oi_descoberto'].idxmax(), 'strike'])
            logging.info(f"  Target CALLS: R$ {max_calls_strike:.2f}")

        max_puts_strike = None
        puts_with_oi = dex_real[dex_real['put_oi_descoberto'] > 0]
        if not puts_with_oi.empty:
            max_puts_strike = float(puts_with_oi.loc[puts_with_oi['put_oi_descoberto'].idxmax(), 'strike'])
            logging.info(f"  Target PUTS: R$ {max_puts_strike:.2f}")

        return max_calls_strike, max_puts_strike

    # ─────────────────────────────────────────────────────────────────────────
    # Gráfico 6 painéis — mantido para compatibilidade
    # ─────────────────────────────────────────────────────────────────────────
    def create_6_charts(self, dex_df, spot_price, symbol,
                        max_calls_strike=None, max_puts_strike=None,
                        expiration_info=None):
        if dex_df.empty:
            return None

        title = expiration_info["desc"] if expiration_info else ""

        subplot_titles = [
            '<b style="color: #ffffff;">Total DEX</b><br><span style="font-size: 12px; color: #888;">Pressão direcional total</span>',
            '<b style="color: #ffffff;">DEX Descoberto</b><br><span style="font-size: 12px; color: #888;">Pressão real descoberta</span>',
            '<b style="color: #ffffff;">Pressão Direcional</b><br><span style="font-size: 12px; color: #888;">Intensidade absoluta</span>',
            '<b style="color: #ffffff;">Calls vs Puts</b><br><span style="font-size: 12px; color: #888;">Sentimento direcional</span>',
            '<b style="color: #ffffff;">DEX Cumulativo</b><br><span style="font-size: 12px; color: #888;">Fluxo de pressão</span>',
            '<b style="color: #ffffff;">Momentum</b><br><span style="font-size: 12px; color: #888;">Velocidade mudança</span>'
        ]

        fig = make_subplots(rows=3, cols=2, subplot_titles=subplot_titles,
                            vertical_spacing=0.08, horizontal_spacing=0.08)

        strikes     = [float(x) for x in dex_df['strike'].tolist()]
        total_dex   = [float(x) for x in dex_df['total_dex'].tolist()]
        descoberto  = [float(x) for x in dex_df['total_dex_descoberto'].tolist()]
        call_dex    = [float(x) for x in dex_df['call_dex'].tolist()]
        put_dex     = [float(x) for x in dex_df['put_dex'].tolist()]

        colors1 = ['#ef4444' if x < 0 else '#22c55e' for x in total_dex]
        fig.add_trace(go.Bar(x=strikes, y=total_dex, marker_color=colors1, showlegend=False), row=1, col=1)

        colors2 = ['#ef4444' if x < 0 else '#22c55e' for x in descoberto]
        fig.add_trace(go.Bar(x=strikes, y=descoberto, marker_color=colors2, showlegend=False), row=1, col=2)

        fig.add_trace(go.Bar(x=strikes, y=[abs(x) for x in descoberto],
                             marker_color='#f97316', showlegend=False), row=2, col=1)

        fig.add_trace(go.Bar(x=strikes, y=call_dex, marker_color='#22c55e', showlegend=False), row=2, col=2)
        fig.add_trace(go.Bar(x=strikes, y=put_dex,  marker_color='#ef4444', showlegend=False), row=2, col=2)

        cumulative = np.cumsum(total_dex).tolist()
        fig.add_trace(go.Scatter(
            x=strikes, y=cumulative, mode='lines',
            line=dict(color='#a855f7', width=4),
            fill='tozeroy', fillcolor='rgba(168,85,247,0.3)',
            showlegend=False
        ), row=3, col=1)

        momentum = [descoberto[i] - descoberto[i-1] if i > 0 else descoberto[i]
                    for i in range(len(descoberto))]
        fig.add_trace(go.Bar(x=strikes, y=momentum,
                             marker_color=['#22c55e' if x > 0 else '#ef4444' for x in momentum],
                             showlegend=False), row=3, col=2)

        for row in range(1, 4):
            for col in range(1, 3):
                fig.add_vline(x=spot_price, line=dict(color='#ffffff', width=3, dash='dash'), row=row, col=col)
                fig.add_hline(y=0, line=dict(color='rgba(255,255,255,0.3)', width=1), row=row, col=col)

        fig.update_layout(
            title={'text': title, 'x': 0.5, 'xanchor': 'center',
                   'font': {'size': 20, 'color': '#ffffff', 'family': 'Inter, sans-serif'}},
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#ffffff', family='Inter, sans-serif'),
            height=1600, showlegend=False,
            margin=dict(l=50, r=50, t=100, b=50)
        )
        fig.update_annotations(font=dict(color='#ffffff', family='Inter, sans-serif', size=21))
        fig.update_xaxes(gridcolor='rgba(255,255,255,0.1)', color='#ffffff', showgrid=True, zeroline=False)
        fig.update_yaxes(gridcolor='rgba(255,255,255,0.1)', color='#ffffff', showgrid=True, zeroline=False)

        return fig.to_json()

    # ─────────────────────────────────────────────────────────────────────────
    # NOVO: gráfico único por modo — espelho exato do gamma_service
    # ─────────────────────────────────────────────────────────────────────────
    def create_single_chart(self, dex_df, spot_price, symbol,
                            expiration_info=None, mode='net'):
        """
        Renderiza um único gráfico Plotly de acordo com o modo selecionado.

        Modos disponíveis:
          'net'        → Net Exposure (total_dex, verde/vermelho)
          'descoberto' → DEX Descoberto (total_dex_descoberto, verde/vermelho)
          'call_put'   → Call/Put Exposure (call_dex verde, put_dex vermelho, relative)
          'oi'         → Open Interest total (call_oi + put_oi, stacked)

        Retorna fig.to_json()
        """
        if dex_df.empty:
            return None

        dex_df   = dex_df.sort_values('strike').reset_index(drop=True)
        strikes  = [float(x) for x in dex_df['strike'].tolist()]
        total_dex   = [float(x) for x in dex_df['total_dex'].tolist()]
        descoberto  = [float(x) for x in dex_df['total_dex_descoberto'].tolist()]
        call_dex    = [float(x) for x in dex_df['call_dex'].tolist()]
        put_dex     = [float(x) for x in dex_df['put_dex'].tolist()]
        call_oi     = [int(x)   for x in dex_df['call_oi_total'].tolist()]
        put_oi      = [int(x)   for x in dex_df['put_oi_total'].tolist()]

        mode_labels = {
            'net':        'Net Exposure',
            'descoberto': 'DEX Descoberto',
            'call_put':   'Call / Put Exposure',
            'oi':         'Open Interest',
        }
        title_mode = mode_labels.get(mode, 'Net Exposure')
        exp_desc   = expiration_info["desc"] if expiration_info else ""

        fig = go.Figure()

        if mode == 'net':
            colors = ['#ef4444' if v < 0 else '#22c55e' for v in total_dex]
            fig.add_trace(go.Bar(
                x=strikes, y=total_dex,
                marker_color=colors, marker_line_width=0,
                showlegend=False,
                hovertemplate='Strike: R$ %{x:.2f}<br>DEX: %{y:,.0f}<extra></extra>'
            ))

        elif mode == 'descoberto':
            colors = ['#ef4444' if v < 0 else '#22c55e' for v in descoberto]
            fig.add_trace(go.Bar(
                x=strikes, y=descoberto,
                marker_color=colors, marker_line_width=0,
                showlegend=False,
                hovertemplate='Strike: R$ %{x:.2f}<br>DEX Desc: %{y:,.0f}<extra></extra>'
            ))

        elif mode == 'call_put':
            fig.add_trace(go.Bar(
                x=strikes, y=call_dex, name='Calls',
                marker_color='#22c55e', marker_line_width=0,
                hovertemplate='Strike: R$ %{x:.2f}<br>Call DEX: %{y:,.0f}<extra></extra>'
            ))
            fig.add_trace(go.Bar(
                x=strikes, y=put_dex, name='Puts',
                marker_color='#ef4444', marker_line_width=0,
                hovertemplate='Strike: R$ %{x:.2f}<br>Put DEX: %{y:,.0f}<extra></extra>'
            ))
            fig.update_layout(barmode='relative')

        elif mode == 'oi':
            fig.add_trace(go.Bar(
                x=strikes, y=call_oi, name='Call OI',
                marker_color='#22c55e', marker_line_width=0,
                hovertemplate='Strike: R$ %{x:.2f}<br>Call OI: %{y:,}<extra></extra>'
            ))
            fig.add_trace(go.Bar(
                x=strikes, y=put_oi, name='Put OI',
                marker_color='#ef4444', marker_line_width=0,
                hovertemplate='Strike: R$ %{x:.2f}<br>Put OI: %{y:,}<extra></extra>'
            ))
            fig.update_layout(barmode='stack')

        # Linhas de referência
        fig.add_vline(
            x=spot_price,
            line=dict(color='#ffffff', width=2, dash='dash'),
            annotation=dict(
                text='SPOT', font=dict(color='#ffffff', size=11),
                yref='paper', y=1.0, yanchor='bottom',
                bgcolor='rgba(0,0,0,0.6)', borderpad=3
            )
        )
        fig.add_hline(y=0, line=dict(color='rgba(255,255,255,0.2)', width=1))

        fig.update_layout(
            title={
                'text': f'{title_mode}  ·  {exp_desc}',
                'x': 0.02, 'xanchor': 'left',
                'font': {'size': 15, 'color': '#aaaaaa', 'family': 'Inter, sans-serif'}
            },
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#ffffff', family='Inter, sans-serif', size=12),
            height=520,
            margin=dict(l=60, r=30, t=60, b=60),
            showlegend=(mode in ['call_put', 'oi']),
            legend=dict(orientation='h', x=0, y=1.08,
                        font=dict(color='#ffffff', size=11)),
            bargap=0.15,
        )
        fig.update_xaxes(
            gridcolor='rgba(255,255,255,0.06)', color='#aaaaaa',
            showgrid=True, zeroline=False,
            tickformat='.2f', tickprefix='R$ '
        )
        fig.update_yaxes(
            gridcolor='rgba(255,255,255,0.06)', color='#aaaaaa',
            showgrid=True, zeroline=False
        )

        return fig.to_json()

    def create_cumulative_chart(self, dex_df, spot_price, symbol, expiration_info=None):
        """Gráfico DEX Cumulativo — linha + área, fixo no novo layout."""
        if dex_df.empty:
            return None

        dex_df     = dex_df.sort_values('strike').reset_index(drop=True)
        strikes    = [float(x) for x in dex_df['strike'].tolist()]
        total_dex  = [float(x) for x in dex_df['total_dex'].tolist()]
        cumulative = list(np.cumsum(total_dex))
        exp_desc   = expiration_info['desc'] if expiration_info else ''

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=strikes, y=cumulative,
            mode='lines',
            line=dict(color='#a855f7', width=2),
            fill='tozeroy',
            fillcolor='rgba(168,85,247,0.08)',
            showlegend=False,
            hovertemplate='Strike: R$ %{x:.2f}<br>Cum DEX: %{y:,.0f}<extra></extra>'
        ))

        fig.add_vline(
            x=spot_price,
            line=dict(color='#ffffff', width=2, dash='dash'),
            annotation=dict(
                text='SPOT', font=dict(color='#ffffff', size=11),
                yref='paper', y=1.0, yanchor='bottom',
                bgcolor='rgba(0,0,0,0.6)', borderpad=3
            )
        )
        fig.add_hline(y=0, line=dict(color='rgba(255,255,255,0.15)', width=1))

        fig.update_layout(
            title=dict(
                text=f'DEX Cumulativo  ·  {exp_desc}',
                x=0.02, xanchor='left',
                font=dict(size=13, color='#555', family='Inter, sans-serif')
            ),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#aaa', family='Inter, sans-serif', size=11),
            height=520,
            margin=dict(l=60, r=20, t=40, b=45),
            showlegend=False,
        )
        fig.update_xaxes(
            gridcolor='rgba(255,255,255,0.05)', color='#555',
            zeroline=False, tickformat='.2f', tickprefix='R$ '
        )
        fig.update_yaxes(
            gridcolor='rgba(255,255,255,0.05)', color='#555',
            zeroline=True, zerolinecolor='rgba(255,255,255,0.15)'
        )

        return fig.to_json()

    def analyze(self, symbol, expiration_code=None):
        """Análise principal DEX"""
        logging.info(f"INICIANDO ANALISE DEX - {symbol}")

        spot_price = self.data_provider.get_spot_price(symbol)
        if not spot_price:
            raise ValueError("Erro: não foi possível obter cotação")

        oplab_df = self.data_provider.get_oplab_historical_data(symbol)
        if oplab_df.empty:
            raise ValueError("Erro: sem dados da Oplab")

        oi_breakdown, expiration_info = self.data_provider.get_floqui_oi_breakdown(symbol, expiration_code)

        dex_df = self.dex_calculator.calculate_dex(oplab_df, oi_breakdown, spot_price)
        if dex_df.empty:
            raise ValueError("Erro: falha no cálculo DEX")

        dex_df = dex_df.sort_values('strike').reset_index(drop=True)

        pressure_detector = DirectionalPressureDetector()
        pressure_levels   = pressure_detector.find_max_pressure_levels(dex_df, spot_price)

        max_calls_strike, max_puts_strike = self.find_targets(dex_df, spot_price)

        # Gráfico 6 painéis — mantido
        plot_json = self.create_6_charts(
            dex_df, spot_price, symbol,
            max_calls_strike=max_calls_strike,
            max_puts_strike=max_puts_strike,
            expiration_info=expiration_info
        )

        # Gráficos individuais por modo — novo layout
        single_charts = {
            'net':        self.create_single_chart(dex_df, spot_price, symbol, expiration_info, mode='net'),
            'descoberto': self.create_single_chart(dex_df, spot_price, symbol, expiration_info, mode='descoberto'),
            'call_put':   self.create_single_chart(dex_df, spot_price, symbol, expiration_info, mode='call_put'),
            'oi':         self.create_single_chart(dex_df, spot_price, symbol, expiration_info, mode='oi'),
            'cumulativo': self.create_cumulative_chart(dex_df, spot_price, symbol, expiration_info),
        }

        net_dex            = float(dex_df['total_dex'].sum())
        net_dex_descoberto = float(dex_df['total_dex_descoberto'].sum())
        real_data_count    = int(dex_df['has_real_data'].sum())

        # Pressão restante — mesmo cálculo do serviço anterior
        cumulative_values  = np.cumsum(dex_df['total_dex'].values)
        max_cumulative     = float(max(cumulative_values)) if len(cumulative_values) > 0 else 0.0
        spot_idx = int((dex_df['strike'] - spot_price).abs().argsort().iloc[0])
        remaining_pressure = float(max_cumulative - cumulative_values[spot_idx])

        logging.info(f"\nRESULTADOS DEX:")
        logging.info(f"Cotação:        R$ {spot_price:.2f}")
        if expiration_info:
            logging.info(f"Vencimento:     {expiration_info['desc']}")
        logging.info(f"DEX Total:      {net_dex:,.0f}")
        logging.info(f"DEX Descoberto: {net_dex_descoberto:,.0f}")
        logging.info(f"Strikes:        {len(dex_df)} ({real_data_count} reais)")

        return {
            'symbol':              symbol,
            'spot_price':          spot_price,
            'pressure_levels':     pressure_levels,
            'net_dex':             net_dex,
            'net_dex_descoberto':  net_dex_descoberto,
            'strikes_analyzed':    len(dex_df),
            'expiration':          expiration_info,
            'plot_json':           plot_json,
            'single_charts':       single_charts,   # NOVO
            'chart_data':          dex_df.to_dict(orient='list'),  # NOVO
            'real_data_count':     real_data_count,
            'remaining_pressure':  remaining_pressure,
            'success':             True
        }


class DeltaService:
    def __init__(self):
        self.analyzer = DEXAnalyzer()

    def get_available_expirations(self, ticker):
        return self.analyzer.data_provider.expiration_manager.get_available_expirations_list(ticker)

    def analyze_delta_complete(self, ticker, expiration_code=None, days_back=60):
        try:
            result = self.analyzer.analyze(ticker, expiration_code)

            pressure_levels    = result.get('pressure_levels', {})
            net_dex_descoberto = result['net_dex_descoberto']

            dex_levels = {
                'total_dex':             result['net_dex'],
                'total_dex_descoberto':  net_dex_descoberto,
                'market_bias':           pressure_levels.get('market_bias', 'NEUTRAL'),
                'concentration_ratio':   pressure_levels.get('concentration_ratio', 0),
                'remaining_pressure':    result['remaining_pressure'],
            }

            api_result = {
                'ticker':        ticker.replace('.SA', ''),
                'spot_price':    result['spot_price'],
                'dex_levels':    dex_levels,
                'plot_json':     result['plot_json'],
                'single_charts': result['single_charts'],   # NOVO
                'chart_data':    result['chart_data'],       # NOVO
                'options_count': result['strikes_analyzed'],
                'data_quality': {
                    'expiration':          result['expiration']['desc'] if result['expiration'] else None,
                    'expiration_window':   result['expiration'].get('window', 'MENSAL') if result['expiration'] else None,
                    'real_data_count':     result['real_data_count'],
                },
                'success': True
            }

            return convert_to_json_serializable(api_result)

        except Exception as e:
            logging.error(f"Erro na análise DEX: {e}")
            raise
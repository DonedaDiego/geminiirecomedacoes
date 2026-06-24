"""
historical_service.py - Análise Histórica GEX COM DADOS DO BANCO POSTGRESQL
VERSÃO CORRIGIDA: Usa spot_price histórico de cada dia específico
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
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, (list, tuple)):
        return [convert_to_json_serializable(item) for item in obj]
    if isinstance(obj, dict):
        return {key: convert_to_json_serializable(value) for key, value in obj.items()}
    try:
        if pd.isna(obj):
            return None
    except Exception:
        pass
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        return float(obj)
    if isinstance(obj, (datetime, pd.Timestamp)):
        return obj.isoformat()
    if hasattr(obj, 'item'):
        return obj.item()
    if hasattr(obj, 'tolist'):
        return obj.tolist()
    return str(obj)


class LiquidityManager:
    def __init__(self):
        self.high_liquidity = {
            'BOVA11': 6, 'PETR4': 6, 'VALE3': 6, 'BBAS3': 6,
            'B3SA3': 6,  'ITSA4': 6, 'BBDC4': 6, 'MGLU3': 6,
        }
        self.medium_liquidity = {
            'ITUB4': 9, 'ABEV3': 9, 'WEGE3': 9, 'RENT3': 9,
            'AXIA3': 9, 'PRIO3': 9, 'SUZB3': 9, 'EMBJ3': 9,
            'RADL3': 9, 'BRAV3': 9,
        }
        self.low_liquidity_range = 13

    def get_flip_range(self, symbol):
        s = symbol.replace('.SA', '').upper()
        if s in self.high_liquidity:
            return self.high_liquidity[s]
        if s in self.medium_liquidity:
            return self.medium_liquidity[s]
        return self.low_liquidity_range

    def get_liquidity_info(self, symbol):
        s = symbol.replace('.SA', '').upper()
        if s in self.high_liquidity:
            return {'range': self.high_liquidity[s], 'category': 'ALTA'}
        if s in self.medium_liquidity:
            return {'range': self.medium_liquidity[s], 'category': 'MEDIA'}
        return {'range': self.low_liquidity_range, 'category': 'BAIXA'}


class HistoricalDataProvider:
    def __init__(self):
        self.token = os.getenv('OPLAB_TOKEN', 'seu_token_aqui')
        self.oplab_url = "https://api.oplab.com.br/v3"
        self.headers   = {'Access-Token': self.token, 'Content-Type': 'application/json'}

        # ── CORREÇÃO: atributo de instância (self.) em vez de variável local ──
        self.AVAILABLE_EXPIRATIONS = {
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
                DB_PORT = '5432'
            DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

        logging.info("Conectando ao banco PostgreSQL (Historical)...")
        try:
            self.db_engine = create_engine(DATABASE_URL)
            with self.db_engine.connect() as conn:
                count = conn.execute(text("SELECT COUNT(*) FROM opcoes_b3")).scalar()
                logging.info(f"Conexão OK (Historical) - {count:,} registros")
        except Exception as e:
            logging.error(f"Erro ao conectar (Historical): {e}")
            raise

    # ── helpers de banco ─────────────────────────────────────────────────────

    def get_business_days(self, days_back=5):
        try:
            with self.db_engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT DISTINCT data_referencia FROM opcoes_b3
                    ORDER BY data_referencia DESC LIMIT :limit
                """), {'limit': days_back}).fetchall()
            if not rows:
                return []
            dates = []
            for row in rows:
                dr = row[0]
                dates.append(dr if isinstance(dr, datetime) else datetime.combine(dr, datetime.min.time()))
            dates_sorted = sorted(dates)
            logging.info(f"Últimas {len(dates_sorted)} datas_referencia do banco")
            return dates_sorted
        except Exception as e:
            logging.error(f"Erro ao buscar datas do banco: {e}")
            return []

    def get_spot_price(self, symbol):
        try:
            url = f"{self.oplab_url}/market/instruments/{symbol}"
            r = requests.get(url, headers=self.headers, timeout=10)
            if r.status_code == 200:
                d = r.json()
                if d and 'close' in d:
                    return float(d['close'])
            ticker_yf = f"{symbol}.SA" if not symbol.endswith('.SA') else symbol
            hist = yf.Ticker(ticker_yf).history(period='1d')
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
            return None
        except Exception as e:
            logging.error(f"Erro cotação: {e}")
            return None

    def get_historical_spot_price(self, symbol, target_date):
        try:
            ticker_yf = f"{symbol}.SA" if not symbol.endswith('.SA') else symbol
            date_str  = target_date.strftime('%Y-%m-%d')
            next_day  = (target_date + timedelta(days=3)).strftime('%Y-%m-%d')
            hist      = yf.Ticker(ticker_yf).history(start=date_str, end=next_day)
            if not hist.empty:
                filtered = hist[hist.index.date >= target_date.date()]
                if not filtered.empty:
                    price = float(filtered['Close'].iloc[0])
                    logging.info(f"Spot histórico {date_str}: R$ {price:.2f}")
                    return price
            # fallback Oplab
            sym   = symbol.replace('.SA', '')
            url   = f"{self.oplab_url}/market/historical/{sym}/{(target_date-timedelta(days=1)).strftime('%Y-%m-%d')}/{(target_date+timedelta(days=1)).strftime('%Y-%m-%d')}"
            r = requests.get(url, headers=self.headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data:
                    price = float(data[-1].get('close', 0))
                    if price > 0:
                        return price
            logging.error(f"Sem spot histórico para {date_str}")
            return None
        except Exception as e:
            logging.error(f"Erro spot histórico {target_date}: {e}")
            return None

    def get_oplab_historical_data(self, symbol, target_date=None):
        try:
            sym       = symbol.replace('.SA', '')
            to_date   = datetime.now().strftime('%Y-%m-%d')
            from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            url       = f"{self.oplab_url}/market/historical/options/{sym}/{from_date}/{to_date}"
            r = requests.get(url, headers=self.headers, timeout=15)
            if r.status_code != 200:
                return pd.DataFrame()
            data = r.json()
            if not data:
                return pd.DataFrame()
            df = pd.DataFrame(data)
            df['time'] = pd.to_datetime(df['time'])
            if target_date:
                tgt = target_date.date() if isinstance(target_date, datetime) else target_date
                df = df[df['time'].dt.date == tgt].copy()
                if df.empty:
                    return pd.DataFrame()
            else:
                latest = df['time'].max().date()
                df = df[df['time'].dt.date == latest].copy()
            valid = df[
                (df['gamma'] > 0) & (df['premium'] > 0) & (df['strike'] > 0) &
                (df['days_to_maturity'] > 0) & (df['days_to_maturity'] <= 180)
            ].copy()
            logging.info(f"Oplab válidos: {len(valid)} opções")
            return valid
        except Exception as e:
            logging.error(f"Erro Oplab: {e}")
            return pd.DataFrame()

    def get_floqui_historical(self, ticker, vencimento, dt_referencia):
        try:
            ticker_clean = ticker.replace('.SA', '')
            exp_date     = datetime.strptime(vencimento, '%Y%m%d')
            query = text("""
                SELECT preco_exercicio, tipo_opcao,
                       SUM(qtd_total) AS qtd_total, SUM(qtd_descoberto) AS qtd_descoberto,
                       SUM(qtd_trava) AS qtd_trava, SUM(qtd_coberto) AS qtd_coberto
                FROM opcoes_b3
                WHERE ticker = :symbol AND vencimento = :vencimento AND data_referencia = :data_ref
                GROUP BY preco_exercicio, tipo_opcao ORDER BY preco_exercicio
            """)
            with self.db_engine.connect() as conn:
                rows = conn.execute(query, {
                    'symbol': ticker_clean, 'vencimento': exp_date, 'data_ref': dt_referencia
                }).fetchall()
            if not rows:
                return {}
            oi_breakdown = {}
            for row in rows:
                strike      = float(row[0])
                option_type = str(row[1]).upper()
                oi_total    = int(row[2])
                oi_desc     = int(row[3])
                if strike > 0 and oi_total > 0:
                    key = f"{strike}_{option_type}"
                    oi_breakdown[key] = {
                        'strike': strike, 'type': option_type,
                        'total': oi_total, 'descoberto': oi_desc,
                        'travado': int(row[4]), 'coberto': int(row[5])
                    }
            logging.info(f"Banco VENC={vencimento} DATA={dt_referencia.strftime('%Y-%m-%d')}: {len(oi_breakdown)} strikes")
            return oi_breakdown
        except Exception as e:
            logging.error(f"Erro banco VENC={vencimento}: {e}")
            return {}

    def get_available_expirations(self, ticker):
        ticker_clean = ticker.replace('.SA', '')
        expirations  = []
        today        = datetime.now().date()
        try:
            with self.db_engine.connect() as conn:
                ultima_data = conn.execute(
                    text("SELECT MAX(data_referencia) FROM opcoes_b3 WHERE ticker = :t"),
                    {'t': ticker_clean}
                ).scalar()
            if not ultima_data:
                logging.warning(f"Nenhuma data_referencia para {ticker_clean}")
                return expirations

            with self.db_engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT DISTINCT vencimento FROM opcoes_b3
                    WHERE ticker = :t AND data_referencia = :dr
                """), {'t': ticker_clean, 'dr': ultima_data}).fetchall()

            venc_no_banco = set()
            for row in rows:
                v = row[0]
                if hasattr(v, 'date'):
                    v = v.date()
                venc_no_banco.add(v.strftime('%Y%m%d') if hasattr(v, 'strftime') else str(v).replace('-', ''))

            logging.info(f"Banco tem {len(venc_no_banco)} vencimentos para {ticker_clean}")

            # usa self.AVAILABLE_EXPIRATIONS — corrigido
            for code, meta in self.AVAILABLE_EXPIRATIONS.items():
                if meta["date"].date() < today:
                    continue
                available  = code in venc_no_banco
                days       = (meta["date"].date() - today).days
                window     = "SEMANAL" if "- W" in meta["desc"] else "MENSAL"
                data_count = 0
                if available:
                    with self.db_engine.connect() as conn:
                        data_count = conn.execute(text("""
                            SELECT COUNT(*) FROM opcoes_b3
                            WHERE ticker = :t AND vencimento = :v AND data_referencia = :dr
                        """), {'t': ticker_clean, 'v': meta["date"].date(), 'dr': ultima_data}).scalar() or 0
                expirations.append({
                    'code': code, 'desc': meta["desc"],
                    'days': days, 'data_count': data_count,
                    'available': available, 'window': window,
                })

            total_avail = sum(1 for e in expirations if e['available'])
            logging.info(f"Vencimentos {ticker_clean}: {len(expirations)} no dict, {total_avail} com dados")
        except Exception as e:
            logging.error(f"Erro ao buscar vencimentos históricos: {e}")
            import traceback; logging.error(traceback.format_exc())
        return expirations


class HistoricalAnalyzer:
    def __init__(self):
        self.data_provider    = HistoricalDataProvider()
        self.liquidity_manager = LiquidityManager()

    def calculate_gex(self, oplab_df, oi_breakdown, spot_price):
        if oplab_df.empty:
            return pd.DataFrame()
        price_range   = spot_price * 0.20
        valid_options = oplab_df[
            (oplab_df['strike'] >= spot_price - price_range) &
            (oplab_df['strike'] <= spot_price + price_range)
        ].copy()
        if valid_options.empty:
            return pd.DataFrame()
        gex_data = []
        for strike in valid_options['strike'].unique():
            strike_opts = valid_options[valid_options['strike'] == strike]
            calls = strike_opts[strike_opts['type'] == 'CALL']
            puts  = strike_opts[strike_opts['type'] == 'PUT']
            call_data = put_data = None
            has_real_call = has_real_put = False
            if len(calls) > 0:
                ck = f"{float(strike)}_CALL"
                if ck in oi_breakdown:
                    call_data = oi_breakdown[ck]; has_real_call = True
            if len(puts) > 0:
                pk = f"{float(strike)}_PUT"
                if pk in oi_breakdown:
                    put_data = oi_breakdown[pk]; has_real_put = True
            if not (has_real_call or has_real_put):
                continue
            call_gex = call_gex_desc = 0.0
            if call_data and len(calls) > 0:
                ag = float(calls['gamma'].mean())
                call_gex      = ag * call_data['total']      * spot_price * 100
                call_gex_desc = ag * call_data['descoberto'] * spot_price * 100
            put_gex = put_gex_desc = 0.0
            if put_data and len(puts) > 0:
                ag = float(puts['gamma'].mean())
                put_gex      = -(ag * put_data['total']      * spot_price * 100)
                put_gex_desc = -(ag * put_data['descoberto'] * spot_price * 100)
            gex_data.append({
                'strike':                float(strike),
                'call_gex':              float(call_gex),
                'put_gex':               float(put_gex),
                'total_gex':             float(call_gex + put_gex),
                'total_gex_descoberto':  float(call_gex_desc + put_gex_desc),
                'call_oi_total':         int(call_data['total']      if call_data else 0),
                'put_oi_total':          int(put_data['total']       if put_data  else 0),
                'call_oi_descoberto':    int(call_data['descoberto'] if call_data else 0),
                'put_oi_descoberto':     int(put_data['descoberto']  if put_data  else 0),
                'has_real_data':         True
            })
        if not gex_data:
            return pd.DataFrame()
        return pd.DataFrame(gex_data).sort_values('strike')

    def find_gamma_flip(self, gex_df, spot_price, symbol):
        if gex_df.empty or len(gex_df) < 2:
            return None
        max_distance = spot_price * (self.liquidity_manager.get_flip_range(symbol) / 100)
        valid_df = gex_df[
            (gex_df['strike'] >= spot_price - max_distance) &
            (gex_df['strike'] <= spot_price + max_distance)
        ].sort_values('strike').reset_index(drop=True)
        if valid_df.empty:
            return None
        spot_idx  = int((valid_df['strike'] - spot_price).abs().argsort().iloc[0])
        spot_gex  = valid_df.iloc[spot_idx]['total_gex_descoberto']
        spot_regime = "SHORT_GAMMA" if spot_gex < -1000 else ("LONG_GAMMA" if spot_gex > 1000 else "NEUTRAL")

        def search_flips(df):
            candidates = []
            for i in range(len(df) - 1):
                cg = df.iloc[i]['total_gex_descoberto']
                ng = df.iloc[i+1]['total_gex_descoberto']
                if (cg > 0 and ng < 0) or (cg < 0 and ng > 0):
                    cs = df.iloc[i]['strike']
                    ns = df.iloc[i+1]['strike']
                    denom = abs(cg) + abs(ng)
                    flip  = cs + (ns - cs) * abs(cg) / denom if denom else (cs + ns) / 2
                    pos   = "ACIMA" if flip > spot_price else "ABAIXO"
                    candidates.append({'strike': flip, 'distance': abs(flip - spot_price), 'position': pos})
            return candidates

        candidates = search_flips(valid_df[valid_df['has_real_data'] == True])
        if not candidates:
            candidates = search_flips(valid_df)
        if not candidates:
            return None
        if spot_regime == "SHORT_GAMMA":
            candidates = [c for c in candidates if c['position'] == "ACIMA"] or candidates
        elif spot_regime == "LONG_GAMMA":
            candidates = [c for c in candidates if c['position'] == "ABAIXO"] or candidates
        candidates.sort(key=lambda x: x['distance'])
        return float(candidates[0]['strike'])

    def identify_walls(self, gex_df, spot_price):
        if gex_df.empty:
            return []
        walls = []
        calls = gex_df[gex_df['call_gex'] > 0]
        if not calls.empty:
            row = calls.loc[calls['call_gex'].idxmax()]
            walls.append({'strike': float(row['strike']), 'type': 'Support',
                          'distance_pct': float(abs(row['strike'] - spot_price) / spot_price * 100)})
        puts = gex_df[gex_df['put_gex'] < 0]
        if not puts.empty:
            row = puts.loc[puts['put_gex'].idxmin()]
            walls.append({'strike': float(row['strike']), 'type': 'Resistance',
                          'distance_pct': float(abs(row['strike'] - spot_price) / spot_price * 100)})
        return walls

    def create_6_charts(self, gex_df, spot_price, symbol, flip_strike, expiration_desc, analysis_date):
        if gex_df.empty:
            return None
        gex_df = gex_df.sort_values('strike').reset_index(drop=True)
        subplot_titles = [
            '<b style="color:#ffffff;">Total GEX</b><br><span style="font-size:12px;color:#888;">Exposição gamma total</span>',
            '<b style="color:#ffffff;">GEX Descoberto</b><br><span style="font-size:12px;color:#888;">Posições descobertas</span>',
            '<b style="color:#ffffff;">Regime por Strike</b><br><span style="font-size:12px;color:#888;">Long vs Short gamma</span>',
            '<b style="color:#ffffff;">Calls vs Puts</b><br><span style="font-size:12px;color:#888;">Sentimento direcional</span>',
            '<b style="color:#ffffff;">GEX Cumulativo</b><br><span style="font-size:12px;color:#888;">Fluxo de pressão</span>',
            '<b style="color:#ffffff;">Open Interest</b><br><span style="font-size:12px;color:#888;">Volume contratos</span>'
        ]
        fig = make_subplots(rows=3, cols=2, subplot_titles=subplot_titles,
                            vertical_spacing=0.08, horizontal_spacing=0.08)
        strikes   = [float(x) for x in gex_df['strike'].tolist()]
        total_gex = [float(x) for x in gex_df['total_gex'].tolist()]
        desc      = [float(x) for x in gex_df['total_gex_descoberto'].tolist()]
        call_gex  = [float(x) for x in gex_df['call_gex'].tolist()]
        put_gex   = [float(x) for x in gex_df['put_gex'].tolist()]
        call_oi   = [int(x)   for x in gex_df['call_oi_total'].tolist()]
        put_oi    = [int(x)   for x in gex_df['put_oi_total'].tolist()]

        fig.add_trace(go.Bar(x=strikes, y=total_gex,
                             marker_color=['#ef4444' if x < 0 else '#22c55e' for x in total_gex],
                             showlegend=False), row=1, col=1)
        fig.add_trace(go.Bar(x=strikes, y=desc,
                             marker_color=['#ef4444' if x < 0 else '#22c55e' for x in desc],
                             showlegend=False), row=1, col=2)
        fig.add_trace(go.Bar(x=strikes, y=[abs(x) for x in desc],
                             marker_color=['#22c55e' if x > 1000 else '#ef4444' if x < -1000 else '#6b7280' for x in desc],
                             showlegend=False), row=2, col=1)
        fig.add_trace(go.Bar(x=strikes, y=call_gex, marker_color='#22c55e', showlegend=False), row=2, col=2)
        fig.add_trace(go.Bar(x=strikes, y=put_gex,  marker_color='#ef4444', showlegend=False), row=2, col=2)
        cumulative = list(np.cumsum(total_gex))
        fig.add_trace(go.Scatter(x=strikes, y=cumulative, mode='lines+markers',
                                 line=dict(color='#06b6d4', width=3),
                                 marker=dict(color='#06b6d4', size=6),
                                 showlegend=False), row=3, col=1)
        fig.add_trace(go.Bar(x=strikes, y=[c+p for c,p in zip(call_oi,put_oi)],
                             marker_color='#a855f7', showlegend=False), row=3, col=2)

        for row in range(1, 4):
            for col in range(1, 3):
                fig.add_vline(x=spot_price, line=dict(color='#fbbf24', width=3, dash='dash'), row=row, col=col)
                if flip_strike:
                    fig.add_vline(x=flip_strike, line=dict(color='#f97316', width=3, dash='dot'), row=row, col=col)
                fig.add_hline(y=0, line=dict(color='rgba(255,255,255,0.3)', width=1), row=row, col=col)

        fig.update_layout(
            title={'text': f"{expiration_desc} - {analysis_date}", 'x': 0.5, 'xanchor': 'center',
                   'font': {'size': 20, 'color': '#ffffff', 'family': 'Inter, sans-serif'}},
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#ffffff', family='Inter, sans-serif'),
            height=1600, showlegend=False, margin=dict(l=50, r=50, t=100, b=50)
        )
        fig.update_annotations(font=dict(color='#ffffff', family='Inter, sans-serif', size=21))
        fig.update_xaxes(gridcolor='rgba(255,255,255,0.1)', color='#ffffff', showgrid=True, zeroline=False)
        fig.update_yaxes(gridcolor='rgba(255,255,255,0.1)', color='#ffffff', showgrid=True, zeroline=False)
        return fig.to_json()

    def calculate_historical_insights(self, data_by_date, spot_prices_by_date):
        if not data_by_date or len(data_by_date) < 2:
            return {}
        dates = sorted(data_by_date.keys())

        flip_evolution = []
        regime_changes = []
        for i, date in enumerate(dates):
            d = data_by_date[date]
            flip_evolution.append({
                'date': date,
                'flip_strike': d.get('flip_strike'),
                'spot_price': spot_prices_by_date.get(date),
                'regime': d['regime']
            })
            if i > 0 and data_by_date[dates[i-1]]['regime'] != d['regime']:
                regime_changes.append({'date': date, 'from': data_by_date[dates[i-1]]['regime'], 'to': d['regime']})

        valid_flips   = [f for f in flip_evolution if f['flip_strike'] is not None]
        flip_movement = None
        if len(valid_flips) >= 2:
            ff, lf = valid_flips[0]['flip_strike'], valid_flips[-1]['flip_strike']
            flip_movement = {
                'first_date': valid_flips[0]['date'],  'last_date': valid_flips[-1]['date'],
                'first_flip': ff, 'last_flip': lf,
                'change_pct': (lf - ff) / ff * 100,
                'direction': 'UP' if lf > ff else 'DOWN',
                'change_abs': lf - ff
            }

        gex_trend = [{'date': d, 'net_gex_descoberto': data_by_date[d]['net_gex_descoberto']} for d in dates]
        gex_change = None
        if len(gex_trend) >= 2:
            fg, lg = gex_trend[0]['net_gex_descoberto'], gex_trend[-1]['net_gex_descoberto']
            gex_change = {
                'first_date': dates[0], 'last_date': dates[-1],
                'first_gex': fg, 'last_gex': lg, 'change_abs': lg - fg,
                'trend': 'INCREASING_LONG' if lg > fg and lg > 0 else
                         'INCREASING_SHORT' if lg < fg and lg < 0 else 'DECREASING'
            }

        most_impacted = self._identify_most_impacted_strikes(data_by_date, spot_prices_by_date, dates)

        def count_consecutive(data, dates):
            current = data[dates[-1]]['regime']
            count = 1
            for i in range(len(dates) - 2, -1, -1):
                if data[dates[i]]['regime'] == current:
                    count += 1
                else:
                    break
            return count

        return {
            'period': {'start': dates[0], 'end': dates[-1], 'days': len(dates)},
            'flip_evolution': flip_evolution,
            'flip_movement': flip_movement,
            'regime_changes': regime_changes,
            'regime_stability': len(regime_changes) == 0,
            'gex_trend': gex_trend,
            'gex_change': gex_change,
            'current_regime': data_by_date[dates[-1]]['regime'],
            'days_in_current_regime': count_consecutive(data_by_date, dates),
            'most_impacted_strikes': most_impacted
        }

    def _identify_most_impacted_strikes(self, data_by_date, spot_prices_by_date, dates):
        if len(dates) < 2:
            return []
        avg_spot = sum(spot_prices_by_date.values()) / len(spot_prices_by_date)
        history  = {}
        for date in dates:
            for rec in data_by_date[date].get('gex_df_records', []):
                s = float(rec['strike'])
                history.setdefault(s, []).append({'date': date, 'gex': float(rec['total_gex_descoberto'])})
        impacts = []
        for strike, h in history.items():
            if len(h) < 2:
                continue
            change = h[-1]['gex'] - h[0]['gex']
            if abs(change) < 5000:
                continue
            impacts.append({
                'strike': strike,
                'distance_from_spot_pct': abs(strike - avg_spot) / avg_spot * 100,
                'first_gex': h[0]['gex'], 'last_gex': h[-1]['gex'],
                'change': change, 'change_abs': abs(change),
                'direction': 'MORE_LONG' if change > 0 else 'MORE_SHORT',
                'dates_tracked': len(h)
            })
        impacts.sort(key=lambda x: x['change_abs'], reverse=True)
        return impacts[:5]

    def analyze_historical(self, ticker, vencimento, days_back=6):
        logging.info(f"INICIANDO ANÁLISE HISTÓRICA - {ticker}")
        business_dates    = self.data_provider.get_business_days(days_back)
        data_by_date      = {}
        spot_prices_by_date = {}
        available_dates   = []
        expirations       = self.data_provider.get_available_expirations(ticker)
        expiration_desc   = next((e['desc'] for e in expirations if e['code'] == vencimento), vencimento)

        for date_obj in business_dates:
            date_str = date_obj.strftime('%Y-%m-%d')
            logging.info(f"Processando {date_str}...")

            spot_price = self.data_provider.get_historical_spot_price(ticker, date_obj)
            if not spot_price:
                continue
            spot_prices_by_date[date_str] = spot_price

            oplab_df = self.data_provider.get_oplab_historical_data(ticker, target_date=date_obj)
            if oplab_df.empty:
                continue

            oi_breakdown = self.data_provider.get_floqui_historical(ticker, vencimento, date_obj)
            if not oi_breakdown:
                for exp in expirations:
                    if exp['code'] != vencimento and exp['available']:
                        oi_breakdown = self.data_provider.get_floqui_historical(ticker, exp['code'], date_obj)
                        if oi_breakdown:
                            vencimento      = exp['code']
                            expiration_desc = exp['desc']
                            break
            if not oi_breakdown:
                continue

            gex_df = self.calculate_gex(oplab_df, oi_breakdown, spot_price)
            if gex_df.empty:
                continue

            flip_strike = self.find_gamma_flip(gex_df, spot_price, ticker)
            walls       = self.identify_walls(gex_df, spot_price)
            net_gex            = float(np.cumsum(gex_df['total_gex'].values)[-1])
            net_gex_descoberto = float(np.cumsum(gex_df['total_gex_descoberto'].values)[-1])
            regime = ('Long Gamma' if spot_price > flip_strike else 'Short Gamma') if flip_strike \
                     else ('Long Gamma' if net_gex_descoberto > 0 else 'Short Gamma')

            plot_json = self.create_6_charts(
                gex_df, spot_price, ticker, flip_strike,
                expiration_desc, date_obj.strftime('%d/%m/%Y')
            )

            data_by_date[date_str] = {
                'spot_price': spot_price,
                'flip_strike': flip_strike,
                'net_gex': net_gex,
                'net_gex_descoberto': net_gex_descoberto,
                'regime': regime,
                'plot_json': plot_json,
                'walls': walls,
                'strikes_count': len(gex_df),
                'real_data_count': int(gex_df['has_real_data'].sum()),
                'gex_df_records': gex_df.to_dict('records')
            }
            available_dates.append(date_str)
            logging.info(f"{date_str}: Spot={spot_price:.2f}, Flip={flip_strike}, {regime}")

        if len(available_dates) < 2:
            raise ValueError(f"Dados insuficientes: {len(available_dates)} dia(s). Mínimo: 2")

        try:
            insights = self.calculate_historical_insights(data_by_date, spot_prices_by_date)
        except Exception as e:
            logging.error(f"Erro insights: {e}")
            insights = {'error': str(e), 'period': {
                'start': available_dates[0], 'end': available_dates[-1], 'days': len(available_dates)
            }}

        return {
            'ticker': ticker,
            'vencimento': vencimento,
            'expiration_desc': expiration_desc,
            'spot_price': spot_prices_by_date[available_dates[-1]],
            'available_dates': available_dates,
            'data_by_date': data_by_date,
            'spot_prices_by_date': spot_prices_by_date,
            'insights': insights,
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
                'ticker':              ticker.replace('.SA', ''),
                'vencimento':          vencimento,
                'expiration_desc':     result['expiration_desc'],
                'spot_price':          result['spot_price'],
                'available_dates':     result['available_dates'],
                'data_by_date':        result['data_by_date'],
                'spot_prices_by_date': result['spot_prices_by_date'],
                'insights':            result['insights'],
                'success':             True
            }
            return convert_to_json_serializable(api_result)
        except Exception as e:
            logging.error(f"Erro na análise histórica: {e}", exc_info=True)
            raise
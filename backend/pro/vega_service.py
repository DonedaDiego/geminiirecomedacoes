"""
vega_service.py - VEX Analysis COM DADOS DO BANCO POSTGRESQL
ATUALIZADO: VI Refinada focada em ATM ± 2 strikes + single_charts por modo
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
            "20260605": {"date": datetime(2026, 6, 5),  "desc": "05 Jun 26 - W1"},
            "20260612": {"date": datetime(2026, 6, 12), "desc": "12 Jun 26 - W2"},
            "20260619": {"date": datetime(2026, 6, 19), "desc": "19 Jun 26 - M"},
            "20260626": {"date": datetime(2026, 6, 26), "desc": "26 Jun 26 - W4"},

            "20260703": {"date": datetime(2026, 7, 3),  "desc": "03 Jul 26 - W1"},
            "20260710": {"date": datetime(2026, 7, 10), "desc": "10 Jul 26 - W2"},
            "20260717": {"date": datetime(2026, 7, 17), "desc": "17 Jul 26 - M"},
            "20260724": {"date": datetime(2026, 7, 24), "desc": "24 Jul 26 - W4"},
            "20260731": {"date": datetime(2026, 7, 31), "desc": "31 Jul 26 - W5"},

            "20260807": {"date": datetime(2026, 8, 7),  "desc": "07 Ago 26 - W1"},
            "20260814": {"date": datetime(2026, 8, 14), "desc": "14 Ago 26 - W2"},
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
        self.headers   = {'Access-Token': self.token, 'Content-Type': 'application/json'}

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

        try:
            self.db_engine = create_engine(DATABASE_URL)
            with self.db_engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM opcoes_b3"))
                count = result.fetchone()[0]
                logging.info(f"Conexão OK (VEX) - {count:,} registros na opcoes_b3")
        except Exception as e:
            logging.error(f"Erro ao conectar (VEX): {e}")
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
            hist  = stock.history(period='1d')
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
                return pd.DataFrame()
            data = response.json()
            if not data:
                return pd.DataFrame()
            df = pd.DataFrame(data)
            df['time'] = pd.to_datetime(df['time'])
            latest_date = df['time'].max().date()
            latest_data = df[df['time'].dt.date == latest_date].copy()
            valid_data  = latest_data[
                (latest_data['vega'] > 0) &
                (latest_data['volatility'] > 0) &
                (latest_data['premium'] > 0) &
                (latest_data['strike'] > 0) &
                (latest_data['days_to_maturity'] > 0) &
                (latest_data['days_to_maturity'] <= 180)
            ].copy()
            return valid_data
        except Exception as e:
            logging.error(f"Erro dados Oplab: {e}")
            return pd.DataFrame()

    def get_floqui_oi_breakdown(self, symbol, expiration_code=None):
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
                return {}, None

            exp_date = datetime.strptime(expiration['code'], '%Y%m%d')
            query = text("""
                SELECT preco_exercicio, tipo_opcao,
                       SUM(qtd_total) AS qtd_total, SUM(qtd_descoberto) AS qtd_descoberto,
                       SUM(qtd_trava) AS qtd_trava, SUM(qtd_coberto) AS qtd_coberto
                FROM opcoes_b3
                WHERE ticker = :symbol AND vencimento = :vencimento
                AND data_referencia = (SELECT MAX(data_referencia) FROM opcoes_b3 WHERE ticker = :symbol)
                GROUP BY preco_exercicio, tipo_opcao ORDER BY preco_exercicio
            """)
            df = pd.read_sql(query, self.db_engine, params={'symbol': symbol, 'vencimento': exp_date})
            if df.empty:
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
                        'strike': strike, 'type': option_type,
                        'total': oi_total, 'descoberto': oi_desc,
                        'travado': int(row['qtd_trava']), 'coberto': int(row['qtd_coberto'])
                    }
            logging.info(f"OI breakdown VEX: {len(oi_breakdown)} strikes (vencimento: {expiration['desc']})")
            return oi_breakdown, expiration
        except Exception as e:
            logging.error(f"Erro Floqui: {e}")
            return {}, None

    def get_historical_iv_context(self, symbol, days=10):
        try:
            to_date   = datetime.now().strftime('%Y-%m-%d')
            from_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            url = f"{self.oplab_url}/market/historical/options/{symbol}/{from_date}/{to_date}"
            response = requests.get(url, headers=self.headers, timeout=15)
            if response.status_code != 200:
                return pd.DataFrame()
            data = response.json()
            if not data:
                return pd.DataFrame()
            df = pd.DataFrame(data)
            df['time'] = pd.to_datetime(df['time'])
            valid_data = df[
                (df['volatility'] > 0) & (df['volatility'] < 300) &
                (df['premium'] > 0) & (df['strike'] > 0)
            ].copy()
            if valid_data.empty:
                return pd.DataFrame()
            valid_data['date'] = valid_data['time'].dt.date
            daily_avg = valid_data.groupby(['date', 'strike'])['volatility'].mean().reset_index()
            daily_avg.rename(columns={'volatility': 'iv_daily_avg'}, inplace=True)
            return daily_avg.sort_values('date')
        except Exception as e:
            logging.error(f"Erro contexto IV: {e}")
            return pd.DataFrame()


class VEXCalculator:

    def calculate_vex_with_context(self, oplab_df, oi_breakdown, spot_price, historical_df=None):
        if oplab_df.empty:
            return pd.DataFrame()

        price_range   = spot_price * 0.25
        valid_options = oplab_df[
            (oplab_df['strike'] >= spot_price - price_range) &
            (oplab_df['strike'] <= spot_price + price_range)
        ].copy()
        if valid_options.empty:
            return pd.DataFrame()

        valid_options['distance_from_spot'] = abs(valid_options['strike'] - spot_price)
        atm_focused_strikes = valid_options.sort_values('distance_from_spot')['strike'].unique()[:5]
        atm_focused = valid_options[valid_options['strike'].isin(atm_focused_strikes)].copy()

        atm_calls = atm_focused[atm_focused['type'] == 'CALL']
        atm_puts  = atm_focused[atm_focused['type'] == 'PUT']

        global_call_iv = float(atm_calls['volatility'].mean()) if len(atm_calls) > 0 else 0
        global_put_iv  = float(atm_puts['volatility'].mean())  if len(atm_puts)  > 0 else 0

        if global_call_iv > 0 and global_put_iv > 0:
            call_oi_sum = sum([oi_breakdown.get(f"{s}_CALL", {}).get('total', 0) for s in atm_focused_strikes])
            put_oi_sum  = sum([oi_breakdown.get(f"{s}_PUT",  {}).get('total', 0) for s in atm_focused_strikes])
            total_oi    = call_oi_sum + put_oi_sum
            global_avg_iv = (global_call_iv * call_oi_sum + global_put_iv * put_oi_sum) / total_oi if total_oi > 0 else (global_call_iv + global_put_iv) / 2
        elif global_call_iv > 0:
            global_avg_iv = global_call_iv
        elif global_put_iv > 0:
            global_avg_iv = global_put_iv
        else:
            global_avg_iv = 0

        global_historical_iv = global_avg_iv
        if historical_df is not None and not historical_df.empty:
            atm_hist = historical_df[historical_df['strike'].isin(atm_focused_strikes)].copy()
            if not atm_hist.empty:
                col = 'iv_daily_avg' if 'iv_daily_avg' in atm_hist.columns else 'volatility'
                iv_vals = atm_hist[col].values
                iv_vals = iv_vals[(iv_vals > 0) & (iv_vals < 200)]
                if len(iv_vals) > 0:
                    global_historical_iv = float(np.mean(iv_vals))

        vex_data = []
        for strike in valid_options['strike'].unique():
            strike_options = valid_options[valid_options['strike'] == strike]
            calls = strike_options[strike_options['type'] == 'CALL']
            puts  = strike_options[strike_options['type'] == 'PUT']

            iv_context = self._calculate_iv_context(strike, historical_df) if historical_df is not None else {}

            call_data = put_data = None
            has_real_call = has_real_put = False

            if len(calls) > 0:
                call_key = f"{float(strike)}_CALL"
                if call_key in oi_breakdown:
                    call_data = oi_breakdown[call_key]; has_real_call = True

            if len(puts) > 0:
                put_key = f"{float(strike)}_PUT"
                if put_key in oi_breakdown:
                    put_data = oi_breakdown[put_key]; has_real_put = True

            if not (has_real_call or has_real_put):
                continue

            call_vex = call_vex_desc = call_iv = 0.0
            if call_data and len(calls) > 0:
                avg_vega = float(calls['vega'].mean())
                avg_iv   = float(calls['volatility'].mean())
                call_vex = avg_vega * call_data['total']      * 100
                call_vex_desc = avg_vega * call_data['descoberto'] * 100
                call_iv  = avg_iv

            put_vex = put_vex_desc = put_iv = 0.0
            if put_data and len(puts) > 0:
                avg_vega = float(puts['vega'].mean())
                avg_iv   = float(puts['volatility'].mean())
                put_vex  = avg_vega * put_data['total']       * 100
                put_vex_desc = avg_vega * put_data['descoberto']  * 100
                put_iv   = avg_iv

            avg_iv_strike = (
                (call_iv + put_iv) / 2 if call_iv > 0 and put_iv > 0
                else call_iv or put_iv
            )

            in_atm = strike in atm_focused_strikes
            refined_call_iv  = call_iv  if call_iv  > 0 else (global_call_iv if in_atm else 0.0)
            refined_put_iv   = put_iv   if put_iv   > 0 else (global_put_iv  if in_atm else 0.0)
            refined_avg_iv   = avg_iv_strike if avg_iv_strike > 0 else (global_avg_iv if in_atm else 0.0)

            vex_data.append({
                'strike':                float(strike),
                'call_vex':              float(call_vex),
                'put_vex':               float(put_vex),
                'total_vex':             float(call_vex + put_vex),
                'call_vex_descoberto':   float(call_vex_desc),
                'put_vex_descoberto':    float(put_vex_desc),
                'total_vex_descoberto':  float(call_vex_desc + put_vex_desc),
                'call_oi_total':         int(call_data['total']      if call_data else 0),
                'put_oi_total':          int(put_data['total']       if put_data  else 0),
                'call_oi_descoberto':    int(call_data['descoberto'] if call_data else 0),
                'put_oi_descoberto':     int(put_data['descoberto']  if put_data  else 0),
                'call_iv':               float(call_iv),
                'put_iv':                float(put_iv),
                'avg_iv':                float(avg_iv_strike),
                'refined_call_iv':       float(refined_call_iv),
                'refined_put_iv':        float(refined_put_iv),
                'refined_avg_iv':        float(refined_avg_iv),
                'iv_10d_avg':            float(iv_context.get('iv_10d_avg', avg_iv_strike)),
                'iv_10d_min':            float(iv_context.get('iv_10d_min', avg_iv_strike * 0.8)),
                'iv_10d_max':            float(iv_context.get('iv_10d_max', avg_iv_strike * 1.2)),
                'iv_percentile':         float(iv_context.get('iv_percentile', 50)),
                'iv_status':             iv_context.get('iv_status', 'NEUTRAL'),
                'has_real_data':         has_real_call or has_real_put,
                'global_avg_iv':         float(global_avg_iv),
                'global_historical_iv':  float(global_historical_iv)
            })

        return pd.DataFrame(vex_data).sort_values('strike')

    def _calculate_iv_context(self, strike, historical_df):
        if historical_df.empty:
            return {}
        strike_data = historical_df[
            (historical_df['strike'] >= strike - 1) &
            (historical_df['strike'] <= strike + 1)
        ].copy()
        if strike_data.empty:
            return {}
        col = 'iv_daily_avg' if 'iv_daily_avg' in strike_data.columns else 'volatility'
        iv_values = strike_data[col].values
        iv_values = iv_values[iv_values < 200]
        if len(iv_values) == 0:
            return {}
        iv_10d_avg    = float(np.mean(iv_values))
        current_iv    = float(iv_values[-1])
        iv_percentile = float(np.percentile(iv_values, 50))
        if current_iv > iv_10d_avg * 1.3:   iv_status = 'MUITO_ALTA'
        elif current_iv > iv_10d_avg * 1.1: iv_status = 'ALTA'
        elif current_iv < iv_10d_avg * 0.7: iv_status = 'MUITO_BAIXA'
        elif current_iv < iv_10d_avg * 0.9: iv_status = 'BAIXA'
        else:                                iv_status = 'NORMAL'
        return {
            'iv_10d_avg': iv_10d_avg,
            'iv_10d_min': float(np.min(iv_values)),
            'iv_10d_max': float(np.max(iv_values)),
            'iv_percentile': iv_percentile,
            'iv_status': iv_status
        }


class VolatilityRegimeDetector:

    def analyze_volatility_regime(self, vex_df, spot_price):
        if vex_df.empty:
            return None

        vex_df_copy = vex_df.copy()
        vex_df_copy['distance_from_spot'] = abs(vex_df_copy['strike'] - spot_price)
        atm_idx = vex_df_copy['distance_from_spot'].idxmin()

        current_iv    = float(vex_df_copy.loc[atm_idx, 'global_avg_iv'])
        atm_strike    = float(vex_df_copy.loc[atm_idx, 'strike'])

        atm_top5 = vex_df_copy.sort_values('distance_from_spot').head(5)
        hist_vals = atm_top5['iv_10d_avg'].values
        hist_vals = hist_vals[hist_vals > 0]
        historical_iv = float(np.mean(hist_vals)) if len(hist_vals) > 0 else current_iv

        total_vex            = float(vex_df_copy['total_vex'].sum())
        total_vex_descoberto = float(vex_df_copy['total_vex_descoberto'].sum())
        max_vex_strike       = float(vex_df_copy.loc[vex_df_copy['total_vex'].idxmax(), 'strike'])

        iv_diff_pp  = current_iv - historical_iv
        iv_diff_pct = ((current_iv - historical_iv) / historical_iv) * 100 if historical_iv > 0 else 0

        if iv_diff_pp > 0.5:
            iv_trend = 'ALTA'
            iv_trend_description = f'IV {iv_diff_pp:+.1f} p.p. acima da média 10D'
        elif iv_diff_pp < -0.5:
            iv_trend = 'BAIXA'
            iv_trend_description = f'IV {iv_diff_pp:.1f} p.p. abaixo da média 10D'
        else:
            iv_trend = 'ESTAVEL'
            iv_trend_description = 'IV dentro da faixa normal'

        volatility_risk = 'HIGH' if abs(iv_diff_pp) > 2 else 'LOW'
        if volatility_risk == 'HIGH':
            interpretation = (f'IV inflada (+{iv_diff_pp:.1f} p.p.) - Alto risco de compressão'
                              if iv_diff_pp > 0
                              else f'IV comprimida ({iv_diff_pp:.1f} p.p.) - Alto risco de explosão')
        else:
            interpretation = 'IV próxima da média histórica - Baixo risco de mudança brusca'

        return {
            'total_vex':             total_vex,
            'total_vex_descoberto':  total_vex_descoberto,
            'weighted_iv':           current_iv,
            'atm_strike':            atm_strike,
            'atm_iv':                current_iv,
            'atm_iv_10d_avg':        historical_iv,
            'iv_diff_pct':           float(iv_diff_pct),
            'iv_trend':              iv_trend,
            'iv_trend_description':  iv_trend_description,
            'max_vex_strike':        max_vex_strike,
            'volatility_risk':       volatility_risk,
            'interpretation':        interpretation
        }


class VEXAnalyzer:
    def __init__(self):
        self.data_provider = DataProvider()
        self.vex_calculator = VEXCalculator()
        self.vol_detector   = VolatilityRegimeDetector()

    # ─────────────────────────────────────────────────────────────────────────
    # Gráfico 6 painéis — mantido para compatibilidade
    # ─────────────────────────────────────────────────────────────────────────
    def create_6_charts(self, vex_df, spot_price, symbol, vol_zones=None, expiration_info=None):
        if vex_df.empty:
            return None

        title = expiration_info["desc"] if expiration_info else ""

        subplot_titles = [
            '<b style="color:#ffffff;">Total VEX</b><br><span style="font-size:12px;color:#888;">Sensibilidade total vega</span>',
            '<b style="color:#ffffff;">VEX Descoberto</b><br><span style="font-size:12px;color:#888;">Risco real volatilidade</span>',
            '<b style="color:#ffffff;">Volatilidade Implícita</b><br><span style="font-size:12px;color:#888;">IV refinada focada</span>',
            '<b style="color:#ffffff;">Calls vs Puts</b><br><span style="font-size:12px;color:#888;">VEX por tipo</span>',
            '<b style="color:#ffffff;">VEX / IV</b><br><span style="font-size:12px;color:#888;">Eficiência risco vol</span>',
            '<b style="color:#ffffff;">Concentração Risco</b><br><span style="font-size:12px;color:#888;">% risco por strike</span>'
        ]

        fig = make_subplots(rows=3, cols=2, subplot_titles=subplot_titles,
                            vertical_spacing=0.08, horizontal_spacing=0.08)

        strikes            = [float(x) for x in vex_df['strike'].tolist()]
        total_vex_values   = [float(x) for x in vex_df['total_vex'].tolist()]
        descoberto_values  = [float(x) for x in vex_df['total_vex_descoberto'].tolist()]
        call_vex_values    = [float(x) for x in vex_df['call_vex'].tolist()]
        put_vex_values     = [float(x) for x in vex_df['put_vex'].tolist()]
        refined_call_iv    = [float(x) for x in vex_df['refined_call_iv'].tolist()]
        refined_put_iv     = [float(x) for x in vex_df['refined_put_iv'].tolist()]
        refined_avg_iv     = [float(x) for x in vex_df['refined_avg_iv'].tolist()]
        iv_10d_avg         = [float(x) for x in vex_df['iv_10d_avg'].tolist()]
        iv_10d_min         = [float(x) for x in vex_df['iv_10d_min'].tolist()]
        iv_10d_max         = [float(x) for x in vex_df['iv_10d_max'].tolist()]

        fig.add_trace(go.Bar(x=strikes, y=total_vex_values,  marker_color='#9333ea', showlegend=False), row=1, col=1)
        fig.add_trace(go.Bar(x=strikes, y=descoberto_values, marker_color='#dc2626', showlegend=False), row=1, col=2)

        fig.add_trace(go.Scatter(x=strikes, y=iv_10d_max, fill=None, mode='lines',
                                 line=dict(color='rgba(0,0,0,0)'), showlegend=False, hoverinfo='skip'), row=2, col=1)
        fig.add_trace(go.Scatter(x=strikes, y=iv_10d_min, fill='tonexty',
                                 fillcolor='rgba(100,100,100,0.15)', mode='lines',
                                 line=dict(color='rgba(0,0,0,0)'), showlegend=False, hoverinfo='skip'), row=2, col=1)
        fig.add_trace(go.Scatter(x=strikes, y=refined_call_iv, mode='lines',
                                 line=dict(color='#22c55e', width=2), showlegend=False), row=2, col=1)
        fig.add_trace(go.Scatter(x=strikes, y=refined_put_iv,  mode='lines',
                                 line=dict(color='#ef4444', width=2), showlegend=False), row=2, col=1)
        fig.add_trace(go.Scatter(x=strikes, y=refined_avg_iv,  mode='lines',
                                 line=dict(color='#f97316', width=3), showlegend=False), row=2, col=1)
        fig.add_trace(go.Scatter(x=strikes, y=iv_10d_avg, mode='lines',
                                 line=dict(color='#06b6d4', width=2, dash='dot'), showlegend=False), row=2, col=1)

        fig.add_trace(go.Bar(x=strikes, y=call_vex_values, marker_color='#22c55e', showlegend=False), row=2, col=2)
        fig.add_trace(go.Bar(x=strikes, y=put_vex_values,  marker_color='#ef4444', showlegend=False), row=2, col=2)

        vex_per_iv = [total_vex_values[i] / refined_avg_iv[i] if refined_avg_iv[i] > 0 else 0
                      for i in range(len(total_vex_values))]
        fig.add_trace(go.Scatter(x=strikes, y=vex_per_iv, mode='lines+markers',
                                 line=dict(color='#06b6d4', width=3),
                                 marker=dict(color='#06b6d4', size=6), showlegend=False), row=3, col=1)

        total_abs = sum(abs(x) for x in total_vex_values)
        conc_pct  = [(abs(x) / total_abs * 100) if total_abs > 0 else 0 for x in total_vex_values]
        risk_col  = ['#ef4444' if x > 20 else '#f97316' if x > 10 else '#22c55e' for x in conc_pct]
        fig.add_trace(go.Bar(x=strikes, y=conc_pct, marker_color=risk_col, showlegend=False), row=3, col=2)

        for row in range(1, 4):
            for col in range(1, 3):
                fig.add_vline(x=spot_price, line=dict(color='#ffffff', width=2, dash='dash'), row=row, col=col)
                if vol_zones and vol_zones.get('max_vex_strike'):
                    fig.add_vline(x=vol_zones['max_vex_strike'], line=dict(color='#9333ea', width=2, dash='dot'), row=row, col=col)
                if not (row == 2 and col == 1):
                    fig.add_hline(y=0, line=dict(color='rgba(255,255,255,0.3)', width=1), row=row, col=col)

        fig.update_layout(
            title={'text': title, 'x': 0.5, 'xanchor': 'center',
                   'font': {'size': 20, 'color': '#ffffff', 'family': 'Inter, sans-serif'}},
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#ffffff', family='Inter, sans-serif'),
            height=1600, showlegend=False, margin=dict(l=50, r=50, t=100, b=50)
        )
        fig.update_annotations(font=dict(color='#ffffff', family='Inter, sans-serif', size=21))
        fig.update_xaxes(gridcolor='rgba(255,255,255,0.1)', color='#ffffff', showgrid=True, zeroline=False)
        fig.update_yaxes(gridcolor='rgba(255,255,255,0.1)', color='#ffffff', showgrid=True, zeroline=False)
        return fig.to_json()

    
    def create_single_chart(self, vex_df, spot_price, symbol,
                            vol_zones=None, expiration_info=None, mode='net'):
    
        if vex_df.empty:
            return None

        vex_df   = vex_df.sort_values('strike').reset_index(drop=True)
        strikes  = [float(x) for x in vex_df['strike'].tolist()]
        total_vex   = [float(x) for x in vex_df['total_vex'].tolist()]
        descoberto  = [float(x) for x in vex_df['total_vex_descoberto'].tolist()]
        call_vex    = [float(x) for x in vex_df['call_vex'].tolist()]
        put_vex     = [float(x) for x in vex_df['put_vex'].tolist()]
        call_oi     = [int(x)   for x in vex_df['call_oi_total'].tolist()]
        put_oi      = [int(x)   for x in vex_df['put_oi_total'].tolist()]

        mode_labels = {
            'net':        'Net Exposure',
            'descoberto': 'VEX Descoberto',
            'call_put':   'Call / Put Exposure',
            'oi':         'Open Interest',
        }
        title_mode = mode_labels.get(mode, 'Net Exposure')
        exp_desc   = expiration_info["desc"] if expiration_info else ""

        fig = go.Figure()

        if mode == 'net':
            fig.add_trace(go.Bar(
                x=strikes, y=total_vex,
                marker_color='#9333ea', marker_line_width=0,
                showlegend=False,
                hovertemplate='Strike: R$ %{x:.2f}<br>VEX: %{y:,.0f}<extra></extra>'
            ))

        elif mode == 'descoberto':
            fig.add_trace(go.Bar(
                x=strikes, y=descoberto,
                marker_color='#dc2626', marker_line_width=0,
                showlegend=False,
                hovertemplate='Strike: R$ %{x:.2f}<br>VEX Desc: %{y:,.0f}<extra></extra>'
            ))

        elif mode == 'call_put':
            fig.add_trace(go.Bar(
                x=strikes, y=call_vex, name='Calls',
                marker_color='#22c55e', marker_line_width=0,
                hovertemplate='Strike: R$ %{x:.2f}<br>Call VEX: %{y:,.0f}<extra></extra>'
            ))
            fig.add_trace(go.Bar(
                x=strikes, y=put_vex, name='Puts',
                marker_color='#ef4444', marker_line_width=0,
                hovertemplate='Strike: R$ %{x:.2f}<br>Put VEX: %{y:,.0f}<extra></extra>'
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

        fig.add_vline(
            x=spot_price,
            line=dict(color='#ffffff', width=2, dash='dash'),
            annotation=dict(
                text='SPOT', font=dict(color='#ffffff', size=11),
                yref='paper', y=1.0, yanchor='bottom',
                bgcolor='rgba(0,0,0,0.6)', borderpad=3
            )
        )
        if vol_zones and vol_zones.get('max_vex_strike'):
            fig.add_vline(
                x=vol_zones['max_vex_strike'],
                line=dict(color='#9333ea', width=2, dash='dot'),
                annotation=dict(
                    text='MAX VEX', font=dict(color='#9333ea', size=11),
                    yref='paper', y=0.97, yanchor='bottom',
                    bgcolor='rgba(0,0,0,0.6)', borderpad=3
                )
            )
        fig.add_hline(y=0, line=dict(color='rgba(255,255,255,0.2)', width=1))

        fig.update_layout(
            title={'text': f'{title_mode}  ·  {exp_desc}', 'x': 0.02, 'xanchor': 'left',
                   'font': {'size': 15, 'color': '#aaaaaa', 'family': 'Inter, sans-serif'}},
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#ffffff', family='Inter, sans-serif', size=12),
            height=520, margin=dict(l=60, r=30, t=60, b=60),
            showlegend=(mode in ['call_put', 'oi']),
            legend=dict(orientation='h', x=0, y=1.08, font=dict(color='#ffffff', size=11)),
            bargap=0.15,
        )
        fig.update_xaxes(gridcolor='rgba(255,255,255,0.06)', color='#aaaaaa',
                         showgrid=True, zeroline=False, tickformat='.2f', tickprefix='R$ ')
        fig.update_yaxes(gridcolor='rgba(255,255,255,0.06)', color='#aaaaaa',
                         showgrid=True, zeroline=False)
        return fig.to_json()

    # ─────────────────────────────────────────────────────────────────────────
    # NOVO: IV Chart — substitui o cumulativo no novo layout
    # ─────────────────────────────────────────────────────────────────────────
    def create_iv_chart(self, vex_df, spot_price, symbol,
                        vol_zones=None, expiration_info=None):
        """
        Volatilidade Implícita por strike:
          - Banda histórica 10D (cinza preenchido)
          - IV Calls (verde)
          - IV Puts (vermelho)
          - IV Média ATM±2 (laranja)
          - Média 10D (cyan tracejado)
        """
        if vex_df.empty:
            return None

        vex_df  = vex_df.sort_values('strike').reset_index(drop=True)
        strikes         = [float(x) for x in vex_df['strike'].tolist()]
        refined_call_iv = [float(x) for x in vex_df['refined_call_iv'].tolist()]
        refined_put_iv  = [float(x) for x in vex_df['refined_put_iv'].tolist()]
        refined_avg_iv  = [float(x) for x in vex_df['refined_avg_iv'].tolist()]
        iv_10d_avg      = [float(x) for x in vex_df['iv_10d_avg'].tolist()]
        iv_10d_min      = [float(x) for x in vex_df['iv_10d_min'].tolist()]
        iv_10d_max      = [float(x) for x in vex_df['iv_10d_max'].tolist()]
        exp_desc        = expiration_info['desc'] if expiration_info else ''

        fig = go.Figure()

        # Banda histórica
        fig.add_trace(go.Scatter(
            x=strikes, y=iv_10d_max, fill=None, mode='lines',
            line=dict(color='rgba(0,0,0,0)'), showlegend=False, hoverinfo='skip'
        ))
        fig.add_trace(go.Scatter(
            x=strikes, y=iv_10d_min, fill='tonexty',
            fillcolor='rgba(100,100,100,0.12)', mode='lines',
            line=dict(color='rgba(0,0,0,0)'),
            name='Banda 10D', showlegend=True, hoverinfo='skip'
        ))

        # IV Calls
        fig.add_trace(go.Scatter(
            x=strikes, y=refined_call_iv, mode='lines',
            line=dict(color='#22c55e', width=2),
            name='IV Calls',
            hovertemplate='Strike: R$ %{x:.2f}<br>IV Calls: %{y:.1f}%<extra></extra>'
        ))

        # IV Puts
        fig.add_trace(go.Scatter(
            x=strikes, y=refined_put_iv, mode='lines',
            line=dict(color='#ef4444', width=2),
            name='IV Puts',
            hovertemplate='Strike: R$ %{x:.2f}<br>IV Puts: %{y:.1f}%<extra></extra>'
        ))

        # IV Média ATM±2
        fig.add_trace(go.Scatter(
            x=strikes, y=refined_avg_iv, mode='lines',
            line=dict(color='#f97316', width=3),
            name='IV Média ATM±2',
            hovertemplate='Strike: R$ %{x:.2f}<br>IV Média: %{y:.1f}%<extra></extra>'
        ))

        # Média 10D
        fig.add_trace(go.Scatter(
            x=strikes, y=iv_10d_avg, mode='lines',
            line=dict(color='#06b6d4', width=2, dash='dot'),
            name='Média 10D',
            hovertemplate='Strike: R$ %{x:.2f}<br>Média 10D: %{y:.1f}%<extra></extra>'
        ))

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
        if vol_zones and vol_zones.get('max_iv_strike'):
            fig.add_vline(
                x=vol_zones['max_iv_strike'],
                line=dict(color='#f97316', width=1, dash='dot')
            )

        fig.update_layout(
            title=dict(
                text=f'Volatilidade Implícita  ·  {exp_desc}',
                x=0.02, xanchor='left',
                font=dict(size=13, color='#555', family='Inter, sans-serif')
            ),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#aaa', family='Inter, sans-serif', size=11),
            height=520,
            margin=dict(l=60, r=20, t=40, b=45),
            showlegend=True,
            legend=dict(orientation='h', x=0, y=1.1,
                        font=dict(color='#aaa', size=10)),
        )
        fig.update_xaxes(gridcolor='rgba(255,255,255,0.05)', color='#555',
                         zeroline=False, tickformat='.2f', tickprefix='R$ ')
        fig.update_yaxes(gridcolor='rgba(255,255,255,0.05)', color='#555',
                         zeroline=False, ticksuffix='%')

        return fig.to_json()

    def find_volatility_zones(self, vex_df, spot_price):
        if vex_df.empty:
            return None
        vex_real = vex_df[vex_df['has_real_data'] == True].copy()
        if len(vex_real) < 2:
            return None
        max_vex_strike = float(vex_real.loc[vex_real['total_vex_descoberto'].idxmax(), 'strike'])
        max_iv_strike  = float(vex_real.loc[vex_real['refined_avg_iv'].idxmax(), 'strike'])
        return {'max_vex_strike': max_vex_strike, 'max_iv_strike': max_iv_strike}

    def analyze(self, symbol, expiration_code=None):
        spot_price = self.data_provider.get_spot_price(symbol)
        if not spot_price:
            raise ValueError("Erro: não foi possível obter cotação")

        oplab_df = self.data_provider.get_oplab_historical_data(symbol)
        if oplab_df.empty:
            raise ValueError("Erro: sem dados da Oplab")

        historical_df = self.data_provider.get_historical_iv_context(symbol, days=10)
        oi_breakdown, expiration_info = self.data_provider.get_floqui_oi_breakdown(symbol, expiration_code)

        vex_df = self.vex_calculator.calculate_vex_with_context(oplab_df, oi_breakdown, spot_price, historical_df)
        if vex_df.empty:
            raise ValueError("Erro: falha no cálculo VEX")

        vol_regime = self.vol_detector.analyze_volatility_regime(vex_df, spot_price)
        vol_zones  = self.find_volatility_zones(vex_df, spot_price)

        # Gráfico 6 painéis — mantido
        plot_json = self.create_6_charts(vex_df, spot_price, symbol, vol_zones, expiration_info)

        # Gráficos individuais por modo — novo layout
        single_charts = {
            'net':        self.create_single_chart(vex_df, spot_price, symbol, vol_zones, expiration_info, mode='net'),
            'descoberto': self.create_single_chart(vex_df, spot_price, symbol, vol_zones, expiration_info, mode='descoberto'),
            'call_put':   self.create_single_chart(vex_df, spot_price, symbol, vol_zones, expiration_info, mode='call_put'),
            'oi':         self.create_single_chart(vex_df, spot_price, symbol, vol_zones, expiration_info, mode='oi'),
            'iv':         self.create_iv_chart(vex_df, spot_price, symbol, vol_zones, expiration_info),  # substitui cumulativo
        }

        logging.info(f"\nRESULTADOS VEX:")
        logging.info(f"Cotação:    R$ {spot_price:.2f}")
        if expiration_info:
            logging.info(f"Vencimento: {expiration_info['desc']}")
        logging.info(f"VEX Total:  {vol_regime.get('total_vex', 0):,.0f}")
        logging.info(f"IV ATM:     {vol_regime.get('atm_iv', 0):.1f}%")
        logging.info(f"Strikes:    {len(vex_df)}")

        return {
            'symbol':           symbol,
            'spot_price':       spot_price,
            'vol_regime':       vol_regime,
            'vol_zones':        vol_zones,
            'strikes_analyzed': len(vex_df),
            'expiration':       expiration_info,
            'plot_json':        plot_json,
            'single_charts':    single_charts,               # NOVO
            'chart_data':       vex_df.to_dict(orient='list'),  # NOVO
            'real_data_count':  int(vex_df['has_real_data'].sum()),
            'success':          True
        }


class VegaService:
    def __init__(self):
        self.analyzer = VEXAnalyzer()

    def get_available_expirations(self, ticker):
        return self.analyzer.data_provider.expiration_manager.get_available_expirations_list(ticker)

    def analyze_vega_complete(self, ticker, expiration_code=None, days_back=60):
        try:
            result     = self.analyzer.analyze(ticker, expiration_code)
            vol_regime = result.get('vol_regime', {})

            api_result = {
                'ticker':        ticker.replace('.SA', ''),
                'spot_price':    result['spot_price'],
                'vol_regime':    vol_regime,
                'plot_json':     result['plot_json'],
                'single_charts': result['single_charts'],    # NOVO
                'chart_data':    result['chart_data'],        # NOVO
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
            logging.error(f"Erro na análise VEX: {e}")
            raise
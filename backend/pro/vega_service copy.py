"""
vega_service.py - VEX Analysis COM DADOS DO BANCO POSTGRESQL
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


class ExpirationManager:
    def __init__(self, db_engine):
        self.db_engine = db_engine
        self.available_expirations = {
            "20251219": {"date": datetime(2025, 12, 19), "desc": "19 Dez 25 - M"},
            "20260116": {"date": datetime(2026, 1, 16),  "desc": "16 Jan 26 - M"},
            "20260220": {"date": datetime(2026, 2, 20),  "desc": "20 Fev 26 - M"},
            "20260320": {"date": datetime(2026, 3, 20),  "desc": "20 Mar 26 - M"},
            "20260417": {"date": datetime(2026, 4, 17),  "desc": "17 Abr 26 - M"},
            "20260515": {"date": datetime(2026, 5, 15),  "desc": "15 Mai 26 - M"},
            "20260619": {"date": datetime(2026, 6, 19),  "desc": "19 Jun 26 - M"},
            "20260717": {"date": datetime(2026, 7, 17),  "desc": "17 Jul 26 - M"},
            "20260821": {"date": datetime(2026, 8, 21),  "desc": "21 Ago 26 - M"},
            "20260918": {"date": datetime(2026, 9, 18),  "desc": "18 Set 26 - M"},
            "20261016": {"date": datetime(2026, 10, 16), "desc": "16 Out 26 - M"},
            "20261119": {"date": datetime(2026, 11, 19), "desc": "19 Nov 26 - M"},
            "20261218": {"date": datetime(2026, 12, 18), "desc": "18 Dez 26 - M"},
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
                result = conn.execute(query, {
                    'symbol': symbol,
                    'vencimento': exp_date
                })
                row = result.fetchone()
                count = row[0] if row else 0
            
            return count
            
        except Exception as e:
            logging.error(f"Erro ao testar disponibilidade: {e}")
            return 0
    
    def get_available_expirations_list(self, symbol):
        today = datetime.now()
        available = []
        
        for code, data in self.available_expirations.items():
            if data["date"] > today:
                days = (data["date"] - today).days
                data_count = self.test_data_availability(symbol, code)
                available.append({
                    "code": code,
                    "desc": data["desc"],
                    "days": days,
                    "data_count": data_count,
                    "available": data_count > 0
                })
        
        return sorted(available, key=lambda x: x["days"])
    
    def get_best_available_expiration(self, symbol):
        for code, data in self.available_expirations.items():
            if data["date"] > datetime.now():
                data_count = self.test_data_availability(symbol, code)
                if data_count > 0:
                    return {
                        "code": code,
                        "desc": data["desc"]
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
        
        # ✅ CONEXÃO COM BANCO DE DADOS - RAILWAY POSTGRESQL
        DATABASE_URL = os.getenv('DATABASE_URL')
        
        if not DATABASE_URL:
            DB_HOST = os.getenv('PGHOST') or os.getenv('DB_HOST', 'localhost')
            DB_NAME = os.getenv('PGDATABASE') or os.getenv('DB_NAME', 'railway')
            DB_USER = os.getenv('PGUSER') or os.getenv('DB_USER', 'postgres')
            DB_PASSWORD = os.getenv('PGPASSWORD') or os.getenv('DB_PASSWORD', '')
            DB_PORT = os.getenv('PGPORT') or os.getenv('DB_PORT', '5432')
            
            # Valida que a porta é um número
            try:
                DB_PORT = str(int(DB_PORT))
            except (ValueError, TypeError):
                logging.error(f"❌ DB_PORT inválido: '{DB_PORT}' - usando 5432")
                DB_PORT = '5432'
            
            DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        
        logging.info(f"🔌 Conectando ao banco PostgreSQL (VEX)...")
        
        try:
            self.db_engine = create_engine(DATABASE_URL)
            
            # TESTA CONEXÃO
            with self.db_engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM opcoes_b3"))
                count = result.fetchone()[0]
                logging.info(f"✅ Conexão OK (VEX) - {count:,} registros na opcoes_b3")
                
        except Exception as e:
            logging.error(f"❌ Erro ao conectar (VEX): {e}")
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
            to_date = datetime.now().strftime('%Y-%m-%d')
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
                (latest_data['vega'] > 0) &
                (latest_data['volatility'] > 0) &
                (latest_data['premium'] > 0) &
                (latest_data['strike'] > 0) &
                (latest_data['days_to_maturity'] > 0) &
                (latest_data['days_to_maturity'] <= 60)
            ].copy()
            
            logging.info(f"Dados Vega Oplab: {len(valid_data)} opções")
            return valid_data
            
        except Exception as e:
            logging.error(f"Erro dados Oplab: {e}")
            return pd.DataFrame()
    
    def get_floqui_oi_breakdown(self, symbol, expiration_code=None):
        """BUSCA DO BANCO DE DADOS POSTGRESQL - Mantém nome da função"""
        try:
            if expiration_code:
                expiration = {
                    "code": expiration_code,
                    "desc": self.expiration_manager.available_expirations.get(expiration_code, {}).get("desc", expiration_code)
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
                    qtd_total,
                    qtd_descoberto,
                    qtd_trava,
                    qtd_coberto
                FROM opcoes_b3
                WHERE ticker = :symbol
                AND vencimento = :vencimento
                AND data_referencia = (
                    SELECT MAX(data_referencia) 
                    FROM opcoes_b3 
                    WHERE ticker = :symbol
                )
                ORDER BY preco_exercicio
            """)
            
            df = pd.read_sql(query, self.db_engine, params={
                'symbol': symbol,
                'vencimento': exp_date
            })
            
            if df.empty:
                logging.warning(f"Nenhum dado encontrado no banco para {symbol}")
                return {}, expiration
            
            # ✅ NOVA ESTRUTURA - USA STRING COMO CHAVE
            oi_breakdown = {}
            for _, row in df.iterrows():
                strike = float(row['preco_exercicio'])
                option_type = str(row['tipo_opcao']).upper()
                oi_total = int(row['qtd_total'])
                oi_descoberto = int(row['qtd_descoberto'])
                
                if strike > 0 and oi_total > 0:
                    # ✅ CHAVE COMO STRING: "7.25_CALL"
                    key = f"{strike}_{option_type}"
                    oi_breakdown[key] = {
                        'strike': strike,
                        'type': option_type,
                        'total': oi_total,
                        'descoberto': oi_descoberto,
                        'travado': int(row['qtd_trava']),
                        'coberto': int(row['qtd_coberto'])
                    }
            
            logging.info(f"OI breakdown VEX: {len(oi_breakdown)} strikes")
            return oi_breakdown, expiration
            
        except Exception as e:
            logging.error(f"Erro Floqui: {e}")
            return {}, None

    def get_historical_iv_context(self, symbol, days=10):
        """Busca contexto histórico de IV para comparação"""
        try:
            to_date = datetime.now().strftime('%Y-%m-%d')
            from_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            url = f"{self.oplab_url}/market/historical/options/{symbol}/{from_date}/{to_date}"
            response = requests.get(url, headers=self.headers, timeout=15)
            
            if response.status_code != 200:
                logging.warning(f"Erro histórico IV: {response.status_code}")
                return pd.DataFrame()
            
            data = response.json()
            if not data:
                return pd.DataFrame()
            
            df = pd.DataFrame(data)
            df['time'] = pd.to_datetime(df['time'])
            
            valid_data = df[
                (df['volatility'] > 0) &
                (df['volatility'] < 300) &
                (df['premium'] > 0) &
                (df['strike'] > 0)
            ].copy()
            
            if valid_data.empty:
                return pd.DataFrame()
            
            valid_data['date'] = valid_data['time'].dt.date
            
            daily_avg = valid_data.groupby(['date', 'strike'])['volatility'].mean().reset_index()
            daily_avg.rename(columns={'volatility': 'iv_daily_avg'}, inplace=True)
            
            daily_avg = daily_avg.sort_values('date')
            
            logging.info(f"Contexto IV histórico: {len(daily_avg)} registros ({daily_avg['date'].nunique()} dias únicos)")
            return daily_avg
            
        except Exception as e:
            logging.error(f"Erro contexto IV: {e}")
            return pd.DataFrame()


class VEXCalculator:
    
    def calculate_vex_with_context(self, oplab_df, oi_breakdown, spot_price, historical_df=None):
        """Calcula VEX = Vega × Open Interest × 100"""
        if oplab_df.empty:
            return pd.DataFrame()
        
        price_range = spot_price * 0.25
        valid_options = oplab_df[
            (oplab_df['strike'] >= spot_price - price_range) &
            (oplab_df['strike'] <= spot_price + price_range)
        ].copy()
        
        if valid_options.empty:
            return pd.DataFrame()
        
        vex_data = []
        
        for strike in valid_options['strike'].unique():
            strike_options = valid_options[valid_options['strike'] == strike]
            
            calls = strike_options[strike_options['type'] == 'CALL']
            puts = strike_options[strike_options['type'] == 'PUT']
            
            iv_context = self._calculate_iv_context(strike, historical_df) if historical_df is not None else {}
            
            call_data = None
            put_data = None
            has_real_call = False
            has_real_put = False
            
            # ✅ BUSCA COM CHAVE STRING
            if len(calls) > 0:
                call_key = f"{float(strike)}_CALL"
                if call_key in oi_breakdown:
                    call_data = oi_breakdown[call_key]
                    has_real_call = True
            
            if len(puts) > 0:
                put_key = f"{float(strike)}_PUT"
                if put_key in oi_breakdown:
                    put_data = oi_breakdown[put_key]
                    has_real_put = True
            
            if not (has_real_call or has_real_put):
                continue
            
            call_vex = 0.0
            call_vex_descoberto = 0.0
            call_iv = 0.0
            if call_data and len(calls) > 0:
                avg_vega = float(calls['vega'].mean())
                avg_iv = float(calls['volatility'].mean())
                call_vex = avg_vega * call_data['total'] * 100
                call_vex_descoberto = avg_vega * call_data['descoberto'] * 100
                call_iv = avg_iv
            
            put_vex = 0.0
            put_vex_descoberto = 0.0
            put_iv = 0.0
            if put_data and len(puts) > 0:
                avg_vega = float(puts['vega'].mean())
                avg_iv = float(puts['volatility'].mean())
                put_vex = avg_vega * put_data['total'] * 100
                put_vex_descoberto = avg_vega * put_data['descoberto'] * 100
                put_iv = avg_iv
            
            total_vex = call_vex + put_vex
            total_vex_descoberto = call_vex_descoberto + put_vex_descoberto
            
            avg_iv = 0.0
            if call_iv > 0 and put_iv > 0:
                avg_iv = (call_iv + put_iv) / 2
            elif call_iv > 0:
                avg_iv = call_iv
            elif put_iv > 0:
                avg_iv = put_iv
            
            vex_data.append({
                'strike': float(strike),
                'call_vex': float(call_vex),
                'put_vex': float(put_vex),
                'total_vex': float(total_vex),
                'call_vex_descoberto': float(call_vex_descoberto),
                'put_vex_descoberto': float(put_vex_descoberto),
                'total_vex_descoberto': float(total_vex_descoberto),
                'call_oi_total': int(call_data['total'] if call_data else 0),
                'put_oi_total': int(put_data['total'] if put_data else 0),
                'call_oi_descoberto': int(call_data['descoberto'] if call_data else 0),
                'put_oi_descoberto': int(put_data['descoberto'] if put_data else 0),
                'call_iv': float(call_iv),
                'put_iv': float(put_iv),
                'avg_iv': float(avg_iv),
                'iv_10d_avg': float(iv_context.get('iv_10d_avg', avg_iv)),
                'iv_10d_min': float(iv_context.get('iv_10d_min', avg_iv * 0.8)),
                'iv_10d_max': float(iv_context.get('iv_10d_max', avg_iv * 1.2)),
                'iv_percentile': float(iv_context.get('iv_percentile', 50)),
                'iv_status': iv_context.get('iv_status', 'NEUTRAL'),
                'has_real_data': has_real_call or has_real_put
            })
        
        result_df = pd.DataFrame(vex_data).sort_values('strike')
        logging.info(f"VEX com contexto calculado para {len(result_df)} strikes")
        
        return result_df
    
    def _calculate_iv_context(self, strike, historical_df):
        """Calcula contexto histórico para um strike específico"""
        if historical_df.empty:
            return {}
        
        strike_data = historical_df[
            (historical_df['strike'] >= strike - 1) &
            (historical_df['strike'] <= strike + 1)
        ].copy()
        
        if strike_data.empty:
            return {}
        
        if 'iv_daily_avg' in strike_data.columns:
            iv_values = strike_data['iv_daily_avg'].values
        else:
            iv_values = strike_data['volatility'].values
        
        iv_values = iv_values[iv_values < 200]
        
        if len(iv_values) == 0:
            return {}
        
        iv_10d_avg = float(np.mean(iv_values))
        iv_10d_min = float(np.min(iv_values))
        iv_10d_max = float(np.max(iv_values))
        
        current_iv = float(iv_values[-1])
        iv_percentile = float(np.percentile(iv_values, 50))
        
        logging.info(f"Strike {strike:.2f}: IV atual={current_iv:.1f}%, Média 10d={iv_10d_avg:.1f}%, Valores={len(iv_values)} dias")
        
        if current_iv > iv_10d_avg * 1.3:
            iv_status = 'MUITO_ALTA'
        elif current_iv > iv_10d_avg * 1.1:
            iv_status = 'ALTA'
        elif current_iv < iv_10d_avg * 0.7:
            iv_status = 'MUITO_BAIXA'
        elif current_iv < iv_10d_avg * 0.9:
            iv_status = 'BAIXA'
        else:
            iv_status = 'NORMAL'
        
        return {
            'iv_10d_avg': iv_10d_avg,
            'iv_10d_min': iv_10d_min,
            'iv_10d_max': iv_10d_max,
            'iv_percentile': iv_percentile,
            'iv_status': iv_status
        }


class VolatilityRegimeDetector:

    def analyze_volatility_regime(self, vex_df, spot_price):
        """Analisa regime de volatilidade baseado em VEX"""
        if vex_df.empty:
            return None
        
        vex_df_copy = vex_df.copy()
        vex_df_copy['distance_from_spot'] = abs(vex_df_copy['strike'] - spot_price)
        atm_idx = vex_df_copy['distance_from_spot'].idxmin()
        
        atm_strike = float(vex_df_copy.loc[atm_idx, 'strike'])
        atm_iv = float(vex_df_copy.loc[atm_idx, 'avg_iv'])
        atm_iv_10d_avg = float(vex_df_copy.loc[atm_idx, 'iv_10d_avg'])
        
        logging.info(f"ATM SELECIONADO: Strike {atm_strike:.2f} (Spot={spot_price:.2f})")
        logging.info(f"ATM IV: atual={atm_iv:.1f}%, média 10d={atm_iv_10d_avg:.1f}%")
        
        total_oi = (vex_df_copy['call_oi_total'] + vex_df_copy['put_oi_total']).sum()
        if total_oi > 0:
            weighted_iv = float((vex_df_copy['avg_iv'] * (vex_df_copy['call_oi_total'] + vex_df_copy['put_oi_total'])).sum() / total_oi)
        else:
            weighted_iv = float(vex_df_copy['avg_iv'].mean())
        
        current_iv = atm_iv if atm_iv > 0 else weighted_iv
        
        total_vex = float(vex_df_copy['total_vex'].sum())
        total_vex_descoberto = float(vex_df_copy['total_vex_descoberto'].sum())
        
        max_vex_idx = vex_df_copy['total_vex'].idxmax()
        max_vex_strike = float(vex_df_copy.loc[max_vex_idx, 'strike'])
        
        iv_diff_pp = current_iv - atm_iv_10d_avg
        iv_diff_pct = ((current_iv - atm_iv_10d_avg) / atm_iv_10d_avg) * 100 if atm_iv_10d_avg > 0 else 0
        
        if iv_diff_pp > 2:
            iv_trend = 'ALTA'
            iv_trend_description = f'IV {iv_diff_pp:+.1f} p.p. acima da média 10D'
        elif iv_diff_pp < -2:
            iv_trend = 'BAIXA'
            iv_trend_description = f'IV {iv_diff_pp:.1f} p.p. abaixo da média 10D'
        else:
            iv_trend = 'ESTAVEL'
            iv_trend_description = 'IV dentro da faixa normal'
        
        abs_iv_diff_pp = abs(iv_diff_pp)
        
        if abs_iv_diff_pp > 10:
            volatility_risk = 'HIGH'
            if iv_diff_pp > 0:
                interpretation = f'IV muito inflada (+{iv_diff_pp:.1f} p.p.) - Alto risco de compressão'
            else:
                interpretation = f'IV muito comprimida ({iv_diff_pp:.1f} p.p.) - Alto risco de explosão'
        
        elif abs_iv_diff_pp > 5:
            volatility_risk = 'MODERATE'
            if iv_diff_pp > 0:
                interpretation = f'IV inflada (+{iv_diff_pp:.1f} p.p.) - Risco moderado de compressão'
            else:
                interpretation = f'IV comprimida ({iv_diff_pp:.1f} p.p.) - Risco moderado de ajuste'
        
        else:
            volatility_risk = 'LOW'
            interpretation = 'IV próxima da média histórica - Baixo risco de mudança brusca'
        
        logging.info(f"IV Diff: {iv_diff_pp:+.1f} p.p. ({iv_diff_pct:+.1f}%) → Risk: {volatility_risk}")
        
        return {
            'total_vex': total_vex,
            'total_vex_descoberto': total_vex_descoberto,
            'weighted_iv': current_iv,
            'atm_strike': atm_strike,
            'atm_iv': atm_iv,
            'atm_iv_10d_avg': atm_iv_10d_avg,
            'iv_diff_pct': float(iv_diff_pct),
            'iv_trend': iv_trend,
            'iv_trend_description': iv_trend_description,
            'max_vex_strike': max_vex_strike,
            'volatility_risk': volatility_risk,
            'interpretation': interpretation
        }


class VEXAnalyzer:
    def __init__(self):
        self.data_provider = DataProvider()
        self.vex_calculator = VEXCalculator()
        self.vol_detector = VolatilityRegimeDetector()
    
    def create_6_charts(self, vex_df, spot_price, symbol, vol_zones=None, expiration_info=None):
        """Cria os 6 gráficos VEX com contexto histórico"""
        if vex_df.empty:
            return None
        
        title = expiration_info["desc"] if expiration_info else ""
        
        subplot_titles = [
            '<b style="color: #ffffff;">Total VEX</b><br><span style="font-size: 12px; color: #888;">Sensibilidade total vega</span>',
            '<b style="color: #ffffff;">VEX Descoberto</b><br><span style="font-size: 12px; color: #888;">Risco real volatilidade</span>',
            '<b style="color: #ffffff;">Volatilidade Implícita</b><br><span style="font-size: 12px; color: #888;">IV por strike</span>',
            '<b style="color: #ffffff;">Calls vs Puts</b><br><span style="font-size: 12px; color: #888;">VEX por tipo</span>',
            '<b style="color: #ffffff;">VEX / IV</b><br><span style="font-size: 12px; color: #888;">Eficiência risco vol</span>',
            '<b style="color: #ffffff;">Concentração Risco</b><br><span style="font-size: 12px; color: #888;">% risco por strike</span>'
        ]
        
        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=subplot_titles,
            vertical_spacing=0.08,
            horizontal_spacing=0.08
        )
        
        strikes = [float(x) for x in vex_df['strike'].tolist()]
        call_iv = [float(x) for x in vex_df['call_iv'].tolist()]
        put_iv = [float(x) for x in vex_df['put_iv'].tolist()]
        avg_iv = [float(x) for x in vex_df['avg_iv'].tolist()]
        iv_10d_avg = [float(x) for x in vex_df['iv_10d_avg'].tolist()]
        iv_10d_min = [float(x) for x in vex_df['iv_10d_min'].tolist()]
        iv_10d_max = [float(x) for x in vex_df['iv_10d_max'].tolist()]
        total_vex_values = [float(x) for x in vex_df['total_vex'].tolist()]
        descoberto_values = [float(x) for x in vex_df['total_vex_descoberto'].tolist()]
        call_vex_values = [float(x) for x in vex_df['call_vex'].tolist()]
        put_vex_values = [float(x) for x in vex_df['put_vex'].tolist()]
        
        # 1. Total VEX
        fig.add_trace(go.Bar(x=strikes, y=total_vex_values, marker_color='#9333ea', showlegend=False), row=1, col=1)
        
        # 2. VEX Descoberto
        fig.add_trace(go.Bar(x=strikes, y=descoberto_values, marker_color='#dc2626', showlegend=False), row=1, col=2)
        
        # 3. Volatilidade Implícita
        fig.add_trace(go.Scatter(
            x=strikes, 
            y=iv_10d_max, 
            fill=None, 
            mode='lines', 
            line=dict(color='rgba(0,0,0,0)'), 
            showlegend=False
        ), row=2, col=1)
        
        fig.add_trace(go.Scatter(
            x=strikes, 
            y=iv_10d_min, 
            fill='tonexty', 
            fillcolor='rgba(100,100,100,0.2)', 
            mode='lines', 
            line=dict(color='rgba(0,0,0,0)'), 
            showlegend=False
        ), row=2, col=1)
        
        fig.add_trace(go.Scatter(
            x=strikes, 
            y=iv_10d_avg, 
            mode='lines', 
            line=dict(color='#06b6d4', width=2, dash='dash'), 
            showlegend=False
        ), row=2, col=1)
        
        fig.add_trace(go.Scatter(
            x=strikes, 
            y=call_iv, 
            mode='lines', 
            line=dict(color='#22c55e', width=2), 
            showlegend=False
        ), row=2, col=1)
        
        fig.add_trace(go.Scatter(
            x=strikes, 
            y=put_iv, 
            mode='lines', 
            line=dict(color='#ef4444', width=2), 
            showlegend=False
        ), row=2, col=1)
        
        fig.add_trace(go.Scatter(
            x=strikes, 
            y=avg_iv, 
            mode='lines+markers', 
            line=dict(color='#f97316', width=3), 
            marker=dict(color='#f97316', size=6),
            showlegend=False
        ), row=2, col=1)
        
        # 4. Calls vs Puts
        fig.add_trace(go.Bar(x=strikes, y=call_vex_values, marker_color='#22c55e', showlegend=False), row=2, col=2)
        fig.add_trace(go.Bar(x=strikes, y=put_vex_values, marker_color='#ef4444', showlegend=False), row=2, col=2)
        
        # 5. VEX / IV
        vex_per_iv = []
        for i in range(len(total_vex_values)):
            if avg_iv[i] > 0:
                vex_per_iv.append(total_vex_values[i] / avg_iv[i])
            else:
                vex_per_iv.append(0)
        
        fig.add_trace(go.Scatter(
            x=strikes, 
            y=vex_per_iv, 
            mode='lines+markers',
            line=dict(color='#06b6d4', width=3),
            marker=dict(color='#06b6d4', size=6),
            showlegend=False
        ), row=3, col=1)
        
        # 6. Concentração de Risco
        total_vex_abs = sum([abs(x) for x in total_vex_values])
        if total_vex_abs > 0:
            concentration_pct = [(abs(x) / total_vex_abs) * 100 for x in total_vex_values]
        else:
            concentration_pct = [0] * len(total_vex_values)
        
        risk_colors = ['#ef4444' if x > 20 else '#f97316' if x > 10 else '#22c55e' for x in concentration_pct]
        fig.add_trace(go.Bar(x=strikes, y=concentration_pct, marker_color=risk_colors, showlegend=False), row=3, col=2)
        
        # Linhas de referência
        for row in range(1, 4):
            for col in range(1, 3):
                fig.add_vline(x=spot_price, line=dict(color='#fbbf24', width=2, dash='dash'), row=row, col=col)
                
                if vol_zones and vol_zones.get('max_vex_strike'):
                    fig.add_vline(x=vol_zones['max_vex_strike'], line=dict(color='#9333ea', width=2, dash='dot'), row=row, col=col)
                
                if vol_zones and vol_zones.get('max_iv_strike') and row == 2 and col == 1:
                    fig.add_vline(x=vol_zones['max_iv_strike'], line=dict(color='#f97316', width=2, dash='dot'), row=row, col=col)
                
                if not (row == 2 and col == 1):
                    fig.add_hline(y=0, line=dict(color='rgba(255,255,255,0.3)', width=1), row=row, col=col)
        
        fig.update_layout(
            title={
                'text': title,
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 20, 'color': '#ffffff', 'family': 'Inter, sans-serif'}
            },
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#ffffff', family='Inter, sans-serif'),
            height=1600,
            showlegend=False,
            margin=dict(l=50, r=50, t=100, b=50)
        )
        
        fig.update_annotations(font=dict(color='#ffffff', family='Inter, sans-serif', size=21))
        fig.update_xaxes(gridcolor='rgba(255,255,255,0.1)', color='#ffffff', showgrid=True, zeroline=False)
        fig.update_yaxes(gridcolor='rgba(255,255,255,0.1)', color='#ffffff', showgrid=True, zeroline=False)
        
        return fig.to_json()
    
    def analyze(self, symbol, expiration_code=None):
        """Análise principal VEX"""
        logging.info(f"INICIANDO ANALISE VEX - {symbol}")
                        
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
        
        vol_zones = self.find_volatility_zones(vex_df, spot_price)
        
        plot_json = self.create_6_charts(vex_df, spot_price, symbol, vol_zones, expiration_info)
        
        return {
            'symbol': symbol,
            'spot_price': spot_price,
            'vol_regime': vol_regime,
            'vol_zones': vol_zones,
            'strikes_analyzed': len(vex_df),
            'expiration': expiration_info,
            'plot_json': plot_json,
            'real_data_count': int(vex_df['has_real_data'].sum()),
            'success': True
        }
    
    def find_volatility_zones(self, vex_df, spot_price):
        """Encontra zonas de máxima sensibilidade à volatilidade"""
        if vex_df.empty:
            return None
        
        vex_real = vex_df[vex_df['has_real_data'] == True].copy()
        
        if len(vex_real) < 2:
            return None
        
        max_vex_idx = vex_real['total_vex_descoberto'].idxmax()
        max_vex_strike = float(vex_real.loc[max_vex_idx, 'strike'])
        
        max_iv_idx = vex_real['avg_iv'].idxmax()
        max_iv_strike = float(vex_real.loc[max_iv_idx, 'strike'])
        
        return {
            'max_vex_strike': max_vex_strike,
            'max_iv_strike': max_iv_strike
        }


class VegaService:
    def __init__(self):
        self.analyzer = VEXAnalyzer()
    
    def get_available_expirations(self, ticker):
        return self.analyzer.data_provider.expiration_manager.get_available_expirations_list(ticker)
    
    def analyze_vega_complete(self, ticker, expiration_code=None, days_back=60):
        try:
            result = self.analyzer.analyze(ticker, expiration_code)
            
            vol_regime = result.get('vol_regime', {})
            
            api_result = {
                'ticker': ticker.replace('.SA', ''),
                'spot_price': result['spot_price'],
                'vol_regime': vol_regime,
                'plot_json': result['plot_json'],
                'options_count': result['strikes_analyzed'],
                'data_quality': {
                    'expiration': result['expiration']['desc'] if result['expiration'] else None,
                    'real_data_count': result['real_data_count']
                },
                'success': True
            }
            
            return convert_to_json_serializable(api_result)
            
        except Exception as e:
            logging.error(f"Erro na análise VEX: {e}")
            raise
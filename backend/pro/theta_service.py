"""
theta_service.py - TEX Analysis COM DADOS DO BANCO POSTGRESQL - VERSÃO CORRIGIDA
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
            "20260213": {"date": datetime(2026, 2, 13), "desc": "13 Fev 26 - W2"},
            "20260220": {"date": datetime(2026, 2, 20), "desc": "20 Fev 26 - M"},
            "20260227": {"date": datetime(2026, 2, 27), "desc": "27 Fev 26 - W4"},
            "20260306": {"date": datetime(2026, 3, 6), "desc": "06 Mar 26 - W1"},
            "20260313": {"date": datetime(2026, 3, 13), "desc": "13 Mar 26 - W2"},
            "20260320": {"date": datetime(2026, 3, 20), "desc": "20 Mar 26 - M"},
            "20260327": {"date": datetime(2026, 3, 27), "desc": "27 Mar 26 - W4"},
            "20260402": {"date": datetime(2026, 4, 2), "desc": "02 Abr 26 - W1"},
            "20260410": {"date": datetime(2026, 4, 10), "desc": "10 Abr 26 - W2"},
            "20260417": {"date": datetime(2026, 4, 17), "desc": "17 Abr 26 - M"},
            "20260424": {"date": datetime(2026, 4, 24), "desc": "24 Abr 26 - W4"},
            "20260515": {"date": datetime(2026, 5, 15), "desc": "15 Mai 26 - M"},
            "20260619": {"date": datetime(2026, 6, 19), "desc": "19 Jun 26 - M"},
            "20260717": {"date": datetime(2026, 7, 17), "desc": "17 Jul 26 - M"},
            "20260821": {"date": datetime(2026, 8, 21), "desc": "21 Ago 26 - M"},
            "20260918": {"date": datetime(2026, 9, 18), "desc": "18 Set 26 - M"},
            "20261016": {"date": datetime(2026, 10, 16), "desc": "16 Out 26 - M"},
            "20261119": {"date": datetime(2026, 11, 19), "desc": "19 Nov 26 - M"},
            "20261119": {"date": datetime(2026, 11, 19), "desc": "19 Nov 26 - W1"},
            "20261119": {"date": datetime(2026, 11, 19), "desc": "19 Nov 26 - W2"},
            "20261119": {"date": datetime(2026, 11, 19), "desc": "19 Nov 26 - W3"},
            "20261119": {"date": datetime(2026, 11, 19), "desc": "19 Nov 26 - W4"},
            "20261119": {"date": datetime(2026, 11, 19), "desc": "19 Nov 26 - W5"},
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
            "20271119": {"date": datetime(2027, 11, 19), "desc": "19 Nov 27 - W1"},
            "20271119": {"date": datetime(2027, 11, 19), "desc": "19 Nov 27 - W2"},
            "20271119": {"date": datetime(2027, 11, 19), "desc": "19 Nov 27 - W3"},
            "20271119": {"date": datetime(2027, 11, 19), "desc": "19 Nov 27 - W4"},
            "20271119": {"date": datetime(2027, 11, 19), "desc": "19 Nov 27 - W5"},
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
                    days = (data["date"] - datetime.now()).days
                    return {
                        "code": code,
                        "desc": data["desc"],
                        "days": max(1, days)
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
            DB_HOST = os.getenv('PGHOST') or os.getenv('DB_HOST', 'localhost')
            DB_NAME = os.getenv('PGDATABASE') or os.getenv('DB_NAME', 'railway')
            DB_USER = os.getenv('PGUSER') or os.getenv('DB_USER', 'postgres')
            DB_PASSWORD = os.getenv('PGPASSWORD') or os.getenv('DB_PASSWORD', '')
            DB_PORT = os.getenv('PGPORT') or os.getenv('DB_PORT', '5432')
            
            try:
                DB_PORT = str(int(DB_PORT))
            except (ValueError, TypeError):
                logging.error(f"❌ DB_PORT inválido: '{DB_PORT}' - usando 5432")
                DB_PORT = '5432'
            
            DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        
        logging.info(f"🔌 Conectando ao banco PostgreSQL (TEX)...")
        
        try:
            self.db_engine = create_engine(DATABASE_URL)
            
            with self.db_engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM opcoes_b3"))
                count = result.fetchone()[0]
                logging.info(f"✅ Conexão OK (TEX) - {count:,} registros na opcoes_b3")
                
        except Exception as e:
            logging.error(f"❌ Erro ao conectar (TEX): {e}")
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
                (latest_data['theta'] != 0) &
                (latest_data['premium'] > 0) &
                (latest_data['strike'] > 0) &
                (latest_data['days_to_maturity'] > 0) &
                (latest_data['days_to_maturity'] <= 60)
            ].copy()
            
            logging.info(f"Dados Theta Oplab: {len(valid_data)} opções")
            return valid_data
            
        except Exception as e:
            logging.error(f"Erro dados Oplab: {e}")
            return pd.DataFrame()
    
    def get_floqui_oi_breakdown(self, symbol, expiration_code=None):
        """✅ VERSÃO CORRIGIDA - Filtra strikes realistas"""
        try:
            if expiration_code:
                expiration = {
                    "code": expiration_code,
                    "desc": self.expiration_manager.available_expirations.get(expiration_code, {}).get("desc", expiration_code)
                }
                days = (self.expiration_manager.available_expirations.get(expiration_code, {}).get("date", datetime.now()) - datetime.now()).days
                expiration["days"] = max(1, days)
            else:
                expiration = self.expiration_manager.get_best_available_expiration(symbol)
            
            if not expiration:
                logging.warning("Nenhum vencimento disponível")
                return {}, None
            
            exp_date = datetime.strptime(expiration['code'], '%Y%m%d')
            
            # ✅ BUSCAR SPOT ATUAL
            spot_price = self.get_spot_price(symbol)
            if not spot_price:
                logging.error(f"Não conseguiu spot para {symbol}")
                spot_price = 100
            
            # ✅ FILTRO: ±50% do spot
            min_strike = spot_price * 0.5
            max_strike = spot_price * 1.5
            
            logging.info(f"🔍 TEX: Filtrando strikes {min_strike:.2f} - {max_strike:.2f} (spot={spot_price:.2f})")
            
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
                AND preco_exercicio BETWEEN :min_strike AND :max_strike
                AND data_referencia = (
                    SELECT MAX(data_referencia) 
                    FROM opcoes_b3 
                    WHERE ticker = :symbol
                )
                ORDER BY preco_exercicio
            """)
            
            df = pd.read_sql(query, self.db_engine, params={
                'symbol': symbol,
                'vencimento': exp_date,
                'min_strike': min_strike,
                'max_strike': max_strike
            })
            
            if df.empty:
                logging.warning(f"❌ TEX: Sem dados para {symbol}")
                return {}, expiration
            
            logging.info(f"✅ TEX: {len(df)} registros, strikes {df['preco_exercicio'].min():.2f} - {df['preco_exercicio'].max():.2f}")
            
            oi_breakdown = {}
            for _, row in df.iterrows():
                strike = float(row['preco_exercicio'])
                option_type = str(row['tipo_opcao']).upper()
                oi_total = int(row['qtd_total'])
                oi_descoberto = int(row['qtd_descoberto'])
                
                if strike > 0 and oi_total > 0:
                    key = f"{strike}_{option_type}"
                    oi_breakdown[key] = {
                        'strike': strike,
                        'type': option_type,
                        'total': oi_total,
                        'descoberto': oi_descoberto,
                        'travado': int(row['qtd_trava']),
                        'coberto': int(row['qtd_coberto'])
                    }
            
            logging.info(f"✅ TEX: {len(oi_breakdown)} chaves no dicionário")
            
            return oi_breakdown, expiration
            
        except Exception as e:
            logging.error(f"❌ Erro TEX Floqui: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return {}, None


class TEXCalculator:
    def calculate_tex(self, oplab_df, oi_breakdown, spot_price):
        """✅ VERSÃO COM DEBUG - Calcula TEX"""
        if oplab_df.empty:
            logging.error("❌ TEX: oplab_df vazio!")
            return pd.DataFrame()
        
        # ✅ DEBUG
        oplab_strikes = sorted(oplab_df['strike'].unique())
        
        db_strikes = set()
        for key in oi_breakdown.keys():
            parts = key.rsplit('_', 1)
            if len(parts) == 2:
                db_strikes.add(float(parts[0]))
        db_strikes_sorted = sorted(db_strikes)
        
        logging.info(f"")
        logging.info(f"🔍 DEBUG TEX:")
        logging.info(f"   Spot: R$ {spot_price:.2f}")
        logging.info(f"   Oplab: {len(oplab_strikes)} strikes ({min(oplab_strikes):.2f} - {max(oplab_strikes):.2f})")
        if db_strikes_sorted:
            logging.info(f"   Banco: {len(db_strikes_sorted)} strikes ({min(db_strikes_sorted):.2f} - {max(db_strikes_sorted):.2f})")
        else:
            logging.error(f"   ❌ Banco vazio!")
            return pd.DataFrame()
        
        price_range = spot_price * 0.25
        valid_options = oplab_df[
            (oplab_df['strike'] >= spot_price - price_range) &
            (oplab_df['strike'] <= spot_price + price_range)
        ].copy()
        
        logging.info(f"   Após filtro ±25%: {len(valid_options)} opções")
        
        if valid_options.empty:
            logging.error("❌ TEX: valid_options vazio!")
            return pd.DataFrame()
        
        tex_data = []
        matches = 0
        no_matches = 0
        
        for strike in valid_options['strike'].unique():
            strike_options = valid_options[valid_options['strike'] == strike]
            
            calls = strike_options[strike_options['type'] == 'CALL']
            puts = strike_options[strike_options['type'] == 'PUT']
            
            call_data = None
            put_data = None
            
            if len(calls) > 0:
                call_key = f"{float(strike)}_CALL"
                if call_key in oi_breakdown:
                    call_data = oi_breakdown[call_key]
                    matches += 1
                else:
                    no_matches += 1
            
            if len(puts) > 0:
                put_key = f"{float(strike)}_PUT"
                if put_key in oi_breakdown:
                    put_data = oi_breakdown[put_key]
                    matches += 1
                else:
                    no_matches += 1
            
            if not (call_data or put_data):
                continue
            
            call_tex = call_tex_descoberto = call_days = 0.0
            if call_data and len(calls) > 0:
                avg_theta = float(calls['theta'].mean())
                avg_days = float(calls['days_to_maturity'].mean())
                call_tex = avg_theta * call_data['total'] * 100
                call_tex_descoberto = avg_theta * call_data['descoberto'] * 100
                call_days = avg_days
            
            put_tex = put_tex_descoberto = put_days = 0.0
            if put_data and len(puts) > 0:
                avg_theta = float(puts['theta'].mean())
                avg_days = float(puts['days_to_maturity'].mean())
                put_tex = avg_theta * put_data['total'] * 100
                put_tex_descoberto = avg_theta * put_data['descoberto'] * 100
                put_days = avg_days
            
            total_tex = call_tex + put_tex
            total_tex_descoberto = call_tex_descoberto + put_tex_descoberto
            
            weighted_days = 0.0
            if call_data and put_data:
                total_oi = call_data['total'] + put_data['total']
                if total_oi > 0:
                    weighted_days = (call_days * call_data['total'] + put_days * put_data['total']) / total_oi
            elif call_data:
                weighted_days = call_days
            elif put_data:
                weighted_days = put_days
            
            time_decay_acceleration = max(0, (30 - weighted_days) / 30) if weighted_days > 0 else 0
            
            tex_data.append({
                'strike': float(strike),
                'call_tex': float(call_tex),
                'put_tex': float(put_tex),
                'total_tex': float(total_tex),
                'call_tex_descoberto': float(call_tex_descoberto),
                'put_tex_descoberto': float(put_tex_descoberto),
                'total_tex_descoberto': float(total_tex_descoberto),
                'call_oi_total': int(call_data['total'] if call_data else 0),
                'put_oi_total': int(put_data['total'] if put_data else 0),
                'call_oi_descoberto': int(call_data['descoberto'] if call_data else 0),
                'put_oi_descoberto': int(put_data['descoberto'] if put_data else 0),
                'days_to_expiration': float(weighted_days),
                'time_decay_acceleration': float(time_decay_acceleration),
                'has_real_data': bool(call_data or put_data)
            })
        
        logging.info(f"   ✅ Matches: {matches} | ❌ No match: {no_matches}")
        logging.info(f"   📊 TEX: {len(tex_data)} strikes")
        
        return pd.DataFrame(tex_data).sort_values('strike')


class TimeDecayRegimeDetector:
    def analyze_time_decay_regime(self, tex_df, spot_price):
        """Analisa regime de decaimento temporal baseado em TEX"""
        if tex_df.empty:
            return None
        
        total_tex = float(tex_df['total_tex'].sum())
        total_tex_descoberto = float(tex_df['total_tex_descoberto'].sum())
        
        total_oi = (tex_df['call_oi_total'] + tex_df['put_oi_total']).sum()
        if total_oi > 0:
            weighted_days = float((tex_df['days_to_expiration'] * (tex_df['call_oi_total'] + tex_df['put_oi_total'])).sum() / total_oi)
        else:
            weighted_days = float(tex_df['days_to_expiration'].mean())
        
        max_bleed_idx = tex_df['total_tex'].idxmin()
        max_bleed_strike = float(tex_df.loc[max_bleed_idx, 'strike'])
        
        if weighted_days < 15:
            time_pressure = 'HIGH'
            pressure_interpretation = 'Alto decaimento diário'
        elif weighted_days < 30:
            time_pressure = 'MODERATE'
            pressure_interpretation = 'Decaimento moderado'
        else:
            time_pressure = 'LOW'
            pressure_interpretation = 'Baixo decaimento temporal'
        
        if total_tex < -30000:
            market_interpretation = 'Bom para vendedores de opções'
            theta_regime = 'Theta positivo dominante'
        elif total_tex < -10000:
            market_interpretation = 'Moderadamente favorável a vendedores'
            theta_regime = 'Theta equilibrado'
        else:
            market_interpretation = 'Baixo impacto temporal'
            theta_regime = 'Theta neutro'
        
        return {
            'total_tex': total_tex,
            'total_tex_descoberto': total_tex_descoberto,
            'weighted_days': weighted_days,
            'max_bleed_strike': max_bleed_strike,
            'time_pressure': time_pressure,
            'pressure_interpretation': pressure_interpretation,
            'market_interpretation': market_interpretation,
            'theta_regime': theta_regime
        }


class TEXAnalyzer:
    def __init__(self):
        self.data_provider = DataProvider()
        self.tex_calculator = TEXCalculator()
        self.decay_detector = TimeDecayRegimeDetector()
    
    def create_6_charts(self, tex_df, spot_price, symbol, expiration_info=None):
        """Cria os 6 gráficos TEX"""
        if tex_df.empty:
            return None
        
        title = expiration_info["desc"] if expiration_info else ""
        
        subplot_titles = [
            '<b style="color: #ffffff;">Total TEX</b><br><span style="font-size: 12px; color: #888;">Sangramento temporal</span>',
            '<b style="color: #ffffff;">TEX Descoberto</b><br><span style="font-size: 12px; color: #888;">Risco temporal real</span>',
            '<b style="color: #ffffff;">Pressão Temporal</b><br><span style="font-size: 12px; color: #888;">% concentração risco</span>',
            '<b style="color: #ffffff;">Calls vs Puts</b><br><span style="font-size: 12px; color: #888;">TEX por tipo</span>',
            '<b style="color: #ffffff;">TEX Cumulativo</b><br><span style="font-size: 12px; color: #888;">Acúmulo sangramento</span>',
            '<b style="color: #ffffff;">Velocidade</b><br><span style="font-size: 12px; color: #888;">R$/dia sangramento</span>'
        ]
        
        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=subplot_titles,
            vertical_spacing=0.08,
            horizontal_spacing=0.08
        )
        
        strikes = [float(x) for x in tex_df['strike'].tolist()]
        total_tex_values = [float(x) for x in tex_df['total_tex'].tolist()]
        descoberto_values = [float(x) for x in tex_df['total_tex_descoberto'].tolist()]
        call_tex_values = [float(x) for x in tex_df['call_tex'].tolist()]
        put_tex_values = [float(x) for x in tex_df['put_tex'].tolist()]
        
        colors1 = ['#7c2d12' if x < 0 else '#22c55e' for x in total_tex_values]
        fig.add_trace(go.Bar(x=strikes, y=total_tex_values, marker_color=colors1, showlegend=False), row=1, col=1)
        
        colors2 = ['#dc2626' if x < 0 else '#22c55e' for x in descoberto_values]
        fig.add_trace(go.Bar(x=strikes, y=descoberto_values, marker_color=colors2, showlegend=False), row=1, col=2)
        
        total_tex_abs = sum([abs(x) for x in total_tex_values])
        if total_tex_abs > 0:
            concentration_pct = [(abs(x) / total_tex_abs) * 100 for x in total_tex_values]
        else:
            concentration_pct = [0] * len(total_tex_values)
        
        risk_colors = ['#ef4444' if x > 20 else '#f97316' if x > 10 else '#22c55e' for x in concentration_pct]
        fig.add_trace(go.Bar(x=strikes, y=concentration_pct, marker_color=risk_colors, showlegend=False), row=2, col=1)
        
        fig.add_trace(go.Bar(x=strikes, y=call_tex_values, marker_color='#22c55e', showlegend=False), row=2, col=2)
        fig.add_trace(go.Bar(x=strikes, y=put_tex_values, marker_color='#ef4444', showlegend=False), row=2, col=2)
        
        cumulative = np.cumsum(total_tex_values).tolist()
        fig.add_trace(go.Scatter(x=strikes, y=cumulative, mode='lines', 
                                line=dict(color='#06b6d4', width=4),
                                fill='tozeroy',
                                fillcolor='rgba(6, 182, 212, 0.3)',
                                showlegend=False), row=3, col=1)
        
        bleeding_velocity = []
        days_remaining = expiration_info.get('days', 30) if expiration_info else 30
        
        for descoberto in descoberto_values:
            if days_remaining > 0:
                daily_bleed = abs(descoberto) / days_remaining
            else:
                daily_bleed = 0
            bleeding_velocity.append(daily_bleed)
        
        velocity_colors = ['#ef4444' if x > 10000000 else '#f97316' if x > 5000000 else '#eab308' for x in bleeding_velocity]
        fig.add_trace(go.Bar(x=strikes, y=bleeding_velocity, marker_color=velocity_colors, showlegend=False), row=3, col=2)
        
        for row in range(1, 4):
            for col in range(1, 3):
                fig.add_vline(x=spot_price, line=dict(color='#fbbf24', width=2, dash='dash'), row=row, col=col)
                if not (row == 2 and col == 1):
                    fig.add_hline(y=0, line=dict(color='rgba(255,255,255,0.3)', width=1), row=row, col=col)
        
        fig.update_layout(
            title={'text': title, 'x': 0.5, 'xanchor': 'center', 'font': {'size': 20, 'color': '#ffffff', 'family': 'Inter, sans-serif'}},
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
        """Análise principal TEX"""
        logging.info(f"INICIANDO ANALISE TEX - {symbol}")
        
        spot_price = self.data_provider.get_spot_price(symbol)
        if not spot_price:
            raise ValueError("Erro: não foi possível obter cotação")
        
        oplab_df = self.data_provider.get_oplab_historical_data(symbol)
        if oplab_df.empty:
            raise ValueError("Erro: sem dados da Oplab")
        
        oi_breakdown, expiration_info = self.data_provider.get_floqui_oi_breakdown(symbol, expiration_code)
        
        tex_df = self.tex_calculator.calculate_tex(oplab_df, oi_breakdown, spot_price)
        if tex_df.empty:
            raise ValueError("Erro: falha no cálculo TEX")
        
        decay_regime = self.decay_detector.analyze_time_decay_regime(tex_df, spot_price)
        
        if expiration_info and 'days' in expiration_info:
            decay_regime['weighted_days'] = float(expiration_info['days'])
            logging.info(f"CORREÇÃO: Usando dias reais: {expiration_info['days']}")
        
        plot_json = self.create_6_charts(tex_df, spot_price, symbol, expiration_info)
        
        return {
            'symbol': symbol,
            'spot_price': spot_price,
            'decay_regime': decay_regime,
            'strikes_analyzed': len(tex_df),
            'expiration': expiration_info,
            'plot_json': plot_json,
            'real_data_count': int(tex_df['has_real_data'].sum()),
            'success': True
        }


class ThetaService:
    def __init__(self):
        self.analyzer = TEXAnalyzer()
    
    def get_available_expirations(self, ticker):
        return self.analyzer.data_provider.expiration_manager.get_available_expirations_list(ticker)
    
    def analyze_theta_complete(self, ticker, expiration_code=None, days_back=60):
        try:
            result = self.analyzer.analyze(ticker, expiration_code)
            
            decay_regime = result.get('decay_regime', {})
            weighted_days = decay_regime.get('weighted_days', 30)
            
            if weighted_days < 10:
                time_pressure = 'HIGH'
            elif weighted_days < 20:
                time_pressure = 'MODERATE'
            else:
                time_pressure = 'LOW'
            
            decay_regime['time_pressure'] = time_pressure
            
            api_result = {
                'ticker': ticker.replace('.SA', ''),
                'spot_price': result['spot_price'],
                'decay_regime': decay_regime,
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
            logging.error(f"Erro na análise TEX: {e}")
            raise
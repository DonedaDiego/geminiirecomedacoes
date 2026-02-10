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
        
        logging.info(f"🔌 Conectando ao banco PostgreSQL (DEX)...")
        
        try:
            self.db_engine = create_engine(DATABASE_URL)
            
            # TESTA CONEXÃO
            with self.db_engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM opcoes_b3"))
                count = result.fetchone()[0]
                logging.info(f"✅ Conexão OK (DEX) - {count:,} registros na opcoes_b3")
                
        except Exception as e:
            logging.error(f"❌ Erro ao conectar (DEX): {e}")
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
                (latest_data['delta'] != 0) &
                (latest_data['premium'] > 0) &
                (latest_data['strike'] > 0) &
                (latest_data['days_to_maturity'] > 0) &
                (latest_data['days_to_maturity'] <= 60)
            ].copy()
            
            logging.info(f"Dados Delta Oplab: {len(valid_data)} opções")
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
            
            logging.info(f"OI breakdown DEX: {len(oi_breakdown)} strikes")
            return oi_breakdown, expiration
            
        except Exception as e:
            logging.error(f"Erro Floqui: {e}")
            return {}, None


class DEXCalculator:
    
    def calculate_dex(self, oplab_df, oi_breakdown, spot_price):
        """Calcula DEX = Delta × Open Interest × 100"""
        if oplab_df.empty:
            return pd.DataFrame()
        
        price_range = spot_price * 0.25
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
            puts = strike_options[strike_options['type'] == 'PUT']
            
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
            
            call_dex = 0.0
            call_dex_descoberto = 0.0
            if call_data and len(calls) > 0:
                avg_delta = float(calls['delta'].mean())
                call_dex = avg_delta * call_data['total'] * 100
                call_dex_descoberto = avg_delta * call_data['descoberto'] * 100
            
            put_dex = 0.0
            put_dex_descoberto = 0.0
            if put_data and len(puts) > 0:
                avg_delta = float(puts['delta'].mean())
                put_dex = avg_delta * put_data['total'] * 100
                put_dex_descoberto = avg_delta * put_data['descoberto'] * 100
            
            total_dex = call_dex + put_dex
            total_dex_descoberto = call_dex_descoberto + put_dex_descoberto
            
            dex_data.append({
                'strike': float(strike),
                'call_dex': float(call_dex),
                'put_dex': float(put_dex),
                'total_dex': float(total_dex),
                'call_dex_descoberto': float(call_dex_descoberto),
                'put_dex_descoberto': float(put_dex_descoberto),
                'total_dex_descoberto': float(total_dex_descoberto),
                'call_oi_total': int(call_data['total'] if call_data else 0),
                'put_oi_total': int(put_data['total'] if put_data else 0),
                'call_oi_descoberto': int(call_data['descoberto'] if call_data else 0),
                'put_oi_descoberto': int(put_data['descoberto'] if put_data else 0),
                'has_real_data': has_real_call or has_real_put
            })
        
        result_df = pd.DataFrame(dex_data).sort_values('strike')
        logging.info(f"DEX calculado para {len(result_df)} strikes com dados reais")
        
        return result_df


class DirectionalPressureDetector:
    """Detector de pressão direcional baseada em DEX"""
    
    def __init__(self):
        pass
    
    def find_max_pressure_levels(self, dex_df, spot_price):
        """Encontra níveis de máxima pressão direcional"""
        if dex_df.empty:
            return None
        
        # Pressão compradora (DEX positivo máximo)
        max_bullish_idx = dex_df['total_dex'].idxmax()
        bullish_strike = dex_df.loc[max_bullish_idx, 'strike']
        bullish_pressure = dex_df.loc[max_bullish_idx, 'total_dex']
        
        # Pressão vendedora (DEX negativo máximo)
        max_bearish_idx = dex_df['total_dex'].idxmin()
        bearish_strike = dex_df.loc[max_bearish_idx, 'strike']
        bearish_pressure = dex_df.loc[max_bearish_idx, 'total_dex']
        
        # Pressão líquida do mercado
        net_pressure = dex_df['total_dex'].sum()
        net_pressure_descoberto = dex_df['total_dex_descoberto'].sum()
        
        # Análise de concentração
        total_abs_pressure = dex_df['total_dex'].abs().sum()
        concentration_ratio = abs(net_pressure) / total_abs_pressure if total_abs_pressure > 0 else 0
        
        return {
            'bullish_target': bullish_strike,
            'bullish_pressure': bullish_pressure,
            'bearish_target': bearish_strike,
            'bearish_pressure': bearish_pressure,
            'net_pressure': net_pressure,
            'net_pressure_descoberto': net_pressure_descoberto,
            'concentration_ratio': concentration_ratio,
            'market_bias': 'BULLISH' if net_pressure > 1000 else 'BEARISH' if net_pressure < -1000 else 'NEUTRAL'
        }


class DEXAnalyzer:
    def __init__(self):
        self.data_provider = DataProvider()
        self.dex_calculator = DEXCalculator()
    
    def find_targets(self, dex_df, spot_price):
        """Encontra maiores concentrações de calls e puts COM DADOS REAIS"""
        if dex_df.empty:
            return None, None
        
        # FILTRAR APENAS DADOS REAIS
        dex_real_data = dex_df[dex_df['has_real_data'] == True].copy()
        
        if len(dex_real_data) < 2:
            logging.warning("Menos de 2 strikes com dados reais do banco (DEX)")
            return None, None
        
        logging.info(f"DEX Targets: {len(dex_real_data)} strikes com dados reais de {len(dex_df)}")
        
        # MAIOR CONCENTRAÇÃO DE CALLS
        calls_with_oi = dex_real_data[dex_real_data['call_oi_descoberto'] > 0]
        max_calls_strike = None
        if not calls_with_oi.empty:
            max_calls_strike = float(calls_with_oi.loc[calls_with_oi['call_oi_descoberto'].idxmax(), 'strike'])
            max_calls_oi = int(calls_with_oi.loc[calls_with_oi['call_oi_descoberto'].idxmax(), 'call_oi_descoberto'])
            logging.info(f"  Target CALLS: R$ {max_calls_strike:.2f} (OI: {max_calls_oi:,})")
        
        # MAIOR CONCENTRAÇÃO DE PUTS
        puts_with_oi = dex_real_data[dex_real_data['put_oi_descoberto'] > 0]
        max_puts_strike = None
        if not puts_with_oi.empty:
            max_puts_strike = float(puts_with_oi.loc[puts_with_oi['put_oi_descoberto'].idxmax(), 'strike'])
            max_puts_oi = int(puts_with_oi.loc[puts_with_oi['put_oi_descoberto'].idxmax(), 'put_oi_descoberto'])
            logging.info(f"  Target PUTS: R$ {max_puts_strike:.2f} (OI: {max_puts_oi:,})")
        
        return max_calls_strike, max_puts_strike

    def create_6_charts(self, dex_df, spot_price, symbol, max_calls_strike=None, max_puts_strike=None, expiration_info=None):
        """Cria os 6 gráficos DEX"""
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
        
        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=subplot_titles,
            vertical_spacing=0.08,
            horizontal_spacing=0.08
        )
        
        strikes = [float(x) for x in dex_df['strike'].tolist()]
        total_dex_values = [float(x) for x in dex_df['total_dex'].tolist()]
        descoberto_values = [float(x) for x in dex_df['total_dex_descoberto'].tolist()]
        call_dex_values = [float(x) for x in dex_df['call_dex'].tolist()]
        put_dex_values = [float(x) for x in dex_df['put_dex'].tolist()]
        
        # 1. Total DEX
        colors1 = ['#ef4444' if x < 0 else '#22c55e' for x in total_dex_values]
        fig.add_trace(go.Bar(x=strikes, y=total_dex_values, marker_color=colors1, showlegend=False), row=1, col=1)
        
        # 2. DEX Descoberto
        colors2 = ['#ef4444' if x < 0 else '#22c55e' for x in descoberto_values]
        fig.add_trace(go.Bar(x=strikes, y=descoberto_values, marker_color=colors2, showlegend=False), row=1, col=2)
        
        # 3. Pressão Direcional
        pressure_values = [abs(x) for x in descoberto_values]
        fig.add_trace(go.Bar(x=strikes, y=pressure_values, marker_color='#f97316', showlegend=False), row=2, col=1)
        
        # 4. Calls vs Puts
        fig.add_trace(go.Bar(x=strikes, y=call_dex_values, marker_color='#22c55e', showlegend=False), row=2, col=2)
        fig.add_trace(go.Bar(x=strikes, y=put_dex_values, marker_color='#ef4444', showlegend=False), row=2, col=2)
        
        # 5. DEX Cumulativo - COM PREENCHIMENTO
        cumulative = np.cumsum(total_dex_values).tolist()
        fig.add_trace(go.Scatter(
            x=strikes, 
            y=cumulative, 
            mode='lines', 
            line=dict(color='#a855f7', width=4),
            fill='tozeroy',
            fillcolor='rgba(168, 85, 247, 0.3)',
            showlegend=False
        ), row=3, col=1)
        
        # 6. Momentum
        momentum_values = []
        for i in range(len(descoberto_values)):
            if i > 0:
                momentum = descoberto_values[i] - descoberto_values[i-1]
            else:
                momentum = descoberto_values[i]
            momentum_values.append(momentum)
        
        momentum_colors = ['#22c55e' if x > 0 else '#ef4444' for x in momentum_values]
        fig.add_trace(go.Bar(x=strikes, y=momentum_values, marker_color=momentum_colors, showlegend=False), row=3, col=2)
        
        # Linhas de referência
        for row in range(1, 4):
            for col in range(1, 3):
                fig.add_vline(x=spot_price, line=dict(color='#fbbf24', width=2, dash='dash'), row=row, col=col)
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
        
        pressure_detector = DirectionalPressureDetector()
        pressure_levels = pressure_detector.find_max_pressure_levels(dex_df, spot_price)
        
        max_calls_strike, max_puts_strike = self.find_targets(dex_df, spot_price)
        
        plot_json = self.create_6_charts(
            dex_df, 
            spot_price, 
            symbol, 
            max_calls_strike=max_calls_strike,
            max_puts_strike=max_puts_strike,
            expiration_info=expiration_info
        )
        
        net_dex = float(dex_df['total_dex'].sum())
        net_dex_descoberto = float(dex_df['total_dex_descoberto'].sum())
        real_data_count = int(dex_df['has_real_data'].sum())
        
        return {
            'symbol': symbol,
            'spot_price': spot_price,
            'pressure_levels': pressure_levels,
            'net_dex': net_dex,
            'net_dex_descoberto': net_dex_descoberto,
            'strikes_analyzed': len(dex_df),
            'expiration': expiration_info,
            'plot_json': plot_json,
            'real_data_count': real_data_count,
            'dex_df': dex_df,
            'success': True
        }


class DeltaService:
    def __init__(self):
        self.analyzer = DEXAnalyzer()
    
    def get_available_expirations(self, ticker):
        return self.analyzer.data_provider.expiration_manager.get_available_expirations_list(ticker)
    
    def analyze_delta_complete(self, ticker, expiration_code=None, days_back=60):
        try:
            result = self.analyzer.analyze(ticker, expiration_code)
            
            pressure_levels = result.get('pressure_levels', {})
            net_dex_descoberto = result['net_dex_descoberto']
            
            # Calcular pressão restante
            dex_df = result.get('dex_df', None)
            spot_price = result['spot_price']
            
            remaining_pressure = 0
            if dex_df is not None and len(dex_df) > 0:
                if 'total_dex' in dex_df.columns:
                    cumulative_values = np.cumsum(dex_df['total_dex'].values)
                    max_cumulative = max(cumulative_values) if len(cumulative_values) > 0 else 0
                    
                    # Encontrar índice mais próximo do spot price
                    current_spot_idx = None
                    for i, strike in enumerate(dex_df['strike'].values):
                        if current_spot_idx is None or abs(strike - spot_price) < abs(dex_df['strike'].iloc[current_spot_idx] - spot_price):
                            current_spot_idx = i
                    
                    if current_spot_idx is not None:
                        current_cumulative = cumulative_values[current_spot_idx]
                        remaining_pressure = max_cumulative - current_cumulative
            
            # ESTRUTURA IGUAL AO GEX
            dex_levels = {
                'total_dex': result['net_dex'],
                'total_dex_descoberto': net_dex_descoberto,
                'market_bias': pressure_levels.get('market_bias', 'NEUTRAL'),
                'concentration_ratio': pressure_levels.get('concentration_ratio', 0),
                'remaining_pressure': remaining_pressure
            }
            
            api_result = {
                'ticker': ticker.replace('.SA', ''),
                'spot_price': result['spot_price'],
                'dex_levels': dex_levels,
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
            logging.error(f"Erro na análise DEX: {e}")
            raise
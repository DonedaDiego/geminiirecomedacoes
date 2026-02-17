"""
gamma_service.py - GEX Analysis COM DADOS DO BANCO POSTGRESQL
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


class LiquidityManager:
    
    def __init__(self):
        self.high_liquidity = {
            'BOVA11': 6,
            'PETR4': 6,
            'VALE3': 6,
            'BBAS3': 6,
            'B3SA3': 6,
            'ITSA4': 6,
            'BBDC4': 6,
            'MGLU3': 6,
        }
        
        self.medium_liquidity = {
            'ITUB4': 9,
            'ABEV3': 9,
            'WEGE3': 9,
            'RENT3': 9,
            'AXIA3': 9,
            'PRIO3': 9,
            'SUZB3': 9,
            'EMJR3': 9,
            'RADL3': 9,
            'BRAV3': 9,
            'BPAC11':9,
        }
        
        self.low_liquidity_range = 13
        self.default_range = 12
    
    def get_flip_range(self, symbol):
        """Retorna o range para busca de flip baseado na liquidez"""
        symbol_clean = symbol.replace('.SA', '').upper()
        
        if symbol_clean in self.high_liquidity:
            range_pct = self.high_liquidity[symbol_clean]
            logging.info(f"Ativo {symbol_clean}: Liquidez ALTA - Range {range_pct}%")
            return range_pct
        
        if symbol_clean in self.medium_liquidity:
            range_pct = self.medium_liquidity[symbol_clean]
            logging.info(f"Ativo {symbol_clean}: Liquidez MEDIA - Range {range_pct}%")
            return range_pct
        
        logging.info(f"Ativo {symbol_clean}: Liquidez BAIXA (auto) - Range {self.low_liquidity_range}%")
        return self.low_liquidity_range
    
    def get_liquidity_info(self, symbol):
        """Retorna informações completas de liquidez"""
        symbol_clean = symbol.replace('.SA', '').upper()
        
        if symbol_clean in self.high_liquidity:
            return {
                'range': self.high_liquidity[symbol_clean],
                'category': 'ALTA'
            }
        
        if symbol_clean in self.medium_liquidity:
            return {
                'range': self.medium_liquidity[symbol_clean],
                'category': 'MEDIA'
            }
        
        return {
            'range': self.low_liquidity_range,
            'category': 'BAIXA'
        }


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
        
        #  CONEXÃO COM BANCO - RAILWAY COMPATIBLE
        DATABASE_URL = os.getenv('DATABASE_URL')
        
        if not DATABASE_URL:
            # Fallback para variáveis individuais
            DB_HOST = os.getenv('PGHOST') or os.getenv('DB_HOST', 'localhost')
            DB_NAME = os.getenv('PGDATABASE') or os.getenv('DB_NAME', 'postgres')
            DB_USER = os.getenv('PGUSER') or os.getenv('DB_USER', 'postgres')
            DB_PASSWORD = os.getenv('PGPASSWORD') or os.getenv('DB_PASSWORD', '')
            DB_PORT = os.getenv('PGPORT') or os.getenv('DB_PORT', '5432')
            
            DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        
        logging.info(f"Conectando ao banco: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'local'}")
        self.db_engine = create_engine(DATABASE_URL)
        
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
                
            logging.error(f"Não foi possível obter cotação para {symbol}")
            return None
            
        except Exception as e:
            logging.error(f"Erro ao buscar cotação: {e}")
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
                (latest_data['gamma'] > 0) &
                (latest_data['premium'] > 0) &
                (latest_data['strike'] > 0) &
                (latest_data['days_to_maturity'] > 0) &
                (latest_data['days_to_maturity'] <= 60)
            ].copy()
            
            logging.info(f"Dados históricos Oplab: {len(valid_data)} opções")
            return valid_data
            
        except Exception as e:
            logging.error(f"Erro ao buscar dados Oplab: {e}")
            return pd.DataFrame()
    
    def get_floqui_oi_breakdown(self, symbol, expiration_code=None):
        """BUSCA DO BANCO DE DADOS POSTGRESQL"""
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
            
            #  NOVA ESTRUTURA - USA STRING COMO CHAVE
            oi_breakdown = {}
            for _, row in df.iterrows():
                strike = float(row['preco_exercicio'])
                option_type = str(row['tipo_opcao']).upper()
                oi_total = int(row['qtd_total'])
                oi_descoberto = int(row['qtd_descoberto'])
                
                if strike > 0 and oi_total > 0:
                    #  CHAVE COMO STRING: "7.25_CALL"
                    key = f"{strike}_{option_type}"
                    oi_breakdown[key] = {
                        'strike': strike,
                        'type': option_type,
                        'total': oi_total,
                        'descoberto': oi_descoberto,
                        'travado': int(row['qtd_trava']),
                        'coberto': int(row['qtd_coberto'])
                    }
            
            logging.info(f"Floqui OI breakdown: {len(oi_breakdown)} strikes")
            return oi_breakdown, expiration
            
        except Exception as e:
            logging.error(f"Erro Floqui: {e}")
            return {}, None


class GEXAnalyzer:
    def __init__(self):
        self.data_provider = DataProvider()
        self.liquidity_manager = LiquidityManager()
    
    def calculate_gex(self, oplab_df, oi_breakdown, spot_price):
        if oplab_df.empty:
            logging.error("DataFrame vazio")
            return pd.DataFrame()
        
        price_range = spot_price * 0.20
        mask1 = oplab_df['strike'] >= (spot_price - price_range)
        mask2 = oplab_df['strike'] <= (spot_price + price_range)
        valid_options = oplab_df[mask1 & mask2].copy()
        
        if valid_options.empty:
            logging.error("Nenhuma opção válida")
            return pd.DataFrame()
        
        gex_data = []
        unique_strikes = valid_options['strike'].unique()
        
        for strike in unique_strikes:
            strike_mask = valid_options['strike'] == strike
            strike_options = valid_options[strike_mask]
            
            call_mask = strike_options['type'] == 'CALL'
            put_mask = strike_options['type'] == 'PUT'
            
            calls = strike_options[call_mask]
            puts = strike_options[put_mask]
            
            call_data = None
            put_data = None
            has_real_call = False
            has_real_put = False
            
            #  BUSCA COM CHAVE STRING
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
            
            call_gex = 0.0
            call_gex_descoberto = 0.0
            if call_data and len(calls) > 0:
                avg_gamma = float(calls['gamma'].mean())
                call_gex = avg_gamma * call_data['total'] * spot_price * 100
                call_gex_descoberto = avg_gamma * call_data['descoberto'] * spot_price * 100
            
            put_gex = 0.0
            put_gex_descoberto = 0.0
            if put_data and len(puts) > 0:
                avg_gamma = float(puts['gamma'].mean())
                put_gex = -(avg_gamma * put_data['total'] * spot_price * 100)
                put_gex_descoberto = -(avg_gamma * put_data['descoberto'] * spot_price * 100)
            
            total_gex = call_gex + put_gex
            total_gex_descoberto = call_gex_descoberto + put_gex_descoberto
            
            gex_data.append({
                'strike': float(strike),
                'call_gex': float(call_gex),
                'put_gex': float(put_gex),
                'total_gex': float(total_gex),
                'total_gex_descoberto': float(total_gex_descoberto),
                'call_oi_total': int(call_data['total'] if call_data else 0),
                'put_oi_total': int(put_data['total'] if put_data else 0),
                'call_oi_descoberto': int(call_data['descoberto'] if call_data else 0),
                'put_oi_descoberto': int(put_data['descoberto'] if put_data else 0),
                'has_real_data': True
            })
        
        result_df = pd.DataFrame(gex_data).sort_values('strike')
        logging.info(f"GEX calculado para {len(result_df)} strikes com dados reais")
        
        return result_df
    
    def find_gamma_flip(self, gex_df, spot_price, symbol):
        if gex_df.empty or len(gex_df) < 2:
            logging.warning("Dados insuficientes para analise de flip")
            return spot_price
        
        max_distance_pct = self.liquidity_manager.get_flip_range(symbol)
        
        def search_flips(df, data_source_name):
            flip_candidates = []
            
            for i in range(len(df) - 1):
                current_strike = df.iloc[i]['strike']
                next_strike = df.iloc[i+1]['strike']
                current_gex = df.iloc[i]['total_gex_descoberto']
                next_gex = df.iloc[i+1]['total_gex_descoberto']
                
                if (current_gex > 0 and next_gex < 0) or (current_gex < 0 and next_gex > 0):
                    if abs(current_gex) + abs(next_gex) > 0:
                        flip_strike = current_strike + (next_strike - current_strike) * abs(current_gex) / (abs(current_gex) + abs(next_gex))
                    else:
                        flip_strike = (current_strike + next_strike) / 2
                    
                    distance_from_spot = abs(flip_strike - spot_price)
                    distance_pct = distance_from_spot / spot_price * 100
                    
                    flip_position = "ACIMA" if flip_strike > spot_price else "ABAIXO"
                    flip_direction = "NEG_TO_POS" if current_gex < 0 and next_gex > 0 else "POS_TO_NEG"
                    
                    flip_candidates.append({
                        'strike': flip_strike,
                        'distance_from_spot': distance_from_spot,
                        'distance_pct': distance_pct,
                        'left_strike': current_strike,
                        'right_strike': next_strike,
                        'left_gex': current_gex,
                        'right_gex': next_gex,
                        'confidence': abs(current_gex) + abs(next_gex),
                        'flip_position': flip_position,
                        'flip_direction': flip_direction,
                        'data_source': data_source_name
                    })
            
            return flip_candidates
        
        ranges_to_try = [max_distance_pct, 10, 15, 20, 25, 30]
        flip_candidates = []
        used_range = max_distance_pct
        
        for range_pct in ranges_to_try:
            max_distance = spot_price * (range_pct / 100)
            
            valid_df = gex_df[
                (gex_df['strike'] >= spot_price - max_distance) &
                (gex_df['strike'] <= spot_price + max_distance)
            ].copy()
            
            if valid_df.empty:
                continue
            
            valid_df = valid_df.sort_values('strike').reset_index(drop=True)
            
            real_data_df = valid_df[valid_df['has_real_data'] == True].copy()
            
            if len(real_data_df) >= 2:
                flip_candidates = search_flips(real_data_df, "REAL")
            
            if not flip_candidates and len(valid_df) >= 2:
                flip_candidates = search_flips(valid_df, "MISTO")
            
            if flip_candidates:
                used_range = range_pct
                if range_pct != max_distance_pct:
                    logging.info(f"Flip encontrado expandindo range de {max_distance_pct}% para {range_pct}%")
                break
        
        if not flip_candidates:
            logging.warning(f"FLIP NAO ENCONTRADO ate 30% - usando spot R$ {spot_price:.2f}")
            return spot_price
        
        logging.info(f"BUSCANDO GAMMA FLIP")
        logging.info(f"Range usado: {used_range}%")
        logging.info(f"Encontrou {len(flip_candidates)} flip(s)")
        
        spot_strike_idx = (gex_df['strike'] - spot_price).abs().argsort()[0]
        spot_gex = gex_df.iloc[spot_strike_idx]['total_gex_descoberto']
        spot_regime = "SHORT_GAMMA" if spot_gex < -1000 else ("LONG_GAMMA" if spot_gex > 1000 else "NEUTRAL")
        
        logging.info(f"REGIME NO SPOT: {spot_regime}")
        
        for candidate in flip_candidates:
            logging.info(f"FLIP CANDIDATO: Strike={candidate['strike']:.2f}, Dist={candidate['distance_from_spot']:.2f}")
        
        original_candidates = flip_candidates.copy()
        
        if spot_regime == "SHORT_GAMMA":
            flip_candidates = [f for f in flip_candidates if f['flip_position'] == "ACIMA"]
        elif spot_regime == "LONG_GAMMA":
            flip_candidates = [f for f in flip_candidates if f['flip_position'] == "ABAIXO"]
        
        if not flip_candidates:
            logging.warning(f"Nenhum flip na direcao esperada ({spot_regime}), usando mais proximo")
            flip_candidates = original_candidates
        
        flip_candidates.sort(key=lambda x: x['distance_from_spot'])
        best_flip = flip_candidates[0]
        
        logging.info(f"GAMMA FLIP SELECIONADO")
        logging.info(f"  Strike: R$ {best_flip['strike']:.2f}")
        logging.info(f"  Fonte: {best_flip['data_source']}")
        logging.info(f"  Posicao: {best_flip['flip_position']} do spot")
        logging.info(f"  Distancia: {best_flip['distance_pct']:.2f}%")
        
        regime = "POSITIVE GAMMA" if spot_price > best_flip['strike'] else "NEGATIVE GAMMA"
        
        logging.info(f"REGIME CALCULADO: {regime}")
        
        if (regime == "POSITIVE GAMMA" and spot_regime == "SHORT_GAMMA") or (regime == "NEGATIVE GAMMA" and spot_regime == "LONG_GAMMA"):
            logging.warning("INCONSISTENCIA: Regime calculado nao bate com GEX no spot")
        else:
            logging.info("Regime consistente com GEX no spot")
        
        return best_flip['strike']
    
    def create_6_charts(self, gex_df, spot_price, symbol, flip_strike=None, expiration_info=None):
        if gex_df.empty:
            return None
        
        gex_df = gex_df.sort_values('strike').reset_index(drop=True)
        
        title = expiration_info["desc"] if expiration_info else ""
        
        subplot_titles = [
            '<b style="color: #ffffff;">Total GEX</b><br><span style="font-size: 12px; color: #888;">Exposição gamma total</span>',
            '<b style="color: #ffffff;">GEX Descoberto</b><br><span style="font-size: 12px; color: #888;">Posições descobertas</span>',
            '<b style="color: #ffffff;">Regime por Strike</b><br><span style="font-size: 12px; color: #888;">Long vs Short gamma</span>',
            '<b style="color: #ffffff;">Calls vs Puts</b><br><span style="font-size: 12px; color: #888;">Sentimento direcional</span>',
            '<b style="color: #ffffff;">GEX Cumulativo</b><br><span style="font-size: 12px; color: #888;">Fluxo de pressão</span>',
            '<b style="color: #ffffff;">Open Interest</b><br><span style="font-size: 12px; color: #888;">Volume contratos</span>'
        ]
        
        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=subplot_titles,
            vertical_spacing=0.08,
            horizontal_spacing=0.08
        )
        
        strikes = [float(x) for x in gex_df['strike'].tolist()]
        total_gex_values = [float(x) for x in gex_df['total_gex'].tolist()]
        descoberto_values = [float(x) for x in gex_df['total_gex_descoberto'].tolist()]
        call_gex_values = [float(x) for x in gex_df['call_gex'].tolist()]
        put_gex_values = [float(x) for x in gex_df['put_gex'].tolist()]
        call_oi = [int(x) for x in gex_df['call_oi_total'].tolist()]
        put_oi = [int(x) for x in gex_df['put_oi_total'].tolist()]
        
        colors1 = ['#ef4444' if x < 0 else '#22c55e' for x in total_gex_values]
        fig.add_trace(go.Bar(x=strikes, y=total_gex_values, marker_color=colors1, showlegend=False), row=1, col=1)
        
        colors2 = ['#ef4444' if x < 0 else '#22c55e' for x in descoberto_values]
        fig.add_trace(go.Bar(x=strikes, y=descoberto_values, marker_color=colors2, showlegend=False), row=1, col=2)
        
        colors3 = ['#22c55e' if x > 1000 else '#ef4444' if x < -1000 else '#6b7280' for x in descoberto_values]
        fig.add_trace(go.Bar(x=strikes, y=[abs(x) for x in descoberto_values], marker_color=colors3, showlegend=False), row=2, col=1)
        
        fig.add_trace(go.Bar(x=strikes, y=call_gex_values, marker_color='#22c55e', name='Calls', showlegend=False), row=2, col=2)
        fig.add_trace(go.Bar(x=strikes, y=put_gex_values, marker_color='#ef4444', name='Puts', showlegend=False), row=2, col=2)
        
        cumulative = np.cumsum(total_gex_values).tolist()
        fig.add_trace(go.Scatter(x=strikes, y=cumulative, mode='lines+markers', 
                                line=dict(color='#06b6d4', width=3), 
                                marker=dict(color='#06b6d4', size=6),
                                showlegend=False), row=3, col=1)
        
        oi_total = [c + p for c, p in zip(call_oi, put_oi)]
        fig.add_trace(go.Bar(x=strikes, y=oi_total, marker_color='#a855f7', showlegend=False), row=3, col=2)
        
        for row in range(1, 4):
            for col in range(1, 3):
                fig.add_vline(x=spot_price, line=dict(color='#fbbf24', width=3, dash='dash'), row=row, col=col)
                
                if flip_strike:
                    fig.add_vline(x=flip_strike, line=dict(color='#f97316', width=3, dash='dot'), row=row, col=col)
                
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
        
        fig.update_xaxes(
            gridcolor='rgba(255,255,255,0.1)', 
            color='#ffffff',
            showgrid=True,
            zeroline=False
        )
        fig.update_yaxes(
            gridcolor='rgba(255,255,255,0.1)', 
            color='#ffffff',
            showgrid=True,
            zeroline=False
        )
        
        return fig.to_json()
    
    def identify_walls(self, gex_df, spot_price):
        if gex_df.empty:
            return []
        
        walls = []
        
        valid_strikes = gex_df[
            (gex_df['call_oi_descoberto'] > 0) | (gex_df['put_oi_descoberto'] > 0)
        ].copy()
        
        if valid_strikes.empty:
            logging.warning("Nenhum strike com OI descoberto válido")
            return []
        
        calls_with_oi = valid_strikes[valid_strikes['call_oi_descoberto'] > 0]
        if not calls_with_oi.empty:
            max_call_row = calls_with_oi.loc[calls_with_oi['call_oi_descoberto'].idxmax()]
            
            walls.append({
                'strike': float(max_call_row['strike']),
                'gamma_descoberto': float(max_call_row['total_gex_descoberto']),
                'oi_descoberto': int(max_call_row['call_oi_descoberto']),
                'intensity': 1.0,
                'type': 'Support',
                'distance_pct': float(abs(max_call_row['strike'] - spot_price) / spot_price * 100),
                'strength': 'Strong'
            })
        
        puts_with_oi = valid_strikes[valid_strikes['put_oi_descoberto'] > 0]
        if not puts_with_oi.empty:
            max_put_row = puts_with_oi.loc[puts_with_oi['put_oi_descoberto'].idxmax()]
            
            walls.append({
                'strike': float(max_put_row['strike']),
                'gamma_descoberto': float(max_put_row['total_gex_descoberto']),
                'oi_descoberto': int(max_put_row['put_oi_descoberto']),
                'intensity': 1.0,
                'type': 'Resistance',
                'distance_pct': float(abs(max_put_row['strike'] - spot_price) / spot_price * 100),
                'strength': 'Strong'
            })
        
        logging.info(f"WALLS: {len(walls)}")
        for wall in walls:
            logging.info(f"  {wall['type']}: R${wall['strike']:.2f} - OI: {wall['oi_descoberto']:,}")
        
        return walls
    
    def analyze(self, symbol, expiration_code=None):
        logging.info(f"INICIANDO ANALISE GEX - {symbol}")
        
        liquidity_info = self.liquidity_manager.get_liquidity_info(symbol)
        logging.info(f"Liquidez: {liquidity_info['category']} - Range ATM: {liquidity_info['range']}%")
        
        spot_price = self.data_provider.get_spot_price(symbol)
        if not spot_price:
            raise ValueError("Erro: não foi possível obter cotação")
        
        logging.info(f"Spot price: R$ {spot_price:.2f}")
        
        oplab_df = self.data_provider.get_oplab_historical_data(symbol)
        if oplab_df.empty:
            raise ValueError("Erro: sem dados da Oplab")
        
        oi_breakdown, expiration_info = self.data_provider.get_floqui_oi_breakdown(symbol, expiration_code)
        
        gex_df = self.calculate_gex(oplab_df, oi_breakdown, spot_price)
        if gex_df.empty:
            raise ValueError("Erro: falha no cálculo GEX")
        
        gex_df = gex_df.sort_values('strike').reset_index(drop=True)
        
        flip_strike = self.find_gamma_flip(gex_df, spot_price, symbol)
        plot_json = self.create_6_charts(gex_df, spot_price, symbol, flip_strike, expiration_info)
        walls = self.identify_walls(gex_df, spot_price)
        
        cumulative_total = np.cumsum(gex_df['total_gex'].values)
        cumulative_descoberto = np.cumsum(gex_df['total_gex_descoberto'].values)
        
        net_gex = float(cumulative_total[-1])
        net_gex_descoberto = float(cumulative_descoberto[-1])
        
        real_data_count = int(gex_df['has_real_data'].sum())
        
        gex_levels = {
            'total_gex': net_gex,
            'total_gex_descoberto': net_gex_descoberto,
            'zero_gamma_level': flip_strike if flip_strike else spot_price,
            'market_bias': 'SUPPRESSIVE' if net_gex > 1000000 else 'EXPLOSIVE' if net_gex < -1000000 else 'NEUTRAL'
        }
        
        logging.info(f"\nRESULTADOS:")
        logging.info(f"Cotação: R$ {spot_price:.2f}")
        if expiration_info:
            logging.info(f"Vencimento: {expiration_info['desc']}")
        if flip_strike:
            distance = ((spot_price - flip_strike) / flip_strike) * 100
            regime = "POSITIVE GAMMA" if spot_price > flip_strike else "NEGATIVE GAMMA"
            logging.info(f"Gamma Flip: R$ {flip_strike:.2f} ({distance:+.1f}%)")
            logging.info(f"Regime: {regime}")
        logging.info(f"GEX Total: {net_gex:,.0f}")
        logging.info(f"GEX Descoberto: {net_gex_descoberto:,.0f}")
        logging.info(f"Strikes: {len(gex_df)} ({real_data_count} reais)")
        
        return {
            'symbol': symbol,
            'spot_price': spot_price,
            'gex_levels': gex_levels,
            'flip_strike': flip_strike,
            'net_gex': net_gex,
            'net_gex_descoberto': net_gex_descoberto,
            'strikes_analyzed': len(gex_df),
            'expiration': expiration_info,
            'plot_json': plot_json,
            'walls': walls,
            'real_data_count': real_data_count,
            'liquidity_info': liquidity_info,
            'success': True
        }


class GammaService:
    def __init__(self):
        self.analyzer = GEXAnalyzer()
    
    def get_available_expirations(self, ticker):
        return self.analyzer.data_provider.expiration_manager.get_available_expirations_list(ticker)
    
    def analyze_gamma_complete(self, ticker, expiration_code=None, days_back=60):
        try:
            result = self.analyzer.analyze(ticker, expiration_code)
            
            flip_strike = result.get('flip_strike')
            spot_price = result['spot_price']
            
            if flip_strike:
                regime = 'Long Gamma' if spot_price > flip_strike else 'Short Gamma'
            else:
                regime = 'Long Gamma' if result['net_gex_descoberto'] > 0 else 'Short Gamma'
            
            api_result = {
                'ticker': ticker.replace('.SA', ''),
                'spot_price': spot_price,
                'gex_levels': result['gex_levels'],
                'flip_strike': flip_strike,
                'regime': regime,
                'plot_json': result['plot_json'],
                'walls': result['walls'],
                'options_count': result['strikes_analyzed'],
                'data_quality': {
                    'expiration': result['expiration']['desc'] if result['expiration'] else None,
                    'real_data_count': result['real_data_count'],
                    'liquidity_category': result['liquidity_info']['category'],
                    'atm_range_pct': result['liquidity_info']['range']
                },
                'success': True
            }
            
            return convert_to_json_serializable(api_result)
            
        except Exception as e:
            logging.error(f"Erro na análise GEX: {e}")
            raise
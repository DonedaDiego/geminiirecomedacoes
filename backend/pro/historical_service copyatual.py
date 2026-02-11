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
    """Converte tipos numpy/pandas para Python nativo"""
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    
    if isinstance(obj, (list, tuple)):
        return [convert_to_json_serializable(item) for item in obj]
    
    if isinstance(obj, dict):
        return {key: convert_to_json_serializable(value) for key, value in obj.items()}
    
    if pd.isna(obj):
        return None
    
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
    """Gerencia ranges de ATM baseado na liquidez do ativo"""
    
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
            'EMBJ3': 9,            
            'RADL3': 9,
            'BRAV3': 9,
        }
        
        self.low_liquidity_range = 13
    
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
            return {'range': self.high_liquidity[symbol_clean], 'category': 'ALTA'}
        
        if symbol_clean in self.medium_liquidity:
            return {'range': self.medium_liquidity[symbol_clean], 'category': 'MEDIA'}
        
        return {'range': self.low_liquidity_range, 'category': 'BAIXA'}


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
        
        # ✅ CONEXÃO COM BANCO DE DADOS - RAILWAY POSTGRESQL
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
        
        logging.info(f"🔌 Conectando ao banco PostgreSQL (Historical)...")
        
        try:
            self.db_engine = create_engine(DATABASE_URL)
            
            with self.db_engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM opcoes_b3"))
                count = result.fetchone()[0]
                logging.info(f"✅ Conexão OK (Historical) - {count:,} registros")
                
        except Exception as e:
            logging.error(f"❌ Erro ao conectar (Historical): {e}")
            raise
    
    def get_last_business_day(self):
        """Busca a última data_referencia disponível NO BANCO"""
        try:
            query = text("""
                SELECT MAX(data_referencia) as ultima_data
                FROM opcoes_b3
            """)
            
            with self.db_engine.connect() as conn:
                result = conn.execute(query)
                row = result.fetchone()
                ultima_data = row[0] if row and row[0] else None
            
            if not ultima_data:
                logging.error("Nenhuma data_referencia encontrada no banco")
                return datetime.now().date()
            
            logging.info(f"✅ Última data_referencia no banco: {ultima_data}")
            return ultima_data if isinstance(ultima_data, datetime) else datetime.combine(ultima_data, datetime.min.time())
            
        except Exception as e:
            logging.error(f"Erro ao buscar última data do banco: {e}")
            return datetime.now().date()
    
    def get_business_days(self, days_back=5):
        """Busca as últimas N datas_referencia REAIS do banco"""
        try:
            query = text("""
                SELECT DISTINCT data_referencia
                FROM opcoes_b3
                ORDER BY data_referencia DESC
                LIMIT :limit
            """)
            
            with self.db_engine.connect() as conn:
                result = conn.execute(query, {'limit': days_back})
                rows = result.fetchall()
            
            if not rows:
                logging.error("Nenhuma data_referencia encontrada no banco")
                return []
            
            # Converter para datetime e ordenar (mais antiga primeiro)
            dates = []
            for row in rows:
                data_ref = row[0]
                if isinstance(data_ref, datetime):
                    dates.append(data_ref)
                else:
                    dates.append(datetime.combine(data_ref, datetime.min.time()))
            
            dates_sorted = sorted(dates)
            
            logging.info(f"✅ Últimas {len(dates_sorted)} datas_referencia do banco:")
            for d in dates_sorted:
                logging.info(f"   📅 {d.strftime('%Y-%m-%d')}")
            
            return dates_sorted
            
        except Exception as e:
            logging.error(f"Erro ao buscar datas do banco: {e}")
            return []
    
    def get_spot_price(self, symbol):
        """Busca cotação atual (tempo real)"""
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
                
            logging.error(f"Erro ao obter cotação para {symbol}")
            return None
            
        except Exception as e:
            logging.error(f"Erro ao buscar cotação: {e}")
            return None
    
    def get_historical_spot_price(self, symbol, target_date):
        """✅ NOVO: Busca cotação HISTÓRICA de uma data específica"""
        try:
            ticker_yf = f"{symbol}.SA" if not symbol.endswith('.SA') else symbol
            stock = yf.Ticker(ticker_yf)
            
            # Busca dados do dia específico + margem de segurança
            date_str = target_date.strftime('%Y-%m-%d')
            next_day = (target_date + timedelta(days=3)).strftime('%Y-%m-%d')
            
            hist = stock.history(start=date_str, end=next_day)
            
            if not hist.empty:
                # Pega o fechamento mais próximo da data alvo
                hist_filtered = hist[hist.index.date >= target_date.date()]
                if not hist_filtered.empty:
                    price = float(hist_filtered['Close'].iloc[0])
                    logging.info(f"✅ Spot histórico {date_str}: R$ {price:.2f}")
                    return price
            
            logging.warning(f"⚠️ Sem dados históricos para {date_str}, tentando Oplab...")
            
            # Fallback: tentar Oplab histórico
            symbol_clean = symbol.replace('.SA', '')
            to_date = (target_date + timedelta(days=1)).strftime('%Y-%m-%d')
            from_date = (target_date - timedelta(days=1)).strftime('%Y-%m-%d')
            
            url = f"{self.oplab_url}/market/historical/{symbol_clean}/{from_date}/{to_date}"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    price = float(data[-1].get('close', 0))
                    if price > 0:
                        logging.info(f"✅ Spot histórico Oplab {date_str}: R$ {price:.2f}")
                        return price
            
            logging.error(f"❌ Não foi possível obter spot histórico para {date_str}")
            return None
            
        except Exception as e:
            logging.error(f"Erro ao buscar spot histórico {target_date}: {e}")
            return None
    
    def get_oplab_historical_data(self, symbol, target_date=None):
        try:
            symbol_clean = symbol.replace('.SA', '')
            
            to_date = datetime.now().strftime('%Y-%m-%d')
            from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            url = f"{self.oplab_url}/market/historical/options/{symbol_clean}/{from_date}/{to_date}"
            response = requests.get(url, headers=self.headers, timeout=15)
            
            if response.status_code != 200:
                logging.error(f"Erro na API Oplab: {response.status_code}")
                return pd.DataFrame()
            
            data = response.json()
            if not data:
                return pd.DataFrame()
            
            df = pd.DataFrame(data)
            df['time'] = pd.to_datetime(df['time'])
            
            if target_date:
                target_date_obj = target_date.date() if isinstance(target_date, datetime) else target_date
                filtered_data = df[df['time'].dt.date == target_date_obj].copy()
                
                if filtered_data.empty:
                    logging.warning(f"Nenhum dado Oplab encontrado para {target_date_obj}")
                    logging.info(f"Datas disponíveis: {sorted(df['time'].dt.date.unique())}")
                    return pd.DataFrame()
                
                logging.info(f"✅ Oplab filtrado para {target_date_obj}: {len(filtered_data)} opções")
                latest_data = filtered_data
            else:
                latest_date = df['time'].max().date()
                latest_data = df[df['time'].dt.date == latest_date].copy()
                logging.info(f"Oplab data mais recente ({latest_date}): {len(latest_data)} opções")
            
            valid_data = latest_data[
                (latest_data['gamma'] > 0) &
                (latest_data['premium'] > 0) &
                (latest_data['strike'] > 0) &
                (latest_data['days_to_maturity'] > 0) &
                (latest_data['days_to_maturity'] <= 60)
            ].copy()
            
            logging.info(f"Dados Oplab válidos: {len(valid_data)} opções")
            return valid_data
            
        except Exception as e:
            logging.error(f"Erro ao buscar dados Oplab: {e}")
            return pd.DataFrame()
    
    def get_floqui_historical(self, ticker, vencimento, dt_referencia):
        """BUSCA DO BANCO DE DADOS POSTGRESQL - histórico"""
        try:
            ticker_clean = ticker.replace('.SA', '')
            
            # Converter vencimento string para datetime
            exp_date = datetime.strptime(vencimento, '%Y%m%d')
            
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
                AND data_referencia = :data_ref
                ORDER BY preco_exercicio
            """)
            
            with self.db_engine.connect() as conn:
                result = conn.execute(query, {
                    'symbol': ticker_clean,
                    'vencimento': exp_date,
                    'data_ref': dt_referencia
                })
                
                rows = result.fetchall()
            
            if not rows:
                logging.warning(f"Sem dados banco: VENC={vencimento} DATA={dt_referencia.strftime('%Y-%m-%d')}")
                return {}
            
            # ✅ ESTRUTURA COM STRING COMO CHAVE
            oi_breakdown = {}
            for row in rows:
                strike = float(row[0])
                option_type = str(row[1]).upper()
                oi_total = int(row[2])
                oi_descoberto = int(row[3])
                
                if strike > 0 and oi_total > 0:
                    key = f"{strike}_{option_type}"
                    oi_breakdown[key] = {
                        'strike': strike,
                        'type': option_type,
                        'total': oi_total,
                        'descoberto': oi_descoberto,
                        'travado': int(row[4]),
                        'coberto': int(row[5])
                    }
            
            logging.info(f"✅ Banco VENC={vencimento} DATA={dt_referencia.strftime('%Y-%m-%d')}: {len(oi_breakdown)} strikes")
            return oi_breakdown
            
        except Exception as e:
            logging.error(f"Erro banco VENC={vencimento} DATA={dt_referencia.strftime('%Y-%m-%d')}: {e}")
            return {}
    
    def get_available_expirations(self, ticker):
        """Lista vencimentos disponíveis NO BANCO para a última data_referencia"""
        available_expirations = {                     
            "20260116": "16 Jan 26 - M",
            "20260220": "20 Fev 26 - M",
            "20260320": "20 Mar 26 - M",
            "20260417": "17 Abr 26 - M",           
        }
        
        expirations = []
        
        try:
            query = text("""
                SELECT MAX(data_referencia) as ultima_data
                FROM opcoes_b3
                WHERE ticker = :ticker
            """)
            
            ticker_clean = ticker.replace('.SA', '')
            
            with self.db_engine.connect() as conn:
                result = conn.execute(query, {'ticker': ticker_clean})
                row = result.fetchone()
                ultima_data = row[0] if row and row[0] else None
            
            if not ultima_data:
                logging.warning(f"Nenhuma data_referencia para {ticker_clean}")
                return expirations
            
            for code, desc in available_expirations.items():
                oi_data = self.get_floqui_historical(ticker_clean, code, ultima_data)
                data_count = len(oi_data)
                
                expirations.append({
                    'code': code,
                    'desc': desc,
                    'data_count': data_count,
                    'available': data_count > 0
                })
            
        except Exception as e:
            logging.error(f"Erro ao buscar vencimentos: {e}")
        
        return expirations


class HistoricalAnalyzer:
    def __init__(self):
        self.data_provider = HistoricalDataProvider()
        self.liquidity_manager = LiquidityManager()
    
    def calculate_gex(self, oplab_df, oi_breakdown, spot_price):
        """Calcula GEX com dados reais"""
        if oplab_df.empty:
            return pd.DataFrame()
        
        price_range = spot_price * 0.20
        valid_options = oplab_df[
            (oplab_df['strike'] >= (spot_price - price_range)) &
            (oplab_df['strike'] <= (spot_price + price_range))
        ].copy()
        
        if valid_options.empty:
            return pd.DataFrame()
        
        gex_data = []
        unique_strikes = valid_options['strike'].unique()
        
        for strike in unique_strikes:
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
        
        return pd.DataFrame(gex_data).sort_values('strike')
    
    def find_gamma_flip(self, gex_df, spot_price, symbol):
        if gex_df.empty or len(gex_df) < 2:
            logging.warning("Dados insuficientes para análise de flip")
            return None
        
        max_distance_pct = self.liquidity_manager.get_flip_range(symbol)
        max_distance = spot_price * (max_distance_pct / 100)
        
        valid_df = gex_df[
            (gex_df['strike'] >= spot_price - max_distance) &
            (gex_df['strike'] <= spot_price + max_distance)
        ].copy()
        
        if valid_df.empty:
            logging.warning(f"Nenhum strike dentro de +-{max_distance_pct}% do spot")
            return None
        
        valid_df = valid_df.sort_values('strike').reset_index(drop=True)
        
        spot_strike_idx = (valid_df['strike'] - spot_price).abs().argsort()[0]
        spot_gex = valid_df.iloc[spot_strike_idx]['total_gex_descoberto']
        spot_regime = "SHORT_GAMMA" if spot_gex < -1000 else ("LONG_GAMMA" if spot_gex > 1000 else "NEUTRAL")
        
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
        
        real_data_df = valid_df[valid_df['has_real_data'] == True].copy()
        flip_candidates = []
        
        if len(real_data_df) >= 2:
            flip_candidates = search_flips(real_data_df, "REAL")
        
        if not flip_candidates and len(valid_df) >= 2:
            flip_candidates = search_flips(valid_df, "MISTO")
        
        if not flip_candidates:
            return None
        
        if spot_regime == "SHORT_GAMMA":
            flip_candidates = [f for f in flip_candidates if f['flip_position'] == "ACIMA"]
            flip_candidates.sort(key=lambda x: x['distance_from_spot'])
        elif spot_regime == "LONG_GAMMA":
            flip_candidates = [f for f in flip_candidates if f['flip_position'] == "ABAIXO"]
            flip_candidates.sort(key=lambda x: x['distance_from_spot'])
        else:
            flip_candidates.sort(key=lambda x: x['distance_from_spot'])
        
        if not flip_candidates:
            return None
        
        best_flip = flip_candidates[0]
        return float(best_flip['strike'])
    
    def identify_walls(self, gex_df, spot_price):
        if gex_df.empty:
            return []
        
        walls = []
        
        calls_gex = gex_df[gex_df['call_gex'] > 0].copy()
        if not calls_gex.empty:
            max_call_row = calls_gex.loc[calls_gex['call_gex'].idxmax()]
            
            walls.append({
                'strike': float(max_call_row['strike']),
                'gamma_descoberto': float(max_call_row['call_gex']),
                'oi_descoberto': int(max_call_row['call_oi_descoberto']),
                'intensity': 1.0,
                'type': 'Support',
                'distance_pct': float(abs(max_call_row['strike'] - spot_price) / spot_price * 100),
                'strength': 'Strong'
            })
        
        puts_gex = gex_df[gex_df['put_gex'] < 0].copy()
        if not puts_gex.empty:
            max_put_row = puts_gex.loc[puts_gex['put_gex'].idxmin()]
            
            walls.append({
                'strike': float(max_put_row['strike']),
                'gamma_descoberto': float(max_put_row['put_gex']),
                'oi_descoberto': int(max_put_row['put_oi_descoberto']),
                'intensity': 1.0,
                'type': 'Resistance',
                'distance_pct': float(abs(max_put_row['strike'] - spot_price) / spot_price * 100),
                'strength': 'Strong'
            })
        
        return walls
    
    def create_6_charts(self, gex_df, spot_price, symbol, flip_strike, expiration_desc, analysis_date):
        """Gera os 6 gráficos padrão do GEX"""
        if gex_df.empty:
            return None
        
        gex_df = gex_df.sort_values('strike').reset_index(drop=True)
        
        title = f"{expiration_desc} - {analysis_date}"
        
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
        
        # 1. Total GEX
        colors1 = ['#ef4444' if x < 0 else '#22c55e' for x in total_gex_values]
        fig.add_trace(go.Bar(x=strikes, y=total_gex_values, marker_color=colors1, showlegend=False), row=1, col=1)
        
        # 2. GEX Descoberto
        colors2 = ['#ef4444' if x < 0 else '#22c55e' for x in descoberto_values]
        fig.add_trace(go.Bar(x=strikes, y=descoberto_values, marker_color=colors2, showlegend=False), row=1, col=2)
        
        # 3. Regime por Strike
        colors3 = ['#22c55e' if x > 1000 else '#ef4444' if x < -1000 else '#6b7280' for x in descoberto_values]
        fig.add_trace(go.Bar(x=strikes, y=[abs(x) for x in descoberto_values], marker_color=colors3, showlegend=False), row=2, col=1)
        
        # 4. Calls vs Puts
        fig.add_trace(go.Bar(x=strikes, y=call_gex_values, marker_color='#22c55e', name='Calls', showlegend=False), row=2, col=2)
        fig.add_trace(go.Bar(x=strikes, y=put_gex_values, marker_color='#ef4444', name='Puts', showlegend=False), row=2, col=2)
        
        # 5. GEX Cumulativo
        cumulative = np.cumsum(total_gex_values).tolist()
        fig.add_trace(go.Scatter(x=strikes, y=cumulative, mode='lines+markers',
                                 line=dict(color='#06b6d4', width=3), 
                                marker=dict(color='#06b6d4', size=6),
                                showlegend=False), row=3, col=1)
        
        # 6. Open Interest
        oi_total = [c + p for c, p in zip(call_oi, put_oi)]
        fig.add_trace(go.Bar(x=strikes, y=oi_total, marker_color='#a855f7', showlegend=False), row=3, col=2)
        
        # Linhas de referência
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
        fig.update_xaxes(gridcolor='rgba(255,255,255,0.1)', color='#ffffff', showgrid=True, zeroline=False)
        fig.update_yaxes(gridcolor='rgba(255,255,255,0.1)', color='#ffffff', showgrid=True, zeroline=False)
        
        return fig.to_json()
    
    def calculate_historical_insights(self, data_by_date, spot_prices_by_date):
        """✅ CORRIGIDO: Usa spot_price de cada dia específico"""
        if not data_by_date or len(data_by_date) < 2:
            return {}
        
        dates = sorted(data_by_date.keys())
        
        # 1. EVOLUÇÃO DO FLIP
        flip_evolution = []
        regime_changes = []
        
        for i, date in enumerate(dates):
            data = data_by_date[date]
            spot_price = spot_prices_by_date.get(date)  # ✅ Spot correto do dia
            
            flip_evolution.append({
                'date': date,
                'flip_strike': data.get('flip_strike'),
                'spot_price': spot_price,  # ✅ Spot histórico
                'regime': data['regime']
            })
            
            if i > 0:
                prev_regime = data_by_date[dates[i-1]]['regime']
                if prev_regime != data['regime']:
                    regime_changes.append({
                        'date': date,
                        'from': prev_regime,
                        'to': data['regime']
                    })
        
        # 2. MOVIMENTO DO FLIP (em %)
        flip_movement = None
        valid_flips = [f for f in flip_evolution if f['flip_strike'] is not None]
        
        if len(valid_flips) >= 2:
            first_flip = valid_flips[0]['flip_strike']
            last_flip = valid_flips[-1]['flip_strike']
            
            flip_movement = {
                'first_date': valid_flips[0]['date'],
                'last_date': valid_flips[-1]['date'],
                'first_flip': first_flip,
                'last_flip': last_flip,
                'change_pct': ((last_flip - first_flip) / first_flip * 100),
                'direction': 'UP' if last_flip > first_flip else 'DOWN',
                'change_abs': last_flip - first_flip
            }
        
        # 3. TENDÊNCIA DE GEX DESCOBERTO
        gex_trend = []
        for date in dates:
            gex_trend.append({
                'date': date,
                'net_gex_descoberto': data_by_date[date]['net_gex_descoberto']
            })
        
        gex_change = None
        if len(gex_trend) >= 2:
            first_gex = gex_trend[0]['net_gex_descoberto']
            last_gex = gex_trend[-1]['net_gex_descoberto']
            
            gex_change = {
                'first_date': dates[0],
                'last_date': dates[-1],
                'first_gex': first_gex,
                'last_gex': last_gex,
                'change_abs': last_gex - first_gex,
                'trend': 'INCREASING_LONG' if last_gex > first_gex and last_gex > 0 else \
                         'INCREASING_SHORT' if last_gex < first_gex and last_gex < 0 else \
                         'DECREASING'
            }
        
        # 4. STRIKES MAIS IMPACTADOS
        most_impacted = self._identify_most_impacted_strikes(data_by_date, spot_prices_by_date, dates)
        
        # 5. RESUMO GERENCIAL
        summary = {
            'period': {
                'start': dates[0],
                'end': dates[-1],
                'days': len(dates)
            },
            'flip_evolution': flip_evolution,
            'flip_movement': flip_movement,
            'regime_changes': regime_changes,
            'regime_stability': len(regime_changes) == 0,
            'gex_trend': gex_trend,
            'gex_change': gex_change,
            'current_regime': data_by_date[dates[-1]]['regime'],
            'days_in_current_regime': self._count_consecutive_regime(data_by_date, dates),
            'most_impacted_strikes': most_impacted
        }
        
        return summary
    
    def _count_consecutive_regime(self, data_by_date, dates):
        if not dates:
            return 0
        
        current_regime = data_by_date[dates[-1]]['regime']
        count = 1
        
        for i in range(len(dates) - 2, -1, -1):
            if data_by_date[dates[i]]['regime'] == current_regime:
                count += 1
            else:
                break
        
        return count
    
    def _identify_most_impacted_strikes(self, data_by_date, spot_prices_by_date, dates):
        """✅ CORRIGIDO: Usa spot_price médio do período"""
        if len(dates) < 2:
            return []
        
        # Calcula spot médio do período
        avg_spot = sum(spot_prices_by_date.values()) / len(spot_prices_by_date)
        
        strike_gex_history = {}
        
        for date in dates:
            if 'gex_df_records' not in data_by_date[date]:
                continue
            
            gex_records = data_by_date[date]['gex_df_records']
            
            for record in gex_records:
                strike = float(record['strike'])
                gex_desc = float(record['total_gex_descoberto'])
                
                if strike not in strike_gex_history:
                    strike_gex_history[strike] = []
                
                strike_gex_history[strike].append({
                    'date': date,
                    'gex': gex_desc
                })
        
        impacts = []
        
        for strike, history in strike_gex_history.items():
            if len(history) < 2:
                continue
            
            first_gex = history[0]['gex']
            last_gex = history[-1]['gex']
            
            change = last_gex - first_gex
            change_abs = abs(change)
            
            if change_abs < 5000:
                continue
            
            impacts.append({
                'strike': strike,
                'distance_from_spot_pct': abs(strike - avg_spot) / avg_spot * 100,
                'first_gex': first_gex,
                'last_gex': last_gex,
                'change': change,
                'change_abs': change_abs,
                'direction': 'MORE_LONG' if change > 0 else 'MORE_SHORT',
                'dates_tracked': len(history)
            })
        
        impacts.sort(key=lambda x: x['change_abs'], reverse=True)
        
        return impacts[:5]
    
    def analyze_historical(self, ticker, vencimento, days_back=6):
        """✅ ANÁLISE HISTÓRICA CORRIGIDA - USA SPOT_PRICE DE CADA DIA"""
        logging.info(f"🔍 INICIANDO ANÁLISE HISTÓRICA - {ticker}")
        
        business_dates = self.data_provider.get_business_days(days_back)
        
        data_by_date = {}
        spot_prices_by_date = {}  # ✅ NOVO: Armazena spot de cada dia
        available_dates = []
        
        expirations = self.data_provider.get_available_expirations(ticker)
        expiration_desc = next((e['desc'] for e in expirations if e['code'] == vencimento), vencimento)
        
        logging.info(f"📅 Tentando buscar dados para {len(business_dates)} dias úteis")
        
        for date_obj in business_dates:
            date_str = date_obj.strftime('%Y-%m-%d')
            
            logging.info(f"🔄 Processando {date_str}...")
            
            # ✅ 1. BUSCAR SPOT HISTÓRICO DO DIA ESPECÍFICO
            spot_price = self.data_provider.get_historical_spot_price(ticker, date_obj)
            
            if not spot_price:
                logging.warning(f"❌ Sem spot_price para {date_str} - pulando dia")
                continue
            
            spot_prices_by_date[date_str] = spot_price  
            
            # 2. BUSCAR DADOS OPLAB
            oplab_df = self.data_provider.get_oplab_historical_data(ticker, target_date=date_obj)
            
            if oplab_df.empty:
                logging.warning(f"Oplab vazio para {date_str} - pulando")
                continue
            
            # 3. BUSCAR DADOS BANCO
            oi_breakdown = self.data_provider.get_floqui_historical(ticker, vencimento, date_obj)
            
            if not oi_breakdown:
                logging.warning(f"Banco vazio para {date_str} - pulando")
                continue
            
            # 4. CALCULAR GEX COM SPOT CORRETO DO DIA
            gex_df = self.calculate_gex(oplab_df, oi_breakdown, spot_price)
            
            if gex_df.empty:
                logging.warning(f"GEX vazio para {date_str} - pulando")
                continue
            
            # 5. ANÁLISES COM SPOT CORRETO
            flip_strike = self.find_gamma_flip(gex_df, spot_price, ticker)
            walls = self.identify_walls(gex_df, spot_price)
            
            cumulative_total = np.cumsum(gex_df['total_gex'].values)
            cumulative_descoberto = np.cumsum(gex_df['total_gex_descoberto'].values)
            
            net_gex = float(cumulative_total[-1])
            net_gex_descoberto = float(cumulative_descoberto[-1])
            
            if flip_strike:
                regime = 'Long Gamma' if spot_price > flip_strike else 'Short Gamma'
            else:
                regime = 'Long Gamma' if net_gex_descoberto > 0 else 'Short Gamma'
            
            # 6. GERAR GRÁFICOS
            plot_json = self.create_6_charts(
                gex_df, spot_price, ticker, flip_strike, 
                expiration_desc, date_obj.strftime('%d/%m/%Y')
            )
            
            gex_df_records = gex_df.to_dict('records')
            
            # 7. ARMAZENAR RESULTADO
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
                'gex_df_records': gex_df_records
            }
            
            available_dates.append(date_str)
            
            logging.info(f"✅ {date_str}: Spot={spot_price:.2f}, {len(gex_df)} strikes, Flip={flip_strike}, {regime}")
        
        if len(available_dates) < 2:
            raise ValueError(f"Dados insuficientes: apenas {len(available_dates)} dia(s) com dados. Mínimo: 2")
        
        logging.info(f"✅ Dados coletados para {len(available_dates)} dias: {available_dates}")
        
        # 8. CALCULAR INSIGHTS COM SPOTS CORRETOS
        insights = {}
        try:
            logging.info(f"Calculando insights...")
            insights = self.calculate_historical_insights(data_by_date, spot_prices_by_date)
            logging.info(f"✅ Insights calculados")
        except Exception as e:
            logging.error(f"Erro ao calcular insights: {e}", exc_info=True)
            insights = {
                'error': str(e),
                'period': {
                    'start': available_dates[0] if available_dates else None,
                    'end': available_dates[-1] if available_dates else None,
                    'days': len(available_dates)
                }
            }
        
        # ✅ Pega último spot para referência
        current_spot = spot_prices_by_date[available_dates[-1]]
        
        result = {
            'ticker': ticker,
            'vencimento': vencimento,
            'expiration_desc': expiration_desc,
            'spot_price': current_spot,  # ✅ Spot mais recente
            'available_dates': available_dates,
            'data_by_date': data_by_date,
            'spot_prices_by_date': spot_prices_by_date,  # ✅ NOVO: Todos os spots
            'insights': insights,
            'success': True
        }
        
        return result


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
                'expiration_desc': result['expiration_desc'],
                'spot_price': result['spot_price'],
                'available_dates': result['available_dates'],
                'data_by_date': result['data_by_date'],
                'spot_prices_by_date': result['spot_prices_by_date'],  # ✅ NOVO
                'insights': result['insights'],
                'success': True
            }
            
            return convert_to_json_serializable(api_result)
            
        except Exception as e:
            logging.error(f"Erro na análise histórica: {e}", exc_info=True)
            raise
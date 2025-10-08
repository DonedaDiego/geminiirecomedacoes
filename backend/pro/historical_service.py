"""
historical_service.py - Análise Histórica GEX com INSIGHTS GERENCIAIS
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
    """
    🔥 VERSÃO CORRIGIDA - Converte tipos numpy/pandas para Python nativo
    SEM esconder erros com try/except genérico
    """
    # SE JÁ É TIPO NATIVO DO PYTHON, RETORNA DIRETO (IMPORTANTE!)
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    
    # LISTA: processa cada item
    if isinstance(obj, (list, tuple)):
        return [convert_to_json_serializable(item) for item in obj]
    
    # DICT: processa cada valor
    if isinstance(obj, dict):
        return {key: convert_to_json_serializable(value) for key, value in obj.items()}
    
    # PANDAS/NUMPY
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
    
    # Tipos numpy especiais
    if hasattr(obj, 'item'):
        return obj.item()
    
    if hasattr(obj, 'tolist'):
        return obj.tolist()
    
    # FALLBACK: converter para string (melhor que None!)
    return str(obj)





class LiquidityManager:
    """
    Gerencia ranges de ATM baseado na liquidez do ativo
    """
    
    def __init__(self):
        # 🔥 ALTA LIQUIDEZ - 5-6%
        self.high_liquidity = {
            'BOVA11': 5,
            'PETR4': 6,
            'VALE3': 6,
            'BBAS3': 6,
            'B3SA3': 6,
            'ITSA4': 6,
        }
        
        # 📈 MÉDIA LIQUIDEZ - 8-10%
        self.medium_liquidity = {
            'ITUB4': 9,
            'BBDC4': 9,
            'ABEV3': 9,
            'WEGE3': 9,
            'RENT3': 9,
            'ELET3': 9,
            'PRIO3': 9,
        }
        
        # 📉 BAIXA LIQUIDEZ - Range padrão 13%
        self.low_liquidity_range = 13
    
    def get_flip_range(self, symbol):
        """Retorna o range para busca de flip baseado na liquidez"""
        symbol_clean = symbol.replace('.SA', '').upper()
        
        if symbol_clean in self.high_liquidity:
            return self.high_liquidity[symbol_clean]
        
        if symbol_clean in self.medium_liquidity:
            return self.medium_liquidity[symbol_clean]
        
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
    
    def get_last_business_day(self):
        """Retorna o ÚLTIMO DIA ÚTIL (D-1 útil, não calendário)"""
        current = datetime.now() - timedelta(days=1)
        
        while current.weekday() >= 5:  # 5=Sábado, 6=Domingo
            current -= timedelta(days=1)
        
        logging.info(f"Último dia útil: {current.strftime('%Y-%m-%d')}")
        return current
    
    def get_business_days(self, days_back=5):
        """Gera lista de dias ÚTEIS respeitando limite de 7 dias do Floqui"""
        dates = []
        current_date = self.get_last_business_day()
        days_calendar_attempted = 0
        MAX_FLOQUI_DAYS = 7
        
        while len(dates) < days_back and days_calendar_attempted < MAX_FLOQUI_DAYS:
            if current_date.weekday() < 5:
                dates.append(current_date)
            
            current_date -= timedelta(days=1)
            days_calendar_attempted += 1
        
        return dates[::-1]  # Ordem cronológica
    
    def get_spot_price(self, symbol):
        """Busca cotação atual"""
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
    
    def get_oplab_historical_data(self, symbol):
        """Busca dados de opções da Oplab (gamma real)"""
        try:
            symbol_clean = symbol.replace('.SA', '')
            
            to_date = datetime.now().strftime('%Y-%m-%d')
            from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            
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
            
            valid_data = df[
                (df['gamma'] > 0) &
                (df['premium'] > 0) &
                (df['strike'] > 0) &
                (df['days_to_maturity'] > 0) &
                (df['days_to_maturity'] <= 60)
            ].copy()
            
            logging.info(f"Dados Oplab: {len(valid_data)} opções")
            return valid_data
            
        except Exception as e:
            logging.error(f"Erro ao buscar dados Oplab: {e}")
            return pd.DataFrame()
    
    def get_floqui_historical(self, ticker, vencimento, dt_referencia):
        """Busca OI histórico do Floqui para data específica"""
        try:
            ticker_clean = ticker.replace('.SA', '')
            date_str = dt_referencia.strftime('%Y%m%d')
            url = f"https://floqui.com.br/api/posicoes_em_aberto/{ticker_clean.lower()}/{vencimento}/{date_str}"
            
            response = requests.get(url, timeout=15)
            
            if response.status_code != 200:
                return {}
            
            data = response.json()
            if not data:
                return {}
            
            oi_breakdown = {}
            for item in data:
                strike = float(item.get('preco_exercicio', 0))
                option_type = item.get('tipo_opcao', '').upper()
                oi_total = int(item.get('qtd_total', 0))
                oi_descoberto = int(item.get('qtd_descoberto', 0))
                
                if strike > 0 and oi_total > 0:
                    key = (strike, 'CALL' if option_type == 'CALL' else 'PUT')
                    oi_breakdown[key] = {
                        'total': oi_total,
                        'descoberto': oi_descoberto,
                        'travado': int(item.get('qtd_trava', 0)),
                        'coberto': int(item.get('qtd_coberto', 0))
                    }
            
            logging.info(f"Floqui {date_str}: {len(oi_breakdown)} strikes")
            return oi_breakdown
            
        except Exception as e:
            logging.error(f"Erro Floqui: {e}")
            return {}
    
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
        test_date = self.get_last_business_day()
        
        for code, desc in available_expirations.items():
            oi_data = self.get_floqui_historical(ticker, code, test_date)
            data_count = len(oi_data)
            
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
        self.liquidity_manager = LiquidityManager()
    
    def calculate_gex(self, oplab_df, oi_breakdown, spot_price):
        """Calcula GEX com dados reais do Floqui"""
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
            
            if len(calls) > 0:
                call_key = (float(strike), 'CALL')
                if call_key in oi_breakdown:
                    call_data = oi_breakdown[call_key]
                    has_real_call = True
            
            if len(puts) > 0:
                put_key = (float(strike), 'PUT')
                if put_key in oi_breakdown:
                    put_data = oi_breakdown[put_key]
                    has_real_put = True
            
            if not (has_real_call or has_real_put):
                continue
            
            # Calcular GEX
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
        """Detecta gamma flip com lógica inteligente baseada no regime do spot"""
        if gex_df.empty or len(gex_df) < 2:
            return None
        
        # Pega range baseado na liquidez
        max_distance_pct = self.liquidity_manager.get_flip_range(symbol)
        max_distance = spot_price * (max_distance_pct / 100)
        
        valid_df = gex_df[
            (gex_df['strike'] >= spot_price - max_distance) &
            (gex_df['strike'] <= spot_price + max_distance)
        ].copy()
        
        if valid_df.empty:
            return None
        
        valid_df = valid_df.sort_values('strike').reset_index(drop=True)
        
        # DETECTA REGIME DO SPOT
        spot_strike_idx = (valid_df['strike'] - spot_price).abs().argsort()[0]
        spot_gex = valid_df.iloc[spot_strike_idx]['total_gex_descoberto']
        spot_regime = "SHORT_GAMMA" if spot_gex < -1000 else ("LONG_GAMMA" if spot_gex > 1000 else "NEUTRAL")
        
        # FUNCAO AUXILIAR
        def search_flips(df):
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
                    flip_position = "ACIMA" if flip_strike > spot_price else "ABAIXO"
                    flip_direction = "NEG_TO_POS" if current_gex < 0 and next_gex > 0 else "POS_TO_NEG"
                    
                    # SCORE DE RELEVANCIA
                    relevance_score = 0
                    
                    if spot_regime == "SHORT_GAMMA":
                        if flip_position == "ACIMA" and flip_direction == "NEG_TO_POS":
                            relevance_score = 1000
                        else:
                            relevance_score = 1
                    elif spot_regime == "LONG_GAMMA":
                        if flip_position == "ABAIXO" and flip_direction == "POS_TO_NEG":
                            relevance_score = 1000
                        else:
                            relevance_score = 1
                    else:
                        relevance_score = 100
                    
                    flip_candidates.append({
                        'strike': flip_strike,
                        'distance_from_spot': distance_from_spot,
                        'relevance_score': relevance_score
                    })
            
            return flip_candidates
        
        # BUSCA FLIPS
        flip_candidates = search_flips(valid_df)
        
        if not flip_candidates:
            return None
        
        # ORDENA POR RELEVANCIA
        flip_candidates.sort(key=lambda x: (-x['relevance_score'], x['distance_from_spot']))
        return float(flip_candidates[0]['strike'])
    
    def identify_walls(self, gex_df, spot_price):
        """Identifica support/resistance baseado em OI descoberto"""
        if gex_df.empty:
            return []
        
        walls = []
        valid_strikes = gex_df[
            (gex_df['call_oi_descoberto'] > 0) | (gex_df['put_oi_descoberto'] > 0)
        ].copy()
        
        if valid_strikes.empty:
            return []
        
        # Maior OI descoberto de CALLS (Support)
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
        
        # Maior OI descoberto de PUTS (Resistance)
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
        
        return walls
    
    def create_6_charts(self, gex_df, spot_price, symbol, flip_strike, expiration_desc, analysis_date):
        """MESMOS 6 GRÁFICOS do gamma_service.py"""
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
        
        # Linhas de referência em TODOS os gráficos
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
    
    def calculate_historical_insights(self, data_by_date, spot_price):
        """
        🔥 ANÁLISE GERENCIAL: tendências, strikes impactados, mudanças de regime
        """
        if not data_by_date or len(data_by_date) < 2:
            return {}
        
        dates = sorted(data_by_date.keys())
        
        # 1. EVOLUÇÃO DO FLIP
        flip_evolution = []
        regime_changes = []
        
        for i, date in enumerate(dates):
            data = data_by_date[date]
            flip_evolution.append({
                'date': date,
                'flip_strike': data.get('flip_strike'),
                'spot_price': spot_price,
                'regime': data['regime']
            })
            
            # Detectar mudanças de regime
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
        
        # Calcular variação de GEX
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
        most_impacted = self._identify_most_impacted_strikes(data_by_date, spot_price, dates)
        
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
        """Conta quantos dias consecutivos no regime atual"""
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
    
    def _identify_most_impacted_strikes(self, data_by_date, spot_price, dates):
        """
        🎯 Identifica strikes com MAIOR VARIAÇÃO de GEX descoberto
        """
        if len(dates) < 2:
            return []
        
        # Estrutura: strike -> [gex por data]
        strike_gex_history = {}
        
        # Coletar histórico de cada strike
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
        
        # Calcular variação para cada strike
        impacts = []
        
        for strike, history in strike_gex_history.items():
            if len(history) < 2:
                continue
            
            first_gex = history[0]['gex']
            last_gex = history[-1]['gex']
            
            change = last_gex - first_gex
            change_abs = abs(change)
            
            # Ignorar mudanças pequenas
            if change_abs < 5000:
                continue
            
            impacts.append({
                'strike': strike,
                'distance_from_spot_pct': abs(strike - spot_price) / spot_price * 100,
                'first_gex': first_gex,
                'last_gex': last_gex,
                'change': change,
                'change_abs': change_abs,
                'direction': 'MORE_LONG' if change > 0 else 'MORE_SHORT',
                'dates_tracked': len(history)
            })
        
        # Ordenar por maior impacto absoluto
        impacts.sort(key=lambda x: x['change_abs'], reverse=True)
        
        # Retornar top 5
        return impacts[:5]
    
    def analyze_historical(self, ticker, vencimento, days_back=5):
        """
        
        Gera 6 gráficos por data + insights gerenciais
        """
        logging.info(f"INICIANDO ANÁLISE HISTÓRICA - {ticker}")
        
        spot_price = self.data_provider.get_spot_price(ticker)
        if not spot_price:
            raise ValueError("Erro: não foi possível obter cotação")
        
        oplab_df = self.data_provider.get_oplab_historical_data(ticker)
        if oplab_df.empty:
            raise ValueError("Erro: sem dados da Oplab")
        
        business_dates = self.data_provider.get_business_days(days_back)
        
        # ESTRUTURA: dict separado por data
        data_by_date = {}
        available_dates = []
        
        # Buscar descrição do vencimento
        expirations = self.data_provider.get_available_expirations(ticker)
        expiration_desc = next((e['desc'] for e in expirations if e['code'] == vencimento), vencimento)
        
        for date_obj in business_dates:
            date_str = date_obj.strftime('%Y-%m-%d')
            
            # Buscar OI histórico
            oi_breakdown = self.data_provider.get_floqui_historical(ticker, vencimento, date_obj)
            
            if not oi_breakdown:
                logging.warning(f"Sem dados para {date_str}")
                continue
            
            # Calcular GEX
            gex_df = self.calculate_gex(oplab_df, oi_breakdown, spot_price)
            
            if gex_df.empty:
                logging.warning(f"GEX vazio para {date_str}")
                continue
            
            # Análise completa
            flip_strike = self.find_gamma_flip(gex_df, spot_price, ticker)
            walls = self.identify_walls(gex_df, spot_price)
            
            cumulative_total = np.cumsum(gex_df['total_gex'].values)
            cumulative_descoberto = np.cumsum(gex_df['total_gex_descoberto'].values)
            
            net_gex = float(cumulative_total[-1])
            net_gex_descoberto = float(cumulative_descoberto[-1])
            
            # Determinar regime
            if flip_strike:
                regime = 'Long Gamma' if spot_price > flip_strike else 'Short Gamma'
            else:
                regime = 'Long Gamma' if net_gex_descoberto > 0 else 'Short Gamma'
            
            # Gerar os 6 gráficos para esta data
            plot_json = self.create_6_charts(
                gex_df, spot_price, ticker, flip_strike, 
                expiration_desc, date_obj.strftime('%d/%m/%Y')
            )
            
            # 🔥 SALVAR TAMBÉM OS REGISTROS DO GEX_DF (para análise gerencial)
            gex_df_records = gex_df.to_dict('records')
            
            # Armazenar dados desta data
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
                'gex_df_records': gex_df_records  # 🔥 NOVO: salvar registros
            }
            
            available_dates.append(date_str)
            
            logging.info(f"{date_str}: {len(gex_df)} strikes, Flip: {flip_strike}, Regime: {regime}")
        
        # 🔥 LOG ANTES DOS INSIGHTS
        logging.info(f"📊 DATAS COLETADAS: {len(available_dates)}")
        logging.info(f"📊 DATAS: {available_dates}")
        
        if not available_dates:
            raise ValueError("Nenhum dado histórico encontrado")
        
        # 🔥 CALCULAR INSIGHTS COM TRY-CATCH
        insights = {}
        try:
            logging.info(f"📊 CALCULANDO INSIGHTS...")
            insights = self.calculate_historical_insights(data_by_date, spot_price)
            logging.info(f"✅ INSIGHTS CALCULADOS")
        except Exception as e:
            logging.error(f"❌ ERRO AO CALCULAR INSIGHTS: {e}", exc_info=True)
            # Não falhar por causa dos insights
            insights = {
                'error': str(e),
                'period': {
                    'start': available_dates[0] if available_dates else None,
                    'end': available_dates[-1] if available_dates else None,
                    'days': len(available_dates)
                }
            }
        
        # 🔥 LOG ANTES DO RETORNO
        logging.info(f"📊 PREPARANDO RETORNO...")
        logging.info(f"   - ticker: {ticker}")
        logging.info(f"   - available_dates count: {len(available_dates)}")
        logging.info(f"   - data_by_date count: {len(data_by_date)}")
        
        result = {
            'ticker': ticker,
            'vencimento': vencimento,
            'expiration_desc': expiration_desc,
            'spot_price': spot_price,
            'available_dates': available_dates,
            'data_by_date': data_by_date,
            'insights': insights,
            'success': True
        }
        
        # 🔥 LOG FINAL
        logging.info(f"✅ RETORNO CRIADO - available_dates: {len(result['available_dates'])}")
        
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
                'insights': result['insights'],  # 🔥 NOVO
                'success': True
            }
            
            return convert_to_json_serializable(api_result)
            
        except Exception as e:
            logging.error(f"Erro na análise histórica: {e}")
            raise
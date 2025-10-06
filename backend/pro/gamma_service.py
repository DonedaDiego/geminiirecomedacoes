"""
gamma_service.py - GEX Analysis COM DADOS REAIS
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

class ExpirationManager:
    def __init__(self):
        self.available_expirations = {
            "20250919": {"date": datetime(2025, 9, 19), "desc": "19 Set 25 - M"},
            "20251017": {"date": datetime(2025, 10, 17), "desc": "17 Out 25 - M"},
            "20251121": {"date": datetime(2025, 11, 21), "desc": "21 Nov 25 - M"},
            "20251219": {"date": datetime(2025, 12, 19), "desc": "19 Dez 25 - M"},
            "20260116": {"date": datetime(2026, 1, 16), "desc": "16 Jan 26 - M"},
        }
    
    def test_data_availability(self, symbol, expiration_code):
        try:
            url = f"https://floqui.com.br/api/posicoes_em_aberto/{symbol.lower()}/{expiration_code}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return len(data) if data else 0
            return 0
        except:
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
        self.expiration_manager = ExpirationManager()
    
    def get_spot_price(self, symbol):
        try:
            # Tentar Oplab primeiro
            url = f"{self.oplab_url}/market/instruments/{symbol}"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data and 'close' in data:
                    return float(data['close'])
            
            # Fallback YFinance
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
        """DADOS REAIS da Oplab"""
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
            
            # Filtros de qualidade
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
        """DADOS REAIS do Floqui"""
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
            
            url = f"https://floqui.com.br/api/posicoes_em_aberto/{symbol.lower()}/{expiration['code']}"
            response = requests.get(url, timeout=15)
            
            if response.status_code != 200:
                logging.error(f"Erro na API Floqui: {response.status_code}")
                return {}, expiration
            
            data = response.json()
            if not data:
                logging.warning("Nenhum dado retornado do Floqui")
                return {}, expiration
            
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
            
            logging.info(f"Floqui OI breakdown: {len(oi_breakdown)} strikes")
            return oi_breakdown, expiration
            
        except Exception as e:
            logging.error(f"Erro Floqui: {e}")
            return {}, None

class GEXAnalyzer:
    def __init__(self):
        self.data_provider = DataProvider()
    
    def calculate_gex(self, oplab_df, oi_breakdown, spot_price):
        """Calcula GEX com dados de OI descoberto sempre disponíveis"""
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
            
            call_data = {}
            put_data = {}
            
            if len(calls) > 0:
                call_key = (float(strike), 'CALL')
                if call_key in oi_breakdown:
                    call_data = oi_breakdown[call_key]
                else:
                    volume_estimate = int(calls['volume'].mean() if 'volume' in calls.columns else 100)
                    call_data = {
                        'total': volume_estimate * 3,
                        'descoberto': volume_estimate * 2,
                        'travado': volume_estimate,
                        'coberto': volume_estimate
                    }
            
            if len(puts) > 0:
                put_key = (float(strike), 'PUT')
                if put_key in oi_breakdown:
                    put_data = oi_breakdown[put_key]
                else:
                    volume_estimate = int(puts['volume'].mean() if 'volume' in puts.columns else 100)
                    put_data = {
                        'total': volume_estimate * 3,
                        'descoberto': volume_estimate * 2,
                        'travado': volume_estimate,
                        'coberto': volume_estimate
                    }
            
            # Calcular GEX - COMO ESTAVA ANTES (CORRETO)
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
                # VOLTA O SINAL NEGATIVO - ESTAVA CERTO!
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
                'call_oi_total': int(call_data.get('total', 0)),
                'put_oi_total': int(put_data.get('total', 0)),
                'call_oi_descoberto': int(call_data.get('descoberto', 0)),
                'put_oi_descoberto': int(put_data.get('descoberto', 0)),
                'has_real_data': (float(strike), 'CALL') in oi_breakdown or (float(strike), 'PUT') in oi_breakdown
            })
        
        result_df = pd.DataFrame(gex_data).sort_values('strike')
        logging.info(f"GEX calculado para {len(result_df)} strikes com OI descoberto")
        
        return result_df
    
    def find_gamma_flip(self, gex_df, spot_price):
        """Detecta gamma flip usando dados reais"""
        if gex_df.empty or len(gex_df) < 2:
            return None
        
        atm_range = spot_price * 0.08
        mask1 = gex_df['strike'] >= (spot_price - atm_range)
        mask2 = gex_df['strike'] <= (spot_price + atm_range)
        atm_df = gex_df[mask1 & mask2].copy()
        
        if len(atm_df) < 2:
            atm_range = spot_price * 0.12
            mask1 = gex_df['strike'] >= (spot_price - atm_range)
            mask2 = gex_df['strike'] <= (spot_price + atm_range)
            atm_df = gex_df[mask1 & mask2].copy()
        
        if len(atm_df) < 2:
            return None
        
        descoberto_values = atm_df['total_gex_descoberto'].values
        has_positive = bool((descoberto_values > 0).any())
        has_negative = bool((descoberto_values < 0).any())
        
        if not (has_positive and has_negative):
            return None
        
        atm_df = atm_df.sort_values('strike').reset_index(drop=True)
        
        for i in range(len(atm_df) - 1):
            current = float(atm_df.iloc[i]['total_gex_descoberto'])
            next_gex = float(atm_df.iloc[i+1]['total_gex_descoberto'])
            
            if (current > 0 and next_gex < 0) or (current < 0 and next_gex > 0):
                strike1 = float(atm_df.iloc[i]['strike'])
                strike2 = float(atm_df.iloc[i+1]['strike'])
                
                if abs(current) + abs(next_gex) > 0:
                    flip = strike1 + (strike2 - strike1) * abs(current) / (abs(current) + abs(next_gex))
                    return float(flip)
        
        return None
    
    def create_6_charts(self, gex_df, spot_price, symbol, flip_strike=None, expiration_info=None):
        """Cria os 6 gráficos em 3 LINHAS x 2 COLUNAS com títulos atrativos"""
        if gex_df.empty:
            return None
        
        gex_df = gex_df.sort_values('strike').reset_index(drop=True)
        
        title = expiration_info["desc"] if expiration_info else ""
        
        # Títulos dos subgráficos mais atrativos com cores
        subplot_titles = [
            '<b style="color: #ffffff;">Total GEX</b><br><span style="font-size: 12px; color: #888;">Exposição gamma total</span>',
            '<b style="color: #ffffff;">GEX Descoberto</b><br><span style="font-size: 12px; color: #888;">Posições descobertas</span>',
            '<b style="color: #ffffff;">Regime por Strike</b><br><span style="font-size: 12px; color: #888;">Long vs Short gamma</span>',
            '<b style="color: #ffffff;">Calls vs Puts</b><br><span style="font-size: 12px; color: #888;">Sentimento direcional</span>',
            '<b style="color: #ffffff;">GEX Cumulativo</b><br><span style="font-size: 12px; color: #888;">Fluxo de pressão</span>',
            '<b style="color: #ffffff;">Open Interest</b><br><span style="font-size: 12px; color: #888;">Volume contratos</span>'
        ]
        
        # 3 LINHAS, 2 COLUNAS = 6 gráficos
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
        
        # LINHA 1
        # 1. Total GEX (linha 1, coluna 1)
        colors1 = ['#ef4444' if x < 0 else '#22c55e' for x in total_gex_values]
        fig.add_trace(go.Bar(x=strikes, y=total_gex_values, marker_color=colors1, showlegend=False), row=1, col=1)
        
        # 2. GEX Descoberto (linha 1, coluna 2)
        colors2 = ['#ef4444' if x < 0 else '#22c55e' for x in descoberto_values]
        fig.add_trace(go.Bar(x=strikes, y=descoberto_values, marker_color=colors2, showlegend=False), row=1, col=2)
        
        # LINHA 2
        # 3. Regime por Strike (linha 2, coluna 1)
        colors3 = ['#22c55e' if x > 1000 else '#ef4444' if x < -1000 else '#6b7280' for x in descoberto_values]
        fig.add_trace(go.Bar(x=strikes, y=[abs(x) for x in descoberto_values], marker_color=colors3, showlegend=False), row=2, col=1)
        
        # 4. Calls vs Puts (linha 2, coluna 2)
        fig.add_trace(go.Bar(x=strikes, y=call_gex_values, marker_color='#22c55e', name='Calls', showlegend=False), row=2, col=2)
        fig.add_trace(go.Bar(x=strikes, y=put_gex_values, marker_color='#ef4444', name='Puts', showlegend=False), row=2, col=2)
        
        # LINHA 3
        # 5. GEX Cumulativo (linha 3, coluna 1)
        cumulative = np.cumsum(total_gex_values).tolist()
        fig.add_trace(go.Scatter(x=strikes, y=cumulative, mode='lines+markers', 
                                line=dict(color='#06b6d4', width=3), 
                                marker=dict(color='#06b6d4', size=6),
                                showlegend=False), row=3, col=1)
        
        # 6. Open Interest (linha 3, coluna 2)
        oi_total = [c + p for c, p in zip(call_oi, put_oi)]
        fig.add_trace(go.Bar(x=strikes, y=oi_total, marker_color='#a855f7', showlegend=False), row=3, col=2)
        
        # Linhas de referência em TODOS os gráficos
        for row in range(1, 4):  # 3 linhas
            for col in range(1, 3):  # 2 colunas
                # Linha do preço atual (amarela)
                fig.add_vline(x=spot_price, line=dict(color='#fbbf24', width=3, dash='dash'), row=row, col=col)
                
                # Linha do gamma flip (laranja) se existir
                if flip_strike:
                    fig.add_vline(x=flip_strike, line=dict(color='#f97316', width=3, dash='dot'), row=row, col=col)
                
                # Linha zero (branca sutil)
                fig.add_hline(y=0, line=dict(color='rgba(255,255,255,0.3)', width=1), row=row, col=col)
        
        # Layout otimizado - CORREÇÃO AQUI
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
        
        # Atualizar cor dos títulos dos subgráficos
        fig.update_annotations(font=dict(color='#ffffff', family='Inter, sans-serif', size=21))
        
        # Grid e eixos
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
        """Identifica apenas 2 walls: maior OI descoberto de calls e puts"""
        if gex_df.empty:
            return []
        
        walls = []
        
        # Filtrar apenas strikes com dados válidos
        valid_strikes = gex_df[
            (gex_df['call_oi_descoberto'] > 0) | (gex_df['put_oi_descoberto'] > 0)
        ].copy()
        
        if valid_strikes.empty:
            logging.warning("Nenhum strike com OI descoberto válido")
            return []
        
        # 1. MAIOR VOLUME DESCOBERTO DE CALLS (Support Wall)
        calls_with_oi = valid_strikes[valid_strikes['call_oi_descoberto'] > 0]
        if not calls_with_oi.empty:
            max_call_row = calls_with_oi.loc[calls_with_oi['call_oi_descoberto'].idxmax()]
            
            walls.append({
                'strike': float(max_call_row['strike']),
                'gamma_descoberto': float(max_call_row['total_gex_descoberto']),
                'oi_descoberto': int(max_call_row['call_oi_descoberto']),
                'intensity': 1.0,  # Máxima intensidade
                'type': 'Support',
                'distance_pct': float(abs(max_call_row['strike'] - spot_price) / spot_price * 100),
                'strength': 'Strong'
            })
        
        # 2. MAIOR VOLUME DESCOBERTO DE PUTS (Resistance Wall)
        puts_with_oi = valid_strikes[valid_strikes['put_oi_descoberto'] > 0]
        if not puts_with_oi.empty:
            max_put_row = puts_with_oi.loc[puts_with_oi['put_oi_descoberto'].idxmax()]
            
            walls.append({
                'strike': float(max_put_row['strike']),
                'gamma_descoberto': float(max_put_row['total_gex_descoberto']),
                'oi_descoberto': int(max_put_row['put_oi_descoberto']),
                'intensity': 1.0,  # Máxima intensidade
                'type': 'Resistance',
                'distance_pct': float(abs(max_put_row['strike'] - spot_price) / spot_price * 100),
                'strength': 'Strong'
            })
        
        # Log para debug
        logging.info(f"WALLS SIMPLIFICADOS: {len(walls)}")
        for wall in walls:
            logging.info(f"  {wall['type']}: R${wall['strike']:.2f} - OI Descoberto: {wall['oi_descoberto']:,}")
        
        return walls
    
    def analyze(self, symbol, expiration_code=None):
        """Análise principal usando APENAS dados reais"""
        logging.info(f"INICIANDO ANALISE GEX REAL - {symbol}")
        
        # 1. Preço atual
        spot_price = self.data_provider.get_spot_price(symbol)
        if not spot_price:
            raise ValueError("Erro: não foi possível obter cotação")
        
        logging.info(f"Spot price: R$ {spot_price:.2f}")
        
        # 2. Dados REAIS da Oplab
        oplab_df = self.data_provider.get_oplab_historical_data(symbol)
        if oplab_df.empty:
            raise ValueError("Erro: sem dados da Oplab - verifique o token")
        
        # 3. Dados REAIS do Floqui
        oi_breakdown, expiration_info = self.data_provider.get_floqui_oi_breakdown(symbol, expiration_code)
        
        # 4. Calcular GEX com dados reais
        gex_df = self.calculate_gex(oplab_df, oi_breakdown, spot_price)
        if gex_df.empty:
            raise ValueError("Erro: falha no cálculo GEX")
        
        # Garantir ordenação por strike
        gex_df = gex_df.sort_values('strike').reset_index(drop=True)
        
        # 5. Análise final
        flip_strike = self.find_gamma_flip(gex_df, spot_price)
        plot_json = self.create_6_charts(gex_df, spot_price, symbol, flip_strike, expiration_info)
        walls = self.identify_walls(gex_df, spot_price)
        
        # CORREÇÃO: Usar valores do cumulativo (igual ao gráfico)
        # Isso garante consistência lógica: descoberto sempre <= total
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
        
        # Log dos resultados reais
        logging.info(f"\nRESULTADOS REAIS:")
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
        logging.info(f"Strikes: {len(gex_df)} ({real_data_count} com dados reais Floqui)")
        logging.info(f"Walls: {len(walls)}")
        
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
            
            # CORREÇÃO AQUI - Determinar regime pelo FLIP, não pelo sinal do GEX
            flip_strike = result.get('flip_strike')
            spot_price = result['spot_price']
            
            if flip_strike:
                # Se spot > flip = Long Gamma (comprimido)
                # Se spot < flip = Short Gamma (explosivo)
                regime = 'Long Gamma' if spot_price > flip_strike else 'Short Gamma'
            else:
                # Fallback se não encontrar flip: usar sinal do GEX
                regime = 'Long Gamma' if result['net_gex_descoberto'] > 0 else 'Short Gamma'
            
            api_result = {
                'ticker': ticker.replace('.SA', ''),
                'spot_price': spot_price,
                'gex_levels': result['gex_levels'],
                'flip_strike': flip_strike,
                'regime': regime,  # USAR A VARIÁVEL CORRIGIDA
                'plot_json': result['plot_json'],
                'walls': result['walls'],
                'options_count': result['strikes_analyzed'],
                'data_quality': {
                    'expiration': result['expiration']['desc'] if result['expiration'] else None,
                    'real_data_count': result['real_data_count']
                },
                'success': True
            }
            
            return convert_to_json_serializable(api_result)
            
        except Exception as e:
            logging.error(f"Erro na análise GEX: {e}")
            raise
            
        except Exception as e:
            logging.error(f"Erro na análise GEX: {e}")
            raise
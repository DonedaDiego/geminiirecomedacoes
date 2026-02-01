"""
theta_service.py - TEX Analysis COMPLETO
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
        self.expiration_manager = ExpirationManager()
    
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
                oi_travado = int(item.get('qtd_trava', 0))
                oi_coberto = int(item.get('qtd_coberto', 0))
                
                if strike > 0 and oi_total > 0:
                    key = (strike, 'CALL' if option_type == 'CALL' else 'PUT')
                    oi_breakdown[key] = {
                        'total': oi_total,
                        'descoberto': oi_descoberto,
                        'travado': oi_travado,
                        'coberto': oi_coberto
                    }
            
            logging.info(f"OI breakdown TEX: {len(oi_breakdown)} strikes")
            return oi_breakdown, expiration
            
        except Exception as e:
            logging.error(f"Erro Floqui: {e}")
            return {}, None

class TEXCalculator:
    def calculate_tex(self, oplab_df, oi_breakdown, spot_price):
        """Calcula TEX = Theta × Open Interest × 100"""
        if oplab_df.empty:
            return pd.DataFrame()
        
        price_range = spot_price * 0.25
        valid_options = oplab_df[
            (oplab_df['strike'] >= spot_price - price_range) &
            (oplab_df['strike'] <= spot_price + price_range)
        ].copy()
        
        if valid_options.empty:
            return pd.DataFrame()
        
        tex_data = []
        
        for strike in valid_options['strike'].unique():
            strike_options = valid_options[valid_options['strike'] == strike]
            
            calls = strike_options[strike_options['type'] == 'CALL']
            puts = strike_options[strike_options['type'] == 'PUT']
            
            call_data = {}
            put_data = {}
            
            if not calls.empty:
                call_key = (float(strike), 'CALL')
                if call_key in oi_breakdown:
                    call_data = oi_breakdown[call_key]
                else:
                    volume_estimate = len(calls) * 100
                    call_data = {
                        'total': volume_estimate * 3,
                        'descoberto': volume_estimate * 2,
                        'travado': volume_estimate,
                        'coberto': volume_estimate
                    }
            
            if not puts.empty:
                put_key = (float(strike), 'PUT')
                if put_key in oi_breakdown:
                    put_data = oi_breakdown[put_key]
                else:
                    volume_estimate = len(puts) * 100
                    put_data = {
                        'total': volume_estimate * 3,
                        'descoberto': volume_estimate * 2,
                        'travado': volume_estimate,
                        'coberto': volume_estimate
                    }
            
            call_tex = 0
            call_tex_descoberto = 0
            call_days = 0
            if call_data and not calls.empty:
                avg_theta = float(calls['theta'].mean())
                avg_days = float(calls['days_to_maturity'].mean())
                call_tex = avg_theta * call_data['total'] * 100
                call_tex_descoberto = avg_theta * call_data['descoberto'] * 100
                call_days = avg_days
            
            put_tex = 0
            put_tex_descoberto = 0
            put_days = 0
            if put_data and not puts.empty:
                avg_theta = float(puts['theta'].mean())
                avg_days = float(puts['days_to_maturity'].mean())
                put_tex = avg_theta * put_data['total'] * 100
                put_tex_descoberto = avg_theta * put_data['descoberto'] * 100
                put_days = avg_days
            
            total_tex = call_tex + put_tex
            total_tex_descoberto = call_tex_descoberto + put_tex_descoberto
            
            # Dias até vencimento médio ponderado
            weighted_days = 0
            if call_data and put_data:
                total_oi = call_data['total'] + put_data['total']
                if total_oi > 0:
                    weighted_days = (call_days * call_data['total'] + put_days * put_data['total']) / total_oi
            elif call_data:
                weighted_days = call_days
            elif put_data:
                weighted_days = put_days
            
            # Aceleração do decaimento
            time_decay_acceleration = max(0, (30 - weighted_days) / 30) if weighted_days > 0 else 0
            
            tex_data.append({
                'strike': float(strike),
                'call_tex': float(call_tex),
                'put_tex': float(put_tex),
                'total_tex': float(total_tex),
                'call_tex_descoberto': float(call_tex_descoberto),
                'put_tex_descoberto': float(put_tex_descoberto),
                'total_tex_descoberto': float(total_tex_descoberto),
                'call_oi_total': int(call_data.get('total', 0)),
                'put_oi_total': int(put_data.get('total', 0)),
                'call_oi_descoberto': int(call_data.get('descoberto', 0)),
                'put_oi_descoberto': int(put_data.get('descoberto', 0)),
                'days_to_expiration': float(weighted_days),
                'time_decay_acceleration': float(time_decay_acceleration),
                'has_real_data': (float(strike), 'CALL') in oi_breakdown or (float(strike), 'PUT') in oi_breakdown
            })
        
        result_df = pd.DataFrame(tex_data).sort_values('strike')
        logging.info(f"TEX calculado para {len(result_df)} strikes")
        
        return result_df

class TimeDecayRegimeDetector:
    def analyze_time_decay_regime(self, tex_df, spot_price):
        """Analisa regime de decaimento temporal baseado em TEX"""
        if tex_df.empty:
            return None
        
        total_tex = float(tex_df['total_tex'].sum())
        total_tex_descoberto = float(tex_df['total_tex_descoberto'].sum())
        
        # Dias médios até vencimento ponderado por OI
        total_oi = (tex_df['call_oi_total'] + tex_df['put_oi_total']).sum()
        if total_oi > 0:
            weighted_days = float((tex_df['days_to_expiration'] * (tex_df['call_oi_total'] + tex_df['put_oi_total'])).sum() / total_oi)
        else:
            weighted_days = float(tex_df['days_to_expiration'].mean())
        
        # Strike de máximo sangramento
        max_bleed_idx = tex_df['total_tex'].idxmin()  # Theta é negativo
        max_bleed_strike = float(tex_df.loc[max_bleed_idx, 'strike'])
        
        # Classificação da pressão temporal
        if weighted_days < 15:
            time_pressure = 'HIGH'
            pressure_interpretation = 'Alto decaimento diário'
        elif weighted_days < 30:
            time_pressure = 'MODERATE'
            pressure_interpretation = 'Decaimento moderado'
        else:
            time_pressure = 'LOW'
            pressure_interpretation = 'Baixo decaimento temporal'
        
        # Análise para vendedores/compradores
        if total_tex < -30000:  # Theta negativo alto
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
        
        # 1. Total TEX (sangramento)
        colors1 = ['#7c2d12' if x < 0 else '#22c55e' for x in total_tex_values]
        fig.add_trace(go.Bar(x=strikes, y=total_tex_values, marker_color=colors1, showlegend=False), row=1, col=1)
        
        # 2. TEX Descoberto
        colors2 = ['#dc2626' if x < 0 else '#22c55e' for x in descoberto_values]
        fig.add_trace(go.Bar(x=strikes, y=descoberto_values, marker_color=colors2, showlegend=False), row=1, col=2)
        
        # 3. Pressão Temporal (concentração %)
        total_tex_abs = sum([abs(x) for x in total_tex_values])
        if total_tex_abs > 0:
            concentration_pct = [(abs(x) / total_tex_abs) * 100 for x in total_tex_values]
        else:
            concentration_pct = [0] * len(total_tex_values)
        
        risk_colors = ['#ef4444' if x > 20 else '#f97316' if x > 10 else '#22c55e' for x in concentration_pct]
        fig.add_trace(go.Bar(x=strikes, y=concentration_pct, marker_color=risk_colors, showlegend=False), row=2, col=1)
        
        # 4. Calls vs Puts
        fig.add_trace(go.Bar(x=strikes, y=call_tex_values, marker_color='#22c55e', showlegend=False), row=2, col=2)
        fig.add_trace(go.Bar(x=strikes, y=put_tex_values, marker_color='#ef4444', showlegend=False), row=2, col=2)
        
        # 5. TEX Cumulativo
        cumulative = np.cumsum(total_tex_values).tolist()
        fig.add_trace(go.Scatter(x=strikes, y=cumulative, mode='lines', 
                                line=dict(color='#06b6d4', width=4),
                                fill='tozeroy',
                                fillcolor='rgba(6, 182, 212, 0.3)',
                                showlegend=False), row=3, col=1)
        
        # 6. Velocidade de sangramento (R$/dia)
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
        
        # Linhas de referência
        for row in range(1, 4):
            for col in range(1, 3):
                fig.add_vline(x=spot_price, line=dict(color='#fbbf24', width=2, dash='dash'), row=row, col=col)
                if not (row == 2 and col == 1):  # Não adiciona linha zero no gráfico de %
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
        
        # CORRIGIR OS DIAS AQUI - ADICIONAR ESTAS LINHAS:
        if expiration_info and 'days' in expiration_info:
            decay_regime['weighted_days'] = float(expiration_info['days'])
            print(f"CORREÇÃO: Usando dias reais: {expiration_info['days']}")
        
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
            
            # ✅ ADICIONAR TIME_PRESSURE BASEADO EM WEIGHTED_DAYS
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
                'decay_regime': decay_regime,  # ← Agora inclui time_pressure
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
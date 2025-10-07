"""
delta_service.py - DEX Analysis COMPLETO
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
            
            # PRINT AQUI - Strike sendo processado
            if strike >= 150 and strike <= 155:  # Foco no strike problemático
                print(f"\n=== STRIKE {strike} ===")
                print(f"Calls encontradas: {len(calls)}")
                print(f"Puts encontradas: {len(puts)}")
            
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
            
            call_dex = 0
            call_dex_descoberto = 0
            if call_data and not calls.empty:
                avg_delta = float(calls['delta'].mean())
                call_dex = avg_delta * call_data['total'] * 100
                call_dex_descoberto = avg_delta * call_data['descoberto'] * 100
                
                # PRINT DETALHADO CALLS
                if strike >= 150 and strike <= 155:
                    print(f"CALLS - Delta médio: {avg_delta:.4f}")
                    print(f"CALLS - OI total: {call_data['total']}")
                    print(f"CALLS - OI descoberto: {call_data['descoberto']}")
                    print(f"CALLS - DEX total: {call_dex:,.0f}")
                    print(f"CALLS - DEX descoberto: {call_dex_descoberto:,.0f}")
            
            put_dex = 0
            put_dex_descoberto = 0
            if put_data and not puts.empty:
                avg_delta = float(puts['delta'].mean())
                put_dex = avg_delta * put_data['total'] * 100
                put_dex_descoberto = avg_delta * put_data['descoberto'] * 100
                
                # PRINT DETALHADO PUTS
                if strike >= 150 and strike <= 155:
                    print(f"PUTS - Delta médio: {avg_delta:.4f}")
                    print(f"PUTS - OI total: {put_data['total']}")
                    print(f"PUTS - OI descoberto: {put_data['descoberto']}")
                    print(f"PUTS - DEX total: {put_dex:,.0f}")
                    print(f"PUTS - DEX descoberto: {put_dex_descoberto:,.0f}")
            
            total_dex = call_dex + put_dex
            total_dex_descoberto = call_dex_descoberto + put_dex_descoberto
            
            # PRINT RESULTADO FINAL
            if strike >= 150 and strike <= 155:
                print(f"TOTAL DEX: {total_dex:,.0f}")
                print(f"TOTAL DEX DESCOBERTO: {total_dex_descoberto:,.0f}")
                print(f"=== FIM STRIKE {strike} ===\n")
            
            dex_data.append({
                'strike': float(strike),
                'call_dex': float(call_dex),
                'put_dex': float(put_dex),
                'total_dex': float(total_dex),
                'call_dex_descoberto': float(call_dex_descoberto),
                'put_dex_descoberto': float(put_dex_descoberto),
                'total_dex_descoberto': float(total_dex_descoberto),
                'call_oi_total': int(call_data.get('total', 0)),
                'put_oi_total': int(put_data.get('total', 0)),
                'call_oi_descoberto': int(call_data.get('descoberto', 0)),
                'put_oi_descoberto': int(put_data.get('descoberto', 0)),
                'has_real_data': (float(strike), 'CALL') in oi_breakdown or (float(strike), 'PUT') in oi_breakdown
            })
        
        result_df = pd.DataFrame(dex_data).sort_values('strike')
        logging.info(f"DEX calculado para {len(result_df)} strikes")
        
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
        
        # FILTRAR APENAS DADOS REAIS (IGUAL AO GEX)
        dex_real_data = dex_df[dex_df['has_real_data'] == True].copy()
        
        if len(dex_real_data) < 2:
            logging.warning("Menos de 2 strikes com dados reais do Floqui (DEX)")
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
        
        # 5. DEX Cumulativo - COM PREENCHIMENTO IGUAL À IMAGEM
        cumulative = np.cumsum(total_dex_values).tolist()
        fig.add_trace(go.Scatter(
            x=strikes, 
            y=cumulative, 
            mode='lines', 
            line=dict(color='#a855f7', width=4),
            fill='tozeroy',  # Preenchimento até o zero
            fillcolor='rgba(168, 85, 247, 0.3)',  # Cor roxa com transparência
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
                
                # Linhas das maiores concentrações
                # if max_calls_strike:
                #     fig.add_vline(x=max_calls_strike, line=dict(color='#22c55e', width=2, dash='dot'), row=row, col=col)
                # if max_puts_strike:
                #     fig.add_vline(x=max_puts_strike, line=dict(color='#ef4444', width=2, dash='dot'), row=row, col=col)
                
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
        
        # CORREÇÃO AQUI - Buscar os targets primeiro
        max_calls_strike, max_puts_strike = self.find_targets(dex_df, spot_price)
        
        # Agora chamar com parâmetros corretos
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
            
            # Calcular pressão restante automaticamente
            dex_df = result.get('dex_df', None)  # Precisa vir do analyzer
            spot_price = result['spot_price']
            
            print(f"=== DEBUG PRESSÃO RESTANTE ===")
            print(f"dex_df existe: {dex_df is not None}")
            print(f"spot_price: {spot_price}")
            
            remaining_pressure = 0
            if dex_df is not None and len(dex_df) > 0:
                print(f"dex_df length: {len(dex_df)}")
                print(f"colunas dex_df: {list(dex_df.columns)}")
                
                if 'total_dex_descoberto' in dex_df.columns:
                    cumulative_values = np.cumsum(dex_df['total_dex'].values)
                    print(f"cumulative_values: {cumulative_values[:5]}...")  
                    print(f"max_cumulative: {max(cumulative_values) if len(cumulative_values) > 0 else 0}")
                    
                    current_spot_idx = None
                    max_cumulative = max(cumulative_values) if len(cumulative_values) > 0 else 0
                    
                    # Encontrar índice mais próximo do spot price
                    for i, strike in enumerate(dex_df['strike'].values):
                        if current_spot_idx is None or abs(strike - spot_price) < abs(dex_df['strike'].iloc[current_spot_idx] - spot_price):
                            current_spot_idx = i
                    
                    print(f"current_spot_idx: {current_spot_idx}")
                    
                    # Calcular pressão restante
                    if current_spot_idx is not None:
                        current_cumulative = cumulative_values[current_spot_idx]
                        remaining_pressure = max_cumulative - current_cumulative
                        print(f"current_cumulative: {current_cumulative}")
                        print(f"remaining_pressure: {remaining_pressure}")
                    else:
                        print("current_spot_idx é None")
                else:
                    print("Coluna 'total_dex_descoberto' não encontrada")
            else:
                print("dex_df é None ou vazio")
            
            print(f"remaining_pressure final: {remaining_pressure}")
            print(f"=== FIM DEBUG ===")
            
            # FAZER IGUAL O GEX - COLOCAR TUDO DENTRO DE UM OBJETO
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
                'dex_levels': dex_levels,  # TUDO JUNTO COMO NO GEX
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
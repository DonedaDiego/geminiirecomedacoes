import numpy as np
import pandas as pd
import yfinance as yf
import requests
from datetime import datetime, timedelta
import warnings
import logging
import time

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)

class GeminiiIntradayFlowTracker:
    """Sistema de Análise de Fluxo de Opções Intraday"""
    
    def __init__(self):
        self.token = "SKIS2ebVJQFUfUaC8OaBZyjQaWpaGAWCJ64V1FUgiQFOxeF9eXAUaoNiGb0Y3mhi--l4z2lSylkQkpvWIGe8+5CA==--MmFlOWVjMTgxMTM3OTY2Nzk5MzU4YzQ2YmI0NWRlZWE="
        self.base_url = "https://api.oplab.com.br/v3/market/options/details"
        # Endpoint correto para listar opções (baseado na documentação)
        self.list_url = "https://api.oplab.com.br/v3/market/stocks"  # Usar endpoint de stocks
        self.headers = {
            "Access-Token": self.token,
            "Content-Type": "application/json"
        }
    
    def get_options_list(self, parent_symbol):
        """Busca lista de opções para um ativo usando método alternativo"""
        try:
            # Método 1: Tentar usar API de stocks para descobrir opções
            logging.info(f"Tentando descobrir opções para {parent_symbol} via API stocks")
            
            variations = [
                parent_symbol,           # PETR4
                parent_symbol[:-1] + "3" if parent_symbol.endswith("4") else parent_symbol,  # PETR3
            ]
            
            for variant in variations:
                try:
                    params = {
                        'symbol': variant,
                        'limit': 1
                    }
                    
                    response = requests.get(self.list_url, headers=self.headers, params=params, timeout=15)
                    logging.info(f"Stocks API response para {variant}: {response.status_code}")
                    
                    if response.status_code == 200:
                        data = response.json()
                        logging.info(f"Stocks data: {data}")
                        
                        # Se conseguimos dados do stock, vamos tentar gerar símbolos de opções
                        if data:
                            return self._generate_option_symbols(variant)
                            
                except Exception as e:
                    logging.warning(f"Erro ao testar {variant}: {e}")
            
            # Método 2: Tentar símbolos conhecidos de opções da PETR
            logging.info("Tentando símbolos conhecidos de opções")
            return self._try_known_option_symbols(parent_symbol)
            
        except Exception as e:
            logging.error(f"Erro ao buscar lista de opções: {e}")
            return []
    
    def _generate_option_symbols(self, parent_symbol):
        """Gera símbolos de opções baseado em padrões conhecidos"""
        today = datetime.now()
        options = []
        
        # Gerar símbolos para os próximos vencimentos
        base_symbols = [
            f"{parent_symbol[:4]}E",  # PETRE (calls)
            f"{parent_symbol[:4]}T",  # PETRT (puts)
            f"{parent_symbol[:4]}F",  # PETRF
            f"{parent_symbol[:4]}G",  # PETRG
        ]
        
        # Testar alguns strikes próximos ao preço atual
        current_price = self.get_current_stock_price(parent_symbol)
        if current_price:
            strikes = [
                int(current_price * 0.9),   # 10% OTM
                int(current_price * 0.95),  # 5% OTM
                int(current_price),         # ATM
                int(current_price * 1.05),  # 5% OTM
                int(current_price * 1.1),   # 10% OTM
            ]
            
            for base in base_symbols:
                for strike in strikes:
                    symbol = f"{base}{strike}"
                    options.append({'symbol': symbol, 'parent_symbol': parent_symbol})
        
        # Testar se algum desses símbolos existe
        valid_options = []
        for option in options[:10]:  # Limitar para não sobrecarregar
            details = self.get_option_details(option['symbol'])
            if details:
                valid_options.append(details)
                
        return valid_options
    
    def _try_known_option_symbols(self, parent_symbol):
        """Tenta símbolos conhecidos baseado no ticker"""
        known_patterns = {
            'PETR4': ['PETRE100', 'PETRE110', 'PETRE120', 'PETRT90', 'PETRT100'],
            'PETR3': ['PETRE100', 'PETRE110', 'PETRE120', 'PETRT90', 'PETRT100'],
            'VALE3': ['VALEE50', 'VALEE60', 'VALEE70', 'VALET40', 'VALET50'],
            'BBDC4': ['BBDCE20', 'BBDCE25', 'BBDCE30', 'BBDCT15', 'BBDCT20'],
        }
        
        symbols_to_try = known_patterns.get(parent_symbol, [])
        valid_options = []
        
        for symbol in symbols_to_try:
            details = self.get_option_details(symbol)
            if details:
                valid_options.append(details)
                logging.info(f" Opção válida encontrada: {symbol}")
            else:
                logging.info(f" Opção não encontrada: {symbol}")
        
        return valid_options
    
    def get_option_details(self, symbol):
        """Busca detalhes de uma opção específica"""
        try:
            url = f"{self.base_url}/{symbol}"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            
            return None
            
        except Exception as e:
            logging.error(f"Erro ao buscar detalhes da opção {symbol}: {e}")
            return None
    
    def get_current_stock_price(self, ticker):
        """Busca preço atual do ativo com yfinance"""
        try:
            stock_ticker = f"{ticker}.SA" if not ticker.endswith('.SA') else ticker
            stock = yf.Ticker(stock_ticker)
            
            # Tentar dados intraday primeiro
            hist = stock.history(period='1d', interval='1m')
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
            
            # Fallback para dados diários
            hist = stock.history(period='1d')
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
                
            return None
            
        except Exception as e:
            logging.error(f"Erro ao buscar preço do ativo: {e}")
            return None
    
    def calculate_moneyness(self, strike, spot_price):
        """Calcula moneyness da opção"""
        if spot_price <= 0:
            return "ATM"
        
        ratio = strike / spot_price
        if ratio < 0.95:
            return "OTM" if strike < spot_price else "ITM"
        elif ratio > 1.05:
            return "ITM" if strike < spot_price else "OTM"
        else:
            return "ATM"
    
    def process_intraday_flow(self, parent_symbol):
        """Processamento principal do flow intraday"""
        logging.info(f"Processando flow intraday para {parent_symbol}")
        
        # 1. Buscar preço atual do ativo
        current_price = self.get_current_stock_price(parent_symbol)
        if not current_price:
            logging.error(f"Não foi possível obter preço atual de {parent_symbol}")
            return pd.DataFrame(), None
        
        logging.info(f"Preço atual de {parent_symbol}: R$ {current_price}")
        
        # 2. Buscar opções usando nosso método melhorado
        options_data = self.get_options_list(parent_symbol)
        if not options_data:
            logging.error(f"Nenhuma opção encontrada para {parent_symbol}")
            return pd.DataFrame(), current_price
        
        logging.info(f"Encontradas {len(options_data)} opções para {parent_symbol}")
        
        # 3. Processar dados
        df = pd.DataFrame(options_data)
        
        # Verificar campos obrigatórios - INCLUINDO TIME
        required = ['category', 'close', 'open', 'strike', 'time']
        missing = [col for col in required if col not in df.columns]
        if missing:
            logging.error(f"Colunas faltando nas opções: {missing}")
            return pd.DataFrame(), current_price
        
        # Converter timestamp para datetime
        df['timestamp'] = pd.to_datetime(df['time'], unit='ms')
        df['hour_minute'] = df['timestamp'].dt.strftime('%H:%M')
        
        # Filtros básicos
        df = df[df['close'] > 0]  # premium atual > 0
        df = df[df['open'] > 0]   # premium abertura > 0
        df = df.dropna(subset=required)
        
        if df.empty:
            logging.warning("Nenhuma opção válida após filtros básicos")
            return pd.DataFrame(), current_price

        # ===== LÓGICA CORRETA: EVOLUÇÃO DO PRÊMIO =====
        # Calcular evolução do prêmio desde a abertura
        df['premium_evolution'] = ((df['close'] - df['open']) / df['open']) * 100
        
        logging.info(f"Evoluções calculadas - Min: {df['premium_evolution'].min():.2f}%, Max: {df['premium_evolution'].max():.2f}%")
        
        # Adicionar preço spot e calcular moneyness
        df['spot_price'] = current_price
        df['moneyness'] = df.apply(lambda row: self.calculate_moneyness(row['strike'], row['spot_price']), axis=1)
        
        # Filtrar apenas OTM e ATM
        df = df[df['moneyness'].isin(['OTM', 'ATM'])]
        
        if df.empty:
            logging.warning("Nenhuma opção OTM/ATM encontrada")
            return df, current_price
        
        # Processar volume e OI com a lógica CORRETA
        df['volume'] = pd.to_numeric(df.get('volume', 1), errors='coerce').fillna(1)
        
        # ===== PESO BASEADO NA EVOLUÇÃO DO PRÊMIO =====
        if 'open_interest' in df.columns:
            df['oi'] = pd.to_numeric(df['open_interest'], errors='coerce').fillna(1)
            # CORRETO: weight = evolução_premium × √(volume × open_interest)
            df['weight'] = df['premium_evolution'] * np.sqrt(df['volume'] * df['oi'])
            logging.info("Usando cálculo: weight = premium_evolution × √(volume × open_interest)")
        else:
            # CORRETO: weight = evolução_premium × √(volume)
            df['weight'] = df['premium_evolution'] * np.sqrt(df['volume'])
            logging.info("Usando cálculo: weight = premium_evolution × √(volume)")
        
        # Mapear tipo da opção corretamente
        df['option_type'] = df['category'].str.upper()
        
        # Validar se temos calls e puts
        call_count = len(df[df['option_type'] == 'CALL'])
        put_count = len(df[df['option_type'] == 'PUT'])
        
        logging.info(f"Processamento concluído: {len(df)} opções válidas ({call_count} calls, {put_count} puts)")
        logging.info(f"Timestamps range: {df['hour_minute'].min()} - {df['hour_minute'].max()}")
        
        return df, current_price
    
    def analyze_intraday_sentiment(self, df):
        """Análise de sentimento intraday"""
        if df.empty:
            return {}
        
        calls = df[df['option_type'] == 'CALL']
        puts = df[df['option_type'] == 'PUT']
        
        call_flow = calls['weight'].sum()
        put_flow = puts['weight'].sum()
        net_flow = call_flow - put_flow
        total_flow = call_flow + put_flow
        cp_ratio = call_flow / (put_flow + 1)
        
        # Intensidade e bias
        intensity = np.log1p(total_flow) if total_flow > 0 else 0
        bias = (call_flow - put_flow) / (total_flow + 1) if total_flow > 0 else 0
        
        # Classificar sentimento
        if net_flow > 0:
            if cp_ratio > 3:
                sentiment = "EXTREMELY BULLISH"
            elif cp_ratio > 2:
                sentiment = "STRONGLY BULLISH"
            elif cp_ratio > 1.5:
                sentiment = "BULLISH"
            else:
                sentiment = "MILDLY BULLISH"
        else:
            if cp_ratio < 0.33:
                sentiment = "EXTREMELY BEARISH"
            elif cp_ratio < 0.5:
                sentiment = "STRONGLY BEARISH"
            elif cp_ratio < 0.8:
                sentiment = "BEARISH"
            else:
                sentiment = "MILDLY BEARISH"
        
        # Força do sinal
        signal_strength = "HIGH" if abs(bias) > 0.3 else "MEDIUM"
        
        return {
            'total_call_flow': float(call_flow),
            'total_put_flow': float(put_flow),
            'net_flow': float(net_flow),
            'cp_ratio': float(cp_ratio),
            'sentiment': sentiment,
            'intensity': float(intensity),
            'bias': float(bias),
            'signal_strength': signal_strength,
            'call_count': len(calls),
            'put_count': len(puts),
            'total_options': len(df),
            'timestamp': datetime.now().isoformat()
        }
    
    def get_plot_data(self, df, ticker, current_price):
        """Preparar dados para gráfico de LINHA temporal (como flow histórico)"""
        if df.empty:
            return None
        
        # Agrupar por TEMPO e tipo de opção
        calls = df[df['option_type'] == 'CALL'].copy()
        puts = df[df['option_type'] == 'PUT'].copy()
        
        # Agrupar por timestamp (agrupamento temporal)
        call_timeline = calls.groupby('hour_minute').agg({
            'weight': 'sum',
            'premium_evolution': 'mean',
            'volume': 'sum',
            'timestamp': 'first'
        }).reset_index()
        
        put_timeline = puts.groupby('hour_minute').agg({
            'weight': 'sum',
            'premium_evolution': 'mean',
            'volume': 'sum',
            'timestamp': 'first'
        }).reset_index()
        
        # Ordenar por tempo
        call_timeline = call_timeline.sort_values('timestamp')
        put_timeline = put_timeline.sort_values('timestamp')
        
        plot_data = {
            'ticker': ticker,
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'current_price': float(current_price),
            'timeline': {
                'call_times': call_timeline['hour_minute'].tolist(),
                'call_weights': call_timeline['weight'].tolist(),
                'call_evolutions': call_timeline['premium_evolution'].tolist(),
                'call_volumes': call_timeline['volume'].tolist(),
                'put_times': put_timeline['hour_minute'].tolist(),
                'put_weights': put_timeline['weight'].tolist(),
                'put_evolutions': put_timeline['premium_evolution'].tolist(),
                'put_volumes': put_timeline['volume'].tolist()
            },
            'summary': {
                'total_call_weight': float(calls['weight'].sum()),
                'total_put_weight': float(puts['weight'].sum()),
                'call_count': len(calls),
                'put_count': len(puts),
                'avg_call_evolution': float(calls['premium_evolution'].mean()) if len(calls) > 0 else 0,
                'avg_put_evolution': float(puts['premium_evolution'].mean()) if len(puts) > 0 else 0,
                'time_range': {
                    'start': df['hour_minute'].min(),
                    'end': df['hour_minute'].max()
                }
            }
        }
        
        return plot_data

class RegimeProIntraService:
    """Serviço principal para análise intraday"""
    
    def __init__(self):
        self.flow_tracker = GeminiiIntradayFlowTracker()
    
    def analyze_intraday_flow(self, ticker):
        """Executa análise completa de flow intraday"""
        logging.info(f"Iniciando análise intraday para {ticker}")
        
        # Limpar ticker
        ticker_clean = ticker.replace('.SA', '').upper()
        
        # Processar flow
        df, current_price = self.flow_tracker.process_intraday_flow(ticker_clean)
        
        if df.empty:
            raise ValueError('Não foi possível processar dados de flow intraday')
        
        # Análises
        analysis = self.flow_tracker.analyze_intraday_sentiment(df)
        plot_data = self.flow_tracker.get_plot_data(df, ticker_clean, current_price)
        
        return {
            'analysis': analysis,
            'plot_data': plot_data,
            'raw_data_count': len(df)
        }
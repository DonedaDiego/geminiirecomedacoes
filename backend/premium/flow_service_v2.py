import numpy as np
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
from scipy.stats import norm
from scipy.optimize import brentq
import warnings
import logging
import os

# Import da função de conexão do seu sistema
from database import get_db_connection

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)

class BlackScholesCalculator:
    @staticmethod
    def calculate_price(spot, strike, time_to_expiry, risk_free_rate, volatility, option_type='call'):
        try:
            if time_to_expiry <= 0:
                # Opção vencida - valor intrínseco
                if option_type.lower() == 'call':
                    return max(0, spot - strike)
                else:
                    return max(0, strike - spot)
            
            # Parâmetros Black-Scholes
            d1 = (np.log(spot / strike) + (risk_free_rate + 0.5 * volatility**2) * time_to_expiry) / (volatility * np.sqrt(time_to_expiry))
            d2 = d1 - volatility * np.sqrt(time_to_expiry)
            
            if option_type.lower() == 'call':
                price = spot * norm.cdf(d1) - strike * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2)
            else:
                price = strike * np.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2) - spot * norm.cdf(-d1)
            
            return max(0, price)
            
        except Exception as e:
            logging.warning(f"Erro no cálculo Black-Scholes: {e}")
            return 0.0
    
    @staticmethod  
    def calculate_implied_volatility(market_price, spot, strike, time_to_expiry, risk_free_rate, option_type='call'):
        try:
            if time_to_expiry <= 0 or market_price <= 0:
                return 0.0
            
            def objective(vol):
                theoretical = BlackScholesCalculator.calculate_price(
                    spot, strike, time_to_expiry, risk_free_rate, vol, option_type
                )
                return theoretical - market_price
            
            # Buscar IV entre 1% e 300%
            iv = brentq(objective, 0.01, 3.0, maxiter=100)
            return iv
            
        except Exception as e:
            logging.warning(f"Erro no cálculo de IV: {e}")
            # Fallback: IV aproximada baseada em ATM
            try:
                atm_vol = market_price / (0.4 * spot * np.sqrt(time_to_expiry))
                return min(max(atm_vol, 0.05), 2.0)
            except:
                return 0.20

class FlowTrackerV2:
    """Sistema de Flow de Opções V2 - Integrado com database.py"""
    
    def __init__(self):
        self.api_token = os.getenv('OPLAB_API_TOKEN', "jeOTw9JanmDhlxReKlF2QwHM4Q3mNVlU3SpNENZUNIxTk24drRqdordyijyeNlfZ--bbybBgsEprbusre2drjwfA==--M2M3ZGFiNDk5ZTRhNzU3M2MxNWE3ZmJkMjcwZjQyNGE=")
        self.base_url = "https://api.oplab.com.br/v3/market/options"
        self.headers = {
            "Access-Token": self.api_token,
            "Content-Type": "application/json"
        }
        
        self.bs_calculator = BlackScholesCalculator()
        self.risk_free_rate = 0.1275
        
        # Verificar se tabelas existem
        self._verify_tables()
    
    def _verify_tables(self):
        """Verificar se as tabelas do Flow Tracker existem"""
        try:
            conn = get_db_connection()
            if not conn:
                logging.error("❌ Não foi possível conectar ao banco")
                return False
                
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('flow_snapshots', 'option_details')
            """)
            
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            if len(existing_tables) < 2:
                logging.warning("⚠️ Tabelas do Flow Tracker não encontradas!")
                logging.warning("💡 Execute setup_enhanced_database() no database.py")
                return False
            
            cursor.close()
            conn.close()
            
            logging.info("✅ Tabelas do Flow Tracker verificadas")
            return True
            
        except Exception as e:
            logging.error(f"Erro ao verificar tabelas: {e}")
            return False
    
    def execute_query(self, query, params=None, fetch=False):
        """Executar query usando a conexão padrão do sistema"""
        conn = None
        try:
            conn = get_db_connection()
            if not conn:
                raise Exception("Não foi possível conectar ao banco")
                
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            if fetch:
                result = cursor.fetchall()
                conn.commit()
                return result
            else:
                conn.commit()
                return cursor.rowcount
                
        except Exception as e:
            if conn:
                conn.rollback()
            logging.error(f"Erro ao executar query: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def get_current_options(self, ticker):
        """Busca opções atuais de um ticker"""
        try:
            ticker_clean = ticker.replace('.SA', '').upper()
            url = f"{self.base_url}/{ticker_clean}"
            
            logging.info(f"Buscando opções atuais para {ticker_clean}")
            
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                logging.info(f"✅ {len(data)} opções encontradas para {ticker_clean}")
                return data
            else:
                logging.warning(f"❌ Erro na API: {response.status_code}")
                return None
                
        except Exception as e:
            logging.error(f"Erro ao buscar opções: {e}")
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
    
    def process_options_data(self, options_data):
        """Processa dados das opções e calcula métricas avançadas"""
        if not options_data:
            return []
        
        processed_options = []
        
        for option in options_data:
            try:
                # Dados básicos da opção
                symbol = option.get('symbol', '')
                strike = float(option.get('strike', 0))
                category = option.get('category', 'CALL').upper()
                close_price = float(option.get('close', 0))
                volume = int(option.get('volume', 0))
                spot_price = float(option.get('spot_price', 0))
                days_to_maturity = int(option.get('days_to_maturity', 0))
                
                # Validações básicas
                if close_price <= 0 or spot_price <= 0 or strike <= 0 or days_to_maturity < 0:
                    continue
                    
                # Calcular tempo até vencimento em anos
                time_to_expiry = days_to_maturity / 365.0
                
                # Calcular volatilidade implícita
                calculated_iv = self.bs_calculator.calculate_implied_volatility(
                    close_price, spot_price, strike, time_to_expiry, 
                    self.risk_free_rate, category.lower()
                )
                
                # Calcular preço teórico Black-Scholes
                bs_theoretical = self.bs_calculator.calculate_price(
                    spot_price, strike, time_to_expiry, self.risk_free_rate,
                    calculated_iv, category.lower()
                )
                
                # Calcular moneyness
                moneyness = self.calculate_moneyness(strike, spot_price)
                
                # Calcular peso para flow
                weight = close_price * volume * np.sqrt(calculated_iv)
                
                processed_option = {
                    'symbol': symbol,
                    'strike': strike,
                    'category': category,
                    'due_date': option.get('due_date'),
                    'days_to_maturity': days_to_maturity,
                    'close_price': close_price,
                    'volume': volume,
                    'bid': float(option.get('bid', 0)),
                    'ask': float(option.get('ask', 0)),
                    'bid_volume': int(option.get('bid_volume', 0)),
                    'ask_volume': int(option.get('ask_volume', 0)),
                    'calculated_iv': calculated_iv,
                    'bs_theoretical': bs_theoretical,
                    'moneyness': moneyness,
                    'weight': weight,
                    'spot_price': spot_price,
                    'time_to_expiry': time_to_expiry
                }
                
                processed_options.append(processed_option)
                
            except Exception as e:
                logging.warning(f"Erro ao processar opção {option.get('symbol', 'unknown')}: {e}")
                continue
        
        logging.info(f"✅ {len(processed_options)} opções processadas")
        return processed_options
    
    def calculate_flow_metrics(self, processed_options):
        """Calcula métricas de flow baseado nas opções processadas"""
        if not processed_options:
            return None
        
        # Separar calls e puts
        calls = [opt for opt in processed_options if opt['category'] == 'CALL']
        puts = [opt for opt in processed_options if opt['category'] == 'PUT']
        
        # Calcular flows por peso
        call_flow = sum(opt['weight'] for opt in calls)
        put_flow = sum(opt['weight'] for opt in puts)
        net_flow = call_flow - put_flow
        
        # Volumes
        call_volume = sum(opt['volume'] for opt in calls)
        put_volume = sum(opt['volume'] for opt in puts)
        total_volume = call_volume + put_volume
        
        # Call/Put Ratio
        call_put_ratio = call_flow / (put_flow + 1) if put_flow > 0 else call_flow
        
        # Volatilidade implícita média
        all_ivs = [opt['calculated_iv'] for opt in processed_options if opt['calculated_iv'] > 0]
        avg_iv = np.mean(all_ivs) if all_ivs else 0
        
        # Determinar sentimento
        sentiment = self._determine_sentiment(call_put_ratio, net_flow)
        
        metrics = {
            'call_flow': float(call_flow),
            'put_flow': float(put_flow),
            'net_flow': float(net_flow),
            'call_put_ratio': float(call_put_ratio),
            'total_volume': total_volume,
            'call_volume': call_volume,
            'put_volume': put_volume,
            'total_options': len(processed_options),
            'call_options': len(calls),
            'put_options': len(puts),
            'avg_iv': float(avg_iv),
            'sentiment': sentiment
        }
        
        return metrics
    
    def _determine_sentiment(self, cp_ratio, net_flow):
        """Determina sentimento baseado em Call/Put ratio"""
        if cp_ratio > 3:
            return "EXTREMELY BULLISH"
        elif cp_ratio > 2:
            return "STRONGLY BULLISH"
        elif cp_ratio > 1.5:
            return "BULLISH"
        elif cp_ratio > 1.2:
            return "MILDLY BULLISH"
        elif cp_ratio > 0.8:
            return "NEUTRAL"
        elif cp_ratio > 0.5:
            return "MILDLY BEARISH"
        elif cp_ratio > 0.33:
            return "BEARISH"
        elif cp_ratio > 0.2:
            return "STRONGLY BEARISH"
        else:
            return "EXTREMELY BEARISH"
    
    def store_flow_snapshot(self, ticker, flow_metrics, processed_options):
        """Armazena snapshot de flow no banco PostgreSQL"""
        try:
            ticker_clean = ticker.replace('.SA', '').upper()
            current_date = datetime.now().date()
            current_timestamp = datetime.now()
            
            # CONVERSÃO EXPLÍCITA DOS DADOS ANTES DO INSERT
            params = (
                ticker_clean, 
                current_date, 
                current_timestamp,
                float(flow_metrics['call_flow']) if flow_metrics['call_flow'] is not None else 0.0,
                float(flow_metrics['put_flow']) if flow_metrics['put_flow'] is not None else 0.0,
                float(flow_metrics['net_flow']) if flow_metrics['net_flow'] is not None else 0.0,
                float(flow_metrics['call_put_ratio']) if flow_metrics['call_put_ratio'] is not None else 0.0,
                int(flow_metrics['total_volume']) if flow_metrics['total_volume'] is not None else 0,
                int(flow_metrics['call_volume']) if flow_metrics['call_volume'] is not None else 0,
                int(flow_metrics['put_volume']) if flow_metrics['put_volume'] is not None else 0,
                int(flow_metrics['total_options']) if flow_metrics['total_options'] is not None else 0,
                int(flow_metrics['call_options']) if flow_metrics['call_options'] is not None else 0,
                int(flow_metrics['put_options']) if flow_metrics['put_options'] is not None else 0,
                float(flow_metrics['avg_iv']) if flow_metrics['avg_iv'] is not None else 0.0,
                str(flow_metrics['sentiment']) if flow_metrics['sentiment'] is not None else 'NEUTRAL'
            )
            
            # Inserir snapshot principal
            insert_snapshot_query = """
            INSERT INTO flow_snapshots (
                ticker, date, timestamp, call_flow, put_flow, net_flow,
                call_put_ratio, total_volume, call_volume, put_volume,
                total_options, call_options, put_options, avg_iv, sentiment
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (ticker, date) 
            DO UPDATE SET 
                timestamp = EXCLUDED.timestamp,
                call_flow = EXCLUDED.call_flow,
                put_flow = EXCLUDED.put_flow,
                net_flow = EXCLUDED.net_flow,
                call_put_ratio = EXCLUDED.call_put_ratio,
                total_volume = EXCLUDED.total_volume,
                call_volume = EXCLUDED.call_volume,
                put_volume = EXCLUDED.put_volume,
                total_options = EXCLUDED.total_options,
                call_options = EXCLUDED.call_options,
                put_options = EXCLUDED.put_options,
                avg_iv = EXCLUDED.avg_iv,
                sentiment = EXCLUDED.sentiment
            RETURNING id;
            """
            
            result = self.execute_query(insert_snapshot_query, params, fetch=True)
            
            snapshot_id = result[0][0] if result else None
            
            if not snapshot_id:
                raise Exception("Falha ao obter snapshot_id")
            
            # Deletar detalhes antigos do mesmo dia
            delete_details_query = "DELETE FROM option_details WHERE snapshot_id = %s"
            self.execute_query(delete_details_query, (snapshot_id,))
            
            # Inserir detalhes das opções COM CONVERSÃO EXPLÍCITA
            for option in processed_options:
                option_params = (
                    snapshot_id,
                    str(option['symbol']),
                    float(option['strike']) if option['strike'] is not None else 0.0,
                    str(option['category']),
                    option['due_date'],
                    int(option['days_to_maturity']) if option['days_to_maturity'] is not None else 0,
                    float(option['close_price']) if option['close_price'] is not None else 0.0,
                    int(option['volume']) if option['volume'] is not None else 0,
                    float(option['bid']) if option['bid'] is not None else 0.0,
                    float(option['ask']) if option['ask'] is not None else 0.0,
                    int(option['bid_volume']) if option['bid_volume'] is not None else 0,
                    int(option['ask_volume']) if option['ask_volume'] is not None else 0,
                    float(option['calculated_iv']) if option['calculated_iv'] is not None else 0.0,
                    float(option['bs_theoretical']) if option['bs_theoretical'] is not None else 0.0,
                    str(option['moneyness']),
                    float(option['weight']) if option['weight'] is not None else 0.0,
                    float(option['spot_price']) if option['spot_price'] is not None else 0.0
                )
                
                insert_detail_query = """
                INSERT INTO option_details (
                    snapshot_id, option_symbol, strike, category, due_date,
                    days_to_maturity, close_price, volume, bid, ask,
                    bid_volume, ask_volume, calculated_iv, bs_theoretical,
                    moneyness, weight, spot_price
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                self.execute_query(insert_detail_query, option_params)
            
            logging.info(f"✅ Snapshot armazenado: {ticker_clean} - {len(processed_options)} opções")
            return snapshot_id
            
        except Exception as e:
            logging.error(f"Erro ao armazenar snapshot: {e}")
            raise
    
    def capture_current_flow(self, ticker):
        """Captura flow atual de um ticker (função principal)"""
        logging.info(f"🚀 Iniciando captura de flow para {ticker}")
        
        try:
            # 1. Buscar opções atuais
            options_data = self.get_current_options(ticker)
            if not options_data:
                raise ValueError(f"Nenhuma opção encontrada para {ticker}")
            
            # 2. Processar opções
            processed_options = self.process_options_data(options_data)
            if not processed_options:
                raise ValueError(f"Nenhuma opção válida processada para {ticker}")
            
            # 3. Calcular métricas de flow
            flow_metrics = self.calculate_flow_metrics(processed_options)
            if not flow_metrics:
                raise ValueError(f"Erro ao calcular métricas de flow para {ticker}")
            
            # 4. Armazenar no banco
            snapshot_id = self.store_flow_snapshot(ticker, flow_metrics, processed_options)
            
            # 5. Retornar resultado
            result = {
                'ticker': ticker.replace('.SA', '').upper(),
                'timestamp': datetime.now().isoformat(),
                'snapshot_id': snapshot_id,
                'metrics': flow_metrics,
                'options_processed': len(processed_options),
                'success': True
            }
            
            logging.info(f"✅ Flow capturado com sucesso para {ticker}")
            return result
            
        except Exception as e:
            logging.error(f"❌ Erro ao capturar flow para {ticker}: {e}")
            raise

# Instância global do serviço
flow_service = FlowTrackerV2()

def convert_to_json_serializable(obj):
    """Converte tipos numpy/pandas para tipos Python nativos"""
    if hasattr(obj, 'item'):
        return obj.item()
    elif hasattr(obj, 'tolist'):
        return obj.tolist()
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, dict):
        return {key: convert_to_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_json_serializable(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_to_json_serializable(item) for item in obj)
    else:
        return obj
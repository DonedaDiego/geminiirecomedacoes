import requests
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import plotly.subplots as sp
from datetime import datetime, timedelta
import numpy as np
import json
import os
import warnings
warnings.filterwarnings('ignore')

class VolatilityImpliedService:
    def __init__(self):
        self.token = self._load_token()
        self.base_url = "https://api.oplab.com.br/v3/market/historical/options"
        self.headers = {
            "Access-Token": self.token,
            "Content-Type": "application/json"
        }
        print(f"✅ VolatilityImpliedService inicializado")
    
    def _load_token(self):
        """Carrega o token das variáveis de ambiente ou config"""
        # 1. Tentar variável de ambiente primeiro (Railway)
        token = os.environ.get('OPLAB_TOKEN')
        if token:
            print("✅ Token OpLab carregado da variável de ambiente")
            return token
        
        # 2. Tentar arquivo config.json
        config_paths = ['config.json', 'backend/config.json', '../config.json']
        
        for config_path in config_paths:
            try:
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    token = config.get('token') or config.get('oplab_token')
                    if token:
                        print(f"✅ Token OpLab carregado de {config_path}")
                        return token
            except Exception as e:
                print(f"⚠️ Erro ao ler {config_path}: {e}")
                continue
        
        # 3. Token padrão como fallback
        default_token = "Z0ZcoMO3V1kByWw4UWmnodYkZWrHs1vLCF3ry0ApsyYabWNV5jsiAQP6YOREHmPf--mQVXl2FfHYxRFCsA1qDtzw==--Y2Y3YTRmNGRjNzI5NTUzMDc3N2YwOTY2NDRhZjJjMDI="
        print("⚠️ Usando token padrão")
        return default_token
    
    def get_historical_data(self, ticker, from_date, to_date, symbol=None):
        """Busca dados históricos das opções"""
        url = f"{self.base_url}/{ticker}/{from_date}/{to_date}"
        
        params = {}
        if symbol:
            params['symbol'] = symbol
        
        print(f"🔍 Buscando dados das opções: {ticker} ({from_date} a {to_date})")
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Dados das opções obtidos: {len(data)} registros")
                return data
            else:
                print(f"❌ Erro na API: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Erro na requisição: {e}")
            return None
    
    def get_spot_price(self, ticker, from_date, to_date):
        """Busca preço do ativo via yfinance"""
        try:
            ticker_yf = f"{ticker}.SA" if not ticker.endswith('.SA') else ticker
            
            print(f"📈 Buscando preço do ativo: {ticker_yf}")
            stock = yf.Ticker(ticker_yf)
            hist = stock.history(start=from_date, end=to_date)
            
            if not hist.empty:
                print(f"✅ Preços obtidos: {len(hist)} registros")
                return hist
            else:
                print("❌ Nenhum dado de preço encontrado")
                return None
                
        except Exception as e:
            print(f"❌ Erro ao buscar preços: {e}")
            return None
    
    def process_options_data(self, data):
        """Processa dados das opções com foco em ATM e liquidez"""
        if not data:
            return pd.DataFrame()
        
        print("📊 Processando dados das opções...")
        df = pd.DataFrame(data)
        
        # Verificar colunas disponíveis
        print(f"Colunas disponíveis: {df.columns.tolist()}")
        
        # Converter datas
        df['time'] = pd.to_datetime(df['time'])
        df['due_date'] = pd.to_datetime(df['due_date'])
        
        # Processar objeto spot se existir
        if 'spot' in df.columns:
            spot_sample = df['spot'].iloc[0] if not df.empty else {}
            if isinstance(spot_sample, dict) and spot_sample:
                try:
                    spot_expanded = pd.json_normalize(df['spot'])
                    spot_expanded.columns = [f'spot_{col}' for col in spot_expanded.columns]
                    df = pd.concat([df.drop('spot', axis=1), spot_expanded], axis=1)
                    print(f"Spot expandido: {spot_expanded.columns.tolist()}")
                except Exception as e:
                    print(f"⚠️ Erro ao expandir spot: {e}")
                    df = df.drop('spot', axis=1)
        
        # Filtros de qualidade
        initial_count = len(df)
        
        # 1. Filtro de liquidez: usar premium > 0
        df = df[df['premium'] > 0]
        
        # 2. Filtro de dados válidos
        required_cols = ['premium', 'strike', 'volatility', 'type', 'moneyness']
        for col in required_cols:
            if col in df.columns:
                df = df.dropna(subset=[col])
        
        # 3. Expandir para ATM + OTM (mais representativo)
        if 'moneyness' in df.columns:
            # Incluir ATM e OTM (mais líquido que ITM)
            df_filtered = df[df['moneyness'].isin(['ATM', 'OTM'])].copy()
            if len(df_filtered) > 0:
                df = df_filtered
                print(f"Filtrado para ATM + OTM: {len(df)} registros")
            else:
                # Fallback: manter todos se não tiver ATM/OTM
                print(f"Mantendo todos os registros: {len(df)}")
        
        print(f"✅ Após filtros: {len(df)} registros (era {initial_count})")
        
        return df
    
    def calculate_historical_volatility(self, price_data, window=30):
        """Calcula volatilidade histórica e sua média"""
        if price_data is None or price_data.empty:
            return pd.Series(), None
        
        print(f"📊 Calculando volatilidade histórica (janela: {window} dias)")
        
        # Calcular retornos logarítmicos
        returns = np.log(price_data['Close'] / price_data['Close'].shift(1))
        
        # Volatilidade anualizada (rolling window)
        vol_hist = returns.rolling(window=window).std() * np.sqrt(252) * 100
        
        # Média da volatilidade histórica (últimos 6 meses)
        vol_hist_mean = vol_hist.tail(126).mean()  # ~6 meses
        
        return vol_hist, vol_hist_mean
    
    def aggregate_daily_metrics(self, df):
        """Agrega métricas diárias com foco em ATM"""
        if df.empty:
            return pd.DataFrame()
        
        print("📊 Agregando métricas diárias...")
        
        # Definir agregações baseadas nas colunas que realmente existem
        agg_dict = {}
        
        if 'volatility' in df.columns:
            agg_dict['volatility'] = 'mean'
        if 'gamma' in df.columns:
            agg_dict['gamma'] = 'mean'
        if 'premium' in df.columns:
            agg_dict['premium'] = 'mean'
        if 'delta' in df.columns:
            agg_dict['delta'] = 'mean'
        if 'vega' in df.columns:
            agg_dict['vega'] = 'mean'
        if 'theta' in df.columns:
            agg_dict['theta'] = 'mean'
        
        # Usar uma coluna existente para contar registros
        if 'symbol' in df.columns:
            agg_dict['symbol'] = 'count'
        
        print(f"Agregações a serem aplicadas: {agg_dict}")
        
        # Agrupar por data e tipo
        daily_agg = df.groupby(['time', 'type']).agg(agg_dict).round(4)
        daily_agg = daily_agg.reset_index()
        
        # Separar calls e puts
        daily_data = []
        for date in daily_agg['time'].unique():
            date_data = daily_agg[daily_agg['time'] == date]
            
            row = {'date': date}
            
            # Dados de calls
            calls = date_data[date_data['type'] == 'CALL']
            if not calls.empty:
                if 'volatility' in agg_dict:
                    row['iv_call'] = calls['volatility'].iloc[0]
                if 'gamma' in agg_dict:
                    row['gamma_call'] = calls['gamma'].iloc[0]
                if 'premium' in agg_dict:
                    row['premium_call'] = calls['premium'].iloc[0]
                if 'delta' in agg_dict:
                    row['delta_call'] = calls['delta'].iloc[0]
                if 'symbol' in agg_dict:
                    row['count_call'] = calls['symbol'].iloc[0]
            
            # Dados de puts
            puts = date_data[date_data['type'] == 'PUT']
            if not puts.empty:
                if 'volatility' in agg_dict:
                    row['iv_put'] = puts['volatility'].iloc[0]
                if 'gamma' in agg_dict:
                    row['gamma_put'] = puts['gamma'].iloc[0]
                if 'premium' in agg_dict:
                    row['premium_put'] = puts['premium'].iloc[0]
                if 'delta' in agg_dict:
                    row['delta_put'] = puts['delta'].iloc[0]
                if 'symbol' in agg_dict:
                    row['count_put'] = puts['symbol'].iloc[0]
            
            # VI média ponderada (se tiver ambos call e put)
            if 'iv_call' in row and 'iv_put' in row:
                weight_call = row.get('count_call', 1)
                weight_put = row.get('count_put', 1)
                total_weight = weight_call + weight_put
                
                row['iv_avg'] = (
                    row['iv_call'] * weight_call + 
                    row['iv_put'] * weight_put
                ) / total_weight
            elif 'iv_call' in row:
                row['iv_avg'] = row['iv_call']
            elif 'iv_put' in row:
                row['iv_avg'] = row['iv_put']
            
            daily_data.append(row)
        
        result = pd.DataFrame(daily_data)
        print(f"✅ Métricas diárias agregadas: {len(result)} dias")
        
        if not result.empty:
            print(f"Colunas finais: {result.columns.tolist()}")
        
        return result
    
    def calculate_options_signal(self, daily_metrics, vol_hist):
        """Calcula sinal baseado APENAS no momentum do gamma (calls vs puts)"""
        if daily_metrics.empty:
            return daily_metrics
        
        print("🎯 Calculando Options Signal (APENAS Gamma Momentum)...")
        
        try:
            signal_list = []
            
            for i, row in daily_metrics.iterrows():
                gamma_call = row.get('gamma_call', np.nan)
                gamma_put = row.get('gamma_put', np.nan)
                
                if pd.isna(gamma_call) or pd.isna(gamma_put):
                    signal_list.append(0)
                    continue
                
                # Sinal baseado APENAS na relação Gamma Call vs Put
                # Positivo = Calls dominando (bias de alta)
                # Negativo = Puts dominando (bias de baixa)
                
                # Calcular diferença percentual entre gamma call e put
                total_gamma = gamma_call + gamma_put
                
                if total_gamma > 0:
                    # % de participação das calls no gamma total
                    call_dominance = (gamma_call / total_gamma) - 0.5  # -0.5 a +0.5
                    
                    # Converter para escala -100 a +100
                    gamma_signal = call_dominance * 200  # -100 a +100
                    gamma_signal = max(-100, min(100, gamma_signal))
                else:
                    gamma_signal = 0
                
                signal_list.append(gamma_signal)
            
            # Adicionar ao DataFrame original
            daily_metrics['options_signal'] = signal_list
            print(f"✅ Options Signal calculado para {len(signal_list)} registros (APENAS Gamma)")
            
            return daily_metrics
            
        except Exception as e:
            print(f"❌ Erro ao calcular Options Signal: {e}")
            return daily_metrics
    
    def create_analysis(self, ticker, period_days=252):
        """Análise completa de volatilidade implícita"""
        print(f"\n{'='*60}")
        print(f"📊 ANÁLISE DE VOLATILIDADE IMPLÍCITA - {ticker}")
        print(f"Período: {period_days} dias")
        print(f"{'='*60}")
        
        try:
            # Datas
            to_date = datetime.now()
            from_date = to_date - timedelta(days=period_days + 50)
            
            to_date_str = to_date.strftime('%Y-%m-%d')
            from_date_str = from_date.strftime('%Y-%m-%d')
            
            # 1. Buscar dados das opções
            options_data = self.get_historical_data(ticker, from_date_str, to_date_str)
            if not options_data:
                return {
                    'success': False,
                    'error': 'Não foi possível obter dados das opções'
                }
            
            # 2. Buscar preços do ativo
            price_data = self.get_spot_price(ticker, from_date_str, to_date_str)
            if price_data is None:
                return {
                    'success': False,
                    'error': 'Não foi possível obter preços do ativo'
                }
            
            # 3. Processar dados
            df_options = self.process_options_data(options_data)
            if df_options.empty:
                return {
                    'success': False,
                    'error': 'Não há dados de opções após processamento'
                }
            
            # 4. Agregar métricas diárias
            daily_metrics = self.aggregate_daily_metrics(df_options)
            if daily_metrics.empty:
                return {
                    'success': False,
                    'error': 'Não foi possível agregar métricas diárias'
                }
            
            # 5. Calcular volatilidade histórica
            vol_hist, vol_hist_mean = self.calculate_historical_volatility(price_data, window=30)
            
            # 6. Calcular Options Signal
            daily_metrics = self.calculate_options_signal(daily_metrics, vol_hist)
            
            # 7. Preparar dados para gráficos
            chart_data = self.prepare_chart_data(price_data, daily_metrics, vol_hist)
            
            # 8. Calcular estatísticas finais
            current_price = float(price_data['Close'].iloc[-1])
            
            # Garantir que o sinal seja um float válido
            if not daily_metrics.empty and 'options_signal' in daily_metrics.columns:
                last_signal = daily_metrics['options_signal'].iloc[-1]
                current_signal = float(last_signal) if not pd.isna(last_signal) else 0.0
            else:
                current_signal = 0.0
            
            # 9. Interpretar sinal
            signal_interpretation = self.interpret_signal(current_signal)
            
            # Calcular médias de forma segura
            iv_mean = None
            if not daily_metrics.empty and 'iv_avg' in daily_metrics.columns:
                iv_mean_val = daily_metrics['iv_avg'].mean()
                if not pd.isna(iv_mean_val):
                    iv_mean = float(iv_mean_val)
            
            vol_hist_mean_safe = None
            if vol_hist_mean is not None and not pd.isna(vol_hist_mean):
                vol_hist_mean_safe = float(vol_hist_mean)
            
            result = {
                'success': True,
                'ticker': ticker,
                'period_days': period_days,
                'current_price': current_price,
                'current_signal': current_signal,
                'signal_interpretation': signal_interpretation,
                'vol_hist_mean': vol_hist_mean_safe,
                'iv_mean': iv_mean,
                'chart_data': chart_data,
                'timestamp': datetime.now().isoformat()
            }
            
            print("✅ Análise concluída com sucesso!")
            return result
            
        except Exception as e:
            print(f"❌ Erro durante análise: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def prepare_chart_data(self, price_data, daily_metrics, vol_hist):
        """Prepara dados para gráficos"""
        try:
            chart_data = {}
            
            # Dados de preços
            if price_data is not None and not price_data.empty:
                chart_data['prices'] = {
                    'dates': price_data.index.strftime('%Y-%m-%d').tolist(),
                    'values': [float(x) for x in price_data['Close'].tolist()]
                }
            
            # Dados de volatilidade histórica
            if vol_hist is not None and not vol_hist.empty:
                chart_data['vol_hist'] = {
                    'dates': vol_hist.index.strftime('%Y-%m-%d').tolist(),
                    'values': [float(x) if not pd.isna(x) else 0 for x in vol_hist.tolist()]
                }
            
            # Métricas diárias - converter para tipos serializáveis
            if not daily_metrics.empty:
                records = []
                for _, row in daily_metrics.iterrows():
                    record = {}
                    for col in daily_metrics.columns:
                        value = row[col]
                        if pd.isna(value):
                            record[col] = None
                        elif col == 'date':
                            record[col] = value.strftime('%Y-%m-%d') if hasattr(value, 'strftime') else str(value)
                        elif isinstance(value, (int, float)):
                            record[col] = float(value)
                        else:
                            record[col] = str(value)
                    records.append(record)
                chart_data['daily_metrics'] = records
            else:
                chart_data['daily_metrics'] = []
            
            return chart_data
            
        except Exception as e:
            print(f"❌ Erro ao preparar dados do gráfico: {e}")
            import traceback
            traceback.print_exc()
            return {
                'prices': {'dates': [], 'values': []},
                'vol_hist': {'dates': [], 'values': []},
                'daily_metrics': []
            }
    
    def interpret_signal(self, signal):
        """Interpreta o sinal baseado APENAS no gamma (calls vs puts)"""
        if signal >= 60:
            return {
                'status': 'CALLS DOMINANDO',
                'description': 'Gamma das calls muito superior - Forte bias altista no mercado de opções',
                'recommendation': 'Calls agressivos, posições de alta',
                'color': 'green',
                'confidence': 'Muito Alta'
            }
        elif signal >= 30:
            return {
                'status': 'BIAS DE CALLS',
                'description': 'Gamma das calls superior - Tendência altista moderada',
                'recommendation': 'Preferência por calls, bull spreads',
                'color': 'lightgreen',
                'confidence': 'Alta'
            }
        elif signal >= 10:
            return {
                'status': 'LEVE CALL',
                'description': 'Calls ligeiramente favorecidas',
                'recommendation': 'Leve preferência por calls',
                'color': 'yellowgreen',
                'confidence': 'Média'
            }
        elif signal >= -10:
            return {
                'status': 'NEUTRO',
                'description': 'Gamma equilibrado entre calls e puts',
                'recommendation': 'Sem bias direcional, estratégias neutras',
                'color': 'gray',
                'confidence': 'Baixa'
            }
        elif signal >= -30:
            return {
                'status': 'LEVE PUT',
                'description': 'Puts ligeiramente favorecidas',
                'recommendation': 'Leve preferência por puts',
                'color': 'orange',
                'confidence': 'Média'
            }
        elif signal >= -60:
            return {
                'status': 'BIAS DE PUTS',
                'description': 'Gamma das puts superior - Tendência baixista moderada',
                'recommendation': 'Preferência por puts, bear spreads',
                'color': 'darkorange',
                'confidence': 'Alta'
            }
        else:
            return {
                'status': 'PUTS DOMINANDO',
                'description': 'Gamma das puts muito superior - Forte bias baixista no mercado de opções',
                'recommendation': 'Puts agressivos, posições de baixa',
                'color': 'red',
                'confidence': 'Muito Alta'
            }

# Função standalone para uso direto
def analyze_volatility_implied(ticker, period_days=252):
    """Função standalone para análise de VI"""
    service = VolatilityImpliedService()
    return service.create_analysis(ticker, period_days)

if __name__ == "__main__":
    # Teste rápido
    result = analyze_volatility_implied("PETR4", 126)
    
    if result['success']:
        print(f"✅ Teste executado com sucesso!")
        print(f"📊 Sinal atual: {result['current_signal']:.1f}")
        print(f"💰 Preço atual: R$ {result['current_price']:.2f}")
        print(f"📈 Status: {result['signal_interpretation']['status']}")
    else:
        print(f"❌ Erro no teste: {result['error']}")
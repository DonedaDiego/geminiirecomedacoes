import yfinance as yf
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import re
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

class OpcoesService:
    def __init__(self):
        self.oplab_token = os.getenv('OPLAB_TOKEN', '')
        self.session = self.criar_sessao_http()
    
    def criar_sessao_http(self):
        """Cria sessão HTTP com retry para OpLab"""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session
    
    def get_ticker_basic_info(self, ticker: str) -> Optional[Dict]:
        """Obtém preço atual via yfinance"""
        try:
            print(f" Buscando preço {ticker} via yfinance...")
            stock = yf.Ticker(f"{ticker}.SA")
            hist = stock.history(period="5d")
            
            if hist.empty:
                print(f" Nenhum histórico para {ticker}")
                return None
            
            current_price = float(hist['Close'].iloc[-1])
            prev_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current_price
            change = current_price - prev_close
            change_pct = (change / prev_close * 100) if prev_close != 0 else 0
            
            print(f" {ticker}: R$ {current_price:.2f} ({change:+.2f} / {change_pct:+.2f}%)")
            
            return {
                'ticker': ticker,
                'name': f'{ticker} - Ação',
                'current_price': round(current_price, 2),
                'change': round(change, 2),
                'change_percent': round(change_pct, 2),
                'volume': int(hist['Volume'].iloc[-1]) if 'Volume' in hist.columns else 0,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f" Erro yfinance {ticker}: {e}")
            return None
    
    def get_options_data(self, ticker: str) -> Optional[List[Dict]]:
        """Obtém dados de opções via OpLab"""
        try:
            if not self.oplab_token:
                print(" OPLAB_TOKEN não configurado")
                return None
            
            url = f"https://api.oplab.com.br/v3/market/options/{ticker}"
            print(f"🔍 Buscando opções: {url}")
            
            response = self.session.get(
                url,
                headers={"Access-Token": self.oplab_token},
                timeout=15
            )
            
            print(f"📡 OpLab Status: {response.status_code}")
            
            if response.status_code != 200:
                print(f" OpLab erro HTTP: {response.status_code}")
                return None
            
            dados_opcoes = response.json()
            
            if not dados_opcoes:
                print(f" OpLab retornou vazio para {ticker}")
                return None
            
            print(f" OpLab: {len(dados_opcoes)} opções brutas")
            
            # Processar opções
            options_list = []
            for opcao in dados_opcoes:
                volume = opcao.get('volume', 0)
                strike = opcao.get('strike', 0)
                symbol = opcao.get('symbol', '')
                categoria = opcao.get('category', '').upper()
                
                # Só opções com volume > 0
                if volume > 0 and strike > 0:
                    options_list.append({
                        'symbol': symbol,
                        'volume': int(volume),
                        'strike': float(strike),
                        'category': categoria,
                        'letra_vencimento': self.extrair_letra_vencimento(symbol)
                    })
            
            print(f" {len(options_list)} opções com volume > 0")
            return options_list if options_list else None
            
        except Exception as e:
            print(f" Erro OpLab {ticker}: {e}")
            return None
    
    def extrair_letra_vencimento(self, symbol: str) -> str:
        """Extrai letra de vencimento do symbol"""
        try:
            # Padrão: PETR4F240 -> F
            match = re.search(r'[A-Z]{4,5}([A-Z])\d+', symbol)
            if match:
                return match.group(1)
        except:
            pass
        return 'X'
    
    def filtrar_opcoes_por_letras(self, options_data: List[Dict], letras: List[str]) -> Tuple[List[Dict], List[Dict]]:
        """Filtra opções pelas letras de vencimento"""
        calls_data = []
        puts_data = []
        
        for opcao in options_data:
            letra = opcao.get('letra_vencimento', '')
            categoria = opcao.get('category', '')
            
            if letra in letras:
                if categoria == 'CALL':
                    calls_data.append(opcao)
                elif categoria == 'PUT':
                    puts_data.append(opcao)
        
        print(f" Filtro {letras}: {len(calls_data)} calls + {len(puts_data)} puts")
        return calls_data, puts_data
    
    def agrupar_por_strike(self, calls_data: List[Dict], puts_data: List[Dict]) -> Dict:
        """Agrupa volumes por strike"""
        strikes_data = {}
        
        for opcao in calls_data + puts_data:
            strike = opcao['strike']
            if strike not in strikes_data:
                strikes_data[strike] = {'calls_volume': 0, 'puts_volume': 0}
            
            if opcao['category'] == 'CALL':
                strikes_data[strike]['calls_volume'] += opcao['volume']
            else:
                strikes_data[strike]['puts_volume'] += opcao['volume']
        
        return strikes_data
    
    def hunter_walls_analysis(self, ticker: str, grupos_vencimentos: List[List[str]]) -> Optional[Dict]:
        """Análise Hunter Walls completa"""
        try:
            print(f" Iniciando Hunter Walls para {ticker}")
            
            # 1. Preço via yfinance
            ticker_info = self.get_ticker_basic_info(ticker)
            if not ticker_info:
                return None
            
            # 2. Opções via OpLab
            options_data = self.get_options_data(ticker)
            if not options_data:
                return None
            
            # 3. Processar grupos
            grupos_processados = {}
            
            for i, grupo in enumerate(grupos_vencimentos):
                nome_grupo = f"Grupo {i+1} ({','.join(grupo)})"
                print(f" Processando {nome_grupo}")
                
                # Filtrar por letras
                calls_grupo, puts_grupo = self.filtrar_opcoes_por_letras(options_data, grupo)
                
                if not calls_grupo and not puts_grupo:
                    print(f"⚠️ {nome_grupo}: sem opções")
                    continue
                
                # Agrupar por strike
                strikes_data = self.agrupar_por_strike(calls_grupo, puts_grupo)
                
                # Filtrar strikes significativos
                volume_min = 30
                strikes_filtrados = {
                    k: v for k, v in strikes_data.items()
                    if v['calls_volume'] + v['puts_volume'] >= volume_min
                }
                
                if not strikes_filtrados:
                    print(f"⚠️ {nome_grupo}: sem strikes significativos")
                    continue
                
                # Top strikes
                top_strikes = sorted(
                    strikes_filtrados.items(),
                    key=lambda x: x[1]['calls_volume'] + x[1]['puts_volume'],
                    reverse=True
                )[:25]
                
                strikes_ordenados = sorted([item[0] for item in top_strikes])
                
                grupos_processados[nome_grupo] = {
                    'strikes': strikes_ordenados,
                    'strikes_data': strikes_data,
                    'calls_data': calls_grupo,
                    'puts_data': puts_grupo,
                    'total_calls': sum(c['volume'] for c in calls_grupo),
                    'total_puts': sum(p['volume'] for p in puts_grupo),
                    'num_opcoes': len(calls_grupo) + len(puts_grupo),
                    'grupo_letras': grupo
                }
                
                print(f" {nome_grupo}: {len(strikes_ordenados)} strikes")
            
            if not grupos_processados:
                print(" Nenhum grupo processado")
                return None
            
            # 4. Preparar dados para frontend
            return {
                'ticker_info': ticker_info,
                'chart_data': self.preparar_dados_grafico(grupos_processados, ticker_info['current_price']),
                'summary': self.preparar_resumo(grupos_processados, ticker_info),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f" Erro Hunter Walls: {e}")
            return None
    
    def preparar_dados_grafico(self, grupos: Dict, preco_atual: float) -> Dict:
        """Prepara dados para gráficos Plotly"""
        chart_data = {}
        
        for nome_grupo, dados in grupos.items():
            strikes = dados['strikes']
            strikes_data = dados['strikes_data']
            
            chart_data[nome_grupo] = {
                'labels': [f"R$ {s:.2f}" for s in strikes],
                'calls_volumes': [-strikes_data[s]['calls_volume'] for s in strikes],
                'puts_volumes': [strikes_data[s]['puts_volume'] for s in strikes],
                'strikes_values': strikes,
                'current_price_index': self.encontrar_strike_proximo(strikes, preco_atual)
            }
        
        return chart_data
    
    def encontrar_strike_proximo(self, strikes: List[float], preco: float) -> int:
        """Encontra índice do strike mais próximo"""
        if not strikes:
            return 0
        
        distancias = [abs(s - preco) for s in strikes]
        return distancias.index(min(distancias))
    
    def preparar_resumo(self, grupos: Dict, ticker_info: Dict) -> Dict:
        """Prepara resumo estatístico"""
        total_calls = sum(g['total_calls'] for g in grupos.values())
        total_puts = sum(g['total_puts'] for g in grupos.values())
        total_volume = total_calls + total_puts
        
        grupos_resumo = []
        for nome, dados in grupos.items():
            ratio = dados['total_puts'] / dados['total_calls'] if dados['total_calls'] > 0 else 0
            pct_total = (dados['total_calls'] + dados['total_puts']) / total_volume * 100 if total_volume > 0 else 0
            
            # Top 3 de cada tipo
            top_calls = sorted(dados['calls_data'], key=lambda x: x['volume'], reverse=True)[:3]
            top_puts = sorted(dados['puts_data'], key=lambda x: x['volume'], reverse=True)[:3]
            
            grupos_resumo.append({
                'nome': nome,
                'letras': dados['grupo_letras'],
                'total_calls': dados['total_calls'],
                'total_puts': dados['total_puts'],
                'total_volume': dados['total_calls'] + dados['total_puts'],
                'put_call_ratio': round(ratio, 2),
                'percent_of_total': round(pct_total, 1),
                'num_opcoes': dados['num_opcoes'],
                'top_calls': top_calls,
                'top_puts': top_puts
            })
        
        return {
            'ticker_info': ticker_info,
            'total_calls': total_calls,
            'total_puts': total_puts,
            'total_volume': total_volume,
            'put_call_ratio_geral': round(total_puts / total_calls, 2) if total_calls > 0 else 0,
            'percent_calls': round(total_calls / total_volume * 100, 1) if total_volume > 0 else 0,
            'percent_puts': round(total_puts / total_volume * 100, 1) if total_volume > 0 else 0,
            'grupos': grupos_resumo
        }

    # ===== FUNÇÕES DE VOLUME HISTÓRICO =====
    
    def volume_historico_analysis(self, ticker: str) -> Optional[Dict]:
        """Análise de volume histórico dos últimos 7 dias úteis (otimizado)"""
        try:
            print(f" Iniciando análise histórica OTIMIZADA para {ticker}")
            
            # 1. Obter dados atuais
            opcoes_hoje = self.get_options_data(ticker)
            if not opcoes_hoje:
                return None
            
            # 2. Extrair tickers reais das opções de hoje
            tickers_reais = list(set([opcao['symbol'] for opcao in opcoes_hoje]))
            print(f"📋 {len(tickers_reais)} tickers únicos encontrados")
            
            # 3. Obter dados históricos REDUZIDOS (7 dias úteis)
            print(" Buscando dados históricos (7 dias)...")
            historico_7d = self.get_historical_volume_data_real(tickers_reais, days=7)
            
            # 4. Processar análise
            resultado = self.processar_analise_historica(opcoes_hoje, historico_7d)
            
            print(f" Análise histórica OTIMIZADA concluída para {ticker}")
            return resultado
            
        except Exception as e:
            print(f" Erro na análise histórica: {e}")
            return None

    def get_historical_volume_data_real(self, tickers_reais: List[str], days: int = 7) -> List[Dict]:
        """Buscar dados históricos OTIMIZADO - apenas 7 dias úteis"""
        try:
            if not self.oplab_token:
                print(" OPLAB_TOKEN não configurado")
                return []
            
            dados_consolidados = []
            end_date = datetime.now()
            
            # OTIMIZAÇÃO 1: Batch menor para evitar timeout
            batch_size = 20  # Reduzido de 30 para 20
            ticker_batches = [tickers_reais[i:i + batch_size] for i in range(0, len(tickers_reais), batch_size)]
            
            print(f"📦 Processando {len(tickers_reais)} tickers em {len(ticker_batches)} lotes (OTIMIZADO)")
            
            # OTIMIZAÇÃO 2: Buscar apenas 7 dias úteis (máximo 14 dias calendário)
            dias_coletados = 0
            max_dias_busca = 14  # Reduzido de 35 para 14
            
            for i in range(max_dias_busca):
                if dias_coletados >= days:  # Parar quando atingir 7 dias úteis
                    print(f" Meta atingida: {dias_coletados} dias úteis coletados")
                    break
                    
                date = end_date - timedelta(days=i+1)
                date_str = date.strftime('%Y-%m-%d')
                
                # Skip weekends
                if date.weekday() >= 5:
                    continue
                
                print(f"🔍 Buscando {date_str}... ({dias_coletados+1}/{days})")
                
                volume_dia_total = 0
                calls_volume_dia = 0
                puts_volume_dia = 0
                opcoes_ativas_dia = 0
                
                # OTIMIZAÇÃO 3: Timeout mais agressivo por lote
                for batch_idx, batch_tickers in enumerate(ticker_batches):
                    try:
                        url = "https://api.oplab.com.br/v3/market/historical/instruments"
                        tickers_param = ','.join(batch_tickers)
                        
                        response = self.session.get(
                            url,
                            headers={"Access-Token": self.oplab_token},
                            params={'tickers': tickers_param, 'date': date_str},
                            timeout=10  # Reduzido de 20 para 10 segundos
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            
                            for opcao in data:
                                volume = opcao.get('volume', 0)
                                if volume > 0:
                                    volume_dia_total += volume
                                    opcoes_ativas_dia += 1
                                    
                                    categoria = opcao.get('category', '').upper()
                                    if categoria == 'CALL':
                                        calls_volume_dia += volume
                                    elif categoria == 'PUT':
                                        puts_volume_dia += volume
                        
                        elif response.status_code == 404:
                            # Sem dados para esta data (normal)
                            continue
                        else:
                            print(f"⚠️ HTTP {response.status_code} para lote {batch_idx}")
                    
                    except Exception as batch_error:
                        print(f"⚠️ Erro lote {batch_idx}: {batch_error}")
                        continue
                
                # Salvar dados do dia se houve volume
                if volume_dia_total > 0:
                    dados_consolidados.append({
                        'date': date_str,
                        'volume_total': volume_dia_total,
                        'calls_volume': calls_volume_dia,
                        'puts_volume': puts_volume_dia,
                        'num_opcoes': opcoes_ativas_dia
                    })
                    
                    print(f" {date_str}: {volume_dia_total:,} volume")
                    dias_coletados += 1
                else:
                    print(f"📭 {date_str}: sem volume")
            
            print(f" RESULTADO: {len(dados_consolidados)} dias de dados coletados em análise otimizada")
            return dados_consolidados
            
        except Exception as e:
            print(f" Erro busca histórica otimizada: {e}")
            return []

    def preparar_chart_historico(self, historico: List[Dict], volume_atual: int) -> Dict:
        """Preparar dados para gráfico histórico OTIMIZADO (7 dias)"""
        try:
            # OTIMIZAÇÃO: Usar todos os dados históricos (máximo 7) + hoje
            historico_ordenado = sorted(historico, key=lambda x: x['date'])
            
            dates = [dia['date'] for dia in historico_ordenado]
            volumes = [dia['volume_total'] for dia in historico_ordenado]
            
            # Adicionar hoje
            hoje = datetime.now().strftime('%Y-%m-%d')
            dates.append(hoje)
            volumes.append(volume_atual)
            
            return {
                'dates': dates,
                'volumes': volumes,
                'current_volume': volume_atual,
                'labels': [d.split('-')[1] + '/' + d.split('-')[2] for d in dates]
            }
            
        except Exception as e:
            print(f" Erro chart histórico: {e}")
            return self.preparar_chart_historico_basico(volume_atual)

    def preparar_chart_historico_basico(self, volume_atual: int) -> Dict:
        """Preparar chart básico OTIMIZADO (7 dias)"""
        try:
            # OTIMIZAÇÃO: Criar dados básicos dos últimos 7 dias
            dates = []
            volumes = []
            
            for i in range(6, -1, -1):  # Reduzido de 13 para 6
                date = datetime.now() - timedelta(days=i)
                dates.append(date.strftime('%Y-%m-%d'))
                
                if i == 0:  # Hoje
                    volumes.append(volume_atual)
                else:
                    # Volume estimado menor
                    volumes.append(max(volume_atual // 3, 50))
            
            return {
                'dates': dates,
                'volumes': volumes,
                'current_volume': volume_atual,
                'labels': [d.split('-')[1] + '/' + d.split('-')[2] for d in dates]
            }
            
        except Exception as e:
            print(f" Erro chart básico: {e}")
            return {'dates': [], 'volumes': [], 'current_volume': volume_atual, 'labels': []}

    def encontrar_hot_strike(self, opcoes_hoje: List[Dict]) -> Dict:
        """Encontrar strike mais ativo"""
        try:
            if not opcoes_hoje:
                return {'strike': 0, 'volume': 0, 'type': 'N/A'}
            
            maior_volume = 0
            hot_strike = 0
            hot_type = 'N/A'
            
            for opcao in opcoes_hoje:
                volume = opcao.get('volume', 0)
                if volume > maior_volume:
                    maior_volume = volume
                    hot_strike = opcao.get('strike', 0)
                    hot_type = opcao.get('category', 'N/A')
            
            return {
                'strike': hot_strike,
                'volume': maior_volume,
                'type': hot_type
            }
            
        except Exception as e:
            print(f" Erro hot strike: {e}")
            return {'strike': 0, 'volume': 0, 'type': 'N/A'}

    def processar_analise_historica(self, opcoes_hoje: List[Dict], historico: List[Dict]) -> Dict:
        """Processar dados históricos vs atuais"""
        try:
            # Calcular volume atual
            volume_atual = sum(opt.get('volume', 0) for opt in opcoes_hoje)
            calls_atual = sum(opt.get('volume', 0) for opt in opcoes_hoje if opt.get('category') == 'CALL')
            puts_atual = sum(opt.get('volume', 0) for opt in opcoes_hoje if opt.get('category') == 'PUT')
            
            print(f" Volume atual: {volume_atual:,} (Calls: {calls_atual:,}, Puts: {puts_atual:,})")
            
            # Se não há dados históricos, criar resposta básica
            if not historico or len(historico) == 0:
                print("⚠️ Sem dados históricos suficientes")
                return {
                    'volume_atual': volume_atual,
                    'volume_medio_7d': max(volume_atual // 2, 100),  # Atualizado para 7d
                    'volume_multiplier': 1.5,
                    'calls_atual': calls_atual,
                    'puts_atual': puts_atual,
                    'dominant_type': "CALLS" if calls_atual > puts_atual else "PUTS",
                    'hot_strike': self.encontrar_hot_strike(opcoes_hoje)['strike'],
                    'hot_strike_volume': self.encontrar_hot_strike(opcoes_hoje)['volume'],
                    'hot_strike_type': self.encontrar_hot_strike(opcoes_hoje)['type'],
                    'chart_data': self.preparar_chart_historico_basico(volume_atual),
                    'status': self.classificar_volume_status(1.5),
                    'dias_analisados': 0
                }
            
            # Calcular médias históricas
            volumes_historicos = [dia['volume_total'] for dia in historico if dia['volume_total'] > 0]
            volume_medio = sum(volumes_historicos) / len(volumes_historicos) if volumes_historicos else max(volume_atual // 2, 100)
            
            # Multiplier atual vs média
            volume_multiplier = volume_atual / volume_medio if volume_medio > 0 else 1.0
            
            # Tipo dominante
            if volume_atual > 0:
                dominant_type = "CALLS" if calls_atual > puts_atual else "PUTS"
                dominant_percentage = (max(calls_atual, puts_atual) / volume_atual * 100)
            else:
                dominant_type = "N/A"
                dominant_percentage = 0
            
            # Hot strike
            hot_strike_data = self.encontrar_hot_strike(opcoes_hoje)
            
            # Chart data
            chart_data = self.preparar_chart_historico(historico, volume_atual)
            
            return {
                'volume_atual': volume_atual,
                'volume_medio_7d': int(volume_medio),  # Atualizado para 7d
                'volume_multiplier': round(volume_multiplier, 2),
                'calls_atual': calls_atual,
                'puts_atual': puts_atual,
                'dominant_type': f"{dominant_type} ({dominant_percentage:.1f}%)",
                'hot_strike': hot_strike_data['strike'],
                'hot_strike_volume': hot_strike_data['volume'],
                'hot_strike_type': hot_strike_data['type'],
                'chart_data': chart_data,
                'status': self.classificar_volume_status(volume_multiplier),
                'dias_analisados': len(historico)
            }
            
        except Exception as e:
            print(f" Erro processamento histórico: {e}")
            return {'error': str(e)}

    def analisar_strike_detalhado(self, ticker: str, strike: float) -> Optional[Dict]:
        """Análise detalhada de um strike específico em tempo real"""
        try:
            print(f" Analisando strike detalhado: {ticker} - R$ {strike}")
            
            # 1. Buscar todas as opções atuais
            options_data = self.get_options_data(ticker)
            if not options_data:
                return None
            
            # 2. Filtrar opções do strike específico
            opcoes_strike = [
                opt for opt in options_data 
                if abs(opt['strike'] - strike) < 0.01  # Tolerância para float
            ]
            
            if not opcoes_strike:
                print(f" Nenhuma opção encontrada para strike R$ {strike}")
                return None
            
            # 3. Separar calls e puts
            calls = [opt for opt in opcoes_strike if opt['category'] == 'CALL']
            puts = [opt for opt in opcoes_strike if opt['category'] == 'PUT']
            
            # 4. Calcular métricas
            total_calls_volume = sum(call['volume'] for call in calls)
            total_puts_volume = sum(put['volume'] for put in puts)
            total_volume = total_calls_volume + total_puts_volume
            
            print(f" Strike R$ {strike}: {total_calls_volume} calls + {total_puts_volume} puts = {total_volume} total")
            
            # 5. Preparar resposta (SEM buscar dados detalhados da OpLab)
            return {
                'ticker': ticker,
                'strike': strike,
                'total_volume': total_volume,
                'calls_volume': total_calls_volume,
                'puts_volume': total_puts_volume,
                'calls_count': len(calls),
                'puts_count': len(puts),
                'calls': calls,  # Usar calls ao invés de calls_data
                'puts': puts,    # Usar puts ao invés de puts_data
                'dominant_type': 'CALLS' if total_calls_volume > total_puts_volume else 'PUTS',
                'volume_ratio': round(total_puts_volume / total_calls_volume, 2) if total_calls_volume > 0 else 0,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f" Erro análise strike detalhado: {e}")
            return None

    def get_strike_market_data(self, ticker: str, strike: float, opcoes_strike: List[Dict]) -> Dict:
        """Buscar dados de mercado em tempo real para o strike"""
        try:
            # Dados básicos que já temos
            market_data = {
                'bid_ask_spread': {},
                'implied_volatility': {},
                'time_to_expiry': {},
                'moneyness': {}
            }
            
            # Obter preço atual da ação
            ticker_info = self.get_ticker_basic_info(ticker)
            current_price = ticker_info['current_price'] if ticker_info else 0
            
            # Calcular moneyness
            if current_price > 0:
                moneyness = (current_price - strike) / current_price * 100
                market_data['moneyness'] = {
                    'value': round(moneyness, 2),
                    'status': self.classify_moneyness(moneyness)
                }
            
            # Analisar cada opção do strike
            for opcao in opcoes_strike:
                symbol = opcao['symbol']
                category = opcao['category']
                
                # Tentar buscar dados adicionais via OpLab (se disponível)
                detailed_data = self.get_option_detailed_data(symbol)
                
                key = f"{category.lower()}s"
                if key not in market_data:
                    market_data[key] = []
                
                option_detail = {
                    'symbol': symbol,
                    'volume': opcao['volume'],
                    'strike': opcao['strike'],
                    'bid': detailed_data.get('bid', 0),
                    'ask': detailed_data.get('ask', 0),
                    'last': detailed_data.get('last', 0),
                    'iv': detailed_data.get('implied_volatility', 0),
                    'delta': detailed_data.get('delta', 0),
                    'gamma': detailed_data.get('gamma', 0),
                    'theta': detailed_data.get('theta', 0),
                    'vega': detailed_data.get('vega', 0)
                }
                
                market_data[key].append(option_detail)
            
            return market_data
            
        except Exception as e:
            print(f" Erro dados mercado: {e}")
            return {}

    def get_option_detailed_data(self, symbol: str) -> Dict:
        """Buscar dados detalhados de uma opção específica"""
        try:
            if not self.oplab_token:
                return {}
            
            # Endpoint para dados detalhados (verificar se existe na API OpLab)
            url = f"https://api.oplab.com.br/v3/market/option/{symbol}"
            
            response = self.session.get(
                url,
                headers={"Access-Token": self.oplab_token},
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"⚠️ Dados detalhados não disponíveis para {symbol}")
                return {}
                
        except Exception as e:
            print(f"⚠️ Erro buscar dados detalhados {symbol}: {e}")
            return {}

    def classify_moneyness(self, moneyness: float) -> str:
        """Classificar moneyness da opção"""
        if abs(moneyness) <= 2:
            return "ATM (At The Money)"
        elif moneyness > 2:
            return "ITM (In The Money)" 
        else:
            return "OTM (Out of The Money)"

    def get_strike_detalhes(self, ticker: str, strike: float) -> Optional[Dict]:
        """Buscar detalhes específicos de um strike"""
        try:
            print(f"🔍 Buscando detalhes strike {ticker} R$ {strike}")
            
            # Buscar opções atuais
            options_data = self.get_options_data(ticker)
            if not options_data:
                return None
            
            # Filtrar pelo strike
            opcoes_strike = [
                opt for opt in options_data 
                if abs(opt['strike'] - strike) < 0.01
            ]
            
            if not opcoes_strike:
                print(f" Nenhuma opção encontrada para strike R$ {strike}")
                return None
            
            # Separar calls e puts
            calls = [opt for opt in opcoes_strike if opt['category'] == 'CALL']
            puts = [opt for opt in opcoes_strike if opt['category'] == 'PUT']
            
            print(f" Strike R$ {strike}: {len(calls)} calls + {len(puts)} puts")
            
            return {
                'ticker': ticker,
                'strike': strike,
                'calls': calls,
                'puts': puts,
                'calls_volume': sum(c['volume'] for c in calls),
                'puts_volume': sum(p['volume'] for p in puts),
                'total_volume': sum(opt['volume'] for opt in opcoes_strike)
            }
            
        except Exception as e:
            print(f" Erro detalhes strike: {e}")
            return None
    
    
    def classificar_volume_status(self, multiplier: float) -> Dict:
        """Classificar status do volume"""
        if multiplier >= 3.0:
            return {
                'level': 'EXTREMO',
                'color': 'red',
                'icon': '',
                'description': 'Volume extremamente elevado - possível insider activity'
            }
        elif multiplier >= 2.0:
            return {
                'level': 'ALTO',
                'color': 'orange', 
                'icon': '',
                'description': 'Volume significativamente acima da média'
            }
        elif multiplier >= 1.5:
            return {
                'level': 'ELEVADO',
                'color': 'yellow',
                'icon': '',
                'description': 'Volume moderadamente elevado'
            }
        else:
            return {
                'level': 'NORMAL',
                'color': 'green',
                'icon': '', 
                'description': 'Volume dentro do padrão normal'
            }
import yfinance as yf
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import re
import os
from datetime import datetime
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
            print(f"📈 Buscando preço {ticker} via yfinance...")
            stock = yf.Ticker(f"{ticker}.SA")
            hist = stock.history(period="5d")
            
            if hist.empty:
                print(f"❌ Nenhum histórico para {ticker}")
                return None
            
            current_price = float(hist['Close'].iloc[-1])
            prev_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current_price
            change = current_price - prev_close
            change_pct = (change / prev_close * 100) if prev_close != 0 else 0
            
            print(f"✅ {ticker}: R$ {current_price:.2f} ({change:+.2f} / {change_pct:+.2f}%)")
            
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
            print(f"❌ Erro yfinance {ticker}: {e}")
            return None
    
    def get_options_data(self, ticker: str) -> Optional[List[Dict]]:
        """Obtém dados de opções via OpLab"""
        try:
            if not self.oplab_token:
                print("❌ OPLAB_TOKEN não configurado")
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
                print(f"❌ OpLab erro HTTP: {response.status_code}")
                return None
            
            dados_opcoes = response.json()
            
            if not dados_opcoes:
                print(f"❌ OpLab retornou vazio para {ticker}")
                return None
            
            print(f"✅ OpLab: {len(dados_opcoes)} opções brutas")
            
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
            
            print(f"✅ {len(options_list)} opções com volume > 0")
            return options_list if options_list else None
            
        except Exception as e:
            print(f"❌ Erro OpLab {ticker}: {e}")
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
        
        print(f"✅ Filtro {letras}: {len(calls_data)} calls + {len(puts_data)} puts")
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
                print(f"📊 Processando {nome_grupo}")
                
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
                
                print(f"✅ {nome_grupo}: {len(strikes_ordenados)} strikes")
            
            if not grupos_processados:
                print("❌ Nenhum grupo processado")
                return None
            
            # 4. Preparar dados para frontend
            return {
                'ticker_info': ticker_info,
                'chart_data': self.preparar_dados_grafico(grupos_processados, ticker_info['current_price']),
                'summary': self.preparar_resumo(grupos_processados, ticker_info),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Erro Hunter Walls: {e}")
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
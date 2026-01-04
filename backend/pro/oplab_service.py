import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Importar GammaService para buscar GEX real
try:
    from pro.gamma_service import GammaService
    GAMMA_SERVICE_AVAILABLE = True
except ImportError:
    GAMMA_SERVICE_AVAILABLE = False
    print("⚠️ gamma_service.py não encontrado - modo standalone")

class OplabService:
    """
    Serviço para buscar dados REAIS de opções da OpLab
    e calcular estruturas inteligentes baseadas em GEX descoberto
    """
    
    def __init__(self):
        self.oplab_token = os.getenv('OPLAB_TOKEN', '')
        self.session = self._criar_sessao_http()
        
        # Inicializar GammaService se disponível
        if GAMMA_SERVICE_AVAILABLE:
            self.gamma_service = GammaService()
            print("✅ GammaService integrado - dados reais de GEX disponíveis")
        else:
            self.gamma_service = None
            print("⚠️ GammaService não disponível - modo standalone")
    
    def _criar_sessao_http(self):
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
    
    def buscar_opcoes_ativas(self, ticker: str) -> Optional[List[Dict]]:
        """
        Busca todas as opções ativas com volume/OI > 0
        """
        try:
            if not self.oplab_token:
                print(" OPLAB_TOKEN não configurado")
                return None
            
            url = f"https://api.oplab.com.br/v3/market/options/{ticker}"
            print(f"🔍 Buscando opções OpLab: {ticker}")
            
            response = self.session.get(
                url,
                headers={"Access-Token": self.oplab_token},
                timeout=15
            )
            
            if response.status_code != 200:
                print(f" OpLab HTTP {response.status_code}")
                return None
            
            dados_opcoes = response.json()
            
            if not dados_opcoes:
                print(f"⚠️ OpLab retornou vazio para {ticker}")
                return None
            
            # Filtrar opções com liquidez
            opcoes_liquidas = []
            for opcao in dados_opcoes:
                volume = opcao.get('volume', 0)
                oi = opcao.get('openInterest', 0)
                strike = opcao.get('strike', 0)
                
                # Critério: volume > 0 OU OI > 10
                if (volume > 0 or oi > 10) and strike > 0:
                    opcoes_liquidas.append({
                        'symbol': opcao.get('symbol', ''),
                        'strike': float(strike),
                        'category': opcao.get('category', '').upper(),
                        'volume': int(volume),
                        'open_interest': int(oi),
                        'bid': float(opcao.get('bid', 0)),
                        'ask': float(opcao.get('ask', 0)),
                        'last': float(opcao.get('last', 0)),
                        'expiration': opcao.get('expirationDate', ''),
                        'liquidity_score': volume + (oi * 0.5)  # Score de liquidez
                    })
            
            print(f"✅ {len(opcoes_liquidas)} opções com liquidez encontradas")
            return opcoes_liquidas if opcoes_liquidas else None
            
        except Exception as e:
            print(f" Erro OpLab {ticker}: {e}")
            return None
    
    def filtrar_strikes_por_liquidez(self, opcoes: List[Dict], min_liquidez: float = 50) -> List[float]:
        """
        Extrai strikes únicos com liquidez mínima
        """
        strikes_liquidez = {}
        
        for opcao in opcoes:
            strike = opcao['strike']
            liquidez = opcao['liquidity_score']
            
            if strike not in strikes_liquidez:
                strikes_liquidez[strike] = 0
            
            strikes_liquidez[strike] += liquidez
        
        # Filtrar por liquidez mínima
        strikes_validos = [
            strike for strike, liq in strikes_liquidez.items()
            if liq >= min_liquidez
        ]
        
        strikes_validos.sort()
        print(f"📊 {len(strikes_validos)} strikes com liquidez >= {min_liquidez}")
        
        return strikes_validos
    
    def encontrar_strike_mais_proximo(self, strikes: List[float], preco_alvo: float) -> Optional[float]:
        """
        Encontra o strike real mais próximo de um preço alvo
        """
        if not strikes:
            return None
        
        strike_mais_proximo = min(strikes, key=lambda x: abs(x - preco_alvo))
        return strike_mais_proximo
    
    def buscar_dados_gex_reais(self, ticker: str, expiration_code: Optional[str] = None) -> Optional[Dict]:
        """
         NOVO - Busca dados REAIS de GEX do gamma_service
        
        Retorna:
        {
            'spot_price': 38.50,
            'flip_strike': 38.00,
            'gex_descoberto': -5000000000,
            'regime': 'Short Gamma',
            'net_gex': -5000000000
        }
        """
        if not self.gamma_service:
            print(" GammaService não disponível")
            return None
        
        try:
            print(f"🔍 Buscando dados GEX reais para {ticker}...")
            
            # Chamar análise completa do GammaService
            resultado = self.gamma_service.analyze_gamma_complete(
                ticker=ticker,
                expiration_code=expiration_code
            )
            
            if not resultado or not resultado.get('success'):
                print(f" Falha ao buscar GEX para {ticker}")
                return None
            
            # Extrair dados relevantes
            dados_gex = {
                'spot_price': resultado['spot_price'],
                'flip_strike': resultado.get('flip_strike'),
                'gex_descoberto': resultado['gex_levels']['total_gex_descoberto'],
                'net_gex': resultado['gex_levels']['total_gex'],
                'regime': resultado['regime'],
                'expiration': resultado.get('data_quality', {}).get('expiration'),
                'liquidity_category': resultado.get('data_quality', {}).get('liquidity_category'),
                'real_data_count': resultado.get('data_quality', {}).get('real_data_count', 0)
            }
            
            print(f"✅ Dados GEX obtidos:")
            print(f"   Spot: R$ {dados_gex['spot_price']:.2f}")
            print(f"   Flip: R$ {dados_gex['flip_strike']:.2f}")
            print(f"   GEX Descoberto: {dados_gex['gex_descoberto']:,.0f}")
            print(f"   Regime: {dados_gex['regime']}")
            print(f"   Vencimento: {dados_gex['expiration']}")
            
            return dados_gex
            
        except Exception as e:
            print(f" Erro ao buscar GEX real: {e}")
            return None
    
    
    def calcular_estruturas_inteligentes(
        self, 
        ticker: str,
        spot_price: float,
        flip_strike: float,
        gex_descoberto: float,
        cenario: Dict,
        opcoes: List[Dict]
    ) -> List[Dict]:
        
        strikes_validos = self.filtrar_strikes_por_liquidez(opcoes)
        
        if not strikes_validos:
            print("Nenhum strike com liquidez suficiente")
            return []
        
        calls = [opt for opt in opcoes if opt['category'] == 'CALL']
        puts = [opt for opt in opcoes if opt['category'] == 'PUT']
        
        estruturas = []
        
        gex_sign = 'SHORT' if gex_descoberto < 0 else 'LONG'
        direction = cenario.get('direction', 'ALTA')
        cenario_num = cenario.get('number', 0)
        
        if gex_sign == 'SHORT':
            if direction == 'ALTA':
                estruturas.extend(self._criar_compra_call(spot_price, flip_strike, strikes_validos, calls))
                
                if cenario_num in [1, 2]:
                    estruturas.extend(self._criar_compra_straddle(spot_price, strikes_validos, calls, puts))
            else:
                estruturas.extend(self._criar_compra_put(spot_price, strikes_validos, puts))
                
                if cenario_num in [5, 6]:
                    estruturas.extend(self._criar_compra_straddle(spot_price, strikes_validos, calls, puts))
        
        else:
            if direction == 'ALTA':
                estruturas.extend(self._criar_venda_put(spot_price, strikes_validos, puts))
                
                if cenario_num == 10 or cenario_num == 12:
                    estruturas.extend(self._criar_venda_coberta(spot_price, strikes_validos, calls))
                
                if cenario_num in [9, 11]:
                    estruturas.extend(self._criar_collar_alta(spot_price, strikes_validos, calls, puts))
                
                if cenario_num == 9:
                    estruturas.extend(self._criar_venda_straddle(spot_price, strikes_validos, calls, puts))
            else:
                estruturas.extend(self._criar_collar_baixa(spot_price, strikes_validos, calls, puts))
                
                if cenario_num == 13:
                    estruturas.extend(self._criar_venda_straddle(spot_price, strikes_validos, calls, puts))
        
        print(f"\n✅ {len(estruturas)} estruturas calculadas")
        return estruturas

    def _criar_compra_call(self, spot, flip, strikes, calls):
        call_strike = self.encontrar_strike_mais_proximo(strikes, max(flip, spot))
        
        if not call_strike:
            return []
        
        call_data = self._buscar_dados_opcao(calls, call_strike)
        
        return [{
            'name': 'Compra de Call',
            'primary': True,
            'tipo_operacao': 'COMPRA',
            'legs': [{
                'action': 'Compra',
                'type': 'Call',
                'strike': call_strike,
                'premium': call_data.get('ask', 0),
                'oi': call_data.get('oi', 0),
                'volume': call_data.get('volume', 0)
            }],
            'logic': f'Short gamma = movimento explosivo para CIMA. Compra call, risco limitado ao premio pago.',
            'max_profit': 'Ilimitado',
            'max_loss': f"R$ {call_data.get('ask', 0):.2f}",
            'breakeven': call_strike + call_data.get('ask', 0)
        }]

    def _criar_compra_put(self, spot, strikes, puts):
        put_strike = self.encontrar_strike_mais_proximo(strikes, spot)
        
        if not put_strike:
            return []
        
        put_data = self._buscar_dados_opcao(puts, put_strike)
        
        return [{
            'name': 'Compra de Put',
            'primary': True,
            'tipo_operacao': 'COMPRA',
            'legs': [{
                'action': 'Compra',
                'type': 'Put',
                'strike': put_strike,
                'premium': put_data.get('ask', 0),
                'oi': put_data.get('oi', 0),
                'volume': put_data.get('volume', 0)
            }],
            'logic': f'Short gamma = queda explosiva. Compra put, risco limitado ao premio pago.',
            'max_profit': f"R$ {put_strike - put_data.get('ask', 0):.2f}",
            'max_loss': f"R$ {put_data.get('ask', 0):.2f}",
            'breakeven': put_strike - put_data.get('ask', 0)
        }]

    def _criar_venda_put(self, spot, strikes, puts):
        put_strike = self.encontrar_strike_mais_proximo(strikes, spot - 3)
        
        if not put_strike:
            return []
        
        put_data = self._buscar_dados_opcao(puts, put_strike)
        
        return [{
            'name': 'Venda de Put Garantida',
            'primary': True,
            'tipo_operacao': 'VENDA',
            'legs': [{
                'action': 'Vende',
                'type': 'Put',
                'strike': put_strike,
                'premium': put_data.get('bid', 0),
                'oi': put_data.get('oi', 0),
                'volume': put_data.get('volume', 0)
            }],
            'logic': f'Long gamma = mercado controlado. Vende put. Se exercido, compra ativo mais barato.',
            'max_profit': f"R$ {put_data.get('bid', 0):.2f}",
            'max_loss': f"R$ {put_strike - put_data.get('bid', 0):.2f}",
            'breakeven': put_strike - put_data.get('bid', 0)
        }]

    def _criar_venda_coberta(self, spot, strikes, calls):
        call_strike = self.encontrar_strike_mais_proximo(strikes, spot + 3)
        
        if not call_strike:
            return []
        
        call_data = self._buscar_dados_opcao(calls, call_strike)
        
        return [{
            'name': 'Venda Coberta de Call',
            'primary': False,
            'tipo_operacao': 'VENDA',
            'legs': [{
                'action': 'Vende',
                'type': 'Call',
                'strike': call_strike,
                'premium': call_data.get('bid', 0),
                'oi': call_data.get('oi', 0),
                'volume': call_data.get('volume', 0)
            }],
            'logic': f'Ja possui acao. Vende call, se subir, vende com lucro.',
            'max_profit': f"R$ {(call_strike - spot) + call_data.get('bid', 0):.2f}",
            'max_loss': 'Limitado a desvalorizacao da acao',
            'breakeven': spot - call_data.get('bid', 0)
        }]

    def _criar_collar_alta(self, spot, strikes, calls, puts):
        put_strike = self.encontrar_strike_mais_proximo(strikes, spot)
        call_strike = self.encontrar_strike_mais_proximo(strikes, spot + 4)
        
        if not put_strike or not call_strike:
            return []
        
        put_data = self._buscar_dados_opcao(puts, put_strike)
        call_data = self._buscar_dados_opcao(calls, call_strike)
        
        custo_liquido = put_data.get('ask', 0) - call_data.get('bid', 0)
        
        return [{
            'name': 'Collar de Alta',
            'primary': False,
            'tipo_operacao': 'PROTECAO',
            'legs': [
                {
                    'action': 'Compra',
                    'type': 'Put',
                    'strike': put_strike,
                    'premium': put_data.get('ask', 0),
                    'oi': put_data.get('oi', 0),
                    'volume': put_data.get('volume', 0)
                },
                {
                    'action': 'Vende',
                    'type': 'Call',
                    'strike': call_strike,
                    'premium': call_data.get('bid', 0),
                    'oi': call_data.get('oi', 0),
                    'volume': call_data.get('volume', 0)
                }
            ],
            'logic': f'Compra put (protecao) + Vende call (financia) + Compra Ativo, risco zero Desde que o PM seja menor que o menor strike.',
            'max_profit': f"R$ {call_strike - spot - custo_liquido:.2f}",
            'max_loss': f"R$ {custo_liquido:.2f}" if custo_liquido > 0 else 'Zero',
            'breakeven': f'{spot + custo_liquido:.2f}' if custo_liquido > 0 else spot
        }]

    def _criar_collar_baixa(self, spot, strikes, calls, puts):
        call_strike = self.encontrar_strike_mais_proximo(strikes, spot)
        put_strike = self.encontrar_strike_mais_proximo(strikes, spot - 4)
        
        if not call_strike or not put_strike:
            return []
        
        call_data = self._buscar_dados_opcao(calls, call_strike)
        put_data = self._buscar_dados_opcao(puts, put_strike)
        
        custo_liquido = call_data.get('ask', 0) - put_data.get('bid', 0)
        
        return [{
            'name': 'Collar de Baixa',
            'primary': True,
            'tipo_operacao': 'PROTECAO',
            'legs': [
                {
                    'action': 'Compra',
                    'type': 'Call',
                    'strike': call_strike,
                    'premium': call_data.get('ask', 0),
                    'oi': call_data.get('oi', 0),
                    'volume': call_data.get('volume', 0)
                },
                {
                    'action': 'Vende',
                    'type': 'Put',
                    'strike': put_strike,
                    'premium': put_data.get('bid', 0),
                    'oi': put_data.get('oi', 0),
                    'volume': put_data.get('volume', 0)
                }
            ],
            'logic': f'Compra call (protege de alta) abaixo do preço do ativo + Vende put R$ (financia) abaixo do preço do ativo + Compra ativo. risco zero Desde que o PM seja menor que o menor strike.',
            'max_profit': f"R$ {spot - put_strike - custo_liquido:.2f}",
            'max_loss': f"R$ {custo_liquido:.2f}" if custo_liquido > 0 else 'Zero',
            'breakeven': f'{spot - custo_liquido:.2f}' if custo_liquido > 0 else spot
        }]

    def _criar_compra_straddle(self, spot, strikes, calls, puts):
        strike_atm = self.encontrar_strike_mais_proximo(strikes, spot)
        
        if not strike_atm:
            return []
        
        call_data = self._buscar_dados_opcao(calls, strike_atm)
        put_data = self._buscar_dados_opcao(puts, strike_atm)
        
        custo_total = call_data.get('ask', 0) + put_data.get('ask', 0)
        
        return [{
            'name': 'Compra de Straddle',
            'primary': False,
            'tipo_operacao': 'VOLATILIDADE',
            'legs': [
                {
                    'action': 'Compra',
                    'type': 'Call',
                    'strike': strike_atm,
                    'premium': call_data.get('ask', 0),
                    'oi': call_data.get('oi', 0),
                    'volume': call_data.get('volume', 0)
                },
                {
                    'action': 'Compra',
                    'type': 'Put',
                    'strike': strike_atm,
                    'premium': put_data.get('ask', 0),
                    'oi': put_data.get('oi', 0),
                    'volume': put_data.get('volume', 0)
                }
            ],
            'logic': f'Compra call + put. Aposta em explosao (qualquer direcao). IV barata favorece compra.',
            'max_profit': 'Ilimitado',
            'max_loss': f"R$ {custo_total:.2f}",
            'breakeven': f'{strike_atm - custo_total:.2f} / {strike_atm + custo_total:.2f}'
        }]

    def _criar_venda_straddle(self, spot, strikes, calls, puts):
        strike_atm = self.encontrar_strike_mais_proximo(strikes, spot)
        
        if not strike_atm:
            return []
        
        call_data = self._buscar_dados_opcao(calls, strike_atm)
        put_data = self._buscar_dados_opcao(puts, strike_atm)
        
        credito_total = call_data.get('bid', 0) + put_data.get('bid', 0)
        
        return [{
            'name': 'Venda de Straddle',
            'primary': False,
            'tipo_operacao': 'VOLATILIDADE',
            'legs': [
                {
                    'action': 'Vende',
                    'type': 'Call',
                    'strike': strike_atm,
                    'premium': call_data.get('bid', 0),
                    'oi': call_data.get('oi', 0),
                    'volume': call_data.get('volume', 0)
                },
                {
                    'action': 'Vende',
                    'type': 'Put',
                    'strike': strike_atm,
                    'premium': put_data.get('bid', 0),
                    'oi': put_data.get('oi', 0),
                    'volume': put_data.get('volume', 0)
                }
            ],
            'logic': f'Vende call + put. Mercado parado, Ideal fazer 3% longe do preço do ativo. IV alta = premios gordos.',
            'max_profit': f"R$ {credito_total:.2f}",
            'max_loss': 'Ilimitado',
            'breakeven': f'{strike_atm - credito_total:.2f} / {strike_atm + credito_total:.2f}'
        }]

    def _buscar_dados_opcao(self, opcoes: List[Dict], strike: float) -> Dict:
        """
        Busca dados de uma opção específica pelo strike
        """
        for opcao in opcoes:
            if abs(opcao['strike'] - strike) < 0.01:
                return {
                    'bid': opcao.get('bid', 0),
                    'ask': opcao.get('ask', 0),
                    'last': opcao.get('last', 0),
                    'oi': opcao.get('open_interest', 0),
                    'volume': opcao.get('volume', 0)
                }
        
        return {'bid': 0, 'ask': 0, 'last': 0, 'oi': 0, 'volume': 0}
    
    def validar_estrutura(self, estrutura: Dict) -> bool:
        """
        Valida se a estrutura tem dados mínimos válidos
        """
        if not estrutura.get('legs'):
            return False
        
        for leg in estrutura['legs']:
            if leg.get('strike', 0) <= 0:
                return False
        
        return True
    
    def calcular_estruturas_automatico(
        self,
        ticker: str,
        cenario: Dict,
        expiration_code: Optional[str] = None
    ) -> Dict:
        """
         MÉTODO PRINCIPAL - Calcula estruturas com dados AUTOMÁTICOS do GEX
        
        Uso:
        ```python
        oplab = OplabService()
        resultado = oplab.calcular_estruturas_automatico(
            ticker='PETR4',
            cenario={'name': 'Squeeze Explosivo', 'direction': 'ALTA', 'number': 1}
        )
        ```
        
        Retorna estruturas calculadas com strikes REAIS baseados em:
        - GEX descoberto REAL (do gamma_service)
        - Flip strike REAL
        - Liquidez REAL das opções
        """
        print(f"\n{'='*60}")
        print(f"🚀 ESTRUTURAS AUTOMÁTICAS - {ticker}")
        print(f"{'='*60}")
        
        # 1. Buscar dados GEX REAIS
        dados_gex = self.buscar_dados_gex_reais(ticker, expiration_code)
        
        if not dados_gex:
            print(" Não foi possível buscar dados GEX - usando modo fallback")
            # Fallback: buscar apenas opções
            opcoes = self.buscar_opcoes_ativas(ticker)
            if not opcoes:
                return {
                    'success': False,
                    'error': 'Não foi possível buscar opções'
                }
            
            # Estimar spot price das opções
            strikes = [opt['strike'] for opt in opcoes]
            spot_price = sum(strikes) / len(strikes) if strikes else 0
            flip_strike = spot_price
            gex_descoberto = 0
        else:
            spot_price = dados_gex['spot_price']
            flip_strike = dados_gex['flip_strike'] or spot_price
            gex_descoberto = dados_gex['gex_descoberto']
        
        # 2. Buscar opções ativas
        opcoes = self.buscar_opcoes_ativas(ticker)
        
        if not opcoes:
            return {
                'success': False,
                'error': f'Nenhuma opção com liquidez encontrada para {ticker}'
            }
        
        # 3. Calcular estruturas
        estruturas = self.calcular_estruturas_inteligentes(
            ticker=ticker,
            spot_price=spot_price,
            flip_strike=flip_strike,
            gex_descoberto=gex_descoberto,
            cenario=cenario,
            opcoes=opcoes
        )
        
        # 4. Validar estruturas
        estruturas_validas = [
            est for est in estruturas
            if self.validar_estrutura(est)
        ]
        
        print(f"\n✅ {len(estruturas_validas)} estruturas calculadas")
        
        return {
            'success': True,
            'ticker': ticker,
            'dados_gex': dados_gex,
            'spot_price': spot_price,
            'flip_strike': flip_strike,
            'gex_descoberto': gex_descoberto,
            'cenario': cenario,
            'estruturas': estruturas_validas,
            'total_opcoes_analisadas': len(opcoes)
        }
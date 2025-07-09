import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import json
import warnings
import time
import math
import os
from datetime import datetime
import logging

warnings.filterwarnings('ignore')

class BoxTresPontasService:
    def __init__(self, config_path=None):
        self.cache_precos = {}  # Cache para preços de ativos
        self.ultimo_update_cache = {}  # Timestamp do último update
        self.taxa_cdi = 11.46  # Taxa CDI anual em % (atualize este valor conforme necessário)
        
        # Logger para debug
        self.logger = logging.getLogger(__name__)
        
        # Inicializar sessão e token (ordem importante!)
        self.session = self._criar_sessao_http()
        self.token_acesso = self._carregar_token(config_path)
        
    def _carregar_token(self, config_path=None):
        """
        Carrega token da OpLab usando o mesmo método do ArbitragemPutsService
        
        Args:
            config_path: Caminho específico para o arquivo de config
            
        Returns:
            Token de acesso ou string vazia se não encontrar
        """
        try:
            # Lista de caminhos para tentar
            caminhos_config = []
            
            if config_path:
                caminhos_config.append(config_path)
            
            # Caminho relativo ao script atual
            caminhos_config.extend([
                os.path.join(os.path.dirname(__file__), 'config.json'),
                os.path.join(os.path.dirname(__file__), '..', 'config.json'),
                os.path.expanduser('~/config.json'),
                r"C:\Users\usuario\Desktop\Vscode\Oplab\config.json"
            ])
            
            for caminho in caminhos_config:
                if os.path.exists(caminho):
                    self.logger.info(f"Carregando config de: {caminho}")
                    with open(caminho, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        
                    # Tentar diferentes chaves possíveis
                    for key in ['token', 'oplab_token', 'access_token']:
                        if key in config and config[key]:
                            self.logger.info("Token OpLab carregado com sucesso")
                            return config[key]
            
            self.logger.warning("Nenhum token OpLab encontrado")
            return ""
            
        except Exception as e:
            self.logger.error(f"Erro ao carregar token: {e}")
            return ""
        """Cria sessão HTTP com retry automático"""
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
    
    def obter_listas_predefinidas(self):
        """Retorna as listas predefinidas de ativos"""
        return {
            'principais': [
                "PETR4", "VALE3", "ITUB4", "BBDC4", "ABEV3", "MGLU3", "WEGE3", "SUZB3",
                "LREN3", "BBAS3", "JBSS3", "RENT3", "B3SA3", "ENGI11", "RADL3"
            ],
            'bancos': [
                "ITUB4", "BBDC4", "BBAS3", "SANB11", "BPAC11"
            ],
            'commodities': [
                "PETR4", "PETR3", "VALE3", "CSNA3", "USIM5", "GGBR4", "SUZB3"
            ],
            'consumo': [
                "ABEV3", "JBSS3", "BRFS3", "MGLU3", "LREN3", "PCAR3", "COGN3"
            ]
        }
    
    def calcular_dias_uteis(self, data_vencimento):
        """Calcula dias úteis entre hoje e a data de vencimento."""
        hoje = datetime.now().date()
        data_vencimento = pd.to_datetime(data_vencimento).date()
        
        # Cria range de datas
        dias = pd.date_range(start=hoje, end=data_vencimento)
        
        # Filtra para dias úteis (seg-sex)
        dias_uteis = dias[dias.weekday < 5]
        
        return len(dias_uteis)
    
    def obter_preco_ativo_yfinance(self, simbolo):
        """Obtém preço do ativo usando yfinance"""
        try:
            # Adiciona .SA para ações brasileiras
            symbol_yf = f"{simbolo}.SA"
            ticker = yf.Ticker(symbol_yf)
            
            # Pega dados dos últimos 2 dias
            hist = ticker.history(period="2d", interval="1d")
            
            if hist.empty:
                self.logger.warning(f"Nenhum dado encontrado para {simbolo}")
                return None
            
            # Pega o último preço disponível
            ultimo_preco = hist['Close'].iloc[-1]
            
            # Simula bid/ask com um spread pequeno (0.5%)
            spread = ultimo_preco * 0.005
            
            return {
                'bid': ultimo_preco - spread,
                'ask': ultimo_preco + spread,
                'last': ultimo_preco
            }
            
        except Exception as e:
            self.logger.error(f"Erro ao obter preço de {simbolo}: {str(e)}")
            return None
    
    def obter_dados_opcoes(self, simbolo):
        """Obtém dados de opções da API OpLab"""
        if not self.token_acesso:
            self.logger.warning(f"Token OpLab não configurado para {simbolo}")
            return None
            
        url = f"https://api.oplab.com.br/v3/market/options/{simbolo}"
        try:
            response = self.session.get(
                url, 
                headers={"Access-Token": self.token_acesso},
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Erro ao obter dados de opções para {simbolo}: {str(e)}")
            return None
    
    def calcular_tia(self, valor_resgate, custo_operacao, dias_uteis):
        """Calcula a Taxa Implícita Anualizada (TIA) da operação."""
        if dias_uteis <= 0 or custo_operacao <= 0 or valor_resgate <= 0:
            return 0
        
        # Fórmula: TIA = (Valor_Resgate / Custo_Operação) ^ (252 / dias_uteis) - 1
        try:
            tia = (valor_resgate / custo_operacao) ** (252 / dias_uteis) - 1
            return tia * 100  # Converte para percentual
        except Exception:
            return 0
    
    def analisar_box_tres_pontas(self, simbolo, volume_min=100, custo_operacional=0.003):
        """
        Analisa oportunidades de Box de 3 Pontas para um ativo específico
        
        Box de 3 Pontas = Compra do Ativo + Venda de Call + Compra de Put (mesmo strike e vencimento)
        Resultado: Renda fixa sintética que paga o valor do strike no vencimento
        """
        try:
            # Obter preço do ativo
            preco_ativo_info = self.obter_preco_ativo_yfinance(simbolo)
            if not preco_ativo_info:
                return None
                
            preco_compra_ativo = preco_ativo_info['ask']  # Usamos o ASK para simular a compra do ativo
            
            # Obter dados de opções
            dados_opcoes = self.obter_dados_opcoes(simbolo)
            if not dados_opcoes:
                return None
            
            # Separar CALLs e PUTs
            df_calls = pd.DataFrame([opt for opt in dados_opcoes if opt['category'] == 'CALL'])
            df_puts = pd.DataFrame([opt for opt in dados_opcoes if opt['category'] == 'PUT'])
            
            if df_calls.empty or df_puts.empty:
                return None
            
            # Filtrar opções com liquidez mínima e com cotações válidas
            df_calls = df_calls[(df_calls['volume'] >= volume_min) & 
                                (df_calls['bid'] > 0) & 
                                (df_calls['ask'] > 0)]
            
            df_puts = df_puts[(df_puts['volume'] >= volume_min) & 
                             (df_puts['bid'] > 0) & 
                             (df_puts['ask'] > 0)]
            
            if df_calls.empty or df_puts.empty:
                return None
            
            # Preparar lista para armazenar as oportunidades encontradas
            oportunidades = []
            
            # Iterar sobre os strikes e vencimentos comuns entre CALLs e PUTs
            strikes_comuns = set(df_calls['strike']).intersection(set(df_puts['strike']))
            
            for strike in strikes_comuns:
                # Filtrar opções pelo strike
                calls_strike = df_calls[df_calls['strike'] == strike]
                puts_strike = df_puts[df_puts['strike'] == strike]
                
                # Encontrar vencimentos comuns
                vencimentos_call = set(calls_strike['due_date'])
                vencimentos_put = set(puts_strike['due_date'])
                vencimentos_comuns = vencimentos_call.intersection(vencimentos_put)
                
                for vencimento in vencimentos_comuns:
                    call = calls_strike[calls_strike['due_date'] == vencimento].iloc[0]
                    put = puts_strike[puts_strike['due_date'] == vencimento].iloc[0]
                    
                    compra_ativo = preco_compra_ativo
                    venda_call = call['bid']  # Recebemos o BID ao vender
                    compra_put = put['ask']   # Pagamos o ASK ao comprar
                    
                    # Custo total da operação
                    custo_operacao = compra_ativo - venda_call + compra_put
                    
                    # Valor a ser recebido no vencimento (sempre igual ao strike)
                    valor_resgate = strike
                    
                    # Calcular lucro bruto e percentual
                    lucro_bruto = valor_resgate - custo_operacao
                    lucro_percentual = (lucro_bruto / custo_operacao) * 100 if custo_operacao > 0 else 0
                    
                    # Calcular custos operacionais
                    valor_custos = custo_operacao * custo_operacional
                    
                    # Lucro líquido considerando custos operacionais
                    lucro_liquido = lucro_bruto - valor_custos
                    lucro_percentual_liquido = (lucro_liquido / custo_operacao) * 100 if custo_operacao > 0 else 0
                    
                    # Calcular dias úteis até o vencimento
                    dias_uteis = self.calcular_dias_uteis(vencimento)
                    
                    # Calcular Taxa Implícita Anualizada (TIA)
                    tia = self.calcular_tia(valor_resgate, custo_operacao, dias_uteis)
                    
                    # Calcular TIA líquida (considerando custos operacionais)
                    tia_liquida = self.calcular_tia(valor_resgate - valor_custos, custo_operacao, dias_uteis)
                    
                    # Calcular spread em relação ao CDI
                    spread_cdi = tia_liquida - self.taxa_cdi
                    
                    # Salvar a oportunidade se a TIA for positiva
                    if tia_liquida > 0 and dias_uteis > 0 and custo_operacao > 0:
                        # Formatar data de vencimento
                        vencimento_formatado = pd.to_datetime(vencimento).strftime('%d/%m/%Y')
                        
                        oportunidades.append({
                            'simbolo': simbolo,
                            'preco_ativo': round(compra_ativo, 2),
                            'strike': round(strike, 2),
                            'vencimento': vencimento,
                            'vencimento_formatado': vencimento_formatado,
                            'call_symbol': call['symbol'],
                            'call_bid': round(venda_call, 2),
                            'put_symbol': put['symbol'],
                            'put_ask': round(compra_put, 2),
                            'custo_operacao': round(custo_operacao, 2),
                            'valor_resgate': round(valor_resgate, 2),
                            'lucro_bruto': round(lucro_bruto, 2),
                            'lucro_pct': round(lucro_percentual, 2),
                            'custos_operacionais': round(valor_custos, 4),
                            'lucro_liquido': round(lucro_liquido, 2),
                            'lucro_liquido_pct': round(lucro_percentual_liquido, 2),
                            'dias_uteis': dias_uteis,
                            'tia_bruta_pct': round(tia, 2),
                            'tia_liquida_pct': round(tia_liquida, 2),
                            'cdi_atual_pct': self.taxa_cdi,
                            'spread_cdi': round(spread_cdi, 2),
                            'volume_call': call['volume'],
                            'volume_put': put['volume'],
                            'vale_pena': spread_cdi >= 0.5  # Considera que vale a pena se o spread for >= 0.5%
                        })
            
            return oportunidades
            
        except Exception as e:
            self.logger.error(f"Erro ao analisar box 3 pontas para {simbolo}: {e}")
            return None
    
    def executar_screening_completo(self, 
                                  simbolos=None, 
                                  lista_predefinida=None,
                                  volume_min=100,
                                  custo_operacional=0.003,
                                  min_spread_cdi=0.5,
                                  tia_min=0.0):
        """
        Executa screening completo de Box de 3 Pontas
        """
        try:
            # Determinar lista de símbolos
            if lista_predefinida:
                listas = self.obter_listas_predefinidas()
                if lista_predefinida not in listas:
                    raise ValueError(f"Lista '{lista_predefinida}' não encontrada")
                simbolos = listas[lista_predefinida]
            elif not simbolos:
                simbolos = self.obter_listas_predefinidas()['principais']
            
            # Resultados
            resultados = {
                'parametros': {
                    'volume_min': volume_min,
                    'custo_operacional': custo_operacional,
                    'min_spread_cdi': min_spread_cdi,
                    'tia_min': tia_min,
                    'taxa_cdi': self.taxa_cdi
                },
                'resultados_por_ativo': {},
                'total_ativos_analisados': 0,
                'total_oportunidades': 0,
                'ranking_top10': [],
                'estatisticas': {
                    'ativos_com_oportunidades': 0,
                    'ativos_sem_oportunidades': 0,
                    'ativos_com_erro': 0
                }
            }
            
            todas_oportunidades = []
            
            for simbolo in simbolos:
                self.logger.info(f"Analisando {simbolo}...")
                
                try:
                    oportunidades = self.analisar_box_tres_pontas(
                        simbolo, 
                        volume_min, 
                        custo_operacional
                    )
                    
                    resultados['total_ativos_analisados'] += 1
                    
                    if oportunidades:
                        # Filtrar por critérios mínimos
                        oportunidades_filtradas = [
                            op for op in oportunidades 
                            if op['spread_cdi'] >= min_spread_cdi and op['tia_liquida_pct'] >= tia_min
                        ]
                        
                        if oportunidades_filtradas:
                            resultados['resultados_por_ativo'][simbolo] = {
                                'total_oportunidades': len(oportunidades_filtradas),
                                'oportunidades': oportunidades_filtradas
                            }
                            
                            todas_oportunidades.extend(oportunidades_filtradas)
                            resultados['total_oportunidades'] += len(oportunidades_filtradas)
                            resultados['estatisticas']['ativos_com_oportunidades'] += 1
                            
                            self.logger.info(f"{simbolo}: {len(oportunidades_filtradas)} oportunidades encontradas")
                        else:
                            resultados['estatisticas']['ativos_sem_oportunidades'] += 1
                            self.logger.info(f"{simbolo}: Sem oportunidades que atendam aos critérios")
                    else:
                        resultados['estatisticas']['ativos_sem_oportunidades'] += 1
                        self.logger.info(f"{simbolo}: Nenhuma oportunidade encontrada")
                        
                except Exception as e:
                    resultados['estatisticas']['ativos_com_erro'] += 1
                    self.logger.error(f"Erro ao analisar {simbolo}: {str(e)}")
                
                # Pequena pausa para não sobrecarregar as APIs
                time.sleep(0.5)
            
            # Criar ranking das 10 melhores oportunidades
            if todas_oportunidades:
                todas_oportunidades.sort(key=lambda x: x.get('spread_cdi', 0), reverse=True)
                resultados['ranking_top10'] = todas_oportunidades[:10]
            
            return resultados
            
        except Exception as e:
            self.logger.error(f"Erro no screening completo: {str(e)}")
            raise e
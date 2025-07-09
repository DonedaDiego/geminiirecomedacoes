import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
from datetime import datetime, timedelta
import json
import warnings
import time
import yfinance as yf
from typing import Dict, List, Optional, Tuple, Union
import os
import logging
from pathlib import Path

warnings.filterwarnings('ignore')

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def calcular_rendimento_liquido_cdi(taxa_cdi_mensal: float, meses: float) -> Tuple[float, float]:

    dias = meses * 30  # Aproximação de 30 dias por mês
    
    # Determinar alíquota de IR
    if dias <= 180:
        aliquota_ir = 0.225
    elif dias <= 360:
        aliquota_ir = 0.20
    elif dias <= 720:
        aliquota_ir = 0.175
    else:
        aliquota_ir = 0.15
    
    # Rendimento bruto acumulado
    rendimento_bruto = ((1 + taxa_cdi_mensal/100) ** meses - 1) * 100
    
    # Rendimento líquido após IR
    rendimento_liquido = rendimento_bruto * (1 - aliquota_ir)
    
    return rendimento_liquido, aliquota_ir * 100

class ScreeningService:
    """
    Serviço para screening de opções com diferentes estratégias
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Inicializa o serviço de screening
        
        Args:
            config_path: Caminho opcional para arquivo de configuração
        """
        self.session = self._criar_sessao_http()
        self.token_acesso = self._carregar_token(config_path)
        self.cache_precos = {}  # Cache para preços de ativos
        self.ultimo_update_cache = {}  # Timestamp do último update
        
    def _criar_sessao_http(self) -> requests.Session:
        """Cria sessão HTTP com retry strategy otimizada"""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]  # Métodos permitidos para retry
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        # Headers padrão
        session.headers.update({
            'User-Agent': 'ScreeningService/1.0',
            'Accept': 'application/json',
            'Connection': 'keep-alive'
        })
        
        return session
    
    def _carregar_token(self, config_path: Optional[str] = None) -> str:
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
                    logger.info(f"Carregando config de: {caminho}")
                    with open(caminho, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        
                    # Tentar diferentes chaves possíveis
                    for key in ['token', 'oplab_token', 'access_token']:
                        if key in config and config[key]:
                            logger.info("Token OpLab carregado com sucesso")
                            return config[key]
            
            logger.warning("Nenhum token OpLab encontrado")
            return ""
            
        except Exception as e:
            logger.error(f"Erro ao carregar token: {e}")
            return ""
    
    def _obter_preco_ativo_yfinance(self, simbolo: str, usar_cache: bool = True) -> Optional[float]:
        try:
            # Verificar cache (válido por 5 minutos)
            if usar_cache and simbolo in self.cache_precos:
                ultimo_update = self.ultimo_update_cache.get(simbolo, 0)
                if time.time() - ultimo_update < 300:  # 5 minutos
                    return self.cache_precos[simbolo]
            
            # Converter para formato Yahoo Finance
            ticker_yahoo = f"{simbolo}.SA"
            ticker = yf.Ticker(ticker_yahoo)
            
            # Tentar diferentes períodos e métodos
            preco = None
            
            # Método 1: Histórico recente
            for period in ["1d", "5d"]:
                try:
                    hist = ticker.history(period=period, interval="1m")
                    if not hist.empty:
                        preco = float(hist['Close'].iloc[-1])
                        break
                except:
                    continue
            
            # Método 2: Info básica se histórico falhar
            if preco is None:
                try:
                    info = ticker.info
                    for price_key in ['currentPrice', 'regularMarketPrice', 'previousClose']:
                        if price_key in info and info[price_key]:
                            preco = float(info[price_key])
                            break
                except:
                    pass
            
            # Atualizar cache se encontrou preço
            if preco is not None:
                self.cache_precos[simbolo] = preco
                self.ultimo_update_cache[simbolo] = time.time()
                return preco
                
            return None
            
        except Exception as e:
            # Log apenas para erros não esperados
            if "possibly delisted" not in str(e).lower():
                logger.warning(f"Erro ao obter preço de {simbolo}: {e}")
            return None
    
    def _obter_dados_opcoes(self, simbolo: str) -> Optional[List[Dict]]:
        if not self.token_acesso:
            logger.warning(f"Token OpLab não configurado para {simbolo}")
            return None
            
        url = f"https://api.oplab.com.br/v3/market/options/{simbolo}"
        
        try:
            response = self.session.get(
                url, 
                headers={"Access-Token": self.token_acesso},
                timeout=15  # Aumentado timeout
            )
            response.raise_for_status()
            
            dados = response.json()
            
            # Validar estrutura da resposta
            if not isinstance(dados, list):
                logger.warning(f"Resposta inesperada da API para {simbolo}")
                return None
                
            return dados
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao obter dados de opções para {simbolo}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar JSON para {simbolo}: {e}")
            return None
    
    def _calcular_meses_ate_vencimento(self, data_vencimento: Union[str, datetime]) -> float:
        try:
            if isinstance(data_vencimento, str):
                # Tentar diferentes formatos de data
                formatos = ['%Y-%m-%d', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S']
                data_venc = None
                
                for formato in formatos:
                    try:
                        data_venc = datetime.strptime(data_vencimento, formato)
                        break
                    except ValueError:
                        continue
                
                if data_venc is None:
                    logger.warning(f"Formato de data não reconhecido: {data_vencimento}")
                    return 0.1
            else:
                data_venc = data_vencimento
            
            hoje = datetime.now()
            diferenca = data_venc - hoje
            meses = diferenca.days / 30.44  # Média de dias por mês
            
            return max(meses, 0.1)  # Mínimo de 0.1 mês
            
        except Exception as e:
            logger.warning(f"Erro ao calcular meses até vencimento: {e}")
            return 0.1
    
    def _aplicar_filtros_avancados(self, df_puts: pd.DataFrame, preco_ativo: float, filtros: Dict) -> pd.DataFrame:
        df_filtrado = df_puts.copy()
        
        try:
            # Filtro de Delta
            if 'delta_min' in filtros and 'delta_max' in filtros and 'delta' in df_filtrado.columns:
                df_filtrado = df_filtrado[
                    (df_filtrado['delta'].abs() >= filtros['delta_min']) &
                    (df_filtrado['delta'].abs() <= filtros['delta_max'])
                ]
                logger.info(f"Filtro delta aplicado: {len(df_filtrado)} opções restantes")
            
            # Filtro de distância do ATM
            if 'atm_min' in filtros and 'atm_max' in filtros:
                distancia_atm = abs(df_filtrado['strike'] - preco_ativo) / preco_ativo * 100
                df_filtrado = df_filtrado[
                    (distancia_atm >= filtros['atm_min']) &
                    (distancia_atm <= filtros['atm_max'])
                ]
                logger.info(f"Filtro ATM aplicado: {len(df_filtrado)} opções restantes")
            
            # Filtro de dias até vencimento
            if 'dias_vencimento_min' in filtros or 'dias_vencimento_max' in filtros:
                df_filtrado['due_date'] = pd.to_datetime(df_filtrado['due_date'])
                hoje = datetime.now()
                df_filtrado['dias_vencimento'] = (df_filtrado['due_date'] - hoje).dt.days
                
                if 'dias_vencimento_min' in filtros:
                    df_filtrado = df_filtrado[df_filtrado['dias_vencimento'] >= filtros['dias_vencimento_min']]
                
                if 'dias_vencimento_max' in filtros:
                    df_filtrado = df_filtrado[df_filtrado['dias_vencimento'] <= filtros['dias_vencimento_max']]
                
                logger.info(f"Filtro dias vencimento aplicado: {len(df_filtrado)} opções restantes")
            
            # Filtro de vencimentos específicos (implementação futura)
            if 'vencimentos' in filtros and filtros['vencimentos']:
                # TODO: Implementar mapeamento de vencimentos (1º, 2º, etc.) para datas reais
                pass
            
            return df_filtrado
            
        except Exception as e:
            logger.error(f"Erro ao aplicar filtros avançados: {e}")
            return df_puts  # Retorna dados originais em caso de erro
    
    def screening_arbitragem_puts(self, 
                                  simbolos: List[str] = None,
                                  lista_predefinida: str = None,
                                  taxa_cdi_mensal: float = 1.0,
                                  volume_min: int = 100,
                                  rentabilidade_min: float = 1.2,
                                  filtros: Dict = None) -> Dict:

        start_time = time.time()
        
        try:
            # Determinar lista de símbolos
            if simbolos:
                lista_ativos = simbolos
            elif lista_predefinida:
                listas = self.get_listas_predefinidas()
                if lista_predefinida not in listas:
                    return {
                        'success': False,
                        'error': f'Lista predefinida não encontrada: {lista_predefinida}',
                        'timestamp': datetime.now().isoformat()
                    }
                lista_ativos = listas[lista_predefinida]
            else:
                return {
                    'success': False,
                    'error': 'Deve especificar símbolos ou lista_predefinida',
                    'timestamp': datetime.now().isoformat()
                }
            
            todas_oportunidades = []
            resultados_por_ativo = {}
            ativos_processados = 0
            ativos_com_erro = 0
            
            logger.info(f"🔍 Iniciando screening de {len(lista_ativos)} ativos...")
            
            # Log dos filtros aplicados
            if filtros:
                logger.info("📋 Filtros aplicados:")
                for key, value in filtros.items():
                    if key == 'vencimentos' and value:
                        logger.info(f"   • {key}: {len(value)} vencimentos selecionados")
                    else:
                        logger.info(f"   • {key}: {value}")
            
            for i, simbolo in enumerate(lista_ativos, 1):
                logger.info(f"[{i}/{len(lista_ativos)}] Analisando {simbolo}...")
                
                try:
                    # Obter preço do ativo
                    preco_ativo = self._obter_preco_ativo_yfinance(simbolo)
                    if not preco_ativo:
                        logger.warning(f"❌ {simbolo}: Preço não encontrado")
                        ativos_com_erro += 1
                        continue
                    
                    # Obter dados de opções
                    dados_opcoes = self._obter_dados_opcoes(simbolo)
                    if not dados_opcoes:
                        logger.warning(f"❌ {simbolo}: Dados de opções não encontrados")
                        ativos_com_erro += 1
                        continue
                    
                    # Processar puts
                    resultado = self._analisar_puts(
                        simbolo, 
                        preco_ativo, 
                        dados_opcoes, 
                        taxa_cdi_mensal,
                        volume_min,
                        rentabilidade_min,
                        filtros
                    )
                    
                    ativos_processados += 1
                    
                    if resultado is not None and not resultado.empty:
                        oportunidades = resultado.to_dict('records')
                        
                        resultados_por_ativo[simbolo] = {
                            'preco_atual': preco_ativo,
                            'oportunidades': oportunidades
                        }
                        todas_oportunidades.extend(oportunidades)
                        logger.info(f"✅ {simbolo}: {len(resultado)} oportunidades encontradas")
                    else:
                        logger.info(f"⚪ {simbolo}: Sem oportunidades")
                    
                except Exception as e:
                    ativos_com_erro += 1
                    logger.error(f"❌ {simbolo}: Erro - {str(e)}")
                    continue
                
                # Delay para não sobrecarregar APIs
                time.sleep(0.3)
            
            # Criar ranking das melhores oportunidades
            ranking = []
            if todas_oportunidades:
                df_ranking = pd.DataFrame(todas_oportunidades)
                df_ranking = df_ranking.sort_values('lucro_pct_bruto', ascending=False)
                ranking = df_ranking.head(10).to_dict('records')
            
            tempo_execucao = time.time() - start_time
            
            logger.info(f"\n📊 Resumo do Screening:")
            logger.info(f"   • Tempo de execução: {tempo_execucao:.1f}s")
            logger.info(f"   • Ativos processados: {ativos_processados}")
            logger.info(f"   • Ativos com erro: {ativos_com_erro}")
            logger.info(f"   • Total de oportunidades: {len(todas_oportunidades)}")
            logger.info(f"   • Ativos com oportunidades: {len(resultados_por_ativo)}")
            
            return {
                'success': True,
                'total_ativos_analisados': len(lista_ativos),
                'ativos_processados': ativos_processados,
                'ativos_com_erro': ativos_com_erro,
                'total_oportunidades': len(todas_oportunidades),
                'resultados_por_ativo': resultados_por_ativo,
                'ranking_top10': ranking,
                'parametros': {
                    'taxa_cdi_mensal': taxa_cdi_mensal,
                    'volume_min': volume_min,
                    'rentabilidade_min': rentabilidade_min,
                    'filtros': filtros,
                    'tempo_execucao': tempo_execucao,
                    'timestamp': datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Erro geral no screening: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _analisar_puts(self, 
                       simbolo: str, 
                       preco_ativo: float, 
                       dados_opcoes: List[Dict],
                       taxa_cdi_mensal: float,
                       volume_min: int,
                       rentabilidade_min: float,
                       filtros: Dict = None) -> Optional[pd.DataFrame]:

        try:
            # Filtrar apenas as PUTs
            puts_data = [opt for opt in dados_opcoes if opt.get('category') == 'PUT']
            if not puts_data:
                return None
                
            df_puts = pd.DataFrame(puts_data)
            
            # Validar colunas essenciais
            colunas_obrigatorias = ['strike', 'bid', 'ask', 'close', 'volume', 'due_date']
            for col in colunas_obrigatorias:
                if col not in df_puts.columns:
                    logger.warning(f"Coluna obrigatória '{col}' não encontrada para {simbolo}")
                    return None
            
            # Limpar dados inválidos
            df_puts = df_puts.dropna(subset=colunas_obrigatorias)
            if df_puts.empty:
                return None
            
            # Cálculos de valor intrínseco e extrínseco
            df_puts['valor_intrinseco'] = (df_puts['strike'] - preco_ativo).clip(lower=0)
            df_puts['extrinseco_ask'] = df_puts['ask'] - df_puts['valor_intrinseco']
            df_puts['extrinseco_close'] = df_puts['close'] - df_puts['valor_intrinseco']
            
            # Aplicar filtros avançados
            if filtros:
                df_puts = self._aplicar_filtros_avancados(df_puts, preco_ativo, filtros)
            
            # Filtros básicos de arbitragem
            df_resultado = df_puts[
                (df_puts['bid'] > 0) &
                (df_puts['ask'] > 0) &
                (df_puts['volume'] >= volume_min) &
                ((df_puts['extrinseco_ask'] < 0) | (df_puts['extrinseco_close'] < 0)) &
                (df_puts['strike'] > preco_ativo)
            ].copy()
            
            if df_resultado.empty:
                return None
            
            # Cálculos financeiros
            df_resultado['spread'] = df_resultado['ask'] - df_resultado['bid']
            df_resultado['custo_op_ask'] = preco_ativo + df_resultado['ask']
            df_resultado['valor_recebido'] = df_resultado['strike']
            
            # Lucros
            df_resultado['lucro_ask'] = df_resultado['valor_recebido'] - df_resultado['custo_op_ask']
            df_resultado['lucro_pct_ask'] = (df_resultado['lucro_ask'] / df_resultado['custo_op_ask']) * 100
            
            # Lucro líquido após IR (15% para renda variável)
            df_resultado['lucro_liquido_ask'] = df_resultado['lucro_ask'] * 0.85
            df_resultado['lucro_pct_liquido_ask'] = (df_resultado['lucro_liquido_ask'] / df_resultado['custo_op_ask']) * 100
            
            # Cálculos temporais
            df_resultado['due_date'] = pd.to_datetime(df_resultado['due_date'])
            df_resultado['meses_vencimento'] = df_resultado['due_date'].apply(self._calcular_meses_ate_vencimento)
            
            # Rentabilidade mensal
            df_resultado['lucro_mensal_liquido'] = df_resultado['lucro_pct_liquido_ask'] / df_resultado['meses_vencimento']
            
            # Comparação com CDI
            df_resultado['cdi_liquido_periodo'] = df_resultado['meses_vencimento'].apply(
                lambda x: calcular_rendimento_liquido_cdi(taxa_cdi_mensal, x)[0]
            )
            df_resultado['cdi_mensal_liquido'] = df_resultado['meses_vencimento'].apply(
                lambda x: calcular_rendimento_liquido_cdi(taxa_cdi_mensal, x)[0] / max(x, 0.1)
            )
            
            # Vantagens vs CDI
            df_resultado['vantagem_vs_cdi'] = df_resultado['lucro_pct_liquido_ask'] - df_resultado['cdi_liquido_periodo']
            df_resultado['vantagem_mensal_vs_cdi'] = df_resultado['lucro_mensal_liquido'] - df_resultado['cdi_mensal_liquido']
            df_resultado['vale_pena'] = df_resultado['vantagem_mensal_vs_cdi'] > 0
            
            # Filtro final de rentabilidade
            lucro_min_final = rentabilidade_min
            if filtros and 'lucro_min' in filtros and filtros['lucro_min'] > 0:
                lucro_min_final = max(rentabilidade_min, filtros['lucro_min'])
            
            df_resultado = df_resultado[df_resultado['lucro_pct_ask'] >= lucro_min_final]
            
            if df_resultado.empty:
                return None
            
            # Preparar dados para retorno
            df_resultado['due_date_formatted'] = df_resultado['due_date'].dt.strftime('%d/%m/%Y')
            df_resultado['simbolo'] = simbolo
            df_resultado['preco_ativo'] = preco_ativo
            
            # Renomear colunas para compatibilidade
            df_resultado = df_resultado.rename(columns={
                'lucro_pct_ask': 'lucro_pct_bruto',
                'lucro_pct_liquido_ask': 'lucro_pct_liquido',
                'lucro_ask': 'lucro_bruto',
                'lucro_liquido_ask': 'lucro_liquido'
            })
            
            # Ordenar por performance
            df_resultado = df_resultado.sort_values(['lucro_pct_bruto', 'volume'], ascending=[False, False])
            
            return df_resultado.round(4)
            
        except Exception as e:
            logger.error(f"Erro ao analisar puts de {simbolo}: {e}")
            return None
    
    def get_listas_predefinidas(self) -> Dict[str, List[str]]:
        """Retorna listas predefinidas de ativos"""
        return {
            'ibov': [
                "ABEV3", "ALOS3", "ASAI3", "AURE3", "AZUL4", "AZZA3", "BBAS3", "BBDC3", "BBDC4", "BBSE3", 
                "BEEF3", "BPAC11", "BRAP4", "BRAV3", "BRFS3", "BRKM5", "B3SA3", "CMIG4", "CMIN3", "COGN3",
                "CPFE3", "CPLE6", "CSAN3", "CSNA3", "CXSE3", "CYRE3", "DIRR3", "EGIE3", "ELET3", "ELET6", 
                "EMBR3", "ENEV3", "ENGI11", "EQTL3", "FLRY3", "GGBR4", "GOAU4", "HAPV3", "HYPE3", "IGTI11", 
                "IRBR3", "ISAE4", "ITSA4", "ITUB4", "KLBN11", "LREN3", "MGLU3", "MOTV3", "MRFG3", "MRVE3",
                "MULT3", "NATU3", "PCAR3", "PETR3", "PETR4", "PETZ3", "POMO4", "PRIO3", "PSSA3", "RAIL3",
                "RAIZ4", "RADL3", "RECV3", "RENT3", "SBSP3", "SLCE3", "SANB11", "SMFT3", "SMTO3", "STBP3", 
                "SUZB3", "TAEE11", "TIMS3", "TOTS3", "UGPA3", "USIM5", "VALE3", "VAMO3", "VBBR3", "VIVA3", 
                "VIVT3", "WEGE3", "YDUQ3"

            ],           
            
        }
    
    def get_tipos_screening(self) -> Dict[str, Dict]:
        """Retorna tipos de screening disponíveis"""
        return {
            'arbitragem_puts': {
                'nome': 'Arbitragem de Puts',
                'descricao': 'Busca oportunidades de arbitragem em puts com valor extrínseco negativo',
                'parametros': ['taxa_cdi_mensal', 'volume_min', 'rentabilidade_min'],
                'status': 'ativo'
            },
            'straddle': {
                'nome': 'Straddle',
                'descricao': 'Análise de estratégias straddle (call + put mesmo strike)',
                'parametros': ['volatilidade_min', 'dias_vencimento'],
                'status': 'em_desenvolvimento'
            },
            'strangle': {
                'nome': 'Strangle',
                'descricao': 'Análise de estratégias strangle (call + put strikes diferentes)',
                'parametros': ['volatilidade_min', 'delta_range'],
                'status': 'em_desenvolvimento'
            },
            'collar': {
                'nome': 'Collar',
                'descricao': 'Análise de estratégias collar (proteção com put + venda de call)',
                'parametros': ['nivel_protecao', 'premio_liquido'],
                'status': 'em_desenvolvimento'
            }
        }
    
    def limpar_cache(self):
        """Limpa o cache de preços"""
        self.cache_precos.clear()
        self.ultimo_update_cache.clear()
        logger.info("Cache de preços limpo")
    
    def estatisticas_cache(self) -> Dict:
        """Retorna estatísticas do cache"""
        return {
            'total_ativos_cache': len(self.cache_precos),
            'ativos_cached': list(self.cache_precos.keys()),
            'cache_hits': sum(1 for t in self.ultimo_update_cache.values() if time.time() - t < 300)
        }

# Função auxiliar para uso standalone
def executar_screening_arbitragem_puts(
    simbolos: List[str] = None,
    lista_predefinida: str = None,
    taxa_cdi_mensal: float = 1.0,
    volume_min: int = 100,
    rentabilidade_min: float = 1.2,
    filtros: Dict = None,
    config_path: str = None
) -> Dict:
    """
    Função conveniente para executar screening de arbitragem de puts
    
    Args:
        simbolos: Lista de símbolos para análise
        lista_predefinida: Nome da lista predefinida ('ibov', 'bancarios', etc.)
        taxa_cdi_mensal: Taxa CDI mensal em %
        volume_min: Volume mínimo
        rentabilidade_min: Rentabilidade mínima em %
        filtros: Filtros adicionais
        config_path: Caminho para arquivo de configuração
    
    Returns:
        Dict com resultados do screening
    
    Exemplo:
        >>> resultado = executar_screening_arbitragem_puts(
        ...     lista_predefinida='bancarios',
        ...     taxa_cdi_mensal=1.1,
        ...     volume_min=50
        ... )
        >>> print(f"Encontradas {resultado['total_oportunidades']} oportunidades")
    """
    service = ScreeningService(config_path=config_path)
    
    return service.screening_arbitragem_puts(
        simbolos=simbolos,
        lista_predefinida=lista_predefinida,
        taxa_cdi_mensal=taxa_cdi_mensal,
        volume_min=volume_min,
        rentabilidade_min=rentabilidade_min,
        filtros=filtros
    )

# Exemplo de uso
if __name__ == "__main__":
    # Teste com lista real
    resultado = executar_screening_arbitragem_puts(
        lista_predefinida='blue_chips',
        taxa_cdi_mensal=1.0,
        volume_min=10,
        rentabilidade_min=0.5
    )
    
    if resultado['success']:
        print(f"✅ Screening concluído!")
        print(f"📊 {resultado['total_oportunidades']} oportunidades encontradas")
        print(f"⏱️ Tempo: {resultado['parametros']['tempo_execucao']:.1f}s")
        
        if resultado['ranking_top10']:
            print(f"\n🏆 Melhor oportunidade:")
            melhor = resultado['ranking_top10'][0]
            print(f"   {melhor['simbolo']} - {melhor['symbol']}")
            print(f"   Lucro: {melhor['lucro_pct_bruto']:.2f}%")
    else:
        print(f"❌ Erro: {resultado['error']}")
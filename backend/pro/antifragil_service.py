# antifragil_service.py - Versão SIMPLIFICADA (sem VI para teste)

import psycopg2
import pandas as pd
import numpy as np
import yfinance as yf
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# 🔥 LISTA DOS 20 PRINCIPAIS ATIVOS
TOP_20_STOCKS = [
    'PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3',
    'WEGE3', 'MGLU3', 'RENT3', 'LREN3', 'JBSS3',
    'HAPV3', 'RAIL3', 'PRIO3', 'SUZB3', 'TOTS3',
    'LWSA3', 'RDOR3', 'CSAN3', 'KLBN3', 'EMBR3'
]

class AntifragilService:
    """Serviço para calcular o Indicador Antifrágil - VERSÃO SIMPLIFICADA"""
    
    def __init__(self):
        self.conn_params = self._get_db_connection()
        self.stress_threshold = 2.0  # Threshold para dias de stress (5% de aumento na IV do mercado)
        
    def _get_db_connection(self) -> dict:
        """Obtém parâmetros de conexão do banco de dados"""
        flask_env = os.getenv('FLASK_ENV', 'production')
        
        if flask_env == 'development':
            return {
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': int(os.getenv('DB_PORT', 5432)),
                'dbname': os.getenv('DB_NAME', 'postgres'),
                'user': os.getenv('DB_USER', 'postgres'),
                'password': os.getenv('DB_PASSWORD', '#geminii')
            }
        else:
            return {
                'host': os.getenv('DB_HOST', 'ballast.proxy.rlwy.net'),
                'port': int(os.getenv('DB_PORT', 33654)),
                'dbname': os.getenv('DB_NAME', 'railway'),
                'user': os.getenv('DB_USER', 'postgres'),
                'password': os.getenv('DB_PASSWORD', 'SWYYPTWLukrNVucLgnyImUfTftHSadyS')
            }
    
    def _conectar_banco(self):
        """Conecta ao banco de dados"""
        try:
            return psycopg2.connect(**self.conn_params)
        except Exception as e:
            logger.error(f"Erro na conexão com banco: {e}")
            raise
    
    def obter_ativos_disponiveis(self) -> List[str]:
        """Obtém lista dos 20 principais ativos para análise antifrágil"""
        try:
            logger.info(f"Usando lista dos {len(TOP_20_STOCKS)} principais ativos para análise antifrágil")
            return TOP_20_STOCKS.copy()
            
        except Exception as e:
            logger.error(f"Erro ao obter lista de ativos: {e}")
            return TOP_20_STOCKS.copy()
    
    def obter_dados_mercado_ibov(self, periodo_dias: int = 252) -> pd.DataFrame:
        """Obtém dados do IBOVESPA como proxy do mercado - VERSÃO SIMPLIFICADA"""
        try:
            to_date = datetime.now()
            from_date = to_date - timedelta(days=periodo_dias + 50)
            
            logger.info(f"Obtendo dados do IBOV para período de {periodo_dias} dias")
            
            # Usar apenas ^BVSP para simplicidade
            ibov = yf.Ticker("^BVSP")
            hist = ibov.history(start=from_date, end=to_date)
            
            if hist.empty:
                logger.error("Não foi possível obter dados do IBOV")
                return pd.DataFrame()
            
            # Calcular retornos
            hist['retorno_mercado'] = hist['Close'].pct_change()
            
            # 🔥 VOLATILIDADE HISTÓRICA SIMPLES (sem tentar VI real)
            returns = hist['retorno_mercado'].dropna()
            if len(returns) > 21:
                rolling_vol = returns.rolling(window=21).std() * np.sqrt(252) * 100
                hist['iv_mercado'] = rolling_vol
                hist['delta_iv_mercado'] = hist['iv_mercado'].diff()
            else:
                logger.warning("Dados insuficientes para calcular volatilidade")
                return pd.DataFrame()
            
            # Limpar dados
            hist = hist.dropna(subset=['retorno_mercado', 'iv_mercado', 'delta_iv_mercado'])
            
            logger.info(f"Dados do IBOV obtidos: {len(hist)} registros")
            return hist
                
        except Exception as e:
            logger.error(f"Erro ao obter dados do mercado: {e}")
            return pd.DataFrame()
    
    def obter_dados_ativo(self, ticker: str, periodo_dias: int = 252) -> pd.DataFrame:
        """Obtém dados históricos de um ativo específico - VERSÃO SIMPLIFICADA"""
        try:
            to_date = datetime.now()
            from_date = to_date - timedelta(days=periodo_dias + 50)
            
            logger.info(f"Obtendo dados do ativo {ticker}")
            
            # Obter preços via yfinance
            ticker_yf = f"{ticker}.SA" if not ticker.endswith('.SA') else ticker
            stock = yf.Ticker(ticker_yf)
            hist = stock.history(start=from_date, end=to_date)
            
            if hist.empty:
                logger.warning(f"Nenhum dado encontrado para {ticker}")
                return pd.DataFrame()
            
            # Calcular retornos
            hist['retorno_ativo'] = hist['Close'].pct_change()
            hist['preco_ativo'] = hist['Close']
            
            # 🔥 SEM VI REAL - USAR APENAS DADOS DE PREÇO
            hist['iv_ativo'] = None  # Não usar VI por enquanto
            
            logger.info(f"Dados do ativo {ticker} obtidos: {len(hist)} registros")
            return hist
            
        except Exception as e:
            logger.error(f"Erro ao obter dados do ativo {ticker}: {e}")
            return pd.DataFrame()
    
    def calcular_dias_stress(self, dados_mercado: pd.DataFrame) -> pd.DataFrame:
        """Identifica dias de stress baseado na variação da IV do mercado"""
        try:
            if dados_mercado is None or dados_mercado.empty:
                logger.warning("dados_mercado está vazio")
                return pd.DataFrame()
            
            if 'delta_iv_mercado' not in dados_mercado.columns:
                logger.warning("Coluna delta_iv_mercado não encontrada")
                return dados_mercado
            
            # 🔥 USAR PERCENTIL PARA IDENTIFICAR DIAS DE ALTA VOLATILIDADE
            delta_iv_values = dados_mercado['delta_iv_mercado'].dropna()
            if len(delta_iv_values) > 10:
                # Usar percentil 90 como threshold dinâmico
                threshold_dinamico = delta_iv_values.quantile(0.85)  # Top 15% dos dias
                logger.info(f"Threshold dinâmico calculado: {threshold_dinamico:.2f}%")
                
                # Usar o maior entre threshold fixo e dinâmico
                threshold_final = max(self.stress_threshold, threshold_dinamico)
            else:
                threshold_final = self.stress_threshold
            
            # Marcar dias de stress
            dados_mercado['stress_day'] = (dados_mercado['delta_iv_mercado'] > threshold_final).astype(int)
            dados_mercado['stress_day'] = dados_mercado['stress_day'].fillna(0)
            
            stress_days = dados_mercado['stress_day'].sum()
            total_days = len(dados_mercado.dropna(subset=['delta_iv_mercado']))
            
            logger.info(f"✅ Dias de stress identificados: {stress_days} de {total_days} ({stress_days/total_days*100:.1f}%) - Threshold: {threshold_final:.2f}%")
            
            return dados_mercado
            
        except Exception as e:
            logger.error(f"Erro ao calcular dias de stress: {e}")
            if dados_mercado is not None and not dados_mercado.empty:
                dados_mercado['stress_day'] = 0
            return dados_mercado
    
    def calcular_afiv_score(self, dados_ativo: pd.DataFrame, dados_mercado: pd.DataFrame) -> Dict:
        """Calcula o AFIV Score para um ativo"""
        try:
            if dados_ativo.empty or dados_mercado.empty:
                return {
                    'afiv_score': 0.0,
                    'retorno_stress_medio': 0.0,
                    'dias_stress': 0,
                    'total_dias': 0,
                    'volatilidade_stress': 0.0,
                    'classificacao': 'DADOS_INSUFICIENTES',
                    'percentual_stress': 0.0  # 🔥 ADICIONAR ESTE CAMPO
                }
            
            # Alinhar datas
            dados_combinados = dados_ativo.merge(
                dados_mercado[['stress_day', 'delta_iv_mercado']], 
                left_index=True, 
                right_index=True, 
                how='inner'
            )
            
            if dados_combinados.empty:
                logger.warning("Nenhuma data comum entre ativo e mercado")
                return {
                    'afiv_score': 0.0,
                    'retorno_stress_medio': 0.0,
                    'dias_stress': 0,
                    'total_dias': 0,
                    'volatilidade_stress': 0.0,
                    'classificacao': 'DADOS_INSUFICIENTES',
                    'percentual_stress': 0.0
                }
            
            # Filtrar dias de stress
            dias_stress = dados_combinados[dados_combinados['stress_day'] == 1]
            total_dias = len(dados_combinados)
            
            if dias_stress.empty:
                logger.warning("Nenhum dia de stress encontrado")
                return {
                    'afiv_score': 0.0,
                    'retorno_stress_medio': 0.0,
                    'dias_stress': 0,
                    'total_dias': total_dias,
                    'volatilidade_stress': 0.0,
                    'classificacao': 'SEM_STRESS',
                    'percentual_stress': 0.0
                }
            
            # Calcular métricas
            retornos_stress = dias_stress['retorno_ativo'].dropna()
            
            if retornos_stress.empty:
                retorno_stress_medio = 0.0
                volatilidade_stress = 0.0
            else:
                retorno_stress_medio = retornos_stress.mean()
                volatilidade_stress = retornos_stress.std()
            
            # AFIV Score = retorno médio nos dias de stress (em %)
            afiv_score = retorno_stress_medio * 100
            
            # Classificação baseada no AFIV Score
            if afiv_score >= 1.5:
                classificacao = 'MUITO_ANTIFRAGIL'
            elif afiv_score >= 0.5:
                classificacao = 'ANTIFRAGIL'
            elif afiv_score >= -0.5:
                classificacao = 'NEUTRO'
            elif afiv_score >= -1.5:
                classificacao = 'FRAGIL'
            else:
                classificacao = 'MUITO_FRAGIL'
            
            percentual_stress = (len(dias_stress) / total_dias * 100) if total_dias > 0 else 0.0
            
            resultado = {
                'afiv_score': float(afiv_score),
                'retorno_stress_medio': float(retorno_stress_medio * 100),
                'dias_stress': int(len(dias_stress)),
                'total_dias': int(total_dias),
                'volatilidade_stress': float(volatilidade_stress * 100) if volatilidade_stress else 0.0,
                'classificacao': classificacao,
                'percentual_stress': float(percentual_stress)
            }
            
            logger.info(f"AFIV Score calculado: {afiv_score:.2f}% ({classificacao})")
            
            return resultado
            
        except Exception as e:
            logger.error(f"Erro ao calcular AFIV Score: {e}")
            return {
                'afiv_score': 0.0,
                'retorno_stress_medio': 0.0,
                'dias_stress': 0,
                'total_dias': 0,
                'volatilidade_stress': 0.0,
                'classificacao': 'ERRO',
                'percentual_stress': 0.0
            }
    
    def analisar_ativo_antifragil(self, ticker: str, periodo_dias: int = 252) -> Dict:
        """Análise antifrágil completa para um ativo - VERSÃO SIMPLIFICADA"""
        try:
            logger.info(f"Iniciando análise antifrágil para {ticker}")
            
            # Obter dados do mercado
            dados_mercado = self.obter_dados_mercado_ibov(periodo_dias)
            if dados_mercado.empty:
                return {
                    'success': False,
                    'error': 'Não foi possível obter dados do mercado'
                }
            
            # Calcular dias de stress
            dados_mercado = self.calcular_dias_stress(dados_mercado)
            
            # Obter dados do ativo
            dados_ativo = self.obter_dados_ativo(ticker, periodo_dias)
            if dados_ativo.empty:
                return {
                    'success': False,
                    'error': f'Não foi possível obter dados do ativo {ticker}'
                }
            
            # Calcular AFIV Score
            afiv_resultado = self.calcular_afiv_score(dados_ativo, dados_mercado)
            
            # Métricas adicionais
            preco_atual = float(dados_ativo['Close'].iloc[-1]) if not dados_ativo.empty else 0.0
            retorno_total = float(dados_ativo['retorno_ativo'].sum() * 100) if 'retorno_ativo' in dados_ativo.columns else 0.0
            volatilidade_total = float(dados_ativo['retorno_ativo'].std() * np.sqrt(252) * 100) if 'retorno_ativo' in dados_ativo.columns else 0.0
            
            # 🔥 DADOS PARA GRÁFICOS SIMPLIFICADOS
            chart_data = self.preparar_dados_graficos_simples(dados_ativo, dados_mercado, ticker)
            
            # 🔥 ANÁLISE BÁSICA DE STRESS
            analise_stress = self.analisar_comportamento_stress_simples(dados_ativo, dados_mercado)
            
            resultado = {
                'success': True,
                'ticker': ticker,
                'periodo_dias': periodo_dias,
                'preco_atual': preco_atual,
                'afiv_score': afiv_resultado['afiv_score'],
                'classificacao': afiv_resultado['classificacao'],
                'retorno_stress_medio': afiv_resultado['retorno_stress_medio'],
                'dias_stress': afiv_resultado['dias_stress'],
                'total_dias': afiv_resultado['total_dias'],
                'percentual_stress': afiv_resultado['percentual_stress'],
                'volatilidade_stress': afiv_resultado['volatilidade_stress'],
                'retorno_total_periodo': retorno_total,
                'volatilidade_anualizada': volatilidade_total,
                'chart_data': chart_data,
                'analise_stress': analise_stress,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"Análise antifrágil concluída para {ticker}: AFIV={afiv_resultado['afiv_score']:.2f}%")
            
            return resultado
            
        except Exception as e:
            logger.error(f"Erro na análise antifrágil de {ticker}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def preparar_dados_graficos_simples(self, dados_ativo: pd.DataFrame, dados_mercado: pd.DataFrame, ticker: str) -> Dict:
        """Prepara dados completos para gráficos"""
        try:
            dados_combinados = dados_ativo.merge(
                dados_mercado[['stress_day', 'delta_iv_mercado', 'iv_mercado']], 
                left_index=True, 
                right_index=True, 
                how='inner'
            )
            
            if dados_combinados.empty:
                return {'error': 'Nenhuma data comum'}
            
            # 🔥 CALCULAR PERFORMANCE COMPARATIVA REAL
            dias_normais = dados_combinados[dados_combinados['stress_day'] == 0]['retorno_ativo']
            dias_stress = dados_combinados[dados_combinados['stress_day'] == 1]['retorno_ativo']
            
            retorno_normal_medio = float(dias_normais.mean() * 100) if not dias_normais.empty else 0.0
            retorno_stress_medio = float(dias_stress.mean() * 100) if not dias_stress.empty else 0.0
            volatilidade_normal = float(dias_normais.std() * 100) if not dias_normais.empty else 0.0
            volatilidade_stress = float(dias_stress.std() * 100) if not dias_stress.empty else 0.0
            
            # 🔥 PREPARAR DISTRIBUIÇÕES REAIS
            retornos_normais = (dias_normais * 100).tolist() if not dias_normais.empty else []
            retornos_stress = (dias_stress * 100).tolist() if not dias_stress.empty else []
            
            logger.info(f"📊 Gráficos {ticker}: {len(dias_normais)} dias normais, {len(dias_stress)} dias stress")
            
            return {
                'preco_vs_stress': {
                    'dates': dados_combinados.index.strftime('%Y-%m-%d').tolist(),
                    'precos': dados_combinados['Close'].tolist(),
                    'stress_days': dados_combinados['stress_day'].tolist(),
                    'retornos': (dados_combinados['retorno_ativo'] * 100).fillna(0).tolist()
                },
                'iv_mercado': {
                    'dates': dados_mercado.index.strftime('%Y-%m-%d').tolist(),
                    'iv_values': dados_mercado['iv_mercado'].fillna(0).tolist(),
                    'delta_iv': dados_mercado['delta_iv_mercado'].fillna(0).tolist(),
                    'threshold': self.stress_threshold
                },
                'performance_comparativa': {
                    'retorno_normal_medio': retorno_normal_medio,
                    'retorno_stress_medio': retorno_stress_medio,
                    'volatilidade_normal': volatilidade_normal,
                    'volatilidade_stress': volatilidade_stress,
                    'count_normal': len(dias_normais),
                    'count_stress': len(dias_stress)
                },
                'distribuicao_retornos': {
                    'retornos_normais': retornos_normais,
                    'retornos_stress': retornos_stress
                }
            }
            
        except Exception as e:
            logger.error(f"Erro ao preparar dados para gráficos: {e}")
            return {'error': str(e)}
    
    def analisar_comportamento_stress_simples(self, dados_ativo: pd.DataFrame, dados_mercado: pd.DataFrame) -> Dict:
        """Análise completa do comportamento em stress"""
        try:
            dados_combinados = dados_ativo.merge(
                dados_mercado[['stress_day', 'delta_iv_mercado']], 
                left_index=True, 
                right_index=True, 
                how='inner'
            )
            
            if dados_combinados.empty:
                return {'error': 'Dados insuficientes'}
            
            dias_stress = dados_combinados[dados_combinados['stress_day'] == 1]
            dias_normais = dados_combinados[dados_combinados['stress_day'] == 0]
            
            # 🔥 CALCULAR MÉTRICAS REAIS
            if not dias_stress.empty:
                stress_positivos = len(dias_stress[dias_stress['retorno_ativo'] > 0])
                stress_negativos = len(dias_stress[dias_stress['retorno_ativo'] <= 0])
                taxa_acerto = (stress_positivos / len(dias_stress) * 100)
                
                maior_ganho_stress = float(dias_stress['retorno_ativo'].max() * 100)
                maior_perda_stress = float(dias_stress['retorno_ativo'].min() * 100)
                retorno_stress_medio = float(dias_stress['retorno_ativo'].mean() * 100)
            else:
                stress_positivos = stress_negativos = taxa_acerto = 0
                maior_ganho_stress = maior_perda_stress = retorno_stress_medio = 0.0
            
            if not dias_normais.empty:
                retorno_normal_medio = float(dias_normais['retorno_ativo'].mean() * 100)
            else:
                retorno_normal_medio = 0.0
            
            # Performance ratio
            performance_ratio = retorno_stress_medio / retorno_normal_medio if retorno_normal_medio != 0 else 0
            
            # 🔥 INTERPRETAÇÃO BASEADA NOS DADOS REAIS
            if len(dias_stress) == 0:
                interpretacao = "POUCOS DADOS: Período analisado apresentou baixa volatilidade no mercado"
                razoes = ["📊 Período de baixa volatilidade no mercado", "⏳ Análise requer mais dados históricos"]
            elif performance_ratio > 1.5:
                interpretacao = "MUITO ANTIFRÁGIL: Performance significativamente melhor em stress"
                razoes = [
                    f"📈 Performance {performance_ratio:.1f}x melhor em stress",
                    f"🎯 {taxa_acerto:.0f}% de consistência em dias de stress",
                    "⚡ Forte capacidade de aproveitar volatilidade"
                ]
            elif performance_ratio > 1:
                interpretacao = "ANTIFRÁGIL: Performance melhor em momentos de stress"
                razoes = [
                    f"📈 Performance {performance_ratio:.1f}x melhor em stress",
                    f"🎯 {taxa_acerto:.0f}% de acertos em stress"
                ]
            elif performance_ratio > 0.5:
                interpretacao = "RESILIENTE: Performance estável mesmo em stress"
                razoes = ["🛡️ Demonstra resistência em períodos voláteis"]
            else:
                interpretacao = "FRÁGIL: Performance deteriora em stress"
                razoes = ["⚠️ Sofre mais em períodos de alta volatilidade"]
            
            return {
                'dias_stress_analisados': len(dias_stress),
                'dias_normais_analisados': len(dias_normais),
                'taxa_acerto_stress': round(taxa_acerto, 1),
                'stress_positivos': stress_positivos,
                'stress_negativos': stress_negativos,
                'maior_ganho_stress': round(maior_ganho_stress, 2),
                'maior_perda_stress': round(maior_perda_stress, 2),
                'retorno_normal_medio': round(retorno_normal_medio, 2),
                'retorno_stress_medio': round(retorno_stress_medio, 2),
                'performance_ratio': round(performance_ratio, 2),
                'interpretacao': interpretacao,
                'razoes_antifragilidade': razoes
            }
            
        except Exception as e:
            logger.error(f"Erro na análise de comportamento: {e}")
            return {'error': str(e)}
    
    def obter_ranking_antifragil(self, limite: int = 20, periodo_dias: int = 252) -> List[Dict]:
        """Obtém ranking dos ativos mais antifrágeis - VERSÃO CORRIGIDA"""
        try:
            logger.info(f"Gerando ranking antifrágil (top {limite})")
            
            # 🔥 EXPANDIR PARA MAIS ATIVOS GRADUALMENTE
            if limite <= 5:
                ativos_analise = TOP_20_STOCKS[:5]
            elif limite <= 10:
                ativos_analise = TOP_20_STOCKS[:10]
            else:
                ativos_analise = TOP_20_STOCKS[:15]  # Máximo 15 por performance
            
            logger.info(f"Analisando {len(ativos_analise)} ativos: {ativos_analise}")
            
            # Obter dados do mercado
            dados_mercado = None
            try:
                dados_mercado = self.obter_dados_mercado_ibov(periodo_dias)
                if dados_mercado is None or dados_mercado.empty:
                    logger.error("Não foi possível obter dados do mercado")
                    return []
                dados_mercado = self.calcular_dias_stress(dados_mercado)
            except Exception as e:
                logger.error(f"Erro ao obter dados do mercado: {e}")
                return []
            
            ranking = []
            
            for i, ticker in enumerate(ativos_analise):
                try:
                    logger.info(f"🔍 Analisando {ticker} ({i+1}/{len(ativos_analise)})")
                    
                    dados_ativo = self.obter_dados_ativo(ticker, periodo_dias)
                    if dados_ativo.empty:
                        logger.warning(f"❌ Dados vazios para {ticker}")
                        continue
                    
                    afiv_resultado = self.calcular_afiv_score(dados_ativo, dados_mercado)
                    
                    if afiv_resultado['total_dias'] > 30:
                        try:
                            preco_atual = float(dados_ativo['Close'].iloc[-1])
                            
                            ranking.append({
                                'posicao': 0,
                                'ticker': ticker,
                                'afiv_score': afiv_resultado['afiv_score'],
                                'classificacao': afiv_resultado['classificacao'],
                                'preco_atual': preco_atual,
                                'retorno_stress_medio': afiv_resultado['retorno_stress_medio'],
                                'dias_stress': afiv_resultado['dias_stress'],
                                'percentual_stress': afiv_resultado['percentual_stress'],
                                'volatilidade_stress': afiv_resultado['volatilidade_stress']
                            })
                            
                            logger.info(f"✅ {ticker}: AFIV={afiv_resultado['afiv_score']:.2f}% ({afiv_resultado['classificacao']}) - {afiv_resultado['dias_stress']} dias stress")
                            
                        except Exception as price_error:
                            logger.warning(f"⚠️ Erro ao processar {ticker}: {price_error}")
                            continue
                    else:
                        logger.warning(f"⚠️ Dados insuficientes para {ticker}: {afiv_resultado['total_dias']} dias")
                
                except Exception as e:
                    logger.warning(f"❌ Erro ao analisar {ticker}: {e}")
                    continue
            
            if not ranking:
                logger.warning("⚠️ Nenhum ativo foi processado com sucesso")
                return []
            
            # Ordenar e posicionar
            ranking.sort(key=lambda x: x['afiv_score'], reverse=True)
            for i, item in enumerate(ranking):
                item['posicao'] = i + 1
            
            ranking = ranking[:limite]
            
            logger.info(f"✅ Ranking antifrágil gerado com {len(ranking)} ativos")
            return ranking
            
        except Exception as e:
            logger.error(f"❌ Erro ao gerar ranking antifrágil: {e}")
            return []
    def obter_estatisticas_antifragil(self) -> Dict:
        """Obtém estatísticas gerais do indicador antifrágil"""
        try:
            return {
                'total_ativos_disponiveis': len(TOP_20_STOCKS),
                'ativos_disponiveis': TOP_20_STOCKS.copy(),
                'periodo_analise_padrao': 252,
                'threshold_stress': self.stress_threshold,
                'proxy_mercado': 'IBOV (^BVSP)',
                'ultima_atualizacao': datetime.now().isoformat(),
                'metodologia': 'AFIV Score = Retorno médio do ativo nos dias de stress do mercado (IV > 5%)',
                'versao': 'Simplificada para testes'
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas antifrágil: {e}")
            return {
                'total_ativos_disponiveis': len(TOP_20_STOCKS),
                'erro': str(e)
            }

# Instância global do serviço
antifragil_service = AntifragilService()

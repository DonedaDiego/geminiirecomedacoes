# antifragil_service.py - Serviço do Indicador Antifrágil

import psycopg2
import pandas as pd
import numpy as np
import yfinance as yf
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging

# Importar o serviço de VI que você já tem
from pro.vi_service import VolatilityImpliedService

logger = logging.getLogger(__name__)

class AntifragilService:
    """Serviço para calcular o Indicador Antifrágil baseado em Volatilidade Implícita"""
    
    def __init__(self):
        self.conn_params = self._get_db_connection()
        self.vi_service = VolatilityImpliedService()
        self.stress_threshold = 5.0  # Threshold para dias de stress (5% de aumento na IV do mercado)
        
    def _get_db_connection(self) -> dict:
        """Obtém parâmetros de conexão do banco de dados"""
        flask_env = os.getenv('FLASK_ENV', 'production')
        
        if flask_env == 'development':
            # Banco local
            return {
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': int(os.getenv('DB_PORT', 5432)),
                'dbname': os.getenv('DB_NAME', 'postgres'),
                'user': os.getenv('DB_USER', 'postgres'),
                'password': os.getenv('DB_PASSWORD', '#geminii')
            }
        else:
            # Railway (produção)
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
        """Obtém lista de ativos da base fundamentalista para análise"""
        try:
            conn = self._conectar_banco()
            cursor = conn.cursor()
            
            # Pegar ativos com liquidez para análise antifrágil
            cursor.execute("""
                SELECT DISTINCT papel 
                FROM banco_fundamentalista 
                WHERE papel IS NOT NULL 
                AND liq_2meses IS NOT NULL
                AND cotacao IS NOT NULL
                ORDER BY papel
            """)
            
            ativos = [row[0] for row in cursor.fetchall()]
            logger.info(f"Ativos disponíveis para análise antifrágil: {len(ativos)}")
            
            cursor.close()
            conn.close()
            
            return ativos
            
        except Exception as e:
            logger.error(f"Erro ao obter ativos: {e}")
            return []
    
    def obter_dados_mercado_ibov(self, periodo_dias: int = 252) -> pd.DataFrame:
        """Obtém dados do IBOVESPA como proxy do mercado"""
        try:
            to_date = datetime.now()
            from_date = to_date - timedelta(days=periodo_dias + 50)
            
            logger.info(f"Obtendo dados do IBOV para período de {periodo_dias} dias")
            
            # Usar BOVA11 como proxy do IBOV (tem opções e IV)
            ibov = yf.Ticker("BOVA11.SA")
            hist = ibov.history(start=from_date, end=to_date)
            
            if hist.empty:
                logger.warning("Usando ^BVSP como fallback")
                ibov = yf.Ticker("^BVSP")
                hist = ibov.history(start=from_date, end=to_date)
            
            if not hist.empty:
                # Calcular retornos
                hist['retorno_mercado'] = hist['Close'].pct_change()
                
                # Calcular volatilidade implícita simulada baseada na volatilidade histórica
                # (Para um indicador mais robusto, use dados reais de IV do BOVA11)
                returns = hist['retorno_mercado'].dropna()
                rolling_vol = returns.rolling(window=21).std() * np.sqrt(252) * 100
                hist['iv_mercado'] = rolling_vol
                hist['delta_iv_mercado'] = hist['iv_mercado'].diff()
                
                logger.info(f"Dados do IBOV obtidos: {len(hist)} registros")
                return hist
            else:
                logger.error("Não foi possível obter dados do IBOV")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Erro ao obter dados do mercado: {e}")
            return pd.DataFrame()
    
    def obter_dados_ativo(self, ticker: str, periodo_dias: int = 252) -> pd.DataFrame:
        """Obtém dados históricos de um ativo específico"""
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
            
            # Tentar obter IV real via OpLab (se disponível)
            try:
                vi_data = self.vi_service.create_analysis(ticker.replace('.SA', ''), periodo_dias)
                if vi_data.get('success') and vi_data.get('chart_data', {}).get('daily_metrics'):
                    # Processar dados de IV real
                    iv_df = pd.DataFrame(vi_data['chart_data']['daily_metrics'])
                    if not iv_df.empty and 'date' in iv_df.columns and 'iv_avg' in iv_df.columns:
                        iv_df['date'] = pd.to_datetime(iv_df['date'])
                        iv_df = iv_df.set_index('date')
                        
                        # Merge com dados históricos
                        hist = hist.merge(iv_df[['iv_avg']], left_index=True, right_index=True, how='left')
                        hist['iv_ativo'] = hist['iv_avg']
                        hist.drop('iv_avg', axis=1, inplace=True)
                        
                        logger.info(f"IV real obtida para {ticker}")
                    else:
                        logger.warning(f"Dados de IV inválidos para {ticker}")
                        hist['iv_ativo'] = None
                else:
                    logger.warning(f"Não foi possível obter IV para {ticker}")
                    hist['iv_ativo'] = None
            except Exception as e:
                logger.warning(f"Erro ao obter IV para {ticker}: {e}")
                hist['iv_ativo'] = None
            
            logger.info(f"Dados do ativo {ticker} obtidos: {len(hist)} registros")
            return hist
            
        except Exception as e:
            logger.error(f"Erro ao obter dados do ativo {ticker}: {e}")
            return pd.DataFrame()
    
    def calcular_dias_stress(self, dados_mercado: pd.DataFrame) -> pd.DataFrame:
        """Identifica dias de stress baseado na variação da IV do mercado"""
        try:
            if dados_mercado.empty or 'delta_iv_mercado' not in dados_mercado.columns:
                logger.warning("Dados de mercado insuficientes para calcular dias de stress")
                return dados_mercado
            
            # Marcar dias de stress (aumento > threshold% na IV do mercado)
            dados_mercado['stress_day'] = (dados_mercado['delta_iv_mercado'] > self.stress_threshold).astype(int)
            
            stress_days = dados_mercado['stress_day'].sum()
            total_days = len(dados_mercado.dropna(subset=['delta_iv_mercado']))
            
            logger.info(f"Dias de stress identificados: {stress_days} de {total_days} ({stress_days/total_days*100:.1f}%)")
            
            return dados_mercado
            
        except Exception as e:
            logger.error(f"Erro ao calcular dias de stress: {e}")
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
                    'classificacao': 'DADOS_INSUFICIENTES'
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
                    'classificacao': 'DADOS_INSUFICIENTES'
                }
            
            # Filtrar dias de stress
            dias_stress = dados_combinados[dados_combinados['stress_day'] == 1]
            
            if dias_stress.empty:
                logger.warning("Nenhum dia de stress encontrado")
                return {
                    'afiv_score': 0.0,
                    'retorno_stress_medio': 0.0,
                    'dias_stress': 0,
                    'total_dias': len(dados_combinados),
                    'volatilidade_stress': 0.0,
                    'classificacao': 'SEM_STRESS'
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
            
            resultado = {
                'afiv_score': float(afiv_score),
                'retorno_stress_medio': float(retorno_stress_medio * 100),
                'dias_stress': int(len(dias_stress)),
                'total_dias': int(len(dados_combinados)),
                'volatilidade_stress': float(volatilidade_stress * 100) if volatilidade_stress else 0.0,
                'classificacao': classificacao,
                'percentual_stress': float(len(dias_stress) / len(dados_combinados) * 100)
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
                'classificacao': 'ERRO'
            }
    
    def analisar_ativo_antifragil(self, ticker: str, periodo_dias: int = 252) -> Dict:
        """Análise antifrágil completa para um ativo"""
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
            
            # 🔥 PREPARAR DADOS PARA GRÁFICOS
            chart_data = self.preparar_dados_graficos(dados_ativo, dados_mercado, ticker)
            
            # 🔥 ANÁLISE DETALHADA DOS DIAS DE STRESS
            analise_stress = self.analisar_comportamento_stress(dados_ativo, dados_mercado)
            
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
                'chart_data': chart_data,  # 🔥 DADOS PARA GRÁFICOS
                'analise_stress': analise_stress,  # 🔥 ANÁLISE DETALHADA
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
    
    def preparar_dados_graficos(self, dados_ativo: pd.DataFrame, dados_mercado: pd.DataFrame, ticker: str) -> Dict:
        """Prepara dados específicos para gráficos do frontend"""
        try:
            chart_data = {}
            
            # Alinhar dados
            dados_combinados = dados_ativo.merge(
                dados_mercado[['stress_day', 'delta_iv_mercado', 'iv_mercado']], 
                left_index=True, 
                right_index=True, 
                how='inner'
            )
            
            if dados_combinados.empty:
                return {'error': 'Nenhuma data comum entre ativo e mercado'}
            
            # 1. GRÁFICO: Preço do ativo + marcação dos dias de stress
            chart_data['preco_vs_stress'] = {
                'dates': dados_combinados.index.strftime('%Y-%m-%d').tolist(),
                'precos': dados_combinados['Close'].tolist(),
                'stress_days': dados_combinados['stress_day'].tolist(),
                'retornos': (dados_combinados['retorno_ativo'] * 100).tolist()
            }
            
            # 2. GRÁFICO: IV do mercado + threshold
            chart_data['iv_mercado'] = {
                'dates': dados_mercado.index.strftime('%Y-%m-%d').tolist(),
                'iv_values': dados_mercado['iv_mercado'].fillna(0).tolist(),
                'delta_iv': dados_mercado['delta_iv_mercado'].fillna(0).tolist(),
                'threshold': self.stress_threshold
            }
            
            # 3. GRÁFICO: Performance em dias normais vs dias de stress
            dias_normais = dados_combinados[dados_combinados['stress_day'] == 0]['retorno_ativo']
            dias_stress = dados_combinados[dados_combinados['stress_day'] == 1]['retorno_ativo']
            
            chart_data['performance_comparativa'] = {
                'retorno_normal_medio': float(dias_normais.mean() * 100) if not dias_normais.empty else 0,
                'retorno_stress_medio': float(dias_stress.mean() * 100) if not dias_stress.empty else 0,
                'volatilidade_normal': float(dias_normais.std() * 100) if not dias_normais.empty else 0,
                'volatilidade_stress': float(dias_stress.std() * 100) if not dias_stress.empty else 0,
                'count_normal': len(dias_normais),
                'count_stress': len(dias_stress)
            }
            
            # 4. GRÁFICO: Retornos acumulados
            retornos_acum = (1 + dados_combinados['retorno_ativo']).cumprod()
            retornos_acum_stress = retornos_acum[dados_combinados['stress_day'] == 1]
            
            chart_data['retornos_acumulados'] = {
                'dates': dados_combinados.index.strftime('%Y-%m-%d').tolist(),
                'retornos_acum_total': ((retornos_acum - 1) * 100).tolist(),
                'stress_periods': {
                    'dates': retornos_acum_stress.index.strftime('%Y-%m-%d').tolist(),
                    'values': ((retornos_acum_stress - 1) * 100).tolist()
                }
            }
            
            # 5. DISTRIBUIÇÃO: Histograma de retornos
            chart_data['distribuicao_retornos'] = {
                'retornos_normais': (dias_normais * 100).tolist(),
                'retornos_stress': (dias_stress * 100).tolist(),
                'bins': 20  # Para histograma
            }
            
            return chart_data
            
        except Exception as e:
            logger.error(f"Erro ao preparar dados para gráficos: {e}")
            return {'error': str(e)}
    
    def analisar_comportamento_stress(self, dados_ativo: pd.DataFrame, dados_mercado: pd.DataFrame) -> Dict:
        """Análise detalhada do comportamento em dias de stress"""
        try:
            # Alinhar dados
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
            
            # Análise de consistência
            stress_positivos = len(dias_stress[dias_stress['retorno_ativo'] > 0])
            stress_negativos = len(dias_stress[dias_stress['retorno_ativo'] <= 0])
            taxa_acerto = (stress_positivos / len(dias_stress) * 100) if len(dias_stress) > 0 else 0
            
            # Maior ganho/perda em stress
            maior_ganho_stress = float(dias_stress['retorno_ativo'].max() * 100) if not dias_stress.empty else 0
            maior_perda_stress = float(dias_stress['retorno_ativo'].min() * 100) if not dias_stress.empty else 0
            
            # Comparação com dias normais
            retorno_normal_medio = float(dias_normais['retorno_ativo'].mean() * 100) if not dias_normais.empty else 0
            retorno_stress_medio = float(dias_stress['retorno_ativo'].mean() * 100) if not dias_stress.empty else 0
            
            # Ratio de performance
            performance_ratio = retorno_stress_medio / retorno_normal_medio if retorno_normal_medio != 0 else 0
            
            # Interpretação
            if performance_ratio > 2:
                interpretacao = "EXCEPCIONALMENTE ANTIFRÁGIL: Performance em stress é mais que 2x melhor"
            elif performance_ratio > 1.5:
                interpretacao = "MUITO ANTIFRÁGIL: Performance significativamente melhor em stress"
            elif performance_ratio > 1:
                interpretacao = "ANTIFRÁGIL: Performance melhor em momentos de stress"
            elif performance_ratio > 0.5:
                interpretacao = "RESILIENTE: Performance estável mesmo em stress"
            else:
                interpretacao = "FRÁGIL: Performance deteriora significativamente em stress"
            
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
                'razoes_antifragilidade': self._gerar_razoes_antifragilidade(performance_ratio, taxa_acerto)
            }
            
        except Exception as e:
            logger.error(f"Erro na análise de comportamento: {e}")
            return {'error': str(e)}
    
    def _gerar_razoes_antifragilidade(self, performance_ratio: float, taxa_acerto: float) -> List[str]:
        """Gera explicações do por que o ativo é antifrágil"""
        razoes = []
        
        if performance_ratio > 1.2:
            razoes.append(f"📈 Performance {performance_ratio:.1f}x melhor em momentos de stress")
        
        if taxa_acerto > 60:
            razoes.append(f"🎯 {taxa_acerto:.0f}% de consistência positiva em dias de stress")
        
        if performance_ratio > 1 and taxa_acerto > 50:
            razoes.append("🛡️ Ativo demonstra características defensivas e oportunísticas")
        
        if performance_ratio > 1.5:
            razoes.append("⚡ Forte capacidade de capturar oportunidades em volatilidade")
        
        if taxa_acerto > 70:
            razoes.append("🔒 Alta previsibilidade de comportamento positivo em crises")
        
        # Se não há razões positivas, explicar por que é frágil
        if not razoes:
            if performance_ratio < 0.5:
                razoes.append("⚠️ Performance deteriora significativamente em momentos de stress")
            if taxa_acerto < 40:
                razoes.append("📉 Baixa consistência de retornos positivos em volatilidade")
            if performance_ratio < 1 and taxa_acerto < 50:
                razoes.append("🚨 Ativo demonstra alta fragilidade em períodos incertos")
        
        return razoes if razoes else ["📊 Comportamento neutro em relação ao stress do mercado"]
    
    def obter_ranking_antifragil(self, limite: int = 20, periodo_dias: int = 252) -> List[Dict]:
        """Obtém ranking dos ativos mais antifrágeis"""
        try:
            logger.info(f"Gerando ranking antifrágil (top {limite})")
            
            ativos = self.obter_ativos_disponiveis()
            if not ativos:
                return []
            
            # Limitar análise para performance (pegar uma amostra representativa)
            if len(ativos) > 50:
                # Pegar ativos com boa liquidez (ordenar alfabeticamente para consistência)
                ativos = sorted(ativos)[:50]
                logger.info(f"Limitando análise a {len(ativos)} ativos por performance")
            
            # Obter dados do mercado uma vez
            dados_mercado = self.obter_dados_mercado_ibov(periodo_dias)
            if dados_mercado.empty:
                logger.error("Não foi possível obter dados do mercado para ranking")
                return []
            
            dados_mercado = self.calcular_dias_stress(dados_mercado)
            
            ranking = []
            
            for i, ticker in enumerate(ativos):
                try:
                    logger.info(f"Analisando {ticker} ({i+1}/{len(ativos)})")
                    
                    # Obter dados do ativo
                    dados_ativo = self.obter_dados_ativo(ticker, periodo_dias)
                    if dados_ativo.empty:
                        continue
                    
                    # Calcular AFIV
                    afiv_resultado = self.calcular_afiv_score(dados_ativo, dados_mercado)
                    
                    if afiv_resultado['total_dias'] > 50:  # Mínimo de dados
                        preco_atual = float(dados_ativo['Close'].iloc[-1])
                        
                        ranking.append({
                            'posicao': 0,  # Será definido após ordenação
                            'ticker': ticker,
                            'afiv_score': afiv_resultado['afiv_score'],
                            'classificacao': afiv_resultado['classificacao'],
                            'preco_atual': preco_atual,
                            'retorno_stress_medio': afiv_resultado['retorno_stress_medio'],
                            'dias_stress': afiv_resultado['dias_stress'],
                            'percentual_stress': afiv_resultado['percentual_stress'],
                            'volatilidade_stress': afiv_resultado['volatilidade_stress']
                        })
                    
                except Exception as e:
                    logger.warning(f"Erro ao analisar {ticker}: {e}")
                    continue
            
            # Ordenar por AFIV Score (decrescente)
            ranking.sort(key=lambda x: x['afiv_score'], reverse=True)
            
            # Definir posições
            for i, item in enumerate(ranking):
                item['posicao'] = i + 1
            
            # Limitar ao top solicitado
            ranking = ranking[:limite]
            
            logger.info(f"Ranking antifrágil gerado com {len(ranking)} ativos")
            
            return ranking
            
        except Exception as e:
            logger.error(f"Erro ao gerar ranking antifrágil: {e}")
            return []
    
    def obter_estatisticas_antifragil(self) -> Dict:
        """Obtém estatísticas gerais do indicador antifrágil"""
        try:
            conn = self._conectar_banco()
            cursor = conn.cursor()
            
            # Total de ativos disponíveis
            cursor.execute("SELECT COUNT(*) FROM banco_fundamentalista WHERE papel IS NOT NULL")
            total_ativos = cursor.fetchone()[0]
            
            cursor.close()
            conn.close()
            
            return {
                'total_ativos_disponiveis': total_ativos,
                'periodo_analise_padrao': 252,
                'threshold_stress': self.stress_threshold,
                'proxy_mercado': 'BOVA11/IBOV',
                'ultima_atualizacao': datetime.now().isoformat(),
                'metodologia': 'AFIV Score = Retorno médio do ativo nos dias de stress do mercado (IV > 5%)'
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas antifrágil: {e}")
            return {
                'total_ativos_disponiveis': 0,
                'erro': str(e)
            }


# Instância global do serviço
antifragil_service = AntifragilService()
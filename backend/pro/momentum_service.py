# momentum_service.py - Serviço do Indicador Momentum US

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class MomentumService:
    """Serviço para análise de Momentum das 50 maiores empresas americanas"""
    
    def __init__(self):
        self.periodo_padrao = 365  # 1 ano de dados
        self.sma_filtro = 50  # Filtro SMA 50
        
        # Períodos para ROC
        self.roc_1mes = 21    # ~1 mês útil
        self.roc_3meses = 63  # ~3 meses úteis
        self.roc_6meses = 126 # ~6 meses úteis
        
        # Pesos para score composto
        self.pesos = {
            'retorno_1m': 0.25,    # 25%
            'retorno_3m': 0.25,    # 25%
            'retorno_6m': 0.25,    # 25%
            'volume_aceleracao': 0.15,  # 15%
            'volatilidade_negativa': 0.10  # 10%
        }
        
    def obter_top_50_empresas_eua(self) -> List[Dict]:
        """Reutiliza a mesma lista das 50 maiores empresas americanas"""
        
        empresas_por_setor = {
            'Technology': [
                {'ticker': 'AAPL', 'nome': 'Apple Inc.'},
                {'ticker': 'MSFT', 'nome': 'Microsoft Corporation'},
                {'ticker': 'GOOGL', 'nome': 'Alphabet Inc.'},
                {'ticker': 'AMZN', 'nome': 'Amazon.com Inc.'},
                {'ticker': 'NVDA', 'nome': 'NVIDIA Corporation'},
                {'ticker': 'META', 'nome': 'Meta Platforms Inc.'},
                {'ticker': 'TSLA', 'nome': 'Tesla Inc.'},
                {'ticker': 'NFLX', 'nome': 'Netflix Inc.'},
                {'ticker': 'ADBE', 'nome': 'Adobe Inc.'},
                {'ticker': 'CRM', 'nome': 'Salesforce Inc.'}
            ],
            'Financial Services': [
                {'ticker': 'BRK-B', 'nome': 'Berkshire Hathaway Inc.'},
                {'ticker': 'JPM', 'nome': 'JPMorgan Chase & Co.'},
                {'ticker': 'V', 'nome': 'Visa Inc.'},
                {'ticker': 'MA', 'nome': 'Mastercard Inc.'},
                {'ticker': 'BAC', 'nome': 'Bank of America Corp.'},
                {'ticker': 'WFC', 'nome': 'Wells Fargo & Co.'},
                {'ticker': 'GS', 'nome': 'Goldman Sachs Group Inc.'},
                {'ticker': 'MS', 'nome': 'Morgan Stanley'},
                {'ticker': 'AXP', 'nome': 'American Express Co.'},
                {'ticker': 'SPGI', 'nome': 'S&P Global Inc.'}
            ],
            'Healthcare': [
                {'ticker': 'UNH', 'nome': 'UnitedHealth Group Inc.'},
                {'ticker': 'JNJ', 'nome': 'Johnson & Johnson'},
                {'ticker': 'PFE', 'nome': 'Pfizer Inc.'},
                {'ticker': 'ABBV', 'nome': 'AbbVie Inc.'},
                {'ticker': 'LLY', 'nome': 'Eli Lilly and Co.'},
                {'ticker': 'TMO', 'nome': 'Thermo Fisher Scientific Inc.'},
                {'ticker': 'DHR', 'nome': 'Danaher Corporation'},
                {'ticker': 'BMY', 'nome': 'Bristol-Myers Squibb Co.'},
                {'ticker': 'AMGN', 'nome': 'Amgen Inc.'},
                {'ticker': 'CVS', 'nome': 'CVS Health Corporation'}
            ],
            'Consumer Cyclical': [
                {'ticker': 'HD', 'nome': 'Home Depot Inc.'},
                {'ticker': 'MCD', 'nome': 'McDonald\'s Corporation'},
                {'ticker': 'NKE', 'nome': 'Nike Inc.'},
                {'ticker': 'SBUX', 'nome': 'Starbucks Corporation'},
                {'ticker': 'LOW', 'nome': 'Lowe\'s Companies Inc.'},
                {'ticker': 'TJX', 'nome': 'TJX Companies Inc.'},
                {'ticker': 'F', 'nome': 'Ford Motor Company'},
                {'ticker': 'GM', 'nome': 'General Motors Company'},
                {'ticker': 'BKNG', 'nome': 'Booking Holdings Inc.'},
                {'ticker': 'ABNB', 'nome': 'Airbnb Inc.'}
            ],
            'Communication Services': [
                {'ticker': 'DIS', 'nome': 'Walt Disney Company'},
                {'ticker': 'CMCSA', 'nome': 'Comcast Corporation'},
                {'ticker': 'VZ', 'nome': 'Verizon Communications Inc.'},
                {'ticker': 'T', 'nome': 'AT&T Inc.'},
                {'ticker': 'TMUS', 'nome': 'T-Mobile US Inc.'}
            ],
            'Industrials': [
                {'ticker': 'BA', 'nome': 'Boeing Company'},
                {'ticker': 'CAT', 'nome': 'Caterpillar Inc.'},
                {'ticker': 'GE', 'nome': 'General Electric Company'},
                {'ticker': 'MMM', 'nome': '3M Company'},
                {'ticker': 'UPS', 'nome': 'United Parcel Service Inc.'}
            ]
        }
        
        # Montar lista final com setor
        empresas_completas = []
        for setor, empresas in empresas_por_setor.items():
            for empresa in empresas:
                empresa['setor'] = setor
                empresas_completas.append(empresa)
        
        return empresas_completas[:50]
    
    def obter_dados_acao(self, ticker: str, periodo_dias: int = 365) -> pd.DataFrame:
        """Obtém dados históricos de uma ação americana"""
        try:
            to_date = datetime.now()
            from_date = to_date - timedelta(days=periodo_dias + 100)  # Margem para cálculos
            
            logger.info(f"Obtendo dados de {ticker}")
            
            stock = yf.Ticker(ticker)
            hist = stock.history(start=from_date, end=to_date)
            
            if hist.empty:
                logger.warning(f"Nenhum dado encontrado para {ticker}")
                return pd.DataFrame()
            
            # Limpar dados
            hist = hist.dropna()
            
            if len(hist) < 150:  # Precisa de pelo menos 150 dias para ROC 6M
                logger.warning(f"Dados insuficientes para {ticker}: {len(hist)} dias")
                return pd.DataFrame()
            
            logger.info(f"Dados obtidos para {ticker}: {len(hist)} registros")
            return hist
            
        except Exception as e:
            logger.error(f"Erro ao obter dados de {ticker}: {e}")
            return pd.DataFrame()
    
    def calcular_roc(self, precos: pd.Series, periodo: int) -> pd.Series:
        """Calcula Rate of Change (ROC) manualmente"""
        try:
            if len(precos) < periodo + 1:
                return pd.Series([np.nan] * len(precos), index=precos.index)
            
            # ROC = (P_atual - P_n_dias_atras) / P_n_dias_atras * 100
            roc = ((precos - precos.shift(periodo)) / precos.shift(periodo)) * 100
            
            # Substituir valores inválidos
            roc = roc.fillna(0)
            roc = roc.replace([np.inf, -np.inf], 0)
            
            return roc
            
        except Exception as e:
            logger.error(f"Erro ao calcular ROC {periodo}: {e}")
            return pd.Series([0] * len(precos), index=precos.index)
    
    def calcular_sma(self, precos: pd.Series, periodo: int) -> pd.Series:
        """Calcula Média Móvel Simples"""
        try:
            return precos.rolling(window=periodo).mean()
        except Exception as e:
            logger.error(f"Erro ao calcular SMA {periodo}: {e}")
            return pd.Series([np.nan] * len(precos), index=precos.index)
    
    def calcular_volatilidade_negativa(self, retornos: pd.Series, janela: int = 21) -> pd.Series:
        """Calcula volatilidade apenas dos retornos negativos"""
        try:
            # Filtrar apenas retornos negativos
            retornos_negativos = retornos.where(retornos < 0, np.nan)
            
            # Calcular desvio padrão móvel dos retornos negativos
            vol_negativa = retornos_negativos.rolling(window=janela).std() * np.sqrt(252) * 100
            
            # Preencher NaN com 0 (menor volatilidade negativa = melhor)
            vol_negativa = vol_negativa.fillna(0)
            
            return vol_negativa
            
        except Exception as e:
            logger.error(f"Erro ao calcular volatilidade negativa: {e}")
            return pd.Series([0] * len(retornos), index=retornos.index)
    
    def calcular_aceleracao_volume(self, volumes: pd.Series, janela: int = 63) -> pd.Series:
        """Calcula aceleração do volume (volume atual vs média de 3M)"""
        try:
            # Média móvel do volume
            volume_media = volumes.rolling(window=janela).mean()
            
            # Aceleração = volume atual / média do volume
            aceleracao = volumes / volume_media
            
            # Normalizar (1 = normal, >1 = acelerando, <1 = desacelerando)
            aceleracao = aceleracao.fillna(1)
            aceleracao = aceleracao.replace([np.inf, -np.inf], 1)
            
            return aceleracao
            
        except Exception as e:
            logger.error(f"Erro ao calcular aceleração de volume: {e}")
            return pd.Series([1] * len(volumes), index=volumes.index)
    
    def calcular_indicadores_momentum(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula todos os indicadores de momentum"""
        try:
            if df.empty or len(df) < 150:
                logger.warning("Dados insuficientes para calcular indicadores momentum")
                return df
            
            # 1. ROCs para diferentes períodos
            df['roc_1m'] = self.calcular_roc(df['Close'], self.roc_1mes)
            df['roc_3m'] = self.calcular_roc(df['Close'], self.roc_3meses)
            df['roc_6m'] = self.calcular_roc(df['Close'], self.roc_6meses)
            
            # 2. SMA para filtro
            df['sma_50'] = self.calcular_sma(df['Close'], self.sma_filtro)
            
            # 3. Retornos diários para volatilidade
            df['retorno_diario'] = df['Close'].pct_change()
            
            # 4. Volatilidade negativa
            df['vol_negativa'] = self.calcular_volatilidade_negativa(df['retorno_diario'])
            
            # 5. Aceleração de volume
            df['aceleracao_volume'] = self.calcular_aceleracao_volume(df['Volume'])
            
            # 6. Filtro: acima da SMA 50
            df['acima_sma50'] = (df['Close'] > df['sma_50']).astype(int)
            
            # Remover NaN das primeiras linhas
            df = df.dropna(subset=['roc_6m', 'sma_50'])  # ROC 6M é o que demora mais
            
            if df.empty:
                logger.warning("DataFrame vazio após remover NaN")
                return df
            
            logger.info("Indicadores momentum calculados com sucesso")
            return df
            
        except Exception as e:
            logger.error(f"Erro ao calcular indicadores momentum: {e}")
            return df
    
    def calcular_momentum_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula o score composto de momentum"""
        try:
            if df.empty:
                return df
            
            # Normalizar componentes individuais (0 a 100)
            df['score_retorno_1m'] = self._normalizar_score(df['roc_1m'])
            df['score_retorno_3m'] = self._normalizar_score(df['roc_3m'])
            df['score_retorno_6m'] = self._normalizar_score(df['roc_6m'])
            
            # Volume: >1 é bom, normalizar diferente
            df['score_volume'] = self._normalizar_volume_score(df['aceleracao_volume'])
            
            # Volatilidade negativa: menor é melhor, inverter
            df['score_vol_negativa'] = self._normalizar_volatilidade_score(df['vol_negativa'])
            
            # Score composto com pesos
            df['momentum_score_raw'] = (
                df['score_retorno_1m'] * self.pesos['retorno_1m'] +
                df['score_retorno_3m'] * self.pesos['retorno_3m'] +
                df['score_retorno_6m'] * self.pesos['retorno_6m'] +
                df['score_volume'] * self.pesos['volume_aceleracao'] +
                df['score_vol_negativa'] * self.pesos['volatilidade_negativa']
            ) * 100
            
            # Aplicar filtro SMA 50 (reduzir score se abaixo da média)
            df['momentum_score'] = df['momentum_score_raw'] * (0.5 + 0.5 * df['acima_sma50'])
            
            # Classificar momentum
            df['momentum_classificacao'] = df['momentum_score'].apply(self._classificar_momentum)
            
            logger.info("Momentum score calculado com sucesso")
            return df
            
        except Exception as e:
            logger.error(f"Erro ao calcular momentum score: {e}")
            return df
    
    def _normalizar_score(self, serie: pd.Series, min_val: float = -50, max_val: float = 50) -> pd.Series:
        """Normaliza uma série para escala 0-100"""
        try:
            # Clampar valores extremos
            serie_clamp = serie.clip(min_val, max_val)
            
            # Normalizar para 0-100
            score = (serie_clamp - min_val) / (max_val - min_val) * 100
            
            return score.fillna(50)  # Neutro para NaN
            
        except Exception as e:
            logger.error(f"Erro ao normalizar score: {e}")
            return pd.Series([50] * len(serie), index=serie.index)
    
    def _normalizar_volume_score(self, serie: pd.Series) -> pd.Series:
        """Normaliza score de volume (>1 é bom)"""
        try:
            # Clampar entre 0.5 e 3.0
            serie_clamp = serie.clip(0.5, 3.0)
            
            # Normalizar: 1 = 50 pontos, 3 = 100 pontos, 0.5 = 0 pontos
            score = (serie_clamp - 0.5) / (3.0 - 0.5) * 100
            
            return score.fillna(50)
            
        except Exception as e:
            logger.error(f"Erro ao normalizar volume score: {e}")
            return pd.Series([50] * len(serie), index=serie.index)
    
    def _normalizar_volatilidade_score(self, serie: pd.Series) -> pd.Series:
        """Normaliza score de volatilidade negativa (menor é melhor)"""
        try:
            # Clampar entre 0 e 50 (volatilidade %)
            serie_clamp = serie.clip(0, 50)
            
            # Inverter: menor volatilidade = maior score
            score = (50 - serie_clamp) / 50 * 100
            
            return score.fillna(100)  # Se não há vol negativa, é bom
            
        except Exception as e:
            logger.error(f"Erro ao normalizar volatilidade score: {e}")
            return pd.Series([100] * len(serie), index=serie.index)
    
    def _classificar_momentum(self, score: float) -> str:
        """Classifica momentum baseado no score"""
        try:
            if score >= 80:
                return 'MOMENTUM_MUITO_FORTE'
            elif score >= 65:
                return 'MOMENTUM_FORTE'
            elif score >= 45:
                return 'MOMENTUM_MODERADO'
            elif score >= 25:
                return 'MOMENTUM_FRACO'
            else:
                return 'MOMENTUM_MUITO_FRACO'
                
        except Exception as e:
            logger.error(f"Erro ao classificar momentum: {e}")
            return 'MOMENTUM_INDEFINIDO'
    
    def analisar_acao_momentum(self, ticker: str, nome: str, setor: str, periodo_dias: int = 365) -> Dict:
        """Análise completa de momentum para uma ação"""
        try:
            logger.info(f"Iniciando análise momentum para {ticker}")
            
            # Obter dados históricos
            df = self.obter_dados_acao(ticker, periodo_dias)
            if df.empty:
                return {
                    'success': False,
                    'error': f'Dados insuficientes para {ticker}'
                }
            
            # Calcular indicadores
            df = self.calcular_indicadores_momentum(df)
            
            if df.empty:
                return {
                    'success': False,
                    'error': f'Erro ao calcular indicadores para {ticker}'
                }
            
            # Calcular momentum score
            df = self.calcular_momentum_score(df)
            
            # Dados mais recentes
            ultimo_registro = df.iloc[-1]
            
            # Métricas atuais
            preco_atual = float(ultimo_registro['Close'])
            momentum_score = float(ultimo_registro['momentum_score'])
            classificacao = ultimo_registro['momentum_classificacao']
            
            # ROCs atuais
            roc_1m = float(ultimo_registro['roc_1m'])
            roc_3m = float(ultimo_registro['roc_3m'])
            roc_6m = float(ultimo_registro['roc_6m'])
            
            # Métricas auxiliares
            acima_sma50 = bool(ultimo_registro['acima_sma50'])
            sma_50_atual = float(ultimo_registro['sma_50'])
            vol_negativa = float(ultimo_registro['vol_negativa'])
            aceleracao_volume = float(ultimo_registro['aceleracao_volume'])
            
            # Tendência do momentum (últimos 10 dias)
            tendencia_momentum = self._calcular_tendencia_momentum(df['momentum_score'].tail(10))
            
            # Performance recente adicional
            preco_7d = float(df.iloc[-7]['Close']) if len(df) >= 7 else preco_atual
            retorno_7d = ((preco_atual - preco_7d) / preco_7d * 100) if preco_7d > 0 else 0
            
            # Estatísticas do período
            df_recente = df.tail(252)  # Último ano
            momentum_medio = float(df_recente['momentum_score'].mean())
            momentum_max = float(df_recente['momentum_score'].max())
            momentum_min = float(df_recente['momentum_score'].min())
            
            # Dias acima/abaixo da SMA 50
            dias_acima_sma = int(df_recente['acima_sma50'].sum())
            percentual_acima_sma = float(dias_acima_sma / len(df_recente) * 100)
            
            # Preparar dados para gráficos
            chart_data = self._preparar_dados_graficos(df.tail(252), ticker)
            
            resultado = {
                'success': True,
                'ticker': ticker,
                'nome': nome,
                'setor': setor,
                'periodo_dias': periodo_dias,
                
                # Dados atuais
                'preco_atual': preco_atual,
                'momentum_score': momentum_score,
                'classificacao': classificacao,
                'sma_50': sma_50_atual,
                'acima_sma50': acima_sma50,
                
                # ROCs (Rate of Change)
                'roc_1m': roc_1m,
                'roc_3m': roc_3m,
                'roc_6m': roc_6m,
                'retorno_7d': float(retorno_7d),
                
                # Métricas auxiliares
                'volatilidade_negativa': vol_negativa,
                'aceleracao_volume': aceleracao_volume,
                'tendencia_momentum': tendencia_momentum,
                
                # Estatísticas do período
                'momentum_medio_periodo': momentum_medio,
                'momentum_max_periodo': momentum_max,
                'momentum_min_periodo': momentum_min,
                'dias_acima_sma50': dias_acima_sma,
                'percentual_acima_sma50': percentual_acima_sma,
                
                # Dados para gráficos
                'chart_data': chart_data,
                
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"Análise momentum concluída para {ticker}: {classificacao} (Score: {momentum_score:.1f})")
            return resultado
            
        except Exception as e:
            logger.error(f"Erro na análise momentum de {ticker}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _calcular_tendencia_momentum(self, serie_momentum) -> str:
        """Calcula tendência do momentum"""
        try:
            if len(serie_momentum) < 5:
                return 'INDEFINIDA'
            
            # Últimos 5 valores
            ultimos = serie_momentum.tail(5).values
            if np.isnan(ultimos).any():
                return 'INDEFINIDA'
            
            # Calcular coeficiente angular
            x = np.arange(len(ultimos))
            coef = np.polyfit(x, ultimos, 1)[0]
            
            if coef > 2:
                return 'ACELERANDO_FORTE'
            elif coef > 0.5:
                return 'ACELERANDO'
            elif coef > -0.5:
                return 'ESTAVEL'
            elif coef > -2:
                return 'DESACELERANDO'
            else:
                return 'DESACELERANDO_FORTE'
                
        except Exception as e:
            logger.error(f"Erro ao calcular tendência momentum: {e}")
            return 'ERRO'
    
    def _preparar_dados_graficos(self, df: pd.DataFrame, ticker: str) -> Dict:
        """Prepara dados para gráficos do frontend"""
        try:
            # Filtrar dados válidos
            df_clean = df.dropna(subset=['momentum_score', 'roc_1m', 'roc_3m', 'roc_6m'])
            
            if df_clean.empty:
                return {'error': 'Dados insuficientes para gráficos'}
            
            chart_data = {
                # Gráfico principal: Preço + SMA + Score
                'preco_momentum': {
                    'dates': df_clean.index.strftime('%Y-%m-%d').tolist(),
                    'precos': df_clean['Close'].tolist(),
                    'sma_50': df_clean['sma_50'].tolist(),
                    'momentum_score': df_clean['momentum_score'].tolist()
                },
                
                # Gráfico ROCs
                'rocs': {
                    'dates': df_clean.index.strftime('%Y-%m-%d').tolist(),
                    'roc_1m': df_clean['roc_1m'].tolist(),
                    'roc_3m': df_clean['roc_3m'].tolist(),
                    'roc_6m': df_clean['roc_6m'].tolist()
                },
                
                # Gráfico Volume
                'volume': {
                    'dates': df_clean.index.strftime('%Y-%m-%d').tolist(),
                    'volume': df_clean['Volume'].tolist(),
                    'aceleracao': df_clean['aceleracao_volume'].tolist()
                },
                
                # Distribuição do Momentum Score
                'momentum_distribution': {
                    'values': df_clean['momentum_score'].tolist(),
                    'bins': 20
                },
                
                # Estatísticas
                'stats': {
                    'momentum_atual': float(df_clean['momentum_score'].iloc[-1]),
                    'momentum_medio': float(df_clean['momentum_score'].mean()),
                    'melhor_momentum': float(df_clean['momentum_score'].max()),
                    'pior_momentum': float(df_clean['momentum_score'].min()),
                    'dias_forte_momentum': int((df_clean['momentum_score'] >= 65).sum()),
                    'dias_fraco_momentum': int((df_clean['momentum_score'] <= 25).sum())
                }
            }
            
            return chart_data
            
        except Exception as e:
            logger.error(f"Erro ao preparar dados para gráficos: {e}")
            return {'error': str(e)}
    
    def obter_ranking_momentum(self, limite: int = 50) -> List[Dict]:
        """Obtém ranking das ações com melhor momentum"""
        try:
            logger.info(f"Gerando ranking Momentum US (top {limite})")
            
            empresas = self.obter_top_50_empresas_eua()
            ranking = []
            
            for i, empresa in enumerate(empresas):
                try:
                    logger.info(f"Analisando {empresa['ticker']} ({i+1}/{len(empresas)})")
                    
                    resultado = self.analisar_acao_momentum(
                        empresa['ticker'], 
                        empresa['nome'], 
                        empresa['setor']
                    )
                    
                    if resultado['success']:
                        ranking.append({
                            'posicao': 0,  # Será definido após ordenação
                            'ticker': resultado['ticker'],
                            'nome': resultado['nome'],
                            'setor': resultado['setor'],
                            'preco_atual': resultado['preco_atual'],
                            'momentum_score': resultado['momentum_score'],
                            'classificacao': resultado['classificacao'],
                            'roc_1m': resultado['roc_1m'],
                            'roc_3m': resultado['roc_3m'],
                            'roc_6m': resultado['roc_6m'],
                            'retorno_7d': resultado['retorno_7d'],
                            'acima_sma50': resultado['acima_sma50'],
                            'aceleracao_volume': resultado['aceleracao_volume'],
                            'tendencia_momentum': resultado['tendencia_momentum']
                        })
                    
                except Exception as e:
                    logger.warning(f"Erro ao analisar {empresa['ticker']}: {e}")
                    continue
            
            # Ordenar por momentum score (decrescente)
            ranking.sort(key=lambda x: x['momentum_score'], reverse=True)
            
            # Definir posições
            for i, item in enumerate(ranking):
                item['posicao'] = i + 1
            
            # Limitar ao top solicitado
            ranking = ranking[:limite]
            
            logger.info(f"Ranking Momentum US gerado com {len(ranking)} ações")
            return ranking
            
        except Exception as e:
            logger.error(f"Erro ao gerar ranking Momentum: {e}")
            return []
    
    def obter_estatisticas_momentum(self) -> Dict:
        """Obtém estatísticas gerais do Momentum US"""
        try:
            empresas = self.obter_top_50_empresas_eua()
            
            # Contar por setor
            setores = {}
            for empresa in empresas:
                setor = empresa['setor']
                setores[setor] = setores.get(setor, 0) + 1
            
            return {
                'total_empresas_analisadas': len(empresas),
                'distribuicao_setores': setores,
                'parametros': {
                    'roc_1mes': self.roc_1mes,
                    'roc_3meses': self.roc_3meses,
                    'roc_6meses': self.roc_6meses,
                    'sma_filtro': self.sma_filtro,
                    'pesos': self.pesos
                },
                'classificacoes': {
                    'MOMENTUM_MUITO_FORTE': '≥ 80 pontos',
                    'MOMENTUM_FORTE': '65-79 pontos',
                    'MOMENTUM_MODERADO': '45-64 pontos',
                    'MOMENTUM_FRACO': '25-44 pontos',
                    'MOMENTUM_MUITO_FRACO': '< 25 pontos'
                },
                'metodologia': 'Score composto: ROC 1M/3M/6M + Volume + Volatilidade Negativa + Filtro SMA50',
                'periodo_analise': f'{self.periodo_padrao} dias',
                'mercado': 'Estados Unidos',
                'ultima_atualizacao': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas momentum: {e}")
            return {
                'total_empresas_analisadas': 0,
                'erro': str(e)
            }


# Instância global do serviço
momentum_service = MomentumService()
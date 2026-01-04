# golden_cross_eua_service.py - Serviço do Golden Cross EUA (SEM biblioteca ta)

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class GoldenCrossEUAService:
    """Serviço para análise de Golden Cross das 50 maiores empresas americanas"""
    
    def __init__(self):
        self.periodo_padrao = 365  # 1 ano de dados
        self.sma_curta = 50
        self.sma_longa = 200
        self.rsi_periodo = 14
        self.rsi_sobrecompra = 70
        self.rsi_sobrevenda = 30
        
    def obter_top_50_empresas_eua(self) -> List[Dict]:
        """Obtém lista das 50 maiores empresas americanas por setor"""
        
        #  TOP 50 EMPRESAS AMERICANAS POR SETOR
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
        
        # Retornar apenas as primeiras 50
        return empresas_completas[:50]
    
    def obter_dados_acao(self, ticker: str, periodo_dias: int = 365) -> pd.DataFrame:
        """Obtém dados históricos de uma ação americana"""
        try:
            to_date = datetime.now()
            from_date = to_date - timedelta(days=periodo_dias + 100)  # Margem para cálculo das SMAs
            
            logger.info(f"Obtendo dados de {ticker}")
            
            stock = yf.Ticker(ticker)
            hist = stock.history(start=from_date, end=to_date)
            
            if hist.empty:
                logger.warning(f"Nenhum dado encontrado para {ticker}")
                return pd.DataFrame()
            
            # Limpar dados
            hist = hist.dropna()
            
            if len(hist) < 250:  # Precisa de pelo menos 250 dias para SMA 200
                logger.warning(f"Dados insuficientes para {ticker}: {len(hist)} dias")
                return pd.DataFrame()
            
            logger.info(f"Dados obtidos para {ticker}: {len(hist)} registros")
            return hist
            
        except Exception as e:
            logger.error(f"Erro ao obter dados de {ticker}: {e}")
            return pd.DataFrame()
    
    def calcular_rsi(self, precos: pd.Series, periodo: int = 14) -> pd.Series:
        """Calcula RSI manualmente sem bibliotecas externas"""
        try:
            if len(precos) < periodo + 1:
                return pd.Series([np.nan] * len(precos), index=precos.index)
            
            # Calcular diferenças diárias
            delta = precos.diff()
            
            # Separar ganhos e perdas
            ganhos = delta.where(delta > 0, 0)
            perdas = -delta.where(delta < 0, 0)
            
            # Calcular médias móveis dos ganhos e perdas
            # Para o primeiro cálculo, usar média simples
            avg_ganho = ganhos.rolling(window=periodo).mean()
            avg_perda = perdas.rolling(window=periodo).mean()
            
            # Calcular RS (Relative Strength)
            rs = avg_ganho / avg_perda
            
            # Calcular RSI
            rsi = 100 - (100 / (1 + rs))
            
            # Substituir valores inválidos
            rsi = rsi.fillna(50)  # Valor neutro para NaN
            rsi = rsi.replace([np.inf, -np.inf], 50)
            
            return rsi
            
        except Exception as e:
            logger.error(f"Erro ao calcular RSI: {e}")
            return pd.Series([50] * len(precos), index=precos.index)
    
    def calcular_sma(self, precos: pd.Series, periodo: int) -> pd.Series:
        """Calcula Média Móvel Simples"""
        try:
            return precos.rolling(window=periodo).mean()
        except Exception as e:
            logger.error(f"Erro ao calcular SMA {periodo}: {e}")
            return pd.Series([np.nan] * len(precos), index=precos.index)
    
    def calcular_indicadores_tecnicos(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula indicadores técnicos (SMA 50, SMA 200, RSI)"""
        try:
            if df.empty or len(df) < 250:
                logger.warning("Dados insuficientes para calcular indicadores")
                return df
            
            # Médias Móveis Simples
            df['sma_50'] = self.calcular_sma(df['Close'], self.sma_curta)
            df['sma_200'] = self.calcular_sma(df['Close'], self.sma_longa)
            
            # RSI
            df['rsi'] = self.calcular_rsi(df['Close'], self.rsi_periodo)
            
            # Remover NaN das SMAs
            df = df.dropna(subset=['sma_50', 'sma_200'])
            
            if df.empty:
                logger.warning("DataFrame vazio após remover NaN")
                return df
            
            # Golden Cross básico (SMA 50 > SMA 200)
            df['golden_cross'] = (df['sma_50'] > df['sma_200']).astype(int)
            
            # Detectar cruzamento (mudança de 0 para 1)
            df['golden_cross_signal'] = ((df['golden_cross'] == 1) & 
                                       (df['golden_cross'].shift(1) == 0)).astype(int)
            
            # Death Cross (oposto do Golden Cross)
            df['death_cross'] = (df['sma_50'] < df['sma_200']).astype(int)
            df['death_cross_signal'] = ((df['death_cross'] == 1) & 
                                      (df['death_cross'].shift(1) == 0)).astype(int)
            
            # Filtros RSI
            df['rsi_ok'] = df['rsi'] < self.rsi_sobrecompra  # Evitar sobrecompra
            df['rsi_oversold'] = df['rsi'] < self.rsi_sobrevenda  # Identificar sobrevenda
            
            # Golden Cross validado com RSI
            df['golden_cross_validado'] = (df['golden_cross'] == 1) & df['rsi_ok']
            df['golden_cross_signal_validado'] = (df['golden_cross_signal'] == 1) & df['rsi_ok']
            
            logger.info("Indicadores técnicos calculados com sucesso")
            return df
            
        except Exception as e:
            logger.error(f"Erro ao calcular indicadores técnicos: {e}")
            return df
    
    def analisar_acao_golden_cross(self, ticker: str, nome: str, setor: str, periodo_dias: int = 365) -> Dict:
        """Análise completa de Golden Cross para uma ação"""
        try:
            logger.info(f"Iniciando análise Golden Cross para {ticker}")
            
            # Obter dados históricos
            df = self.obter_dados_acao(ticker, periodo_dias)
            if df.empty:
                return {
                    'success': False,
                    'error': f'Dados insuficientes para {ticker}'
                }
            
            # Calcular indicadores
            df = self.calcular_indicadores_tecnicos(df)
            
            if df.empty:
                return {
                    'success': False,
                    'error': f'Erro ao calcular indicadores para {ticker}'
                }
            
            # Dados mais recentes
            ultimo_registro = df.iloc[-1]
            
            # Status atual
            status_atual = self._definir_status_golden_cross(ultimo_registro)
            
            # Estatísticas dos últimos 252 dias (1 ano)
            df_recente = df.tail(252)
            
            # Contar sinais
            total_golden_signals = int(df_recente['golden_cross_signal'].sum())
            total_golden_validados = int(df_recente['golden_cross_signal_validado'].sum())
            total_death_signals = int(df_recente['death_cross_signal'].sum())
            
            # Dias em Golden Cross
            dias_golden = int(df_recente['golden_cross'].sum())
            dias_death = int(df_recente['death_cross'].sum())
            
            # Performance recente
            preco_atual = float(ultimo_registro['Close'])
            preco_30d = float(df.iloc[-30]['Close']) if len(df) >= 30 else preco_atual
            preco_90d = float(df.iloc[-90]['Close']) if len(df) >= 90 else preco_atual
            
            retorno_30d = ((preco_atual - preco_30d) / preco_30d * 100) if preco_30d > 0 else 0
            retorno_90d = ((preco_atual - preco_90d) / preco_90d * 100) if preco_90d > 0 else 0
            
            # Distância das médias
            sma_50_atual = float(ultimo_registro['sma_50'])
            sma_200_atual = float(ultimo_registro['sma_200'])
            
            distancia_sma50 = ((preco_atual - sma_50_atual) / sma_50_atual * 100) if sma_50_atual > 0 else 0
            distancia_sma200 = ((preco_atual - sma_200_atual) / sma_200_atual * 100) if sma_200_atual > 0 else 0
            
            # RSI atual
            rsi_atual = float(ultimo_registro['rsi'])
            
            # Tendência das médias
            tendencia_sma50 = self._calcular_tendencia_media(df['sma_50'].tail(10))
            tendencia_sma200 = self._calcular_tendencia_media(df['sma_200'].tail(10))
            
            # Força do Golden Cross (diferença entre as médias)
            forca_golden = ((sma_50_atual - sma_200_atual) / sma_200_atual * 100) if sma_200_atual > 0 else 0
            
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
                'sma_50': sma_50_atual,
                'sma_200': sma_200_atual,
                'rsi': rsi_atual,
                'status_atual': status_atual,
                
                # Sinais e estatísticas
                'total_golden_signals': total_golden_signals,
                'total_golden_validados': total_golden_validados,
                'total_death_signals': total_death_signals,
                'dias_golden_cross': dias_golden,
                'dias_death_cross': dias_death,
                'percentual_tempo_golden': float(dias_golden / len(df_recente) * 100),
                
                # Performance
                'retorno_30d': float(retorno_30d),
                'retorno_90d': float(retorno_90d),
                'distancia_sma50': float(distancia_sma50),
                'distancia_sma200': float(distancia_sma200),
                
                # Análise técnica
                'tendencia_sma50': tendencia_sma50,
                'tendencia_sma200': tendencia_sma200,
                'forca_golden_cross': float(forca_golden),
                
                # Validações RSI
                'rsi_ok': bool(ultimo_registro['rsi_ok']),
                'rsi_oversold': bool(ultimo_registro['rsi_oversold']),
                'golden_cross_validado': bool(ultimo_registro['golden_cross_validado']),
                
                # Dados para gráficos
                'chart_data': chart_data,
                
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"Análise Golden Cross concluída para {ticker}: {status_atual}")
            return resultado
            
        except Exception as e:
            logger.error(f"Erro na análise Golden Cross de {ticker}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _definir_status_golden_cross(self, registro) -> str:
        """Define o status atual do Golden Cross"""
        try:
            golden_cross = registro['golden_cross'] == 1
            rsi_ok = registro['rsi_ok']
            rsi_oversold = registro['rsi_oversold']
            
            if golden_cross and rsi_ok:
                return 'GOLDEN_CROSS_ATIVO'
            elif golden_cross and not rsi_ok:
                return 'GOLDEN_CROSS_SOBRECOMPRA'
            elif not golden_cross and rsi_oversold:
                return 'DEATH_CROSS_SOBREVENDA'
            elif not golden_cross:
                return 'DEATH_CROSS_ATIVO'
            else:
                return 'NEUTRO'
                
        except Exception as e:
            logger.error(f"Erro ao definir status: {e}")
            return 'ERRO'
    
    def _calcular_tendencia_media(self, serie_media) -> str:
        """Calcula tendência de uma média móvel"""
        try:
            if len(serie_media) < 5:
                return 'INDEFINIDA'
            
            # Comparar últimos 5 valores
            ultimos = serie_media.tail(5).values
            if np.isnan(ultimos).any():
                return 'INDEFINIDA'
            
            # Calcular coeficiente angular
            x = np.arange(len(ultimos))
            coef = np.polyfit(x, ultimos, 1)[0]
            
            if coef > 0.5:
                return 'ALTA_FORTE'
            elif coef > 0.1:
                return 'ALTA'
            elif coef > -0.1:
                return 'LATERAL'
            elif coef > -0.5:
                return 'BAIXA'
            else:
                return 'BAIXA_FORTE'
                
        except Exception as e:
            logger.error(f"Erro ao calcular tendência: {e}")
            return 'ERRO'
    
    def _preparar_dados_graficos(self, df: pd.DataFrame, ticker: str) -> Dict:
        """Prepara dados para gráficos do frontend"""
        try:
            # Filtrar dados válidos (não NaN)
            df_clean = df.dropna(subset=['sma_50', 'sma_200', 'rsi'])
            
            if df_clean.empty:
                return {'error': 'Dados insuficientes para gráficos'}
            
            # Identificar sinais
            golden_signals = df_clean[df_clean['golden_cross_signal'] == 1]
            death_signals = df_clean[df_clean['death_cross_signal'] == 1]
            
            chart_data = {
                # Gráfico principal: Preço + SMAs
                'preco_smas': {
                    'dates': df_clean.index.strftime('%Y-%m-%d').tolist(),
                    'precos': df_clean['Close'].tolist(),
                    'sma_50': df_clean['sma_50'].tolist(),
                    'sma_200': df_clean['sma_200'].tolist(),
                    'golden_signals': {
                        'dates': golden_signals.index.strftime('%Y-%m-%d').tolist(),
                        'values': golden_signals['Close'].tolist()
                    },
                    'death_signals': {
                        'dates': death_signals.index.strftime('%Y-%m-%d').tolist(),
                        'values': death_signals['Close'].tolist()
                    }
                },
                
                # Gráfico RSI
                'rsi': {
                    'dates': df_clean.index.strftime('%Y-%m-%d').tolist(),
                    'values': df_clean['rsi'].tolist(),
                    'sobrecompra': self.rsi_sobrecompra,
                    'sobrevenda': self.rsi_sobrevenda
                },
                
                # Histograma de distribuição RSI
                'rsi_distribution': {
                    'values': df_clean['rsi'].tolist(),
                    'bins': 20
                },
                
                # Estatísticas dos cruzamentos
                'cross_stats': {
                    'total_golden': int(df_clean['golden_cross_signal'].sum()),
                    'total_death': int(df_clean['death_cross_signal'].sum()),
                    'golden_validados': int(df_clean['golden_cross_signal_validado'].sum()),
                    'dias_golden': int(df_clean['golden_cross'].sum()),
                    'dias_death': int(df_clean['death_cross'].sum())
                }
            }
            
            return chart_data
            
        except Exception as e:
            logger.error(f"Erro ao preparar dados para gráficos: {e}")
            return {'error': str(e)}
    
    def obter_ranking_golden_cross(self, limite: int = 50) -> List[Dict]:
        """Obtém ranking das ações com melhor setup de Golden Cross"""
        try:
            logger.info(f"Gerando ranking Golden Cross EUA (top {limite})")
            
            empresas = self.obter_top_50_empresas_eua()
            ranking = []
            
            for i, empresa in enumerate(empresas):
                try:
                    logger.info(f"Analisando {empresa['ticker']} ({i+1}/{len(empresas)})")
                    
                    resultado = self.analisar_acao_golden_cross(
                        empresa['ticker'], 
                        empresa['nome'], 
                        empresa['setor']
                    )
                    
                    if resultado['success']:
                        # Calcular score de qualidade do Golden Cross
                        score = self._calcular_score_golden_cross(resultado)
                        
                        ranking.append({
                            'posicao': 0,  # Será definido após ordenação
                            'ticker': resultado['ticker'],
                            'nome': resultado['nome'],
                            'setor': resultado['setor'],
                            'preco_atual': resultado['preco_atual'],
                            'status_atual': resultado['status_atual'],
                            'rsi': resultado['rsi'],
                            'forca_golden_cross': resultado['forca_golden_cross'],
                            'retorno_30d': resultado['retorno_30d'],
                            'retorno_90d': resultado['retorno_90d'],
                            'total_golden_validados': resultado['total_golden_validados'],
                            'percentual_tempo_golden': resultado['percentual_tempo_golden'],
                            'score': score
                        })
                    
                except Exception as e:
                    logger.warning(f"Erro ao analisar {empresa['ticker']}: {e}")
                    continue
            
            # Ordenar por score (decrescente)
            ranking.sort(key=lambda x: x['score'], reverse=True)
            
            # Definir posições
            for i, item in enumerate(ranking):
                item['posicao'] = i + 1
            
            # Limitar ao top solicitado
            ranking = ranking[:limite]
            
            logger.info(f"Ranking Golden Cross EUA gerado com {len(ranking)} ações")
            return ranking
            
        except Exception as e:
            logger.error(f"Erro ao gerar ranking Golden Cross: {e}")
            return []
    
    def _calcular_score_golden_cross(self, dados: Dict) -> float:
        """Calcula score de qualidade do Golden Cross"""
        try:
            score = 0.0
            
            # Peso para Golden Cross ativo (30%)
            if dados['status_atual'] == 'GOLDEN_CROSS_ATIVO':
                score += 30
            elif dados['status_atual'] == 'GOLDEN_CROSS_SOBRECOMPRA':
                score += 15  # Menos pontos por estar sobrecomprado
            
            # Peso para força do Golden Cross (25%)
            forca = dados['forca_golden_cross']
            if forca > 5:
                score += 25
            elif forca > 2:
                score += 20
            elif forca > 0:
                score += 15
            
            # Peso para RSI (20%)
            rsi = dados['rsi']
            if 30 <= rsi <= 70:  # Zona neutra/ideal
                score += 20
            elif 20 <= rsi <= 80:  # Aceitável
                score += 15
            elif rsi < 30:  # Sobrevenda pode ser oportunidade
                score += 10
            # RSI > 80 não ganha pontos (sobrecompra)
            
            # Peso para performance recente (15%)
            ret_30d = dados['retorno_30d']
            if ret_30d > 5:
                score += 15
            elif ret_30d > 0:
                score += 10
            elif ret_30d > -5:
                score += 5
            
            # Peso para consistência (10%)
            validados = dados['total_golden_validados']
            tempo_golden = dados['percentual_tempo_golden']
            if validados >= 2 and tempo_golden > 30:
                score += 10
            elif validados >= 1 or tempo_golden > 20:
                score += 5
            
            return round(score, 2)
            
        except Exception as e:
            logger.error(f"Erro ao calcular score: {e}")
            return 0.0
    
    def obter_estatisticas_golden_cross(self) -> Dict:
        """Obtém estatísticas gerais do Golden Cross EUA"""
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
                    'sma_curta': self.sma_curta,
                    'sma_longa': self.sma_longa,
                    'rsi_periodo': self.rsi_periodo,
                    'rsi_sobrecompra': self.rsi_sobrecompra,
                    'rsi_sobrevenda': self.rsi_sobrevenda
                },
                'metodologia': 'Golden Cross = SMA 50 > SMA 200 + Filtro RSI < 70 (manual)',
                'periodo_analise': f'{self.periodo_padrao} dias',
                'mercado': 'Estados Unidos',
                'ultima_atualizacao': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            return {
                'total_empresas_analisadas': 0,
                'erro': str(e)
            }


# Instância global do serviço
golden_cross_eua_service = GoldenCrossEUAService()
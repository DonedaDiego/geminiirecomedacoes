import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from statsmodels.tsa.stattools import adfuller, coint
from statsmodels.regression.linear_model import OLS
from statsmodels.regression.rolling import RollingOLS
import logging
import json
import warnings
warnings.filterwarnings('ignore')

class LongShortService:
    """Serviço completo para análise de pares Long & Short por cointegração"""
    
    def __init__(self):
        self.top_50_acoes = [
            "ABEV3", "ALOS3", "ALUP3", "ALUP4", "AURE3", "AZZA3", "B3SA3", "BBAS3", 
            "BBDC3", "BBDC4", "BBSE3", "BPAC11", "BPAN4", "BRAP3", "BRAP4", "BRAV3", 
            "BRFS3", "CMIG3", "CMIG4", "CMIN3", "CPFE3", "CPLE3", "CPLE5", 
            "CPLE6", "CRFB3", "CSAN3", "CSMG3", "CSNA3", "CXSE3", "CYRE3", "ELET3", 
            "ELET6", "EGIE3", "EMBR3", "ENEV3", "ENGI11", "ENGI3", "ENGI4", "EQTL3", 
            "GGBR3", "GGBR4", "GOAU4", "HAPV3", "HYPE3", "ITSA3", "ITSA4", "ITUB3", 
            "ITUB4", "JBSS3", "KLBN11", "KLBN3", "KLBN4", "LREN3", "MDIA3", "NEOE3", 
            "NTCO3", "PETR3", "PETR4", "PRIO3", "PSSA3", "RAIL3", "RAIZ4", "RDOR3", 
            "RENT3", "SANB11", "SANB4", "SBSP3", "SUZB3", "VBBR3", "VALE3", "VIVT3", 
            "WEGE3", "UGPA3"
        ]
        
        self.setores = {
            "ABEV3": "Bebidas", "ALOS3": "Exploração de Imóveis", "ALUP3": "Energia Elétrica",
            "ALUP4": "Energia Elétrica", "AURE3": "Energia Elétrica", "AZZA3": "Comércio Varejista",
            "B3SA3": "Serviços Financeiros", "BBAS3": "Intermediários Financeiros", 
            "BBDC3": "Intermediários Financeiros", "BBDC4": "Intermediários Financeiros",
            "BBSE3": "Previdência e Seguros", "BPAC11": "Intermediários Financeiros",
            "BPAN4": "Intermediários Financeiros", "BRAP3": "Mineração", "BRAP4": "Mineração",
            "BRAV3": "Petróleo, Gás e Biocombustíveis", "BRFS3": "Alimentos Processados",
            "CMIN3": "Mineração", "CPFE3": "Energia Elétrica", "CPLE3": "Energia Elétrica",
            "CPLE5": "Energia Elétrica", "CPLE6": "Energia Elétrica", "CRFB3": "Comércio e Distribuição",
            "CSAN3": "Petróleo, Gás e Biocombustíveis", "CSMG3": "Água e Saneamento",
            "CSNA3": "Siderurgia e Metalurgia", "CXSE3": "Previdência e Seguros",
            "CYRE3": "Construção Civil", "ELET3": "Energia Elétrica", "ELET6": "Energia Elétrica",
            "EGIE3": "Energia Elétrica", "EMBR3": "Material de Transporte", "ENEV3": "Energia Elétrica",
            "ENGI11": "Energia Elétrica", "ENGI3": "Energia Elétrica", "ENGI4": "Energia Elétrica",
            "EQTL3": "Energia Elétrica", "GGBR3": "Siderurgia e Metalurgia",
            "GGBR4": "Siderurgia e Metalurgia", "GOAU4": "Siderurgia e Metalurgia",
            "HAPV3": "Serviços Médicos", "HYPE3": "Comércio e Distribuição",
            "ITSA3": "Holdings Diversificadas", "ITSA4": "Holdings Diversificadas",
            "ITUB3": "Intermediários Financeiros", "ITUB4": "Intermediários Financeiros",
            "JBSS3": "Alimentos Processados", "KLBN11": "Madeira e Papel", "KLBN3": "Madeira e Papel",
            "KLBN4": "Madeira e Papel", "LREN3": "Comércio Varejista", "MDIA3": "Alimentos Processados",
            "NEOE3": "Energia Elétrica", "NTCO3": "Produtos de Cuidado Pessoal",
            "PETR3": "Petróleo, Gás e Biocombustíveis", "PETR4": "Petróleo, Gás e Biocombustíveis",
            "PRIO3": "Petróleo, Gás e Biocombustíveis", "PSSA3": "Previdência e Seguros",
            "RAIL3": "Transporte", "RAIZ4": "Petróleo, Gás e Biocombustíveis",
            "RDOR3": "Serviços Médicos", "RENT3": "Diversos", "SANB11": "Intermediários Financeiros",
            "SANB4": "Intermediários Financeiros", "SBSP3": "Água e Saneamento",
            "SUZB3": "Madeira e Papel", "VBBR3": "Petróleo, Gás e Biocombustíveis",
            "VALE3": "Mineração", "VIVT3": "Telecomunicações", "WEGE3": "Máquinas e Equipamentos",
            "UGPA3": "Petróleo, Gás e Biocombustíveis"
        }

    def obter_dados(self, tickers, data_inicio, data_fim):
        """Obter dados históricos para múltiplas ações"""
        try:
            print(f"📊 Obtendo dados para {len(tickers)} ações de {data_inicio} até {data_fim}")
            
            tuples = []
            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                for ticker in tickers:
                    tuples.append((col, ticker))
            columns = pd.MultiIndex.from_tuples(tuples)
            dados_final = pd.DataFrame(columns=columns)
            
            all_dates = set()
            ticker_data = {}
            
            for ticker in tickers:
                try:
                    yf_ticker = ticker + '.SA'
                    data = yf.download(yf_ticker, start=data_inicio, end=data_fim, progress=False)
                    
                    if not data.empty:
                        ticker_data[ticker] = data
                        all_dates.update(data.index)
                        print(f"✅ {ticker}: {len(data)} registros")
                    else:
                        print(f"⚠️ {ticker}: Sem dados")
                except Exception as e:
                    print(f"❌ Erro ao obter {ticker}: {str(e)}")
                    continue
            
            if not ticker_data:
                print("❌ Nenhum dado foi obtido")
                return pd.DataFrame()
                
            dados_final = pd.DataFrame(index=sorted(all_dates), columns=columns)
            
            for ticker, df in ticker_data.items():
                dados_final[('Open', ticker)] = df['Open']
                dados_final[('High', ticker)] = df['High']
                dados_final[('Low', ticker)] = df['Low']
                dados_final[('Close', ticker)] = df['Close']
                dados_final[('Volume', ticker)] = df['Volume']
            
            dados_final = dados_final.ffill().bfill().infer_objects(copy=False)
            print(f"📈 Dados finais: {dados_final.shape} ({len(dados_final)} dias, {dados_final.shape[1]} colunas)")
            return dados_final
            
        except Exception as e:
            print(f"❌ Erro ao obter dados: {str(e)}")
            return pd.DataFrame()

    def processar_cache_para_estabilidade(self, dados_cache_json, acao1, acao2):
        """Processar cache JSON específico para análise de estabilidade"""
        try:
            print("🔄 Processando cache para análise de estabilidade...")
            
            # Parse do JSON
            cache_data = json.loads(dados_cache_json)
            
            # Reconstruir DataFrame com estrutura MultiIndex
            df = pd.DataFrame(cache_data['data'], 
                            index=pd.to_datetime(cache_data['index']), 
                            columns=pd.MultiIndex.from_tuples(cache_data['columns']))
            
            # Verificar se as ações existem no cache
            acoes_disponiveis = df['Close'].columns.tolist()
            print(f"📊 Ações no cache: {acoes_disponiveis}")
            
            if acao1 not in acoes_disponiveis or acao2 not in acoes_disponiveis:
                print(f"⚠️ Ações {acao1} e/ou {acao2} não encontradas no cache")
                return None
                
            # Filtrar apenas as colunas necessárias para as duas ações
            colunas_necessarias = []
            for col_type in ['Open', 'High', 'Low', 'Close', 'Volume']:
                if (col_type, acao1) in df.columns:
                    colunas_necessarias.append((col_type, acao1))
                if (col_type, acao2) in df.columns:
                    colunas_necessarias.append((col_type, acao2))
            
            df_filtrado = df[colunas_necessarias].copy()
            
            # Limpar dados
            df_filtrado = df_filtrado.dropna()
            
            print(f"✅ Cache processado: {df_filtrado.shape} - {len(df_filtrado)} dias")
            return df_filtrado
            
        except Exception as e:
            print(f"❌ Erro ao processar cache: {str(e)}")
            return None

    def calcular_meia_vida(self, spread):
        """Calcular meia-vida do spread"""
        try:
            spread_clean = spread.dropna()
            if len(spread_clean) < 10:
                return None
                
            spread_lag = spread_clean.shift(1)
            spread_diff = spread_clean.diff()
            
            # Remover NaNs
            valid_idx = ~(spread_lag.isna() | spread_diff.isna())
            spread_lag = spread_lag[valid_idx]
            spread_diff = spread_diff[valid_idx]
            
            if len(spread_lag) < 5:
                return None
                
            modelo = OLS(spread_diff, spread_lag).fit()
            
            if modelo.params[0] < 0:
                meia_vida = -np.log(2) / modelo.params[0]
                return meia_vida if meia_vida > 0 and meia_vida < 1000 else None
            return None
            
        except Exception as e:
            print(f"❌ Erro no cálculo da meia-vida: {e}")
            return None

    def teste_adf(self, serie_temporal):
        """Teste de Dickey-Fuller Aumentado"""
        try:
            serie_clean = serie_temporal.dropna()
            if len(serie_clean) < 10:
                return 1.0
            return adfuller(serie_clean)[1]
        except:
            return 1.0

    def calcular_zscore(self, spread):
        """Calcular Z-Score do spread"""
        spread_clean = spread.dropna()
        if len(spread_clean) == 0:
            return pd.Series()
        return (spread_clean - spread_clean.mean()) / spread_clean.std()

    def teste_cointegração_robusto(self, serie1, serie2, max_pvalor=0.05):
        """Teste de cointegração mais robusto"""
        try:
            # Limpar dados
            df = pd.DataFrame({'s1': serie1, 's2': serie2}).dropna()
            
            if len(df) < 10:
                return False, 1.0, None, None, None
                
            s1, s2 = df['s1'], df['s2']
            
            # Teste de cointegração
            score, pvalor, _ = coint(s1, s2)
            
            # Modelo de regressão
            modelo = OLS(s1, s2).fit()
            
            # Calcular spread e métricas
            spread = s1 - modelo.params[0] * s2
            meia_vida = self.calcular_meia_vida(spread)
            
            # R²
            r_squared = modelo.rsquared
            
            # Correlação
            correlacao = s1.corr(s2)
            
            # Determinar se é cointegrado
            is_cointegrated = (pvalor <= max_pvalor and 
                             r_squared >= 0.5 and 
                             correlacao >= 0.3 and
                             meia_vida is not None and 
                             1 <= meia_vida <= 100)
            
            return is_cointegrated, pvalor, r_squared, correlacao, meia_vida
            
        except Exception as e:
            print(f"❌ Erro no teste de cointegração: {e}")
            return False, 1.0, None, None, None

    def analisar_estabilidade_par(self, dados_cache_json, acao1, acao2):
        """Análise de estabilidade de cointegração para um par específico - VERSÃO CORRIGIDA"""
        try:
            print(f"🔍 Análise de estabilidade: {acao1} x {acao2}")
            
            # NOVO: Usar o processador específico de cache
            dados = self.processar_cache_para_pares(dados_cache_json, acao1, acao2)
            
            if dados is None or dados.empty:
                print("🔄 Cache inválido, obtendo dados novamente para estabilidade...")
                # Fallback: obter dados diretamente
                data_fim = datetime.now()
                data_inicio = data_fim - timedelta(days=300)  # Período maior para análise
                dados = self.obter_dados([acao1, acao2], data_inicio, data_fim)
                
                if dados.empty:
                    return {
                        'success': False,
                        'error': 'Não foi possível obter dados para análise de estabilidade'
                    }
            
            print(f"📊 Dados para estabilidade: {dados.shape}")
            print(f"📊 Colunas disponíveis: {dados.columns.tolist()}")
            
            # Verificar se temos os dados necessários
            if not isinstance(dados.columns, pd.MultiIndex):
                return {
                    'success': False,
                    'error': 'Estrutura de dados inválida para análise de estabilidade'
                }
            
            if 'Close' not in dados.columns.levels[0]:
                return {
                    'success': False,
                    'error': 'Dados de preços de fechamento não encontrados'
                }
            
            acoes_disponiveis = dados['Close'].columns.tolist()
            if acao1 not in acoes_disponiveis or acao2 not in acoes_disponiveis:
                return {
                    'success': False,
                    'error': f'Ações {acao1} ou {acao2} não encontradas. Disponíveis: {acoes_disponiveis}'
                }
            
            # Períodos para análise
            periodos = [60, 90, 120, 140, 180, 200, 240]
            resultados = []
            
            print("📊 Iniciando análise de estabilidade por períodos...")
            
            for periodo in periodos:
                print(f"🔍 Analisando período de {periodo} dias...")
                
                if len(dados) < periodo:
                    print(f"⚠️ Dados insuficientes para período de {periodo} dias")
                    resultados.append({
                        'periodo': periodo,
                        'status': 'Dados Insuficientes',
                        'pvalor_cointegração': None,
                        'r_squared': None,
                        'correlacao': None,
                        'meia_vida': None
                    })
                    continue
                
                try:
                    # Pegar os últimos N dias
                    dados_periodo = dados.tail(periodo)
                    
                    # Extrair séries de preços
                    serie1 = dados_periodo['Close', acao1].dropna()
                    serie2 = dados_periodo['Close', acao2].dropna()
                    
                    if len(serie1) < 30 or len(serie2) < 30:
                        print(f"⚠️ Dados insuficientes no período {periodo}")
                        resultados.append({
                            'periodo': periodo,
                            'status': 'Dados Insuficientes',
                            'pvalor_cointegração': None,
                            'r_squared': None,
                            'correlacao': None,
                            'meia_vida': None
                        })
                        continue
                    
                    # Teste de cointegração robusto
                    is_cointegrated, pvalor, r_squared, correlacao, meia_vida = self.teste_cointegração_robusto(
                        serie1, serie2
                    )
                    
                    status = 'Cointegrado' if is_cointegrated else 'Não Cointegrado'
                    
                    print(f"✅ Período {periodo} concluído: {status}")
                    if pvalor is not None:
                        print(f"   📊 P-valor: {pvalor:.4f}")
                    if r_squared is not None:
                        print(f"   📊 R²: {r_squared:.4f}")
                    if meia_vida is not None:
                        print(f"   📊 Meia-vida: {meia_vida:.2f} dias")
                    
                    resultados.append({
                        'periodo': periodo,
                        'status': status,
                        'pvalor_cointegração': f"{pvalor:.4f}" if pvalor is not None else None,
                        'r_squared': f"{r_squared:.4f}" if r_squared is not None else None,
                        'correlacao': f"{correlacao:.4f}" if correlacao is not None else None,
                        'meia_vida': f"{meia_vida:.1f}" if meia_vida is not None else None
                    })
                    
                except Exception as e:
                    print(f"❌ Erro no período {periodo}: {e}")
                    resultados.append({
                        'periodo': periodo,
                        'status': 'Erro',
                        'pvalor_cointegração': None,
                        'r_squared': None,
                        'correlacao': None,
                        'meia_vida': None
                    })
            
            # Calcular diagnóstico
            periodos_cointegrados = sum(1 for r in resultados if r['status'] == 'Cointegrado')
            periodos_validos = sum(1 for r in resultados if r['status'] in ['Cointegrado', 'Não Cointegrado'])
            
            # Calcular R² médio dos períodos válidos
            r2_values = [float(r['r_squared']) for r in resultados if r['r_squared'] is not None]
            r2_medio = sum(r2_values) / len(r2_values) if r2_values else 0
            
            # Determinar diagnóstico
            if periodos_cointegrados == 0:
                diagnostico_texto = "Cointegração instável ou ausente"
                diagnostico_icon = "❌"
            elif periodos_cointegrados == periodos_validos:
                diagnostico_texto = "Cointegração estável e robusta"
                diagnostico_icon = "✅"
            elif periodos_cointegrados >= periodos_validos * 0.7:
                diagnostico_texto = "Cointegração majoritariamente estável"
                diagnostico_icon = "⚠️"
            else:
                diagnostico_texto = "Cointegração instável"
                diagnostico_icon = "❌"
            
            print(f"🎯 Diagnóstico final: {diagnostico_texto}")
            print(f"📊 Períodos cointegrados: {periodos_cointegrados}/{periodos_validos}")
            
            return {
                'success': True,
                'data': {
                    'analise_periodos': resultados,
                    'diagnostico': {
                        'texto': diagnostico_texto,
                        'status_icon': diagnostico_icon,
                        'periodos_cointegrados': periodos_cointegrados,
                        'total_periodos': periodos_validos,
                        'r2_medio': f"{r2_medio:.4f}" if r2_medio > 0 else "N/A"
                    }
                }
            }
            
        except Exception as e:
            print(f"❌ Erro na análise de estabilidade: {str(e)}")
            return {
                'success': False,
                'error': f'Erro na análise de estabilidade: {str(e)}'
            }

    def analisar_pares(self, dados, max_meia_vida=30, min_meia_vida=1, 
                      max_pvalor_adf=0.05, min_correlacao=0.5, max_pvalor_coint=0.05):
        """Análise completa de pares para Long & Short"""
        try:
            n = dados['Close'].shape[1]
            resultados = []
            total_pares = 0
            
            print(f"📊 Analisando {n} ações - Total de pares possíveis: {n*(n-1)//2}")
            
            for i in range(n):
                for j in range(i+1, n):
                    total_pares += 1
                    acao1, acao2 = dados['Close'].columns[i], dados['Close'].columns[j]
                    
                    if total_pares % 100 == 0:
                        print(f"📈 Processando par {total_pares}...")
                    
                    try:
                        serie1 = dados['Close'][acao1].dropna()
                        serie2 = dados['Close'][acao2].dropna()
                        
                        if len(serie1) < 30 or len(serie2) < 30:
                            continue
                            
                        # Teste de cointegração
                        is_cointegrated, pvalor, r_squared, correlacao, meia_vida = self.teste_cointegração_robusto(
                            serie1, serie2, max_pvalor_coint
                        )
                        
                        if is_cointegrated and meia_vida is not None:
                            # Modelo para calcular beta
                            modelo = OLS(serie1, serie2).fit()
                            
                            # Teste ADF adicional no spread
                            spread = serie1 - modelo.params[0] * serie2
                            pvalor_adf = self.teste_adf(spread)
                            
                            # Verificar todos os critérios
                            if (min_meia_vida <= meia_vida <= max_meia_vida and 
                                pvalor_adf <= max_pvalor_adf and 
                                correlacao >= min_correlacao):
                                
                                resultados.append({
                                    'acao1': acao1,
                                    'acao2': acao2,
                                    'pvalor_cointegração': pvalor,
                                    'meia_vida': meia_vida,
                                    'pvalor_adf': pvalor_adf,
                                    'correlacao': correlacao,
                                    'beta': float(modelo.params[0]),
                                    'setor1': self.setores.get(acao1, 'N/A'),
                                    'setor2': self.setores.get(acao2, 'N/A')
                                })
                                
                    except Exception as e:
                        continue
            
            print(f"✅ Análise concluída: {len(resultados)} pares válidos de {total_pares} analisados")
            
            return {
                'success': True,
                'data': {
                    'pares': resultados,
                    'total_analisados': total_pares,
                    'pares_validos': len(resultados)
                }
            }
            
        except Exception as e:
            print(f"❌ Erro na análise de pares: {str(e)}")
            return {
                'success': False,
                'error': f'Erro na análise de pares: {str(e)}'
            }

    def filtrar_pares_por_zscore(self, dados, pares, zscore_minimo=2):
        """Filtrar pares com Z-Score significativo"""
        try:
            pares_validos = []
            
            print(f"🔍 Filtrando {len(pares)} pares por Z-Score >= {zscore_minimo}")
            
            for par in pares:
                try:
                    acao1, acao2 = par['acao1'], par['acao2']
                    
                    # Calcular Beta Rotativo
                    beta_rotativo = self.calcular_beta_rotativo(dados, acao1, acao2, 60)
                    
                    if not beta_rotativo.empty:
                        beta_atual = beta_rotativo.iloc[-1]
                        beta_medio = beta_rotativo.mean()
                        desvio_padrao = beta_rotativo.std()
                        
                        distancia_media = abs(beta_atual - beta_medio)
                        if distancia_media <= desvio_padrao:
                            status = 'Favorável'
                        elif distancia_media <= 1.5 * desvio_padrao:
                            status = 'Cautela'
                        else:
                            status = 'Não Recomendado'
                    else:
                        status = 'Indisponível'
                    
                    # Calcular spread e Z-Score
                    serie1 = dados['Close'][acao1]
                    serie2 = dados['Close'][acao2]
                    modelo = OLS(serie1, serie2).fit()
                    spread = serie1 - modelo.params[0] * serie2
                    zscore_serie = self.calcular_zscore(spread)
                    
                    if not zscore_serie.empty:
                        zscore_atual = zscore_serie.iloc[-1]
                        
                        if abs(zscore_atual) >= zscore_minimo:
                            direcao_acao1 = "Venda" if zscore_atual > 0 else "Compra"
                            direcao_acao2 = "Compra" if zscore_atual > 0 else "Venda"
                            
                            par_atualizado = par.copy()
                            par_atualizado.update({
                                'status_beta': status,
                                'zscore_atual': zscore_atual,
                                'direcao_acao1': direcao_acao1,
                                'direcao_acao2': direcao_acao2,
                                'ultimo_preco1': float(dados['Close'][acao1].iloc[-1]),
                                'ultimo_preco2': float(dados['Close'][acao2].iloc[-1])
                            })
                            
                            pares_validos.append(par_atualizado)
                            
                except Exception as e:
                    print(f"❌ Erro ao processar par {par.get('acao1')}-{par.get('acao2')}: {e}")
                    continue
            
            print(f"✅ {len(pares_validos)} pares válidos após filtro Z-Score")
            
            return {
                'success': True,
                'data': pares_validos
            }
            
        except Exception as e:
            print(f"❌ Erro no filtro por Z-Score: {str(e)}")
            return {
                'success': False,
                'error': f'Erro no filtro por Z-Score: {str(e)}'
            }

    def calcular_beta_rotativo(self, dados, acao1, acao2, janela):
        """Calcular Beta Rotativo entre duas ações"""
        try:
            serie1 = dados['Close'][acao1].dropna()
            serie2 = dados['Close'][acao2].dropna()
            
            # Calcular retornos logarítmicos
            log_returns1 = np.log(serie1 / serie1.shift(1)).dropna()
            log_returns2 = np.log(serie2 / serie2.shift(1)).dropna()

            if len(log_returns1) < janela or len(log_returns2) < janela:
                return pd.Series()

            # Alinhar as séries
            df_returns = pd.DataFrame({
                'ret1': log_returns1,
                'ret2': log_returns2
            }).dropna()
            
            if len(df_returns) < janela:
                return pd.Series()

            model = RollingOLS(df_returns['ret1'], df_returns['ret2'], window=janela)
            rolling_res = model.fit()

            return pd.Series(rolling_res.params.iloc[:, 0], index=df_returns.index[janela-1:])
            
        except Exception as e:
            print(f"❌ Erro no cálculo do beta rotativo: {e}")
            return pd.Series()

    def calcular_atr(self, dados, acao, periodo=14):
        """Calcular Average True Range"""
        try:
            high = dados['High'][acao]
            low = dados['Low'][acao]
            close = dados['Close'][acao].shift(1)
            
            tr = pd.DataFrame({
                'hl': high - low,
                'hc': abs(high - close),
                'lc': abs(low - close)
            }).max(axis=1)
            
            return tr.rolling(window=periodo).mean()
        except:
            return pd.Series()

    def analisar_par_detalhado(self, dados, acao1, acao2, investimento=10000):
        """Análise detalhada de um par específico"""
        try:
            print(f"🎯 Análise detalhada: {acao1} x {acao2}")
            
            # Informações básicas
            ultimo_preco1 = float(dados['Close'][acao1].iloc[-1])
            ultimo_preco2 = float(dados['Close'][acao2].iloc[-1])
            
            # Modelo de cointegração
            serie1 = dados['Close'][acao1].dropna()
            serie2 = dados['Close'][acao2].dropna()
            modelo = OLS(serie1, serie2).fit()
            spread = serie1 - modelo.params[0] * serie2
            zscore_serie = self.calcular_zscore(spread)
            zscore_atual = float(zscore_serie.iloc[-1]) if not zscore_serie.empty else 0
            
            # Direções de operação
            direcao_acao1 = "Venda" if zscore_atual > 0 else "Compra"
            direcao_acao2 = "Compra" if zscore_atual > 0 else "Venda"
            
            # Cálculo de quantidades
            valor_por_lado = investimento / 2
            qtd1 = self.ajustar_quantidade(round(valor_por_lado / ultimo_preco1))
            qtd2 = self.ajustar_quantidade(round(valor_por_lado / ultimo_preco2))
            
            # Valores finais
            valor_total_acao1 = qtd1 * ultimo_preco1
            valor_total_acao2 = qtd2 * ultimo_preco2
            
            # ATR para Stop/Gain
            atr1 = self.calcular_atr(dados, acao1)
            atr2 = self.calcular_atr(dados, acao2)
            
            if not atr1.empty and not atr2.empty:
                valor_stop = self.calcular_valor_stop_atr(
                    dados, acao1, acao2, qtd1, qtd2, direcao_acao1, direcao_acao2
                )
                valor_gain = self.calcular_valor_gain_atr(
                    dados, acao1, acao2, qtd1, qtd2, direcao_acao1, direcao_acao2
                )
            else:
                valor_stop = valor_gain = 0
            
            # Dados para gráficos - limitando aos últimos 100 pontos
            zscore_serie_grafico = zscore_serie.tail(100) if not zscore_serie.empty else pd.Series()
            spread_ratio = (dados['Close'][acao1] / dados['Close'][acao2]).tail(100)
            
            # Beta rotativo
            beta_rotativo = self.calcular_beta_rotativo(dados, acao1, acao2, 60)
            beta_rotativo_grafico = beta_rotativo.tail(100) if not beta_rotativo.empty else pd.Series()
            
            print(f"✅ Análise detalhada concluída: Z-Score={zscore_atual:.3f}")
            
            return {
                'success': True,
                'data': {
                    'acao1': acao1,
                    'acao2': acao2,
                    'setor1': self.setores.get(acao1, 'N/A'),
                    'setor2': self.setores.get(acao2, 'N/A'),
                    'ultimo_preco1': ultimo_preco1,
                    'ultimo_preco2': ultimo_preco2,
                    'zscore_atual': zscore_atual,
                    'direcao_acao1': direcao_acao1,
                    'direcao_acao2': direcao_acao2,
                    'qtd1': qtd1,
                    'qtd2': qtd2,
                    'valor_total_acao1': valor_total_acao1,
                    'valor_total_acao2': valor_total_acao2,
                    'valor_stop': valor_stop,
                    'valor_gain': valor_gain,
                    'beta': float(modelo.params[0]),
                    'r_squared': float(modelo.rsquared),
                    'correlacao': float(dados['Close'][acao1].corr(dados['Close'][acao2])),
                    'meia_vida': self.calcular_meia_vida(spread),
                    'graficos': {
                        'zscore': {
                            'dates': [d.strftime('%Y-%m-%d') for d in zscore_serie_grafico.index],
                            'values': [float(v) if not pd.isna(v) else 0 for v in zscore_serie_grafico.values]
                        },
                        'spread': {
                            'dates': [d.strftime('%Y-%m-%d') for d in spread_ratio.index],
                            'values': [float(v) if not pd.isna(v) else 0 for v in spread_ratio.values]
                        },
                        'beta_rotativo': {
                            'dates': [d.strftime('%Y-%m-%d') for d in beta_rotativo_grafico.index],
                            'values': [float(v) if not pd.isna(v) else 0 for v in beta_rotativo_grafico.values]
                        }
                    }
                }
            }
            
        except Exception as e:
            print(f"❌ Erro na análise detalhada: {str(e)}")
            return {
                'success': False,
                'error': f'Erro na análise detalhada: {str(e)}'
            }

    def ajustar_quantidade(self, qtd):
        """Ajustar quantidade para lotes padrão"""
        if qtd >= 100:
            resto = qtd % 100
            if resto >= 51:
                return round((qtd + (100 - resto)) / 100) * 100
            return round((qtd - resto) / 100) * 100
        return max(1, round(qtd))

    def calcular_valor_stop_atr(self, dados, acao1, acao2, qtd1, qtd2, 
                               direcao_acao1, direcao_acao2, multiplicador_atr=2):
        """Calcular valor de Stop Loss baseado em ATR"""
        try:
            atr1 = self.calcular_atr(dados, acao1)
            atr2 = self.calcular_atr(dados, acao2)
            ultimo_preco1 = dados['Close'][acao1].iloc[-1]
            ultimo_preco2 = dados['Close'][acao2].iloc[-1]

            if atr1.empty or atr2.empty:
                return 0

            if direcao_acao1 == "Compra":
                stop_acao1 = ultimo_preco1 - (multiplicador_atr * atr1.iloc[-1])
                stop_acao2 = ultimo_preco2 + (multiplicador_atr * atr2.iloc[-1])
            else:
                stop_acao1 = ultimo_preco1 + (multiplicador_atr * atr1.iloc[-1])
                stop_acao2 = ultimo_preco2 - (multiplicador_atr * atr2.iloc[-1])
                
            return abs(qtd1 * (ultimo_preco1 - stop_acao1) + qtd2 * (stop_acao2 - ultimo_preco2))
        except:
            return 0

    def calcular_valor_gain_atr(self, dados, acao1, acao2, qtd1, qtd2, 
                               direcao_acao1, direcao_acao2, multiplicador_atr=3):
        """Calcular valor de Take Profit baseado em ATR"""
        try:
            atr1 = self.calcular_atr(dados, acao1)
            atr2 = self.calcular_atr(dados, acao2)
            ultimo_preco1 = dados['Close'][acao1].iloc[-1]
            ultimo_preco2 = dados['Close'][acao2].iloc[-1]

            if atr1.empty or atr2.empty:
                return 0

            if direcao_acao1 == "Compra":
                gain_acao1 = ultimo_preco1 + (multiplicador_atr * atr1.iloc[-1])
                gain_acao2 = ultimo_preco2 - (multiplicador_atr * atr2.iloc[-1])
            else:
                gain_acao1 = ultimo_preco1 - (multiplicador_atr * atr1.iloc[-1])
                gain_acao2 = ultimo_preco2 + (multiplicador_atr * atr2.iloc[-1])
                
            return abs(qtd1 * (gain_acao1 - ultimo_preco1) + qtd2 * (ultimo_preco2 - gain_acao2))
        except:
            return 0

    def calcular_margem_e_custos(self, valor_vendido, valor_comprado, percentual_garantia=25, 
                                taxa_btc_anual=2.0, dias_operacao=10, taxa_corretora_btc=35):
        """Calcular margem necessária e custos operacionais"""
        try:
            # Garantias
            garantia_venda = valor_vendido * (percentual_garantia / 100)
            garantia_compra = valor_comprado * (percentual_garantia / 100)
            margem_necessaria = max(0, garantia_venda - garantia_compra)
            
            # Custos operacionais
            volume_total = valor_vendido + valor_comprado
            emolumentos = volume_total * 0.000325  # 0.0325% sobre volume negociado
            
            # Custo BTC (apenas sobre valor vendido)
            taxa_btc_diaria = taxa_btc_anual / 365 / 100
            custo_btc_periodo = valor_vendido * taxa_btc_diaria * dias_operacao
            
            # Taxa da corretora sobre BTC
            taxa_corretora = custo_btc_periodo * (taxa_corretora_btc / 100)
            
            # Custo total
            custo_total = emolumentos + custo_btc_periodo + taxa_corretora
            
            return {
                'success': True,
                'data': {
                    'garantia_venda': garantia_venda,
                    'garantia_compra': garantia_compra,
                    'margem_necessaria': margem_necessaria,
                    'emolumentos': emolumentos,
                    'custo_btc_periodo': custo_btc_periodo,
                    'taxa_corretora': taxa_corretora,
                    'custo_total': custo_total,
                    'parametros': {
                        'percentual_garantia': percentual_garantia,
                        'taxa_btc_anual': taxa_btc_anual,
                        'dias_operacao': dias_operacao,
                        'taxa_corretora_btc': taxa_corretora_btc
                    }
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Erro no cálculo de margem: {str(e)}'
            }

    def executar_analise_completa(self, dias=240, zscore_minimo=2.0, investimento=10000):
        """Executar análise completa de Long & Short"""
        try:
            print(f"🚀 Iniciando análise completa - {dias} dias, Z-Score >= {zscore_minimo}")
            
            # Período de análise
            data_fim = datetime.now()
            data_inicio = data_fim - timedelta(days=dias)
            
            # Obter dados
            print(f"📊 Obtendo dados para {len(self.top_50_acoes)} ações...")
            dados = self.obter_dados(self.top_50_acoes, data_inicio, data_fim)
            
            if dados.empty:
                return {
                    'success': False,
                    'error': 'Não foi possível obter dados das ações'
                }
            
            print(f"✅ Dados obtidos: {dados.shape}")
            
            # Analisar pares
            print("🔍 Analisando pares por cointegração...")
            resultado_pares = self.analisar_pares(dados)
            
            if not resultado_pares['success']:
                return resultado_pares
            
            # Filtrar por Z-Score
            print(f"📊 Filtrando por Z-Score >= {zscore_minimo}...")
            pares_filtrados = self.filtrar_pares_por_zscore(
                dados, resultado_pares['data']['pares'], zscore_minimo
            )
            
            if not pares_filtrados['success']:
                return pares_filtrados
            
            # Estatísticas
            setores_unicos = set()
            for par in pares_filtrados['data']:
                setores_unicos.add(par['setor1'])
                setores_unicos.add(par['setor2'])
            
            # Preparar cache para análises futuras
            dados_cache = dados.to_json(orient='split', date_format='iso')
            
            print(f"✅ Análise completa finalizada:")
            print(f"   📊 {resultado_pares['data']['total_analisados']} pares analisados")
            print(f"   🎯 {len(pares_filtrados['data'])} oportunidades encontradas")
            print(f"   🏢 {len(setores_unicos)} setores envolvidos")
            
            return {
                'success': True,
                'data': {
                    'pares_oportunidade': pares_filtrados['data'],
                    'total_analisados': resultado_pares['data']['total_analisados'],
                    'total_oportunidades': len(pares_filtrados['data']),
                    'setores_envolvidos': len(setores_unicos),
                    'parametros': {
                        'dias': dias,
                        'zscore_minimo': zscore_minimo,
                        'investimento': investimento
                    },
                    'dados_cache': dados_cache
                }
            }
            
        except Exception as e:
            print(f"❌ Erro na análise completa: {str(e)}")
            return {
                'success': False,
                'error': f'Erro na análise completa: {str(e)}'
            }

    def verificar_status(self):
        """Verificar status do serviço"""
        try:
            return {
                'success': True,
                'data': {
                    'status': 'online',
                    'acoes_disponiveis': len(self.top_50_acoes),
                    'timestamp': datetime.now().isoformat()
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Erro no status: {str(e)}'
            }
            
def processar_cache_para_pares(self, dados_cache_json, acao1, acao2):
    """Processar cache JSON especificamente para pares específicos"""
    try:
        print("🔄 Processando cache otimizado para pares...")
        
        # Parse do JSON
        cache_data = json.loads(dados_cache_json) if isinstance(dados_cache_json, str) else dados_cache_json
        
        # Verificar formato do cache
        if isinstance(cache_data, dict) and all(key in cache_data for key in ['index', 'columns', 'data']):
            print("📦 Cache no formato otimizado detectado")
            
            # Reconstruir DataFrame básico
            df = pd.DataFrame(
                data=cache_data['data'],
                index=pd.to_datetime(cache_data['index']),
                columns=cache_data['columns']
            )
            
            print(f"📊 DataFrame inicial: {df.shape}")
            print(f"📊 Colunas: {df.columns[:5].tolist()}...")
            
            # Identificar colunas das ações desejadas
            colunas_acao1 = [col for col in df.columns if acao1 in str(col)]
            colunas_acao2 = [col for col in df.columns if acao2 in str(col)]
            
            print(f"🎯 Colunas {acao1}: {colunas_acao1}")
            print(f"🎯 Colunas {acao2}: {colunas_acao2}")
            
            if not colunas_acao1 or not colunas_acao2:
                print(f"⚠️ Ações {acao1} ou {acao2} não encontradas no cache")
                return None
            
            # Extrair apenas as colunas necessárias
            colunas_necessarias = colunas_acao1 + colunas_acao2
            df_filtrado = df[colunas_necessarias].copy()
            
            # Reconstruir MultiIndex manualmente
            tuples_multiindex = []
            dados_finais = {}
            
            for col in df_filtrado.columns:
                col_str = str(col)
                
                # Detectar tipo de dado e ação
                if 'Open' in col_str or 'open' in col_str.lower():
                    tipo = 'Open'
                elif 'High' in col_str or 'high' in col_str.lower():
                    tipo = 'High'
                elif 'Low' in col_str or 'low' in col_str.lower():
                    tipo = 'Low'
                elif 'Close' in col_str or 'close' in col_str.lower():
                    tipo = 'Close'
                elif 'Volume' in col_str or 'volume' in col_str.lower():
                    tipo = 'Volume'
                else:
                    continue  # Pular colunas não reconhecidas
                
                # Detectar ação
                if acao1 in col_str:
                    acao = acao1
                elif acao2 in col_str:
                    acao = acao2
                else:
                    continue
                
                # Adicionar aos dados finais
                tuples_multiindex.append((tipo, acao))
                dados_finais[(tipo, acao)] = df_filtrado[col]
            
            if not dados_finais:
                print("❌ Nenhuma coluna válida encontrada após processamento")
                return None
            
            # Criar DataFrame final com MultiIndex
            df_final = pd.DataFrame(dados_finais, index=df_filtrado.index)
            df_final.columns = pd.MultiIndex.from_tuples(tuples_multiindex)
            
            print(f"✅ Cache processado: {df_final.shape}")
            print(f"📊 MultiIndex criado: {df_final.columns.tolist()}")
            
            return df_final
            
        else:
            print("📦 Tentando formato de cache original...")
            # Fallback para formato original
            df = pd.read_json(cache_data, orient='split')
            
            # Filtrar apenas as ações necessárias se possível
            if isinstance(df.columns, pd.MultiIndex):
                if 'Close' in df.columns.levels[0]:
                    acoes_disponiveis = df['Close'].columns.tolist()
                    if acao1 in acoes_disponiveis and acao2 in acoes_disponiveis:
                        # Filtrar apenas as colunas das duas ações
                        colunas_filtradas = []
                        for nivel0 in df.columns.levels[0]:
                            for acao in [acao1, acao2]:
                                if (nivel0, acao) in df.columns:
                                    colunas_filtradas.append((nivel0, acao))
                        
                        if colunas_filtradas:
                            df_filtrado = df[colunas_filtradas]
                            print(f"✅ Cache original filtrado: {df_filtrado.shape}")
                            return df_filtrado
            
            print("⚠️ Não foi possível processar o cache no formato original")
            return None
            
    except Exception as e:
        print(f"❌ Erro ao processar cache: {str(e)}")
        return None
            
# Função para testar o serviço
if __name__ == "__main__":
    print("🧪 Testando Long Short Service Corrigido...")
    
    service = LongShortService()
    
    # Teste análise completa
    print("\n1️⃣ Executando análise completa:")
    resultado = service.executar_analise_completa(dias=120, zscore_minimo=2.0)
    
    if resultado['success']:
        data = resultado['data']
        print(f"✅ Análise concluída:")
        print(f"   📊 {data['total_analisados']} pares analisados")
        print(f"   🎯 {data['total_oportunidades']} oportunidades encontradas")
        print(f"   🏢 {data['setores_envolvidos']} setores envolvidos")
        
        if data['pares_oportunidade']:
            print(f"\n🔍 Primeira oportunidade:")
            primeiro_par = data['pares_oportunidade'][0]
            print(f"      {primeiro_par['acao1']} vs {primeiro_par['acao2']}")
            print(f"      Z-Score: {primeiro_par['zscore_atual']:.3f}")
            print(f"      Status Beta: {primeiro_par['status_beta']}")
            
            # Teste análise de estabilidade
            print(f"\n2️⃣ Testando análise de estabilidade:")
            resultado_estabilidade = service.analisar_estabilidade_par(
                data['dados_cache'], 
                primeiro_par['acao1'], 
                primeiro_par['acao2']
            )
            
            if resultado_estabilidade['success']:
                estab_data = resultado_estabilidade['data']
                print(f"✅ Estabilidade analisada:")
                print(f"   📊 Diagnóstico: {estab_data['diagnostico']['texto']}")
                print(f"   🎯 Períodos cointegrados: {estab_data['diagnostico']['periodos_cointegrados']}/{estab_data['diagnostico']['total_periodos']}")
            else:
                print(f"❌ Erro na estabilidade: {resultado_estabilidade['error']}")
                
    else:
        print(f"❌ {resultado['error']}")
    
    print("\n🎉 Teste concluído!")
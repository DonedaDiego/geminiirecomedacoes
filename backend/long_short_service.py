import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from statsmodels.tsa.stattools import adfuller, coint
from statsmodels.regression.linear_model import OLS
from statsmodels.regression.rolling import RollingOLS
import logging

class LongShortService:
    """Serviço completo para análise de pares Long & Short por cointegração"""
    
    def __init__(self):
        self.top_50_acoes = [
            "ABEV3", "ALOS3", "ALUP3", "ALUP4", "AURE3", "AZZA3", "B3SA3", "BBAS3", 
            "BBDC3", "BBDC4", "BBSE3", "BPAC11", "BPAN4", "BRAP3", "BRAP4", "BRAV3", 
            "BRFS3", "CCRO3", "CMIG3", "CMIG4", "CMIN3", "CPFE3", "CPLE3", "CPLE5", 
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
            "CCRO3": "Transporte", "CMIG3": "Energia Elétrica", "CMIG4": "Energia Elétrica",
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
            tuples = []
            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                for ticker in tickers:
                    tuples.append((col, ticker))
            columns = pd.MultiIndex.from_tuples(tuples)
            dados_final = pd.DataFrame(columns=columns)
            
            all_dates = set()
            ticker_data = {}
            
            for ticker in tickers:
                yf_ticker = ticker + '.SA'
                data = yf.download(yf_ticker, start=data_inicio, end=data_fim)
                
                if not data.empty:
                    ticker_data[ticker] = data
                    all_dates.update(data.index)
            
            dados_final = pd.DataFrame(index=sorted(all_dates), columns=columns)
            
            for ticker, df in ticker_data.items():
                dados_final[('Open', ticker)] = df['Open']
                dados_final[('High', ticker)] = df['High']
                dados_final[('Low', ticker)] = df['Low']
                dados_final[('Close', ticker)] = df['Close']
                dados_final[('Volume', ticker)] = df['Volume']
            
            dados_final = dados_final.ffill().bfill().infer_objects(copy=False)
            return dados_final
            
        except Exception as e:
            print(f"Erro ao obter dados: {str(e)}")
            return pd.DataFrame()

    def calcular_meia_vida(self, spread):
        """Calcular meia-vida do spread"""
        try:
            spread_lag = spread.shift(1)
            spread_diff = spread.diff()
            spread_lag = spread_lag.iloc[1:]
            spread_diff = spread_diff.iloc[1:]
            modelo = OLS(spread_diff, spread_lag).fit()
            if modelo.params[0] < 0:
                return -np.log(2) / modelo.params[0]
            return None
        except:
            return None

    def teste_adf(self, serie_temporal):
        """Teste de Dickey-Fuller Aumentado"""
        try:
            return adfuller(serie_temporal)[1]
        except:
            return 1.0

    def calcular_zscore(self, spread):
        """Calcular Z-Score do spread"""
        return (spread - spread.mean()) / spread.std()

    def analisar_pares(self, dados, max_meia_vida=30, min_meia_vida=1, 
                      max_pvalor_adf=0.05, min_correlacao=0.5, max_pvalor_coint=0.05):
        """Análise completa de pares para Long & Short"""
        try:
            n = dados['Close'].shape[1]
            resultados = []
            total_pares = 0
            
            for i in range(n):
                for j in range(i+1, n):
                    total_pares += 1
                    acao1, acao2 = dados['Close'].columns[i], dados['Close'].columns[j]
                    
                    if len(dados['Close'][acao1].dropna()) > 1 and len(dados['Close'][acao2].dropna()) > 1:
                        try:
                            _, pvalor, _ = coint(dados['Close'][acao1], dados['Close'][acao2])
                            
                            if pvalor <= max_pvalor_coint:
                                modelo = OLS(dados['Close'][acao1], dados['Close'][acao2]).fit()
                                spread = dados.loc[:, ('Close', acao1)] - modelo.params[0] * dados.loc[:, ('Close', acao2)]
                                meia_vida = self.calcular_meia_vida(spread)
                                
                                if meia_vida is not None:
                                    pvalor_adf = self.teste_adf(spread)
                                    correlacao = dados['Close'][acao1].corr(dados['Close'][acao2])
                                    
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
                        except:
                            continue
            
            return {
                'success': True,
                'data': {
                    'pares': resultados,
                    'total_analisados': total_pares,
                    'pares_validos': len(resultados)
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Erro na análise de pares: {str(e)}'
            }

    def filtrar_pares_por_zscore(self, dados, pares, zscore_minimo=2):
        """Filtrar pares com Z-Score significativo"""
        try:
            pares_validos = []
            
            for par in pares:
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
                modelo = OLS(dados['Close'][acao1], dados['Close'][acao2]).fit()
                spread = dados['Close', acao1] - modelo.params[0] * dados['Close', acao2]
                zscore_atual = self.calcular_zscore(spread).iloc[-1]
                
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
            
            return {
                'success': True,
                'data': pares_validos
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Erro no filtro por Z-Score: {str(e)}'
            }

    def calcular_beta_rotativo(self, dados, acao1, acao2, janela):
        """Calcular Beta Rotativo entre duas ações"""
        try:
            log_returns1 = np.log(dados['Close'][acao1] / dados['Close'][acao1].shift(1))
            log_returns2 = np.log(dados['Close'][acao2] / dados['Close'][acao2].shift(1))

            if len(log_returns1.dropna()) < janela or len(log_returns2.dropna()) < janela:
                return pd.Series()

            model = RollingOLS(log_returns1, log_returns2, window=janela)
            rolling_res = model.fit()

            return pd.Series(rolling_res.params.iloc[:, 0], index=dados.index[janela:])
        except:
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
            # Informações básicas
            ultimo_preco1 = float(dados['Close'][acao1].iloc[-1])
            ultimo_preco2 = float(dados['Close'][acao2].iloc[-1])
            
            # Modelo de cointegração
            modelo = OLS(dados['Close'][acao1], dados['Close'][acao2]).fit()
            spread = dados['Close'][acao1] - modelo.params[0] * dados['Close'][acao2]
            zscore_atual = float(self.calcular_zscore(spread).iloc[-1])
            
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
            
            # Dados para gráficos
            zscore_serie = self.calcular_zscore(spread)
            spread_ratio = dados['Close'][acao1] / dados['Close'][acao2]
            
            # Beta rotativo
            beta_rotativo = self.calcular_beta_rotativo(dados, acao1, acao2, 60)
            
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
                            'dates': [d.strftime('%Y-%m-%d') for d in zscore_serie.index[-100:]],
                            'values': zscore_serie.iloc[-100:].tolist()
                        },
                        'spread': {
                            'dates': [d.strftime('%Y-%m-%d') for d in spread_ratio.index[-100:]],
                            'values': spread_ratio.iloc[-100:].tolist()
                        },
                        'beta_rotativo': {
                            'dates': [d.strftime('%Y-%m-%d') for d in beta_rotativo.index[-100:]] if not beta_rotativo.empty else [],
                            'values': beta_rotativo.iloc[-100:].tolist() if not beta_rotativo.empty else []
                        }
                    }
                }
            }
            
        except Exception as e:
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
        return round(qtd)

    def calcular_valor_stop_atr(self, dados, acao1, acao2, qtd1, qtd2, 
                               direcao_acao1, direcao_acao2, multiplicador_atr=2):
        """Calcular valor de Stop Loss baseado em ATR"""
        try:
            atr1 = self.calcular_atr(dados, acao1)
            atr2 = self.calcular_atr(dados, acao2)
            ultimo_preco1 = dados['Close'][acao1].iloc[-1]
            ultimo_preco2 = dados['Close'][acao2].iloc[-1]

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

            if direcao_acao1 == "Compra":
                gain_acao1 = ultimo_preco1 + (multiplicador_atr * atr1.iloc[-1])
                gain_acao2 = ultimo_preco2 - (multiplicador_atr * atr2.iloc[-1])
            else:
                gain_acao1 = ultimo_preco1 - (multiplicador_atr * atr1.iloc[-1])
                gain_acao2 = ultimo_preco2 + (multiplicador_atr * atr2.iloc[-1])
                
            return abs(qtd1 * (gain_acao1 - ultimo_preco1) + qtd2 * (ultimo_preco2 - gain_acao2))
        except:
            return 0

    def executar_analise_completa(self, dias=240, zscore_minimo=2.0, investimento=10000):
        """Executar análise completa de Long & Short"""
        try:
            # Período de análise
            data_fim = datetime.now()
            data_inicio = data_fim - timedelta(days=dias)
            
            # Obter dados
            print(f"Obtendo dados para {len(self.top_50_acoes)} ações...")
            dados = self.obter_dados(self.top_50_acoes, data_inicio, data_fim)
            
            if dados.empty:
                return {
                    'success': False,
                    'error': 'Não foi possível obter dados das ações'
                }
            
            # Analisar pares
            print("Analisando pares...")
            resultado_pares = self.analisar_pares(dados)
            
            if not resultado_pares['success']:
                return resultado_pares
            
            # Filtrar por Z-Score
            print("Filtrando por Z-Score...")
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
                    'dados_cache': dados.to_json(orient='split', date_format='iso')
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Erro na análise completa: {str(e)}'
            }

# Função para testar o serviço
if __name__ == "__main__":
    print("🧪 Testando Long Short Service...")
    
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
            print(f"\n   🔍 Primeira oportunidade:")
            primeiro_par = data['pares_oportunidade'][0]
            print(f"      {primeiro_par['acao1']} vs {primeiro_par['acao2']}")
            print(f"      Z-Score: {primeiro_par['zscore_atual']:.3f}")
            print(f"      Status Beta: {primeiro_par['status_beta']}")
    else:
        print(f"❌ {resultado['error']}")
    
    print("\n🎉 Teste concluído!")
import yfinance as yf
import pandas as pd
import numpy as np
from statsmodels.tsa.stattools import adfuller, coint
from statsmodels.regression.linear_model import OLS
from statsmodels.regression.rolling import RollingOLS
from datetime import datetime, timedelta
from functools import lru_cache
import hashlib
from multiprocessing import Pool, cpu_count
import pickle
import os

# Cache persistente em disco
CACHE_DIR = os.path.join(os.path.dirname(__file__), '.cache')
os.makedirs(CACHE_DIR, exist_ok=True)

CACHE_DADOS = {}
CACHE_TTL = 3600 

SETORES = {
   "ABEV3": "Bebidas",
   "ALOS3": "Exploração de Imóveis",
   "AZZA3": "Comércio Varejista", 
   "B3SA3": "Serviços Financeiros",
   "BBAS3": "Intermediários Financeiros",
   "BBDC3": "Intermediários Financeiros",
   "BBDC4": "Intermediários Financeiros",
   "BBSE3": "Previdência e Seguros",
   "BPAC11": "Intermediários Financeiros",
   "BPAN4": "Intermediários Financeiros",
   "BRAP3": "Mineração",
   "BRAP4": "Mineração",
   "BRAV3": "Petróleo, Gás e Biocombustíveis",
   "CMIG3": "Energia Elétrica",
   "CMIG4": "Energia Elétrica",
   "CMIN3": "Mineração",
   "CPFE3": "Energia Elétrica",
   "CPLE5": "Energia Elétrica",
   "CSAN3": "Petróleo, Gás e Biocombustíveis",
   "CSMG3": "Água e Saneamento",
   "CSNA3": "Siderurgia e Metalurgia",
   "CXSE3": "Previdência e Seguros",
   "CYRE3": "Construção Civil",
   "AXIA3": "Energia Elétrica",
   "AXIA6": "Energia Elétrica",
   "AXIA6": "Energia Elétrica",
   "EGIE3": "Energia Elétrica",
   "EMBJ3": "Material de Transporte",
   "MBRF3": "Processadora de Alimentos",
   "ENEV3": "Energia Elétrica",
   "ENGI11": "Energia Elétrica",
   "ENGI3": "Energia Elétrica",
   "ENGI4": "Energia Elétrica",
   "EQTL3": "Energia Elétrica",
   "GGBR3": "Siderurgia e Metalurgia",
   "GGBR4": "Siderurgia e Metalurgia",
   "GOAU4": "Siderurgia e Metalurgia",
   "HAPV3": "Serviços Médicos",
   "HYPE3": "Comércio e Distribuição",
   "ITSA3": "Holdings Diversificadas",
   "ITSA4": "Holdings Diversificadas",
   "ITUB3": "Intermediários Financeiros",
   "ITUB4": "Intermediários Financeiros",   
   "KLBN11": "Madeira e Papel",
   "KLBN3": "Madeira e Papel",
   "KLBN4": "Madeira e Papel",
   "LREN3": "Comércio Varejista",
   "MDIA3": "Alimentos Processados",
   "NEOE3": "Energia Elétrica",
   "NATU3": "Produtos de Cuidado Pessoal",
   "PETR3": "Petróleo, Gás e Biocombustíveis",
   "PETR4": "Petróleo, Gás e Biocombustíveis",
   "PRIO3": "Petróleo, Gás e Biocombustíveis",
   "PSSA3": "Previdência e Seguros",
   "RAIL3": "Transporte",
   "RAIZ4": "Petróleo, Gás e Biocombustíveis",
   "RDOR3": "Serviços Médicos",
   "RENT3": "Diversos",
   "SANB11": "Intermediários Financeiros",
   "SANB4": "Intermediários Financeiros",
   "SBSP3": "Água e Saneamento",
   "SUZB3": "Madeira e Papel",
   "VBBR3": "Petróleo, Gás e Biocombustíveis",
   "VALE3": "Mineração",
   "VIVT3": "Telecomunicações",
   "WEGE3": "Máquinas e Equipamentos",
   "UGPA3": "Petróleo, Gás e Biocombustíveis"
}


def obter_top_50_acoes_brasileiras():
    return [
      "ABEV3",  "AZZA3", "B3SA3", "BBAS3", "BBDC3", "BBDC4", "BBSE3", "BPAC11",  
      "BPAN4", "BRAP3", "BRAP4", "BRAV3", "CMIG3", "CMIG4", "CMIN3", 
      "CPFE3",  "CPLE5", "CSAN3", "CSMG3", "CSNA3", "CXSE3", "CYRE3",  "AXIA3", "AXIA6", 
      "EGIE3", "EMBJ3", "ENEV3", "ENGI11", "ENGI3", "ENGI4", "EQTL3", "GGBR3", "GGBR4", "GOAU4", "HAPV3", "HYPE3", 
      "ITSA3", "ITSA4", "ITUB3", "ITUB4", "KLBN11", "KLBN3", "KLBN4", "LREN3", "MDIA3",  "NEOE3","MBRF3",
      "NATU3", "PETR3", "PETR4", "PRIO3", "PSSA3", "RAIL3", "RAIZ4", "RDOR3", "RENT3", "SANB11", "SANB4", "SBSP3", "SUZB3", 
      "VBBR3", "VALE3", "VIVT3", "WEGE3", "UGPA3"
    ]


def obter_dados(tickers, data_inicio, data_fim):
    try:
        # Normaliza as datas para evitar hashes diferentes
        if isinstance(data_inicio, str):
            data_inicio = pd.to_datetime(data_inicio).strftime('%Y-%m-%d')
        if isinstance(data_fim, str):
            data_fim = pd.to_datetime(data_fim).strftime('%Y-%m-%d')
        
        # Ordena os tickers para garantir mesmo hash
        tickers_sorted = sorted(tickers)
        cache_key = hashlib.md5(f"{','.join(tickers_sorted)}_{data_inicio}_{data_fim}".encode()).hexdigest()
        cache_file = os.path.join(CACHE_DIR, f"{cache_key}.pkl")
        
        # Verifica cache em memória primeiro
        if cache_key in CACHE_DADOS:
            cached_data, cached_time = CACHE_DADOS[cache_key]
            if (datetime.now() - cached_time).total_seconds() < CACHE_TTL:
                print(f"[CACHE HIT - MEMÓRIA] {len(tickers)} tickers")
                return cached_data
        
        # Verifica cache em disco
        if os.path.exists(cache_file):
            file_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
            if (datetime.now() - file_time).total_seconds() < CACHE_TTL:
                print(f"[CACHE HIT - DISCO] {len(tickers)} tickers")
                with open(cache_file, 'rb') as f:
                    cached_data = pickle.load(f)
                    CACHE_DADOS[cache_key] = (cached_data, datetime.now())
                    return cached_data
        
        # Download dos dados
        print(f"[DOWNLOAD] Baixando {len(tickers)} tickers...")
        tickers_sa = [t + '.SA' for t in tickers_sorted]
        tickers_string = ' '.join(tickers_sa)
        
        data = yf.download(
            tickers_string, 
            start=data_inicio, 
            end=data_fim, 
            group_by='ticker', 
            threads=True,
            auto_adjust=True,  # Adiciona para evitar o warning
            progress=False  # Remove a barra de progresso repetitiva
        )
        
        tuples = []
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            for ticker in tickers_sorted:
                tuples.append((col, ticker))
        columns = pd.MultiIndex.from_tuples(tuples)
        dados_final = pd.DataFrame(index=data.index, columns=columns)
        
        for ticker in tickers_sorted:
            ticker_sa = ticker + '.SA'
            if ticker_sa in data.columns.get_level_values(0):
                dados_final[('Open', ticker)] = data[ticker_sa]['Open']
                dados_final[('High', ticker)] = data[ticker_sa]['High']
                dados_final[('Low', ticker)] = data[ticker_sa]['Low']
                dados_final[('Close', ticker)] = data[ticker_sa]['Close']
                dados_final[('Volume', ticker)] = data[ticker_sa]['Volume']
        
        dados_final = dados_final.ffill().bfill().infer_objects(copy=False)
        
        # Salva em memória e disco
        CACHE_DADOS[cache_key] = (dados_final, datetime.now())
        with open(cache_file, 'wb') as f:
            pickle.dump(dados_final, f)
        
        print(f"[CACHE SALVO] {len(tickers)} tickers")
        return dados_final
        
    except Exception as e:
        raise Exception(f"Erro ao obter dados: {str(e)}")

def limpar_cache_antigo(dias=7):
    """Remove arquivos de cache com mais de X dias"""
    try:
        agora = datetime.now()
        for filename in os.listdir(CACHE_DIR):
            filepath = os.path.join(CACHE_DIR, filename)
            if os.path.isfile(filepath):
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                if (agora - file_time).days > dias:
                    os.remove(filepath)
                    print(f"[CACHE LIMPO] {filename}")
    except Exception as e:
        print(f"Erro ao limpar cache: {e}")


def calcular_meia_vida(spread):
    spread_lag = spread.shift(1)
    spread_diff = spread.diff()
    spread_lag = spread_lag.iloc[1:]
    spread_diff = spread_diff.iloc[1:]
    modelo = OLS(spread_diff, spread_lag).fit()
    if modelo.params[0] < 0:
        return -np.log(2) / modelo.params[0]
    return None


def teste_adf(serie_temporal):
    return adfuller(serie_temporal)[1]


def calcular_zscore(spread):
    mean = spread.mean()
    std = spread.std()
    return (spread - mean) / std


def processar_par(args):
    dados_close, i, j, max_meia_vida, min_meia_vida, max_pvalor_adf, max_pvalor_coint, correlacao_ij = args
    
    acao1, acao2 = dados_close.columns[i], dados_close.columns[j]
    
    try:
        serie1 = dados_close[acao1].dropna()
        serie2 = dados_close[acao2].dropna()
        
        if len(serie1) <= 1 or len(serie2) <= 1:
            return None
        
        _, pvalor, _ = coint(serie1, serie2)
        
        if pvalor > max_pvalor_coint:
            return None
        
        modelo = OLS(serie1, serie2).fit()
        spread = serie1 - modelo.params[0] * serie2
        meia_vida = calcular_meia_vida(spread)
        
        if meia_vida is None:
            return None
        
        pvalor_adf = teste_adf(spread)
        
        if not (min_meia_vida <= meia_vida <= max_meia_vida and pvalor_adf <= max_pvalor_adf):
            return None
        
        return {
            'Acao1': acao1,
            'Acao2': acao2,
            'PvalorCointegracao': pvalor,
            'MeiaVida': meia_vida,
            'PvalorADF': pvalor_adf,
            'Correlacao': correlacao_ij,
            'Beta': float(modelo.params[0])
        }
    except:
        return None


def analisar_pares(dados, max_meia_vida=30, min_meia_vida=1, max_pvalor_adf=0.05, min_correlacao=0.5, max_pvalor_coint=0.05):
    n = dados['Close'].shape[1]
    total_pares = 0
    
    print(f"[DEBUG] Colunas no Close: {n}")
    print(f"[DEBUG] Shape dos dados: {dados['Close'].shape}")
    
    correlacoes = dados['Close'].corr()
    
    resultados = []
    pares_testados = 0
    
    for i in range(n):
        for j in range(i+1, n):
            total_pares += 1
            correlacao = correlacoes.iloc[i, j]
            
            if correlacao >= min_correlacao:
                pares_testados += 1
                resultado = processar_par((
                    dados['Close'],
                    i,
                    j,
                    max_meia_vida,
                    min_meia_vida,
                    max_pvalor_adf,
                    max_pvalor_coint,
                    correlacao
                ))
                if resultado is not None:
                    resultados.append(resultado)
    
    print(f"[DEBUG] Total pares: {total_pares}")
    print(f"[DEBUG] Pares testados (correlação ok): {pares_testados}")
    print(f"[DEBUG] Pares cointegrados encontrados: {len(resultados)}")
    
    return pd.DataFrame(resultados), total_pares


def filtrar_pares_por_zscore(dados, df_resultados, zscore_minimo=2):
    pares_validos = []
    
    for _, row in df_resultados.iterrows():
        acao1, acao2 = row['Acao1'], row['Acao2']
        
        beta_rotativo = calcular_beta_rotativo(dados, acao1, acao2, 60)  
        if not beta_rotativo.empty:
            beta_atual = beta_rotativo.iloc[-1]
            beta_medio = beta_rotativo.mean()
            desvio_padrao = beta_rotativo.std()
            
            distancia_media = abs(beta_atual - beta_medio)
            if distancia_media <= desvio_padrao:
                status = 'Favoravel'
            elif distancia_media <= 1.5 * desvio_padrao:
                status = 'Cautela'
            else:
                status = 'Não Recomendado'
        else:
            status = 'Indisponivel'
                
        modelo = OLS(dados['Close'][acao1], dados['Close'][acao2]).fit()
        spread = dados['Close', acao1] - modelo.params[0] * dados['Close', acao2]
        zscore_atual = calcular_zscore(spread).iloc[-1]

        if abs(zscore_atual) >= zscore_minimo:
            print(f"[DEBUG] Par válido: {acao1}/{acao2} zscore={zscore_atual:.2f}")
            direcao_acao1 = "Venda" if zscore_atual > 0 else "Compra"
            direcao_acao2 = "Compra" if zscore_atual > 0 else "Venda"
            
            pares_validos.append({
                'Acao1': acao1,
                'Acao2': acao2,
                'PvalorCointegracao': row['PvalorCointegracao'],
                'MeiaVida': row['MeiaVida'],
                'PvalorADF': row['PvalorADF'],
                'Correlacao': row['Correlacao'],
                'Beta': row['Beta'],  
                'Status': status,
                'ZscoreAtual': zscore_atual,
                'DirecaoAcao1': direcao_acao1,
                'DirecaoAcao2': direcao_acao2
            })
    print(f"[DEBUG] Pares após filtro zscore: {len(pares_validos)}")        
    return pd.DataFrame(pares_validos)


def analisar_cointegration_stability(dados, acao1, acao2, periodos=None):
    """Analisa estabilidade da cointegração em diferentes períodos"""
    if periodos is None:
        periodos = [60, 90, 120, 140, 180, 200, 240]
    
    resultados = []
    
    for periodo in periodos:
        if len(dados) < periodo:
            continue
            
        dados_recentes = dados.tail(periodo)
        
        # Cointegração
        _, pvalor, _ = coint(dados_recentes['Close'][acao1], dados_recentes['Close'][acao2])
        
        # Spread e Meia-Vida
        modelo = OLS(dados_recentes['Close'][acao1], dados_recentes['Close'][acao2]).fit()
        spread = dados_recentes['Close'][acao1] - modelo.params[0] * dados_recentes['Close'][acao2]
        meia_vida = calcular_meia_vida(spread) if len(spread.dropna()) > 1 else None
        
        resultados.append({
            'Periodo': periodo,
            'PvalorCoint': round(pvalor, 4),
            'MeiaVida': round(meia_vida, 2) if meia_vida else None,
            'R2': round(modelo.rsquared, 4),
            'Status': 'Cointegrado' if pvalor < 0.05 else 'Não Cointegrado'
        })

    return pd.DataFrame(resultados)


def calcular_atr(dados, acao, periodo=14):
    high = dados['High'][acao].values
    low = dados['Low'][acao].values
    close = np.roll(dados['Close'][acao].values, 1)
    close[0] = np.nan
    
    tr = np.maximum.reduce([
        high - low,
        np.abs(high - close),
        np.abs(low - close)
    ])
    
    atr = pd.Series(tr, index=dados['High'][acao].index).rolling(window=periodo).mean()
    return atr


def calcular_valor_stop_atr(dados, acao1, acao2, qtd1, qtd2, direcao_acao1, direcao_acao2, multiplicador_atr=2):
    atr1 = calcular_atr(dados, acao1)
    atr2 = calcular_atr(dados, acao2)
    ultimo_preco1 = dados['Close'][acao1].iloc[-1]
    ultimo_preco2 = dados['Close'][acao2].iloc[-1]

    if direcao_acao1 == "Compra":
        stop_acao1 = ultimo_preco1 - (multiplicador_atr * atr1.iloc[-1])
        stop_acao2 = ultimo_preco2 + (multiplicador_atr * atr2.iloc[-1])
    else:
        stop_acao1 = ultimo_preco1 + (multiplicador_atr * atr1.iloc[-1])
        stop_acao2 = ultimo_preco2 - (multiplicador_atr * atr2.iloc[-1])
        
    return abs(qtd1 * (ultimo_preco1 - stop_acao1) + qtd2 * (stop_acao2 - ultimo_preco2))


def calcular_valor_gain_atr(dados, acao1, acao2, qtd1, qtd2, direcao_acao1, direcao_acao2, multiplicador_atr=3):
    atr1 = calcular_atr(dados, acao1)
    atr2 = calcular_atr(dados, acao2)
    ultimo_preco1 = dados['Close'][acao1].iloc[-1]
    ultimo_preco2 = dados['Close'][acao2].iloc[-1]

    if direcao_acao1 == "Compra":
        gain_acao1 = ultimo_preco1 + (multiplicador_atr * atr1.iloc[-1])
        gain_acao2 = ultimo_preco2 - (multiplicador_atr * atr2.iloc[-1])
    else:
        gain_acao1 = ultimo_preco1 - (multiplicador_atr * atr1.iloc[-1])
        gain_acao2 = ultimo_preco2 + (multiplicador_atr * atr2.iloc[-1])
        
    return abs(qtd1 * (gain_acao1 - ultimo_preco1) + qtd2 * (ultimo_preco2 - gain_acao2))


def calcular_zscore_serie(dados, acao1, acao2):
    modelo = OLS(dados['Close'][acao1], dados['Close'][acao2]).fit()
    spread = dados['Close'][acao1] - modelo.params[0] * dados['Close'][acao2]
    zscore = calcular_zscore(spread)
    
    return {
        'zscore': zscore.tolist(),
        'datas': zscore.index.strftime('%Y-%m-%d').tolist()
    }


def calcular_spread_serie(dados, acao1, acao2):
    spread = dados['Close'][acao1] / dados['Close'][acao2]
    
    return {
        'spread': spread.tolist(),
        'datas': spread.index.strftime('%Y-%m-%d').tolist()
    }


def calcular_beta_rotativo(dados, acao1, acao2, janela):
    log_returns1 = np.log(dados['Close'][acao1] / dados['Close'][acao1].shift(1))
    log_returns2 = np.log(dados['Close'][acao2] / dados['Close'][acao2].shift(1))

    if len(log_returns1.dropna()) < janela or len(log_returns2.dropna()) < janela:
        return pd.Series()

    model = RollingOLS(log_returns1, log_returns2, window=janela)
    rolling_res = model.fit()

    return pd.Series(rolling_res.params.iloc[:, 0], index=dados.index[janela:])


def analisar_beta_rotativo(beta_rotativo, beta_atual, beta_medio, desvio_padrao):
    analise = {
        'status': 'Normal',
        'nivelRisco': 'Baixo',
        'alertas': [],
        'sugestoes': [],
        'interpretacao': '',
        'explicacaoStatus': ''
    }
    
    distancia_media = abs(beta_atual - beta_medio)
    
    if distancia_media <= desvio_padrao:
        analise['status'] = 'Favoravel'
        analise['nivelRisco'] = 'Baixo'
        analise['explicacaoStatus'] = 'Beta proximo da media historica'
        analise['sugestoes'].extend([
            "Tamanho normal de posicao",
            "Stops podem ser mais relaxados",
            "Monitoramento normal"
        ])
        
    elif distancia_media <= 1.5 * desvio_padrao:
        analise['status'] = 'Cautela'
        analise['nivelRisco'] = 'Medio'
        analise['explicacaoStatus'] = 'Beta se afastando da media'
        analise['sugestoes'].extend([
            "Reduzir tamanho da posicao",
            "Stops mais proximos",
            "Monitoramento mais frequente"
        ])
        
    else:
        analise['status'] = 'Não Recomendado'
        analise['nivelRisco'] = 'Alto'
        analise['explicacaoStatus'] = 'Beta muito distante da media'
        analise['sugestoes'].extend([
            "Evitar novas entradas",
            "Se ja estiver posicionado, considerar sair",
            "Aguardar estabilizacao do beta"
        ])

    if beta_atual > beta_medio:
        analise['interpretacao'] = f"Ativos {((beta_atual/beta_medio - 1) * 100):.1f}% mais correlacionados que o normal"
    else:
        analise['interpretacao'] = f"Ativos {((1 - beta_atual/beta_medio) * 100):.1f}% menos correlacionados que o normal"
        
    return analise


def calcular_beta_rotativo_serie(dados, acao1, acao2, janela):
    beta_rotativo = calcular_beta_rotativo(dados, acao1, acao2, janela)
    
    if beta_rotativo.empty:
        return None

    media_beta = beta_rotativo.mean()
    desvio_padrao_beta = beta_rotativo.std()
    limite_superior = media_beta + 2 * desvio_padrao_beta
    limite_inferior = media_beta - 2 * desvio_padrao_beta

    return {
        'beta': beta_rotativo.tolist(),
        'datas': beta_rotativo.index.strftime('%Y-%m-%d').tolist(),
        'mediaBeta': float(media_beta),
        'desvioPadraoBeta': float(desvio_padrao_beta),
        'limiteSuperior': float(limite_superior),
        'limiteInferior': float(limite_inferior)
    }


def ajustar_quantidade(qtd):
    if qtd >= 100:
        resto = qtd % 100
        if resto >= 51:
            return round((qtd + (100 - resto)) / 100) * 100
        return round((qtd - resto) / 100) * 100
    return round(qtd)


def calcular_quantidades_operacao(dados, acao1, acao2, beta, direcao_acao1, direcao_acao2, investimento):    
    ultimo_preco1 = dados['Close'][acao1].iloc[-1]
    ultimo_preco2 = dados['Close'][acao2].iloc[-1]

    if beta > 0:
        valor_por_lado = investimento / 2
        qtd1 = ajustar_quantidade(round(valor_por_lado / ultimo_preco1))
        qtd2 = ajustar_quantidade(round(valor_por_lado / ultimo_preco2))
        
        valor_acao1 = qtd1 * ultimo_preco1
        valor_acao2 = qtd2 * ultimo_preco2
        
        valor_total = abs(qtd1 * ultimo_preco1) + abs(qtd2 * ultimo_preco2)
        if valor_total > investimento:
            fator_ajuste = investimento / valor_total
            qtd1 = round(qtd1 * fator_ajuste)
            qtd2 = round(qtd2 * fator_ajuste)
            qtd1 = ajustar_quantidade(qtd1)
            qtd2 = ajustar_quantidade(qtd2)
                
        valor_acao1 = qtd1 * ultimo_preco1
        valor_acao2 = qtd2 * ultimo_preco2

        if abs(valor_acao1 - valor_acao2) > min(ultimo_preco1, ultimo_preco2):
            if valor_acao1 > valor_acao2:
                qtd1 = ajustar_quantidade(round(qtd1 * (valor_acao2 / valor_acao1)))
            else:
                qtd2 = ajustar_quantidade(round(qtd2 * (valor_acao1 / valor_acao2)))
    else:
        valor_por_lado = investimento / 2
        qtd1 = ajustar_quantidade(round(valor_por_lado / ultimo_preco1))
        qtd2 = ajustar_quantidade(round(valor_por_lado / ultimo_preco2))
                    
        valor_total = abs(qtd1 * ultimo_preco1) + abs(qtd2 * ultimo_preco2)
        if valor_total > investimento:
            fator_ajuste = investimento / valor_total
            qtd1 = round(qtd1 * fator_ajuste)
            qtd2 = round(qtd2 * fator_ajuste)
            qtd1 = ajustar_quantidade(qtd1)
            qtd2 = ajustar_quantidade(qtd2)

    valor_total_acao1 = (qtd1 * ultimo_preco1) * (1 if direcao_acao1 == "Venda" else -1)
    valor_total_acao2 = (qtd2 * ultimo_preco2) * (1 if direcao_acao2 == "Venda" else -1)

    impacto_liquido = abs(valor_total_acao1) if "Venda" in direcao_acao1 else -abs(valor_total_acao1)
    impacto_liquido += abs(valor_total_acao2) if "Venda" in direcao_acao2 else -abs(valor_total_acao2)

    return {
        'qtd1': int(qtd1),
        'qtd2': int(qtd2),
        'ultimoPreco1': float(ultimo_preco1),
        'ultimoPreco2': float(ultimo_preco2),
        'valorTotal1': float(abs(valor_total_acao1)),
        'valorTotal2': float(abs(valor_total_acao2)),
        'impactoLiquido': float(impacto_liquido)
    }


def calcular_margem_custos(valor_vendido, valor_comprado, percentual_garantia, taxa_btc_anual, dias_operacao, taxa_corretora_btc):
    garantia_venda = valor_vendido * (1 + percentual_garantia/100)
    garantia_compra = abs(valor_comprado) * (1 + percentual_garantia/100)
    margem_necessaria = abs(garantia_venda - garantia_compra)
    
    volume_total = abs(valor_vendido) + abs(valor_comprado)
    emolumentos = (volume_total / 10000) * 3.25
    taxa_btc_diaria = (taxa_btc_anual/100) / 252
    custo_btc_periodo = abs(valor_vendido) * taxa_btc_diaria * dias_operacao
    taxa_corretora = custo_btc_periodo * (taxa_corretora_btc/100)
    custo_total = margem_necessaria + emolumentos + custo_btc_periodo + taxa_corretora
    
    return {
        'valorVendido': float(abs(valor_vendido)),
        'valorComprado': float(abs(valor_comprado)),
        'garantiaVenda': float(garantia_venda),
        'garantiaCompra': float(garantia_compra),
        'margemNecessaria': float(margem_necessaria),
        'emolumentos': float(emolumentos),
        'custoBTC': float(custo_btc_periodo),
        'taxaCorretora': float(taxa_corretora),
        'custoTotal': float(custo_total)
    }
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from statsmodels.tsa.stattools import coint
from statsmodels.regression.linear_model import OLS
from premium import longshortservice as lss

longshort_bp = Blueprint('longshort', __name__, url_prefix='/api/longshort')


@longshort_bp.route('/analisar', methods=['POST'])
def analisar_pares():
    try:
        data = request.json
        investimento = data.get('investimento', 10000.0)
        dias = data.get('dias', 240)
        janela_beta = data.get('janelaBeta', 60)
        zscore_minimo = data.get('zscoreMinimo', 2.0)
        max_meia_vida = data.get('maxMeiaVida', 50)
        max_pvalor_adf = data.get('maxPvalorAdf', 0.05)
        min_correlacao = data.get('minCorrelacao', 0.05)
        max_pvalor_coint = data.get('maxPvalorCoint', 0.05)
        
        tickers = lss.obter_top_50_acoes_brasileiras()
        data_fim = datetime.now()
        data_inicio = data_fim - timedelta(days=dias)
        
        dados = lss.obter_dados(tickers, data_inicio, data_fim)
        
        df_resultados, total_pares = lss.analisar_pares(
            dados, 
            max_meia_vida=max_meia_vida,
            min_meia_vida=1,
            max_pvalor_adf=max_pvalor_adf,
            min_correlacao=min_correlacao,
            max_pvalor_coint=max_pvalor_coint
        )
        
        df_resultados_filtrados = lss.filtrar_pares_por_zscore(dados, df_resultados, zscore_minimo)
        
        setores_unicos = set()
        for _, row in df_resultados_filtrados.iterrows():
            setores_unicos.add(lss.SETORES[row['Acao1']])
            setores_unicos.add(lss.SETORES[row['Acao2']])
        
        pares = []
        for _, row in df_resultados_filtrados.iterrows():
            pares.append({
                'acao1': row['Acao1'],
                'acao2': row['Acao2'],
                'setorAcao1': lss.SETORES[row['Acao1']],
                'setorAcao2': lss.SETORES[row['Acao2']],
                'meiaVida': float(row['MeiaVida']),
                'status': row['Status'],
                'zscoreAtual': float(row['ZscoreAtual']),
                'direcaoAcao1': row['DirecaoAcao1'],
                'direcaoAcao2': row['DirecaoAcao2'],
                'pvalorCointegracao': float(row['PvalorCointegracao']),
                'pvalorADF': float(row['PvalorADF']),
                'correlacao': float(row['Correlacao']),
                'beta': float(row['Beta'])
            })
        
        return jsonify({
            'sucesso': True,
            'totalParesAnalisados': total_pares,
            'paresEncontrados': len(df_resultados_filtrados),
            'setoresUnicos': len(setores_unicos),
            'pares': pares
        }), 200
        
    except Exception as e:
        return jsonify({
            'sucesso': False,
            'erro': str(e)
        }), 500


@longshort_bp.route('/par/<acao1>/<acao2>', methods=['POST'])
def analisar_par_detalhado(acao1, acao2):
    try:
        data = request.json        
        investimento = data.get('investimento', 10000.0)
        dias = data.get('dias', 240)
        janela_beta = data.get('janelaBeta', 60)
        
        tickers = lss.obter_top_50_acoes_brasileiras()
        data_fim = datetime.now()
        data_inicio = data_fim - timedelta(days=dias)
        
        dados = lss.obter_dados(tickers, data_inicio, data_fim)
        
        # Calcular estatísticas do par diretamente
        serie1 = dados['Close'][acao1].dropna()
        serie2 = dados['Close'][acao2].dropna()
        
        if len(serie1) == 0 or len(serie2) == 0:
            return jsonify({
                'sucesso': False,
                'erro': 'Dados insuficientes para as ações solicitadas'
            }), 404
        
        # Cointegração
        _, pvalor_coint, _ = coint(serie1, serie2)
        
        # Beta e R²  <-- ADICIONAR R² AQUI
        modelo = OLS(serie1, serie2).fit()
        beta = modelo.params.iloc[0]
        r2 = modelo.rsquared  # <-- ADICIONAR ESSA LINHA
        
        # Spread e Z-score
        spread = serie1 - beta * serie2
        zscore_atual = lss.calcular_zscore(spread).iloc[-1]
        
        # Meia-vida
        meia_vida = lss.calcular_meia_vida(spread)
        if meia_vida is None:
            meia_vida = 0
        
        # P-valor ADF
        pvalor_adf = lss.teste_adf(spread)
        
        # Correlação
        correlacao = serie1.corr(serie2)
        
        # Beta Rotation e Status
        beta_rotativo = lss.calcular_beta_rotativo(dados, acao1, acao2, janela_beta)
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
                status = 'NaoRecomendado'
        else:
            status = 'Indisponivel'
        
        # Direções
        direcao_acao1 = "Venda" if zscore_atual > 0 else "Compra"
        direcao_acao2 = "Compra" if zscore_atual > 0 else "Venda"
        
        quantidades = lss.calcular_quantidades_operacao(
            dados, 
            acao1, 
            acao2, 
            beta,
            direcao_acao1,
            direcao_acao2,
            investimento
        )
        
        valor_stop = lss.calcular_valor_stop_atr(
            dados, acao1, acao2, 
            quantidades['qtd1'], 
            quantidades['qtd2'],
            direcao_acao1, 
            direcao_acao2
        )
        
        valor_gain = lss.calcular_valor_gain_atr(
            dados, acao1, acao2, 
            quantidades['qtd1'], 
            quantidades['qtd2'],
            direcao_acao1, 
            direcao_acao2
        )
        
        valor_total_operacao = (
            abs(quantidades['qtd1']) * quantidades['ultimoPreco1'] + 
            abs(quantidades['qtd2']) * quantidades['ultimoPreco2']
        )
        
        percentual_stop = (valor_stop / valor_total_operacao) * 100 if valor_total_operacao != 0 else 0
        percentual_gain = (valor_gain / valor_total_operacao) * 100 if valor_total_operacao != 0 else 0
        
        return jsonify({
            'sucesso': True,
            'par': {
                'acao1': acao1,
                'acao2': acao2,
                'setorAcao1': lss.SETORES.get(acao1, 'N/A'),
                'setorAcao2': lss.SETORES.get(acao2, 'N/A'),
                'correlacao': float(correlacao),
                'beta': float(beta),
                'r2': float(r2),  # <-- ADICIONAR ESSA LINHA
                'meiaVida': float(meia_vida),
                'pvalorCointegracao': float(pvalor_coint),
                'pvalorADF': float(pvalor_adf),
                'zscoreAtual': float(zscore_atual),
                'status': status,
                'direcaoAcao1': direcao_acao1,
                'direcaoAcao2': direcao_acao2
            },
            'quantidades': quantidades,
            'stopGain': {
                'valorStop': float(valor_stop),
                'valorGain': float(valor_gain),
                'percentualStop': float(percentual_stop),
                'percentualGain': float(percentual_gain)
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'sucesso': False,
            'erro': str(e)
        }), 500


@longshort_bp.route('/zscore/<acao1>/<acao2>', methods=['GET'])
def obter_zscore(acao1, acao2):
    try:
        dias = int(request.args.get('dias', 240))
        
        tickers = lss.obter_top_50_acoes_brasileiras()
        data_fim = datetime.now()
        data_inicio = data_fim - timedelta(days=dias)
        
        dados = lss.obter_dados(tickers, data_inicio, data_fim)
        
        zscore_data = lss.calcular_zscore_serie(dados, acao1, acao2)
        
        return jsonify({
            'sucesso': True,
            'zscore': zscore_data
        }), 200
        
    except Exception as e:
        return jsonify({
            'sucesso': False,
            'erro': str(e)
        }), 500


@longshort_bp.route('/spread/<acao1>/<acao2>', methods=['GET'])
def obter_spread(acao1, acao2):
    try:
        dias = int(request.args.get('dias', 240))
        
        tickers = lss.obter_top_50_acoes_brasileiras()
        data_fim = datetime.now()
        data_inicio = data_fim - timedelta(days=dias)
        
        dados = lss.obter_dados(tickers, data_inicio, data_fim)
        
        spread_data = lss.calcular_spread_serie(dados, acao1, acao2)
        
        return jsonify({
            'sucesso': True,
            'spread': spread_data
        }), 200
        
    except Exception as e:
        return jsonify({
            'sucesso': False,
            'erro': str(e)
        }), 500


@longshort_bp.route('/beta/<acao1>/<acao2>', methods=['GET'])
def obter_beta(acao1, acao2):
    try:
        dias = int(request.args.get('dias', 240))
        janela = int(request.args.get('janela', 60))
        
        tickers = lss.obter_top_50_acoes_brasileiras()
        data_fim = datetime.now()
        data_inicio = data_fim - timedelta(days=dias)
        
        dados = lss.obter_dados(tickers, data_inicio, data_fim)
        
        beta_data = lss.calcular_beta_rotativo_serie(dados, acao1, acao2, janela)
        
        if beta_data is None:
            return jsonify({
                'sucesso': False,
                'erro': 'Nao foi possivel calcular o beta'
            }), 400
        
        beta_atual = beta_data['beta'][-1]
        analise = lss.analisar_beta_rotativo(
            None,
            beta_atual,
            beta_data['mediaBeta'],
            beta_data['desvioPadraoBeta']
        )
        
        return jsonify({
            'sucesso': True,
            'beta': beta_data,
            'analise': analise
        }), 200
        
    except Exception as e:
        return jsonify({
            'sucesso': False,
            'erro': str(e)
        }), 500


@longshort_bp.route('/estabilidade/<acao1>/<acao2>', methods=['GET'])
def obter_estabilidade(acao1, acao2):
    try:
        dias = int(request.args.get('dias', 240))
        
        tickers = lss.obter_top_50_acoes_brasileiras()
        data_fim = datetime.now()
        data_inicio = data_fim - timedelta(days=dias)
        
        dados = lss.obter_dados(tickers, data_inicio, data_fim)
        
        periodos = [60, 90, 120, 140, 180]
        df_estabilidade = lss.analisar_cointegration_stability(dados, acao1, acao2, periodos)
        
        resultados = []
        for _, row in df_estabilidade.iterrows():
            resultados.append({
                'periodo': int(row['Periodo']),
                'pvalorCoint': float(row['PvalorCoint']),
                'meiaVida': float(row['MeiaVida']) if row['MeiaVida'] else None,
                'r2': float(row['R2']),
                'status': row['Status']
            })
        
        # Diagnóstico
        periodos_cointegrados = df_estabilidade['Status'].eq('Cointegrado').sum()
        total_periodos = len(df_estabilidade)
        r2_medio = df_estabilidade['R2'].mean()
        
        if periodos_cointegrados == total_periodos:
            diagnostico = "Cointegração estável em todos os períodos"
        elif periodos_cointegrados >= total_periodos * 0.7:
            diagnostico = "Cointegração presente na maioria dos períodos"
        else:
            diagnostico = "Períodos sem cointegração detectados"
        
        return jsonify({
            'sucesso': True,
            'periodos': resultados,
            'diagnostico': {
                'periodosCointegrados': int(periodos_cointegrados),
                'totalPeriodos': int(total_periodos),
                'r2Medio': float(r2_medio),
                'mensagem': diagnostico
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'sucesso': False,
            'erro': str(e)
        }), 500


@longshort_bp.route('/margem', methods=['POST'])
def calcular_margem():
    try:
        data = request.json
        valor_vendido = data.get('valorVendido', 0)
        valor_comprado = data.get('valorComprado', 0)
        percentual_garantia = data.get('percentualGarantia', 25.0)
        taxa_btc_anual = data.get('taxaBtcAnual', 2.0)
        dias_operacao = data.get('diasOperacao', 10)
        taxa_corretora_btc = data.get('taxaCorretoraBtc', 35.0)
        
        resultado = lss.calcular_margem_custos(
            valor_vendido,
            valor_comprado,
            percentual_garantia,
            taxa_btc_anual,
            dias_operacao,
            taxa_corretora_btc
        )
        
        return jsonify({
            'sucesso': True,
            'margem': resultado
        }), 200
        
    except Exception as e:
        return jsonify({
            'sucesso': False,
            'erro': str(e)
        }), 500


@longshort_bp.route('/setores', methods=['GET'])
def obter_setores():
    return jsonify({
        'sucesso': True,
        'setores': lss.SETORES
    }), 200


@longshort_bp.route('/acoes', methods=['GET'])
def obter_acoes():
    return jsonify({
        'sucesso': True,
        'acoes': lss.obter_top_50_acoes_brasileiras()
    }), 200
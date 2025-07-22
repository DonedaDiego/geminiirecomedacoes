# antifragil_routes.py - Rotas Flask para Indicador Antifrágil

from flask import Blueprint, jsonify, request, render_template
from pro.antifragil_service import antifragil_service
import logging

logger = logging.getLogger(__name__)

# Blueprint para as rotas do Indicador Antifrágil
antifragil_bp = Blueprint('antifragil', __name__, url_prefix='/api/antifragil')

@antifragil_bp.route('/ranking', methods=['GET'])
def obter_ranking():
    try:
        # Parâmetros da requisição
        limite = int(request.args.get('limite', 20))
        periodo_dias = int(request.args.get('periodo_dias', 252))
        
        # Validações
        if limite < 1 or limite > 100:
            return jsonify({
                'erro': 'Limite deve estar entre 1 e 100',
                'codigo': 'LIMITE_INVALIDO'
            }), 400
        
        if periodo_dias < 30 or periodo_dias > 1000:
            return jsonify({
                'erro': 'Período deve estar entre 30 e 1000 dias',
                'codigo': 'PERIODO_INVALIDO'
            }), 400
        
        # Obter ranking
        ranking = antifragil_service.obter_ranking_antifragil(
            limite=limite,
            periodo_dias=periodo_dias
        )
        
        return jsonify({
            'sucesso': True,
            'data': ranking,
            'total': len(ranking),
            'parametros': {
                'limite': limite,
                'periodo_dias': periodo_dias
            },
            'metodologia': {
                'nome': 'AFIV Score - Indicador Antifrágil',
                'descricao': 'Retorno médio do ativo nos dias de stress do mercado (aumento >5% na IV)',
                'interpretacao': {
                    'muito_antifragil': '>= 1.5%',
                    'antifragil': '0.5% a 1.5%',
                    'neutro': '-0.5% a 0.5%',
                    'fragil': '-1.5% a -0.5%',
                    'muito_fragil': '< -1.5%'
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Erro no endpoint ranking: {e}")
        return jsonify({
            'erro': 'Erro interno do servidor',
            'codigo': 'ERRO_INTERNO',
            'detalhes': str(e)
        }), 500

@antifragil_bp.route('/ativo/<string:ticker>', methods=['GET'])
def analisar_ativo(ticker):
    try:
        if not ticker or len(ticker) > 10:
            return jsonify({
                'erro': 'Código do ativo inválido',
                'codigo': 'TICKER_INVALIDO'
            }), 400
        
        periodo_dias = int(request.args.get('periodo_dias', 252))
        
        if periodo_dias < 30 or periodo_dias > 1000:
            return jsonify({
                'erro': 'Período deve estar entre 30 e 1000 dias',
                'codigo': 'PERIODO_INVALIDO'
            }), 400
        
        # Analisar ativo
        resultado = antifragil_service.analisar_ativo_antifragil(
            ticker.upper(), 
            periodo_dias
        )
        
        if not resultado['success']:
            return jsonify({
                'erro': resultado.get('error', 'Erro na análise'),
                'codigo': 'ERRO_ANALISE'
            }), 404
        
        return jsonify({
            'sucesso': True,
            'data': resultado
        })
        
    except Exception as e:
        logger.error(f"Erro no endpoint ativo {ticker}: {e}")
        return jsonify({
            'erro': 'Erro interno do servidor',
            'codigo': 'ERRO_INTERNO',
            'detalhes': str(e)
        }), 500

@antifragil_bp.route('/estatisticas', methods=['GET'])
def obter_estatisticas():
    try:
        estatisticas = antifragil_service.obter_estatisticas_antifragil()
        
        return jsonify({
            'sucesso': True,
            'data': estatisticas
        })
        
    except Exception as e:
        logger.error(f"Erro no endpoint estatisticas: {e}")
        return jsonify({
            'erro': 'Erro interno do servidor',
            'codigo': 'ERRO_INTERNO',
            'detalhes': str(e)
        }), 500

@antifragil_bp.route('/explicacao', methods=['GET'])
def obter_explicacao():
    try:
        explicacao = {
            'nome': 'Indicador Antifrágil (AFIV Score)',
            'conceito': 'Baseado no conceito de Antifragilidade de Nassim Nicholas Taleb',
            'objetivo': 'Identificar ativos que se beneficiam de períodos de stress e alta volatilidade no mercado',
            'metodologia': {
                'passo_1': 'Identificar dias de stress: aumento >5% na volatilidade implícita do mercado (IBOV)',
                'passo_2': 'Calcular retorno médio do ativo especificamente nos dias de stress',
                'passo_3': 'AFIV Score = Retorno médio nos dias de stress (em %)',
                'passo_4': 'Ranking dos ativos por AFIV Score (maior = mais antifrágil)'
            },
            'interpretacao': {
                'muito_antifragil': {
                    'range': '>= 1.5%',
                    'descricao': 'Ativo se beneficia significativamente dos períodos de stress',
                    'estrategia': 'Excelente para proteção e crescimento em crises'
                },
                'antifragil': {
                    'range': '0.5% a 1.5%',
                    'descricao': 'Ativo apresenta performance positiva em stress',
                    'estrategia': 'Boa opção para diversificação defensiva'
                },
                'neutro': {
                    'range': '-0.5% a 0.5%',
                    'descricao': 'Ativo não apresenta comportamento especial em stress',
                    'estrategia': 'Comportamento típico do mercado'
                },
                'fragil': {
                    'range': '-1.5% a -0.5%',
                    'descricao': 'Ativo sofre em períodos de stress',
                    'estrategia': 'Evitar em cenários de incerteza'
                },
                'muito_fragil': {
                    'range': '< -1.5%',
                    'descricao': 'Ativo é severamente impactado por stress',
                    'estrategia': 'Alto risco em períodos de volatilidade'
                }
            },
            'aplicacoes': [
                'Construção de carteiras defensivas',
                'Hedge contra crises e volatilidade',
                'Identificação de oportunidades em momentos de stress',
                'Complemento a análises fundamentalistas tradicionais',
                'Estratégias de long/short baseadas em antifragilidade'
            ],
            'limitacoes': [
                'Baseado em dados históricos (performance passada)',
                'Requer dados de volatilidade implícita de qualidade',
                'Pode não capturar mudanças estruturais no ativo',
                'Funciona melhor em períodos com múltiplos eventos de stress'
            ],
            'dados_necessarios': {
                'ativo': 'Preços históricos, volatilidade implícita (quando disponível)',
                'mercado': 'Volatilidade implícita do IBOV/BOVA11 como proxy',
                'periodo': 'Mínimo 6 meses, ideal 1 ano para resultados robustos'
            },
            'referencias': {
                'livro': 'Antifragile: Things That Gain from Disorder - Nassim Nicholas Taleb',
                'conceito': 'Sistemas que não apenas resistem ao stress, mas se beneficiam dele'
            }
        }
        
        return jsonify({
            'sucesso': True,
            'data': explicacao
        })
        
    except Exception as e:
        logger.error(f"Erro no endpoint explicacao: {e}")
        return jsonify({
            'erro': 'Erro interno do servidor',
            'codigo': 'ERRO_INTERNO'
        }), 500

@antifragil_bp.route('/comparar', methods=['POST'])

def comparar_ativos():

    try:
        data = request.get_json()
        
        if not data or 'tickers' not in data:
            return jsonify({
                'erro': 'Lista de tickers é obrigatória',
                'codigo': 'TICKERS_OBRIGATORIOS'
            }), 400
        
        tickers = data['tickers']
        periodo_dias = data.get('periodo_dias', 252)
        
        if not isinstance(tickers, list) or len(tickers) == 0:
            return jsonify({
                'erro': 'Lista de tickers deve ser um array não vazio',
                'codigo': 'LISTA_INVALIDA'
            }), 400
        
        if len(tickers) > 10:
            return jsonify({
                'erro': 'Máximo de 10 ativos por comparação',
                'codigo': 'LIMITE_COMPARACAO'
            }), 400
        
        if periodo_dias < 30 or periodo_dias > 1000:
            return jsonify({
                'erro': 'Período deve estar entre 30 e 1000 dias',
                'codigo': 'PERIODO_INVALIDO'
            }), 400
        
        # Analisar cada ativo
        resultados = []
        nao_encontrados = []
        
        for ticker in tickers:
            try:
                resultado = antifragil_service.analisar_ativo_antifragil(
                    ticker.upper(), 
                    periodo_dias
                )
                
                if resultado['success']:
                    resultados.append(resultado)
                else:
                    nao_encontrados.append(ticker.upper())
                    
            except Exception as e:
                logger.warning(f"Erro ao analisar {ticker}: {e}")
                nao_encontrados.append(ticker.upper())
        
        if not resultados:
            return jsonify({
                'erro': 'Nenhum ativo encontrado',
                'codigo': 'NENHUM_ATIVO_ENCONTRADO',
                'nao_encontrados': nao_encontrados
            }), 404
        
        # Calcular rankings relativos entre os ativos comparados
        if len(resultados) > 1:
            # Ordenar por AFIV Score
            resultados_ordenados = sorted(resultados, key=lambda x: x['afiv_score'], reverse=True)
            
            # Adicionar ranking relativo
            for i, resultado in enumerate(resultados_ordenados):
                resultado['ranking_relativo'] = i + 1
            
            # Calcular estatísticas do grupo
            afiv_scores = [r['afiv_score'] for r in resultados]
            estatisticas_grupo = {
                'afiv_medio': sum(afiv_scores) / len(afiv_scores),
                'afiv_max': max(afiv_scores),
                'afiv_min': min(afiv_scores),
                'amplitude': max(afiv_scores) - min(afiv_scores),
                'total_analisados': len(resultados)
            }
        else:
            resultados_ordenados = resultados
            resultados_ordenados[0]['ranking_relativo'] = 1
            estatisticas_grupo = {
                'afiv_medio': resultados[0]['afiv_score'],
                'afiv_max': resultados[0]['afiv_score'],
                'afiv_min': resultados[0]['afiv_score'],
                'amplitude': 0,
                'total_analisados': 1
            }
        
        return jsonify({
            'sucesso': True,
            'data': {
                'ativos': resultados_ordenados,
                'estatisticas_grupo': estatisticas_grupo,
                'nao_encontrados': nao_encontrados,
                'parametros': {
                    'periodo_dias': periodo_dias,
                    'total_solicitados': len(tickers),
                    'total_analisados': len(resultados)
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Erro no endpoint comparar: {e}")
        return jsonify({
            'erro': 'Erro interno do servidor',
            'codigo': 'ERRO_INTERNO',
            'detalhes': str(e)
        }), 500

@antifragil_bp.route('/setores', methods=['GET'])
def analisar_por_setores():
    """
    Endpoint para análise antifrágil por setores
    """
    try:
        # Esta funcionalidade pode ser expandida quando houver dados de setor
        # Por enquanto, retorna informação básica
        
        return jsonify({
            'sucesso': True,
            'data': {
                'mensagem': 'Análise por setores em desenvolvimento',
                'disponivel_em': 'Versão futura com dados setoriais',
                'alternativa': 'Use o endpoint /ranking para ver todos os ativos'
            }
        })
        
    except Exception as e:
        logger.error(f"Erro no endpoint setores: {e}")
        return jsonify({
            'erro': 'Erro interno do servidor',
            'codigo': 'ERRO_INTERNO'
        }), 500

@antifragil_bp.route('/stress-days', methods=['GET'])
def obter_dias_stress():
    """
    Endpoint para obter informações sobre dias de stress do mercado
    
    Query Parameters:
    - periodo_dias: Período de análise em dias (padrão: 252)
    """
    try:
        periodo_dias = int(request.args.get('periodo_dias', 252))
        
        if periodo_dias < 30 or periodo_dias > 1000:
            return jsonify({
                'erro': 'Período deve estar entre 30 e 1000 dias',
                'codigo': 'PERIODO_INVALIDO'
            }), 400
        
        # Obter dados do mercado
        dados_mercado = antifragil_service.obter_dados_mercado_ibov(periodo_dias)
        
        if dados_mercado.empty:
            return jsonify({
                'erro': 'Não foi possível obter dados do mercado',
                'codigo': 'ERRO_DADOS_MERCADO'
            }), 500
        
        # Calcular dias de stress
        dados_mercado = antifragil_service.calcular_dias_stress(dados_mercado)
        
        # Preparar estatísticas
        total_dias = len(dados_mercado.dropna(subset=['delta_iv_mercado']))
        dias_stress = dados_mercado['stress_day'].sum()
        percentual_stress = (dias_stress / total_dias * 100) if total_dias > 0 else 0
        
        # Últimos dias de stress
        stress_recentes = dados_mercado[dados_mercado['stress_day'] == 1].tail(10)
        dias_stress_lista = []
        
        for idx, row in stress_recentes.iterrows():
            dias_stress_lista.append({
                'data': idx.strftime('%Y-%m-%d'),
                'delta_iv_mercado': float(row['delta_iv_mercado']),
                'iv_mercado': float(row.get('iv_mercado', 0)),
                'retorno_mercado': float(row.get('retorno_mercado', 0)) * 100
            })
        
        return jsonify({
            'sucesso': True,
            'data': {
                'periodo_dias': periodo_dias,
                'total_dias_analisados': int(total_dias),
                'total_dias_stress': int(dias_stress),
                'percentual_stress': round(percentual_stress, 2),
                'threshold_stress': antifragil_service.stress_threshold,
                'ultimos_stress_days': dias_stress_lista,
                'interpretacao': {
                    'definicao': 'Dias com aumento >5% na volatilidade implícita do mercado',
                    'impacto': 'Períodos de maior incerteza e oportunidade para ativos antifrágeis'
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Erro no endpoint stress-days: {e}")
        return jsonify({
            'erro': 'Erro interno do servidor',
            'codigo': 'ERRO_INTERNO',
            'detalhes': str(e)
        }), 500

# Endpoints para views HTML (se necessário)
@antifragil_bp.route('/dashboard')
def dashboard():
    """Página do dashboard do Indicador Antifrágil"""
    try:
        # Obter dados básicos
        ranking = antifragil_service.obter_ranking_antifragil(limite=10)
        estatisticas = antifragil_service.obter_estatisticas_antifragil()
        
        return render_template('antifragil_dashboard.html', 
                             ranking=ranking, 
                             estatisticas=estatisticas)
    except Exception as e:
        logger.error(f"Erro no dashboard: {e}")
        return render_template('error.html', error=str(e)), 500

# Tratamento de erros específicos do blueprint
@antifragil_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'erro': 'Endpoint não encontrado',
        'codigo': 'ENDPOINT_NAO_ENCONTRADO'
    }), 404

@antifragil_bp.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        'erro': 'Método HTTP não permitido',
        'codigo': 'METODO_NAO_PERMITIDO'
    }), 405

@antifragil_bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        'erro': 'Erro interno do servidor',
        'codigo': 'ERRO_INTERNO'
    }), 500
# formula_routes.py - Rotas Flask para Fórmula Mágica Joel Greenblatt

from flask import Blueprint, jsonify, request, render_template
from gratis.formula_service import formula_service
import logging

logger = logging.getLogger(__name__)

# Blueprint para as rotas da Fórmula Mágica
formula_bp = Blueprint('formula', __name__, url_prefix='/api/formula')

@formula_bp.route('/ranking', methods=['GET'])
def obter_ranking():
    """
    Endpoint para obter o ranking da Fórmula Mágica
    
    Query Parameters:
    - limite: Número de empresas no ranking (padrão: 20)
    - filtrar_liquidez: Se deve filtrar por liquidez (padrão: true)
    - liquidez_minima: Valor mínimo de liquidez (padrão: 1000000)
    """
    try:
        # Parâmetros da requisição
        limite = int(request.args.get('limite', 20))
        filtrar_liquidez = request.args.get('filtrar_liquidez', 'true').lower() == 'true'
        liquidez_minima = float(request.args.get('liquidez_minima', 1000000))
        
        # Validações
        if limite < 1 or limite > 100:
            return jsonify({
                'erro': 'Limite deve estar entre 1 e 100',
                'codigo': 'LIMITE_INVALIDO'
            }), 400
        
        # Obter ranking
        ranking = formula_service.obter_top_formula_magica(
            limite=limite,
            filtrar_liquidez=filtrar_liquidez,
            liquidez_minima=liquidez_minima
        )
        
        return jsonify({
            'sucesso': True,
            'data': ranking,
            'total': len(ranking),
            'parametros': {
                'limite': limite,
                'filtrar_liquidez': filtrar_liquidez,
                'liquidez_minima': liquidez_minima
            }
        })
        
    except Exception as e:
        logger.error(f"Erro no endpoint ranking: {e}")
        return jsonify({
            'erro': 'Erro interno do servidor',
            'codigo': 'ERRO_INTERNO',
            'detalhes': str(e)
        }), 500

@formula_bp.route('/empresa/<string:papel>', methods=['GET'])
def obter_empresa(papel):
    """
    Endpoint para obter dados de uma empresa específica
    
    Path Parameters:
    - papel: Código da empresa (ex: PETR4)
    """
    try:
        if not papel or len(papel) > 10:
            return jsonify({
                'erro': 'Código do papel inválido',
                'codigo': 'PAPEL_INVALIDO'
            }), 400
        
        # Buscar empresa
        empresa = formula_service.buscar_empresa(papel.upper())
        
        if not empresa:
            return jsonify({
                'erro': f'Empresa {papel.upper()} não encontrada',
                'codigo': 'EMPRESA_NAO_ENCONTRADA'
            }), 404
        
        return jsonify({
            'sucesso': True,
            'data': empresa
        })
        
    except Exception as e:
        logger.error(f"Erro no endpoint empresa {papel}: {e}")
        return jsonify({
            'erro': 'Erro interno do servidor',
            'codigo': 'ERRO_INTERNO',
            'detalhes': str(e)
        }), 500

@formula_bp.route('/estatisticas', methods=['GET'])
def obter_estatisticas():
    """
    Endpoint para obter estatísticas da base de dados
    """
    try:
        estatisticas = formula_service.obter_estatisticas_base()
        
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

@formula_bp.route('/explicacao', methods=['GET'])
def obter_explicacao():
    """
    Endpoint para obter explicação sobre a Fórmula Mágica
    """
    try:
        explicacao = {
            'nome': 'Fórmula Mágica do Joel Greenblatt',
            'autor': 'Joel Greenblatt',
            'livro': 'The Little Book That Beats the Market',
            'objetivo': 'Encontrar empresas de qualidade negociadas a preços atrativos',
            'criterios': [
                {
                    'nome': 'ROIC (Return on Invested Capital)',
                    'descricao': 'Mede a eficiência da empresa em gerar lucro com o capital investido',
                    'formula': 'EBIT / Capital Investido',
                    'interpretacao': 'Quanto maior, melhor. Indica qualidade da empresa.'
                },
                {
                    'nome': 'Earnings Yield',
                    'descricao': 'Mede o retorno dos lucros em relação ao valor da empresa',
                    'formula': 'EBIT / Enterprise Value',
                    'interpretacao': 'Quanto maior, melhor. Indica preço atrativo.'
                }
            ],
            'metodologia': [
                '1. Rankear todas as empresas por ROIC (maior = melhor)',
                '2. Rankear todas as empresas por Earnings Yield (maior = melhor)',
                '3. Somar os dois rankings para cada empresa',
                '4. Ordenar pela soma (menor soma = melhor posição)',
                '5. Investir nas empresas com melhor posição no ranking combinado'
            ],
            'vantagens': [
                'Estratégia quantitativa e objetiva',
                'Combina qualidade (ROIC) com preço (Earnings Yield)',
                'Histórico de performance superior ao mercado',
                'Simples de entender e aplicar'
            ],
            'limitacoes': [
                'Baseada em dados históricos',
                'Não considera fatores qualitativos',
                'Pode incluir empresas em dificuldades temporárias',
                'Requer disciplina para seguir a estratégia'
            ]
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

@formula_bp.route('/filtros', methods=['GET'])
def obter_opcoes_filtros():
    """
    Endpoint para obter opções de filtros disponíveis
    """
    try:
        filtros = {
            'limite': {
                'min': 1,
                'max': 100,
                'default': 20,
                'descricao': 'Número de empresas no ranking'
            },
            'filtrar_liquidez': {
                'type': 'boolean',
                'default': True,
                'descricao': 'Se deve filtrar empresas por liquidez mínima'
            },
            'liquidez_minima': {
                'min': 0,
                'max': 10000000,
                'default': 1000000,
                'descricao': 'Valor mínimo de liquidez em 2 meses (R$)'
            },
            'setores_disponiveis': [
                'Todos',
                'Bancos',
                'Energia Elétrica',
                'Petróleo e Gás',
                'Siderurgia',
                'Telecomunicações',
                'Varejo'
            ]
        }
        
        return jsonify({
            'sucesso': True,
            'data': filtros
        })
        
    except Exception as e:
        logger.error(f"Erro no endpoint filtros: {e}")
        return jsonify({
            'erro': 'Erro interno do servidor',
            'codigo': 'ERRO_INTERNO'
        }), 500

@formula_bp.route('/comparar', methods=['POST'])
def comparar_empresas():
    """
    Endpoint para comparar múltiplas empresas
    
    Body JSON:
    {
        "papeis": ["PETR4", "VALE3", "ITUB4"]
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'papeis' not in data:
            return jsonify({
                'erro': 'Lista de papéis é obrigatória',
                'codigo': 'PAPEIS_OBRIGATORIOS'
            }), 400
        
        papeis = data['papeis']
        
        if not isinstance(papeis, list) or len(papeis) == 0:
            return jsonify({
                'erro': 'Lista de papéis deve ser um array não vazio',
                'codigo': 'LISTA_INVALIDA'
            }), 400
        
        if len(papeis) > 10:
            return jsonify({
                'erro': 'Máximo de 10 empresas por comparação',
                'codigo': 'LIMITE_COMPARACAO'
            }), 400
        
        # Buscar dados das empresas
        empresas = []
        nao_encontradas = []
        
        for papel in papeis:
            empresa = formula_service.buscar_empresa(papel.upper())
            if empresa:
                empresas.append(empresa)
            else:
                nao_encontradas.append(papel.upper())
        
        if not empresas:
            return jsonify({
                'erro': 'Nenhuma empresa encontrada',
                'codigo': 'NENHUMA_EMPRESA_ENCONTRADA',
                'nao_encontradas': nao_encontradas
            }), 404
        
        # Calcular rankings relativos entre as empresas comparadas
        if len(empresas) > 1:
            import pandas as pd
            df_comparacao = pd.DataFrame(empresas)
            
            # Rankings relativos
            df_comparacao['rank_roic_relativo'] = df_comparacao['roic_num'].rank(ascending=False)
            df_comparacao['rank_earnings_yield_relativo'] = df_comparacao['earnings_yield'].rank(ascending=False)
            df_comparacao['rank_combinado_relativo'] = (df_comparacao['rank_roic_relativo'] + 
                                                       df_comparacao['rank_earnings_yield_relativo'])
            
            # Atualizar os dados
            for i, empresa in enumerate(empresas):
                empresa['rank_roic_relativo'] = int(df_comparacao.iloc[i]['rank_roic_relativo'])
                empresa['rank_earnings_yield_relativo'] = int(df_comparacao.iloc[i]['rank_earnings_yield_relativo'])
                empresa['rank_combinado_relativo'] = float(df_comparacao.iloc[i]['rank_combinado_relativo'])
        
        return jsonify({
            'sucesso': True,
            'data': {
                'empresas': empresas,
                'total_comparadas': len(empresas),
                'nao_encontradas': nao_encontradas
            }
        })
        
    except Exception as e:
        logger.error(f"Erro no endpoint comparar: {e}")
        return jsonify({
            'erro': 'Erro interno do servidor',
            'codigo': 'ERRO_INTERNO',
            'detalhes': str(e)
        }), 500

# Endpoints para views HTML (se necessário)
@formula_bp.route('/dashboard')
def dashboard():
    """Página do dashboard da Fórmula Mágica"""
    try:
        # Obter dados básicos
        ranking = formula_service.obter_top_formula_magica(limite=10)
        estatisticas = formula_service.obter_estatisticas_base()
        
        return render_template('formula_dashboard.html', 
                             ranking=ranking, 
                             estatisticas=estatisticas)
    except Exception as e:
        logger.error(f"Erro no dashboard: {e}")
        return render_template('error.html', error=str(e)), 500

# Tratamento de erros específicos do blueprint
@formula_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'erro': 'Endpoint não encontrado',
        'codigo': 'ENDPOINT_NAO_ENCONTRADO'
    }), 404

@formula_bp.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        'erro': 'Método HTTP não permitido',
        'codigo': 'METODO_NAO_PERMITIDO'
    }), 405

@formula_bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        'erro': 'Erro interno do servidor',
        'codigo': 'ERRO_INTERNO'
    }), 500
# golden_cross_eua_routes.py - Rotas da API do Golden Cross EUA

from flask import Blueprint, jsonify, request
from premium.golden_cross_eua_service import golden_cross_eua_service
import logging

logger = logging.getLogger(__name__)

# Criar blueprint para as rotas
golden_cross_eua_bp = Blueprint('golden_cross_eua', __name__, url_prefix='/api/golden-cross-eua')

@golden_cross_eua_bp.route('/estatisticas', methods=['GET'])
def obter_estatisticas():
    """Obtém estatísticas gerais do Golden Cross EUA"""
    try:
        logger.info(" Solicitação de estatísticas Golden Cross EUA")
        
        estatisticas = golden_cross_eua_service.obter_estatisticas_golden_cross()
        
        return jsonify({
            'sucesso': True,
            'data': estatisticas,
            'timestamp': estatisticas.get('ultima_atualizacao')
        })
        
    except Exception as e:
        logger.error(f" Erro ao obter estatísticas Golden Cross EUA: {e}")
        return jsonify({
            'sucesso': False,
            'erro': str(e)
        }), 500

@golden_cross_eua_bp.route('/ranking', methods=['GET'])
def obter_ranking():
    """Obtém ranking das ações com melhor setup de Golden Cross"""
    try:
        # Parâmetros da requisição
        limite = int(request.args.get('limite', 50))
        
        if limite < 1 or limite > 100:
            return jsonify({
                'sucesso': False,
                'erro': 'Limite deve estar entre 1 e 100'
            }), 400
        
        logger.info(f" Solicitação de ranking Golden Cross EUA (limite: {limite})")
        
        # Gerar ranking
        ranking = golden_cross_eua_service.obter_ranking_golden_cross(limite)
        
        if not ranking:
            logger.warning("⚠️ Nenhum dado encontrado para o ranking")
            return jsonify({
                'sucesso': False,
                'erro': 'Nenhum dado disponível para ranking'
            }), 404
        
        # Estatísticas do ranking
        total_golden_ativo = len([r for r in ranking if r['status_atual'] == 'GOLDEN_CROSS_ATIVO'])
        total_sobrecompra = len([r for r in ranking if r['status_atual'] == 'GOLDEN_CROSS_SOBRECOMPRA'])
        score_medio = sum(r['score'] for r in ranking) / len(ranking)
        
        response_data = {
            'sucesso': True,
            'data': ranking,
            'metadados': {
                'total_retornado': len(ranking),
                'limite_solicitado': limite,
                'total_golden_ativo': total_golden_ativo,
                'total_sobrecompra': total_sobrecompra,
                'score_medio': round(score_medio, 2),
                'melhor_score': ranking[0]['score'] if ranking else 0,
                'pior_score': ranking[-1]['score'] if ranking else 0
            }
        }
        
        logger.info(f" Ranking Golden Cross EUA retornado: {len(ranking)} ações")
        
        return jsonify(response_data)
        
    except ValueError as e:
        logger.error(f" Erro de validação: {e}")
        return jsonify({
            'sucesso': False,
            'erro': 'Parâmetros inválidos'
        }), 400
        
    except Exception as e:
        logger.error(f" Erro ao gerar ranking Golden Cross EUA: {e}")
        return jsonify({
            'sucesso': False,
            'erro': str(e)
        }), 500

@golden_cross_eua_bp.route('/acao/<ticker>', methods=['GET'])
def obter_analise_acao(ticker):
    """Obtém análise detalhada de uma ação específica"""
    try:
        # Validar ticker
        if not ticker or len(ticker) > 10:
            return jsonify({
                'sucesso': False,
                'erro': 'Ticker inválido'
            }), 400
        
        # Parâmetros opcionais
        periodo_dias = int(request.args.get('periodo_dias', 365))
        
        if periodo_dias < 100 or periodo_dias > 1000:
            return jsonify({
                'sucesso': False,
                'erro': 'Período deve estar entre 100 e 1000 dias'
            }), 400
        
        logger.info(f"🔍 Solicitação de análise Golden Cross para {ticker.upper()}")
        
        # Buscar dados da empresa na lista
        empresas = golden_cross_eua_service.obter_top_50_empresas_eua()
        empresa_info = next((e for e in empresas if e['ticker'].upper() == ticker.upper()), None)
        
        if not empresa_info:
            return jsonify({
                'sucesso': False,
                'erro': f'Ação {ticker.upper()} não está na lista das 50 maiores empresas americanas'
            }), 404
        
        # Realizar análise
        resultado = golden_cross_eua_service.analisar_acao_golden_cross(
            ticker.upper(),
            empresa_info['nome'],
            empresa_info['setor'],
            periodo_dias
        )
        
        if not resultado['success']:
            logger.warning(f"⚠️ Falha na análise de {ticker}: {resultado.get('error')}")
            return jsonify({
                'sucesso': False,
                'erro': resultado.get('error', 'Erro na análise')
            }), 404
        
        # Calcular score para contexto
        score = golden_cross_eua_service._calcular_score_golden_cross(resultado)
        resultado['score'] = score
        
        logger.info(f" Análise Golden Cross concluída para {ticker}: {resultado['status_atual']}")
        
        return jsonify({
            'sucesso': True,
            'data': resultado
        })
        
    except ValueError as e:
        logger.error(f" Erro de validação para {ticker}: {e}")
        return jsonify({
            'sucesso': False,
            'erro': 'Parâmetros inválidos'
        }), 400
        
    except Exception as e:
        logger.error(f" Erro na análise de {ticker}: {e}")
        return jsonify({
            'sucesso': False,
            'erro': str(e)
        }), 500

@golden_cross_eua_bp.route('/setores', methods=['GET'])
def obter_ranking_por_setor():
    """Obtém ranking agrupado por setor"""
    try:
        logger.info("🏢 Solicitação de ranking por setor")
        
        # Obter ranking completo
        ranking_completo = golden_cross_eua_service.obter_ranking_golden_cross(50)
        
        if not ranking_completo:
            return jsonify({
                'sucesso': False,
                'erro': 'Nenhum dado disponível'
            }), 404
        
        # Agrupar por setor
        setores = {}
        for acao in ranking_completo:
            setor = acao['setor']
            if setor not in setores:
                setores[setor] = {
                    'nome_setor': setor,
                    'acoes': [],
                    'estatisticas': {
                        'total_acoes': 0,
                        'golden_cross_ativo': 0,
                        'score_medio': 0,
                        'melhor_performance_30d': 0,
                        'acoes_rsi_ok': 0
                    }
                }
            
            setores[setor]['acoes'].append(acao)
        
        # Calcular estatísticas por setor
        for setor_nome, setor_data in setores.items():
            acoes = setor_data['acoes']
            stats = setor_data['estatisticas']
            
            stats['total_acoes'] = len(acoes)
            stats['golden_cross_ativo'] = len([a for a in acoes if a['status_atual'] == 'GOLDEN_CROSS_ATIVO'])
            stats['score_medio'] = round(sum(a['score'] for a in acoes) / len(acoes), 2)
            stats['melhor_performance_30d'] = max(a['retorno_30d'] for a in acoes)
            stats['acoes_rsi_ok'] = len([a for a in acoes if a['rsi'] < 70])
            
            # Ordenar ações do setor por score
            setor_data['acoes'].sort(key=lambda x: x['score'], reverse=True)
        
        # Ordenar setores por score médio
        setores_ordenados = sorted(setores.values(), key=lambda x: x['estatisticas']['score_medio'], reverse=True)
        
        logger.info(f" Ranking por setor retornado: {len(setores_ordenados)} setores")
        
        return jsonify({
            'sucesso': True,
            'data': setores_ordenados,
            'metadados': {
                'total_setores': len(setores_ordenados),
                'total_acoes': len(ranking_completo)
            }
        })
        
    except Exception as e:
        logger.error(f" Erro ao obter ranking por setor: {e}")
        return jsonify({
            'sucesso': False,
            'erro': str(e)
        }), 500

@golden_cross_eua_bp.route('/empresas', methods=['GET'])
def listar_empresas():
    """Lista todas as empresas disponíveis para análise"""
    try:
        logger.info("📋 Solicitação de lista de empresas")
        
        empresas = golden_cross_eua_service.obter_top_50_empresas_eua()
        
        # Agrupar por setor para facilitar visualização
        empresas_por_setor = {}
        for empresa in empresas:
            setor = empresa['setor']
            if setor not in empresas_por_setor:
                empresas_por_setor[setor] = []
            empresas_por_setor[setor].append({
                'ticker': empresa['ticker'],
                'nome': empresa['nome']
            })
        
        # Ordenar empresas dentro de cada setor
        for setor in empresas_por_setor:
            empresas_por_setor[setor].sort(key=lambda x: x['ticker'])
        
        return jsonify({
            'sucesso': True,
            'data': {
                'empresas_por_setor': empresas_por_setor,
                'lista_completa': empresas
            },
            'metadados': {
                'total_empresas': len(empresas),
                'total_setores': len(empresas_por_setor)
            }
        })
        
    except Exception as e:
        logger.error(f" Erro ao listar empresas: {e}")
        return jsonify({
            'sucesso': False,
            'erro': str(e)
        }), 500

@golden_cross_eua_bp.route('/status', methods=['GET'])
def verificar_status():
    """Verifica status da API e conectividade"""
    try:
        logger.info("🔍 Verificação de status da API")
        
        # Teste rápido com uma ação
        teste = golden_cross_eua_service.obter_dados_acao('AAPL', 50)
        dados_ok = not teste.empty
        
        return jsonify({
            'sucesso': True,
            'status': 'ONLINE',
            'conectividade_yfinance': dados_ok,
            'total_empresas': len(golden_cross_eua_service.obter_top_50_empresas_eua()),
            'versao': '1.0.0'
        })
        
    except Exception as e:
        logger.error(f" Erro na verificação de status: {e}")
        return jsonify({
            'sucesso': False,
            'status': 'ERRO',
            'erro': str(e)
        }), 500

# Middleware para logging de requests
@golden_cross_eua_bp.before_request
def log_request():
    """Log de todas as requisições"""
    logger.info(f"🔄 {request.method} {request.path} - IP: {request.remote_addr}")

@golden_cross_eua_bp.after_request
def log_response(response):
    """Log de todas as respostas"""
    logger.info(f" {request.method} {request.path} - Status: {response.status_code}")
    return response

# Handler de erros
@golden_cross_eua_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'sucesso': False,
        'erro': 'Endpoint não encontrado'
    }), 404

@golden_cross_eua_bp.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        'sucesso': False,
        'erro': 'Método não permitido'
    }), 405

@golden_cross_eua_bp.errorhandler(500)
def internal_error(error):
    logger.error(f" Erro interno do servidor: {error}")
    return jsonify({
        'sucesso': False,
        'erro': 'Erro interno do servidor'
    }), 500
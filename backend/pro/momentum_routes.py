# momentum_routes.py - Rotas da API do Momentum US

from flask import Blueprint, jsonify, request
from datetime import datetime
from pro.momentum_service import momentum_service
import logging

logger = logging.getLogger(__name__)

# Criar blueprint para as rotas
momentum_bp = Blueprint('momentum', __name__, url_prefix='/api/momentum-us')

@momentum_bp.route('/estatisticas', methods=['GET'])
def obter_estatisticas():
    """Obtém estatísticas gerais do Momentum US"""
    try:
        logger.info("📊 Solicitação de estatísticas Momentum US")
        
        estatisticas = momentum_service.obter_estatisticas_momentum()
        
        return jsonify({
            'sucesso': True,
            'data': estatisticas,
            'timestamp': estatisticas.get('ultima_atualizacao')
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao obter estatísticas Momentum US: {e}")
        return jsonify({
            'sucesso': False,
            'erro': str(e)
        }), 500

@momentum_bp.route('/ranking', methods=['GET'])
def obter_ranking():
    """Obtém ranking das ações com melhor momentum"""
    try:
        # Parâmetros da requisição
        limite = int(request.args.get('limite', 50))
        
        if limite < 1 or limite > 100:
            return jsonify({
                'sucesso': False,
                'erro': 'Limite deve estar entre 1 e 100'
            }), 400
        
        logger.info(f"📈 Solicitação de ranking Momentum US (limite: {limite})")
        
        # Gerar ranking
        ranking = momentum_service.obter_ranking_momentum(limite)
        
        if not ranking:
            logger.warning("⚠️ Nenhum dado encontrado para o ranking")
            return jsonify({
                'sucesso': False,
                'erro': 'Nenhum dado disponível para ranking'
            }), 404
        
        # Estatísticas do ranking
        momentum_forte = len([r for r in ranking if r['momentum_score'] >= 65])
        momentum_fraco = len([r for r in ranking if r['momentum_score'] <= 25])
        acima_sma50 = len([r for r in ranking if r['acima_sma50']])
        score_medio = sum(r['momentum_score'] for r in ranking) / len(ranking)
        
        response_data = {
            'sucesso': True,
            'data': ranking,
            'metadados': {
                'total_retornado': len(ranking),
                'limite_solicitado': limite,
                'momentum_forte': momentum_forte,
                'momentum_fraco': momentum_fraco,
                'acima_sma50': acima_sma50,
                'score_medio': round(score_medio, 2),
                'melhor_score': ranking[0]['momentum_score'] if ranking else 0,
                'pior_score': ranking[-1]['momentum_score'] if ranking else 0
            }
        }
        
        logger.info(f"✅ Ranking Momentum US retornado: {len(ranking)} ações")
        
        return jsonify(response_data)
        
    except ValueError as e:
        logger.error(f"❌ Erro de validação: {e}")
        return jsonify({
            'sucesso': False,
            'erro': 'Parâmetros inválidos'
        }), 400
        
    except Exception as e:
        logger.error(f"❌ Erro ao gerar ranking Momentum US: {e}")
        return jsonify({
            'sucesso': False,
            'erro': str(e)
        }), 500

@momentum_bp.route('/acao/<ticker>', methods=['GET'])
def obter_analise_acao(ticker):
    """Obtém análise detalhada de momentum de uma ação específica"""
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
        
        logger.info(f"🔍 Solicitação de análise Momentum para {ticker.upper()}")
        
        # Buscar dados da empresa na lista
        empresas = momentum_service.obter_top_50_empresas_eua()
        empresa_info = next((e for e in empresas if e['ticker'].upper() == ticker.upper()), None)
        
        if not empresa_info:
            return jsonify({
                'sucesso': False,
                'erro': f'Ação {ticker.upper()} não está na lista das 50 maiores empresas americanas'
            }), 404
        
        # Realizar análise
        resultado = momentum_service.analisar_acao_momentum(
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
        
        logger.info(f"✅ Análise Momentum concluída para {ticker}: {resultado['classificacao']} (Score: {resultado['momentum_score']:.1f})")
        
        return jsonify({
            'sucesso': True,
            'data': resultado
        })
        
    except ValueError as e:
        logger.error(f"❌ Erro de validação para {ticker}: {e}")
        return jsonify({
            'sucesso': False,
            'erro': 'Parâmetros inválidos'
        }), 400
        
    except Exception as e:
        logger.error(f"❌ Erro na análise de {ticker}: {e}")
        return jsonify({
            'sucesso': False,
            'erro': str(e)
        }), 500

@momentum_bp.route('/setores', methods=['GET'])
def obter_ranking_por_setor():
    """Obtém ranking de momentum agrupado por setor"""
    try:
        logger.info("🏢 Solicitação de ranking Momentum por setor")
        
        # Obter ranking completo
        ranking_completo = momentum_service.obter_ranking_momentum(50)
        
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
                        'momentum_forte': 0,
                        'score_medio': 0,
                        'melhor_roc_1m': 0,
                        'acoes_acima_sma50': 0,
                        'aceleracao_volume_media': 0
                    }
                }
            
            setores[setor]['acoes'].append(acao)
        
        # Calcular estatísticas por setor
        for setor_nome, setor_data in setores.items():
            acoes = setor_data['acoes']
            stats = setor_data['estatisticas']
            
            stats['total_acoes'] = len(acoes)
            stats['momentum_forte'] = len([a for a in acoes if a['momentum_score'] >= 65])
            stats['score_medio'] = round(sum(a['momentum_score'] for a in acoes) / len(acoes), 2)
            stats['melhor_roc_1m'] = max(a['roc_1m'] for a in acoes)
            stats['acoes_acima_sma50'] = len([a for a in acoes if a['acima_sma50']])
            stats['aceleracao_volume_media'] = round(sum(a['aceleracao_volume'] for a in acoes) / len(acoes), 2)
            
            # Ordenar ações do setor por momentum score
            setor_data['acoes'].sort(key=lambda x: x['momentum_score'], reverse=True)
        
        # Ordenar setores por score médio
        setores_ordenados = sorted(setores.values(), key=lambda x: x['estatisticas']['score_medio'], reverse=True)
        
        logger.info(f"✅ Ranking Momentum por setor retornado: {len(setores_ordenados)} setores")
        
        return jsonify({
            'sucesso': True,
            'data': setores_ordenados,
            'metadados': {
                'total_setores': len(setores_ordenados),
                'total_acoes': len(ranking_completo)
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao obter ranking por setor: {e}")
        return jsonify({
            'sucesso': False,
            'erro': str(e)
        }), 500

@momentum_bp.route('/empresas', methods=['GET'])
def listar_empresas():
    """Lista todas as empresas disponíveis para análise de momentum"""
    try:
        logger.info("📋 Solicitação de lista de empresas para momentum")
        
        empresas = momentum_service.obter_top_50_empresas_eua()
        
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
        logger.error(f"❌ Erro ao listar empresas: {e}")
        return jsonify({
            'sucesso': False,
            'erro': str(e)
        }), 500

@momentum_bp.route('/classificacoes', methods=['GET'])
def obter_classificacoes():
    """Obtém as faixas de classificação do momentum"""
    try:
        logger.info("📊 Solicitação de classificações de momentum")
        
        classificacoes = {
            'MOMENTUM_MUITO_FORTE': {
                'faixa': '≥ 80 pontos',
                'descricao': 'Momentum excepcional, múltiplos períodos positivos',
                'cor': '#10b981',  # Verde forte
                'recomendacao': 'COMPRA_FORTE'
            },
            'MOMENTUM_FORTE': {
                'faixa': '65-79 pontos',
                'descricao': 'Momentum consistente, boa performance multi-período',
                'cor': '#84cc16',  # Verde
                'recomendacao': 'COMPRA'
            },
            'MOMENTUM_MODERADO': {
                'faixa': '45-64 pontos',
                'descricao': 'Momentum neutro, desempenho misto',
                'cor': '#6b7280',  # Cinza
                'recomendacao': 'NEUTRO'
            },
            'MOMENTUM_FRACO': {
                'faixa': '25-44 pontos',
                'descricao': 'Momentum baixo, performance inconsistente',
                'cor': '#f59e0b',  # Amarelo/Laranja
                'recomendacao': 'CUIDADO'
            },
            'MOMENTUM_MUITO_FRACO': {
                'faixa': '< 25 pontos',
                'descricao': 'Momentum muito baixo, tendência negativa',
                'cor': '#ef4444',  # Vermelho
                'recomendacao': 'EVITAR'
            }
        }
        
        return jsonify({
            'sucesso': True,
            'data': classificacoes,
            'metodologia': {
                'componentes': {
                    'retorno_1m': '25% - ROC 21 dias',
                    'retorno_3m': '25% - ROC 63 dias',
                    'retorno_6m': '25% - ROC 126 dias',
                    'volume_aceleracao': '15% - Volume atual vs média 3M',
                    'volatilidade_negativa': '10% - Volatilidade apenas dias negativos'
                },
                'filtros': {
                    'sma_50': 'Penalização se preço abaixo da SMA 50',
                    'normalizacao': 'Cada componente normalizado 0-100'
                }
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Erro ao obter classificações: {e}")
        return jsonify({
            'sucesso': False,
            'erro': str(e)
        }), 500

@momentum_bp.route('/status', methods=['GET'])
def verificar_status():
    """Verifica status da API de Momentum e conectividade"""
    try:
        logger.info("🔍 Verificação de status da API Momentum")
        
        # Teste rápido com uma ação
        teste = momentum_service.obter_dados_acao('AAPL', 50)
        dados_ok = not teste.empty
        
        # Testar cálculo básico
        if dados_ok and len(teste) > 30:
            teste_roc = momentum_service.calcular_roc(teste['Close'], 21)
            calculo_ok = not teste_roc.empty and not teste_roc.isna().all()
        else:
            calculo_ok = False
        
        return jsonify({
            'sucesso': True,
            'status': 'ONLINE',
            'conectividade_yfinance': dados_ok,
            'calculos_funcionando': calculo_ok,
            'total_empresas': len(momentum_service.obter_top_50_empresas_eua()),
            'versao': '1.0.0',
            'ultima_verificacao': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ Erro na verificação de status: {e}")
        return jsonify({
            'sucesso': False,
            'status': 'ERRO',
            'erro': str(e)
        }), 500
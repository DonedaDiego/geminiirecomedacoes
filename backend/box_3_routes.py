from flask import Blueprint, request, jsonify
import logging
import pandas as pd
import os
import json
from box_3_service import BoxTresPontasService

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Criar blueprint
box3_bp = Blueprint('box3', __name__, url_prefix='/api/box3')

def carregar_token():
    """Carrega o token usando o mesmo método do ArbitragemPutsService"""
    try:
        # Lista de caminhos para tentar (igual ao ArbitragemPutsService)
        caminhos_config = [
            os.path.join(os.path.dirname(__file__), 'config.json'),
            os.path.join(os.path.dirname(__file__), '..', 'config.json'),
            os.path.expanduser('~/config.json'),
            r"C:\Users\usuario\Desktop\Vscode\Oplab\config.json"
        ]
        
        for caminho in caminhos_config:
            if os.path.exists(caminho):
                logger.info(f"Carregando config de: {caminho}")
                with open(caminho, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                # Tentar diferentes chaves possíveis
                for key in ['token', 'oplab_token', 'access_token']:
                    if key in config and config[key]:
                        logger.info("Token OpLab carregado com sucesso")
                        return config[key]
        
        logger.warning("Nenhum token OpLab encontrado")
        return None
        
    except Exception as e:
        logger.error(f"Erro ao carregar token: {e}")
        return None

@box3_bp.route('/health', methods=['GET'])
def health_check():
    """Health check do serviço Box de 3 Pontas"""
    try:
        token = carregar_token()
        if not token:
            return jsonify({
                'status': 'ERROR',
                'message': 'Token de acesso não configurado'
            }), 500
        
        service = BoxTresPontasService()
        
        return jsonify({
            'status': 'OK',
            'message': 'Serviço Box de 3 Pontas funcionando',
            'servico': 'Box de 3 Pontas',
            'versao': '1.0.0',
            'token_configurado': bool(service.token_acesso)
        })
        
    except Exception as e:
        logger.error(f"Erro no health check: {str(e)}")
        return jsonify({
            'status': 'ERROR',
            'message': f'Erro interno: {str(e)}'
        }), 500

@box3_bp.route('/listas', methods=['GET'])
def obter_listas():
    """Retorna as listas predefinidas de ativos para Box de 3 Pontas"""
    try:
        token = carregar_token()
        if not token:
            return jsonify({
                'success': False,
                'error': 'Token de acesso não configurado'
            }), 500
        
        service = BoxTresPontasService()
        listas = service.obter_listas_predefinidas()
        
        return jsonify({
            'success': True,
            'listas': listas,
            'total_listas': len(listas)
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter listas: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@box3_bp.route('/screening', methods=['POST'])
def executar_screening():
    """
    Executa screening de Box de 3 Pontas
    
    Body JSON:
    {
        "simbolos": ["PETR4", "VALE3"] (opcional se lista_predefinida for fornecida),
        "lista_predefinida": "principais" (opcional se simbolos for fornecido),
        "volume_min": 100,
        "custo_operacional": 0.003,
        "min_spread_cdi": 0.5,
        "tia_min": 0.0
    }
    """
    try:
        # Validar token
        token = carregar_token()
        if not token:
            return jsonify({
                'success': False,
                'error': 'Token de acesso não configurado'
            }), 500
        
        # Obter parâmetros do request
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Body JSON é obrigatório'
            }), 400
        
        # Parâmetros com valores padrão
        simbolos = data.get('simbolos')
        lista_predefinida = data.get('lista_predefinida')
        volume_min = data.get('volume_min', 100)
        custo_operacional = data.get('custo_operacional', 0.003)
        min_spread_cdi = data.get('min_spread_cdi', 0.5)
        tia_min = data.get('tia_min', 0.0)
        
        # Validar parâmetros
        if not simbolos and not lista_predefinida:
            return jsonify({
                'success': False,
                'error': 'É necessário fornecer "simbolos" ou "lista_predefinida"'
            }), 400
        
        # Validar tipos e valores
        try:
            volume_min = int(volume_min)
            custo_operacional = float(custo_operacional)
            min_spread_cdi = float(min_spread_cdi)
            tia_min = float(tia_min)
            
            if volume_min < 0:
                raise ValueError("Volume mínimo deve ser >= 0")
            if custo_operacional < 0 or custo_operacional > 1:
                raise ValueError("Custo operacional deve estar entre 0 e 1")
            if min_spread_cdi < -50 or min_spread_cdi > 50:
                raise ValueError("Spread mínimo deve estar entre -50% e 50%")
            if tia_min < -50 or tia_min > 100:
                raise ValueError("TIA mínima deve estar entre -50% e 100%")
                
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': f'Parâmetro inválido: {str(e)}'
            }), 400
        
        # Executar screening
        service = BoxTresPontasService()
        
        logger.info(f"Iniciando screening Box de 3 Pontas...")
        logger.info(f"Símbolos: {simbolos if simbolos else f'Lista: {lista_predefinida}'}")
        logger.info(f"Volume mín: {volume_min}, Custo op: {custo_operacional}")
        logger.info(f"Spread CDI mín: {min_spread_cdi}%, TIA mín: {tia_min}%")
        
        resultados = service.executar_screening_completo(
            simbolos=simbolos,
            lista_predefinida=lista_predefinida,
            volume_min=volume_min,
            custo_operacional=custo_operacional,
            min_spread_cdi=min_spread_cdi,
            tia_min=tia_min
        )
        
        # Adicionar informações extras à resposta
        resultados['success'] = True
        resultados['tipo_screening'] = 'Box de 3 Pontas'
        resultados['timestamp'] = pd.Timestamp.now().isoformat()
        
        logger.info(f"Screening concluído: {resultados['total_oportunidades']} oportunidades encontradas")
        
        return jsonify(resultados)
        
    except Exception as e:
        logger.error(f"Erro no screening: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@box3_bp.route('/ativo/<simbolo>', methods=['POST'])
def analisar_ativo_especifico(simbolo):
    """
    Analisa Box de 3 Pontas para um ativo específico
    
    Body JSON:
    {
        "volume_min": 100,
        "custo_operacional": 0.003
    }
    """
    try:
        # Validar token
        token = carregar_token()
        if not token:
            return jsonify({
                'success': False,
                'error': 'Token de acesso não configurado'
            }), 500
        
        # Obter parâmetros
        data = request.get_json() or {}
        volume_min = data.get('volume_min', 100)
        custo_operacional = data.get('custo_operacional', 0.003)
        
        # Validar parâmetros
        try:
            volume_min = int(volume_min)
            custo_operacional = float(custo_operacional)
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Parâmetros inválidos'
            }), 400
        
        # Executar análise
        service = BoxTresPontasService()
        oportunidades = service.analisar_box_tres_pontas(
            simbolo.upper(),
            volume_min,
            custo_operacional
        )
        
        if oportunidades is None:
            return jsonify({
                'success': True,
                'simbolo': simbolo.upper(),
                'total_oportunidades': 0,
                'oportunidades': [],
                'message': 'Nenhuma oportunidade encontrada'
            })
        
        return jsonify({
            'success': True,
            'simbolo': simbolo.upper(),
            'total_oportunidades': len(oportunidades),
            'oportunidades': oportunidades,
            'parametros': {
                'volume_min': volume_min,
                'custo_operacional': custo_operacional
            }
        })
        
    except Exception as e:
        logger.error(f"Erro na análise do ativo {simbolo}: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@box3_bp.route('/info', methods=['GET'])
def obter_info_servico():
    """Retorna informações sobre o serviço Box de 3 Pontas"""
    return jsonify({
        'nome': 'Box de 3 Pontas',
        'descricao': 'Serviço para análise de oportunidades de Box de 3 Pontas (renda fixa sintética)',
        'estrategia': {
            'definicao': 'Compra do ativo + Venda de call + Compra de put (mesmo strike e vencimento)',
            'objetivo': 'Criar renda fixa sintética que paga o valor do strike no vencimento',
            'risco': 'Baixo - resultado conhecido no vencimento',
            'retorno': 'Fixo - TIA (Taxa Implícita Anualizada) calculada'
        },
        'endpoints': {
            '/health': 'Health check do serviço',
            '/listas': 'Listas predefinidas de ativos',
            '/screening': 'Screening completo de múltiplos ativos',
            '/ativo/<simbolo>': 'Análise de ativo específico',
            '/info': 'Informações sobre o serviço'
        },
        'parametros': {
            'volume_min': 'Volume mínimo de negociação das opções',
            'custo_operacional': 'Percentual de custos operacionais (corretagem, impostos)',
            'min_spread_cdi': 'Spread mínimo sobre CDI para filtrar oportunidades',
            'tia_min': 'Taxa Implícita Anualizada mínima'
        },
        'listas_disponiveis': ['principais', 'bancos', 'commodities', 'consumo'],
        'versao': '1.0.0'
    })

# Exportar o blueprint para importação direta
__all__ = ['box3_bp']

# Função para registrar o blueprint (opcional)
def register_box3_routes(app):
    """Registra as rotas do Box de 3 Pontas na aplicação Flask"""
    app.register_blueprint(box3_bp)
    logger.info("Rotas do Box de 3 Pontas registradas com sucesso")
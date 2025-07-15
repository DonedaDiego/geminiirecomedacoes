from flask import Blueprint, request, jsonify
from datetime import datetime
import traceback
import json
import math
from typing import Any, Dict, List, Union
from pro.arbitragem_puts_service import arbitragem_puts_service

# Criar blueprint específico para arbitragem de puts
arbitragem_puts_bp = Blueprint('arbitragem_puts', __name__, url_prefix='/api/arbi-puts')

def sanitize_json_data(obj: Any) -> Any:
    """
    Remove valores NaN, Infinity e None problemáticos do JSON
    CORREÇÃO PRINCIPAL PARA O ERRO NaN
    """
    if isinstance(obj, dict):
        return {k: sanitize_json_data(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_json_data(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj):
            return 0.0  # Ou None, dependendo do contexto
        elif math.isinf(obj):
            return 0.0
        else:
            return obj
    else:
        return obj

def validate_numeric_parameter(value: Any, param_name: str, min_val: float = None, max_val: float = None) -> float:
    """
    Valida e converte parâmetros numéricos de forma segura
    """
    try:
        if value is None or value == '':
            raise ValueError(f"{param_name} não pode estar vazio")
        
        # Converter para float
        num_value = float(value)
        
        # Verificar se é NaN ou Infinity
        if math.isnan(num_value):
            raise ValueError(f"{param_name} não pode ser NaN")
        
        if math.isinf(num_value):
            raise ValueError(f"{param_name} não pode ser infinito")
        
        # Verificar limites
        if min_val is not None and num_value < min_val:
            raise ValueError(f"{param_name} deve ser >= {min_val}")
        
        if max_val is not None and num_value > max_val:
            raise ValueError(f"{param_name} deve ser <= {max_val}")
        
        return num_value
        
    except (ValueError, TypeError) as e:
        if "could not convert" in str(e) or "invalid literal" in str(e):
            raise ValueError(f"{param_name} deve ser um número válido")
        raise e

def validate_integer_parameter(value: Any, param_name: str, min_val: int = None, max_val: int = None) -> int:
    """
    Valida e converte parâmetros inteiros de forma segura
    """
    try:
        if value is None or value == '':
            raise ValueError(f"{param_name} não pode estar vazio")
        
        # Converter para int (via float primeiro para lidar com strings como "100.0")
        int_value = int(float(value))
        
        # Verificar limites
        if min_val is not None and int_value < min_val:
            raise ValueError(f"{param_name} deve ser >= {min_val}")
        
        if max_val is not None and int_value > max_val:
            raise ValueError(f"{param_name} deve ser <= {max_val}")
        
        return int_value
        
    except (ValueError, TypeError) as e:
        if "could not convert" in str(e) or "invalid literal" in str(e):
            raise ValueError(f"{param_name} deve ser um número inteiro válido")
        raise e

@arbitragem_puts_bp.route('/health', methods=['GET'])
def health_check():
    """Health check específico do serviço de arbitragem puts"""
    try:
        cache_stats = arbitragem_puts_service.estatisticas_cache()
        
        return jsonify({
            'status': 'OK',
            'service': 'Arbitragem de Puts',
            'message': 'Serviço funcionando normalmente',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0',
            'cache_stats': cache_stats
        })
    except Exception as e:
        return jsonify({
            'status': 'ERROR',
            'service': 'Arbitragem de Puts',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@arbitragem_puts_bp.route('/listas', methods=['GET'])
def get_listas_predefinidas():
    """Retorna listas predefinidas de ativos para arbitragem puts"""
    try:
        listas = arbitragem_puts_service.get_listas_predefinidas()
        
        return jsonify({
            'success': True,
            'service': 'arbitragem_puts',
            'listas': listas,
            'total_listas': len(listas),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@arbitragem_puts_bp.route('/screening', methods=['POST'])
def executar_screening():

    start_time = datetime.now()
    
    try:
        # Verificar se há dados JSON
        if not request.is_json:
            return jsonify({
                'success': False,
                'error': 'Content-Type deve ser application/json',
                'service': 'arbitragem_puts',
                'timestamp': datetime.now().isoformat()
            }), 400
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Payload JSON é obrigatório',
                'service': 'arbitragem_puts',
                'timestamp': datetime.now().isoformat()
            }), 400
        
        print(f"📥 [ARBI-PUTS] Payload recebido: {json.dumps(data, indent=2)}")
        
        # Determinar lista de símbolos
        simbolos = []
        if 'simbolos' in data and data['simbolos']:
            simbolos = [s.upper().strip() for s in data['simbolos'] if s.strip()]
        elif 'lista_predefinida' in data and data['lista_predefinida']:
            lista_nome = data['lista_predefinida'].lower().strip()
            listas = arbitragem_puts_service.get_listas_predefinidas()
            if lista_nome in listas:
                simbolos = listas[lista_nome]
            else:
                return jsonify({
                    'success': False,
                    'error': f'Lista predefinida "{lista_nome}" não encontrada',
                    'listas_disponiveis': list(listas.keys()),
                    'service': 'arbitragem_puts',
                    'timestamp': datetime.now().isoformat()
                }), 400
        
        if not simbolos:
            return jsonify({
                'success': False,
                'error': 'É necessário fornecer símbolos ou lista_predefinida',
                'service': 'arbitragem_puts',
                'timestamp': datetime.now().isoformat()
            }), 400
        
        # Validar quantidade de símbolos (limite para performance)
        if len(simbolos) > 100:
            return jsonify({
                'success': False,
                'error': 'Máximo de 100 símbolos por análise',
                'simbolos_fornecidos': len(simbolos),
                'service': 'arbitragem_puts',
                'timestamp': datetime.now().isoformat()
            }), 400
        
        print(f"📋 [ARBI-PUTS] Símbolos para análise: {simbolos[:5]}{'...' if len(simbolos) > 5 else ''} (total: {len(simbolos)})")
        
        # Validar e sanitizar parâmetros principais
        try:
            taxa_cdi_mensal = validate_numeric_parameter(
                data.get('taxa_cdi_mensal', 1.0), 
                'taxa_cdi_mensal', 
                min_val=0.0, 
                max_val=10.0
            )
            
            volume_min = validate_integer_parameter(
                data.get('volume_min', 100), 
                'volume_min', 
                min_val=0, 
                max_val=10000
            )
            
            rentabilidade_min = validate_numeric_parameter(
                data.get('rentabilidade_min', 1.2), 
                'rentabilidade_min', 
                min_val=0.0, 
                max_val=50.0
            )
            
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': str(e),
                'service': 'arbitragem_puts',
                'timestamp': datetime.now().isoformat()
            }), 400
        
        # Validar e sanitizar filtros
        filtros = data.get('filtros', {})
        if filtros:
            try:
                # Validar filtros numéricos
                if 'delta_min' in filtros:
                    filtros['delta_min'] = validate_numeric_parameter(
                        filtros['delta_min'], 'delta_min', min_val=0.0, max_val=1.0
                    )
                
                if 'delta_max' in filtros:
                    filtros['delta_max'] = validate_numeric_parameter(
                        filtros['delta_max'], 'delta_max', min_val=0.0, max_val=1.0
                    )
                
                if 'atm_min' in filtros:
                    filtros['atm_min'] = validate_integer_parameter(
                        filtros['atm_min'], 'atm_min', min_val=0, max_val=50
                    )
                
                if 'atm_max' in filtros:
                    filtros['atm_max'] = validate_integer_parameter(
                        filtros['atm_max'], 'atm_max', min_val=0, max_val=50
                    )
                
                if 'lucro_min' in filtros:
                    filtros['lucro_min'] = validate_numeric_parameter(
                        filtros['lucro_min'], 'lucro_min', min_val=0.0, max_val=20.0
                    )
                
                if 'dias_vencimento_min' in filtros:
                    filtros['dias_vencimento_min'] = validate_integer_parameter(
                        filtros['dias_vencimento_min'], 'dias_vencimento_min', min_val=1, max_val=365
                    )
                
                if 'dias_vencimento_max' in filtros:
                    filtros['dias_vencimento_max'] = validate_integer_parameter(
                        filtros['dias_vencimento_max'], 'dias_vencimento_max', min_val=1, max_val=365
                    )
                
                # Validar vencimentos (deve ser lista)
                if 'vencimentos' in filtros:
                    if not isinstance(filtros['vencimentos'], list):
                        filtros['vencimentos'] = []
                
                # Validações de consistência
                if 'delta_min' in filtros and 'delta_max' in filtros:
                    if filtros['delta_min'] >= filtros['delta_max']:
                        return jsonify({
                            'success': False,
                            'error': 'Delta mínimo deve ser menor que delta máximo',
                            'service': 'arbitragem_puts',
                            'timestamp': datetime.now().isoformat()
                        }), 400
                
                if 'atm_min' in filtros and 'atm_max' in filtros:
                    if filtros['atm_min'] >= filtros['atm_max']:
                        return jsonify({
                            'success': False,
                            'error': 'ATM mínimo deve ser menor que ATM máximo',
                            'service': 'arbitragem_puts',
                            'timestamp': datetime.now().isoformat()
                        }), 400
                
                if 'dias_vencimento_min' in filtros and 'dias_vencimento_max' in filtros:
                    if filtros['dias_vencimento_min'] >= filtros['dias_vencimento_max']:
                        return jsonify({
                            'success': False,
                            'error': 'Dias vencimento mínimo deve ser menor que máximo',
                            'service': 'arbitragem_puts',
                            'timestamp': datetime.now().isoformat()
                        }), 400
                
            except ValueError as e:
                return jsonify({
                    'success': False,
                    'error': f'Erro nos filtros: {str(e)}',
                    'service': 'arbitragem_puts',
                    'timestamp': datetime.now().isoformat()
                }), 400
        
        print(f"⚙️ [ARBI-PUTS] Parâmetros validados:")
        print(f"   • Taxa CDI: {taxa_cdi_mensal}%")
        print(f"   • Volume mín: {volume_min}")
        print(f"   • Rentabilidade mín: {rentabilidade_min}%")
        print(f"   • Filtros: {filtros}")
        
        # Executar screening
        print(f"🚀 [ARBI-PUTS] Iniciando screening...")
        resultado = arbitragem_puts_service.executar_screening(
            simbolos=simbolos,
            taxa_cdi_mensal=taxa_cdi_mensal,
            volume_min=volume_min,
            rentabilidade_min=rentabilidade_min,
            filtros=filtros
        )
        
        # SANITIZAR RESULTADO ANTES DE RETORNAR (CORREÇÃO PRINCIPAL)
        resultado_sanitized = sanitize_json_data(resultado)
        
        # Adicionar métricas de performance
        tempo_execucao = (datetime.now() - start_time).total_seconds()
        resultado_sanitized['performance'] = {
            'tempo_execucao_segundos': tempo_execucao,
            'simbolos_por_segundo': len(simbolos) / max(tempo_execucao, 0.1),
            'timestamp_inicio': start_time.isoformat(),
            'timestamp_fim': datetime.now().isoformat()
        }
        
        print(f"✅ [ARBI-PUTS] Screening concluído em {tempo_execucao:.1f}s")
        print(f"📊 [ARBI-PUTS] Resultado: {resultado_sanitized.get('total_oportunidades', 0)} oportunidades")
        
        return jsonify(resultado_sanitized)
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': f'Erro de validação: {str(e)}',
            'service': 'arbitragem_puts',
            'timestamp': datetime.now().isoformat()
        }), 400
    except json.JSONDecodeError as e:
        return jsonify({
            'success': False,
            'error': 'JSON inválido no payload',
            'service': 'arbitragem_puts',
            'timestamp': datetime.now().isoformat()
        }), 400
    except Exception as e:
        print(f"❌ [ARBI-PUTS] Erro no screening: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor',
            'error_detail': str(e) if request.args.get('debug') == 'true' else None,
            'service': 'arbitragem_puts',
            'timestamp': datetime.now().isoformat()
        }), 500

@arbitragem_puts_bp.route('/cache/limpar', methods=['POST'])
def limpar_cache():
    """Limpa o cache de preços do serviço"""
    try:
        arbitragem_puts_service.limpar_cache()
        return jsonify({
            'success': True,
            'message': 'Cache limpo com sucesso',
            'service': 'arbitragem_puts',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'service': 'arbitragem_puts',
            'timestamp': datetime.now().isoformat()
        }), 500

@arbitragem_puts_bp.route('/cache/stats', methods=['GET'])
def get_cache_stats():
    """Retorna estatísticas do cache"""
    try:
        stats = arbitragem_puts_service.estatisticas_cache()
        return jsonify({
            'success': True,
            'cache_stats': stats,
            'service': 'arbitragem_puts',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'service': 'arbitragem_puts',
            'timestamp': datetime.now().isoformat()
        }), 500

@arbitragem_puts_bp.route('/info', methods=['GET'])
def get_service_info():
    """Retorna informações sobre o serviço de arbitragem de puts"""
    try:
        listas = arbitragem_puts_service.get_listas_predefinidas()
        
        return jsonify({
            'success': True,
            'service': 'arbitragem_puts',
            'info': {
                'nome': 'Arbitragem de Puts',
                'descricao': 'Busca oportunidades de arbitragem em puts com valor extrínseco negativo',
                'estrategia': 'Compra de ativo + Compra de put com valor extrínseco negativo',
                'parametros': {
                    'taxa_cdi_mensal': {
                        'descricao': 'Taxa CDI mensal para comparação (%)',
                        'range': '0.0 - 10.0',
                        'default': 1.0
                    },
                    'volume_min': {
                        'descricao': 'Volume mínimo de contratos negociados',
                        'range': '0 - 10000',
                        'default': 100
                    },
                    'rentabilidade_min': {
                        'descricao': 'Rentabilidade mínima esperada (%)',
                        'range': '0.0 - 50.0',
                        'default': 1.2
                    }
                },
                'filtros_avancados': {
                    'delta_min/max': 'Range de delta das opções (0.0 - 1.0)',
                    'atm_min/max': 'Distância do ATM em % (0 - 50)',
                    'lucro_min': 'Lucro mínimo adicional (0.0 - 20.0)',
                    'dias_vencimento_min/max': 'Range de dias até vencimento (1 - 365)',
                    'vencimentos': 'Lista de vencimentos específicos'
                }
            },
            'listas_disponiveis': {
                nome: f"{nome.upper()} ({len(ativos)} ativos)" 
                for nome, ativos in listas.items()
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'service': 'arbitragem_puts',
            'timestamp': datetime.now().isoformat()
        }), 500

# Handlers de erro específicos
@arbitragem_puts_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint não encontrado',
        'service': 'arbitragem_puts',
        'available_endpoints': [
            '/health', '/listas', '/screening', '/info',
            '/cache/limpar', '/cache/stats'
        ],
        'timestamp': datetime.now().isoformat()
    }), 404

@arbitragem_puts_bp.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        'success': False,
        'error': 'Método HTTP não permitido',
        'service': 'arbitragem_puts',
        'timestamp': datetime.now().isoformat()
    }), 405

@arbitragem_puts_bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Erro interno do servidor',
        'service': 'arbitragem_puts',
        'timestamp': datetime.now().isoformat()
    }), 500
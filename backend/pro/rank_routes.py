from flask import Blueprint, request, jsonify
from datetime import datetime
import traceback

# Importar o serviço
from pro.rank_service import RankingService  # Serviço está em rank_service.py

# Blueprint
rank_bp = Blueprint('rank', __name__, url_prefix='/api/rank')

# Instância global do serviço
ranking_service = RankingService()

@rank_bp.route('/health', methods=['GET'])
def health_check():
    """Health check"""
    return jsonify({
        'status': 'OK',
        'message': 'Ranking de Volatilidade Implícita funcionando',
        'timestamp': datetime.now().isoformat(),
        'acoes_monitoradas': len(ranking_service.options_stocks),
        'token_configurado': bool(ranking_service.token)
    })

@rank_bp.route('/iv-ranking', methods=['GET'])
def get_iv_ranking():
    """Ranking principal de IV - USA O SERVIÇO"""
    try:
        # Parâmetros
        rank_by = request.args.get('rank_by', 'iv_current')
        top_n = int(request.args.get('top_n', 20))
        
        print(f" Ranking solicitado: {rank_by}, top {top_n}")
        
        # **USAR O SERVIÇO** - método principal
        result = ranking_service.get_full_analysis(rank_by=rank_by, top_n=top_n)
        
        if not result['success']:
            return jsonify(result), 500
        
        return jsonify(result)
        
    except Exception as e:
        print(f" Erro no ranking: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@rank_bp.route('/top-iv', methods=['GET'])
def get_top_iv():
    """Top ações por IV alta/baixa - USA O SERVIÇO"""
    try:
        tipo = request.args.get('tipo', 'alta').lower()
        quantidade = int(request.args.get('quantidade', 5))
        
        print(f" Top IV {tipo}: {quantidade} ações")
        
        # Buscar dados usando o serviço
        data = ranking_service.fetch_data(limit=150)
        if not data:
            return jsonify({
                'success': False,
                'error': 'Erro ao buscar dados'
            }), 500
        
        # Processar usando o serviço
        df = ranking_service.process_data(data)
        if df is None:
            return jsonify({
                'success': False,
                'error': 'Erro ao processar dados'
            }), 500
        
        # **USAR MÉTODO DO SERVIÇO**
        top_acoes = ranking_service.get_top_iv(df, tipo, quantidade)
        
        return jsonify({
            'success': True,
            'tipo': tipo,
            'quantidade': len(top_acoes),
            'top_acoes': top_acoes,
            'descricao': f'Top {quantidade} ações com IV {"mais alta" if tipo == "alta" else "mais baixa"}',
            'ideal_para': 'vendedores de opções' if tipo == 'alta' else 'compradores de opções',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f" Erro no top IV: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@rank_bp.route('/iv-vs-volume', methods=['GET'])
def get_iv_vs_volume():
    """IV vs Volume para scatter plot - USA O SERVIÇO"""
    try:
        top_n = int(request.args.get('top_n', 20))
        
        print(f" IV vs Volume: top {top_n}")
        
        # Buscar e processar dados usando o serviço
        data = ranking_service.fetch_data(limit=150)
        if not data:
            return jsonify({
                'success': False,
                'error': 'Erro ao buscar dados'
            }), 500
        
        df = ranking_service.process_data(data)
        if df is None:
            return jsonify({
                'success': False,
                'error': 'Erro ao processar dados'
            }), 500
        
        # **USAR MÉTODO DO SERVIÇO**
        scatter_data = ranking_service.get_scatter_data(df, top_n)
        
        return jsonify({
            'success': True,
            'total_acoes': len(scatter_data),
            'scatter_data': scatter_data,
            'descricao': 'IV vs Volume Financeiro',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f" Erro no IV vs Volume: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@rank_bp.route('/iv-percentil', methods=['GET'])
def get_iv_percentil():
    """Ranking por percentil de IV - USA O SERVIÇO"""
    try:
        top_n = int(request.args.get('top_n', 20))
        
        print(f" IV Percentil: top {top_n}")
        
        # Buscar dados específicos para percentil
        data = ranking_service.fetch_data(rank_by='iv_6m_percentile', limit=150)
        if not data:
            return jsonify({
                'success': False,
                'error': 'Erro ao buscar dados'
            }), 500
        
        df = ranking_service.process_data(data)
        if df is None:
            return jsonify({
                'success': False,
                'error': 'Erro ao processar dados'
            }), 500
        
        # **USAR MÉTODO DO SERVIÇO**
        ranking, categorias = ranking_service.get_percentil_data(df, top_n)
        
        return jsonify({
            'success': True,
            'total_acoes': len(ranking),
            'ranking': ranking,
            'resumo_categorias': categorias,
            'descricao': 'Ranking por Percentil IV 6M',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f" Erro no percentil: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@rank_bp.route('/iv-6m-comparison', methods=['GET'])
def get_iv_6m_comparison():
    """Comparação IV atual vs IV 6M máximo - USA O SERVIÇO"""
    try:
        top_n = int(request.args.get('top_n', 20))
        
        print(f" IV 6M Comparison: top {top_n}")
        
        # Buscar e processar dados
        data = ranking_service.fetch_data(limit=150)
        if not data:
            return jsonify({
                'success': False,
                'error': 'Erro ao buscar dados'
            }), 500
        
        df = ranking_service.process_data(data)
        if df is None:
            return jsonify({
                'success': False,
                'error': 'Erro ao processar dados'
            }), 500
        
        # **USAR MÉTODO DO SERVIÇO**
        comparison_data, stats = ranking_service.get_comparison_data(df, top_n)
        
        return jsonify({
            'success': True,
            'total_acoes': len(comparison_data),
            'comparison_data': comparison_data,
            'estatisticas': stats,
            'descricao': 'IV Atual vs IV 6M Máximo',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f" Erro na comparação 6M: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@rank_bp.route('/estatisticas', methods=['GET'])
def get_estatisticas():
    """Estatísticas gerais - USA O SERVIÇO"""
    try:
        print(" Estatísticas gerais solicitadas")
        
        # **USAR MÉTODO PRINCIPAL DO SERVIÇO**
        result = ranking_service.get_full_analysis(top_n=5)
        
        if not result['success']:
            return jsonify(result), 500
        
        # Reformatar para o formato esperado
        return jsonify({
            'success': True,
            'total_acoes_monitoradas': len(ranking_service.options_stocks),
            'total_acoes_processadas': result['total_acoes'],
            'estatisticas_iv': result['estatisticas'],
            'destaques': {
                'iv_alta': result['top_5']['iv_alta'],
                'iv_baixa': result['top_5']['iv_baixa']
            },
            'timestamp': result['timestamp']
        })
        
    except Exception as e:
        print(f" Erro nas estatísticas: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# Rota adicional para análise completa
@rank_bp.route('/analise-completa', methods=['GET'])
def get_analise_completa():
    """Análise completa usando todos os recursos do serviço"""
    try:
        rank_by = request.args.get('rank_by', 'iv_current')
        top_n = int(request.args.get('top_n', 20))
        
        print(f" Análise completa solicitada: {rank_by}, top {top_n}")
        
        # **USAR MÉTODO PRINCIPAL DO SERVIÇO**
        result = ranking_service.get_full_analysis(rank_by=rank_by, top_n=top_n)
        
        if not result['success']:
            return jsonify(result), 500
        
        # Buscar dados adicionais usando outros métodos do serviço
        data = ranking_service.fetch_data(rank_by=rank_by)
        if data:
            df = ranking_service.process_data(data)
            if df is not None:
                # Adicionar dados extras
                result['dados_extras'] = {
                    'scatter_data': ranking_service.get_scatter_data(df, top_n),
                    'comparison_data': ranking_service.get_comparison_data(df, top_n)[0],
                    'percentil_data': ranking_service.get_percentil_data(df, top_n)[0]
                }
        
        return jsonify(result)
        
    except Exception as e:
        print(f" Erro na análise completa: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# Error handlers
@rank_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint não encontrado',
        'timestamp': datetime.now().isoformat()
    }), 404

@rank_bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Erro interno do servidor',
        'timestamp': datetime.now().isoformat()
    }), 500

# Função para retornar blueprint
def get_rank_blueprint():
    """Retorna blueprint para registrar no Flask"""
    return rank_bp
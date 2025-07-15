from flask import Blueprint, jsonify, request
from gratis.rsl_service import YFinanceRSLService
import logging
from datetime import datetime

# Criar blueprint
rsl_bp = Blueprint('rsl', __name__, url_prefix='/api')

# ===== ROTAS RSL =====

@rsl_bp.route('/setores', methods=['GET'])
def get_all_setores():
    """Lista todos os setores disponíveis na base"""
    try:
        service = YFinanceRSLService()
        info = service.get_database_info()
        
        # Formatar resposta para o frontend
        setores_lista = []
        for setor_nome, dados in info['setores_detalhes'].items():
            setores_lista.append({
                'setor_economico': setor_nome,
                'total_empresas': dados['total_empresas'],
                'tickers': dados['tickers']
            })
        
        return jsonify({
            'success': True,
            'data': setores_lista,
            'total_setores': info['total_setores'],
            'total_empresas': info['total_tickers'],
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Erro ao buscar setores: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@rsl_bp.route('/setor/<setor_nome>', methods=['GET'])
def get_empresas_setor(setor_nome):
    """Lista empresas de um setor específico"""
    try:
        service = YFinanceRSLService()
        tickers = service.get_tickers_by_setor(setor_nome)
        
        if not tickers:
            return jsonify({
                'success': False,
                'error': f'Setor "{setor_nome}" não encontrado'
            }), 404
        
        # Formatar como esperado pelo frontend
        empresas_lista = []
        for ticker in tickers:
            empresas_lista.append({
                'ticker': ticker,
                'acao': ticker,  # Compatibilidade
                'empresa': ticker,  # Compatibilidade
                'setor_economico': setor_nome
            })
        
        return jsonify({
            'success': True,
            'data': empresas_lista,
            'setor': setor_nome,
            'total_empresas': len(empresas_lista),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Erro ao buscar empresas do setor {setor_nome}: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@rsl_bp.route('/rsl-setor/<setor_nome>', methods=['GET'])
def get_rsl_setor(setor_nome):
    """Calcula RSL de um setor específico"""
    try:
        # Parâmetros opcionais
        period = request.args.get('period', '1y')
        
        print(f"🔍 Calculando RSL para setor: {setor_nome} (período: {period})")
        
        service = YFinanceRSLService()
        rsl_data = service.get_sector_rsl_data(setor_nome, period)
        
        if not rsl_data:
            return jsonify({
                'success': False,
                'error': f'Não foi possível calcular RSL para o setor "{setor_nome}"'
            }), 404
        
        return jsonify({
            'success': True,
            'data': rsl_data,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Erro ao calcular RSL do setor {setor_nome}: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@rsl_bp.route('/rsl-ticker/<ticker>', methods=['GET'])
def get_rsl_ticker(ticker):
    """Calcula RSL de um ticker específico"""
    try:
        # Parâmetros opcionais
        period = request.args.get('period', '1y')
        
        print(f"🔍 Calculando RSL para ticker: {ticker} (período: {period})")
        
        service = YFinanceRSLService()
        rsl_data = service.get_ticker_rsl(ticker, period)
        
        if not rsl_data:
            return jsonify({
                'success': False,
                'error': f'Não foi possível calcular RSL para o ticker "{ticker}"'
            }), 404
        
        return jsonify({
            'success': True,
            'data': rsl_data,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Erro ao calcular RSL do ticker {ticker}: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@rsl_bp.route('/rsl-todos-setores', methods=['GET'])
def get_rsl_todos_setores():
    """Calcula RSL de todos os setores"""
    try:
        # Parâmetros opcionais
        period = request.args.get('period', '1y')
        
        print(f"🚀 Calculando RSL para todos os setores (período: {period})")
        
        service = YFinanceRSLService()
        all_rsl_data = service.get_all_sectors_rsl(period)
        
        if not all_rsl_data:
            return jsonify({
                'success': False,
                'error': 'Não foi possível calcular RSL para nenhum setor'
            }), 500
        
        # Transformar em lista para o frontend
        setores_lista = []
        for setor_nome, rsl_data in all_rsl_data.items():
            setores_lista.append(rsl_data)
        
        return jsonify({
            'success': True,
            'data': {
                'setores': setores_lista,
                'total_processados': len(setores_lista),
                'period': period
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Erro ao calcular RSL de todos os setores: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@rsl_bp.route('/rsl-info', methods=['GET'])
def get_rsl_info():
    """Informações sobre a base de dados RSL"""
    try:
        service = YFinanceRSLService()
        info = service.get_database_info()
        cache_info = service.get_cache_info()
        
        return jsonify({
            'success': True,
            'data': {
                'database_info': info,
                'cache_info': cache_info,
                'setores_disponíveis': service.get_all_setores()
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Erro ao buscar informações RSL: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@rsl_bp.route('/rsl-cache', methods=['DELETE'])
def clear_rsl_cache():
    """Limpa o cache RSL"""
    try:
        service = YFinanceRSLService()
        cache_info_antes = service.get_cache_info()
        
        service.clear_cache()
        
        cache_info_depois = service.get_cache_info()
        
        return jsonify({
            'success': True,
            'message': 'Cache RSL limpo com sucesso',
            'cache_antes': cache_info_antes,
            'cache_depois': cache_info_depois,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Erro ao limpar cache RSL: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@rsl_bp.route('/rsl-cache', methods=['GET'])
def get_rsl_cache_info():
    """Informações sobre o cache RSL"""
    try:
        service = YFinanceRSLService()
        cache_info = service.get_cache_info()
        
        return jsonify({
            'success': True,
            'data': cache_info,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Erro ao buscar informações do cache: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

# ===== ROTAS DE TESTE E DEBUG =====

@rsl_bp.route('/test-rsl', methods=['GET'])
def test_rsl():
    """Rota de teste para verificar se o RSL está funcionando"""
    try:
        service = YFinanceRSLService()
        
        # Teste básico com PETR4
        print("🧪 Testando RSL com PETR4...")
        rsl_petr4 = service.get_ticker_rsl('PETR4')
        
        # Teste de setor
        print("🧪 Testando RSL do setor Petróleo...")
        rsl_petroleo = service.get_sector_rsl_data('Petróleo, Gás e Bio')
        
        # Info da base
        info = service.get_database_info()
        cache_info = service.get_cache_info()
        
        return jsonify({
            'success': True,
            'tests': {
                'ticker_test': {
                    'ticker': 'PETR4',
                    'success': rsl_petr4 is not None,
                    'data': rsl_petr4
                },
                'sector_test': {
                    'setor': 'Petróleo, Gás e Bio',
                    'success': rsl_petroleo is not None,
                    'data': rsl_petroleo
                }
            },
            'database_info': info,
            'cache_info': cache_info,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Erro no teste RSL: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro no teste: {str(e)}'
        }), 500

@rsl_bp.route('/radar-setores', methods=['GET'])
def get_radar_setores():
    """
    Endpoint específico para a página Radar de Setores
    Retorna dados formatados para o gráfico
    """
    try:
        period = request.args.get('period', '1y')
        
        print(f"📊 Gerando dados para Radar de Setores (período: {period})")
        
        service = YFinanceRSLService()
        all_rsl_data = service.get_all_sectors_rsl(period)
        
        if not all_rsl_data:
            return jsonify({
                'success': False,
                'error': 'Erro ao calcular dados dos setores'
            }), 500
        
        # Formatar dados para o frontend do radar
        setores_radar = []
        total_empresas = 0
        
        for i, (setor_nome, rsl_data) in enumerate(all_rsl_data.items()):
            setores_radar.append({
                'id': i,
                'setor': setor_nome,
                'rsl': rsl_data['rsl'],
                'volatilidade': rsl_data['volatilidade'],
                'empresas': rsl_data['total_empresas'],
                'empresas_com_dados': rsl_data['empresas_com_dados'],
                'taxa_sucesso': rsl_data['taxa_sucesso'],
                'has_real_data': rsl_data['has_real_data'],
                'detalhes_empresas': rsl_data['detalhes_empresas'],
                'cor': f'hsl({(i * 137.5) % 360}, 70%, 60%)'  # Cores automáticas
            })
            total_empresas += rsl_data['total_empresas']
        
        return jsonify({
            'success': True,
            'data': {
                'setores': setores_radar,
                'statistics': {
                    'total_setores': len(setores_radar),
                    'total_empresas': total_empresas,
                    'setores_com_dados': len([s for s in setores_radar if s['has_real_data']]),
                    'period': period
                },
                'last_update': datetime.now().strftime('%d/%m/%Y %H:%M')
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Erro ao gerar radar de setores: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

# ===== FUNÇÃO PARA REGISTRAR BLUEPRINT =====
def get_rsl_blueprint():
    """Retorna o blueprint configurado"""
    return rsl_bp

# ===== LOG DE INICIALIZAÇÃO =====
# print("✅ RSL Routes Blueprint criado com sucesso!")
# print("📊 Rotas disponíveis:")
# print("  GET  /api/setores - Lista todos os setores")
# print("  GET  /api/setor/<nome> - Empresas de um setor")
# print("  GET  /api/rsl-setor/<nome> - RSL de um setor")
# print("  GET  /api/rsl-ticker/<ticker> - RSL de um ticker")
# print("  GET  /api/rsl-todos-setores - RSL de todos os setores")
# print("  GET  /api/rsl-info - Informações da base")
# print("  GET  /api/radar-setores - Dados para o radar")
# print("  GET  /api/test-rsl - Teste do sistema")
# print("  GET  /api/rsl-cache - Info do cache")
# print("  DEL  /api/rsl-cache - Limpar cache")
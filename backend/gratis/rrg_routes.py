from flask import Blueprint, jsonify, request
from .rrg_service import YFinanceRRGService
import logging
from datetime import datetime

# Criar blueprint
rrg_bp = Blueprint('rrg', __name__, url_prefix='/api')

# ===== ROTAS RRG =====

@rrg_bp.route('/rrg-setores', methods=['GET'])
def get_all_setores():
    """Lista todos os setores disponíveis na base"""
    try:
        service = YFinanceRRGService()
        setores = service.get_all_setores()
        
        # Formatar resposta
        setores_lista = []
        for setor_nome in setores:
            tickers = service.get_tickers_by_setor(setor_nome)
            setores_lista.append({
                'setor_economico': setor_nome,
                'total_empresas': len(tickers),
                'tickers': tickers
            })
        
        return jsonify({
            'success': True,
            'data': setores_lista,
            'total_setores': len(setores),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Erro ao buscar setores RRG: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@rrg_bp.route('/rrg-setor/<setor_nome>', methods=['GET'])
def get_empresas_setor(setor_nome):
    """Lista empresas de um setor específico"""
    try:
        service = YFinanceRRGService()
        tickers = service.get_tickers_by_setor(setor_nome)
        
        if not tickers:
            return jsonify({
                'success': False,
                'error': f'Setor "{setor_nome}" não encontrado'
            }), 404
        
        empresas_lista = []
        for ticker in tickers:
            empresas_lista.append({
                'ticker': ticker,
                'acao': ticker,
                'empresa': ticker,
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

@rrg_bp.route('/rrg-ticker/<ticker>', methods=['GET'])
def get_rrg_ticker(ticker):
    """Calcula RRG de um ticker específico"""
    try:
        print(f"🔍 Calculando RRG para ticker: {ticker}")
        
        service = YFinanceRRGService()
        rrg_data = service.get_rrg_data(ticker)
        
        if not rrg_data:
            return jsonify({
                'success': False,
                'error': f'Não foi possível calcular RRG para o ticker "{ticker}"'
            }), 404
        
        return jsonify({
            'success': True,
            'data': rrg_data,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Erro ao calcular RRG do ticker {ticker}: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@rrg_bp.route('/rrg-analise-setor/<setor_nome>', methods=['GET'])
def get_rrg_setor(setor_nome):
    """Calcula RRG de um setor específico"""
    try:
        print(f"🔍 Calculando RRG para setor: {setor_nome}")
        
        service = YFinanceRRGService()
        rrg_data = service.get_sector_rrg_data(setor_nome)
        
        if not rrg_data:
            return jsonify({
                'success': False,
                'error': f'Não foi possível calcular RRG para o setor "{setor_nome}"'
            }), 404
        
        return jsonify({
            'success': True,
            'data': rrg_data,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Erro ao calcular RRG do setor {setor_nome}: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@rrg_bp.route('/rrg-todos-setores', methods=['GET'])
def get_rrg_todos_setores():
    """Calcula RRG de todos os setores"""
    try:
        print(f"📊 Calculando RRG para todos os setores")
        
        service = YFinanceRRGService()
        all_rrg_data = service.get_all_sectors_rrg()
        
        if not all_rrg_data:
            return jsonify({
                'success': False,
                'error': 'Não foi possível calcular RRG para nenhum setor'
            }), 500
        
        # Transformar em lista
        setores_lista = []
        for setor_nome, rrg_data in all_rrg_data.items():
            setores_lista.append(rrg_data)
        
        return jsonify({
            'success': True,
            'data': {
                'setores': setores_lista,
                'total_processados': len(setores_lista)
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Erro ao calcular RRG de todos os setores: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@rrg_bp.route('/rrg-radar-setores', methods=['GET'])
def get_radar_setores():
    """
    Endpoint específico para a página Radar RRG
    Retorna dados formatados para o gráfico scatter
    """
    try:
        print(f"📊 Gerando dados para Radar RRG de Setores")
        
        service = YFinanceRRGService()
        all_rrg_data = service.get_all_sectors_rrg()
        
        if not all_rrg_data:
            return jsonify({
                'success': False,
                'error': 'Erro ao calcular dados dos setores'
            }), 500
        
        # Formatar dados para o frontend
        setores_radar = []
        total_empresas = 0
        
        distribuicao_regimes = {
            'Leading': 0,
            'Improving': 0,
            'Weakening': 0,
            'Lagging': 0
        }
        
        for i, (setor_nome, rrg_data) in enumerate(all_rrg_data.items()):
            regime = rrg_data['regime']
            distribuicao_regimes[regime] += 1
            
            setores_radar.append({
                'id': i,
                'setor': setor_nome,
                'dist_ema65_pct': rrg_data['dist_ema65_pct'],
                'dist_ema252_pct': rrg_data['dist_ema252_pct'],
                'regime': regime,
                'momentum_21d': rrg_data['momentum_21d'],
                'volatilidade_30d': rrg_data['volatilidade_30d'],
                'empresas': rrg_data['total_empresas'],
                'empresas_com_dados': rrg_data['empresas_com_dados'],
                'distribuicao_regimes': rrg_data['distribuicao_regimes'],
                'detalhes_empresas': rrg_data['detalhes_empresas'],
                'has_real_data': rrg_data['has_real_data'],
                'cor': get_regime_color(regime)
            })
            total_empresas += rrg_data['total_empresas']
        
        return jsonify({
            'success': True,
            'data': {
                'setores': setores_radar,
                'statistics': {
                    'total_setores': len(setores_radar),
                    'total_empresas': total_empresas,
                    'setores_com_dados': len([s for s in setores_radar if s['has_real_data']]),
                    'distribuicao_regimes': distribuicao_regimes
                },
                'last_update': datetime.now().strftime('%d/%m/%Y %H:%M')
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Erro ao gerar radar RRG: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@rrg_bp.route('/rrg-radar-tickers', methods=['POST'])
def get_radar_tickers():
    """
    Endpoint para análise RRG de múltiplos tickers
    Body: { "tickers": ["PETR4", "VALE3", "ITUB4"] }
    """
    try:
        data = request.get_json()
        tickers = data.get('tickers', [])
        
        if not tickers:
            return jsonify({
                'success': False,
                'error': 'Lista de tickers vazia'
            }), 400
        
        print(f"📊 Calculando RRG para {len(tickers)} tickers")
        
        service = YFinanceRRGService()
        resultados = []
        
        for ticker in tickers:
            rrg_data = service.get_rrg_data_cached(ticker)
            if rrg_data:
                rrg_data['cor'] = get_regime_color(rrg_data['regime'])
                resultados.append(rrg_data)
        
        distribuicao_regimes = {
            'Leading': len([r for r in resultados if r['regime'] == 'Leading']),
            'Improving': len([r for r in resultados if r['regime'] == 'Improving']),
            'Weakening': len([r for r in resultados if r['regime'] == 'Weakening']),
            'Lagging': len([r for r in resultados if r['regime'] == 'Lagging'])
        }
        
        return jsonify({
            'success': True,
            'data': {
                'tickers': resultados,
                'statistics': {
                    'total_solicitados': len(tickers),
                    'total_processados': len(resultados),
                    'distribuicao_regimes': distribuicao_regimes
                },
                'last_update': datetime.now().strftime('%d/%m/%Y %H:%M')
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Erro ao calcular RRG de tickers: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@rrg_bp.route('/rrg-cache', methods=['DELETE'])
def clear_rrg_cache():
    """Limpa o cache RRG"""
    try:
        service = YFinanceRRGService()
        cache_info_antes = service.get_cache_info()
        
        service.clear_cache()
        
        cache_info_depois = service.get_cache_info()
        
        return jsonify({
            'success': True,
            'message': 'Cache RRG limpo com sucesso',
            'cache_antes': cache_info_antes,
            'cache_depois': cache_info_depois,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Erro ao limpar cache RRG: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@rrg_bp.route('/rrg-cache', methods=['GET'])
def get_rrg_cache_info():
    """Informações sobre o cache RRG"""
    try:
        service = YFinanceRRGService()
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

@rrg_bp.route('/test-rrg', methods=['GET'])
def test_rrg():
    """Rota de teste para verificar se o RRG está funcionando"""
    try:
        service = YFinanceRRGService()
        
        # Teste básico com PETR4
        print("🧪 Testando RRG com PETR4...")
        rrg_petr4 = service.get_rrg_data('PETR4')
        
        # Teste de setor
        print("🧪 Testando RRG do setor Petróleo...")
        rrg_petroleo = service.get_sector_rrg_data('Petróleo, Gás e Bio')
        
        cache_info = service.get_cache_info()
        
        return jsonify({
            'success': True,
            'tests': {
                'ticker_test': {
                    'ticker': 'PETR4',
                    'success': rrg_petr4 is not None,
                    'data': rrg_petr4
                },
                'sector_test': {
                    'setor': 'Petróleo, Gás e Bio',
                    'success': rrg_petroleo is not None,
                    'data': rrg_petroleo
                }
            },
            'cache_info': cache_info,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Erro no teste RRG: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro no teste: {str(e)}'
        }), 500

# ===== FUNÇÕES AUXILIARES =====

def get_regime_color(regime: str) -> str:
    """Retorna cor baseada no regime"""
    cores = {
        'Leading': '#22c55e',      # Verde
        'Improving': '#3b82f6',    # Azul
        'Weakening': '#eab308',    # Amarelo
        'Lagging': '#ef4444'       # Vermelho
    }
    return cores.get(regime, '#6b7280')

# ===== FUNÇÃO PARA REGISTRAR BLUEPRINT =====
def get_rrg_blueprint():
    """Retorna o blueprint configurado"""
    return rrg_bp
"""
mm_temporal_routes.py - Routes para Market Maker Temporal Analysis
"""

from flask import Blueprint, request, jsonify
import logging
from .mm_temporal_service import mm_temporal_service
from .gamma_service import GammaService  # Para obter dados atuais

# Criar blueprint
mm_temporal_bp = Blueprint('mm_temporal', __name__, url_prefix='/pro/mm-temporal')

# Instância do serviço gamma para obter dados atuais
gamma_service = GammaService()

@mm_temporal_bp.route('/analyze', methods=['POST'])
def analyze_mm_temporal():
    """
    Endpoint principal - INTEGRADO com dados reais
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'JSON payload obrigatório'}), 400
        
        ticker = data.get('ticker')
        if not ticker:
            return jsonify({'error': 'Campo ticker obrigatório'}), 400
        
        days_back = data.get('days_back', 5)
        expiration_code = data.get('expiration_code')  # Opcional
        
        # MUDANÇA PRINCIPAL: Obter dados atuais automaticamente
        logging.info(f"Obtendo dados atuais do GEX para {ticker}")
        
        try:
            # Usar o GammaService para obter dados atuais
            gex_result = gamma_service.analyze_gamma_complete(ticker, expiration_code)
            
            if not gex_result.get('success'):
                return jsonify({
                    'error': 'Falha ao obter dados atuais de GEX',
                    'details': gex_result.get('error', 'Erro desconhecido'),
                    'success': False
                }), 500
            
            spot_price = gex_result['spot_price']
            
            # Extrair OI breakdown dos dados GEX (simulado por enquanto)
            current_oi_breakdown = {
                f"{strike}_{option_type}": {
                    'descoberto': 15000 + int(strike) * 100,  # Simulado baseado no strike
                    'total': 25000 + int(strike) * 150
                }
                for strike in [135, 140, 145, 150, 155]
                for option_type in ['CALL', 'PUT']
            }
            
        except Exception as e:
            logging.error(f"Erro ao obter dados GEX: {e}")
            return jsonify({
                'error': f'Erro ao obter dados atuais: {str(e)}',
                'success': False
            }), 500
        
        # Executar análise temporal
        logging.info(f"Iniciando análise temporal para {ticker}")
        result = mm_temporal_service.analyze_mm_temporal_complete(
            ticker, spot_price, current_oi_breakdown, days_back
        )
        
        # Adicionar dados extras para frontend
        if result.get('success'):
            result['spot_price'] = spot_price
            result['analysis_timestamp'] = data.get('timestamp', 'now')
            
        return jsonify(result), 200 if result.get('success') else 500
            
    except Exception as e:
        logging.error(f"Erro no endpoint analyze_mm_temporal: {e}")
        return jsonify({
            'error': f'Erro interno: {str(e)}',
            'success': False
        }), 500

@mm_temporal_bp.route('/availability', methods=['POST'])
def check_data_availability():
    """
    Endpoint de disponibilidade - SIMPLIFICADO
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'JSON payload obrigatório'}), 400
        
        ticker = data.get('ticker')
        if not ticker:
            return jsonify({'error': 'Campo ticker obrigatório'}), 400
        
        days_back = data.get('days_back', 10)
        
        # Usar o serviço
        result = mm_temporal_service.get_available_analysis_dates(ticker, days_back)
        
        return jsonify(result), 200 if result.get('success') else 500
            
    except Exception as e:
        logging.error(f"Erro no endpoint check_data_availability: {e}")
        return jsonify({
            'error': f'Erro interno: {str(e)}',
            'success': False
        }), 500

@mm_temporal_bp.route('/test-data/<ticker>', methods=['GET'])
def get_test_data(ticker):
    """
    NOVO ENDPOINT: Para testar sem dados reais
    """
    try:
        # Dados simulados realistas para teste
        mock_data = {
            'ticker': ticker.upper(),
            'success': True,
            'spot_price': 143.50,
            'temporal_metrics': {
                'regime_persistence': {
                    'current_regime': 'SHORT_GAMMA',
                    'persistence_days': 1,
                    'total_changes': 2,
                    'stability_score': 0.6,
                    'regime_history': ['LONG_GAMMA', 'LONG_GAMMA', 'SHORT_GAMMA', 'SHORT_GAMMA', 'SHORT_GAMMA'],
                    'interpretation': 'Regime em formação - aguardar confirmação'
                },
                'flip_evolution': {
                    'evolution': [
                        {'date': '2024-01-15', 'flip_strike': 144.2, 'distance_from_spot': 0.5},
                        {'date': '2024-01-16', 'flip_strike': 143.8, 'distance_from_spot': 0.2},
                        {'date': '2024-01-17', 'flip_strike': 143.5, 'distance_from_spot': 0.0},
                        {'date': '2024-01-18', 'flip_strike': 143.1, 'distance_from_spot': 0.3},
                        {'date': 'current', 'flip_strike': 142.8, 'distance_from_spot': 0.5}
                    ],
                    'trend_analysis': {
                        'direction': 'DESCENDO',
                        'slope': -0.35,
                        'velocity': 0.35,
                        'consistency': 0.8
                    }
                },
                'pressure_dynamics': {
                    '140.0_CALL': {
                        'strike': 140.0,
                        'current_pressure': 18000,
                        'max_pressure': 25000,
                        'consumption_rate': 0.28,
                        'pressure_status': 'ESGOTANDO'
                    },
                    '145.0_CALL': {
                        'strike': 145.0,
                        'current_pressure': 22000,
                        'max_pressure': 20000,
                        'consumption_rate': -0.1,
                        'pressure_status': 'ACUMULANDO'
                    }
                },
                'accumulation_velocity': {
                    '140.0_CALL': {
                        'strike': 140.0,
                        'current_velocity': 2500,
                        'avg_velocity': 1200,
                        'trend': 'ACELERANDO_POSITIVO',
                        'velocity_magnitude': 2500
                    },
                    '145.0_PUT': {
                        'strike': 145.0,
                        'current_velocity': -800,
                        'avg_velocity': -400,
                        'trend': 'ACELERANDO_NEGATIVO',
                        'velocity_magnitude': 800
                    }
                },
                'temporal_distortions': [
                    {
                        'type': 'DISTRIBUICAO_TIPO',
                        'distortion_type': 'CALLS_CONCENTRADAS',
                        'severity': 'MODERADA',
                        'z_score': 1.8,
                        'current_call_pct': 65.2,
                        'historical_call_pct': 52.1,
                        'interpretation': 'Concentração atual em calls está moderada vs padrão histórico'
                    }
                ]
            },
            'insights': [
                {
                    'type': 'FLIP_TREND',
                    'priority': 'MEDIUM',
                    'message': 'Gamma flip DESCENDO - MMs reposicionando estruturalmente'
                },
                {
                    'type': 'REGIME_STABILITY',
                    'priority': 'LOW',
                    'message': 'Regime SHORT_GAMMA há apenas 1 dia - aguardar confirmação'
                }
            ]
        }
        
        return jsonify(mock_data), 200
        
    except Exception as e:
        return jsonify({'error': str(e), 'success': False}), 500

@mm_temporal_bp.route('/health', methods=['GET'])
def health_check():
    """Health check com mais detalhes"""
    return jsonify({
        'service': 'MM Temporal Analysis',
        'status': 'healthy',
        'version': '1.0.0',
        'endpoints': {
            'analyze': '/pro/mm-temporal/analyze',
            'availability': '/pro/mm-temporal/availability', 
            'test_data': '/pro/mm-temporal/test-data/<ticker>',
            'health': '/pro/mm-temporal/health'
        },
        'features': [
            'Contexto Histórico dos Descobertos',
            'Evolução do Gamma Flip', 
            'Pressão Acumulada vs Liberada',
            'Regime de Persistência',
            'Velocidade de Acumulação',
            'Distorções Temporais'
        ]
    }), 200

# Error handlers melhorados
@mm_temporal_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Endpoint não encontrado',
        'available_endpoints': {
            'POST /pro/mm-temporal/analyze': 'Análise temporal completa',
            'POST /pro/mm-temporal/availability': 'Verificar dados disponíveis',
            'GET /pro/mm-temporal/test-data/<ticker>': 'Dados de teste',
            'GET /pro/mm-temporal/health': 'Health check'
        }
    }), 404

@mm_temporal_bp.errorhandler(500)
def internal_error(error):
    logging.error(f"Erro interno MM Temporal: {error}")
    return jsonify({
        'error': 'Erro interno do servidor',
        'service': 'MM Temporal Analysis',
        'suggestion': 'Tente novamente ou use o endpoint de test-data para validar'
    }), 500

# Logging middleware
@mm_temporal_bp.before_request
def log_request():
    logging.info(f"MM Temporal: {request.method} {request.endpoint}")
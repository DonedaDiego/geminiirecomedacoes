from flask import Blueprint, request, jsonify
from atsmom_service import ATSMOMService
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Criar blueprint
atsmom_bp = Blueprint('atsmom', __name__, url_prefix='/atsmom')

# Instanciar serviço
atsmom_service = ATSMOMService()

@atsmom_bp.route('/health', methods=['GET'])
def health_check():
    """Endpoint para verificar saúde do serviço"""
    try:
        return jsonify({
            'status': 'OK',
            'message': 'Serviço ATSMOM funcionando corretamente (5 anos)',
            'period': '5y',
            'timestamp': atsmom_service.get_available_symbols()[:5]  # Teste básico
        })
    except Exception as e:
        logger.error(f"Erro no health check: {e}")
        return jsonify({
            'status': 'ERROR',
            'message': f'Erro no serviço: {str(e)}'
        }), 500

@atsmom_bp.route('/symbols', methods=['GET'])
def get_symbols():
    """Retorna lista de símbolos disponíveis"""
    try:
        symbols = atsmom_service.get_available_symbols()
        return jsonify({
            'success': True,
            'symbols': symbols,
            'total': len(symbols),
            'period': '5y'
        })
    except Exception as e:
        logger.error(f"Erro ao obter símbolos: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@atsmom_bp.route('/analyze', methods=['POST'])
def analyze_asset():
    """
    Analisa um ativo usando ATSMOM (sempre 5 anos)
    
    Payload esperado:
    {
        "symbol": "PETR4"
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Dados não fornecidos'
            }), 400
        
        symbol = data.get('symbol', '').upper().strip()
        if not symbol:
            return jsonify({
                'success': False,
                'error': 'Símbolo é obrigatório'
            }), 400
        
        logger.info(f"Analisando {symbol} com período fixo de 5 anos")
        
        # Executar análise (sempre 5 anos)
        result = atsmom_service.analyze_single_asset(symbol)
        
        if result['success']:
            logger.info(f"Análise de {symbol} concluída com sucesso")
        else:
            logger.warning(f"Erro na análise de {symbol}: {result.get('error')}")
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Erro no endpoint de análise: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@atsmom_bp.route('/compare', methods=['POST'])
def compare_assets():

    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Dados não fornecidos'
            }), 400
        
        symbol1 = data.get('symbol1', '').upper().strip()
        symbol2 = data.get('symbol2', '').upper().strip()
        
        if not symbol1 or not symbol2:
            return jsonify({
                'success': False,
                'error': 'Ambos os símbolos são obrigatórios'
            }), 400
        
        if symbol1 == symbol2:
            return jsonify({
                'success': False,
                'error': 'Os símbolos devem ser diferentes'
            }), 400
        
        logger.info(f"Comparando {symbol1} vs {symbol2} (5 anos)")
        
        # Analisar ambos os ativos (sempre 5 anos)
        result1 = atsmom_service.analyze_single_asset(symbol1)
        result2 = atsmom_service.analyze_single_asset(symbol2)
        
        if not result1['success']:
            return jsonify({
                'success': False,
                'error': f'Erro ao analisar {symbol1}: {result1["error"]}'
            })
        
        if not result2['success']:
            return jsonify({
                'success': False,
                'error': f'Erro ao analisar {symbol2}: {result2["error"]}'
            })
        
        # Compilar comparação
        comparison = {
            'symbol1': {
                'symbol': symbol1,
                'data': result1['analysis_data']
            },
            'symbol2': {
                'symbol': symbol2,
                'data': result2['analysis_data']
            },
            'comparison_summary': {
                'stronger_signal': symbol1 if abs(result1['analysis_data']['current_signal']) > abs(result2['analysis_data']['current_signal']) else symbol2,
                'higher_volatility': symbol1 if result1['analysis_data']['current_volatility'] > result2['analysis_data']['current_volatility'] else symbol2,
                'higher_beta': symbol1 if result1['analysis_data']['beta'] > result2['analysis_data']['beta'] else symbol2
            }
        }
        
        logger.info(f"Comparação {symbol1} vs {symbol2} concluída")
        
        return jsonify({
            'success': True,
            'comparison': comparison,
            'period': '5y'
        })
        
    except Exception as e:
        logger.error(f"Erro no endpoint de comparação: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

# Função para registrar o blueprint
def register_atsmom_routes(app):
    """Registra as rotas ATSMOM na aplicação Flask"""
    app.register_blueprint(atsmom_bp)
    logger.info("Rotas ATSMOM registradas com sucesso (5 anos fixo)")
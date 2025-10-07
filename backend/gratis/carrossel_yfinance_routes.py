"""
Blueprint de rotas para o carrossel de ações
Fornece endpoints para dados em tempo real do carrossel
"""

from flask import Blueprint, jsonify, request
from gratis.carrossel_yfinance_service import CarrosselYFinanceService
import logging
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)

# Criar blueprint
carrossel_bp = Blueprint('carrossel', __name__, url_prefix='/api/carrossel')

# Cache simples para evitar muitas requisições
_cache = {
    'data': None,
    'timestamp': None,
    'ttl': 30  # 30 segundos de cache
}

def is_cache_valid():
    """Verifica se o cache ainda é válido"""
    if not _cache['data'] or not _cache['timestamp']:
        return False
    
    return (datetime.now() - _cache['timestamp']).total_seconds() < _cache['ttl']

def update_cache(data):
    """Atualiza o cache com novos dados"""
    _cache['data'] = data
    _cache['timestamp'] = datetime.now()

@carrossel_bp.route('/stocks', methods=['GET'])
def get_carrossel_stocks():
    """
    Endpoint principal para obter dados do carrossel
    GET /api/carrossel/stocks
    
    Query Parameters:
    - force_refresh: bool - força atualização ignorando cache
    
    Response:
    {
        "success": true,
        "data": {
            "stocks": [...],
            "market_stats": {...},
            "total_stocks": 12,
            "last_update": "25/06/2025 14:30:15",
            "cache_hit": false
        }
    }
    """
    try:
        start_time = time.time()
        
        # Verificar se deve usar cache
        force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
        
        if not force_refresh and is_cache_valid():
            logger.info(" Carrossel: Dados servidos do cache")
            response_data = _cache['data'].copy()
            response_data['data']['cache_hit'] = True
            response_data['data']['response_time'] = round((time.time() - start_time) * 1000, 2)
            return jsonify(response_data)
        
        # Buscar dados frescos
        logger.info("🔄 Carrossel: Buscando dados frescos...")
        carrossel_data = CarrosselYFinanceService.get_carrossel_data()
        
        if carrossel_data['success']:
            # Adicionar informações de resposta
            carrossel_data['data']['cache_hit'] = False
            carrossel_data['data']['response_time'] = round((time.time() - start_time) * 1000, 2)
            
            # Atualizar cache
            update_cache(carrossel_data)
            
            logger.info(f" Carrossel: {carrossel_data['data']['total_stocks']} ações em {carrossel_data['data']['response_time']}ms")
            
            return jsonify(carrossel_data)
        else:
            logger.error(f" Carrossel: Erro ao buscar dados - {carrossel_data.get('error')}")
            return jsonify(carrossel_data), 500
            
    except Exception as e:
        logger.error(f" Erro no endpoint /stocks: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}',
            'data': {
                'stocks': [],
                'market_stats': {'positive': 0, 'negative': 0, 'neutral': 0},
                'total_stocks': 0,
                'last_update': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            }
        }), 500

@carrossel_bp.route('/stock/<symbol>', methods=['GET'])
def get_single_stock(symbol):
    """
    Endpoint para obter dados de uma ação específica
    GET /api/carrossel/stock/PETR4
    
    Response:
    {
        "success": true,
        "data": {
            "symbol": "PETR4",
            "name": "Petróleo Brasileiro S.A. - Petrobras",
            "price": 35.42,
            "change": 0.85,
            "change_percent": 2.46,
            "volume": 45234567,
            "last_update": "14:30"
        }
    }
    """
    try:
        start_time = time.time()
        
        if not symbol:
            return jsonify({
                'success': False,
                'error': 'Símbolo da ação é obrigatório'
            }), 400
        
        # Limpar e formatar símbolo
        symbol = symbol.upper().strip()
        
        logger.info(f"🔍 Buscando dados de: {symbol}")
        
        # Buscar dados da ação
        stock_data = CarrosselYFinanceService.get_stock_by_symbol(symbol)
        
        if stock_data:
            response_data = {
                'success': True,
                'data': stock_data,
                'response_time': round((time.time() - start_time) * 1000, 2)
            }
            
            logger.info(f" {symbol}: R$ {stock_data['price']} ({stock_data['change_percent']:+.2f}%)")
            return jsonify(response_data)
        else:
            logger.warning(f"⚠️ Ação {symbol} não encontrada")
            return jsonify({
                'success': False,
                'error': f'Dados da ação {symbol} não encontrados',
                'data': None
            }), 404
            
    except Exception as e:
        logger.error(f" Erro ao buscar {symbol}: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}',
            'data': None
        }), 500

@carrossel_bp.route('/market-stats', methods=['GET'])
def get_market_stats():
    """
    Endpoint para obter apenas estatísticas do mercado
    GET /api/carrossel/market-stats
    
    Response:
    {
        "success": true,
        "data": {
            "positive": 8,
            "negative": 3,
            "neutral": 1,
            "total": 12,
            "average_change": 1.25,
            "positive_percent": 66.7,
            "negative_percent": 25.0
        }
    }
    """
    try:
        # Verificar cache primeiro
        if is_cache_valid() and _cache['data'] and _cache['data']['success']:
            market_stats = _cache['data']['data']['market_stats']
            return jsonify({
                'success': True,
                'data': market_stats,
                'cache_hit': True
            })
        
        # Buscar dados frescos se cache inválido
        carrossel_data = CarrosselYFinanceService.get_carrossel_data()
        
        if carrossel_data['success']:
            update_cache(carrossel_data)
            return jsonify({
                'success': True,
                'data': carrossel_data['data']['market_stats'],
                'cache_hit': False
            })
        else:
            return jsonify({
                'success': False,
                'error': carrossel_data.get('error', 'Erro desconhecido')
            }), 500
            
    except Exception as e:
        logger.error(f" Erro ao buscar estatísticas do mercado: {e}")
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@carrossel_bp.route('/status', methods=['GET'])
def get_carrossel_status():
    """
    Endpoint para verificar status do serviço de carrossel
    GET /api/carrossel/status
    
    Response:
    {
        "success": true,
        "data": {
            "service": "online",
            "cache_status": "valid",
            "last_update": "25/06/2025 14:30:15",
            "total_tickers": 12,
            "cache_ttl": 30
        }
    }
    """
    try:
        cache_status = "valid" if is_cache_valid() else "expired"
        
        return jsonify({
            'success': True,
            'data': {
                'service': 'online',
                'cache_status': cache_status,
                'last_update': _cache['timestamp'].strftime('%d/%m/%Y %H:%M:%S') if _cache['timestamp'] else 'Nunca',
                'total_tickers': len(CarrosselYFinanceService.MAIN_TICKERS),
                'cache_ttl': _cache['ttl'],
                'available_endpoints': [
                    '/api/carrossel/stocks',
                    '/api/carrossel/stock/<symbol>',
                    '/api/carrossel/market-stats',
                    '/api/carrossel/status'
                ]
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }), 500

@carrossel_bp.route('/clear-cache', methods=['POST'])
def clear_cache():
    """
    Endpoint para limpar cache (útil para desenvolvimento)
    POST /api/carrossel/clear-cache
    """
    try:
        _cache['data'] = None
        _cache['timestamp'] = None
        
        logger.info("🗑️ Cache do carrossel limpo")
        
        return jsonify({
            'success': True,
            'message': 'Cache limpo com sucesso',
            'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Erro ao limpar cache: {str(e)}'
        }), 500

# Função para obter blueprint (usada no main.py)
def get_carrossel_blueprint():
    """
    Função para obter o blueprint do carrossel
    Usado para registrar no main.py
    """
    return carrossel_bp

# Tratamento de erro para o blueprint
@carrossel_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint não encontrado',
        'available_endpoints': [
            '/api/carrossel/stocks',
            '/api/carrossel/stock/<symbol>',
            '/api/carrossel/market-stats',
            '/api/carrossel/status'
        ]
    }), 404

@carrossel_bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Erro interno do servidor',
        'message': 'Tente novamente em alguns instantes'
    }), 500


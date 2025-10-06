"""
historical_routes.py - Rotas para análise histórica
"""

from flask import Blueprint, request, jsonify
from .historical_service import HistoricalService
import logging

def create_historical_blueprint():
    """Cria blueprint para análise histórica"""
    
    historical_bp = Blueprint('historical', __name__, url_prefix='/pro/historical')
    historical_service = HistoricalService()
    
    @historical_bp.route('/expirations', methods=['POST'])
    def get_historical_expirations():
        """Obter vencimentos disponíveis para análise histórica"""
        try:
            data = request.get_json()
            ticker = data.get('ticker')
            
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            logging.info(f"Buscando vencimentos históricos para {ticker}")
            
            expirations = historical_service.get_available_expirations(ticker)
            total_available = sum(1 for exp in expirations if exp['available'])
            
            return jsonify({
                'expirations': expirations,
                'total_available': total_available,
                'success': True
            })
            
        except Exception as e:
            logging.error(f"Erro ao buscar vencimentos históricos: {e}")
            return jsonify({'error': str(e)}), 500

    @historical_bp.route('/analyze', methods=['POST'])
    def analyze_historical():
        """Executar análise histórica completa"""
        try:
            data = request.get_json()
            ticker = data.get('ticker')
            vencimento = data.get('vencimento')
            days_back = data.get('days_back', 5)
            
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            if not vencimento:
                return jsonify({'error': 'Vencimento é obrigatório'}), 400
            
            logging.info(f"Iniciando análise histórica: {ticker} - {vencimento} - {days_back} dias")
            
            result = historical_service.analyze_historical_complete(ticker, vencimento, days_back)
            
            logging.info(f"Análise histórica concluída para {ticker}")
            return jsonify(result)
            
        except Exception as e:
            logging.error(f"Erro na análise histórica: {e}")
            return jsonify({'error': str(e)}), 500

    @historical_bp.route('/health', methods=['GET'])
    def health_check():
        """Health check do serviço histórico"""
        return jsonify({
            'service': 'historical',
            'status': 'active',
            'message': 'Serviço de análise histórica funcionando'
        })

    return historical_bp

def get_historical_blueprint():
    """Função helper para obter o blueprint"""
    return create_historical_blueprint()
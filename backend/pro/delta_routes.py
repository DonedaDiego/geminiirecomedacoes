"""
delta_routes.py - Rotas DEX simplificadas
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import logging
import traceback

from .delta_service import DeltaService

def get_delta_blueprint():
    """Factory function para criar o blueprint do DEX"""
    
    delta_bp = Blueprint('delta', __name__)
    logging.basicConfig(level=logging.INFO)
    service = DeltaService()

    @delta_bp.route('/pro/delta/expirations', methods=['POST'])
    def get_available_expirations():
        """Retorna vencimentos disponíveis"""
        try:
            data = request.get_json()
            ticker = data.get('ticker', '').strip().upper()
            
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            logging.info(f"API: Buscando vencimentos para {ticker}")
            
            expirations = service.get_available_expirations(ticker)
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'ticker': ticker.replace('.SA', ''),
                'expirations': expirations,
                'total_available': len([e for e in expirations if e['available']])
            }
            
            return jsonify(response)
            
        except Exception as e:
            logging.error(f"Erro ao buscar vencimentos: {str(e)}")
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @delta_bp.route('/pro/delta/analyze', methods=['POST'])
    def analyze_dex_complete():
        """Análise completa de DEX com os 6 gráficos"""
        try:
            data = request.get_json()
            
            ticker = data.get('ticker', '').strip().upper()
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            expiration_code = data.get('expiration_code')
            days_back = data.get('days_back', 60)
            
            logging.info(f"API: Análise DEX solicitada para {ticker}")
            if expiration_code:
                logging.info(f"Vencimento específico: {expiration_code}")
            
            # Executar análise DEX
            result = service.analyze_delta_complete(ticker, expiration_code, days_back)
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'ticker': ticker.replace('.SA', ''),
                'analysis_type': 'DEX_COMPLETE_6_CHARTS',
                **result
            }
            
            logging.info(f"API: Análise DEX concluída para {ticker}")
            return jsonify(response)
            
        except ValueError as e:
            logging.error(f"Erro de validação DEX: {str(e)}")
            return jsonify({'error': str(e)}), 404
            
        except Exception as e:
            logging.error(f"Erro na análise DEX: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @delta_bp.route('/pro/delta/health', methods=['GET'])
    def dex_health_check():
        """Health check do sistema DEX"""
        return jsonify({
            'service': 'DEX Analysis',
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0-simplified',
            'features': [
                ' Automáticos',
                'Seleção de Vencimentos',
                'Pressão Direcional',
                'Target Detection',
                'Real-time Analysis'
            ]
        })

    return delta_bp
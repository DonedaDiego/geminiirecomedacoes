"""
vega_routes.py - Rotas VEX simplificadas
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import logging
import traceback

from .vega_service import VegaService

def get_vega_blueprint():
    """Factory function para criar o blueprint do VEX"""
    
    vega_bp = Blueprint('vega', __name__)
    logging.basicConfig(level=logging.INFO)
    service = VegaService()

    @vega_bp.route('/pro/vega/expirations', methods=['POST'])
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

    @vega_bp.route('/pro/vega/analyze', methods=['POST'])
    def analyze_vex_complete():
        """Análise completa de VEX com os 6 gráficos"""
        try:
            data = request.get_json()
            
            ticker = data.get('ticker', '').strip().upper()
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            expiration_code = data.get('expiration_code')
            days_back = data.get('days_back', 60)
            
            logging.info(f"API: Análise VEX solicitada para {ticker}")
            if expiration_code:
                logging.info(f"Vencimento específico: {expiration_code}")
            
            result = service.analyze_vega_complete(ticker, expiration_code, days_back)
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'ticker': ticker.replace('.SA', ''),
                'analysis_type': 'VEX_COMPLETE_6_CHARTS',
                **result
            }
            
            logging.info(f"API: Análise VEX concluída para {ticker}")
            return jsonify(response)
            
        except ValueError as e:
            logging.error(f"Erro de validação VEX: {str(e)}")
            return jsonify({'error': str(e)}), 404
            
        except Exception as e:
            logging.error(f"Erro na análise VEX: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @vega_bp.route('/pro/vega/health', methods=['GET'])
    def vex_health_check():
        """Health check do sistema VEX"""
        return jsonify({
            'service': 'VEX Analysis',
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0-simplified',
            'features': [
                ' Automáticos',
                'Seleção de Vencimentos',
                'Análise de Volatilidade',
                'Regime Detection',
                'Real-time Analysis'
            ]
        })

    return vega_bp
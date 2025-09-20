"""
theta_routes.py - Rotas TEX simplificadas
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import logging
import traceback

from .theta_service import ThetaService

def get_theta_blueprint():
    """Factory function para criar o blueprint do TEX"""
    
    theta_bp = Blueprint('theta', __name__)
    logging.basicConfig(level=logging.INFO)
    service = ThetaService()

    @theta_bp.route('/pro/theta/expirations', methods=['POST'])
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

    @theta_bp.route('/pro/theta/analyze', methods=['POST'])
    def analyze_tex_complete():
        """Análise completa de TEX com os 6 gráficos"""
        try:
            data = request.get_json()
            
            ticker = data.get('ticker', '').strip().upper()
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            expiration_code = data.get('expiration_code')
            days_back = data.get('days_back', 60)
            
            logging.info(f"API: Análise TEX solicitada para {ticker}")
            if expiration_code:
                logging.info(f"Vencimento específico: {expiration_code}")
            
            result = service.analyze_theta_complete(ticker, expiration_code, days_back)
            
            # VERIFICAR SE RESULT NÃO É NONE
            if result is None:
                logging.error("Service retornou None")
                return jsonify({'error': 'Falha na análise TEX - resultado nulo'}), 500
            
            # CONSTRUIR RESPONSE SEGURA
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'ticker': ticker.replace('.SA', ''),
                'analysis_type': 'TEX_COMPLETE_6_CHARTS'
            }
            
            # ADICIONAR RESULT APENAS SE VÁLIDO
            response.update(result)
            
            logging.info(f"API: Análise TEX concluída para {ticker}")
            return jsonify(response)
            
        except ValueError as e:
            logging.error(f"Erro de validação TEX: {str(e)}")
            return jsonify({'error': str(e)}), 404
            
        except Exception as e:
            logging.error(f"Erro na análise TEX: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @theta_bp.route('/pro/theta/health', methods=['GET'])
    def tex_health_check():
        """Health check do sistema TEX"""
        return jsonify({
            'service': 'TEX Analysis',
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0-simplified',
            'features': [
                ' Automáticos',
                'Seleção de Vencimentos',
                'Análise Decaimento',
                'Regime Detection',
                'Real-time Analysis'
            ]
        })

    return theta_bp
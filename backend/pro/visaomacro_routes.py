"""
visaomacro_routes.py - Rotas da Visão Macro Multidimensional
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import logging
import traceback

from .visaomacro_service import VisaoMacroService


def get_visaomacro_blueprint():
    """Factory function para criar o blueprint da Visão Macro"""

    visaomacro_bp = Blueprint('visaomacro', __name__)
    logging.basicConfig(level=logging.INFO)
    service = VisaoMacroService()

    @visaomacro_bp.route('/pro/visaomacro/analyze', methods=['POST'])
    def analyze_macro():
        """Análise macro completa - Agrega Gamma, Delta, Vega e Theta"""
        try:
            data = request.get_json()

            ticker = data.get('ticker', '').strip().upper()
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400

            expiration_code = data.get('expiration_code')

            logging.info(f"API: Análise MACRO solicitada para {ticker}")
            if expiration_code:
                logging.info(f"Vencimento específico: {expiration_code}")

            # Executar análise macro
            result = service.analyze_macro(ticker, expiration_code)

            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'ticker': ticker.replace('.SA', ''),
                'analysis_type': 'MACRO_MULTIDIMENSIONAL',
                **result
            }

            logging.info(f"API: Análise MACRO concluída para {ticker}")
            return jsonify(response)

        except ValueError as e:
            logging.error(f"Erro de validação MACRO: {str(e)}")
            return jsonify({'error': str(e)}), 404

        except Exception as e:
            logging.error(f"Erro na análise MACRO: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @visaomacro_bp.route('/pro/visaomacro/health', methods=['GET'])
    def macro_health_check():
        """Health check do sistema de Visão Macro"""
        return jsonify({
            'service': 'Visão Macro Multidimensional',
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0',
            'features': [
                'Agregação Gamma + Delta + Vega + Theta',
                'Análise Integrada de Greeks',
                'Alertas Inteligentes',
                'Identificação de Oportunidades',
                'Gráficos Consolidados'
            ]
        })

    return visaomacro_bp

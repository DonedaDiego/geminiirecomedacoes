"""
bandas_pro_routes.py
Rotas da API para o sistema de Bandas PRO
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import logging
import traceback

# Import do serviço
from .bandas_pro_service import BandasProService

def get_bandas_pro_blueprint():
    """Factory function para criar o blueprint das bandas PRO"""
    
    bandas_pro_bp = Blueprint('bandas_pro', __name__)
    
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Instância do serviço
    service = BandasProService()

    @bandas_pro_bp.route('/pro/bandas/analyze', methods=['POST'])
    def analyze_complete():
        """Análise completa: Bandas + Flow"""
        try:
            data = request.get_json()
            
            # Validação de parâmetros
            ticker = data.get('ticker', '').strip().upper()
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            period = data.get('period', '6mo')
            flow_days = data.get('flow_days', 30)
            
            # Validações adicionais
            if flow_days < 7 or flow_days > 90:
                return jsonify({'error': 'flow_days deve estar entre 7 e 90'}), 400
            
            logging.info(f"API: Análise completa solicitada para {ticker}")
            
            # Executar análise
            
            result = service.analyze_complete(ticker, period, flow_days)
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                **result
            }
            
            return jsonify(response)
            
        except ValueError as e:
            logging.error(f"Erro de validação: {str(e)}")
            return jsonify({'error': str(e)}), 404
            
        except Exception as e:
            logging.error(f"Erro na análise completa: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @bandas_pro_bp.route('/pro/bandas/analyze-bands', methods=['POST'])
    def analyze_bands_only():
        """Análise apenas das Bandas de Volatilidade"""
        try:
            data = request.get_json()
            
            # Validação de parâmetros
            ticker = data.get('ticker', '').strip().upper()
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            period = data.get('period', '6mo')
            logging.info(f"API: Análise de bandas solicitada para {ticker}")
            
            # Executar análise
            result = service.analyze_bands(ticker, period)
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'ticker': ticker.replace('.SA', ''),
                **result
            }
            
            return jsonify(response)
            
        except ValueError as e:
            logging.error(f"Erro de validação: {str(e)}")
            return jsonify({'error': str(e)}), 404
            
        except Exception as e:
            logging.error(f"Erro na análise de bandas: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @bandas_pro_bp.route('/pro/bandas/analyze-flow', methods=['POST'])
    def analyze_flow_only():
        """Análise apenas do Flow de Opções"""
        try:
            data = request.get_json()
            
            # Validação de parâmetros
            ticker = data.get('ticker', '').strip().upper()
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            flow_days = data.get('flow_days', 30)
            
            # Validações adicionais
            if flow_days < 7 or flow_days > 90:
                return jsonify({'error': 'flow_days deve estar entre 7 e 90'}), 400
            
            logging.info(f"API: Análise de flow solicitada para {ticker}")
            
            # Executar análise
            result = service.analyze_flow(ticker, flow_days)
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'ticker': ticker.replace('.SA', ''),
                **result
            }
            
            return jsonify(response)
            
        except ValueError as e:
            logging.error(f"Erro de validação: {str(e)}")
            return jsonify({'error': str(e)}), 404
            
        except Exception as e:
            logging.error(f"Erro na análise de flow: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @bandas_pro_bp.route('/pro/bandas/health', methods=['GET'])
    def health_check():
        """Health check da API"""
        return jsonify({
            'status': 'healthy',
            'service': 'Bandas PRO API',
            'version': '1.0.0',
            'timestamp': datetime.now().isoformat(),
            'endpoints': [
                'POST /pro/bandas/analyze - Análise Completa',
                'POST /pro/bandas/analyze-bands - Apenas Bandas',
                'POST /pro/bandas/analyze-flow - Apenas Flow',
                'GET /pro/bandas/health - Health Check'
            ]
        })

    @bandas_pro_bp.route('/pro/bandas/tickers/validate', methods=['POST'])
    def validate_ticker():
        """Valida se um ticker está disponível"""
        try:
            data = request.get_json()
            ticker = data.get('ticker', '').strip().upper()
            
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            # Tentar carregar dados básicos para validar
            from .bandas_pro_service import HybridVolatilityBands
            import yfinance as yf
            
            # Normalizar ticker
            if len(ticker) <= 6 and not ticker.endswith('.SA') and '-' not in ticker:
                test_ticker = ticker + '.SA'
            else:
                test_ticker = ticker
            
            # Testar se ticker existe
            stock = yf.Ticker(test_ticker)
            info = stock.info
            
            # Verificar se tem dados básicos
            if not info or 'regularMarketPrice' not in info:
                return jsonify({
                    'valid': False,
                    'ticker': ticker,
                    'message': 'Ticker não encontrado ou sem dados'
                })
            
            return jsonify({
                'valid': True,
                'ticker': ticker,
                'normalized_ticker': test_ticker,
                'name': info.get('longName', ticker),
                'currency': info.get('currency', 'BRL'),
                'market': info.get('exchange', 'BVSP')
            })
            
        except Exception as e:
            return jsonify({
                'valid': False,
                'ticker': ticker if 'ticker' in locals() else '',
                'message': f'Erro na validação: {str(e)}'
            })

    @bandas_pro_bp.route('/pro/bandas/status', methods=['GET'])
    def service_status():
        """Status detalhado do serviço"""
        try:
            # Testar componentes principais
            from .bandas_pro_service import VolatilityValidator, GeminiiFlowTracker
            
            status = {
                'service': 'Bandas PRO',
                'timestamp': datetime.now().isoformat(),
                'status': 'operational',
                'components': {}
            }
            
            # Testar validador IV
            try:
                iv_validator = VolatilityValidator()
                status['components']['iv_validator'] = 'operational'
            except Exception as e:
                status['components']['iv_validator'] = f'error: {str(e)}'
            
            # Testar flow tracker
            try:
                flow_tracker = GeminiiFlowTracker()
                status['components']['flow_tracker'] = 'operational'
            except Exception as e:
                status['components']['flow_tracker'] = f'error: {str(e)}'
            
            # Testar yfinance
            try:
                import yfinance as yf
                status['components']['yfinance'] = 'operational'
            except Exception as e:
                status['components']['yfinance'] = f'error: {str(e)}'
            
            # Testar bibliotecas ML
            try:
                import xgboost as xgb
                from arch import arch_model
                status['components']['ml_libraries'] = 'operational'
            except Exception as e:
                status['components']['ml_libraries'] = f'error: {str(e)}'
            
            return jsonify(status)
            
        except Exception as e:
            return jsonify({
                'service': 'Bandas PRO',
                'timestamp': datetime.now().isoformat(),
                'status': 'error',
                'error': str(e)
            }), 500

    return bandas_pro_bp
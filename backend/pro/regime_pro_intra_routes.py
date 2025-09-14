"""
regime_pro_intra_routes.py
Rotas da API para o sistema de Flow Intraday
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import logging
import traceback

# Import do serviço
from .regime_pro_intra_service import RegimeProIntraService

def get_regime_pro_intra_blueprint():
    """Factory function para criar o blueprint do flow intraday"""
    
    intra_bp = Blueprint('regime_pro_intra', __name__)
    
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Instância do serviço
    service = RegimeProIntraService()

    @intra_bp.route('/pro/intraday/analyze', methods=['POST'])
    def analyze_intraday_flow():
        """Análise de Flow Intraday"""
        try:
            data = request.get_json()
            
            # Validação de parâmetros
            ticker = data.get('ticker', '').strip().upper()
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            logging.info(f"API: Análise intraday solicitada para {ticker}")
            
            # Executar análise
            result = service.analyze_intraday_flow(ticker)
            
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
            logging.error(f"Erro na análise intraday: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @intra_bp.route('/pro/intraday/health', methods=['GET'])
    def health_check():
        """Health check da API intraday"""
        return jsonify({
            'status': 'healthy',
            'service': 'Regime PRO Intraday API',
            'version': '1.0.0',
            'timestamp': datetime.now().isoformat(),
            'endpoints': [
                'POST /pro/intraday/analyze - Análise Flow Intraday',
                'GET /pro/intraday/health - Health Check',
                'GET /pro/intraday/status - Status Detalhado'
            ]
        })

    @intra_bp.route('/pro/intraday/tickers/validate', methods=['POST'])
    def validate_ticker():
        """Valida se um ticker está disponível para análise intraday"""
        try:
            data = request.get_json()
            ticker = data.get('ticker', '').strip().upper()
            
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            # Testar se ticker existe usando yfinance
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
            
            # Testar se há opções disponíveis na OpLab
            from .regime_pro_intra_service import GeminiiIntradayFlowTracker
            flow_tracker = GeminiiIntradayFlowTracker()
            
            ticker_clean = ticker.replace('.SA', '')
            options_list = flow_tracker.get_options_list(ticker_clean)
            
            if not options_list:
                return jsonify({
                    'valid': False,
                    'ticker': ticker,
                    'message': 'Nenhuma opção encontrada para este ticker'
                })
            
            return jsonify({
                'valid': True,
                'ticker': ticker,
                'normalized_ticker': test_ticker,
                'name': info.get('longName', ticker),
                'currency': info.get('currency', 'BRL'),
                'market': info.get('exchange', 'BVSP'),
                'options_count': len(options_list)
            })
            
        except Exception as e:
            return jsonify({
                'valid': False,
                'ticker': ticker if 'ticker' in locals() else '',
                'message': f'Erro na validação: {str(e)}'
            })

    @intra_bp.route('/pro/intraday/status', methods=['GET'])
    def service_status():
        """Status detalhado do serviço intraday"""
        try:
            from .regime_pro_intra_service import GeminiiIntradayFlowTracker
            
            status = {
                'service': 'Regime PRO Intraday',
                'timestamp': datetime.now().isoformat(),
                'status': 'operational',
                'components': {}
            }
            
            # Testar flow tracker
            try:
                flow_tracker = GeminiiIntradayFlowTracker()
                status['components']['flow_tracker'] = 'operational'
            except Exception as e:
                status['components']['flow_tracker'] = f'error: {str(e)}'
            
            # Testar yfinance
            try:
                import yfinance as yf
                status['components']['yfinance'] = 'operational'
            except Exception as e:
                status['components']['yfinance'] = f'error: {str(e)}'
            
            # Testar API OpLab
            try:
                import requests
                response = requests.get(
                    "https://api.oplab.com.br/v3/market/options", 
                    headers={
                        "Access-Token": "7gMd+LaFRJ6u6bmjgv9gxeGd5fAc6EHtpM4UoQ41tLivobEa4YTd5dA9xi00s/yd--NJ1uhr4hX+m6KeMsjdVfog==--ZTMyNzIyMjM3OGIxYThmN2YzNzdmZmYzOTZjY2RhYzc=",
                        "Content-Type": "application/json"
                    },
                    params={'limit': 1},
                    timeout=10
                )
                
                if response.status_code == 200:
                    status['components']['oplab_api'] = 'operational'
                else:
                    status['components']['oplab_api'] = f'error: HTTP {response.status_code}'
                    
            except Exception as e:
                status['components']['oplab_api'] = f'error: {str(e)}'
            
            # Testar bibliotecas necessárias
            try:
                import numpy as np
                import pandas as pd
                status['components']['data_libraries'] = 'operational'
            except Exception as e:
                status['components']['data_libraries'] = f'error: {str(e)}'
            
            return jsonify(status)
            
        except Exception as e:
            return jsonify({
                'service': 'Regime PRO Intraday',
                'timestamp': datetime.now().isoformat(),
                'status': 'error',
                'error': str(e)
            }), 500

    @intra_bp.route('/pro/intraday/debug/<ticker>', methods=['GET'])
    def debug_ticker_options(ticker):
        """Endpoint de debug para investigar opções disponíveis"""
        try:
            from .regime_pro_intra_service import GeminiiIntradayFlowTracker
            import requests
            
            ticker = ticker.upper().replace('.SA', '')
            flow_tracker = GeminiiIntradayFlowTracker()
            
            debug_info = {
                'ticker': ticker,
                'timestamp': datetime.now().isoformat(),
                'tests': {}
            }
            
            # Teste 1: API de stocks (endpoint correto)
            try:
                response = requests.get(
                    "https://api.oplab.com.br/v3/market/stocks",
                    headers=flow_tracker.headers,
                    params={'symbol': ticker, 'limit': 1},
                    timeout=10
                )
                
                debug_info['tests']['stocks_api'] = {
                    'status_code': response.status_code,
                    'response': response.json() if response.status_code == 200 else response.text[:200]
                }
            except Exception as e:
                debug_info['tests']['stocks_api'] = {'error': str(e)}
            
            # Teste 2: Testar símbolos conhecidos de opções
            known_symbols = ['PETRE100', 'PETRE110', 'PETRE120', 'PETRT90', 'PETRT100']
            
            for symbol in known_symbols:
                try:
                    response = requests.get(
                        f"https://api.oplab.com.br/v3/market/options/details/{symbol}",
                        headers=flow_tracker.headers,
                        timeout=10
                    )
                    
                    debug_info['tests'][f'option_{symbol}'] = {
                        'status_code': response.status_code,
                        'exists': response.status_code == 200,
                        'data': response.json() if response.status_code == 200 else None
                    }
                except Exception as e:
                    debug_info['tests'][f'option_{symbol}'] = {'error': str(e)}
            
            # Teste 3: Preço atual
            debug_info['current_price'] = flow_tracker.get_current_stock_price(ticker)
            
            return jsonify(debug_info)
            
        except Exception as e:
            return jsonify({
                'error': str(e),
                'ticker': ticker,
                'timestamp': datetime.now().isoformat()
            }), 500

    return intra_bp
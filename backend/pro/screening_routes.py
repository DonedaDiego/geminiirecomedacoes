"""
screening_routes.py - Rotas para Screening de Gamma Flip
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import logging
import traceback

from .screening_service import ScreeningService

def get_screening_blueprint():
    """Factory function para criar o blueprint do Screening"""
    
    screening_bp = Blueprint('screening', __name__)
    logging.basicConfig(level=logging.INFO)
    service = ScreeningService()

    @screening_bp.route('/pro/screening/flip', methods=['POST'])
    def screen_gamma_flip():        
        try:
            data = request.get_json()
            
            tickers = data.get('tickers', [])
            if not tickers or not isinstance(tickers, list):
                return jsonify({
                    'error': 'Lista de tickers é obrigatória',
                    'example': {'tickers': ['PETR4', 'VALE3', 'BBAS3']}
                }), 400
            
            # Remove duplicatas e limpa tickers
            tickers = list(set([t.strip().upper() for t in tickers if t.strip()]))
            
            if not tickers:
                return jsonify({'error': 'Nenhum ticker válido fornecido'}), 400
            
            # Configuração opcional de workers
            max_workers = data.get('max_workers')
            if max_workers:
                service.max_workers = min(max_workers, 10)  # Máximo de 10
            
            logging.info(f"API Screening: {len(tickers)} tickers solicitados")
            logging.info(f"Tickers: {', '.join(tickers[:5])}{'...' if len(tickers) > 5 else ''}")
            
            # Executa screening
            result = service.screen_multiple_tickers(tickers)
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'screening_type': 'GAMMA_FLIP_MULTI',
                **result
            }
            
            logging.info(f"API Screening concluído: {result.get('successful_analysis', 0)}/{len(tickers)}")
            return jsonify(response)
            
        except Exception as e:
            logging.error(f"Erro no screening: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @screening_bp.route('/pro/screening/flip/single', methods=['POST'])
    def screen_single_ticker():
        """
        Screening de um único ticker (versão simplificada)
        
        Body JSON:
        {
            "ticker": "PETR4"
        }
        """
        try:
            data = request.get_json()
            
            ticker = data.get('ticker', '').strip().upper()
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            logging.info(f"API Screening Single: {ticker}")
            
            result = service.analyze_single_ticker(ticker)
            
            if not result:
                return jsonify({'error': 'Falha na análise do ticker'}), 404
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'screening_type': 'GAMMA_FLIP_SINGLE',
                'result': result
            }
            
            return jsonify(response)
            
        except Exception as e:
            logging.error(f"Erro no screening single: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @screening_bp.route('/pro/screening/presets', methods=['GET'])
    def get_preset_lists():
        """Retorna listas pré-definidas de ativos para screening"""
        
        presets = {
            'ibovespa_liquidos': [
                'PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'BBAS3', 'ABEV3',
                'B3SA3', 'WEGE3', 'RENT3', 'ITSA4', 'SUZB3', 'EMBJ3'
            ],
            'alta_liquidez': [
                'BOVA11', 'PETR4', 'VALE3', 'BBAS3', 'B3SA3', 
                'ITSA4', 'BBDC4', 'MGLU3'
            ],
            'media_liquidez': [
                'ITUB4', 'ABEV3', 'WEGE3', 'RENT3', 'AXIA3', 
                'PRIO3', 'SUZB3', 'EMBJ3', 'CIEL3', 'RADL3'
            ],
            'small_caps': [
                'VIVT3', 'CSAN3', 'GGBR4', 'USIM5', 'BRAV3', 'BPAC11'
            ],
            'commodities': [
                'PETR4', 'VALE3', 'SUZB3', 'GGBR4', 'USIM5'
            ],
            'financeiro': [
                'ITUB4', 'BBDC4', 'BBAS3', 'B3SA3', 'BPAC11', 'ITSA4'
            ]
        }
        
        return jsonify({
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'presets': presets,
            'total_presets': len(presets)
        })

    @screening_bp.route('/pro/screening/health', methods=['GET'])
    def screening_health_check():
        """Health check do sistema de Screening"""
        return jsonify({
            'service': 'Gamma Flip Screening',
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0',
            'features': [
                'Multi-ticker Screening',
                'Parallel Processing',
                'Flip Distance Calculation',
                'Regime Detection',
                'Liquidity Classification',
                'Statistical Summary'
            ],
            'max_workers': service.max_workers
        })

    return screening_bp
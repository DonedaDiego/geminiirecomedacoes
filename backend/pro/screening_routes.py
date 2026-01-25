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
        """
        Screening de Gamma Flip para múltiplos ativos
        
        Body JSON:
        {
            "tickers": ["PETR4", "VALE3", "BBAS3", ...],  // opcional
            "max_workers": 5  // opcional
        }
        
        Se tickers vazio ou não fornecido = usa lista oficial completa
        """
        try:
            data = request.get_json() if request.get_json() else {}
            
            tickers = data.get('tickers', [])
            
            # Se não forneceu tickers, usa None (lista oficial)
            if not tickers:
                tickers = None
                logging.info("API Screening: Usando lista oficial completa")
            else:
                # Remove duplicatas e limpa tickers
                tickers = list(set([t.strip().upper() for t in tickers if t.strip()]))
                
                if not tickers:
                    return jsonify({'error': 'Nenhum ticker válido fornecido'}), 400
                
                logging.info(f"API Screening: {len(tickers)} tickers customizados")
            
            # Configuração opcional de workers
            max_workers = data.get('max_workers')
            if max_workers:
                service.max_workers = min(max_workers, 10)
            
            # Executa screening
            result = service.screen_multiple_tickers(tickers)
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'screening_type': 'GAMMA_FLIP_MULTI',
                **result
            }
            
            logging.info(f"API Screening concluído: {result.get('successful_analysis', 0)}")
            return jsonify(response)
            
        except Exception as e:
            logging.error(f"Erro no screening: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @screening_bp.route('/pro/screening/flip/single', methods=['POST'])
    def screen_single_ticker():
        """Screening de um único ticker"""
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
    
    @screening_bp.route('/pro/screening/refresh', methods=['POST'])
    def force_refresh_cache():
        """Força atualização completa do cache"""
        try:
            logging.info("API: Force refresh solicitado")
            
            result = service.screen_multiple_tickers(
                tickers_list=None,
                use_cache=False,
                force_refresh=True
            )
            
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'screening_type': 'FULL_REFRESH',
                **result
            }
            
            return jsonify(response)
            
        except Exception as e:
            logging.error(f"Erro no refresh: {str(e)}")
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @screening_bp.route('/pro/screening/cache/check', methods=['GET'])
    def check_cache_freshness():
        """Verifica se o cache precisa ser atualizado (1x por dia)"""
        try:
            from database import get_cache_status
            
            cache_status = get_cache_status()
            
            if not cache_status or cache_status['total_tickers'] == 0:
                return jsonify({
                    'success': True,
                    'needs_refresh': True,
                    'reason': 'Cache vazio',
                    'cache_status': cache_status
                })
            
            last_update = cache_status.get('last_update')
            if not last_update:
                return jsonify({
                    'success': True,
                    'needs_refresh': True,
                    'reason': 'Sem data de atualização',
                    'cache_status': cache_status
                })
            
            last_update_dt = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
            today = datetime.now(last_update_dt.tzinfo)
            
            is_same_day = (
                last_update_dt.year == today.year and
                last_update_dt.month == today.month and
                last_update_dt.day == today.day
            )
            
            if is_same_day:
                hours_ago = (today - last_update_dt).total_seconds() / 3600
                
                return jsonify({
                    'success': True,
                    'needs_refresh': False,
                    'reason': f'Cache atualizado hoje há {hours_ago:.1f}h',
                    'last_update': last_update,
                    'cache_status': cache_status
                })
            else:
                days_ago = (today - last_update_dt).days
                
                return jsonify({
                    'success': True,
                    'needs_refresh': True,
                    'reason': f'Cache desatualizado ({days_ago} dia(s) atrás)',
                    'last_update': last_update,
                    'cache_status': cache_status
                })
            
        except Exception as e:
            logging.error(f"Erro ao verificar freshness: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

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
                'Statistical Summary',
                'Database Cache (1x/day)'
            ],
            'max_workers': service.max_workers
        })

    return screening_bp
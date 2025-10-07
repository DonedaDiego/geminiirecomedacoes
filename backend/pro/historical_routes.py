"""
historical_routes.py - Rotas para análise histórica GEX
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
                return jsonify({'error': 'Ticker é obrigatório', 'success': False}), 400
            
            # Adicionar .SA se necessário
            if not ticker.endswith('.SA'):
                ticker = f"{ticker}.SA"
            
            logging.info(f"Buscando vencimentos históricos para {ticker}")
            
            expirations = historical_service.get_available_expirations(ticker)
            total_available = sum(1 for exp in expirations if exp['available'])
            
            return jsonify({
                'ticker': ticker.replace('.SA', ''),
                'expirations': expirations,
                'total_available': total_available,
                'success': True
            })
            
        except Exception as e:
            logging.error(f"Erro ao buscar vencimentos históricos: {e}")
            return jsonify({'error': str(e), 'success': False}), 500

    @historical_bp.route('/analyze', methods=['POST'])
    def analyze_historical():
        """Executar análise histórica completa - retorna dados separados por data"""
        try:
            data = request.get_json()
            ticker = data.get('ticker')
            vencimento = data.get('vencimento')
            days_back = data.get('days_back', 5)
            
            # Validações
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório', 'success': False}), 400
            
            if not vencimento:
                return jsonify({'error': 'Vencimento é obrigatório', 'success': False}), 400
            
            if not isinstance(days_back, int) or days_back < 2 or days_back > 5:
                return jsonify({
                    'error': 'days_back deve ser entre 2 e 5 (limite Floqui)',
                    'success': False
                }), 400
            
            # Adicionar .SA se necessário
            if not ticker.endswith('.SA'):
                ticker = f"{ticker}.SA"
            
            logging.info(f"Análise histórica: {ticker} - {vencimento} - {days_back} dias úteis")
            
            # Executar análise
            result = historical_service.analyze_historical_complete(ticker, vencimento, days_back)
            
            #  CORREÇÃO: usar 'available_dates' (não 'dates_analyzed')
            if result and result.get('available_dates') and len(result['available_dates']) > 0:
                dates_count = len(result['available_dates'])
                logging.info(f" Análise concluída: {ticker} - {dates_count} datas disponíveis")
            else:
                logging.error(f" Análise retornou vazia: {ticker}")
                return jsonify({
                    'error': 'Nenhuma data histórica encontrada',
                    'success': False
                }), 404
            
            return jsonify(result)
        
        except ValueError as e:
            logging.warning(f"Erro de validação: {e}")
            return jsonify({'error': str(e), 'success': False}), 400
        
        except Exception as e:
            logging.error(f"Erro na análise histórica: {e}", exc_info=True)
            return jsonify({
                'error': 'Erro interno na análise histórica',
                'details': str(e),
                'success': False
            }), 500

    @historical_bp.route('/analyze/<date>', methods=['POST'])
    def get_specific_date(date):
        """Obter dados de uma data específica (otimização para frontend)"""
        try:
            data = request.get_json()
            ticker = data.get('ticker')
            vencimento = data.get('vencimento')
            
            if not ticker or not vencimento:
                return jsonify({
                    'error': 'Ticker e vencimento são obrigatórios',
                    'success': False
                }), 400
            
            if not ticker.endswith('.SA'):
                ticker = f"{ticker}.SA"
            
            # Buscar dados completos (você pode otimizar cacheando isso)
            result = historical_service.analyze_historical_complete(ticker, vencimento, 5)
            
            # Retornar apenas a data solicitada
            if date in result['data_by_date']:
                return jsonify({
                    'ticker': ticker.replace('.SA', ''),
                    'vencimento': vencimento,
                    'date': date,
                    'data': result['data_by_date'][date],
                    'success': True
                })
            else:
                return jsonify({
                    'error': f'Data {date} não disponível',
                    'available_dates': result['available_dates'],
                    'success': False
                }), 404
        
        except Exception as e:
            logging.error(f"Erro ao buscar data específica: {e}")
            return jsonify({'error': str(e), 'success': False}), 500

    @historical_bp.route('/dates', methods=['POST'])
    def get_available_dates():
        """Obter apenas lista de datas disponíveis (leve)"""
        try:
            data = request.get_json()
            ticker = data.get('ticker')
            vencimento = data.get('vencimento')
            days_back = data.get('days_back', 5)
            
            if not ticker or not vencimento:
                return jsonify({
                    'error': 'Ticker e vencimento são obrigatórios',
                    'success': False
                }), 400
            
            if not ticker.endswith('.SA'):
                ticker = f"{ticker}.SA"
            
            # Obter apenas datas (sem calcular gráficos)
            from datetime import datetime, timedelta
            
            business_dates = historical_service.analyzer.data_provider.get_business_days(days_back)
            available_dates = []
            
            for date_obj in business_dates:
                oi_data = historical_service.analyzer.data_provider.get_floqui_historical(
                    ticker, vencimento, date_obj
                )
                if oi_data:
                    available_dates.append({
                        'date': date_obj.strftime('%Y-%m-%d'),
                        'display': date_obj.strftime('%d/%m/%Y'),
                        'weekday': date_obj.strftime('%A'),
                        'strikes_count': len(oi_data)
                    })
            
            return jsonify({
                'ticker': ticker.replace('.SA', ''),
                'vencimento': vencimento,
                'available_dates': available_dates,
                'total': len(available_dates),
                'success': True
            })
            
        except Exception as e:
            logging.error(f"Erro ao buscar datas: {e}")
            return jsonify({'error': str(e), 'success': False}), 500

    @historical_bp.route('/health', methods=['GET'])
    def health_check():
        """Health check do serviço histórico"""
        return jsonify({
            'service': 'historical',
            'status': 'active',
            'version': '3.0',
            'features': [
                'Dados históricos Floqui (até 5 dias úteis)',
                'Gregas reais Oplab',
                '6 gráficos por data',
                'Gamma flip histórico',
                'Walls dinâmicos'
            ],
            'message': 'Serviço de análise histórica GEX com dados reais separados por data'
        })
    
    @historical_bp.route('/test', methods=['POST'])
    def test_data_availability():
        """Testa disponibilidade de dados para um ticker/vencimento"""
        try:
            data = request.get_json()
            ticker = data.get('ticker')
            vencimento = data.get('vencimento')
            
            if not ticker or not vencimento:
                return jsonify({
                    'error': 'Ticker e vencimento são obrigatórios',
                    'success': False
                }), 400
            
            if not ticker.endswith('.SA'):
                ticker = f"{ticker}.SA"
            
            # Testar últimos 3 dias
            from datetime import datetime, timedelta
            
            test_results = []
            for i in range(1, 4):
                test_date = datetime.now() - timedelta(days=i)
                if test_date.weekday() < 5:  # Apenas dias úteis
                    oi_data = historical_service.analyzer.data_provider.get_floqui_historical(
                        ticker, vencimento, test_date
                    )
                    test_results.append({
                        'date': test_date.strftime('%Y-%m-%d'),
                        'strikes': len(oi_data),
                        'available': len(oi_data) > 0
                    })
            
            oplab_data = historical_service.analyzer.data_provider.get_oplab_historical_data(ticker)
            
            return jsonify({
                'ticker': ticker.replace('.SA', ''),
                'vencimento': vencimento,
                'oplab_options': len(oplab_data),
                'oplab_available': len(oplab_data) > 0,
                'floqui_tests': test_results,
                'floqui_available': any(t['available'] for t in test_results),
                'overall_available': len(oplab_data) > 0 and any(t['available'] for t in test_results),
                'success': True
            })
            
        except Exception as e:
            logging.error(f"Erro no teste de dados: {e}")
            return jsonify({'error': str(e), 'success': False}), 500

    return historical_bp


def get_historical_blueprint():
    """Função helper para obter o blueprint"""
    return create_historical_blueprint()
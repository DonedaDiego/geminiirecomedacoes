"""
historical_routes.py - Rotas para análise histórica GEX
"""

from flask import Blueprint, request, jsonify
from .historical_service import HistoricalService
import logging
from datetime import datetime

def create_historical_blueprint():

    historical_bp      = Blueprint('historical', __name__, url_prefix='/pro/historical')
    historical_service = HistoricalService()

    # ── Vencimentos disponíveis ───────────────────────────────────────────────
    @historical_bp.route('/expirations', methods=['POST'])
    def get_historical_expirations():
        try:
            data   = request.get_json()
            ticker = data.get('ticker')
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório', 'success': False}), 400

            if not ticker.endswith('.SA'):
                ticker = f"{ticker}.SA"

            logging.info(f"Buscando vencimentos históricos para {ticker}")

            expirations     = historical_service.get_available_expirations(ticker)
            total_available = sum(1 for e in expirations if e['available'])

            return jsonify({
                'ticker':          ticker.replace('.SA', ''),
                'expirations':     expirations,
                'total_available': total_available,
                'success':         True
            })

        except Exception as e:
            logging.error(f"Erro ao buscar vencimentos históricos: {e}")
            return jsonify({'error': str(e), 'success': False}), 500

    # ── Análise histórica completa ────────────────────────────────────────────
    @historical_bp.route('/analyze', methods=['POST'])
    def analyze_historical():
        try:
            data       = request.get_json()
            ticker     = data.get('ticker')
            vencimento = data.get('vencimento')
            days_back  = data.get('days_back', 5)

            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório', 'success': False}), 400
            if not vencimento:
                return jsonify({'error': 'Vencimento é obrigatório', 'success': False}), 400

            # Aceita de 2 até 15 sessões (o HTML oferece 5/7/10/15)
            if not isinstance(days_back, int) or days_back < 2 or days_back > 15:
                return jsonify({
                    'error': 'days_back deve ser entre 2 e 15',
                    'success': False
                }), 400

            if not ticker.endswith('.SA'):
                ticker = f"{ticker}.SA"

            logging.info(f"Análise histórica: {ticker} - {vencimento} - {days_back} dias úteis")

            result = historical_service.analyze_historical_complete(ticker, vencimento, days_back)

            logging.info(f"Resultado: success={result.get('success')} | datas={result.get('available_dates')}")

            if not result or not result.get('success'):
                return jsonify({'error': 'Análise não foi bem sucedida', 'success': False}), 500

            available_dates = result.get('available_dates', [])
            if not available_dates:
                return jsonify({
                    'error': 'Nenhuma data histórica encontrada',
                    'success': False
                }), 404

            logging.info(f"Análise concluída: {ticker} - {len(available_dates)} datas")
            return jsonify(result)

        except ValueError as e:
            logging.warning(f"Erro de validação: {e}")
            return jsonify({'error': str(e), 'success': False}), 400

        except Exception as e:
            import traceback
            logging.error(f"Erro na análise histórica: {e}\n{traceback.format_exc()}")
            return jsonify({
                'error':   'Erro interno na análise histórica',
                'details': str(e),
                'success': False
            }), 500

    # ── Data específica ───────────────────────────────────────────────────────
    @historical_bp.route('/analyze/<date>', methods=['POST'])
    def get_specific_date(date):
        try:
            data       = request.get_json()
            ticker     = data.get('ticker')
            vencimento = data.get('vencimento')

            if not ticker or not vencimento:
                return jsonify({'error': 'Ticker e vencimento são obrigatórios', 'success': False}), 400

            try:
                datetime.strptime(date, '%Y-%m-%d')
            except ValueError:
                return jsonify({'error': 'Formato de data inválido. Use YYYY-MM-DD', 'success': False}), 400

            if not ticker.endswith('.SA'):
                ticker = f"{ticker}.SA"

            result = historical_service.analyze_historical_complete(ticker, vencimento, 5)

            if date in result['data_by_date']:
                return jsonify({
                    'ticker':     ticker.replace('.SA', ''),
                    'vencimento': vencimento,
                    'date':       date,
                    'data':       result['data_by_date'][date],
                    'success':    True
                })
            else:
                return jsonify({
                    'error':           f'Data {date} não disponível',
                    'available_dates': result['available_dates'],
                    'success':         False
                }), 404

        except Exception as e:
            logging.error(f"Erro ao buscar data específica: {e}")
            return jsonify({'error': str(e), 'success': False}), 500

    # ── Insights isolados ─────────────────────────────────────────────────────
    @historical_bp.route('/insights', methods=['POST'])
    def get_insights():
        try:
            data       = request.get_json()
            ticker     = data.get('ticker')
            vencimento = data.get('vencimento')
            days_back  = data.get('days_back', 5)

            if not ticker or not vencimento:
                return jsonify({'error': 'Ticker e vencimento são obrigatórios', 'success': False}), 400

            if not ticker.endswith('.SA'):
                ticker = f"{ticker}.SA"

            result = historical_service.analyze_historical_complete(ticker, vencimento, days_back)

            return jsonify({
                'ticker':          ticker.replace('.SA', ''),
                'vencimento':      vencimento,
                'expiration_desc': result['expiration_desc'],
                'spot_price':      result['spot_price'],
                'available_dates': result['available_dates'],
                'insights':        result['insights'],
                'success':         True
            })

        except Exception as e:
            logging.error(f"Erro ao buscar insights: {e}")
            return jsonify({'error': str(e), 'success': False}), 500

    # ── Datas disponíveis (leve) ──────────────────────────────────────────────
    @historical_bp.route('/dates', methods=['POST'])
    def get_available_dates():
        try:
            data       = request.get_json()
            ticker     = data.get('ticker')
            vencimento = data.get('vencimento')
            days_back  = data.get('days_back', 5)

            if not ticker or not vencimento:
                return jsonify({'error': 'Ticker e vencimento são obrigatórios', 'success': False}), 400

            if not ticker.endswith('.SA'):
                ticker = f"{ticker}.SA"

            business_dates  = historical_service.analyzer.data_provider.get_business_days(days_back)
            available_dates = []

            for date_obj in business_dates:
                oi_data = historical_service.analyzer.data_provider.get_floqui_historical(
                    ticker, vencimento, date_obj
                )
                if oi_data:
                    available_dates.append({
                        'date':          date_obj.strftime('%Y-%m-%d'),
                        'display':       date_obj.strftime('%d/%m/%Y'),
                        'weekday':       date_obj.strftime('%A'),
                        'strikes_count': len(oi_data)
                    })

            return jsonify({
                'ticker':          ticker.replace('.SA', ''),
                'vencimento':      vencimento,
                'available_dates': available_dates,
                'total':           len(available_dates),
                'success':         True
            })

        except Exception as e:
            logging.error(f"Erro ao buscar datas: {e}")
            return jsonify({'error': str(e), 'success': False}), 500

    # ── Health check ──────────────────────────────────────────────────────────
    @historical_bp.route('/health', methods=['GET'])
    def health_check():
        return jsonify({
            'service': 'historical',
            'status':  'active',
            'version': '3.2',
            'features': [
                'Dados históricos banco PostgreSQL (até 15 sessões)',
                'Gregas reais Oplab',
                'Gamma flip histórico',
                'Insights gerenciais',
                'Strikes mais impactados',
            ],
            'message': 'Serviço de análise histórica GEX com dados reais separados por data'
        })

    # ── Teste de disponibilidade ──────────────────────────────────────────────
    @historical_bp.route('/test', methods=['POST'])
    def test_data_availability():
        try:
            data       = request.get_json()
            ticker     = data.get('ticker')
            vencimento = data.get('vencimento')

            if not ticker or not vencimento:
                return jsonify({'error': 'Ticker e vencimento são obrigatórios', 'success': False}), 400

            if not ticker.endswith('.SA'):
                ticker = f"{ticker}.SA"

            from datetime import timedelta
            test_results = []
            for i in range(1, 4):
                test_date = datetime.now() - timedelta(days=i)
                if test_date.weekday() < 5:
                    oi_data = historical_service.analyzer.data_provider.get_floqui_historical(
                        ticker, vencimento, test_date
                    )
                    test_results.append({
                        'date':      test_date.strftime('%Y-%m-%d'),
                        'strikes':   len(oi_data),
                        'available': len(oi_data) > 0
                    })

            oplab_data = historical_service.analyzer.data_provider.get_oplab_historical_data(ticker)

            return jsonify({
                'ticker':            ticker.replace('.SA', ''),
                'vencimento':        vencimento,
                'oplab_options':     len(oplab_data),
                'oplab_available':   len(oplab_data) > 0,
                'floqui_tests':      test_results,
                'floqui_available':  any(t['available'] for t in test_results),
                'overall_available': len(oplab_data) > 0 and any(t['available'] for t in test_results),
                'success':           True
            })

        except Exception as e:
            logging.error(f"Erro no teste de dados: {e}")
            return jsonify({'error': str(e), 'success': False}), 500

    return historical_bp


def get_historical_blueprint():
    return create_historical_blueprint()
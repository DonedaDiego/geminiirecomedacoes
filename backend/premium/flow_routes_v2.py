
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import logging
import traceback

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db_connection

# IMPORTS CORRIGIDOS
from premium.flow_service_v2 import flow_service, convert_to_json_serializable
from database import get_db_connection  # Usar sua função de conexão

def get_flow_v2_blueprint():
    """Factory function para criar o blueprint do flow V2"""
    
    flow_v2_bp = Blueprint('flow_v2', __name__)
    
    # Função helper para executar queries
    def execute_flow_query(query, params=None, fetch=False):
        """Executar query usando a conexão padrão do sistema"""
        conn = None
        try:
            conn = get_db_connection()
            if not conn:
                raise Exception("Não foi possível conectar ao banco")
                
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            if fetch:
                result = cursor.fetchall()
                # Converter para lista de dicionários se necessário
                if result:
                    columns = [desc[0] for desc in cursor.description]
                    result = [dict(zip(columns, row)) for row in result]
                conn.commit()
                return result
            else:
                conn.commit()
                return cursor.rowcount
                
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()

    @flow_v2_bp.route('/flow/v2/capture', methods=['POST'])
    def capture_current_flow():
        """Captura flow atual de um ticker em tempo real"""
        try:
            data = request.get_json()
            
            # Validação de parâmetros
            ticker = data.get('ticker', '').strip().upper()
            if not ticker:
                return jsonify({'error': 'Ticker é obrigatório'}), 400
            
            logging.info(f"API: Captura de flow V2 solicitada para {ticker}")
            
            # Capturar flow atual
            result = flow_service.capture_current_flow(ticker)
            
            # Preparar resposta
            response = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                **convert_to_json_serializable(result)
            }
            
            logging.info(f"API: Flow V2 capturado com sucesso para {ticker}")
            return jsonify(response)
            
        except ValueError as e:
            logging.error(f"Erro de validação: {str(e)}")
            return jsonify({'error': str(e)}), 404
            
        except Exception as e:
            logging.error(f"Erro na captura de flow V2: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @flow_v2_bp.route('/flow/v2/current/<ticker>', methods=['GET'])
    def get_current_flow(ticker):
        """Busca o último snapshot de flow armazenado para um ticker"""
        try:
            ticker_clean = ticker.strip().upper().replace('.SA', '')
            
            logging.info(f"API: Busca de flow atual para {ticker_clean}")
            
            # Query corrigida para buscar último snapshot
            query = """
            SELECT fs.*, 
                   (SELECT COUNT(*) FROM option_details WHERE snapshot_id = fs.id) as total_options_detailed
            FROM flow_snapshots fs
            WHERE fs.ticker = %s
            ORDER BY fs.timestamp DESC
            LIMIT 1;
            """
            
            result = execute_flow_query(query, (ticker_clean,), fetch=True)
            
            if not result:
                return jsonify({'error': f'Nenhum flow encontrado para {ticker_clean}'}), 404
            
            snapshot = result[0]
            
            # Buscar detalhes das opções se solicitado
            include_details = request.args.get('include_details', 'false').lower() == 'true'
            
            option_details = []
            if include_details:
                details_query = """
                SELECT * FROM option_details 
                WHERE snapshot_id = %s 
                ORDER BY category, strike;
                """
                option_details = execute_flow_query(
                    details_query, (snapshot.get('id'),), fetch=True
                )
            
            response = {
                'success': True,
                'ticker': ticker_clean,
                'flow_data': convert_to_json_serializable(snapshot),
                'option_details': convert_to_json_serializable(option_details),
                'total_details': len(option_details),
                'timestamp': datetime.now().isoformat()
            }
            
            return jsonify(response)
            
        except Exception as e:
            logging.error(f"Erro ao buscar flow atual: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @flow_v2_bp.route('/flow/v2/history/<ticker>', methods=['GET'])
    def get_flow_history(ticker):
        """Busca histórico de flow armazenado no banco"""
        try:
            ticker_clean = ticker.strip().upper().replace('.SA', '')
            
            # Parâmetros de busca
            days_back = min(int(request.args.get('days_back', 30)), 365)
            limit = min(int(request.args.get('limit', 50)), 200)
            
            logging.info(f"API: Histórico de flow para {ticker_clean} - {days_back} dias")
            
            # Query para histórico
            query = """
            SELECT * FROM flow_snapshots 
            WHERE ticker = %s 
              AND date >= %s
            ORDER BY date DESC, timestamp DESC
            LIMIT %s;
            """
            
            start_date = (datetime.now() - timedelta(days=days_back)).date()
            
            result = execute_flow_query(query, (ticker_clean, start_date, limit), fetch=True)
            
            if not result:
                return jsonify({
                    'success': True,
                    'ticker': ticker_clean,
                    'history': [],
                    'count': 0,
                    'message': f'Nenhum histórico encontrado para {ticker_clean}'
                })
            
            response = {
                'success': True,
                'ticker': ticker_clean,
                'history': convert_to_json_serializable(result),
                'count': len(result),
                'period': {
                    'days_back': days_back,
                    'start_date': start_date.isoformat(),
                    'end_date': datetime.now().date().isoformat()
                },
                'timestamp': datetime.now().isoformat()
            }
            
            return jsonify(response)
            
        except Exception as e:
            logging.error(f"Erro ao buscar histórico de flow: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @flow_v2_bp.route('/flow/v2/analyze/<ticker>', methods=['GET'])
    def analyze_flow_detailed(ticker):
        """Análise detalhada do flow com métricas avançadas"""
        try:
            ticker_clean = ticker.strip().upper().replace('.SA', '')
            
            logging.info(f"API: Análise detalhada de flow para {ticker_clean}")
            
            # Buscar último snapshot
            current_query = """
            SELECT * FROM flow_snapshots 
            WHERE ticker = %s 
            ORDER BY timestamp DESC 
            LIMIT 1;
            """
            
            current_result = execute_flow_query(current_query, (ticker_clean,), fetch=True)
            
            if not current_result:
                return jsonify({'error': f'Nenhum flow encontrado para {ticker_clean}'}), 404
            
            current_flow = current_result[0]
            
            # Buscar histórico para comparação (últimos 7 dias)
            history_query = """
            SELECT * FROM flow_snapshots 
            WHERE ticker = %s 
              AND date >= %s
              AND date < %s
            ORDER BY date DESC;
            """
            
            week_ago = (datetime.now() - timedelta(days=7)).date()
            today = datetime.now().date()
            
            history = execute_flow_query(history_query, (ticker_clean, week_ago, today), fetch=True)
            
            # Calcular métricas comparativas
            analysis = {
                'current': current_flow,
                'trends': {},
                'comparisons': {},
                'alerts': []
            }
            
            if len(history) >= 2:
                # Tendência de Call/Put Ratio
                recent_ratios = [h['call_put_ratio'] for h in history[:3] if h['call_put_ratio']]
                if recent_ratios:
                    avg_ratio = sum(recent_ratios) / len(recent_ratios)
                    current_ratio = float(current_flow['call_put_ratio'])
                    
                    analysis['trends']['cp_ratio_trend'] = 'INCREASING' if current_ratio > avg_ratio else 'DECREASING'
                    analysis['trends']['cp_ratio_change'] = ((current_ratio / avg_ratio) - 1) * 100
                
                # Volume trends
                recent_volumes = [h['total_volume'] for h in history[:3] if h['total_volume']]
                if recent_volumes:
                    avg_volume = sum(recent_volumes) / len(recent_volumes)
                    current_volume = int(current_flow['total_volume'])
                    
                    analysis['trends']['volume_trend'] = 'INCREASING' if current_volume > avg_volume else 'DECREASING'
                    analysis['trends']['volume_change'] = ((current_volume / avg_volume) - 1) * 100
            
            # Alertas baseados em thresholds
            cp_ratio = float(current_flow['call_put_ratio']) if current_flow['call_put_ratio'] else 0
            if cp_ratio > 3:
                analysis['alerts'].append("CALL FLOW EXTREMO - Possível evento especial")
            elif cp_ratio < 0.33:
                analysis['alerts'].append("PUT FLOW EXTREMO - Proteção massiva detectada")
            
            if float(current_flow['avg_iv'] or 0) > 0.5:
                analysis['alerts'].append("VOLATILIDADE IMPLÍCITA ALTA - Movimento esperado")
            
            # Buscar detalhes das opções mais relevantes
            top_options_query = """
            SELECT * FROM option_details 
            WHERE snapshot_id = %s 
            ORDER BY weight DESC 
            LIMIT 10;
            """
            
            top_options = execute_flow_query(top_options_query, (current_flow['id'],), fetch=True)
            
            response = {
                'success': True,
                'ticker': ticker_clean,
                'analysis': convert_to_json_serializable(analysis),
                'top_options': convert_to_json_serializable(top_options),
                'history_depth': len(history),
                'timestamp': datetime.now().isoformat()
            }
            
            return jsonify(response)
            
        except Exception as e:
            logging.error(f"Erro na análise detalhada: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @flow_v2_bp.route('/flow/v2/stats', methods=['GET'])
    def get_flow_stats():
        """Estatísticas gerais do sistema de flow"""
        try:
            logging.info("API: Estatísticas do sistema de flow solicitadas")
            
            # Estatísticas básicas
            stats_query = """
            SELECT 
                COUNT(DISTINCT ticker) as unique_tickers,
                COUNT(*) as total_snapshots,
                MAX(timestamp) as last_capture,
                MIN(date) as first_data,
                AVG(total_volume) as avg_volume,
                AVG(total_options) as avg_options_per_snapshot
            FROM flow_snapshots;
            """
            
            stats_result = execute_flow_query(stats_query, fetch=True)
            stats = stats_result[0] if stats_result else {}
            
            # Top tickers por atividade
            top_tickers_query = """
            SELECT 
                ticker,
                COUNT(*) as snapshots,
                AVG(total_volume) as avg_volume,
                MAX(timestamp) as last_update
            FROM flow_snapshots 
            GROUP BY ticker 
            ORDER BY snapshots DESC, avg_volume DESC 
            LIMIT 10;
            """
            
            top_tickers = execute_flow_query(top_tickers_query, fetch=True)
            
            response = {
                'success': True,
                'stats': convert_to_json_serializable(stats),
                'top_tickers': convert_to_json_serializable(top_tickers),
                'system_status': 'operational',
                'timestamp': datetime.now().isoformat()
            }
            
            return jsonify(response)
            
        except Exception as e:
            logging.error(f"Erro ao buscar estatísticas: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    @flow_v2_bp.route('/flow/v2/health', methods=['GET'])
    def health_check():
        """Health check do sistema Flow V2"""
        try:
            # Testar conexão com banco usando sua função
            db_status = 'healthy'
            try:
                test_result = execute_flow_query("SELECT 1 as test;", fetch=True)
                if not test_result:
                    db_status = 'error'
            except:
                db_status = 'error'
            
            # Testar API OpLab
            api_status = 'healthy'
            try:
                test_options = flow_service.get_current_options('PETR4')
                if not test_options:
                    api_status = 'limited'
            except:
                api_status = 'error'
            
            # Status geral
            overall_status = 'healthy' if db_status == 'healthy' and api_status == 'healthy' else 'degraded'
            
            response = {
                'service': 'Flow Tracker V2',
                'status': overall_status,
                'version': '2.0.0',
                'timestamp': datetime.now().isoformat(),
                'components': {
                    'database': db_status,
                    'oplab_api': api_status,
                    'black_scholes': 'healthy'
                }
            }
            
            return jsonify(response)
            
        except Exception as e:
            logging.error(f"Erro no health check: {str(e)}")
            return jsonify({
                'service': 'Flow Tracker V2',
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }), 500

    # Simplificar algumas rotas que tinham complexidade desnecessária
    @flow_v2_bp.route('/flow/v2/batch-capture', methods=['POST'])
    def batch_capture_flow():
        """Captura flow de múltiplos tickers"""
        try:
            data = request.get_json()
            tickers = data.get('tickers', [])[:5]  # Limitar a 5 para não sobrecarregar
            
            results = []
            errors = []
            
            for ticker in tickers:
                try:
                    result = flow_service.capture_current_flow(ticker)
                    results.append(result)
                except Exception as e:
                    errors.append({'ticker': ticker, 'error': str(e)})
            
            return jsonify({
                'success': True,
                'results': convert_to_json_serializable(results),
                'errors': errors,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            return jsonify({'error': f'Erro interno: {str(e)}'}), 500

    return flow_v2_bp
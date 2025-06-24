from flask import Blueprint, render_template, request, jsonify, current_app
from swing_trade_ml_service import SwingTradeMachineLearningService
import jwt
import json

# Criar blueprint
swing_trade_ml_bp = Blueprint('swing_trade_ml', __name__, url_prefix='/api/swing-trade-ml')
swing_service = SwingTradeMachineLearningService()

def verify_user_access(auth_header):
    """Verificar se usuário tem acesso via JWT token"""
    try:
        if not auth_header or not auth_header.startswith('Bearer '):
            return False
        
        token = auth_header.replace('Bearer ', '')
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload['user_id']
        
        return user_id
        
    except Exception as e:
        print(f"Erro na verificação do token: {e}")
        return False

@swing_trade_ml_bp.route('/analysis', methods=['POST'])
def run_swing_trade_analysis():
    """Endpoint principal para executar análise de swing trade"""
    try:
        print("=== NOVA REQUISIÇÃO DE ANÁLISE ===")
        
        # Verificar autenticação
        auth_header = request.headers.get('Authorization')
        current_user_id = verify_user_access(auth_header)
        
        if not current_user_id:
            print("Erro: Usuário não autenticado")
            return jsonify({
                'success': False,
                'error': 'Usuário não autenticado'
            }), 401
        
        print(f"Usuário autenticado: {current_user_id}")

        # Obter dados da requisição
        data = request.get_json()
        
        if not data:
            print("Erro: Dados não fornecidos")
            return jsonify({
                'success': False,
                'error': 'Dados não fornecidos'
            }), 400

        ticker = data.get('ticker', '').strip().upper()
        prediction_days = data.get('prediction_days', 5)

        print(f"Parâmetros recebidos - Ticker: {ticker}, Dias: {prediction_days}")

        # Validações
        if not ticker:
            return jsonify({
                'success': False,
                'error': 'Código da ação é obrigatório'
            }), 400

        try:
            prediction_days = int(prediction_days)
            if prediction_days < 1 or prediction_days > 30:
                return jsonify({
                    'success': False,
                    'error': 'Número de dias deve estar entre 1 e 30'
                }), 400
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Número de dias deve ser um valor numérico válido'
            }), 400

        # Executar análise
        print("Iniciando análise...")
        result = swing_service.run_analysis(ticker, prediction_days)
        
        if result['success']:
            print("Análise concluída com sucesso!")
            
            # Preparar dados para Chart.js
            df = result.get('dataframe')
            chart_data = None
            
            if df is not None:
                try:
                    # Pegar últimos 252 pontos para o gráfico (1 ano de pregões)
                    last_252 = df.tail(252)
                    
                    chart_data = {
                        'labels': last_252.index.strftime('%d/%m').tolist(),
                        'prices': last_252['Close'].round(2).tolist(),
                        'predictions': last_252['prediction'].tolist() if 'prediction' in last_252.columns else [],
                        'stop_loss': last_252['Stop_Loss'].round(2).tolist() if 'Stop_Loss' in last_252.columns else [],
                        'take_profit': last_252['Take_Profit'].round(2).tolist() if 'Take_Profit' in last_252.columns else [],
                        'colors': last_252['color'].tolist() if 'color' in last_252.columns else []
                    }
                    print(f"Dados do gráfico preparados: {len(chart_data['labels'])} pontos (252 dias)")
                except Exception as e:
                    print(f"Erro ao preparar dados do gráfico: {e}")
                    chart_data = None
            
            return jsonify({
                'success': True,
                'chart_html': result['chart_html'],    # Plotly (backup)
                'chart_data': chart_data,              # Chart.js (principal)
                'analysis_data': result['analysis_data']
            })
        else:
            print(f"Erro na análise: {result['error']}")
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500

    except Exception as e:
        print(f"Erro interno: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'error': f'Erro interno do servidor: {str(e)}'
        }), 500

@swing_trade_ml_bp.route('/health')
def swing_trade_health():
    """Endpoint de health check"""
    try:
        return jsonify({
            'success': True,
            'service': 'Swing Trade Machine Learning',
            'status': 'operational',
            'version': '1.0.0'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@swing_trade_ml_bp.route('/tickers')
def get_available_tickers():
    """Lista de tickers sugeridos"""
    try:
        suggested_tickers = [
            {'symbol': 'PETR4', 'name': 'Petrobras PN'},
            {'symbol': 'VALE3', 'name': 'Vale ON'},
            {'symbol': 'ITUB4', 'name': 'Itaú Unibanco PN'},
            {'symbol': 'BBDC4', 'name': 'Bradesco PN'},
            {'symbol': 'ABEV3', 'name': 'Ambev ON'},
            {'symbol': 'WEGE3', 'name': 'WEG ON'},
            {'symbol': 'MGLU3', 'name': 'Magazine Luiza ON'},
            {'symbol': 'HAPV3', 'name': 'Hapvida ON'},
            {'symbol': 'RENT3', 'name': 'Localiza ON'},
            {'symbol': 'LREN3', 'name': 'Lojas Renner ON'},
            {'symbol': 'SUZB3', 'name': 'Suzano ON'},
            {'symbol': 'JBSS3', 'name': 'JBS ON'},
            {'symbol': 'UGPA3', 'name': 'Ultrapar ON'},
            {'symbol': 'CIEL3', 'name': 'Cielo ON'},
            {'symbol': 'GGBR4', 'name': 'Gerdau PN'},
            {'symbol': 'BBAS3', 'name': 'Banco do Brasil ON'},
            {'symbol': 'SANB11', 'name': 'Santander BR Units'},
            {'symbol': 'VIVT3', 'name': 'Vivo ON'},
            {'symbol': 'EMBR3', 'name': 'Embraer ON'},
            {'symbol': 'RADL3', 'name': 'Raia Drogasil ON'}
        ]
        
        return jsonify({
            'success': True,
            'tickers': suggested_tickers
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Função para exportar o blueprint
def get_swing_trade_ml_blueprint():
    """Retorna o blueprint para registrar no Flask"""
    return swing_trade_ml_bp
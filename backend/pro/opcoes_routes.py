from flask import Blueprint, request, jsonify
from functools import wraps
import jwt
import os
from database import get_db_connection
from pro.opcoes_service import OpcoesService
from config import JWT_SECRET, JWT_KEYS_TO_TRY  # Importar lista de chaves

opcoes_bp = Blueprint('opcoes', __name__)

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'success': False, 'message': 'Token é obrigatório'}), 401
        
        try:
            token = token.split(' ')[1]  # Remove 'Bearer '
            
            # Tentar decodificar com diferentes chaves
            decoded_data = None
            successful_key = None
            
            for key in JWT_KEYS_TO_TRY:
                try:
                    decoded_data = jwt.decode(token, key, algorithms=['HS256'])
                    successful_key = key
                    break
                except jwt.InvalidTokenError:
                    continue
            
            if not decoded_data:
                print(f" Token não pôde ser decodificado com nenhuma das chaves: {JWT_KEYS_TO_TRY}")
                return jsonify({'success': False, 'message': 'Token inválido'}), 401
            
            print(f" Token decodificado com sucesso usando chave: {successful_key}")
            current_user_id = decoded_data['user_id']
            
        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'message': 'Token expirado'}), 401
        except Exception as e:
            print(f" Erro geral na autenticação: {e}")
            return jsonify({'success': False, 'message': 'Erro de autenticação'}), 401
        
        return f(current_user_id, *args, **kwargs)
    return decorated

@opcoes_bp.route('/api/opcoes/hunter-walls', methods=['POST'])
@token_required
def hunter_walls_analysis(current_user_id):
    """Análise Hunter Walls para múltiplos vencimentos - CORRIGIDO"""
    try:
        data = request.get_json()
        ticker = data.get('ticker', '').upper()
        grupos_vencimentos = data.get('grupos_vencimentos', [])
        
        if not ticker:
            return jsonify({'success': False, 'message': 'Ticker é obrigatório'}), 400
        
        if not grupos_vencimentos:
            return jsonify({'success': False, 'message': 'Grupos de vencimentos são obrigatórios'}), 400
        
        print(f" Hunter Walls - Usuário: {current_user_id}, Ticker: {ticker}")
        
        #  VERIFICAR PLANO DO USUÁRIO - CORRIGIDO
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Erro de conexão com banco'}), 500
            
        cursor = conn.cursor()
        cursor.execute("""
            SELECT plan_id, user_type, plan_name FROM users 
            WHERE id = %s
        """, (current_user_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user:
            return jsonify({
                'success': False, 
                'message': 'Usuário não encontrado'
            }), 404
        
        plan_id, user_type, plan_name = user
        
        print(f"👤 Usuário verificado - Plan ID: {plan_id}, User Type: {user_type}, Plan Name: {plan_name}")
        
        #  LÓGICA DE ACESSO CORRIGIDA
        allowed_plans = [3, 4]  # Free (3) e Community (4)
        allowed_user_types = ['trial', 'paid', 'free', 'admin', 'master']
        
        has_valid_plan = plan_id in allowed_plans
        has_valid_user_type = user_type in allowed_user_types
        is_admin = user_type in ['admin', 'master']
        
        print(f"🔍 Verificação de acesso:")
        print(f"   - Plan válido: {has_valid_plan} (plan_id {plan_id} in {allowed_plans})")
        print(f"   - User type válido: {has_valid_user_type} (user_type '{user_type}' in {allowed_user_types})")
        print(f"   - É admin: {is_admin}")
        
        #  PERMITIR ACESSO SE QUALQUER CONDIÇÃO FOR VERDADEIRA
        if not (has_valid_plan or has_valid_user_type or is_admin):
            print(f" ACESSO NEGADO - Plan ID: {plan_id}, User Type: {user_type}")
            return jsonify({
                'success': False, 
                'message': 'Recurso disponível apenas para planos Community ou superior',
                'upgrade_required': True,
                'debug_info': {
                    'current_plan_id': plan_id,
                    'current_user_type': user_type,
                    'allowed_plans': allowed_plans,
                    'allowed_user_types': allowed_user_types
                }
            }), 403
        
        print(f" ACESSO LIBERADO para usuário {current_user_id}")
        
        #  EXECUTAR ANÁLISE
        try:
            opcoes_service = OpcoesService()
            print(f" Iniciando análise Hunter Walls...")
            
            resultado = opcoes_service.hunter_walls_analysis(ticker, grupos_vencimentos)
            
            if not resultado:
                print(f" Análise retornou vazio para {ticker}")
                return jsonify({
                    'success': False, 
                    'message': f'Não foi possível obter dados para {ticker}. Verifique se o ticker está correto e tem opções disponíveis.'
                }), 404
            
            print(f" Análise concluída com sucesso para {ticker}")
            
            return jsonify({
                'success': True,
                'data': resultado,
                'user_info': {
                    'plan_id': plan_id,
                    'user_type': user_type,
                    'plan_name': plan_name
                }
            })
            
        except Exception as analysis_error:
            print(f" Erro na análise do OpcoesService: {analysis_error}")
            return jsonify({
                'success': False, 
                'message': f'Erro ao processar análise: {str(analysis_error)}'
            }), 500
        
    except Exception as e:
        print(f" Erro geral em hunter_walls_analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'message': 'Erro interno do servidor',
            'debug_error': str(e)
        }), 500


# ===== ADICIONAR APÓS A ROTA hunter-walls =====

@opcoes_bp.route('/api/opcoes/volume-historico', methods=['POST'])
@token_required
def volume_historico_analysis(current_user_id):
    """ NOVA ROTA - Análise de volume histórico vs atual"""
    try:
        data = request.get_json()
        ticker = data.get('ticker', '').upper()
        
        if not ticker:
            return jsonify({'success': False, 'message': 'Ticker é obrigatório'}), 400
        
        print(f" Volume Histórico - Usuário: {current_user_id}, Ticker: {ticker}")
        
        #  MESMA VERIFICAÇÃO DE ACESSO DO HUNTER WALLS
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Erro de conexão com banco'}), 500
            
        cursor = conn.cursor()
        cursor.execute("""
            SELECT plan_id, user_type, plan_name FROM users 
            WHERE id = %s
        """, (current_user_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user:
            return jsonify({
                'success': False, 
                'message': 'Usuário não encontrado'
            }), 404
        
        plan_id, user_type, plan_name = user
        
        #  LÓGICA DE ACESSO IGUAL AO HUNTER WALLS
        allowed_plans = [3, 4]  # Free (3) e Community (4)
        allowed_user_types = ['trial', 'paid', 'free', 'admin', 'master']
        
        has_valid_plan = plan_id in allowed_plans
        has_valid_user_type = user_type in allowed_user_types
        is_admin = user_type in ['admin', 'master']
        
        if not (has_valid_plan or has_valid_user_type or is_admin):
            return jsonify({
                'success': False, 
                'message': 'Recurso disponível apenas para planos Community ou superior',
                'upgrade_required': True
            }), 403
        
        #  EXECUTAR ANÁLISE HISTÓRICA
        try:
            opcoes_service = OpcoesService()
            resultado = opcoes_service.volume_historico_analysis(ticker)
            
            if not resultado or 'error' in resultado:
                return jsonify({
                    'success': False, 
                    'message': f'Não foi possível obter dados históricos para {ticker}'
                }), 404
            
            return jsonify({
                'success': True,
                'data': resultado
            })
            
        except Exception as analysis_error:
            print(f" Erro na análise histórica: {analysis_error}")
            return jsonify({
                'success': False, 
                'message': f'Erro ao processar análise histórica: {str(analysis_error)}'
            }), 500
        
    except Exception as e:
        print(f" Erro geral em volume_historico_analysis: {str(e)}")
        return jsonify({
            'success': False, 
            'message': 'Erro interno do servidor'
        }), 500

@opcoes_bp.route('/api/opcoes/strike-detalhado', methods=['POST'])
@token_required
def strike_detalhado_analysis(current_user_id):
    """ NOVA ROTA - Análise detalhada de um strike específico"""
    try:
        data = request.get_json()
        ticker = data.get('ticker', '').upper()
        strike = float(data.get('strike', 0))
        
        if not ticker or strike <= 0:
            return jsonify({'success': False, 'message': 'Ticker e strike são obrigatórios'}), 400
        
        print(f" Strike Detalhado - Usuário: {current_user_id}, Ticker: {ticker}, Strike: R$ {strike}")
        
        # Mesma verificação de acesso
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Erro de conexão com banco'}), 500
            
        cursor = conn.cursor()
        cursor.execute("""
            SELECT plan_id, user_type, plan_name FROM users 
            WHERE id = %s
        """, (current_user_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user:
            return jsonify({'success': False, 'message': 'Usuário não encontrado'}), 404
        
        plan_id, user_type, plan_name = user
        
        # Verificação de acesso
        allowed_plans = [3, 4]
        allowed_user_types = ['trial', 'paid', 'free', 'admin', 'master']
        
        has_valid_plan = plan_id in allowed_plans
        has_valid_user_type = user_type in allowed_user_types
        is_admin = user_type in ['admin', 'master']
        
        if not (has_valid_plan or has_valid_user_type or is_admin):
            return jsonify({
                'success': False, 
                'message': 'Recurso disponível apenas para planos Community ou superior',
                'upgrade_required': True
            }), 403
        
        # Executar análise
        try:
            opcoes_service = OpcoesService()
            resultado = opcoes_service.analisar_strike_detalhado(ticker, strike)
            
            if not resultado:
                return jsonify({
                    'success': False, 
                    'message': f'Não foi possível analisar o strike R$ {strike} para {ticker}'
                }), 404
            
            return jsonify({
                'success': True,
                'data': resultado
            })
            
        except Exception as analysis_error:
            print(f" Erro na análise do strike: {analysis_error}")
            return jsonify({
                'success': False, 
                'message': f'Erro ao analisar strike: {str(analysis_error)}'
            }), 500
        
    except Exception as e:
        print(f" Erro geral em strike_detalhado_analysis: {str(e)}")
        return jsonify({
            'success': False, 
            'message': 'Erro interno do servidor'
        }), 500

@opcoes_bp.route('/api/opcoes/ticker-info', methods=['GET'])
@token_required
def get_ticker_info(current_user_id):
    """Obtém informações básicas do ticker"""
    try:
        ticker = request.args.get('ticker', '').upper()
        
        if not ticker:
            return jsonify({'success': False, 'message': 'Ticker é obrigatório'}), 400
        
        opcoes_service = OpcoesService()
        info = opcoes_service.get_ticker_basic_info(ticker)
        
        if not info:
            return jsonify({
                'success': False, 
                'message': f'Não foi possível obter informações para {ticker}'
            }), 404
        
        return jsonify({
            'success': True,
            'data': info
        })
        
    except Exception as e:
        print(f"Erro em get_ticker_info: {str(e)}")
        return jsonify({'success': False, 'message': 'Erro interno do servidor'}), 500

@opcoes_bp.route('/api/opcoes/available-expirations', methods=['GET'])
@token_required
def get_available_expirations(current_user_id):
    """Obtém datas de expiração disponíveis para um ticker"""
    try:
        ticker = request.args.get('ticker', '').upper()
        
        if not ticker:
            return jsonify({'success': False, 'message': 'Ticker é obrigatório'}), 400
        
        opcoes_service = OpcoesService()
        
        # Obter dados básicos para verificar se ticker existe
        ticker_info = opcoes_service.get_ticker_basic_info(ticker)
        if not ticker_info:
            return jsonify({
                'success': False, 
                'message': f'Ticker {ticker} não encontrado'
            }), 404
        
        # Obter dados de opções para extrair vencimentos
        options_data = opcoes_service.get_options_data(ticker)
        if not options_data:
            return jsonify({
                'success': False, 
                'message': f'Nenhuma opção encontrada para {ticker}'
            }), 404
        
        # Extrair letras de vencimento únicas
        letras_disponiveis = list(set([opt.get('letra_vencimento', '') for opt in options_data if opt.get('letra_vencimento')]))
        letras_disponiveis.sort()
        
        return jsonify({
            'success': True,
            'data': {
                'ticker': ticker,
                'letras_disponiveis': letras_disponiveis,
                'total_opcoes': len(options_data)
            }
        })
        
    except Exception as e:
        print(f"Erro em get_available_expirations: {str(e)}")
        return jsonify({'success': False, 'message': 'Erro interno do servidor'}), 500
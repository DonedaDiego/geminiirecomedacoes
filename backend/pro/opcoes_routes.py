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
                print(f"❌ Token não pôde ser decodificado com nenhuma das chaves: {JWT_KEYS_TO_TRY}")
                return jsonify({'success': False, 'message': 'Token inválido'}), 401
            
            print(f"✅ Token decodificado com sucesso usando chave: {successful_key}")
            current_user_id = decoded_data['user_id']
            
        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'message': 'Token expirado'}), 401
        except Exception as e:
            print(f"❌ Erro geral na autenticação: {e}")
            return jsonify({'success': False, 'message': 'Erro de autenticação'}), 401
        
        return f(current_user_id, *args, **kwargs)
    return decorated

@opcoes_bp.route('/api/opcoes/hunter-walls', methods=['POST'])
@token_required
def hunter_walls_analysis(current_user_id):
    """Análise Hunter Walls para múltiplos vencimentos"""
    try:
        data = request.get_json()
        ticker = data.get('ticker', '').upper()
        grupos_vencimentos = data.get('grupos_vencimentos', [])
        
        if not ticker:
            return jsonify({'success': False, 'message': 'Ticker é obrigatório'}), 400
        
        if not grupos_vencimentos:
            return jsonify({'success': False, 'message': 'Grupos de vencimentos são obrigatórios'}), 400
        
        # Verificar plano do usuário
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT plan_id FROM users WHERE id = %s", (current_user_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user or user[0] < 2:  # Plano Premium necessário
            return jsonify({
                'success': False, 
                'message': 'Recurso disponível apenas para planos Premium ou superior',
                'upgrade_required': True
            }), 403
        
        # Executar análise
        opcoes_service = OpcoesService()
        resultado = opcoes_service.hunter_walls_analysis(ticker, grupos_vencimentos)
        
        if not resultado:
            return jsonify({
                'success': False, 
                'message': f'Não foi possível obter dados para {ticker}'
            }), 404
        
        return jsonify({
            'success': True,
            'data': resultado
        })
        
    except Exception as e:
        print(f"Erro em hunter_walls_analysis: {str(e)}")
        return jsonify({'success': False, 'message': 'Erro interno do servidor'}), 500

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
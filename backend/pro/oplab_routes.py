from flask import Blueprint, request, jsonify
from functools import wraps
import jwt
from pro.oplab_service import OplabService

oplab_bp = Blueprint('oplab', __name__)

def token_required(f):
    """Decorator para proteger rotas com JWT"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'success': False, 'message': 'Token é obrigatório'}), 401
        
        try:
            from config import JWT_SECRET, JWT_KEYS_TO_TRY
            token = token.split(' ')[1]  # Remove 'Bearer '
            
            # Tentar decodificar com diferentes chaves
            decoded_data = None
            for key in JWT_KEYS_TO_TRY:
                try:
                    decoded_data = jwt.decode(token, key, algorithms=['HS256'])
                    break
                except jwt.InvalidTokenError:
                    continue
            
            if not decoded_data:
                return jsonify({'success': False, 'message': 'Token inválido'}), 401
            
            current_user_id = decoded_data['user_id']
            
        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'message': 'Token expirado'}), 401
        except Exception as e:
            print(f" Erro autenticação: {e}")
            return jsonify({'success': False, 'message': 'Erro de autenticação'}), 401
        
        return f(current_user_id, *args, **kwargs)
    return decorated


@oplab_bp.route('/api/oplab/estruturas-inteligentes', methods=['POST'])
@token_required
def estruturas_inteligentes(current_user_id):  
    try:
        data = request.get_json()
        
        # Validar payload
        ticker = data.get('ticker', '').upper()
        spot_price = float(data.get('spot_price', 0))
        flip_strike = float(data.get('flip_strike', 0))
        gex_descoberto = float(data.get('gex_descoberto', 0))
        cenario = data.get('cenario', {})
        
        if not ticker or spot_price <= 0:
            return jsonify({
                'success': False,
                'message': 'Ticker e spot_price são obrigatórios'
            }), 400
        
              
        # Inicializar serviço
        oplab_service = OplabService()
        
        # 1. Buscar opções ativas
        opcoes = oplab_service.buscar_opcoes_ativas(ticker)
        
        if not opcoes:
            return jsonify({
                'success': False,
                'message': f'Nenhuma opção com liquidez encontrada para {ticker}'
            }), 404
        
        # 2. Calcular estruturas inteligentes
        estruturas = oplab_service.calcular_estruturas_inteligentes(
            ticker=ticker,
            spot_price=spot_price,
            flip_strike=flip_strike if flip_strike > 0 else spot_price,
            gex_descoberto=gex_descoberto,
            cenario=cenario,
            opcoes=opcoes
        )
        
        if not estruturas:
            return jsonify({
                'success': False,
                'message': 'Não foi possível calcular estruturas com os dados fornecidos'
            }), 404
        
        # 3. Validar e filtrar estruturas
        estruturas_validas = [
            est for est in estruturas 
            if oplab_service.validar_estrutura(est)
        ]
        
        print(f" {len(estruturas_validas)} estruturas válidas calculadas")
        
        return jsonify({
            'success': True,
            'data': {
                'ticker': ticker,
                'spot_price': spot_price,
                'flip_strike': flip_strike,
                'gex_descoberto': gex_descoberto,
                'cenario': cenario,
                'estruturas': estruturas_validas,
                'total_opcoes_analisadas': len(opcoes)
            }
        })
        
    except Exception as e:
        print(f" Erro estruturas_inteligentes: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Erro ao calcular estruturas: {str(e)}'
        }), 500


@oplab_bp.route('/api/oplab/strikes-liquidos', methods=['GET'])
@token_required
def strikes_liquidos(current_user_id):
    """
    Retorna lista de strikes com liquidez para um ticker
    
    Query params:
    - ticker: PETR4
    - min_liquidez: 50 (opcional)
    """
    try:
        ticker = request.args.get('ticker', '').upper()
        min_liquidez = float(request.args.get('min_liquidez', 50))
        
        if not ticker:
            return jsonify({
                'success': False,
                'message': 'Ticker é obrigatório'
            }), 400
        
        print(f" Strikes líquidos - User: {current_user_id}, Ticker: {ticker}")
        
        # Buscar opções
        oplab_service = OplabService()
        opcoes = oplab_service.buscar_opcoes_ativas(ticker)
        
        if not opcoes:
            return jsonify({
                'success': False,
                'message': f'Nenhuma opção encontrada para {ticker}'
            }), 404
        
        # Filtrar strikes
        strikes = oplab_service.filtrar_strikes_por_liquidez(opcoes, min_liquidez)
        
        # Calcular estatísticas por strike
        strikes_info = []
        for strike in strikes:
            calls = [o for o in opcoes if o['strike'] == strike and o['category'] == 'CALL']
            puts = [o for o in opcoes if o['strike'] == strike and o['category'] == 'PUT']
            
            total_volume = sum(o['volume'] for o in calls + puts)
            total_oi = sum(o['open_interest'] for o in calls + puts)
            
            strikes_info.append({
                'strike': strike,
                'total_volume': total_volume,
                'total_oi': total_oi,
                'calls_count': len(calls),
                'puts_count': len(puts),
                'liquidity_score': total_volume + (total_oi * 0.5)
            })
        
        # Ordenar por liquidez
        strikes_info.sort(key=lambda x: x['liquidity_score'], reverse=True)
        
        return jsonify({
            'success': True,
            'data': {
                'ticker': ticker,
                'total_strikes': len(strikes_info),
                'strikes': strikes_info[:50]  # Top 50
            }
        })
        
    except Exception as e:
        print(f" Erro strikes_liquidos: {e}")
        return jsonify({
            'success': False,
            'message': f'Erro ao buscar strikes: {str(e)}'
        }), 500


@oplab_bp.route('/api/oplab/opcoes-por-strike', methods=['GET'])
@token_required
def opcoes_por_strike(current_user_id):
    """
    Retorna todas as opções (calls e puts) de um strike específico
    
    Query params:
    - ticker: PETR4
    - strike: 38.50
    """
    try:
        ticker = request.args.get('ticker', '').upper()
        strike = float(request.args.get('strike', 0))
        
        if not ticker or strike <= 0:
            return jsonify({
                'success': False,
                'message': 'Ticker e strike são obrigatórios'
            }), 400
        
        print(f"Opções por strike - User: {current_user_id}, {ticker} R$ {strike}")
        
        # Buscar opções
        oplab_service = OplabService()
        opcoes = oplab_service.buscar_opcoes_ativas(ticker)
        
        if not opcoes:
            return jsonify({
                'success': False,
                'message': f'Nenhuma opção encontrada para {ticker}'
            }), 404
        
        # Filtrar pelo strike
        opcoes_strike = [
            o for o in opcoes 
            if abs(o['strike'] - strike) < 0.01
        ]
        
        if not opcoes_strike:
            return jsonify({
                'success': False,
                'message': f'Nenhuma opção encontrada para strike R$ {strike}'
            }), 404
        
        # Separar calls e puts
        calls = [o for o in opcoes_strike if o['category'] == 'CALL']
        puts = [o for o in opcoes_strike if o['category'] == 'PUT']
        
        return jsonify({
            'success': True,
            'data': {
                'ticker': ticker,
                'strike': strike,
                'calls': calls,
                'puts': puts,
                'total_volume': sum(o['volume'] for o in opcoes_strike),
                'total_oi': sum(o['open_interest'] for o in opcoes_strike)
            }
        })
        
    except Exception as e:
        print(f" Erro opcoes_por_strike: {e}")
        return jsonify({
            'success': False,
            'message': f'Erro ao buscar opções: {str(e)}'
        }), 500


@oplab_bp.route('/api/oplab/health', methods=['GET'])
def health_check():
    """Health check do serviço OpLab"""
    try:
        oplab_service = OplabService()
        
        # Testar se token está configurado
        has_token = bool(oplab_service.oplab_token)
        
        return jsonify({
            'success': True,
            'service': 'OpLab Service',
            'status': 'online',
            'token_configured': has_token
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'service': 'OpLab Service',
            'status': 'error',
            'error': str(e)
        }), 500
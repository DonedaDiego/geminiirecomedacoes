# mercadopago_routes.py - VERSÃO LIMPA E CORRIGIDA SEM DUPLICATAS
# ========================================================================

from flask import Blueprint, request, jsonify
from datetime import datetime
import os

# ===== VERIFICAÇÃO CRÍTICA DO SDK =====
try:
    import mercadopago
    import pag.mercadopago_service as mercadopago_service
    MP_AVAILABLE = True
    print(" SDK Mercado Pago carregado com sucesso!")
except ImportError as e:
    MP_AVAILABLE = False
    print(f" SDK Mercado Pago não disponível: {e}")
    print(" Instale com: pip install mercadopago")
    # Criar service mock para evitar crashes
    class MockService:
        @staticmethod
        def create_checkout_service(*args, **kwargs):
            return {'success': False, 'error': 'SDK não instalado'}
        @staticmethod
        def process_payment(*args, **kwargs):
            return {'status': 'error', 'error': 'SDK não instalado'}
        @staticmethod
        def test_mercadopago_connection():
            return {'success': False, 'error': 'SDK não instalado'}
        @staticmethod
        def get_plans_service():
            return {'success': False, 'error': 'SDK não instalado'}
        @staticmethod
        def check_payment_status_service(*args, **kwargs):
            return {'success': False, 'error': 'SDK não instalado'}
        @staticmethod
        def validate_device_id(*args, **kwargs):
            return False
    
    mercadopago_service = MockService()

# ===== CONFIGURAÇÃO DO BLUEPRINT =====
mercadopago_bp = Blueprint('mercadopago', __name__, url_prefix='/api/mercadopago')

# ===== DECORATOR PARA VERIFICAR SDK =====
def require_mp_sdk(f):
    """Decorator para verificar se SDK está disponível"""
    def wrapper(*args, **kwargs):
        if not MP_AVAILABLE:
            return jsonify({
                'success': False,
                'error': 'Mercado Pago temporariamente indisponível',
                'details': 'SDK não instalado - execute: pip install mercadopago'
            }), 503
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# ===== ROTAS PRINCIPAIS =====

@mercadopago_bp.route('/test', methods=['GET'])
@require_mp_sdk
def test_connection():
    """Testar conexão com Mercado Pago"""
    result = mercadopago_service.test_mercadopago_connection()
    return jsonify(result)

@mercadopago_bp.route('/plans', methods=['GET'])
@require_mp_sdk
def get_plans():
    """Retornar planos disponíveis"""
    result = mercadopago_service.get_plans_service()
    return jsonify(result)

@mercadopago_bp.route('/checkout/create', methods=['POST'])
@require_mp_sdk
def create_checkout():
    """ Criar checkout com Device ID para aprovação - VERSÃO CORRIGIDA E LIMPA"""
    
    if mercadopago_service is None:
        return jsonify({'success': False, 'error': 'Serviço temporariamente indisponível'}), 503
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "Dados JSON são obrigatórios"
            }), 400
        
        #  EXTRAIR DADOS CORRETOS DO FRONTEND
        plan = data.get('plan', 'pro')
        cycle = data.get('cycle', 'monthly')
        user_id = data.get('user_id')           
        user_email = data.get('user_email')      
        user_name = data.get('user_name')       
        device_id = data.get('device_id', 'web-browser-local')  #  VALOR PADRÃO
        discounted_price = data.get('discounted_price')
        coupon_code = data.get('coupon_code')
        
        #  CORREÇÃO: Tratar device_id undefined/null
        if not device_id or device_id == 'undefined' or device_id == 'null':
            device_id = 'web-browser-local'
        
        # Compatibilidade com versão antiga
        customer_email = data.get('customer_email', user_email)
        
        print(f" ROUTE: Criando checkout CORRIGIDO")
        print(f"   Plan: {plan} | Cycle: {cycle}")
        print(f"   User ID: {user_id}")
        print(f"   User Email: {user_email}")
        print(f"   User Name: {user_name}")
        print(f"   Device ID: {device_id}")
        
        # =====  APLICAR DESCONTO DO CUPOM (NOVA ADIÇÃO) =====
        if coupon_code and discounted_price:
            print(f"🎫 CUPOM DETECTADO: {coupon_code}")
            print(f" PREÇO COM DESCONTO: R$ {discounted_price}")
        else:
            print("ℹ️ Nenhum cupom aplicado")
        
        #  CHAMAR SERVIÇO COM PARÂMETROS CORRETOS
        result = mercadopago_service.create_checkout_service(
            plan=plan, 
            cycle=cycle, 
            customer_email=customer_email,      
            user_id=user_id,                    
            user_email=user_email,              
            user_name=user_name,                
            discounted_price=discounted_price, 
            coupon_code=coupon_code,
            device_id=device_id
        )
        
        if result['success']:
            print(f" ROUTE: Checkout criado com sucesso - {result['data']['preference_id']}")
            return jsonify(result), 200
        else:
            print(f" ROUTE: Erro no checkout - {result['error']}")
            return jsonify(result), 500
            
    except Exception as e:
        print(f" ROUTE: Erro crítico no checkout - {e}")
        return jsonify({
            "success": False,
            "error": "Erro interno do servidor",
            "details": str(e)
        }), 500

@mercadopago_bp.route('/webhook', methods=['POST', 'GET'])
@require_mp_sdk
def webhook():
    """ WEBHOOK OTIMIZADO PARA APROVAÇÃO"""
    
    if request.method == 'GET':
        return jsonify({
            'status': 'webhook_active',
            'service': 'mercadopago',
            'timestamp': datetime.now().isoformat(),
            'version': '2.0_optimized',
            'sdk_available': MP_AVAILABLE
        })
    
    print("\n" + "🔔" + "="*50)
    print(f"WEBHOOK RECEBIDO - {datetime.now()}")
    print("="*51)
    
    try:
        data = request.get_json()
        if not data:
            print(" Webhook sem dados JSON")
            return jsonify({"error": "No data"}), 400
        
        print(f"📋 Tipo: {data.get('type')}")
        print(f"📋 Action: {data.get('action', 'N/A')}")
        
        webhook_type = data.get("type")
        
        if webhook_type != "payment":
            print(f" Webhook ignorado: {webhook_type}")
            return jsonify({
                "success": True, 
                "message": f"Webhook '{webhook_type}' ignorado"
            }), 200
        
        payment_data = data.get("data", {})
        payment_id = payment_data.get("id")
        
        if not payment_id:
            print(" Payment ID ausente")
            return jsonify({"error": "Payment ID missing"}), 400
        
        print(f"💳 Payment ID: {payment_id}")
        
        print(" Iniciando processamento otimizado...")
        result = mercadopago_service.process_payment(payment_id)
        
        if result['status'] == 'success':
            print(" WEBHOOK: Processamento bem-sucedido!")
            return jsonify({
                "success": True,
                "message": "Pagamento processado e plano ativado!",
                "payment_id": payment_id,
                "user_plan": result.get('plan_name'),
                "user_name": result.get('user_name'),
                "sdk_status": "available"
            }), 200
        
        elif result['status'] == 'already_processed':
            print(" WEBHOOK: Pagamento já processado")
            return jsonify({
                "success": True,
                "message": "Pagamento já processado",
                "payment_id": payment_id
            }), 200
        
        else:
            print(f" WEBHOOK: Erro no processamento: {result.get('error')}")
            return jsonify({
                "success": False,
                "error": result.get('error', 'Erro no processamento'),
                "payment_id": payment_id
            }), 500
        
    except Exception as e:
        print(f" WEBHOOK: ERRO CRÍTICO - {e}")
        return jsonify({
            "success": False,
            "error": f"Erro interno: {str(e)}"
        }), 500

@mercadopago_bp.route('/payment/status/<payment_id>')
@require_mp_sdk
def check_payment_status(payment_id):
    """Verificar status de pagamento"""
    try:
        print(f" Verificando status do pagamento: {payment_id}")
        result = mercadopago_service.check_payment_status_service(payment_id)
        return jsonify(result)
        
    except Exception as e:
        print(f" Erro ao verificar status: {e}")
        return jsonify({'error': str(e)}), 500

@mercadopago_bp.route('/validate-device', methods=['POST'])
@require_mp_sdk
def validate_device():
    """Validar Device ID (para debug e testes)"""
    try:
        data = request.get_json()
        device_id = data.get('device_id', 'web-browser-local')
        
        #  SEMPRE ACEITAR DEVICE_ID (mesmo que seja padrão)
        return jsonify({
            "success": True,
            "data": {
                "device_id": device_id,
                "is_valid": True,  # Sempre válido
                "format_check": True,
                "length_check": len(device_id) >= 10
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ===== ROTA DE STATUS SEM REQUIRE_MP_SDK =====
@mercadopago_bp.route('/debug/info', methods=['GET'])
def debug_info():
    """Informações de debug para aprovação"""
    try:
        debug_data = {
            "service_status": "active" if MP_AVAILABLE else "sdk_missing",
            "sdk_loaded": MP_AVAILABLE,
            "environment": "sandbox" if "TEST" in str(os.environ.get('MP_ACCESS_TOKEN', '')) else "production",
            "has_token": bool(os.environ.get('MP_ACCESS_TOKEN')),
            "token_type": "TEST" if "TEST" in str(os.environ.get('MP_ACCESS_TOKEN', '')) else "PROD",
            "features": {
                "device_id_validation": MP_AVAILABLE,
                "auto_return": MP_AVAILABLE,
                "binary_mode": MP_AVAILABLE,
                "retry_logic": MP_AVAILABLE,
                "webhook_active": MP_AVAILABLE
            }
        }
        
        return jsonify({
            "success": True,
            "data": debug_data
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ===== FUNÇÕES DE EXPORT =====

def get_mercadopago_blueprint():
    """Retornar blueprint otimizado"""
    return mercadopago_bp
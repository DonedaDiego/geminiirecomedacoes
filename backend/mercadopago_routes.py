# mercadopago_routes.py - VERSÃO NOVA COM MELHORIAS PARA APROVAÇÃO
# ========================================================================

from flask import Blueprint, request, jsonify
from datetime import datetime
import mercadopago_service

# ===== CONFIGURAÇÃO DO BLUEPRINT =====
mercadopago_bp = Blueprint('mercadopago', __name__, url_prefix='/api/mercadopago')

# ===== ROTAS PRINCIPAIS =====

@mercadopago_bp.route('/test', methods=['GET'])
def test_connection():
    """Testar conexão com Mercado Pago"""
    result = mercadopago_service.test_mercadopago_connection()
    return jsonify(result)

@mercadopago_bp.route('/plans', methods=['GET'])
def get_plans():
    """Retornar planos disponíveis"""
    result = mercadopago_service.get_plans_service()
    return jsonify(result)

@mercadopago_bp.route('/checkout/create', methods=['POST'])
def create_checkout():
    """🔥 Criar checkout com Device ID para aprovação"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "Dados JSON são obrigatórios"
            }), 400
        
        # Extrair dados
        plan = data.get('plan', 'pro')
        cycle = data.get('cycle', 'monthly')
        customer_email = data.get('customer_email', 'cliente@geminii.com.br')
        discounted_price = data.get('discounted_price')
        coupon_code = data.get('coupon_code')
        device_id = data.get('device_id')  # 🔥 DEVICE ID PARA APROVAÇÃO
        
        print(f"🔥 ROUTE: Criando checkout com Device ID")
        print(f"   Plan: {plan} | Cycle: {cycle}")
        print(f"   Email: {customer_email}")
        print(f"   Device ID: {device_id[:20] + '...' if device_id else 'NÃO FORNECIDO'}")
        
        # Chamar serviço COM device_id
        result = mercadopago_service.create_checkout_service(
            plan=plan, 
            cycle=cycle, 
            customer_email=customer_email, 
            discounted_price=discounted_price, 
            coupon_code=coupon_code,
            device_id=device_id  # 🔥 PASSAR DEVICE ID
        )
        
        if result['success']:
            print(f"✅ ROUTE: Checkout criado com sucesso - {result['data']['preference_id']}")
            return jsonify(result), 200
        else:
            print(f"❌ ROUTE: Erro no checkout - {result['error']}")
            return jsonify(result), 500
            
    except Exception as e:
        print(f"❌ ROUTE: Erro crítico no checkout - {e}")
        return jsonify({
            "success": False,
            "error": "Erro interno do servidor",
            "details": str(e)
        }), 500

@mercadopago_bp.route('/webhook', methods=['POST', 'GET'])
def webhook():
    """🔥 WEBHOOK OTIMIZADO PARA APROVAÇÃO"""
    
    if request.method == 'GET':
        return jsonify({
            'status': 'webhook_active',
            'service': 'mercadopago',
            'timestamp': datetime.now().isoformat(),
            'version': '2.0_optimized'
        })
    
    print("\n" + "🔔" + "="*50)
    print(f"WEBHOOK RECEBIDO - {datetime.now()}")
    print("="*51)
    
    try:
        # 1. OBTER DADOS DO WEBHOOK
        data = request.get_json()
        if not data:
            print("❌ Webhook sem dados JSON")
            return jsonify({"error": "No data"}), 400
        
        print(f"📋 Tipo: {data.get('type')}")
        print(f"📋 Action: {data.get('action', 'N/A')}")
        
        # 2. VERIFICAR SE É PAGAMENTO
        webhook_type = data.get("type")
        
        if webhook_type != "payment":
            print(f"⚠️ Webhook ignorado: {webhook_type}")
            return jsonify({
                "success": True, 
                "message": f"Webhook '{webhook_type}' ignorado"
            }), 200
        
        # 3. EXTRAIR ID DO PAGAMENTO
        payment_data = data.get("data", {})
        payment_id = payment_data.get("id")
        
        if not payment_id:
            print("❌ Payment ID ausente")
            return jsonify({"error": "Payment ID missing"}), 400
        
        print(f"💳 Payment ID: {payment_id}")
        
        # 4. PROCESSAR PAGAMENTO COM MELHORIAS
        print("🔄 Iniciando processamento otimizado...")
        result = mercadopago_service.process_payment(payment_id)
        
        # 5. RETORNAR RESPOSTA BASEADA NO RESULTADO
        if result['status'] == 'success':
            print("✅ WEBHOOK: Processamento bem-sucedido!")
            
            response_data = {
                "success": True,
                "message": "Pagamento processado e plano ativado!",
                "payment_id": payment_id,
                "user_plan": result.get('plan_name'),
                "user_name": result.get('user_name'),
                "device_id_present": bool(result.get('device_id'))
            }
            
            # Adicionar device_id se presente (para debug)
            if result.get('device_id'):
                response_data["device_validation"] = "Device ID processado com sucesso"
            
            return jsonify(response_data), 200
        
        elif result['status'] == 'already_processed':
            print("⚠️ WEBHOOK: Pagamento já processado")
            return jsonify({
                "success": True,
                "message": "Pagamento já processado",
                "payment_id": payment_id
            }), 200
        
        elif result['status'] == 'not_approved':
            print(f"⚠️ WEBHOOK: Pagamento não aprovado: {result.get('mp_status')}")
            return jsonify({
                "success": True,
                "message": f"Pagamento não aprovado: {result.get('mp_status')}",
                "payment_id": payment_id
            }), 200
        
        else:
            print(f"❌ WEBHOOK: Erro no processamento: {result.get('error')}")
            return jsonify({
                "success": False,
                "error": result.get('error', 'Erro no processamento'),
                "payment_id": payment_id
            }), 500
        
    except Exception as e:
        print(f"❌ WEBHOOK: ERRO CRÍTICO - {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "success": False,
            "error": f"Erro interno: {str(e)}"
        }), 500

@mercadopago_bp.route('/payment/status/<payment_id>')
def check_payment_status(payment_id):
    """Verificar status de pagamento"""
    try:
        print(f"🔍 Verificando status do pagamento: {payment_id}")
        result = mercadopago_service.check_payment_status_service(payment_id)
        
        # Adicionar informações extras para debug
        if result.get('mercado_pago'):
            mp_data = result['mercado_pago']
            if mp_data.get('device_id'):
                result['device_validation'] = f"Device ID presente: {mp_data['device_id'][:20]}..."
            else:
                result['device_validation'] = "Device ID não encontrado"
        
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ Erro ao verificar status: {e}")
        return jsonify({'error': str(e)}), 500

# 🔥 ROTA ADICIONAL PARA VALIDAÇÃO DE DEVICE ID
@mercadopago_bp.route('/validate-device', methods=['POST'])
def validate_device():
    """Validar Device ID (para debug e testes)"""
    try:
        data = request.get_json()
        device_id = data.get('device_id')
        
        if not device_id:
            return jsonify({
                "success": False,
                "error": "Device ID é obrigatório"
            }), 400
        
        is_valid = mercadopago_service.validate_device_id(device_id)
        
        return jsonify({
            "success": True,
            "data": {
                "device_id": device_id,
                "is_valid": is_valid,
                "format_check": device_id.startswith('mp-device-') if device_id else False,
                "length_check": len(device_id) >= 10 if device_id else False
            }
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ===== ROTAS DE TESTE E DEBUG =====

@mercadopago_bp.route('/debug/info', methods=['GET'])
def debug_info():
    """Informações de debug para aprovação"""
    try:
        import os
        
        debug_data = {
            "service_status": "active",
            "sdk_loaded": mercadopago_service.mp_sdk is not None,
            "environment": "sandbox" if "TEST" in str(os.environ.get('MP_ACCESS_TOKEN', '')) else "production",
            "features": {
                "device_id_validation": True,
                "auto_return": True,
                "binary_mode": True,
                "retry_logic": True,
                "webhook_active": True
            },
            "endpoints": [
                "POST /api/mercadopago/checkout/create",
                "POST /api/mercadopago/webhook", 
                "GET  /api/mercadopago/payment/status/<id>",
                "POST /api/mercadopago/validate-device",
                "GET  /api/mercadopago/test"
            ]
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

# Funções de compatibilidade
def process_payment(payment_id):
    """Wrapper para compatibilidade"""
    return mercadopago_service.process_payment(payment_id)

def create_payments_table():
    """Função de compatibilidade"""
    print("✅ create_payments_table: Gerenciado automaticamente")
    return True

def add_plan_expires_field():
    """Função de compatibilidade"""
    print("✅ add_plan_expires_field: Gerenciado automaticamente")
    return True

# ===== DEBUG INFO =====
if __name__ == "__main__":
    print("🔥 Mercado Pago Routes NOVO com melhorias!")
    print("📋 Rotas otimizadas:")
    print("   - ✅ Device ID capture")
    print("   - ✅ Enhanced webhook")
    print("   - ✅ Payment validation")
    print("   - ✅ Debug endpoints")
    print("   - ✅ Error handling")
    print("\n🎯 PRONTO PARA APROVAÇÃO!")

print("🚀 MercadoPago Routes carregado e otimizado!")
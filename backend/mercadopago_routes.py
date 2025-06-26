# mercadopago_routes.py - ROUTES LIMPAS (só chama services)
from flask import Blueprint, request, jsonify
from datetime import datetime
import mercadopago_service

# ===== CONFIGURAÇÃO DO BLUEPRINT =====
mercadopago_bp = Blueprint('mercadopago', __name__, url_prefix='/api/mercadopago')

# ===== ROTAS =====

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
    """Criar checkout do Mercado Pago"""
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
        
        # Chamar serviço
        result = mercadopago_service.create_checkout_service(
            plan, cycle, customer_email, discounted_price, coupon_code
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Erro interno do servidor",
            "details": str(e)
        }), 500

@mercadopago_bp.route('/webhook', methods=['POST', 'GET'])
def webhook():
    """WEBHOOK PRINCIPAL"""
    
    if request.method == 'GET':
        return jsonify({
            'status': 'webhook_active',
            'service': 'mercadopago',
            'timestamp': datetime.now().isoformat()
        })
    
    try:
        print(f"\n🔔 ROUTE: WEBHOOK RECEBIDO - {datetime.now()}")
        
        # Obter dados
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data"}), 400
        
        webhook_type = data.get("type")
        
        if webhook_type == "payment":
            payment_data = data.get("data", {})
            payment_id = payment_data.get("id")
            
            if not payment_id:
                return jsonify({"error": "Payment ID missing"}), 400
            
            # Chamar serviço de processamento
            result = mercadopago_service.process_payment(payment_id)
            
            if result['status'] == 'success':
                return jsonify({
                    "success": True,
                    "message": "Pagamento processado e plano ativado!",
                    "payment_id": payment_id,
                    "user_plan": result.get('plan_name'),
                    "user_name": result.get('user_name')
                }), 200
            
            elif result['status'] == 'already_processed':
                return jsonify({
                    "success": True,
                    "message": "Pagamento já processado",
                    "payment_id": payment_id
                }), 200
            
            else:
                return jsonify({
                    "success": False,
                    "error": result.get('error', 'Erro no processamento'),
                    "payment_id": payment_id
                }), 500
        
        else:
            return jsonify({
                "success": True, 
                "message": f"Webhook '{webhook_type}' ignorado"
            }), 200
        
    except Exception as e:
        print(f"❌ ROUTE: ERRO NO WEBHOOK - {e}")
        
        return jsonify({
            "success": False,
            "error": f"Erro: {str(e)}"
        }), 500

@mercadopago_bp.route('/payment/status/<payment_id>')
def check_payment_status(payment_id):
    """Verificar status de pagamento"""
    try:
        result = mercadopago_service.check_payment_status_service(payment_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== FUNÇÃO DE EXPORT =====

def get_mercadopago_blueprint():
    """Retornar blueprint"""
    return mercadopago_bp

# Para compatibilidade - funções que o main.py ainda pode chamar
def process_payment(payment_id):
    """Wrapper para compatibilidade com main.py"""
    return mercadopago_service.process_payment(payment_id)

def create_payments_table():
    """Função vazia para compatibilidade"""
    print("✅ create_payments_table: Tabela já existe via database.py")
    return True

def add_plan_expires_field():
    """Função vazia para compatibilidade"""
    print("✅ add_plan_expires_field: Campo já existe via database.py")
    return True

# Debug info
if __name__ == "__main__":
    print("🔧 Mercado Pago Routes (limpo) carregado!")
    print("📋 Todas as funções delegadas para mercadopago_service.py")
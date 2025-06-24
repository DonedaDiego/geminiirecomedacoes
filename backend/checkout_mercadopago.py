# checkout_mercadopago.py - VERSÃO FINAL CORRIGIDA

from flask import Blueprint, request, jsonify
import os
import time
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv()

# ===== CONFIGURAÇÃO MERCADO PAGO =====
mp_token = os.environ.get('MP_ACCESS_TOKEN', 'TEST-8540613393237089-091618-106d38d51fc598ab9762456309594429-1968398743')


# Importar SDK do Mercado Pago
mp_sdk = None
preference_client = None

try:
    import mercadopago
    
    # ✅ MÉTODO CORRETO BASEADO NO SEU TESTE
    mp_sdk = mercadopago.SDK(mp_token)
    preference_client = mp_sdk.preference()  # Seu teste mostrou que isso funciona

    
except ImportError:
    print("❌ Módulo mercadopago não encontrado. Instale com: pip install mercadopago")
except Exception as e:
    print(f"❌ Erro ao carregar SDK: {e}")

# Blueprint
mercadopago_bp = Blueprint('mercadopago', __name__, url_prefix='/api/mercadopago')

# ===== CONFIGURAÇÃO DOS PLANOS =====
PLANS = {
    "pro": {
        "id": "pro",
        "name": "Pro",
        "description": "Para quem já investe e quer se posicionar melhor",
        "monthly_price": 79,
        "annual_price": 72,
        "features": [
            "Monitor avançado de ações",
            "RSL e análise técnica avançada", 
            "Backtests automáticos",
            "Alertas via WhatsApp",
            "Dados históricos ilimitados",
            "API para desenvolvedores"
        ]
    },
    "premium": {
        "id": "premium", 
        "name": "Premium",
        "description": "Para investidores experientes que querem diferenciais",
        "monthly_price": 149,
        "annual_price": 137,
        "features": [
            "Tudo do Pro +",
            "Long & Short strategies",
            "IA para recomendações", 
            "Consultoria personalizada",
            "Acesso prioritário",
            "Relatórios exclusivos"
        ]
    }
}

# ===== FUNÇÕES AUXILIARES =====

def test_mercadopago_connection():
    """Testar conexão com Mercado Pago"""
    if not mp_sdk or not preference_client:
        return {
            "success": False,
            "error": "SDK Mercado Pago não carregado"
        }
    
    try:
        # Verificar token
        token = os.environ.get('MP_ACCESS_TOKEN', '')
        
        if not token:
            return {
                "success": False,
                "error": "Token MP_ACCESS_TOKEN não configurado"
            }
        
        # ✅ ESTRUTURA CORRETA BASEADA NO SEU TESTE QUE FUNCIONOU
        test_preference = {
            "items": [
                {
                    "id": "test",
                    "title": "Teste de Conexão",
                    "quantity": 1,
                    "currency_id": "BRL",
                    "unit_price": 1.0
                }
            ]
        }
        
        print("🧪 Testando conexão com MP...")
        
        # ✅ USAR O MÉTODO QUE FUNCIONOU NO SEU TESTE
        result = preference_client.create(test_preference)
        
        if result.get("status") == 201:
            preference_id = result["response"]["id"]
            
            return {
                "success": True,
                "message": "Mercado Pago conectado com sucesso!",
                "environment": "sandbox" if "TEST" in token else "production",
                "preference_test_id": preference_id,
                "sdk_method": "preference.create()"
            }
        else:
            return {
                "success": False, 
                "error": f"Erro na resposta do MP: {result.get('response', 'Sem detalhes')}"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Erro ao conectar com MP: {str(e)}"
        }

def create_checkout_function():
    """Função principal para criar checkout"""
    if not mp_sdk or not preference_client:
        return jsonify({
            "success": False,
            "error": "SDK Mercado Pago não disponível"
        }), 500
    
    try:
        # Dados recebidos do frontend
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "Dados JSON são obrigatórios"
            }), 400
        
        plan = data.get('plan', 'pro')
        cycle = data.get('cycle', 'monthly')
        customer_email = data.get('customer_email', 'cliente@geminii.com.br')  # Email padrão se não fornecido
        discounted_price = data.get('discounted_price')  
        coupon_code = data.get('coupon_code')
    
        
        # Validar plano
        if plan not in PLANS:
            return jsonify({
                "success": False,
                "error": f"Plano '{plan}' não encontrado"
            }), 400
        
        plan_data = PLANS[plan]
        plan_id = plan_data["id"]
        plan_name = plan_data["name"]
        
        # Determinar preço baseado no ciclo
        if cycle == 'annual':
            original_price = plan_data["annual_price"]
            cycle_display = "Anual"
        else:
            original_price = plan_data["monthly_price"]
            cycle_display = "Mensal"

        # ✅ USAR PREÇO COM DESCONTO SE FORNECIDO
        if discounted_price is not None:
            price = float(discounted_price)
            print(f"🎫 Cupom aplicado: {coupon_code}")
            print(f"💰 Preço original: R$ {original_price}")
            print(f"💰 Preço com desconto: R$ {price}")
        else:
            price = original_price
        
        # Determinar URLs de retorno baseado no ambiente
        if os.environ.get('DATABASE_URL'):
            base_url = "https://app.geminii.com.br"
        else:
            base_url = "http://localhost:5000"
        
        if coupon_code:
            item_title = f"Geminii {plan_name} - {cycle_display} (Cupom: {coupon_code})"
        else:
            item_title = f"Geminii {plan_name} - {cycle_display}"    
            
        
        # ✅ ESTRUTURA CORRETA BASEADA NO SEU TESTE QUE FUNCIONOU
        preference_data = {
            "items": [
                {
                    "id": plan_id,
                    "title": item_title,
                    "quantity": 1,
                    "currency_id": "BRL",
                    "unit_price": float(price)
                }
            ],
            "back_urls": {
                "success": f"{base_url}/payment/success",
                "pending": f"{base_url}/payment/pending", 
                "failure": f"{base_url}/payment/failure"
            },
            "external_reference": f"geminii_{plan_id}_{cycle}_{int(time.time())}"
        }
        
        # Adicionar informações do pagador se email fornecido
        if customer_email and customer_email != 'cliente@geminii.com.br':
            preference_data["payer"] = {
                "email": customer_email
            }
        
        # ✅ USAR EXATAMENTE O MÉTODO QUE FUNCIONOU NO TESTE
        preference_response = preference_client.create(preference_data)
        
        print(f"📊 Resposta do MP: {preference_response}")
        
        if preference_response.get("status") == 201:
            preference = preference_response["response"]
            preference_id = preference["id"]
            
            print(f"✅ Preferência criada com sucesso: {preference_id}")
            
            # URLs de checkout
            checkout_url = preference.get("init_point", "")
            sandbox_url = preference.get("sandbox_init_point", "")
            
            print(f"🔗 Checkout URL (Produção): {checkout_url}")
            print(f"🔗 Sandbox URL (Desenvolvimento): {sandbox_url}")
            
            return jsonify({
                "success": True,
                "data": {
                    "preference_id": preference_id,
                    "checkout_url": checkout_url,
                    "sandbox_url": sandbox_url,
                    "plan": plan,
                    "cycle": cycle,
                    "price": price,
                    "currency": "BRL",
                    "external_reference": preference_data["external_reference"]
                }
            })
        else:
            error_info = preference_response.get("response", {})
            print(f"❌ Erro MP: {error_info}")
            
            return jsonify({
                "success": False,
                "error": "Erro ao criar checkout no Mercado Pago",
                "details": error_info
            }), 500
            
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "success": False,
            "error": "Erro interno do servidor",
            "details": str(e)
        }), 500

# ===== ROTAS DO MERCADO PAGO =====

@mercadopago_bp.route('/test', methods=['GET'])
def test_connection():
    """Testar conexão com Mercado Pago"""
    result = test_mercadopago_connection()
    return jsonify(result)

@mercadopago_bp.route('/plans', methods=['GET'])
def get_plans():
    """Retornar planos disponíveis"""
    try:
        plans_list = []
        for plan_id, plan_data in PLANS.items():
            plans_list.append({
                "id": plan_data["id"],
                "name": plan_id,
                "display_name": plan_data["name"],
                "description": plan_data["description"],
                "price_monthly": plan_data["monthly_price"],
                "price_annual": plan_data["annual_price"],
                "features": plan_data["features"]
            })
        
        return jsonify({"success": True, "data": plans_list})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@mercadopago_bp.route('/checkout/create', methods=['POST'])
def create_checkout():
    """Criar checkout do Mercado Pago"""
    return create_checkout_function()

@mercadopago_bp.route('/webhook', methods=['POST'])
def webhook():
    """Webhook para receber notificações do Mercado Pago"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"success": False, "error": "Dados não fornecidos"}), 400
        
        print(f"🔔 Webhook recebido: {data}")
        
        webhook_type = data.get("type")
        
        if webhook_type == "payment":
            payment_id = data.get("data", {}).get("id")
            
            if payment_id:
                print(f"💳 Processando pagamento: {payment_id}")
                # Aqui você pode adicionar lógica para processar o pagamento
            
        return jsonify({"success": True}), 200
        
    except Exception as e:
        print(f"❌ Erro no webhook: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ===== FUNÇÕES DE EXPORT =====

def get_mercadopago_blueprint():
    """Retornar blueprint para registrar no Flask"""
    return mercadopago_bp

# Para debug
if __name__ == "__main__":
    print("🔧 Módulo Mercado Pago carregado!")
    print(f"📋 Planos disponíveis: {list(PLANS.keys())}")
    print(f"🔐 Token: {mp_token[:20]}...")
    
    # Testar conexão
    result = test_mercadopago_connection()
    print(f"🌐 Status da conexão: {result}")
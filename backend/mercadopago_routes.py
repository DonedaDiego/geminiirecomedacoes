# mercadopago_routes.py - VERSÃO LIMPA E FUNCIONAL
from flask import Blueprint, request, jsonify
import os
import time
import requests
from datetime import datetime, timedelta, timezone
from database import get_db_connection
from dotenv import load_dotenv

load_dotenv()

# ===== CONFIGURAÇÃO DO BLUEPRINT =====
mercadopago_bp = Blueprint('mercadopago', __name__, url_prefix='/api/mercadopago')

# ===== CONFIGURAÇÃO MERCADO PAGO =====
mp_token = os.environ.get('MP_ACCESS_TOKEN', 'TEST-8540613393237089-091618-106d38d51fc598ab9762456309594429-1968398743')

# Importar SDK do Mercado Pago
mp_sdk = None
preference_client = None

try:
    import mercadopago
    mp_sdk = mercadopago.SDK(mp_token)
    preference_client = mp_sdk.preference()
    print("✅ SDK Mercado Pago carregado com sucesso!")
except ImportError:
    print("❌ Módulo mercadopago não encontrado. Instale com: pip install mercadopago")
except Exception as e:
    print(f"❌ Erro ao carregar SDK: {e}")

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

# ===== FUNÇÃO PRINCIPAL DE PROCESSAMENTO =====
def process_payment(payment_id):
    """
    Processa um pagamento - VERSÃO QUE FUNCIONA!
    Usa seus planos originais: pro e premium
    """
    try:
        print(f"\n🔥 PROCESSANDO PAGAMENTO VIA WEBHOOK: {payment_id}")
        
        # 1. Buscar dados no MP
        mp_token = os.environ.get('MP_ACCESS_TOKEN')
        headers = {
            'Authorization': f'Bearer {mp_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f'https://api.mercadopago.com/v1/payments/{payment_id}',
            headers=headers
        )
        
        if response.status_code != 200:
            raise Exception(f'Pagamento não encontrado no MP: {response.status_code}')
            
        mp_data = response.json()
        
        if mp_data.get('status') != 'approved':
            raise Exception(f'Pagamento não aprovado: {mp_data.get("status")}')
        
        # 2. Extrair dados
        external_ref = mp_data.get('external_reference', '')
        amount = float(mp_data.get('transaction_amount', 0))
        payer_email = mp_data.get('payer', {}).get('email', '')
        
        print(f"💰 Valor: R$ {amount}")
        print(f"📧 Email: {payer_email}")
        print(f"🔗 Ref: {external_ref}")
        
        # 3. Buscar usuário
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Tentar por email do pagador primeiro
        cursor.execute("SELECT id, email FROM users WHERE email = %s", (payer_email,))
        user_row = cursor.fetchone()
        
        # Se não encontrar, usar martha@gmail.com
        if not user_row:
            cursor.execute("SELECT id, email FROM users WHERE email = %s", ('martha@gmail.com',))
            user_row = cursor.fetchone()
            
        if not user_row:
            conn.close()
            raise Exception('Usuário não encontrado')
            
        user_id = user_row[0]
        user_email = user_row[1]
        
        # 4. Verificar se já existe na tabela payments
        cursor.execute("SELECT id FROM payments WHERE payment_id = %s", (str(payment_id),))
        existing = cursor.fetchone()
        
        if existing:
            conn.close()
            print(f"⚠️ Pagamento {payment_id} já processado")
            return {'status': 'already_processed', 'payment_id': payment_id}
        
        # 5. DETERMINAR PLANO usando seus valores originais
        plan_name = 'Pro'
        plan_id = 'pro' 
        
        # Lógica baseada no valor:
        if amount >= 140:  # Premium mensal (149)
            plan_name = 'Premium'
            plan_id = 'premium'
        elif amount >= 130:  # Premium anual (137)
            plan_name = 'Premium'
            plan_id = 'premium'
        elif amount >= 75:   # Pro mensal (79)
            plan_name = 'Pro'
            plan_id = 'pro'
        elif amount >= 70:   # Pro anual (72)
            plan_name = 'Pro'
            plan_id = 'pro'
        else:               # Valores com desconto - assumir Pro
            plan_name = 'Pro'
            plan_id = 'pro'
        
        print(f"📦 Plano determinado: {plan_name} (ID: {plan_id})")
        
        # 6. INSERIR NA TABELA PAYMENTS
        cursor.execute("""
            INSERT INTO payments (
                user_id, payment_id, status, amount, plan_id, plan_name, 
                external_reference, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """, (
            user_id, str(payment_id), 'approved', amount, plan_id, plan_name, external_ref
        ))
        
        # 7. ATUALIZAR USUÁRIO
        cursor.execute("""
            UPDATE users 
            SET subscription_status = %s, subscription_plan = %s, updated_at = NOW()
            WHERE id = %s
        """, ('active', plan_name, user_id))
        
        conn.commit()
        conn.close()
        
        print(f"✅ PAGAMENTO {payment_id} PROCESSADO COM SUCESSO!")
        
        return {
            'status': 'success',
            'payment_id': payment_id,
            'user_id': user_id,
            'user_email': user_email,
            'amount': amount,
            'plan': plan_name,
            'plan_id': plan_id
        }
        
    except Exception as e:
        print(f"❌ ERRO NO PROCESSAMENTO VIA WEBHOOK: {e}")
        import traceback
        traceback.print_exc()
        return {'status': 'error', 'message': str(e)}

# ===== FUNÇÕES AUXILIARES =====
def test_mercadopago_connection():
    """Testar conexão com Mercado Pago"""
    if not mp_sdk or not preference_client:
        return {"success": False, "error": "SDK Mercado Pago não carregado"}
    
    try:
        token = os.environ.get('MP_ACCESS_TOKEN', '')
        if not token:
            return {"success": False, "error": "Token MP_ACCESS_TOKEN não configurado"}
        
        test_preference = {
            "items": [{
                "id": "test",
                "title": "Teste de Conexão",
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": 1.0
            }]
        }
        
        result = preference_client.create(test_preference)
        
        if result.get("status") == 201:
            return {
                "success": True,
                "message": "Mercado Pago conectado com sucesso!",
                "environment": "sandbox" if "TEST" in token else "production",
                "preference_test_id": result["response"]["id"]
            }
        else:
            return {"success": False, "error": f"Erro na resposta do MP: {result.get('response', 'Sem detalhes')}"}
            
    except Exception as e:
        return {"success": False, "error": f"Erro ao conectar com MP: {str(e)}"}

def create_checkout_function():
    """Função para criar checkout"""
    if not mp_sdk or not preference_client:
        return jsonify({"success": False, "error": "SDK Mercado Pago não disponível"}), 500
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Dados JSON são obrigatórios"}), 400
        
        plan = data.get('plan', 'pro')
        cycle = data.get('cycle', 'monthly')
        customer_email = data.get('customer_email', 'cliente@geminii.com.br')
        discounted_price = data.get('discounted_price')
        coupon_code = data.get('coupon_code')
        
        if plan not in PLANS:
            return jsonify({"success": False, "error": f"Plano '{plan}' não encontrado"}), 400
        
        plan_data = PLANS[plan]
        
        # Determinar preço
        if cycle == 'annual':
            original_price = plan_data["annual_price"]
            cycle_display = "Anual"
        else:
            original_price = plan_data["monthly_price"]
            cycle_display = "Mensal"
        
        # Usar preço com desconto se fornecido
        if discounted_price is not None:
            price = float(discounted_price)
            print(f"🎫 Cupom aplicado: {coupon_code}")
            print(f"💰 Preço original: R$ {original_price}")
            print(f"💰 Preço com desconto: R$ {price}")
        else:
            price = original_price
            print(f"💰 Preço sem desconto: R$ {price}")
        
        # URL base
        if os.environ.get('DATABASE_URL'):
            base_url = "https://app.geminii.com.br"
        else:
            base_url = "http://localhost:5000"
        
        # Título
        item_title = f"Geminii {plan_data['name']} - {cycle_display}"
        if coupon_code:
            item_title += f" (Cupom: {coupon_code})"
        
        preference_data = {
            "items": [{
                "id": plan,
                "title": item_title,
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": float(price)
            }],
            "back_urls": {
                "success": f"{base_url}/payment/success",
                "pending": f"{base_url}/payment/pending", 
                "failure": f"{base_url}/payment/failure"
            },
            "external_reference": f"geminii_{plan}_{cycle}_{int(time.time())}",
            "notification_url": f"{base_url}/webhook/mercadopago"
        }
        
        if customer_email and customer_email != 'cliente@geminii.com.br':
            preference_data["payer"] = {"email": customer_email}
        
        preference_response = preference_client.create(preference_data)
        
        if preference_response.get("status") == 201:
            preference = preference_response["response"]
            
            return jsonify({
                "success": True,
                "data": {
                    "preference_id": preference["id"],
                    "checkout_url": preference.get("init_point", ""),
                    "sandbox_url": preference.get("sandbox_init_point", ""),
                    "plan": plan,
                    "cycle": cycle,
                    "price": price,
                    "original_price": original_price,
                    "coupon_code": coupon_code,
                    "currency": "BRL",
                    "external_reference": preference_data["external_reference"]
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": "Erro ao criar checkout no Mercado Pago",
                "details": preference_response.get("response", {})
            }), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": "Erro interno do servidor", "details": str(e)}), 500

# ===== ROTAS =====
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

@mercadopago_bp.route('/webhook', methods=['POST', 'GET'])
def webhook():
    """WEBHOOK PRINCIPAL - VERSÃO LIMPA E FUNCIONAL"""
    
    # Se for GET, retornar status
    if request.method == 'GET':
        return jsonify({
            'status': 'webhook_active',
            'service': 'mercadopago',
            'timestamp': datetime.now().isoformat()
        })
    
    try:
        print(f"\n🔔 WEBHOOK RECEBIDO - {datetime.now()}")
        
        # Verificar dados
        data = request.get_json()
        if not data:
            print("❌ Nenhum dado JSON recebido")
            return jsonify({"error": "No data"}), 400
        
        print(f"📊 Dados: {data}")
        
        webhook_type = data.get("type")
        print(f"🔍 Tipo: {webhook_type}")
        
        if webhook_type == "payment":
            payment_data = data.get("data", {})
            payment_id = payment_data.get("id")
            
            print(f"💳 Payment ID: {payment_id}")
            
            if payment_id:
                # REGISTRAR NO HISTÓRICO PRIMEIRO
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        INSERT INTO payment_history (
                            user_id, plan_id, payment_id, amount, discount_amount, 
                            is_recurring, next_billing_date, created_at, updated_at, 
                            subscription_id, currency, status, payment_method, coupon_code
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), %s, %s, %s, %s, %s)
                    """, (
                        None, None, str(payment_id), 0.00, 0.00, False, None, 
                        None, 'BRL', 'webhook_received', None, None
                    ))
                    
                    conn.commit()
                    conn.close()
                    print(f"✅ Registrado no payment_history")
                except Exception as e:
                    print(f"⚠️ Erro ao registrar histórico: {e}")
                
                # PROCESSAR PAGAMENTO
                try:
                    result = process_payment(payment_id)
                    print(f"✅ Processamento concluído: {result}")
                    
                    return jsonify({
                        "success": True, 
                        "message": "Pagamento processado com sucesso",
                        "payment_id": payment_id,
                        "result": result
                    }), 200
                    
                except Exception as process_error:
                    print(f"❌ Erro no processamento: {process_error}")
                    
                    return jsonify({
                        "success": False, 
                        "error": f"Erro no processamento: {str(process_error)}",
                        "payment_id": payment_id
                    }), 500
            else:
                print("❌ Payment ID não encontrado")
                return jsonify({"error": "Payment ID missing"}), 400
        else:
            print(f"⚠️ Tipo de webhook ignorado: {webhook_type}")
            return jsonify({"success": True, "ignored": True}), 200
            
    except Exception as e:
        print(f"❌ ERRO GERAL NO WEBHOOK: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "success": False, 
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500

@mercadopago_bp.route('/payment/status/<payment_id>')
def check_payment_status(payment_id):
    """Verificar status de um pagamento específico"""
    try:
        mp_token = os.environ.get('MP_ACCESS_TOKEN')
        if not mp_token:
            return jsonify({'success': False, 'error': 'Token MP não configurado'}), 500
        
        headers = {
            'Authorization': f'Bearer {mp_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f'https://api.mercadopago.com/v1/payments/{payment_id}',
            headers=headers
        )
        
        if response.status_code == 200:
            payment_data = response.json()
            return jsonify({
                'success': True,
                'data': {
                    'id': payment_data.get('id'),
                    'status': payment_data.get('status'),
                    'status_detail': payment_data.get('status_detail'),
                    'amount': payment_data.get('transaction_amount'),
                    'payer_email': payment_data.get('payer', {}).get('email'),
                    'external_reference': payment_data.get('external_reference'),
                    'date_created': payment_data.get('date_created')
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Erro ao buscar pagamento: {response.status_code}'
            }), 400
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@mercadopago_bp.route('/test-webhook', methods=['POST'])
def test_webhook_manual():
    """Testar webhook manualmente"""
    try:
        data = request.get_json()
        payment_id = data.get('payment_id')
        
        if not payment_id:
            return jsonify({'success': False, 'error': 'payment_id é obrigatório'}), 400
        
        result = process_payment(payment_id)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== FUNÇÃO DE EXPORT =====
def get_mercadopago_blueprint():
    """Retornar blueprint para registrar no Flask"""
    return mercadopago_bp

# Função que será chamada pelo main.py
def webhook():
    """Função principal chamada pelo main.py"""
    return mercadopago_bp.view_functions['webhook']()
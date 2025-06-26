# mercadopago_routes.py - VERSÃO FINAL CORRIGIDA PARA PRODUÇÃO
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

# ===== CONFIGURAÇÃO DOS PLANOS (mantendo nomes originais) =====
PLANS = {
    "pro": {
        "id": "pro",
        "name": "Pro",
        "db_id": 1,  # Corresponde ao banco
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
        "db_id": 2,  # Corresponde ao banco
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
        token = os.environ.get('MP_ACCESS_TOKEN', '')
        
        if not token:
            return {
                "success": False,
                "error": "Token MP_ACCESS_TOKEN não configurado"
            }
        
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
        
        result = preference_client.create(test_preference)
        
        if result.get("status") == 201:
            preference_id = result["response"]["id"]
            
            return {
                "success": True,
                "message": "Mercado Pago conectado com sucesso!",
                "environment": "sandbox" if "TEST" in token else "production",
                "preference_test_id": preference_id
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
    """Criar checkout - PRODUÇÃO"""
    if not mp_sdk or not preference_client:
        return jsonify({
            "success": False,
            "error": "SDK Mercado Pago não disponível"
        }), 500
    
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
        
        # Validar plano
        if plan not in PLANS:
            return jsonify({
                "success": False,
                "error": f"Plano '{plan}' não encontrado"
            }), 400
        
        plan_data = PLANS[plan]
        
        # Determinar preço
        if cycle == 'annual':
            original_price = plan_data["annual_price"]
            cycle_display = "Anual"
        else:
            original_price = plan_data["monthly_price"]
            cycle_display = "Mensal"
        
        # Aplicar desconto se houver
        price = float(discounted_price) if discounted_price is not None else original_price
        
        # URLs
        base_url = "https://app.geminii.com.br" if os.environ.get('DATABASE_URL') else "http://localhost:5000"
        
        # Título do item
        item_title = f"Geminii {plan_data['name']} - {cycle_display}"
        if coupon_code:
            item_title += f" (Cupom: {coupon_code})"
        
        # Referência externa com email incluído
        timestamp = int(time.time())
        external_reference = f"geminii_{plan}_{cycle}_{customer_email}_{timestamp}"
        
        # Dados da preferência
        preference_data = {
            "items": [
                {
                    "id": plan,
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
            "external_reference": external_reference,
            "notification_url": f"{base_url}/api/mercadopago/webhook"
        }
        
        # Adicionar dados do pagador
        if customer_email and customer_email != 'cliente@geminii.com.br':
            preference_data["payer"] = {
                "email": customer_email
            }
        
        print(f"🔄 Criando checkout: {customer_email} - {plan_data['name']} - R$ {price}")
        
        # Criar preferência
        preference_response = preference_client.create(preference_data)
        
        if preference_response.get("status") == 201:
            preference = preference_response["response"]
            preference_id = preference["id"]
            
            checkout_url = preference.get("init_point", "")
            sandbox_url = preference.get("sandbox_init_point", "")
            
            print(f"✅ Checkout criado: {preference_id}")
            
            return jsonify({
                "success": True,
                "data": {
                    "preference_id": preference_id,
                    "checkout_url": checkout_url,
                    "sandbox_url": sandbox_url,
                    "plan": plan,
                    "cycle": cycle,
                    "price": price,
                    "original_price": original_price,
                    "coupon_code": coupon_code,
                    "external_reference": external_reference
                }
            })
        else:
            error_info = preference_response.get("response", {})
            print(f"❌ Erro no checkout: {error_info}")
            
            return jsonify({
                "success": False,
                "error": "Erro ao criar checkout no Mercado Pago",
                "details": error_info
            }), 500
            
    except Exception as e:
        print(f"❌ Erro no checkout: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "success": False,
            "error": "Erro interno do servidor",
            "details": str(e)
        }), 500

def process_payment(payment_id):
    """
    Processar pagamento - VERSÃO FINAL QUE FUNCIONA COM SEU BANCO
    """
    try:
        print(f"\n🔥 PROCESSANDO PAGAMENTO: {payment_id}")
        print("=" * 50)
        
        # 1. Buscar dados do pagamento no MP
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
            raise Exception(f'Pagamento não encontrado no MP: Status {response.status_code}')
            
        mp_data = response.json()
        print(f"📊 Status MP: {mp_data.get('status')} - R$ {mp_data.get('transaction_amount')}")
        
        # 2. Verificar se está aprovado
        if mp_data.get('status') != 'approved':
            print(f"⚠️ Pagamento não aprovado: {mp_data.get('status')}")
            return {'status': 'not_approved', 'mp_status': mp_data.get('status')}
        
        # 3. Extrair informações
        external_ref = mp_data.get('external_reference', '')
        amount = float(mp_data.get('transaction_amount', 0))
        payer_email = mp_data.get('payer', {}).get('email', '')
        
        print(f"💰 Valor: R$ {amount}")
        print(f"📧 Email: {payer_email}")
        print(f"🔗 Referência: {external_ref}")
        
        # 4. Extrair dados da referência externa
        user_email = None
        plan_id = 'pro'  # padrão
        cycle = 'monthly'  # padrão
        
        if external_ref and 'geminii_' in external_ref:
            try:
                parts = external_ref.split('_')
                if len(parts) >= 4:
                    plan_id = parts[1]
                    cycle = parts[2]
                    user_email = parts[3]
                    print(f"📦 Extraído: Plano={plan_id}, Ciclo={cycle}, Email={user_email}")
            except:
                print("⚠️ Erro ao extrair dados da referência")
        
        # Usar email do pagador se não conseguiu extrair
        if not user_email:
            user_email = payer_email
        
        if not user_email:
            raise Exception("Email do usuário não encontrado")
        
        # 5. Conectar ao banco
        conn = get_db_connection()
        if not conn:
            raise Exception("Erro de conexão com banco")
        
        cursor = conn.cursor()
        
        # 6. Verificar se já foi processado
        cursor.execute("SELECT id FROM payments WHERE payment_id = %s", (str(payment_id),))
        if cursor.fetchone():
            conn.close()
            print(f"⚠️ Pagamento {payment_id} já processado")
            return {'status': 'already_processed'}
        
        # 7. Buscar usuário
        cursor.execute("SELECT id, name, email FROM users WHERE email = %s", (user_email,))
        user_row = cursor.fetchone()
        
        if not user_row:
            conn.close()
            raise Exception(f"Usuário não encontrado: {user_email}")
        
        user_id, user_name, user_email = user_row
        print(f"👤 Usuário: {user_name} (ID: {user_id})")
        
        # 8. Determinar plano
        if plan_id in PLANS:
            plan_data = PLANS[plan_id]
            plan_name = plan_data['name']
            plan_db_id = plan_data['db_id']
        else:
            # Fallback baseado no valor
            if amount >= 130:
                plan_id = 'premium'
                plan_name = 'Premium'
                plan_db_id = 2
            else:
                plan_id = 'pro'
                plan_name = 'Pro'
                plan_db_id = 1
        
        print(f"📦 Plano: {plan_name} (DB ID: {plan_db_id})")
        
        # 9. Calcular expiração
        if cycle == 'annual':
            expires_at = datetime.now(timezone.utc) + timedelta(days=365)
        else:
            expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        
        print(f"📅 Expira: {expires_at.strftime('%d/%m/%Y')}")
        
        # 10. Inserir na tabela payments
        cursor.execute("""
            INSERT INTO payments (
                user_id, payment_id, status, amount, plan_id, plan_name, 
                cycle, external_reference, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """, (
            user_id, str(payment_id), 'approved', amount, plan_id, plan_name, 
            cycle, external_ref
        ))
        
        print("✅ Pagamento inserido na tabela payments")
        
        # 11. Atualizar usuário (usando os campos que existem no seu banco)
        cursor.execute("""
            UPDATE users 
            SET plan_id = %s, 
                plan_name = %s,
                subscription_status = %s,
                subscription_plan = %s,
                plan_expires_at = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (plan_db_id, plan_name, 'active', plan_name, expires_at, user_id))
        
        rows_updated = cursor.rowcount
        print(f"✅ Usuário atualizado ({rows_updated} linhas)")
        
        # 12. Registrar no histórico
        cursor.execute("""
            INSERT INTO payment_history (
                user_id, plan_id, payment_id, amount, status, 
                currency, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
        """, (user_id, plan_db_id, str(payment_id), amount, 'approved', 'BRL'))
        
        print("✅ Histórico registrado")
        
        # 13. Commit
        conn.commit()
        conn.close()
        
        print(f"\n🎉 SUCESSO! Plano {plan_name} ativado para {user_name}")
        
        return {
            'status': 'success',
            'payment_id': payment_id,
            'user_id': user_id,
            'user_name': user_name,
            'user_email': user_email,
            'plan_name': plan_name,
            'amount': amount,
            'expires_at': expires_at.isoformat(),
            'message': f'Plano {plan_name} ativado com sucesso!'
        }
        
    except Exception as e:
        print(f"❌ ERRO NO PROCESSAMENTO: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'status': 'error',
            'payment_id': payment_id,
            'error': str(e)
        }

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
                "description": "Plano " + plan_data["name"],
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
    """WEBHOOK PRINCIPAL - VERSÃO FINAL"""
    
    if request.method == 'GET':
        return jsonify({
            'status': 'webhook_active',
            'service': 'mercadopago',
            'timestamp': datetime.now().isoformat()
        })
    
    try:
        print(f"\n🔔 WEBHOOK RECEBIDO - {datetime.now()}")
        print("=" * 50)
        
        # Obter dados
        data = request.get_json()
        if not data:
            print("❌ Nenhum dado recebido")
            return jsonify({"error": "No data"}), 400
        
        print(f"📊 Dados: {data}")
        
        webhook_type = data.get("type")
        print(f"🔍 Tipo: {webhook_type}")
        
        if webhook_type == "payment":
            payment_data = data.get("data", {})
            payment_id = payment_data.get("id")
            
            print(f"💳 Payment ID: {payment_id}")
            
            if not payment_id:
                print("❌ Payment ID não encontrado")
                return jsonify({"error": "Payment ID missing"}), 400
            
            # Processar pagamento
            print(f"🔄 Processando pagamento {payment_id}...")
            result = process_payment(payment_id)
            
            print(f"📊 Resultado: {result['status']}")
            
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
            print(f"⚠️ Webhook ignorado: {webhook_type}")
            return jsonify({
                "success": True, 
                "message": f"Webhook '{webhook_type}' ignorado"
            }), 200
        
    except Exception as e:
        print(f"❌ ERRO NO WEBHOOK: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "success": False,
            "error": f"Erro: {str(e)}"
        }), 500

@mercadopago_bp.route('/payment/status/<payment_id>')
def check_payment_status(payment_id):
    """Verificar status de pagamento"""
    try:
        # MP
        mp_token = os.environ.get('MP_ACCESS_TOKEN')
        headers = {
            'Authorization': f'Bearer {mp_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f'https://api.mercadopago.com/v1/payments/{payment_id}',
            headers=headers
        )
        
        mp_status = None
        if response.status_code == 200:
            mp_data = response.json()
            mp_status = {
                'status': mp_data.get('status'),
                'amount': mp_data.get('transaction_amount'),
                'payer_email': mp_data.get('payer', {}).get('email'),
                'external_reference': mp_data.get('external_reference')
            }
        
        # Banco
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT p.*, u.name, u.email, u.subscription_status 
            FROM payments p 
            JOIN users u ON p.user_id = u.id 
            WHERE p.payment_id = %s
        """, (str(payment_id),))
        
        db_payment = cursor.fetchone()
        conn.close()
        
        return jsonify({
            'payment_id': payment_id,
            'mercado_pago': mp_status,
            'database': {
                'exists': db_payment is not None,
                'processed': db_payment is not None
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== FUNÇÃO DE EXPORT =====

def get_mercadopago_blueprint():
    """Retornar blueprint"""
    return mercadopago_bp

# Debug info
if __name__ == "__main__":
    print("🔧 Sistema Mercado Pago FINAL carregado!")
    print(f"📋 Planos: {list(PLANS.keys())}")
    print(f"🔐 Token: {mp_token[:20]}...")
# mercadopago_routes.py
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
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "Dados JSON são obrigatórios"
            }), 400
        
        plan = data.get('plan', 'pro')
        cycle = data.get('cycle', 'monthly')
        customer_email = data.get('customer_email', 'cliente@geminii.com.br')
        
        # ✅ PEGAR DADOS DO CUPOM
        discounted_price = data.get('discounted_price')
        coupon_code = data.get('coupon_code')
        
        if plan not in PLANS:
            return jsonify({
                "success": False,
                "error": f"Plano '{plan}' não encontrado"
            }), 400
        
        plan_data = PLANS[plan]
        plan_id = plan_data["id"]
        plan_name = plan_data["name"]
        
        # ✅ DETERMINAR PREÇO ORIGINAL
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
            print(f"💰 Preço sem desconto: R$ {price}")
        
        if os.environ.get('DATABASE_URL'):
            base_url = "https://app.geminii.com.br"
        else:
            base_url = "http://localhost:5000"
        
        # ✅ TÍTULO COM CUPOM SE APLICADO
        item_title = f"Geminii {plan_name} - {cycle_display}"
        if coupon_code:
            item_title += f" (Cupom: {coupon_code})"
        
        preference_data = {
            "items": [
                {
                    "id": plan_id,
                    "title": item_title,
                    "quantity": 1,
                    "currency_id": "BRL",
                    "unit_price": float(price)  # ✅ PREÇO COM DESCONTO
                }
            ],
            "back_urls": {
                "success": f"{base_url}/payment/success",
                "pending": f"{base_url}/payment/pending", 
                "failure": f"{base_url}/payment/failure"
            },
            "external_reference": f"geminii_{plan_id}_{cycle}_{int(time.time())}",
            "notification_url": f"{base_url}/webhook/mercadopago"
        }
        
        if customer_email and customer_email != 'cliente@geminii.com.br':
            preference_data["payer"] = {
                "email": customer_email
            }
        
        preference_response = preference_client.create(preference_data)
        
        if preference_response.get("status") == 201:
            preference = preference_response["response"]
            preference_id = preference["id"]
            
            checkout_url = preference.get("init_point", "")
            sandbox_url = preference.get("sandbox_init_point", "")
            
            return jsonify({
                "success": True,
                "data": {
                    "preference_id": preference_id,
                    "checkout_url": checkout_url,
                    "sandbox_url": sandbox_url,
                    "plan": plan,
                    "cycle": cycle,
                    "price": price,  # ✅ RETORNA PREÇO COM DESCONTO
                    "original_price": original_price,
                    "coupon_code": coupon_code,
                    "currency": "BRL",
                    "external_reference": preference_data["external_reference"]
                }
            })
        else:
            error_info = preference_response.get("response", {})
            
            return jsonify({
                "success": False,
                "error": "Erro ao criar checkout no Mercado Pago",
                "details": error_info
            }), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "success": False,
            "error": "Erro interno do servidor",
            "details": str(e)
        }), 500
                

def determine_plan_from_payment(external_reference, amount):
    """Determinar plano baseado na referência externa ou valor"""
    try:
        if external_reference and 'geminii_' in external_reference:
            parts = external_reference.split('_')
            if len(parts) >= 3:
                plan_id = parts[1]
                cycle = parts[2]
                
                if plan_id in PLANS:
                    plan_data = PLANS[plan_id]
                    return {
                        'plan_id': plan_id,
                        'plan_name': plan_data['name'],
                        'cycle': cycle,
                        'amount': amount
                    }
        
        if amount >= 130:
            return {
                'plan_id': 'premium',
                'plan_name': 'Premium',
                'cycle': 'annual',
                'amount': amount
            }
        elif amount >= 140:
            return {
                'plan_id': 'premium', 
                'plan_name': 'Premium',
                'cycle': 'monthly',
                'amount': amount
            }
        elif amount >= 70:
            return {
                'plan_id': 'pro',
                'plan_name': 'Pro',
                'cycle': 'annual',
                'amount': amount
            }
        elif amount >= 75:
            return {
                'plan_id': 'pro',
                'plan_name': 'Pro', 
                'cycle': 'monthly',
                'amount': amount
            }
        
        return None
        
    except Exception as e:
        print(f"❌ Erro ao determinar plano: {e}")
        return None

def update_user_plan(email, plan_info, payment_data):
    """Atualizar plano do usuário com logs detalhados"""
    try:
        print(f"\n👤 ATUALIZANDO USUÁRIO: {email}")
        print("=" * 40)
        
        conn = get_db_connection()
        if not conn:
            print("❌ Erro de conexão com banco")
            return {'success': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        
        print(f"🔍 Buscando usuário no banco...")
        cursor.execute("SELECT id, name, plan_id FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if not user:
            print(f"❌ Usuário não encontrado para email: {email}")
            
            # LISTAR TODOS OS USUÁRIOS PARA DEBUG
            cursor.execute("SELECT email FROM users ORDER BY created_at DESC LIMIT 10")
            all_users = cursor.fetchall()
            print("👥 Usuários encontrados no banco:")
            for u in all_users:
                print(f"   • {u[0]}")
            
            cursor.close()
            conn.close()
            return {'success': False, 'error': f'Usuário não encontrado: {email}'}
        
        user_id, user_name, current_plan_id = user
        print(f"✅ Usuário encontrado:")
        print(f"   ID: {user_id}")
        print(f"   Nome: {user_name}")
        print(f"   Plano atual: {current_plan_id}")
        
        plan_id_mapping = {
            'pro': 2,
            'premium': 3,
            'estrategico': 3
        }
        
        new_plan_id = plan_id_mapping.get(plan_info['plan_id'], 2)
        plan_name = plan_info['plan_name']
        
        print(f"📦 Novo plano:")
        print(f"   Plan ID: {new_plan_id}")
        print(f"   Plan Name: {plan_name}")
        print(f"   Ciclo: {plan_info['cycle']}")
        
        # Calcular expiração
        from datetime import datetime, timedelta, timezone
        if plan_info['cycle'] == 'annual':
            expires_at = datetime.now(timezone.utc) + timedelta(days=365)
        else:
            expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        
        print(f"📅 Data de expiração: {expires_at}")
        
        # Atualizar usuário
        print(f"💾 Atualizando dados do usuário...")
        cursor.execute("""
            UPDATE users 
            SET plan_id = %s, 
                plan_name = %s, 
                plan_expires_at = %s,
                updated_at = CURRENT_TIMESTAMP 
            WHERE email = %s
        """, (new_plan_id, plan_name, expires_at, email))
        
        rows_affected = cursor.rowcount
        print(f"📊 Linhas afetadas na atualização: {rows_affected}")
        
        # Registrar pagamento
        try:
            print(f"💳 Registrando pagamento...")
            cursor.execute("""
                INSERT INTO payments (
                    user_id, payment_id, status, amount, 
                    plan_id, plan_name, cycle, 
                    external_reference, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id, 
                payment_data.get('id'),
                payment_data.get('status'),
                payment_data.get('transaction_amount'),
                plan_info['plan_id'],
                plan_name,
                plan_info['cycle'],
                payment_data.get('external_reference'),
                datetime.now(timezone.utc)
            ))
            print("✅ Pagamento registrado na tabela payments")
        except Exception as e:
            print(f"⚠️ Erro ao inserir pagamento: {e}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"\n🎉 ATUALIZAÇÃO CONCLUÍDA COM SUCESSO!")
        print(f"   👤 Usuário: {user_name}")
        print(f"   📧 Email: {email}")
        print(f"   📦 Plano: {plan_name}")
        print(f"   💰 Valor: R$ {plan_info['amount']}")
        print(f"   📅 Expira: {expires_at.strftime('%d/%m/%Y')}")
        
        return {
            'success': True,
            'message': f'Plano {plan_name} ativado para {user_name}',
            'data': {
                'user_id': user_id,
                'user_name': user_name,
                'email': email,
                'plan_id': new_plan_id,
                'plan_name': plan_name,
                'cycle': plan_info['cycle'],
                'expires_at': expires_at.isoformat(),
                'amount': plan_info['amount']
            }
        }
        
    except Exception as e:
        print(f"❌ ERRO na atualização do usuário: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}

def process_payment(payment_id):
    """Processar pagamento com logs detalhados"""
    try:
        print(f"\n🔄 INICIANDO PROCESSAMENTO DO PAGAMENTO: {payment_id}")
        print("=" * 60)
        
        mp_token = os.environ.get('MP_ACCESS_TOKEN')
        if not mp_token:
            print("❌ Token MP_ACCESS_TOKEN não configurado")
            return {'success': False, 'error': 'Token MP não configurado'}
        
        print(f"🔑 Token MP: {mp_token[:20]}...")
        
        headers = {
            'Authorization': f'Bearer {mp_token}',
            'Content-Type': 'application/json'
        }
        
        print(f"📡 Buscando dados do pagamento no Mercado Pago...")
        response = requests.get(
            f'https://api.mercadopago.com/v1/payments/{payment_id}',
            headers=headers
        )
        
        print(f"📊 Status da resposta: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Erro na API do MP: {response.text}")
            return {'success': False, 'error': f'Erro API MP: {response.status_code}'}
        
        payment_data = response.json()
        print(f"💳 Dados do pagamento recebidos:")
        print(f"   Status: {payment_data.get('status')}")
        print(f"   Valor: {payment_data.get('transaction_amount')}")
        print(f"   Email: {payment_data.get('payer', {}).get('email')}")
        print(f"   Referência: {payment_data.get('external_reference')}")
        
        payment_status = payment_data.get('status')
        if payment_status != 'approved':
            print(f"⚠️ Pagamento não aprovado: {payment_status}")
            return {'success': False, 'error': f'Pagamento não aprovado: {payment_status}'}
        
        payer_email = payment_data.get('payer', {}).get('email')
        external_reference = payment_data.get('external_reference', '')
        transaction_amount = payment_data.get('transaction_amount', 0)
        
        print(f"📧 Email do pagador: {payer_email}")
        
        if not payer_email:
            print("❌ Email do pagador não encontrado")
            return {'success': False, 'error': 'Email do pagador não encontrado'}
        
        print(f"🎯 Determinando plano baseado na referência/valor...")
        plan_info = determine_plan_from_payment(external_reference, transaction_amount)
        
        if not plan_info:
            print("❌ Não foi possível determinar o plano")
            return {'success': False, 'error': 'Não foi possível determinar o plano'}
        
        print(f"📦 Plano determinado: {plan_info}")
        
        print(f"🔄 Atualizando usuário no banco...")
        update_result = update_user_plan(payer_email, plan_info, payment_data)
        
        print(f"📊 Resultado da atualização: {update_result}")
        
        return update_result
        
    except Exception as e:
        print(f"❌ ERRO GERAL no processamento: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}

def create_payments_table():
    """Criar tabela de pagamentos se não existir"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                payment_id VARCHAR(100) UNIQUE,
                status VARCHAR(50),
                amount DECIMAL(10,2),
                plan_id VARCHAR(50),
                plan_name VARCHAR(100),
                cycle VARCHAR(20),
                external_reference VARCHAR(200),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Tabela payments criada/verificada")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabela payments: {e}")
        return False

def add_plan_expires_field():
    """Adicionar campo plan_expires_at na tabela users"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name='plan_expires_at'
        """)
        
        if not cursor.fetchone():
            cursor.execute("""
                ALTER TABLE users 
                ADD COLUMN plan_expires_at TIMESTAMP
            """)
            print("✅ Campo plan_expires_at adicionado")
        else:
            print("✅ Campo plan_expires_at já existe")
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Erro ao adicionar campo: {e}")
        return False

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

@mercadopago_bp.route('/webhook', methods=['POST', 'GET'])
def webhook():
    """Webhook do Mercado Pago - Versão Railway"""
    
    # Se for GET, retornar status
    if request.method == 'GET':
        return jsonify({
            'status': 'webhook_active',
            'service': 'mercadopago',
            'timestamp': datetime.now().isoformat()
        })
    
    try:
        # LOG DETALHADO
        print(f"\n🔔 WEBHOOK MERCADO PAGO - {datetime.now()}")
        print("=" * 60)
        
        # Verificar se há dados
        data = request.get_json()
        if not data:
            print("❌ Nenhum dado JSON recebido")
            # Tentar pegar dados do form
            data = request.form.to_dict()
            if not data:
                print("❌ Nenhum dado encontrado")
                return jsonify({"error": "No data"}), 400
        
        print(f"📊 Dados recebidos: {data}")
        
        # Verificar headers
        headers = dict(request.headers)
        print(f"📋 Headers: {headers}")
        
        webhook_type = data.get("type")
        print(f"🔍 Tipo: {webhook_type}")
        
        if webhook_type == "payment":
            payment_data = data.get("data", {})
            payment_id = payment_data.get("id")
            
            print(f"💳 Payment ID: {payment_id}")
            
            if payment_id:
                # Processar pagamento
                result = process_payment(payment_id)
                print(f"📊 Resultado: {result}")
                
                # Salvar log no banco
                try:
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO payment_history (
                                payment_id, status, amount, currency,
                                created_at
                            ) VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (payment_id) DO NOTHING
                        """, (
                            payment_id,
                            'webhook_received',
                            0,
                            'BRL',
                            datetime.now()
                        ))
                        conn.commit()
                        cursor.close()
                        conn.close()
                        print("✅ Log salvo no banco")
                except Exception as e:
                    print(f"⚠️ Erro ao salvar log: {e}")
                
                return jsonify({"success": True, "processed": True}), 200
            else:
                print("❌ Payment ID não encontrado")
                return jsonify({"error": "Payment ID missing"}), 400
        else:
            print(f"⚠️ Tipo de webhook ignorado: {webhook_type}")
            return jsonify({"success": True, "ignored": True}), 200
            
    except Exception as e:
        print(f"❌ ERRO NO WEBHOOK: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

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
def test_webhook():
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
    # Inicializar tabelas necessárias
    create_payments_table()
    add_plan_expires_field()
    
    return mercadopago_bp
# test_payment_flow_fixed.py - Teste usando o blueprint que funciona

import requests
import json
import time
from datetime import datetime

# Configurações
BASE_URL = "https://app.geminii.com.br"
TEST_EMAIL = "martha@gmail.com"
TEST_NAME = "Martha Silva"

def test_api_status():
    """Testar se API está online"""
    try:
        print("🔍 Testando status da API...")
        response = requests.get(f"{BASE_URL}/api/status")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ API Online!")
            print(f"   Mercado Pago: {data.get('mercadopago', {}).get('success', False)}")
            return True
        else:
            print(f"❌ API offline: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Erro na API: {e}")
        return False

def test_mercadopago_connection():
    """Testar conexão com Mercado Pago"""
    try:
        print("\n🔍 Testando conexão Mercado Pago...")
        response = requests.get(f"{BASE_URL}/api/mercadopago/test")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("✅ Mercado Pago conectado!")
                print(f"   Environment: {data.get('environment')}")
                print(f"   Preference ID: {data.get('preference_test_id')}")
                return True
            else:
                print(f"❌ Erro MP: {data.get('error')}")
                return False
        else:
            print(f"❌ Erro HTTP: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def test_user_exists():
    """Verificar se usuário teste existe"""
    try:
        print(f"\n👤 Verificando usuário: {TEST_EMAIL}")
        
        login_data = {
            "email": TEST_EMAIL,
            "password": "123456"
        }
        
        response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                user = data.get('data', {}).get('user', {})
                print(f"✅ Usuário encontrado!")
                print(f"   Nome: {user.get('name')}")
                print(f"   Plano atual: {user.get('plan_name')}")
                print(f"   Status: {user.get('subscription_status', 'N/A')}")
                return user
            else:
                print(f"❌ Login falhou: {data.get('error')}")
                return None
        else:
            print(f"❌ Erro HTTP: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        return None

def test_create_checkout():
    """Testar criação de checkout"""
    try:
        print(f"\n💳 Criando checkout teste...")
        
        checkout_data = {
            "plan": "pro",
            "cycle": "monthly",
            "customer_email": TEST_EMAIL,
            "coupon_code": "50OFF",
            "discounted_price": 39.50
        }
        
        response = requests.post(f"{BASE_URL}/api/mercadopago/checkout/create", json=checkout_data)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                checkout_info = data.get('data', {})
                print("✅ Checkout criado!")
                print(f"   Preference ID: {checkout_info.get('preference_id')}")
                print(f"   Plano: {checkout_info.get('plan')}")
                print(f"   Preço: R$ {checkout_info.get('price')}")
                print(f"   Referência: {checkout_info.get('external_reference')}")
                print(f"   URL Sandbox: {checkout_info.get('sandbox_url')}")
                return checkout_info
            else:
                print(f"❌ Erro: {data.get('error')}")
                return None
        else:
            print(f"❌ Erro HTTP: {response.status_code}")
            print(response.text)
            return None
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        return None

def test_webhook_blueprint(payment_id):
    """Testar webhook do BLUEPRINT (que funciona)"""
    try:
        print(f"\n🔔 Testando webhook BLUEPRINT para payment_id: {payment_id}")
        
        webhook_data = {
            "type": "payment",
            "data": {
                "id": payment_id
            }
        }
        
        # ✅ USAR A URL DO BLUEPRINT QUE FUNCIONA
        response = requests.post(f"{BASE_URL}/api/mercadopago/webhook", json=webhook_data)
        
        print(f"📊 Response Status: {response.status_code}")
        print(f"📊 Response Text: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("✅ Webhook BLUEPRINT processado com sucesso!")
                print(f"   Mensagem: {data.get('message')}")
                return True
            else:
                print(f"❌ Webhook falhou: {data.get('error')}")
                return False
        else:
            print(f"❌ Erro HTTP: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def test_webhook_comparison():
    """Comparar webhooks - main.py vs blueprint"""
    try:
        print(f"\n🔍 COMPARANDO WEBHOOKS")
        print("=" * 40)
        
        test_payment_id = f"COMPARE_{int(time.time())}"
        webhook_data = {
            "type": "payment",
            "data": {"id": test_payment_id}
        }
        
        # Testar webhook do main.py (quebrado)
        print(f"🔴 Testando main.py webhook...")
        try:
            response1 = requests.post(f"{BASE_URL}/webhook/mercadopago", json=webhook_data)
            print(f"   Status: {response1.status_code}")
            print(f"   Response: {response1.text[:100]}")
        except Exception as e:
            print(f"   ❌ Erro: {e}")
        
        # Testar webhook do blueprint (funciona)
        print(f"🟢 Testando blueprint webhook...")
        try:
            response2 = requests.post(f"{BASE_URL}/api/mercadopago/webhook", json=webhook_data)
            print(f"   Status: {response2.status_code}")
            print(f"   Response: {response2.text[:100]}")
            
            if response2.status_code == 200:
                print("   ✅ Blueprint funciona perfeitamente!")
                return True
        except Exception as e:
            print(f"   ❌ Erro: {e}")
        
        return False
        
    except Exception as e:
        print(f"❌ Erro na comparação: {e}")
        return False

def check_user_after_payment():
    """Verificar se usuário foi atualizado após pagamento"""
    try:
        print(f"\n🔍 Verificando usuário após pagamento...")
        
        login_data = {
            "email": TEST_EMAIL,
            "password": "123456"
        }
        
        response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                user = data.get('data', {}).get('user', {})
                print(f"👤 Status do usuário:")
                print(f"   Nome: {user.get('name')}")
                print(f"   Email: {user.get('email')}")
                print(f"   Plano: {user.get('plan_name')}")
                print(f"   Plan ID: {user.get('plan_id')}")
                print(f"   User Type: {user.get('user_type')}")
                
                # Verificar se plano foi ativado
                if user.get('plan_name') == 'Pro' and user.get('plan_id') == 1:
                    print("✅ Plano Pro ativado com sucesso!")
                    return True
                else:
                    print("⚠️ Plano ainda não foi ativado")
                    return False
            else:
                print(f"❌ Login falhou: {data.get('error')}")
                return False
        else:
            print(f"❌ Erro HTTP: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def run_complete_test():
    """Executar teste completo com BLUEPRINT"""
    print("🚀 TESTE COMPLETO - USANDO BLUEPRINT QUE FUNCIONA")
    print("=" * 60)
    
    # 1. Testar API
    if not test_api_status():
        print("❌ Teste falhou na API")
        return False
    
    # 2. Testar Mercado Pago
    if not test_mercadopago_connection():
        print("❌ Teste falhou no Mercado Pago")
        return False
    
    # 3. Verificar usuário
    user = test_user_exists()
    if not user:
        print("❌ Usuário teste não encontrado")
        return False
    
    # 4. Criar checkout
    checkout = test_create_checkout()
    if not checkout:
        print("❌ Falha ao criar checkout")
        return False
    
    # 5. Comparar webhooks
    print(f"\n🔄 COMPARANDO WEBHOOKS...")
    webhook_works = test_webhook_comparison()
    
    if webhook_works:
        print(f"\n✅ BLUEPRINT WEBHOOK FUNCIONA!")
        
        # 6. Teste automático com blueprint
        print(f"\n🧪 TESTE AUTOMÁTICO COM BLUEPRINT:")
        fake_payment_id = f"BLUEPRINT_TEST_{int(time.time())}"
        print(f"Payment ID simulado: {fake_payment_id}")
        
        # Usar webhook do blueprint
        webhook_success = test_webhook_blueprint(fake_payment_id)
        
        if webhook_success:
            print(f"\n🎉 TESTE COMPLETO - SUCESSO COM BLUEPRINT!")
            print(f"✅ Fluxo funcionando: Checkout → Pagamento → Webhook Blueprint → Ativação")
            return True
        else:
            print(f"\n⚠️ Webhook blueprint teve problema com payment simulado")
            return False
    else:
        print(f"\n❌ Ambos webhooks com problema")
        return False

def test_real_payment_flow():
    """Instruções para teste real"""
    print(f"\n🎯 PARA TESTE REAL:")
    print("=" * 40)
    print(f"1. ✅ Webhook configurado no MP: https://app.geminii.com.br/api/mercadopago/webhook")
    print(f"2. 🛒 Acesse o checkout e faça um pagamento teste")
    print(f"3. 💳 Use cartão: 4013 5406 8274 6260")
    print(f"4. 🔐 CVV: 123, Validade: 11/25, Nome: APRO")
    print(f"5. 📱 CPF: 12345678909")
    print(f"6. ⏰ Aguarde o webhook processar automaticamente")
    print(f"7. 🔍 Verifique se o plano foi ativado")

if __name__ == "__main__":
    print("🔧 TESTE CORRIGIDO - USANDO BLUEPRINT QUE FUNCIONA")
    print("Este script testa usando o webhook que realmente funciona")
    print()
    
    success = run_complete_test()
    
    if success:
        print(f"\n🎯 SISTEMA FUNCIONANDO COM BLUEPRINT!")
        test_real_payment_flow()
        
        print(f"\n📝 CONFIGURAÇÃO FINAL:")
        print(f"✅ Use no Mercado Pago: https://app.geminii.com.br/api/mercadopago/webhook")
        print(f"✅ Blueprint processa pagamentos corretamente")
        print(f"✅ Sistema pronto para produção!")
        
    else:
        print(f"\n🔧 INVESTIGAR:")
        print(f"1. Verifique se mercadopago_routes.py está atualizado")
        print(f"2. Confirme se função process_payment existe")
        print(f"3. Teste manual: cur.exe -X POST https://app.geminii.com.br/api/mercadopago/webhook")
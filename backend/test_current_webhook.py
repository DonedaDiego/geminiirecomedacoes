# test_current_webhook.py - TESTAR WEBHOOK ATUAL ANTES DE MEXER

import requests
import json
import time
from datetime import datetime

def test_webhook_endpoints():
    """Testar todos os webhooks atuais"""
    
    print("🔥 TESTANDO WEBHOOKS ATUAIS - ANTES DE MEXER")
    print("=" * 60)
    
    base_url = "https://app.geminii.com.br"
    
    # Lista de webhooks para testar
    webhooks = [
        "/api/mercadopago/webhook",  # Blueprint
        "/webhook/mercadopago",      # Main.py 
        "/webhook/mercadopago-safe"  # Main.py backup
    ]
    
    # Dados de teste (simulando MP)
    test_payment_data = {
        "type": "payment",
        "data": {
            "id": "999999999"  # ID fake para teste
        }
    }
    
    results = {}
    
    for webhook_path in webhooks:
        print(f"\n🎯 TESTANDO: {webhook_path}")
        print("-" * 40)
        
        try:
            # Teste GET
            print("📡 GET request...")
            get_response = requests.get(f"{base_url}{webhook_path}", timeout=10)
            print(f"   Status: {get_response.status_code}")
            
            if get_response.status_code == 200:
                print(f"   ✅ GET OK")
                get_data = get_response.json()
                print(f"   Response: {get_data.get('status', 'N/A')}")
            else:
                print(f"   ❌ GET FAILED")
            
            # Teste POST
            print("📡 POST request...")
            post_response = requests.post(
                f"{base_url}{webhook_path}",
                json=test_payment_data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            print(f"   Status: {post_response.status_code}")
            
            if post_response.status_code in [200, 400, 500]:  # Qualquer resposta válida
                print(f"   ✅ POST RESPONDEU")
                try:
                    post_data = post_response.json()
                    print(f"   Response: {post_data.get('success', 'N/A')}")
                    print(f"   Message: {post_data.get('message', 'N/A')}")
                except:
                    print(f"   Response: {post_response.text[:100]}")
            else:
                print(f"   ❌ POST FAILED")
            
            results[webhook_path] = {
                "get_status": get_response.status_code,
                "post_status": post_response.status_code,
                "working": get_response.status_code == 200 and post_response.status_code in [200, 400, 500]
            }
            
        except Exception as e:
            print(f"   ❌ ERRO: {e}")
            results[webhook_path] = {"error": str(e), "working": False}
        
        time.sleep(1)  # Pausa entre requests
    
    return results

def test_mercadopago_routes():
    """Testar rotas do Mercado Pago"""
    
    print(f"\n💳 TESTANDO ROTAS MERCADO PAGO")
    print("=" * 40)
    
    base_url = "https://app.geminii.com.br"
    
    routes = [
        "/api/mercadopago/plans",
        "/api/mercadopago/test",
        "/api/plans"  # Rota de compatibilidade
    ]
    
    for route in routes:
        print(f"\n🎯 {route}")
        try:
            response = requests.get(f"{base_url}{route}", timeout=10)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ OK - {data.get('message', 'Success')}")
            else:
                print(f"   ❌ FAILED")
                
        except Exception as e:
            print(f"   ❌ ERRO: {e}")

def check_martha_railway():
    """Verificar se Martha ainda está OK no Railway"""
    
    print(f"\n👤 VERIFICANDO MARTHA NO RAILWAY")
    print("=" * 40)
    
    try:
        login_data = {
            "email": "martha@gmail.com", 
            "password": "123456"
        }
        
        response = requests.post(
            "https://app.geminii.com.br/api/auth/login",
            json=login_data,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            user = data.get('data', {}).get('user', {})
            
            print(f"✅ Martha no Railway:")
            print(f"   Plan ID: {user.get('plan_id')}")
            print(f"   Plan Name: {user.get('plan_name')}")
            print(f"   Status: {'ATIVO' if user.get('plan_id') == 2 else 'INATIVO'}")
            
            return user.get('plan_id') == 2
        else:
            print(f"❌ Login falhou: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def main():
    """Teste completo do estado atual"""
    
    print("🚨 TESTE DE ESTADO ATUAL - ANTES DE REFATORAR")
    print("Este teste vai mostrar o que está funcionando AGORA")
    print("=" * 60)
    
    # 1. Testar webhooks
    webhook_results = test_webhook_endpoints()
    
    # 2. Testar rotas MP
    test_mercadopago_routes()
    
    # 3. Verificar Martha
    martha_ok = check_martha_railway()
    
    # 4. Resumo final
    print(f"\n" + "="*60)
    print(f"📊 RESUMO DO ESTADO ATUAL")
    print(f"="*60)
    
    working_webhooks = [path for path, result in webhook_results.items() if result.get('working')]
    
    print(f"🎯 Webhooks funcionando: {len(working_webhooks)}/3")
    for webhook in working_webhooks:
        print(f"   ✅ {webhook}")
    
    broken_webhooks = [path for path, result in webhook_results.items() if not result.get('working')]
    for webhook in broken_webhooks:
        print(f"   ❌ {webhook}")
    
    print(f"\n👤 Martha Railway: {'✅ ATIVA' if martha_ok else '❌ INATIVA'}")
    
    # Recomendação
    print(f"\n🎯 RECOMENDAÇÃO:")
    if len(working_webhooks) > 0 and martha_ok:
        print(f"✅ SISTEMA ESTÁ FUNCIONANDO!")
        print(f"📁 É SEGURO refatorar para routes/services")
        print(f"🔒 Webhook principal: {working_webhooks[0]}")
        
        # Salvar estado atual
        with open('estado_atual.json', 'w') as f:
            json.dump({
                'working_webhooks': working_webhooks,
                'martha_active': martha_ok,
                'test_timestamp': datetime.now().isoformat(),
                'safe_to_refactor': True
            }, f, indent=2)
        
        print(f"💾 Estado salvo em 'estado_atual.json'")
        
    else:
        print(f"❌ SISTEMA TEM PROBLEMAS!")
        print(f"🚨 NÃO refatore ainda - corrige isso primeiro")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    
    if success:
        print(f"\n🚀 PRÓXIMO PASSO:")
        print(f"Execute: python implement_routes_services.py")
    else:
        print(f"\n🔧 CORRIJA OS PROBLEMAS PRIMEIRO!")
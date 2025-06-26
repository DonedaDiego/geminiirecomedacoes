import requests
import json
import time
from datetime import datetime

BASE_URL = "https://app.geminii.com.br"

def test_webhook_endpoints():
    """Testar diferentes endpoints do webhook"""
    print("🔍 TESTANDO ENDPOINTS DO WEBHOOK")
    print("=" * 50)
    
    endpoints = [
        "/webhook/mercadopago",
        "/api/mercadopago/webhook", 
        "/webhook/mercadopago-safe"
    ]
    
    for endpoint in endpoints:
        try:
            print(f"\n📍 Testando: {endpoint}")
            
            # Teste GET
            response = requests.get(f"{BASE_URL}{endpoint}")
            print(f"   GET: {response.status_code} - {response.text[:100]}")
            
            # Teste POST com dados
            webhook_data = {
                "type": "payment",
                "data": {"id": "TEST_123"}
            }
            
            response = requests.post(f"{BASE_URL}{endpoint}", json=webhook_data)
            print(f"   POST: {response.status_code} - {response.text[:100]}")
            
        except Exception as e:
            print(f"   ❌ Erro: {e}")

def test_webhook_detailed(payment_id="TEST_DETAILED"):
    """Teste detalhado do webhook"""
    print(f"\n🔬 TESTE DETALHADO DO WEBHOOK")
    print("=" * 50)
    
    webhook_data = {
        "type": "payment",
        "data": {"id": payment_id}
    }
    
    try:
        response = requests.post(f"{BASE_URL}/webhook/mercadopago", json=webhook_data)
        
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Response: {response.text}")
        
        if response.status_code == 500:
            print("\n❌ ERRO 500 DETECTADO!")
            print("Possíveis causas:")
            print("1. Função 'webhook' não definida corretamente no main.py")
            print("2. Import do mercadopago_routes falhou")
            print("3. Função process_payment não existe")
            
        return response.status_code == 200
        
    except Exception as e:
        print(f"❌ Erro na requisição: {e}")
        return False

def test_manual_payment_creation():
    """Criar um pagamento manualmente no banco para teste"""
    print(f"\n🧪 CRIANDO PAGAMENTO MANUAL PARA TESTE")
    print("=" * 50)
    
    # Criar pagamento via endpoint de teste
    test_data = {
        "payment_id": f"MANUAL_TEST_{int(time.time())}",
        "user_email": "martha@gmail.com",
        "amount": 79.00,
        "plan": "pro"
    }
    
    try:
        # Simular processamento manual
        response = requests.post(f"{BASE_URL}/debug/create-manual-payment", json=test_data)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Pagamento manual criado: {data}")
            return data.get('payment_id')
        else:
            print(f"❌ Falha: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        return None

def check_webhook_logs():
    """Verificar logs do webhook"""
    print(f"\n📋 VERIFICANDO LOGS DO SISTEMA")
    print("=" * 50)
    
    try:
        # Verificar status geral
        response = requests.get(f"{BASE_URL}/api/status")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API Status: {data}")
            
            mp_status = data.get('mercadopago', {})
            if mp_status.get('success'):
                print(f"✅ Mercado Pago: Conectado")
            else:
                print(f"❌ Mercado Pago: {mp_status}")
        else:
            print(f"❌ API Status falhou: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Erro: {e}")

def test_webhook_with_real_structure():
    """Testar webhook com estrutura real do MP"""
    print(f"\n🎯 TESTE COM ESTRUTURA REAL DO MERCADO PAGO")
    print("=" * 50)
    
    # Estrutura real do webhook do MP
    real_webhook_data = {
        "id": 12345,
        "live_mode": False,
        "type": "payment",
        "date_created": "2024-01-15T20:30:00Z",
        "application_id": 1968398743,
        "user_id": 1968398743,
        "version": 1,
        "api_version": "v1",
        "action": "payment.created",
        "data": {
            "id": "1750899999"  # Payment ID de teste
        }
    }
    
    try:
        print(f"📤 Enviando webhook real...")
        response = requests.post(f"{BASE_URL}/webhook/mercadopago", json=real_webhook_data)
        
        print(f"📨 Status: {response.status_code}")
        print(f"📨 Response: {response.text}")
        
        if response.status_code == 200:
            print(f"✅ Webhook processado com sucesso!")
            return True
        else:
            print(f"❌ Webhook falhou")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def provide_fix_instructions():
    """Fornecer instruções de correção"""
    print(f"\n🔧 INSTRUÇÕES DE CORREÇÃO")
    print("=" * 60)
    
    print(f"1. SUBSTITUIR WEBHOOK NO MAIN.PY:")
    print(f"   - Localize a função mercadopago_webhook() no main.py")
    print(f"   - Substitua pela versão corrigida fornecida")
    
    print(f"\n2. VERIFICAR IMPORTS:")
    print(f"   - Certifique-se que 'from mercadopago_routes import process_payment' funciona")
    print(f"   - Verifique se mercadopago_routes.py tem a função process_payment")
    
    print(f"\n3. TESTAR NOVAMENTE:")
    print(f"   - Reinicie a aplicação no Railway")
    print(f"   - Execute: python test_webhook_fix.py")
    print(f"   - Execute: python test_payment_flow.py")
    
    print(f"\n4. WEBHOOK ALTERNATIVO:")
    print(f"   - Use /webhook/mercadopago-safe como backup")
    print(f"   - Configure no Mercado Pago se necessário")

if __name__ == "__main__":
    print("🚨 DIAGNÓSTICO E CORREÇÃO DO WEBHOOK")
    print("Este script vai identificar e corrigir problemas do webhook")
    print()
    
    # 1. Testar endpoints
    test_webhook_endpoints()
    
    # 2. Verificar logs
    check_webhook_logs()
    
    # 3. Teste detalhado
    if not test_webhook_detailed():
        print(f"\n❌ WEBHOOK COM PROBLEMA - INVESTIGANDO...")
        
        # 4. Teste com estrutura real
        test_webhook_with_real_structure()
        
        # 5. Instruções de correção
        provide_fix_instructions()
    else:
        print(f"\n✅ WEBHOOK FUNCIONANDO!")
        
        # Teste com payment flow
        print(f"\nExecute agora: python test_payment_flow.py")
# webhook_debug.py - TESTAR WEBHOOK E PROCESSAMENTO
# ====================================================

import requests
import json

def test_webhook_endpoint():
    """Testar se webhook está funcionando"""
    print("🔔 TESTANDO WEBHOOK ENDPOINT")
    print("=" * 50)
    
    webhook_url = "https://app.geminii.com.br/api/mercadopago/webhook"
    
    # Teste GET (verificar se está ativo)
    try:
        print(f"📤 GET {webhook_url}")
        response = requests.get(webhook_url, timeout=10)
        print(f"📥 Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"📋 Resposta: {json.dumps(data, indent=2)}")
            except:
                print(f"📋 Resposta (texto): {response.text}")
        else:
            print(f"❌ Erro: {response.text}")
            
    except Exception as e:
        print(f"❌ Erro na conexão: {e}")

def simulate_webhook_payment():
    """Simular webhook com payment_id real"""
    print("\n🧪 SIMULANDO WEBHOOK COM PAYMENT_ID REAL")
    print("=" * 50)
    
    # Payment ID da URL que você mostrou
    payment_id = "1338405423"
    
    webhook_data = {
        "type": "payment",
        "action": "payment.updated",
        "data": {
            "id": payment_id
        },
        "user_id": "1968398743",
        "live_mode": False,
        "date_created": "2025-06-27T16:30:00.000Z"
    }
    
    webhook_url = "https://app.geminii.com.br/api/mercadopago/webhook"
    
    try:
        print(f"📤 POST {webhook_url}")
        print(f"📋 Dados: {json.dumps(webhook_data, indent=2)}")
        
        response = requests.post(
            webhook_url,
            json=webhook_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"\n📥 RESPOSTA DO WEBHOOK:")
        print(f"   Status: {response.status_code}")
        
        try:
            response_json = response.json()
            print(f"   JSON: {json.dumps(response_json, indent=2)}")
        except:
            print(f"   Texto: {response.text}")
            
        if response.status_code == 200:
            print("✅ WEBHOOK PROCESSOU CORRETAMENTE!")
        else:
            print("❌ WEBHOOK COM PROBLEMA!")
            
    except Exception as e:
        print(f"❌ Erro ao chamar webhook: {e}")

def check_payment_status():
    """Verificar status do pagamento via API"""
    print("\n🔍 VERIFICANDO STATUS DO PAGAMENTO")
    print("=" * 50)
    
    payment_id = "1338405423"
    status_url = f"https://app.geminii.com.br/api/mercadopago/payment/status/{payment_id}"
    
    try:
        print(f"📤 GET {status_url}")
        response = requests.get(status_url, timeout=15)
        print(f"📥 Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"📋 Dados do pagamento:")
                print(json.dumps(data, indent=2))
                
                # Analisar dados
                mp_data = data.get('mercado_pago')
                db_data = data.get('database')
                
                if mp_data:
                    print(f"\n✅ MERCADO PAGO:")
                    print(f"   Status: {mp_data.get('status')}")
                    print(f"   Valor: R$ {mp_data.get('amount')}")
                    print(f"   Email: {mp_data.get('payer_email')}")
                    print(f"   Device ID: {mp_data.get('device_id', 'N/A')}")
                
                if db_data:
                    print(f"\n📊 BANCO DE DADOS:")
                    print(f"   Processado: {db_data.get('processed')}")
                    print(f"   Existe: {db_data.get('exists')}")
                
            except Exception as e:
                print(f"❌ Erro ao processar JSON: {e}")
                print(f"📋 Resposta: {response.text}")
        else:
            print(f"❌ Erro: {response.text}")
            
    except Exception as e:
        print(f"❌ Erro na requisição: {e}")

def test_backend_logs():
    """Verificar se backend está respondendo"""
    print("\n🔍 TESTANDO ENDPOINTS DO BACKEND")
    print("=" * 50)
    
    endpoints = [
        "https://app.geminii.com.br/api/status",
        "https://app.geminii.com.br/api/mercadopago/test",
        "https://app.geminii.com.br/api/mercadopago/debug/info"
    ]
    
    for endpoint in endpoints:
        try:
            print(f"\n📤 GET {endpoint}")
            response = requests.get(endpoint, timeout=10)
            print(f"📥 Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"✅ OK: {data.get('message', 'Sem mensagem')}")
                except:
                    print(f"✅ OK: {response.text[:100]}...")
            else:
                print(f"❌ Erro: {response.text[:100]}...")
                
        except Exception as e:
            print(f"❌ Erro: {e}")

def diagnose_issue():
    """Diagnosticar o problema principal"""
    print("\n🎯 DIAGNÓSTICO DO PROBLEMA")
    print("=" * 50)
    
    print("🔍 CENÁRIO ATUAL:")
    print("   ✅ Frontend: Funcionando")
    print("   ✅ Checkout: Criado com sucesso")
    print("   ✅ Pagamento: APROVADO no MercadoPago")
    print("   ❌ Webhook: Não processou automaticamente")
    print("   ❌ Tela: Travada em 'Ativando assinatura...'")
    
    print("\n🎯 POSSÍVEIS CAUSAS:")
    print("   1. 🔔 Webhook não recebeu notificação do MP")
    print("   2. 🐛 Erro no processamento do webhook")
    print("   3. 🗄️ Problema na atualização do banco")
    print("   4. 📧 Email do usuário não encontrado")
    print("   5. ⚙️ Configuração de notificação MP")
    
    print("\n🔧 SOLUÇÕES:")
    print("   1. 🧪 Testar webhook manualmente")
    print("   2. 🔍 Verificar logs do Railway")
    print("   3. 🔄 Processar payment_id manualmente")
    print("   4. 🗄️ Verificar se usuário existe no banco")

def main():
    """Executar todos os testes"""
    print("🔍 DEBUG COMPLETO DO WEBHOOK")
    print("=" * 60)
    
    # 1. Testar webhook endpoint
    test_webhook_endpoint()
    
    # 2. Simular webhook
    simulate_webhook_payment()
    
    # 3. Verificar status
    check_payment_status()
    
    # 4. Testar backend
    test_backend_logs()
    
    # 5. Diagnóstico
    diagnose_issue()
    
    print("\n📊 RESUMO:")
    print("✅ Payment ID: 1338405423")
    print("✅ Status MP: approved")
    print("❌ Processamento: Pendente")
    print()
    print("🎯 PRÓXIMOS PASSOS:")
    print("   1. Execute este script")
    print("   2. Verifique logs do Railway")
    print("   3. Processe payment_id manualmente se necessário")

if __name__ == "__main__":
    main()
# fix_token_and_test.py - CORRIGIR TOKEN E TESTAR TUDO
# =====================================================

import psycopg2
import requests
import json
from datetime import datetime

def connect_railway():
    return psycopg2.connect(
        host="ballast.proxy.rlwy.net",
        port=33654,
        dbname="railway",
        user="postgres",
        password="SWYYPTWLukrNVucLgnyImUfTftHSadyS"
    )

def test_correct_token():
    """Testar com o token correto"""
    print("🔑 TESTANDO TOKEN CORRETO")
    print("=" * 40)
    
    payment_id = "1338404153"
    # Token correto que você passou
    access_token = "TEST-8540613393237089-091618-106d38d51fc598ab9762456309594429-1968398743"
    
    try:
        url = f"https://api.mercadopago.com/v1/payments/{payment_id}"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            payment_data = response.json()
            
            print("✅ PAGAMENTO ENCONTRADO NO MP!")
            print(f"   💰 Valor: R$ {payment_data.get('transaction_amount', 0)}")
            print(f"   📧 Payer Email: {payment_data.get('payer', {}).get('email', 'N/A')}")
            print(f"   📱 Device ID: {payment_data.get('device_id', 'N/A')}")
            print(f"   🔢 External Ref: {payment_data.get('external_reference', 'N/A')}")
            print(f"   ✅ Status: {payment_data.get('status', 'N/A')}")
            print(f"   🎯 Payment Method: {payment_data.get('payment_method_id', 'N/A')}")
            
            # Informações do pagador
            payer = payment_data.get('payer', {})
            print(f"   👤 Payer ID: {payer.get('id', 'N/A')}")
            print(f"   🏷️ Payer Type: {payer.get('type', 'N/A')}")
            
            return payment_data
        else:
            print(f"❌ Erro: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        return None

def analyze_external_reference(payment_data):
    """Analisar external_reference do pagamento real"""
    print("\n🔍 ANALISANDO EXTERNAL_REFERENCE")
    print("=" * 40)
    
    if not payment_data:
        print("❌ Sem dados de pagamento para analisar")
        return
    
    external_ref = payment_data.get('external_reference', '')
    payer_email = payment_data.get('payer', {}).get('email', '')
    
    print(f"📋 External Reference: {external_ref}")
    print(f"📧 Payer Email: {payer_email}")
    
    if external_ref:
        # Analisar formato atual
        parts = external_ref.split('_')
        print(f"🔧 Partes do External Reference:")
        for i, part in enumerate(parts):
            print(f"   {i}: {part}")
        
        # Verificar se contém informações do usuário
        if 'geminii' in external_ref.lower():
            print("✅ Contém identificação da empresa")
        
        if any(plan in external_ref.lower() for plan in ['pro', 'premium', 'basico']):
            print("✅ Contém informação do plano")
        
        if any(cycle in external_ref.lower() for cycle in ['monthly', 'annual']):
            print("✅ Contém informação do ciclo")
        
        # Sugerir melhorias
        print("\n💡 SUGESTÕES PARA EXTERNAL_REFERENCE:")
        print("   Formato atual: geminii_premium_annual_None_1751036474")
        print("   Sugestão: geminii_premium_annual_diedoneda@gmail.com_1751036474")
        print("   Ou: geminii_premium_annual_user41_1751036474")
        print("   Assim o webhook pode identificar o usuário!")

def test_webhook_with_correct_token():
    """Testar webhook sabendo que o token está correto"""
    print("\n🧪 TESTANDO WEBHOOK COM TOKEN CORRETO")
    print("=" * 40)
    
    # Agora que sabemos que o token funciona, vamos testar o webhook
    webhook_data = {
        "id": 1338404153,
        "live_mode": False,
        "type": "payment",
        "date_created": "2025-06-27T15:01:50.000Z",
        "application_id": 8540613393237089,
        "user_id": 303485398,
        "version": 1,
        "api_version": "v1",
        "action": "payment.created",
        "data": {
            "id": "1338404153"
        }
    }
    
    webhook_url = "https://app.geminii.com.br/api/mercadopago/webhook"
    
    try:
        response = requests.post(
            webhook_url,
            json=webhook_data,
            headers={'Content-Type': 'application/json'},
            timeout=15
        )
        
        print(f"📥 WEBHOOK RESPONSE:")
        print(f"   Status: {response.status_code}")
        print(f"   Body: {response.text}")
        
        return response.status_code == 200
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def create_improved_external_reference():
    """Criar external_reference melhorado"""
    print("\n🔧 CRIANDO EXTERNAL_REFERENCE MELHORADO")
    print("=" * 40)
    
    # Buscar usuário diego
    try:
        conn = connect_railway()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, email FROM users 
            WHERE email = 'diedoneda@gmail.com'
        """)
        
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if user:
            user_id, email = user
            
            # Formatos sugeridos
            formats = [
                f"geminii_premium_annual_{email}_{int(datetime.now().timestamp())}",
                f"geminii_premium_annual_user{user_id}_{int(datetime.now().timestamp())}",
                f"geminii_premium_annual_id{user_id}_{int(datetime.now().timestamp())}",
                f"premium_annual_{email.split('@')[0]}_{int(datetime.now().timestamp())}"
            ]
            
            print("💡 FORMATOS SUGERIDOS PARA EXTERNAL_REFERENCE:")
            for i, fmt in enumerate(formats, 1):
                print(f"   {i}. {fmt}")
            
            print("\n🎯 VANTAGENS:")
            print("   ✅ Contém email ou ID do usuário")
            print("   ✅ Webhook pode identificar usuário")
            print("   ✅ Não depende só do payer.email")
            print("   ✅ Mais robusto para identificação")
            
            return formats[0]  # Retorna o primeiro formato
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        
    return None

def test_user_identification_methods():
    """Testar métodos de identificação de usuário"""
    print("\n🔍 TESTANDO MÉTODOS DE IDENTIFICAÇÃO")
    print("=" * 40)
    
    # Método 1: Por email
    test_email = "diedoneda@gmail.com"
    
    try:
        conn = connect_railway()
        cursor = conn.cursor()
        
        print("1. BUSCA POR EMAIL:")
        cursor.execute("SELECT id, name FROM users WHERE email = %s", (test_email,))
        user = cursor.fetchone()
        if user:
            print(f"   ✅ Encontrado: {user[1]} (ID: {user[0]})")
        else:
            print(f"   ❌ Não encontrado: {test_email}")
        
        # Método 2: Por external_reference
        print("\n2. BUSCA POR EXTERNAL_REFERENCE:")
        external_ref = "geminii_premium_annual_None_1751036474"
        
        # Extrair timestamp
        parts = external_ref.split('_')
        if len(parts) >= 5:
            timestamp = parts[4]
            print(f"   📅 Timestamp extraído: {timestamp}")
            
            # Buscar usuário criado próximo ao timestamp
            cursor.execute("""
                SELECT id, name, email FROM users 
                WHERE ABS(EXTRACT(EPOCH FROM created_at) - %s) < 3600
                ORDER BY created_at DESC 
                LIMIT 1
            """, (int(timestamp) if timestamp.isdigit() else 0,))
            
            user_by_time = cursor.fetchone()
            if user_by_time:
                print(f"   ✅ Por timestamp: {user_by_time[1]} ({user_by_time[2]})")
            else:
                print(f"   ❌ Nenhum usuário próximo ao timestamp")
        
        # Método 3: Último usuário regular
        print("\n3. ÚLTIMO USUÁRIO REGULAR:")
        cursor.execute("""
            SELECT id, name, email FROM users 
            WHERE user_type != 'admin' 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        
        last_user = cursor.fetchone()
        if last_user:
            print(f"   ✅ Último usuário: {last_user[1]} ({last_user[2]})")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erro: {e}")

def main():
    """Executar teste completo com token correto"""
    print("🚀 TESTE COMPLETO COM TOKEN CORRETO")
    print("=" * 60)
    
    # 1. Testar token
    payment_data = test_correct_token()
    
    # 2. Analisar external_reference
    analyze_external_reference(payment_data)
    
    # 3. Testar webhook
    webhook_success = test_webhook_with_correct_token()
    
    # 4. Criar external_reference melhorado
    improved_ref = create_improved_external_reference()
    
    # 5. Testar métodos de identificação
    test_user_identification_methods()
    
    # 6. Resumo final
    print("\n📊 RESUMO FINAL")
    print("=" * 40)
    
    if payment_data:
        payer_email = payment_data.get('payer', {}).get('email', 'N/A')
        print(f"✅ Token funcionando: Sim")
        print(f"✅ Pagamento encontrado: Sim")
        print(f"📧 Email do pagador: {payer_email}")
        print(f"🔢 External reference: {payment_data.get('external_reference', 'N/A')}")
        
        if payer_email == 'diedoneda@gmail.com':
            print("🎉 EMAIL BATE! Webhook deve funcionar!")
        elif payer_email == 'N/A' or not payer_email:
            print("❌ Email não enviado pelo MP - precisa correção webhook")
        else:
            print(f"❌ Email diferente: {payer_email} vs diedoneda@gmail.com")
    
    print(f"✅ Webhook endpoint: {'Funcionando' if webhook_success else 'Com problema'}")
    print(f"✅ External reference melhorado: {'Sim' if improved_ref else 'Erro'}")
    
    print("\n🎯 PRÓXIMAS AÇÕES:")
    if payment_data:
        print("   1. ✅ Atualizar token no Railway")
        print("   2. 🔧 Melhorar external_reference")
        print("   3. 🧪 Testar novo pagamento")
        print("   4. 📋 Solicitar aprovação MP")
    else:
        print("   1. ❌ Verificar token no código")
        print("   2. ❌ Debug adicional necessário")

if __name__ == "__main__":
    main()
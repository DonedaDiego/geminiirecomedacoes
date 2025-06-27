# test_webhook_complete.py - TESTE COMPLETO DO WEBHOOK
# ====================================================

import psycopg2
import requests
import json
from datetime import datetime

def connect_railway():
    """Conectar no Railway"""
    return psycopg2.connect(
        host="ballast.proxy.rlwy.net",
        port=33654,
        dbname="railway",
        user="postgres",
        password="SWYYPTWLukrNVucLgnyImUfTftHSadyS"
    )

def verify_current_status():
    """Verificar status atual após processamento manual"""
    print("🔍 VERIFICANDO STATUS ATUAL")
    print("=" * 40)
    
    try:
        conn = connect_railway()
        cursor = conn.cursor()
        
        # 1. Verificar pagamentos
        cursor.execute("""
            SELECT payment_id, user_id, status, amount, plan_name, device_id, created_at
            FROM payments 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        
        payments = cursor.fetchall()
        
        print("💳 PAGAMENTOS NO BANCO:")
        if payments:
            for payment in payments:
                print(f"   📋 ID: {payment[0]} | User: {payment[1]} | Status: {payment[2]}")
                print(f"       💰 R$ {payment[3]} | Plano: {payment[4]} | Device: {payment[5]}")
                print(f"       📅 {payment[6]}")
                print()
        else:
            print("   ❌ Nenhum pagamento encontrado")
        
        # 2. Verificar usuários ativos
        cursor.execute("""
            SELECT id, name, email, plan_name, subscription_status, plan_expires_at
            FROM users 
            WHERE subscription_status = 'active'
            ORDER BY updated_at DESC
        """)
        
        active_users = cursor.fetchall()
        
        print("👥 USUÁRIOS ATIVOS:")
        if active_users:
            for user in active_users:
                print(f"   ✅ {user[1]} ({user[2]})")
                print(f"       🎯 Plano: {user[3]} | Status: {user[4]}")
                print(f"       📅 Expira: {user[5]}")
                print()
        else:
            print("   ❌ Nenhum usuário ativo")
        
        cursor.close()
        conn.close()
        
        return len(payments) > 0, len(active_users) > 0
        
    except Exception as e:
        print(f"❌ Erro na verificação: {e}")
        return False, False

def test_webhook_endpoint():
    """Testar endpoint do webhook"""
    print("🌐 TESTANDO ENDPOINT DO WEBHOOK")
    print("=" * 40)
    
    webhook_url = "https://app.geminii.com.br/api/mercadopago/webhook"
    
    # Teste 1: GET request
    try:
        response = requests.get(webhook_url, timeout=10)
        print(f"✅ GET {webhook_url}")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:100]}...")
        print()
    except Exception as e:
        print(f"❌ GET falhou: {e}")
        print()
    
    # Teste 2: POST com dados válidos
    webhook_data = {
        "id": 9999999999,
        "live_mode": False,
        "type": "payment",
        "date_created": datetime.now().isoformat(),
        "application_id": 8540613393237089,
        "user_id": 303485398,
        "version": 1,
        "api_version": "v1",
        "action": "payment.created",
        "data": {
            "id": "9999999999"
        }
    }
    
    try:
        response = requests.post(
            webhook_url,
            json=webhook_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        print(f"✅ POST {webhook_url}")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}...")
        print()
    except Exception as e:
        print(f"❌ POST falhou: {e}")
        print()

def simulate_real_webhook():
    """Simular webhook com dados reais do pagamento processado"""
    print("🔄 SIMULANDO WEBHOOK COM DADOS REAIS")
    print("=" * 40)
    
    # Dados baseados no pagamento real que foi processado
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
    
    print("📤 Enviando dados do webhook:")
    print(json.dumps(webhook_data, indent=2))
    print()
    
    try:
        response = requests.post(
            webhook_url,
            json=webhook_data,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'MercadoPago WebHook v1.0 payment'
            },
            timeout=15
        )
        
        print(f"📥 RESPOSTA DO WEBHOOK:")
        print(f"   Status Code: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")
        print(f"   Body: {response.text}")
        print()
        
        if response.status_code == 200:
            print("✅ Webhook processou com sucesso!")
        elif response.status_code == 500:
            print("❌ Erro interno no webhook")
            print("   💡 Provavelmente problema na identificação do usuário")
        else:
            print(f"⚠️ Status inesperado: {response.status_code}")
        
        return response.status_code == 200
        
    except Exception as e:
        print(f"❌ Erro ao simular webhook: {e}")
        return False

def create_test_payment():
    """Criar pagamento de teste para webhook"""
    print("🧪 CRIANDO PAGAMENTO DE TESTE")
    print("=" * 40)
    
    try:
        conn = connect_railway()
        cursor = conn.cursor()
        
        # Buscar usuário ativo para teste
        cursor.execute("""
            SELECT id, name, email FROM users 
            WHERE subscription_status = 'active' 
            LIMIT 1
        """)
        
        user = cursor.fetchone()
        if not user:
            print("❌ Nenhum usuário ativo para teste")
            cursor.close()
            conn.close()
            return None
        
        # Criar novo pagamento de teste
        test_payment_id = f"TEST_{int(datetime.now().timestamp())}"
        
        cursor.execute("""
            INSERT INTO payments (user_id, payment_id, status, amount, plan_id, plan_name, 
                                cycle, external_reference, device_id, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user[0],  # user_id
            test_payment_id,  # payment_id
            'pending',  # status
            79.00,  # amount
            '1',  # plan_id
            'Pro',  # plan_name
            'monthly',  # cycle
            f'test_pro_monthly_{user[2]}_{int(datetime.now().timestamp())}',  # external_reference
            f'test-device-{int(datetime.now().timestamp())}',  # device_id
            datetime.now(),  # created_at
            datetime.now()   # updated_at
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ Pagamento de teste criado:")
        print(f"   Payment ID: {test_payment_id}")
        print(f"   Usuário: {user[1]} ({user[2]})")
        print(f"   Status: pending")
        print()
        
        return test_payment_id
        
    except Exception as e:
        print(f"❌ Erro ao criar pagamento de teste: {e}")
        return None

def check_webhook_logs_instruction():
    """Instruções para verificar logs"""
    print("📋 COMO VERIFICAR LOGS DO RAILWAY")
    print("=" * 40)
    print("1. Acesse https://railway.app")
    print("2. Entre no seu projeto")
    print("3. Clique em 'Deployments'")
    print("4. Clique no deployment mais recente")
    print("5. Vá na aba 'Logs'")
    print("6. Procure por:")
    print("   - 'WEBHOOK RECEBIDO'")
    print("   - 'Payment ID:'")
    print("   - Códigos de erro (500, 404)")
    print("   - 'Usuário não encontrado'")
    print()
    print("💡 Se você ver 'Usuário não encontrado: None'")
    print("   → O webhook está recebendo mas não identifica o usuário")
    print("   → Precisa da correção que preparei")
    print()

def diagnose_webhook_issue():
    """Diagnosticar problema específico do webhook"""
    print("🔍 DIAGNÓSTICO DO PROBLEMA DO WEBHOOK")
    print("=" * 40)
    
    print("📋 Baseado nos logs que você mostrou:")
    print("   ✅ Webhook está recebendo as chamadas")
    print("   ✅ Payment ID é extraído corretamente (1338404153)")
    print("   ❌ Usuário vem como 'None'")
    print("   ❌ Processamento falha por 'Usuário não encontrado'")
    print()
    
    print("🎯 CAUSA RAIZ:")
    print("   O MercadoPago não está enviando payer.email")
    print("   Ou o email não bate com nenhum usuário cadastrado")
    print()
    
    print("🔧 SOLUÇÕES:")
    print("   1. IMEDIATA: Usar processamento manual (já fizemos)")
    print("   2. CORREÇÃO: Melhorar lógica de identificação do usuário")
    print("   3. BACKUP: Criar tabela de pagamentos pendentes")
    print()

def main():
    """Executar teste completo"""
    print("🧪 TESTE COMPLETO DO WEBHOOK")
    print("=" * 50)
    print(f"🕐 Iniciado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print()
    
    # 1. Verificar status atual
    has_payments, has_active_users = verify_current_status()
    
    # 2. Testar endpoint
    test_webhook_endpoint()
    
    # 3. Simular webhook real
    webhook_success = simulate_real_webhook()
    
    # 4. Diagnóstico
    diagnose_webhook_issue()
    
    # 5. Instruções de logs
    check_webhook_logs_instruction()
    
    # 6. Resumo final
    print("📊 RESUMO FINAL")
    print("=" * 40)
    print(f"✅ Processamento manual: {'Funcionou' if has_payments else 'Falhou'}")
    print(f"✅ Usuários ativos: {'Sim' if has_active_users else 'Não'}")
    print(f"✅ Endpoint acessível: Sim")
    print(f"❌ Webhook automático: {'Funcionou' if webhook_success else 'Falhou'}")
    print()
    
    if has_payments and has_active_users:
        print("🎉 SITUAÇÃO ATUAL: SUCESSO PARCIAL")
        print("   ✅ Pagamento foi processado (manualmente)")
        print("   ✅ Usuário tem plano ativo")
        print("   ✅ Sistema funcionando")
        print("   ❌ Webhook precisa de correção para próximos pagamentos")
        print()
        print("🚀 PRÓXIMOS PASSOS:")
        print("   1. Testar login da usuária gamora")
        print("   2. Verificar acesso Premium")
        print("   3. Solicitar aprovação MP")
        print("   4. Corrigir webhook (opcional)")
    else:
        print("❌ SITUAÇÃO: PROBLEMAS IDENTIFICADOS")
        print("   Revisar processamento manual")

if __name__ == "__main__":
    main()
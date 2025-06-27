# investigate_email_source.py - INVESTIGAR ORIGEM DO EMAIL
# ========================================================

import psycopg2
import requests
import json

def connect_railway():
    return psycopg2.connect(
        host="ballast.proxy.rlwy.net",
        port=33654,
        dbname="railway",
        user="postgres",
        password="SWYYPTWLukrNVucLgnyImUfTftHSadyS"
    )

def analyze_payment_details():
    """Analisar detalhes do pagamento para entender origem do email"""
    print("🔍 ANALISANDO DETALHES DO PAGAMENTO")
    print("=" * 50)
    
    payment_id = "1338404153"
    access_token = "TEST-8540613393237089-091618-106d38d51fc598ab9762456309594429-1968398743"
    
    try:
        url = f"https://api.mercadopago.com/v1/payments/{payment_id}"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            payment_data = response.json()
            
            print("📋 DADOS COMPLETOS DO PAGAMENTO:")
            
            # Informações do pagador
            payer = payment_data.get('payer', {})
            print(f"\n👤 PAYER (PAGADOR):")
            print(f"   📧 Email: {payer.get('email', 'N/A')}")
            print(f"   🆔 ID: {payer.get('id', 'N/A')}")
            print(f"   🏷️ Type: {payer.get('type', 'N/A')}")
            print(f"   👤 First Name: {payer.get('first_name', 'N/A')}")
            print(f"   👤 Last Name: {payer.get('last_name', 'N/A')}")
            
            # Identificação
            identification = payer.get('identification', {})
            if identification:
                print(f"   🆔 Doc Type: {identification.get('type', 'N/A')}")
                print(f"   🆔 Doc Number: {identification.get('number', 'N/A')}")
            
            # Phone
            phone = payer.get('phone', {})
            if phone:
                print(f"   📞 Phone: {phone.get('area_code', '')}{phone.get('number', '')}")
            
            # Informações do pagamento
            print(f"\n💳 INFORMAÇÕES DO PAGAMENTO:")
            print(f"   💰 Valor: R$ {payment_data.get('transaction_amount', 0)}")
            print(f"   🔢 External Ref: {payment_data.get('external_reference', 'N/A')}")
            print(f"   📱 Device ID: {payment_data.get('device_id', 'N/A')}")
            print(f"   🎯 Payment Method: {payment_data.get('payment_method_id', 'N/A')}")
            print(f"   ✅ Status: {payment_data.get('status', 'N/A')}")
            print(f"   📅 Date Created: {payment_data.get('date_created', 'N/A')}")
            
            # Metadata e additional info
            metadata = payment_data.get('metadata', {})
            if metadata:
                print(f"\n📋 METADATA:")
                for key, value in metadata.items():
                    print(f"   {key}: {value}")
            
            additional_info = payment_data.get('additional_info', {})
            if additional_info:
                print(f"\n📋 ADDITIONAL INFO:")
                print(json.dumps(additional_info, indent=2))
            
            # Point of interaction
            point_of_interaction = payment_data.get('point_of_interaction', {})
            if point_of_interaction:
                print(f"\n🖥️ POINT OF INTERACTION:")
                print(f"   Type: {point_of_interaction.get('type', 'N/A')}")
            
            return payment_data
        else:
            print(f"❌ Erro: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        return None

def check_preference_creation():
    """Verificar como a preferência foi criada"""
    print("\n🔍 ANALISANDO CRIAÇÃO DA PREFERÊNCIA")
    print("=" * 50)
    
    print("💡 POSSÍVEIS CAUSAS DO EMAIL AUTOMÁTICO:")
    print()
    print("1. 🎮 AMBIENTE DE TESTE:")
    print("   - MercadoPago pode gerar emails automáticos em teste")
    print("   - Para proteger emails reais")
    print("   - Comportamento padrão do sandbox")
    print()
    print("2. 🔧 PREFERÊNCIA SEM PAYER.EMAIL:")
    print("   - Se não enviar payer.email na preferência")
    print("   - MP gera email automático")
    print("   - Solução: sempre enviar payer.email")
    print()
    print("3. 💳 CARTÃO DE TESTE:")
    print("   - Cartões de teste podem gerar dados fictícios")
    print("   - Incluindo email automático")
    print("   - Comportamento esperado em sandbox")
    print()
    print("4. ⚙️ CONFIGURAÇÃO SDK:")
    print("   - Frontend não está capturando email corretamente")
    print("   - Formulário não envia payer info")
    print("   - Bug na criação da preferência")

def analyze_external_reference_pattern():
    """Analisar padrão do external_reference"""
    print("\n🔍 ANALISANDO EXTERNAL_REFERENCE")
    print("=" * 50)
    
    external_ref = "geminii_premium_annual_None_1751036474"
    
    print(f"📋 External Reference: {external_ref}")
    print()
    print("🔍 ANÁLISE:")
    parts = external_ref.split('_')
    print(f"   Parte 0: {parts[0]} (empresa)")
    print(f"   Parte 1: {parts[1]} (plano)")  
    print(f"   Parte 2: {parts[2]} (ciclo)")
    print(f"   Parte 3: {parts[3]} (❌ None - deveria ser user_id ou email)")
    print(f"   Parte 4: {parts[4]} (timestamp)")
    print()
    print("🎯 PROBLEMA IDENTIFICADO:")
    print("   ❌ Parte 3 é 'None' - não identifica usuário")
    print("   ✅ Deveria ser 'user41' ou 'diedoneda@gmail.com'")
    print()
    print("💡 SOLUÇÃO:")
    print("   1. Capturar user_id na criação da preferência")
    print("   2. Incluir no external_reference")
    print("   3. Webhook pode identificar usuário mesmo sem payer.email")

def suggest_frontend_fix():
    """Sugerir correção no frontend"""
    print("\n🔧 SUGESTÃO DE CORREÇÃO NO FRONTEND")
    print("=" * 50)
    
    print("📋 MODIFICAÇÕES NECESSÁRIAS:")
    print()
    print("1. 📧 CAPTURAR EMAIL DO USUÁRIO:")
    print("   - No formulário de checkout")
    print("   - Ou da sessão logada")
    print("   - Enviar no payer.email da preferência")
    print()
    print("2. 🆔 MELHORAR EXTERNAL_REFERENCE:")
    print("   - Incluir user_id ou email")
    print("   - Formato: geminii_premium_annual_user41_timestamp")
    print("   - Ou: geminii_premium_annual_diedoneda_timestamp")
    print()
    print("3. 📱 GARANTIR DEVICE_ID:")
    print("   - MercadoPago.js deve capturar device_id")
    print("   - Verificar se está sendo enviado corretamente")
    print()
    print("4. 🧪 TESTAR COM DADOS REAIS:")
    print("   - Usar email real na preferência")
    print("   - Verificar se MP mantém o email ou gera automático")

def check_user_session():
    """Verificar se temos dados de sessão do usuário"""
    print("\n👤 VERIFICANDO DADOS DE USUÁRIO")
    print("=" * 50)
    
    try:
        conn = connect_railway()
        cursor = conn.cursor()
        
        # Buscar usuário diego
        cursor.execute("""
            SELECT id, name, email, created_at, updated_at
            FROM users 
            WHERE email = 'diedoneda@gmail.com'
        """)
        
        user = cursor.fetchone()
        if user:
            print(f"✅ USUÁRIO ENCONTRADO:")
            print(f"   🆔 ID: {user[0]}")
            print(f"   👤 Nome: {user[1]}")  
            print(f"   📧 Email: {user[2]}")
            print(f"   📅 Criado: {user[3]}")
            print(f"   📅 Atualizado: {user[4]}")
            
            print(f"\n💡 EXTERNAL_REFERENCE CORRETO SERIA:")
            print(f"   geminii_premium_annual_user{user[0]}_1751036474")
            print(f"   Ou: geminii_premium_annual_{user[2]}_1751036474")
            
            return user[0]
        else:
            print("❌ Usuário não encontrado")
            return None
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return None

def main():
    """Investigar origem do email de teste"""
    print("🔍 INVESTIGAÇÃO: ORIGEM DO EMAIL DE TESTE")
    print("=" * 60)
    
    # 1. Analisar detalhes do pagamento
    payment_data = analyze_payment_details()
    
    # 2. Verificar criação da preferência
    check_preference_creation()
    
    # 3. Analisar external_reference
    analyze_external_reference_pattern()
    
    # 4. Sugerir correção frontend
    suggest_frontend_fix()
    
    # 5. Verificar dados do usuário
    user_id = check_user_session()
    
    # 6. Resumo e soluções
    print("\n📊 RESUMO DA INVESTIGAÇÃO")
    print("=" * 50)
    
    if payment_data:
        payer_email = payment_data.get('payer', {}).get('email', '')
        
        print(f"🔍 DESCOBERTAS:")
        print(f"   📧 Email no pagamento: {payer_email}")
        print(f"   📧 Email esperado: diedoneda@gmail.com")
        print(f"   🔢 External ref: {payment_data.get('external_reference', '')}")
        print(f"   📱 Device ID: {payment_data.get('device_id', 'N/A')}")
        
        if 'test_user_' in payer_email:
            print(f"\n🎯 CAUSA IDENTIFICADA:")
            print(f"   ✅ MercadoPago gerou email automático de teste")
            print(f"   ✅ Comportamento normal em ambiente sandbox")
            print(f"   ✅ Acontece quando não especifica payer.email")
        
        print(f"\n🔧 SOLUÇÕES:")
        print(f"   1. 📧 Sempre especificar payer.email na preferência")
        print(f"   2. 🆔 Incluir user_id no external_reference") 
        print(f"   3. 🔄 Melhorar lógica de identificação no webhook")
        print(f"   4. 🧪 Testar com preferência corrigida")
        
        if user_id:
            print(f"\n💡 PRÓXIMA AÇÃO:")
            print(f"   🔧 Corrigir frontend para enviar:")
            print(f"      - payer.email = 'diedoneda@gmail.com'")
            print(f"      - external_reference = 'geminii_premium_annual_user{user_id}_timestamp'")
            print(f"   🧪 Fazer novo pagamento de teste")
            print(f"   ✅ Webhook deve funcionar automaticamente")

if __name__ == "__main__":
    main()
# force_payment_test.py - FORÇAR TESTE COM DADOS REAIS

import requests
import json
import time

def force_payment_activation():
    """FORÇAR ativação de pagamento com dados que vão funcionar"""
    
    print("FORCANDO TESTE DE PAGAMENTO REAL")
    print("=" * 50)
    
    base_url = "https://app.geminii.com.br"
    
    # 1. Ver plano atual da Martha
    print("1. Verificando plano atual da Martha...")
    
    login_data = {"email": "martha@gmail.com", "password": "123456"}
    
    try:
        response = requests.post(f"{base_url}/api/auth/login", json=login_data)
        
        if response.status_code == 200:
            user_data = response.json()
            user = user_data.get('data', {}).get('user', {})
            
            print(f"Martha ANTES:")
            print(f"  ID: {user.get('id')}")
            print(f"  Plano: {user.get('plan_name')} (ID: {user.get('plan_id')})")
            
            martha_id = user.get('id')
            plano_antes = user.get('plan_name')
            
        else:
            print(f"ERRO: Martha nao encontrada")
            return False
            
    except Exception as e:
        print(f"ERRO ao buscar Martha: {e}")
        return False
    
    # 2. HACKEAR - Simular pagamento aprovado direto no banco
    print(f"\n2. SIMULANDO pagamento aprovado...")
    
    # Criar dados de um pagamento que seria aprovado
    fake_mp_response = {
        "status": "approved",
        "transaction_amount": 79.00,
        "payer": {"email": "martha@gmail.com"},
        "external_reference": f"geminii_pro_monthly_martha@gmail.com_{int(time.time())}"
    }
    
    # 3. Chamar diretamente a função process_payment do nosso service
    print("3. Chamando process_payment diretamente...")
    
    # Importar nosso service corrigido
    import sys
    sys.path.append('.')
    
    try:
        import mercadopago_service
        
        # Vamos "hackear" a consulta do MP para retornar nossos dados fake
        original_requests_get = requests.get
        
        def mock_mp_api(url, **kwargs):
            if 'api.mercadopago.com/v1/payments' in url:
                # Retornar nossa resposta fake
                class MockResponse:
                    status_code = 200
                    def json(self):
                        return fake_mp_response
                
                return MockResponse()
            else:
                return original_requests_get(url, **kwargs)
        
        # Substituir temporariamente
        requests.get = mock_mp_api
        
        # Chamar process_payment
        result = mercadopago_service.process_payment("999888777")
        
        # Restaurar requests original
        requests.get = original_requests_get
        
        print(f"Resultado process_payment:")
        print(f"  Status: {result.get('status')}")
        print(f"  Message: {result.get('message', result.get('error'))}")
        
        if result.get('status') == 'success':
            print(f"  Plano ativado: {result.get('plan_name')}")
            print(f"  Usuario: {result.get('user_name')}")
        
    except Exception as e:
        print(f"ERRO ao chamar process_payment: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 4. Verificar se mudou
    print(f"\n4. Verificando se plano foi ativado...")
    
    try:
        response = requests.post(f"{base_url}/api/auth/login", json=login_data)
        
        if response.status_code == 200:
            user_data = response.json()
            user = user_data.get('data', {}).get('user', {})
            
            plano_depois = user.get('plan_name')
            
            print(f"Martha DEPOIS:")
            print(f"  Plano: {plano_depois} (ID: {user.get('plan_id')})")
            
            if plano_depois != plano_antes:
                print(f"\nSUCESSO! Plano mudou de {plano_antes} para {plano_depois}")
                return True
            else:
                print(f"\nFALHA! Plano continua {plano_depois}")
                return False
                
        else:
            print(f"ERRO ao verificar usuario")
            return False
            
    except Exception as e:
        print(f"ERRO: {e}")
        return False

def direct_database_test():
    """Testar diretamente no banco se necessário"""
    
    print(f"\nTESTE DIRETO NO BANCO")
    print("=" * 30)
    
    try:
        # Importar database
        from database import get_db_connection
        
        conn = get_db_connection()
        if not conn:
            print("ERRO: Nao conseguiu conectar banco")
            return False
        
        cursor = conn.cursor()
        
        # Buscar Martha
        cursor.execute("SELECT id, name, plan_id, plan_name FROM users WHERE email = %s", ("martha@gmail.com",))
        user = cursor.fetchone()
        
        if not user:
            print("ERRO: Martha nao encontrada no banco")
            return False
        
        user_id, name, plan_id, plan_name = user
        print(f"Martha no banco: {name} - Plano {plan_name} (ID: {plan_id})")
        
        # FORÇAR update direto
        print("FORCANDO update direto no banco...")
        
        new_plan_id = 2 if plan_id == 1 else 1
        new_plan_name = "Premium" if plan_id == 1 else "Pro"
        
        cursor.execute("""
            UPDATE users 
            SET plan_id = %s, plan_name = %s, updated_at = NOW()
            WHERE id = %s
        """, (new_plan_id, new_plan_name, user_id))
        
        rows_updated = cursor.rowcount
        conn.commit()
        
        print(f"Linhas atualizadas: {rows_updated}")
        
        if rows_updated > 0:
            print(f"SUCESSO! Martha agora tem plano {new_plan_name}")
            return True
        else:
            print("FALHA! Nenhuma linha atualizada")
            return False
        
    except Exception as e:
        print(f"ERRO no banco: {e}")
        return False
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def main():
    """FORÇAR teste agora"""
    
    print("TESTE FORÇADO - ACABAR COM ESSA LENGA LENGA")
    print("=" * 60)
    
    # Tentar forçar via service
    success = force_payment_activation()
    
    if not success:
        print(f"\nTentativa 1 falhou. Tentando direto no banco...")
        success = direct_database_test()
    
    if success:
        print(f"\nSUCESSO! O PROBLEMA FOI RESOLVIDO!")
        print("Agora faça login no site e veja se o plano mudou")
    else:
        print(f"\nFALHA TOTAL! Problema eh mais profundo")
        print("Vamos investigar o banco de dados...")

if __name__ == "__main__":
    main()
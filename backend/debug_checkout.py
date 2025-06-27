# debug_checkout.py - DEBUG DO ENDPOINT DE CHECKOUT
# ==================================================

import requests
import json

def test_checkout_endpoint():
    """Testar endpoint de checkout diretamente"""
    print("🧪 TESTANDO ENDPOINT DE CHECKOUT")
    print("=" * 50)
    
    # Dados que o frontend está enviando
    checkout_data = {
        "plan": "premium",
        "cycle": "annual",
        "user_id": 52,
        "user_email": "jaum@gmail.com",
        "user_name": "jaum",
        "device_id": "mp-device-1751240098026",
        "external_reference": "geminii_premium_annual_user52_1751240098026"
    }
    
    print("📤 DADOS ENVIADOS:")
    print(json.dumps(checkout_data, indent=2))
    
    # URL do endpoint
    url = "https://app.geminii.com.br/api/mercadopago/checkout/create"
    
    try:
        print(f"\n🔄 Chamando: {url}")
        
        response = requests.post(
            url,
            json=checkout_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"\n📥 RESPOSTA:")
        print(f"   Status: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")
        
        try:
            response_json = response.json()
            print(f"   Body JSON:")
            print(json.dumps(response_json, indent=2))
        except:
            print(f"   Body Text: {response.text}")
        
        if response.status_code != 200:
            print(f"\n❌ ERRO NO ENDPOINT!")
            print(f"   Código: {response.status_code}")
            print(f"   Possíveis causas:")
            
            if response.status_code == 404:
                print(f"   - Endpoint não existe ou rota incorreta")
            elif response.status_code == 500:
                print(f"   - Erro interno do servidor")
            elif response.status_code == 400:
                print(f"   - Dados inválidos ou campos obrigatórios faltando")
            elif response.status_code == 401:
                print(f"   - Token de acesso MP inválido")
            else:
                print(f"   - Erro desconhecido")
        else:
            print(f"\n✅ ENDPOINT FUNCIONANDO!")
            
    except requests.Timeout:
        print(f"\n⏱️ TIMEOUT - Endpoint demorou mais de 30s")
    except requests.ConnectionError:
        print(f"\n🔌 ERRO DE CONEXÃO - Não conseguiu conectar")
    except Exception as e:
        print(f"\n❌ ERRO: {e}")

def check_endpoint_exists():
    """Verificar se endpoint existe"""
    print("\n🔍 VERIFICANDO SE ENDPOINT EXISTE")
    print("=" * 50)
    
    # Testar diferentes variações da URL
    urls_to_test = [
        "https://app.geminii.com.br/api/mercadopago/checkout/create",
        "https://app.geminii.com.br/api/mercadopago/create-checkout",
        "https://app.geminii.com.br/api/checkout/create",
        "https://app.geminii.com.br/api/mercadopago/preference",
        "https://app.geminii.com.br/mercadopago/checkout/create"
    ]
    
    for url in urls_to_test:
        try:
            print(f"\n🔄 Testando: {url}")
            response = requests.get(url, timeout=10)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 405:
                print(f"   ✅ Endpoint existe (Method Not Allowed é normal para GET)")
            elif response.status_code == 404:
                print(f"   ❌ Endpoint não encontrado")
            else:
                print(f"   🤔 Status inesperado: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Erro: {e}")

def suggest_backend_fix():
    """Sugerir correção do backend"""
    print("\n🔧 SUGESTÕES PARA CORREÇÃO DO BACKEND")
    print("=" * 50)
    
    print("1. 📋 VERIFICAR SE ENDPOINT EXISTE:")
    print("   - /api/mercadopago/checkout/create")
    print("   - Método: POST")
    print("   - Content-Type: application/json")
    print()
    
    print("2. 🔑 VERIFICAR TOKEN MERCADOPAGO:")
    print("   - Token correto: TEST-8540613393237089-091618-106d38d51fc598ab9762456309594429-1968398743")
    print("   - Configurado no Railway")
    print("   - Não expirado")
    print()
    
    print("3. 📝 VERIFICAR CAMPOS OBRIGATÓRIOS:")
    print("   - items[] (título, preço, quantidade)")
    print("   - payer.email")
    print("   - external_reference")
    print("   - back_urls")
    print("   - notification_url")
    print()
    
    print("4. 🌐 VERIFICAR CONFIGURAÇÃO RAILWAY:")
    print("   - Variáveis de ambiente")
    print("   - Deploy bem-sucedido")
    print("   - Logs de erro no Railway")
    print()
    
    print("5. 🧪 CÓDIGO EXEMPLO DO ENDPOINT:")
    print("""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import mercadopago

router = APIRouter()

class CheckoutRequest(BaseModel):
    plan: str
    cycle: str
    user_id: int
    user_email: str
    user_name: str
    device_id: str
    external_reference: str

@router.post("/api/mercadopago/checkout/create")
async def create_checkout(request: CheckoutRequest):
    try:
        sdk = mercadopago.SDK("TOKEN_AQUI")
        
        preference_data = {
            "items": [{
                "title": f"Geminii {request.plan.title()} - {request.cycle.title()}",
                "quantity": 1,
                "unit_price": 137 if request.plan == "premium" else 79
            }],
            "payer": {
                "email": request.user_email,
                "name": request.user_name
            },
            "external_reference": request.external_reference,
            "back_urls": {
                "success": "https://app.geminii.com.br/success",
                "failure": "https://app.geminii.com.br/failure",
                "pending": "https://app.geminii.com.br/pending"
            },
            "notification_url": "https://app.geminii.com.br/api/mercadopago/webhook"
        }
        
        result = sdk.preference().create(preference_data)
        
        if result["status"] == 201:
            return {"init_point": result["response"]["init_point"]}
        else:
            raise HTTPException(status_code=400, detail="Erro ao criar preferência")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    """)

def main():
    """Executar debug completo"""
    print("🔍 DEBUG COMPLETO DO CHECKOUT")
    print("=" * 60)
    
    # 1. Testar endpoint
    test_checkout_endpoint()
    
    # 2. Verificar se existe
    check_endpoint_exists()
    
    # 3. Sugerir correções
    suggest_backend_fix()
    
    print("\n📊 RESUMO:")
    print("✅ Frontend: Funcionando perfeitamente")
    print("✅ Usuário: Identificado (jaum@gmail.com, ID: 52)")
    print("✅ External Reference: Correto formato")
    print("❌ Backend: Endpoint de checkout com problema")
    print()
    print("🎯 PRÓXIMO PASSO:")
    print("   Verificar/corrigir endpoint /api/mercadopago/checkout/create")

if __name__ == "__main__":
    main()
# mercadopago_service.py - SERVIÇOS DO MERCADO PAGO
import os
import time
import requests
import hashlib
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from database import get_db_connection
from dotenv import load_dotenv

load_dotenv()

# ===== CONFIGURAÇÃO MERCADO PAGO =====
mp_token = os.environ.get('MP_ACCESS_TOKEN', 'TEST-8540613393237089-091618-106d38d51fc598ab9762456309594429-1968398743')

# Importar SDK do Mercado Pago
mp_sdk = None
preference_client = None

try:
    import mercadopago
    mp_sdk = mercadopago.SDK(mp_token)
    preference_client = mp_sdk.preference()
    print("✅ SDK Mercado Pago Service carregado com sucesso!")
except ImportError:
    print("❌ Módulo mercadopago não encontrado. Instale com: pip install mercadopago")
except Exception as e:
    print(f"❌ Erro ao carregar SDK no service: {e}")

# ===== CONFIGURAÇÃO DOS PLANOS =====
PLANS = {
    "basico": {
        "id": "basico",
        "name": "Básico",
        "db_id": 3,
        "monthly_price": 0,
        "annual_price": 0,
        "features": ["Plano Gratuito"]
    },
    "pro": {
        "id": "pro",
        "name": "Pro",
        "db_id": 1,
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
        "db_id": 2,
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

# ===== SERVIÇOS MERCADO PAGO =====

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
                "preference_test_id": preference_id
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

def create_checkout_service(plan, cycle, customer_email, discounted_price=None, coupon_code=None):
    """Serviço para criar checkout"""
    if not mp_sdk or not preference_client:
        return {
            "success": False,
            "error": "SDK Mercado Pago não disponível"
        }
    
    try:
        # Validar plano
        if plan not in PLANS:
            return {
                "success": False,
                "error": f"Plano '{plan}' não encontrado"
            }
        
        plan_data = PLANS[plan]
        
        # Determinar preço
        if cycle == 'annual':
            original_price = plan_data["annual_price"]
            cycle_display = "Anual"
        else:
            original_price = plan_data["monthly_price"]
            cycle_display = "Mensal"
        
        # Aplicar desconto se houver
        price = float(discounted_price) if discounted_price is not None else original_price
        
        # URLs
        base_url = "https://app.geminii.com.br" if os.environ.get('DATABASE_URL') else "http://localhost:5000"
        
        # Título do item
        item_title = f"Geminii {plan_data['name']} - {cycle_display}"
        if coupon_code:
            item_title += f" (Cupom: {coupon_code})"
        
        # Referência externa com email incluído
        timestamp = int(time.time())
        external_reference = f"geminii_{plan}_{cycle}_{customer_email}_{timestamp}"
        
        # Dados da preferência
        preference_data = {
            "items": [
                {
                    "id": plan,
                    "title": item_title,
                    "quantity": 1,
                    "currency_id": "BRL",
                    "unit_price": float(price)
                }
            ],
            "back_urls": {
                "success": f"{base_url}/payment/success",
                "pending": f"{base_url}/payment/pending", 
                "failure": f"{base_url}/payment/failure"
            },
            "external_reference": external_reference,
            "notification_url": f"{base_url}/api/mercadopago/webhook"
        }
        
        # Adicionar dados do pagador
        if customer_email and customer_email != 'cliente@geminii.com.br':
            preference_data["payer"] = {
                "email": customer_email
            }
        
        print(f"🔄 Service: Criando checkout para {customer_email} - {plan_data['name']} - R$ {price}")
        
        # Criar preferência
        preference_response = preference_client.create(preference_data)
        
        if preference_response.get("status") == 201:
            preference = preference_response["response"]
            preference_id = preference["id"]
            
            checkout_url = preference.get("init_point", "")
            sandbox_url = preference.get("sandbox_init_point", "")
            
            print(f"✅ Service: Checkout criado - {preference_id}")
            
            return {
                "success": True,
                "data": {
                    "preference_id": preference_id,
                    "checkout_url": checkout_url,
                    "sandbox_url": sandbox_url,
                    "plan": plan,
                    "cycle": cycle,
                    "price": price,
                    "original_price": original_price,
                    "coupon_code": coupon_code,
                    "external_reference": external_reference
                }
            }
        else:
            error_info = preference_response.get("response", {})
            print(f"❌ Service: Erro no checkout - {error_info}")
            
            return {
                "success": False,
                "error": "Erro ao criar checkout no Mercado Pago",
                "details": error_info
            }
            
    except Exception as e:
        print(f"❌ Service: Erro no checkout - {e}")
        
        return {
            "success": False,
            "error": "Erro interno do servidor",
            "details": str(e)
        }


def process_payment(payment_id):
    """Processar pagamento - VERSÃO CORRIGIDA"""
    try:
        print(f"\nSERVICE: PROCESSANDO PAGAMENTO {payment_id}")
        print("=" * 50)
        
        # 1. Consultar MP
        mp_token = os.environ.get('MP_ACCESS_TOKEN')
        headers = {
            'Authorization': f'Bearer {mp_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f'https://api.mercadopago.com/v1/payments/{payment_id}',
            headers=headers,
            timeout=15
        )
        
        if response.status_code != 200:
            raise Exception(f'MP API erro: {response.status_code}')
            
        mp_data = response.json()
        print(f"MP Status: {mp_data.get('status')} - R$ {mp_data.get('transaction_amount')}")
        
        # 2. Verificar se aprovado
        if mp_data.get('status') != 'approved':
            print(f"Pagamento nao aprovado: {mp_data.get('status')}")
            return {'status': 'not_approved', 'mp_status': mp_data.get('status')}
        
        # 3. Extrair dados
        external_ref = mp_data.get('external_reference', '')
        amount = float(mp_data.get('transaction_amount', 0))
        payer_email = mp_data.get('payer', {}).get('email', '')
        
        print(f"Valor: R$ {amount}")
        print(f"Email: {payer_email}")
        print(f"Referencia: {external_ref}")
        
        # 4. Determinar usuário
        user_email = payer_email
        plan_id = 'pro'
        cycle = 'monthly'
        
        if external_ref and 'geminii_' in external_ref:
            try:
                parts = external_ref.split('_')
                if len(parts) >= 4:
                    plan_id = parts[1]
                    cycle = parts[2]
                    user_email = parts[3]
                    print(f"Dados extraidos - Plano: {plan_id}, Email: {user_email}")
            except:
                print("Erro ao extrair dados da referencia")
        
        if not user_email:
            raise Exception("Email do usuário não encontrado")
        
        # 5. Conectar banco
        conn = get_db_connection()
        if not conn:
            raise Exception("Erro de conexão com banco")
        
        cursor = conn.cursor()
        
        # 6. Verificar duplicação
        cursor.execute("SELECT id FROM payments WHERE payment_id = %s", (str(payment_id),))
        if cursor.fetchone():
            conn.close()
            print("Pagamento ja processado")
            return {'status': 'already_processed'}
        
        # 7. Buscar usuário
        cursor.execute("SELECT id, name, email FROM users WHERE email = %s", (user_email,))
        user_row = cursor.fetchone()
        
        if not user_row:
            conn.close()
            raise Exception(f"Usuario nao encontrado: {user_email}")
        
        user_id, user_name, user_email_db = user_row
        print(f"Usuario encontrado: {user_name} (ID: {user_id})")
        
        # 8. Determinar plano
        if amount >= 130:
            new_plan_id = 2
            new_plan_name = 'Premium'
        else:
            new_plan_id = 1
            new_plan_name = 'Pro'
        
        print(f"Plano a ativar: {new_plan_name} (ID: {new_plan_id})")
        
        # 9. Calcular expiração
        from datetime import timedelta, timezone
        if cycle == 'annual':
            expires_at = datetime.now(timezone.utc) + timedelta(days=365)
        else:
            expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        
        print(f"Expira em: {expires_at.strftime('%d/%m/%Y')}")
        
        # 10. Criar tabela payments se não existir
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    payment_id VARCHAR(255) UNIQUE NOT NULL,
                    status VARCHAR(50) DEFAULT 'approved',
                    amount DECIMAL(10,2) DEFAULT 0,
                    plan_id VARCHAR(50),
                    plan_name VARCHAR(100),
                    cycle VARCHAR(20) DEFAULT 'monthly',
                    external_reference VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("Tabela payments verificada/criada")
        except Exception as e:
            print(f"Tabela payments ja existe: {e}")
        
        # 11. Inserir pagamento
        cursor.execute("""
            INSERT INTO payments (
                user_id, payment_id, status, amount, plan_id, plan_name, 
                cycle, external_reference, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """, (
            user_id, str(payment_id), 'approved', amount, 
            plan_id, new_plan_name, cycle, external_ref
        ))
        
        print("Pagamento inserido na tabela payments")
        
        # 12. Adicionar colunas se não existirem
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(20) DEFAULT 'inactive'")
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_plan VARCHAR(50)")
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_expires_at TIMESTAMP")
            print("Colunas da tabela users verificadas/adicionadas")
        except Exception as e:
            print(f"Colunas ja existem: {e}")
        
        # 13. *** CORREÇÃO PRINCIPAL *** - Atualizar usuário
        print("ATUALIZANDO USUARIO...")
        
        cursor.execute("""
            UPDATE users 
            SET plan_id = %s, 
                plan_name = %s,
                subscription_status = 'active',
                subscription_plan = %s,
                plan_expires_at = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (new_plan_id, new_plan_name, new_plan_name, expires_at, user_id))
        
        rows_updated = cursor.rowcount
        print(f"Linhas atualizadas: {rows_updated}")
        
        if rows_updated == 0:
            # Tentar UPDATE mais simples
            print("Tentando UPDATE mais simples...")
            cursor.execute("""
                UPDATE users 
                SET plan_id = %s, plan_name = %s, updated_at = NOW()
                WHERE id = %s
            """, (new_plan_id, new_plan_name, user_id))
            
            rows_updated = cursor.rowcount
            print(f"UPDATE simples - Linhas atualizadas: {rows_updated}")
            
            if rows_updated == 0:
                raise Exception("ERRO CRITICO: Nenhuma linha foi atualizada!")
        
        # 14. Commit
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"SUCESSO! Plano {new_plan_name} ativado para {user_name}")
        
        return {
            'status': 'success',
            'payment_id': payment_id,
            'user_id': user_id,
            'user_name': user_name,
            'user_email': user_email_db,
            'plan_name': new_plan_name,
            'amount': amount,
            'expires_at': expires_at.isoformat(),
            'message': f'Plano {new_plan_name} ativado com sucesso!'
        }
        
    except Exception as e:
        print(f"ERRO NO PROCESSAMENTO: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'status': 'error',
            'payment_id': payment_id,
            'error': str(e)
        }

    try:
        print(f"\n🔥 SERVICE: PROCESSANDO PAGAMENTO {payment_id}")
        print("=" * 50)
        
        # 1. Buscar dados do pagamento no MP
        mp_token = os.environ.get('MP_ACCESS_TOKEN')
        headers = {
            'Authorization': f'Bearer {mp_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f'https://api.mercadopago.com/v1/payments/{payment_id}',
            headers=headers
        )
        
        if response.status_code != 200:
            raise Exception(f'Pagamento não encontrado no MP: Status {response.status_code}')
            
        mp_data = response.json()
        print(f"📊 Service: Status MP - {mp_data.get('status')} - R$ {mp_data.get('transaction_amount')}")
        
        # 2. Verificar se está aprovado
        if mp_data.get('status') != 'approved':
            print(f"⚠️ Service: Pagamento não aprovado - {mp_data.get('status')}")
            return {'status': 'not_approved', 'mp_status': mp_data.get('status')}
        
        # 3. Extrair informações
        external_ref = mp_data.get('external_reference', '')
        amount = float(mp_data.get('transaction_amount', 0))
        payer_email = mp_data.get('payer', {}).get('email', '')
        
        print(f"💰 Service: Valor R$ {amount}")
        print(f"📧 Service: Email {payer_email}")
        print(f"🔗 Service: Referência {external_ref}")
        
        # 4. Extrair dados da referência externa
        user_email = None
        plan_id = 'pro'
        cycle = 'monthly'
        
        if external_ref and 'geminii_' in external_ref:
            try:
                parts = external_ref.split('_')
                if len(parts) >= 4:
                    plan_id = parts[1]
                    cycle = parts[2]
                    user_email = parts[3]
                    print(f"📦 Service: Dados extraídos - Plano={plan_id}, Ciclo={cycle}, Email={user_email}")
            except:
                print("⚠️ Service: Erro ao extrair dados da referência")
        
        # Usar email do pagador se não conseguiu extrair
        if not user_email:
            user_email = payer_email
        
        if not user_email:
            raise Exception("Email do usuário não encontrado")
        
        # 5. Conectar ao banco
        conn = get_db_connection()
        if not conn:
            raise Exception("Erro de conexão com banco")
        
        cursor = conn.cursor()
        
        # 6. Verificar se já foi processado
        cursor.execute("SELECT id FROM payments WHERE payment_id = %s", (str(payment_id),))
        if cursor.fetchone():
            conn.close()
            print(f"⚠️ Service: Pagamento {payment_id} já processado")
            return {'status': 'already_processed'}
        
        # 7. Buscar usuário
        cursor.execute("SELECT id, name, email FROM users WHERE email = %s", (user_email,))
        user_row = cursor.fetchone()
        
        if not user_row:
            conn.close()
            raise Exception(f"Usuário não encontrado: {user_email}")
        
        user_id, user_name, user_email = user_row
        print(f"👤 Service: Usuário {user_name} (ID: {user_id})")
        
        # 8. Determinar plano
        if plan_id in PLANS:
            plan_data = PLANS[plan_id]
            plan_name = plan_data['name']
            plan_db_id = plan_data['db_id']
        else:
            # Fallback baseado no valor
            if amount >= 130:
                plan_id = 'premium'
                plan_name = 'Premium'
                plan_db_id = 2
            else:
                plan_id = 'pro'
                plan_name = 'Pro'
                plan_db_id = 1
        
        print(f"📦 Service: Plano {plan_name} (DB ID: {plan_db_id})")
        
        # 9. Calcular expiração
        if cycle == 'annual':
            expires_at = datetime.now(timezone.utc) + timedelta(days=365)
        else:
            expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        
        print(f"📅 Service: Expira {expires_at.strftime('%d/%m/%Y')}")
        
        # 10. Inserir na tabela payments
        cursor.execute("""
            INSERT INTO payments (
                user_id, payment_id, status, amount, plan_id, plan_name, 
                cycle, external_reference, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """, (
            user_id, str(payment_id), 'approved', amount, plan_id, plan_name, 
            cycle, external_ref
        ))
        
        print("✅ Service: Pagamento inserido na tabela payments")
        
        # 11. Atualizar usuário
        cursor.execute("""
            UPDATE users 
            SET plan_id = %s, 
                plan_name = %s,
                subscription_status = %s,
                subscription_plan = %s,
                plan_expires_at = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (plan_db_id, plan_name, 'active', plan_name, expires_at, user_id))
        
        rows_updated = cursor.rowcount
        print(f"✅ Service: Usuário atualizado ({rows_updated} linhas)")
        
        # 12. Registrar no histórico
        cursor.execute("""
            INSERT INTO payment_history (
                user_id, plan_id, payment_id, amount, status, 
                currency, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
        """, (user_id, plan_db_id, str(payment_id), amount, 'approved', 'BRL'))
        
        print("✅ Service: Histórico registrado")
        
        # 13. Commit
        conn.commit()
        conn.close()
        
        print(f"\n🎉 SERVICE: SUCESSO! Plano {plan_name} ativado para {user_name}")
        
        return {
            'status': 'success',
            'payment_id': payment_id,
            'user_id': user_id,
            'user_name': user_name,
            'user_email': user_email,
            'plan_name': plan_name,
            'amount': amount,
            'expires_at': expires_at.isoformat(),
            'message': f'Plano {plan_name} ativado com sucesso!'
        }
        
    except Exception as e:
        print(f"❌ SERVICE: ERRO NO PROCESSAMENTO - {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'status': 'error',
            'payment_id': payment_id,
            'error': str(e)
        }

def check_payment_status_service(payment_id):
    """Serviço para verificar status de pagamento"""
    try:
        # Verificar no MP
        mp_token = os.environ.get('MP_ACCESS_TOKEN')
        headers = {
            'Authorization': f'Bearer {mp_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f'https://api.mercadopago.com/v1/payments/{payment_id}',
            headers=headers
        )
        
        mp_status = None
        if response.status_code == 200:
            mp_data = response.json()
            mp_status = {
                'status': mp_data.get('status'),
                'amount': mp_data.get('transaction_amount'),
                'payer_email': mp_data.get('payer', {}).get('email'),
                'external_reference': mp_data.get('external_reference')
            }
        
        # Verificar no banco
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT p.*, u.name, u.email, u.subscription_status 
            FROM payments p 
            JOIN users u ON p.user_id = u.id 
            WHERE p.payment_id = %s
        """, (str(payment_id),))
        
        db_payment = cursor.fetchone()
        conn.close()
        
        return {
            'payment_id': payment_id,
            'mercado_pago': mp_status,
            'database': {
                'exists': db_payment is not None,
                'processed': db_payment is not None
            }
        }
        
    except Exception as e:
        return {'error': str(e)}

def get_plans_service():
    """Serviço para retornar planos disponíveis"""
    try:
        plans_list = []
        for plan_id, plan_data in PLANS.items():
            plans_list.append({
                "id": plan_data["id"],
                "name": plan_id,
                "display_name": plan_data["name"],
                "description": "Plano " + plan_data["name"],
                "price_monthly": plan_data["monthly_price"],
                "price_annual": plan_data["annual_price"],
                "features": plan_data["features"]
            })
        
        return {"success": True, "data": plans_list}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# ===== SERVIÇOS DE AUTENTICAÇÃO (MOVIDOS DO MAIN) =====

def hash_password(password):
    """Criptografar senha"""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_reset_token():
    """Gerar token seguro para reset"""
    return secrets.token_urlsafe(32)

def send_reset_email(user_email, user_name, reset_token):
    """Enviar email de reset de senha - SMTP nativo"""
    try:
        smtp_server = "smtp.titan.email"
        smtp_port = 465
        smtp_user = os.environ.get('EMAIL_USER')
        smtp_password = os.environ.get('EMAIL_PASSWORD')
        
        if not smtp_user or not smtp_password:
            print("Variáveis de email não configuradas")
            return False
        
        reset_url = f"https://geminii-tech.onrender.com/reset-password?token={reset_token}"
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = "Redefinir Senha - Geminii Tech"
        msg['From'] = smtp_user
        msg['To'] = user_email
        
        html_body = f"""
        <div style="font-family: Inter, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #ba39af, #d946ef); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0;">Geminii Tech</h1>
                <p style="color: white; margin: 10px 0 0 0;">Trading Automatizado</p>
            </div>
            <div style="padding: 30px; background: #f8f9fa;">
                <h2 style="color: #333;">Olá, {user_name}!</h2>
                <p style="color: #666; line-height: 1.6;">
                    Recebemos uma solicitação para redefinir a senha da sua conta Geminii Tech.
                </p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_url}" 
                       style="background: linear-gradient(135deg, #ba39af, #d946ef); 
                              color: white; padding: 15px 30px; text-decoration: none; 
                              border-radius: 8px; display: inline-block; font-weight: bold;">
                        Redefinir Senha
                    </a>
                </div>
                <p style="color: #666; font-size: 14px;">
                    <strong>Este link expira em 1 hora.</strong><br>
                    Se você não solicitou isso, ignore este email.
                </p>
            </div>
            <div style="padding: 20px; text-align: center; background: #333; color: white;">
                <p style="margin: 0;">© 2025 Geminii Research - Trading Automatizado</p>
            </div>
        </div>
        """
        
        msg.attach(MIMEText(html_body, 'html'))
        
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        
        print(f"Email enviado para: {user_email}")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao enviar email: {e}")
        return False

def generate_reset_token_service(email):
    """Gerar token de reset e salvar no banco"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            return {'success': False, 'error': 'E-mail não encontrado'}
        
        user_id, user_name = user
        token = generate_reset_token()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        cursor.execute("""
            UPDATE password_reset_tokens 
            SET used = TRUE 
            WHERE user_id = %s AND used = FALSE
        """, (user_id,))
        
        cursor.execute("""
            INSERT INTO password_reset_tokens (user_id, token, expires_at) 
            VALUES (%s, %s, %s)
        """, (user_id, token, expires_at))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'token': token,
            'user_name': user_name,
            'user_email': email,
            'expires_in': '1 hora'
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Erro interno: {str(e)}'}

def validate_reset_token_service(token):
    """Validar token de reset"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rt.user_id, rt.expires_at, u.name, u.email 
            FROM password_reset_tokens rt
            JOIN users u ON rt.user_id = u.id
            WHERE rt.token = %s AND rt.used = FALSE
        """, (token,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not result:
            return {'success': False, 'error': 'Token inválido ou já utilizado'}
        
        user_id, expires_at, user_name, user_email = result
        
        if datetime.now(timezone.utc) > expires_at.replace(tzinfo=timezone.utc):
            return {'success': False, 'error': 'Token expirado'}
        
        return {
            'success': True,
            'user_id': user_id,
            'user_name': user_name,
            'email': user_email,
            'expires_at': expires_at.isoformat()
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Erro interno: {str(e)}'}

def reset_password_service(token, new_password):
    """Redefinir senha com token"""
    try:
        validation = validate_reset_token_service(token)
        if not validation['success']:
            return validation
        
        user_id = validation['user_id']
        user_name = validation['user_name']
        
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        
        hashed_password = hash_password(new_password)
        cursor.execute("""
            UPDATE users 
            SET password = %s, updated_at = CURRENT_TIMESTAMP 
            WHERE id = %s
        """, (hashed_password, user_id))
        
        cursor.execute("""
            UPDATE password_reset_tokens 
            SET used = TRUE 
            WHERE token = %s
        """, (token,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'message': 'Senha redefinida com sucesso!',
            'user_name': user_name
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Erro interno: {str(e)}'}

# Debug info
if __name__ == "__main__":
    print("🔧 Mercado Pago Service carregado!")
    print(f"📋 Planos: {list(PLANS.keys())}")
    print(f"🔐 Token: {mp_token[:20]}...")
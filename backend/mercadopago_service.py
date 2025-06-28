# mercadopago_service.py - VERSÃO LIMPA E ORGANIZADA
# ====================================================

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
mp_public_key = os.environ.get('MP_PUBLIC_KEY', 'TEST-a5bcc6b2-29d6-4c1e-ad6c-31ce73d0d377')

# Importar SDK do Mercado Pago
mp_sdk = None
preference_client = None

try:
    import mercadopago
    mp_sdk = mercadopago.SDK(mp_token)
    mp_sdk.request_options.timeout = 30
    mp_sdk.request_options.max_retries = 3
    preference_client = mp_sdk.preference()
    print("✅ SDK Mercado Pago carregado com configurações de aprovação!")
except ImportError:
    print("❌ Módulo mercadopago não encontrado. Instale: pip install mercadopago")
except Exception as e:
    print(f"❌ Erro ao carregar SDK: {e}")

# ===== CONFIGURAÇÃO DOS PLANOS =====
PLANS = {
    "basico": {
        "id": "basico",
        "name": "Básico", 
        "db_id": 3,
        "monthly_price": 0,
        "annual_price": 0,
        "features": ["Acesso básico ao sistema", "Dados limitados", "Funcionalidades essenciais"]
    },
    "pro": {
        "id": "pro",
        "name": "Pro", 
        "db_id": 1,
        "monthly_price": 79,
        "annual_price": 72,
        "features": ["Monitor avançado de ações", "RSL e análise técnica avançada", "Backtests automáticos", "Alertas via WhatsApp", "Dados históricos ilimitados", "API para desenvolvedores"]
    },
    "premium": {
        "id": "premium", 
        "name": "Premium",
        "db_id": 2,
        "monthly_price": 149,
        "annual_price": 137,
        "features": ["Tudo do Pro +", "Long & Short strategies", "IA para recomendações", "Consultoria personalizada", "Acesso prioritário", "Relatórios exclusivos"]
    }
}

# ===== FUNÇÕES DE VALIDAÇÃO =====

def validate_device_id(device_id):
    """Validar device ID do frontend"""
    try:
        if not device_id or len(device_id) < 10:
            return False
        if not device_id.startswith('mp-device-'):
            return False
        return True
    except:
        return False

def ensure_tables_exist(cursor):
    """Verificar e criar tabelas necessárias"""
    try:
        print("   🔧 Verificando estrutura do banco...")
        
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
                device_id VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(20) DEFAULT 'inactive'")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_plan VARCHAR(50)")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_expires_at TIMESTAMP")
        
        print("   ✅ Estrutura do banco verificada")
    except Exception as e:
        print(f"   ❌ Erro ao preparar tabelas: {e}")
        raise e

# ===== FUNÇÕES PRINCIPAIS =====

def test_mercadopago_connection():
    """Testar conexão com Mercado Pago"""
    if not mp_sdk or not preference_client:
        return {"success": False, "error": "SDK Mercado Pago não carregado"}
    
    try:
        token = os.environ.get('MP_ACCESS_TOKEN', '')
        if not token:
            return {"success": False, "error": "Token MP_ACCESS_TOKEN não configurado"}
        
        test_preference = {
            "items": [{
                "id": "test",
                "title": "Teste de Conexão - Geminii",
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": 1.0
            }],
            "auto_return": "approved",
            "binary_mode": True
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
            return {"success": False, "error": f"Erro na resposta do MP: {result.get('response', 'Sem detalhes')}"}
            
    except Exception as e:
        return {"success": False, "error": f"Erro ao conectar com MP: {str(e)}"}

def get_plans_service():
    """Retornar planos disponíveis"""
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

def create_checkout_service(plan, cycle, customer_email=None, user_id=None, user_email=None, user_name=None, discounted_price=None, coupon_code=None, device_id=None):
    """Criar checkout com melhorias para aprovação - VERSÃO CORRIGIDA"""
    if not mp_sdk or not preference_client:
        return {"success": False, "error": "SDK Mercado Pago não disponível"}
    
    try:
        if plan not in PLANS:
            return {"success": False, "error": f"Plano '{plan}' não encontrado"}
        
        plan_data = PLANS[plan]
        
        if cycle == 'annual':
            original_price = plan_data["annual_price"]
            cycle_display = "Anual"
        else:
            original_price = plan_data["monthly_price"]
            cycle_display = "Mensal"
        
        price = float(discounted_price) if discounted_price is not None else original_price
        
        
        ## descomentar par ao deploy
        base_url = "https://app.geminii.com.br" if os.environ.get('DATABASE_URL') else "http://localhost:5000"
        
        # Usar temporariamente para testes:
        #base_url = "https://geminii-tech.up.railway.app"
        
        item_title = f"Geminii {plan_data['name']} - {cycle_display}"
        if coupon_code:
            item_title += f" (Cupom: {coupon_code})"
        
        timestamp = int(time.time())
        
        # 🔥 CORREÇÃO PRINCIPAL: USAR USER_ID EM VEZ DE EMAIL
        if user_id:
            external_reference = f"geminii_{plan}_{cycle}_user{user_id}_{timestamp}"
            payer_email = user_email or customer_email or "cliente@geminii.com.br"
            payer_name = user_name or "Cliente Geminii"
        else:
            # Fallback para compatibilidade
            external_reference = f"geminii_{plan}_{cycle}_{customer_email or 'cliente@geminii.com.br'}_{timestamp}"
            payer_email = customer_email or "cliente@geminii.com.br"
            payer_name = "Cliente Geminii"
        
        preference_data = {
            "items": [{
                "id": plan,
                "title": item_title,
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": float(price),
                "description": f"Assinatura {plan_data['name']} - {cycle_display}"
            }],
            "back_urls": {
                "success": f"{base_url}/payment/success",
                "pending": f"{base_url}/payment/pending", 
                "failure": f"{base_url}/payment/failure"
            },
            "external_reference": external_reference,
            "notification_url": f"{base_url}/api/mercadopago/webhook",
            "auto_return": "approved",
            "binary_mode": True,
            "expires": True,
            "expiration_date_from": datetime.now(timezone.utc).isoformat(),
            "expiration_date_to": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
            "payment_methods": {
                "excluded_payment_methods": [],
                "excluded_payment_types": [],
                "installments": 12,
                "default_installments": 1
            }
        }
        
        # 🔥 CORREÇÃO: USAR DADOS REAIS DO USUÁRIO
        if payer_email and payer_email != 'cliente@geminii.com.br':
            preference_data["payer"] = {
                "email": payer_email,
                "name": payer_name
            }
        
        if device_id and validate_device_id(device_id):
            preference_data["additional_info"] = {"device_id": device_id}
            print(f"   ✅ Device ID válido adicionado: {device_id[:20]}...")
        elif device_id:
            print(f"   ⚠️ Device ID inválido ignorado: {device_id}")
        
        print(f"🔄 Criando checkout otimizado para aprovação...")
        print(f"💰 Valor: R$ {price} ({cycle_display})")
        print(f"📧 Email: {payer_email}")
        print(f"👤 User ID: {user_id}")
        print(f"🔗 External Ref: {external_reference}")
        
        preference_response = None
        for attempt in range(3):
            try:
                preference_response = preference_client.create(preference_data)
                break
            except Exception as retry_error:
                print(f"❌ Tentativa {attempt + 1} falhou: {retry_error}")
                if attempt == 2:
                    raise retry_error
                time.sleep(1)
        
        if preference_response and preference_response.get("status") == 201:
            preference = preference_response["response"]
            preference_id = preference["id"]
            
            checkout_url = preference.get("init_point", "")
            sandbox_url = preference.get("sandbox_init_point", "")
            
            print(f"✅ Checkout criado com sucesso - {preference_id}")
            
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
                    "external_reference": external_reference,
                    "device_id": device_id,
                    "user_id": user_id,
                    "user_email": payer_email,
                    "expires_in": "24 horas"
                }
            }
        else:
            error_info = preference_response.get("response", {}) if preference_response else {}
            print(f"❌ Erro no checkout: {error_info}")
            
            return {
                "success": False,
                "error": "Erro ao criar checkout no Mercado Pago",
                "details": error_info
            }
            
    except Exception as e:
        print(f"❌ Erro crítico no checkout: {e}")
        return {"success": False, "error": "Erro interno do servidor", "details": str(e)}

def check_payment_status_service(payment_id):
    """Verificar status de pagamento"""
    try:
        mp_data = get_payment_from_mercadopago(payment_id)
        
        mp_status = None
        if mp_data:
            mp_status = {
                'status': mp_data.get('status'),
                'amount': mp_data.get('transaction_amount'),
                'payer_email': mp_data.get('payer', {}).get('email'),
                'external_reference': mp_data.get('external_reference'),
                'device_id': mp_data.get('additional_info', {}).get('device_id')
            }
        
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

# ===== PROCESSAMENTO DE PAGAMENTOS =====

def get_payment_from_mercadopago(payment_id):
    """Consultar pagamento no Mercado Pago"""
    try:
        mp_token = os.environ.get('MP_ACCESS_TOKEN')
        headers = {
            'Authorization': f'Bearer {mp_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f'https://api.mercadopago.com/v1/payments/{payment_id}',
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Erro MP API: Status {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Erro ao consultar MP: {e}")
        return None

def extract_user_id_from_reference(external_ref):
    """Extrair user_id do external_reference"""
    try:
        # "geminii_premium_annual_user52_1751041790" → 52
        import re
        match = re.search(r'user(\d+)', external_ref)
        return int(match.group(1)) if match else None
    except:
        return None

def extract_payment_data(mp_data):
    """Extrair dados relevantes do pagamento - VERSÃO CORRIGIDA"""
    amount = float(mp_data.get('transaction_amount', 0))
    external_ref = mp_data.get('external_reference', '')
    payer_email = mp_data.get('payer', {}).get('email', '')
    
    # 🔥 CORREÇÃO PRINCIPAL: PRIORIZAR USER_ID DO EXTERNAL_REFERENCE
    user_id = extract_user_id_from_reference(external_ref)
    
    # Extrair dados do external_reference
    plan_id = 'pro'
    cycle = 'monthly'
    
    if external_ref and 'geminii_' in external_ref:
        try:
            parts = external_ref.split('_')
            if len(parts) >= 3:
                plan_id = parts[1]  # premium, pro
                cycle = parts[2]    # annual, monthly
        except:
            pass
    
    # Determinar plano baseado no valor
    if amount >= 130:
        plan_id = 'premium'
        plan_name = 'Premium'
        plan_db_id = 2
    else:
        plan_id = 'pro'
        plan_name = 'Pro'
        plan_db_id = 1
    
    # Usar dados do PLANS se disponível
    if plan_id in PLANS:
        plan_data = PLANS[plan_id]
        plan_name = plan_data['name']
        plan_db_id = plan_data['db_id']
    
    return {
        'amount': amount,
        'user_id': user_id,           # 🔥 NOVO: Priorizar user_id
        'user_email': payer_email,    # Backup por email
        'plan_id': plan_id,
        'plan_name': plan_name,
        'plan_db_id': plan_db_id,
        'cycle': cycle,
        'external_reference': external_ref,
        'search_strategy': 'user_id' if user_id else 'email'  # Para debug
    }

def find_or_create_user(cursor, payment_data):
    """Buscar usuário por ID ou email - VERSÃO CORRIGIDA"""
    user_id = payment_data.get('user_id')
    user_email = payment_data.get('user_email')
    
    print(f"🔍 Buscando usuário...")
    print(f"   Strategy: {payment_data.get('search_strategy', 'unknown')}")
    print(f"   User ID: {user_id}")
    print(f"   Email: {user_email}")
    
    # 🔥 ESTRATÉGIA 1: BUSCAR POR USER_ID (PRIORIDADE)
    if user_id:
        cursor.execute("SELECT id, name, email FROM users WHERE id = %s", (user_id,))
        result = cursor.fetchone()
        
        if result:
            print(f"✅ Usuário encontrado por ID: {result[1]} (ID: {result[0]})")
            return {'id': result[0], 'name': result[1], 'email': result[2]}
        else:
            print(f"❌ Usuário ID {user_id} não encontrado")
    
    # 🔥 ESTRATÉGIA 2: BUSCAR POR EMAIL (FALLBACK)
    if user_email:
        cursor.execute("SELECT id, name, email FROM users WHERE LOWER(email) = LOWER(%s)", (user_email,))
        result = cursor.fetchone()
        
        if result:
            print(f"✅ Usuário encontrado por email: {result[1]} (ID: {result[0]})")
            return {'id': result[0], 'name': result[1], 'email': result[2]}
        else:
            print(f"❌ Usuário email {user_email} não encontrado")
    
    # 🔥 ESTRATÉGIA 3: BUSCAR USUÁRIOS RECENTES (ÚLTIMO RECURSO)
    print("🔍 Tentando encontrar usuário recente...")
    cursor.execute("""
        SELECT id, name, email FROM users 
        WHERE created_at > NOW() - INTERVAL '7 days'
        AND plan_name = 'Básico'
        ORDER BY created_at DESC 
        LIMIT 5
    """)
    
    recent_users = cursor.fetchall()
    if recent_users:
        print(f"📋 Usuários recentes encontrados: {len(recent_users)}")
        for user in recent_users:
            print(f"   - {user[1]} ({user[2]}) - ID: {user[0]}")
        
        # Por enquanto, não auto-selecionar
        # return {'id': recent_users[0][0], 'name': recent_users[0][1], 'email': recent_users[0][2]}
    
    print(f"❌ Nenhum usuário encontrado - ID: {user_id}, Email: {user_email}")
    return None

def calculate_expiration(cycle):
    """Calcular data de expiração"""
    if cycle == 'annual':
        return datetime.now(timezone.utc) + timedelta(days=365)
    else:
        return datetime.now(timezone.utc) + timedelta(days=30)

def update_user_plan(cursor, user_id, plan_db_id, plan_name, expires_at):
    """Atualizar plano do usuário"""
    print(f"   🔄 Atualizando usuário {user_id} para plano {plan_name}")
    
    cursor.execute("""
        UPDATE users 
        SET plan_id = %s, 
            plan_name = %s,
            subscription_status = 'active',
            subscription_plan = %s,
            plan_expires_at = %s,
            updated_at = NOW()
        WHERE id = %s
    """, (plan_db_id, plan_name, plan_name, expires_at, user_id))
    
    rows_updated = cursor.rowcount
    print(f"   ✅ {rows_updated} linha(s) atualizada(s)")
    
    if rows_updated == 0:
        raise Exception("ERRO: Nenhuma linha foi atualizada!")

def insert_payment_record(cursor, payment_id, user_id, payment_data, device_id=None):
    """Inserir registro na tabela payments"""
    cursor.execute("""
        INSERT INTO payments (
            user_id, payment_id, status, amount, plan_id, plan_name, 
            cycle, external_reference, device_id, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
    """, (
        user_id, str(payment_id), 'approved', payment_data['amount'],
        payment_data['plan_id'], payment_data['plan_name'], 
        payment_data['cycle'], payment_data['external_reference'], device_id
    ))
    print("   ✅ Pagamento inserido na tabela payments")

def insert_payment_history(cursor, user_id, payment_data, payment_id):
    """Inserir histórico de pagamento"""
    try:
        cursor.execute("""
            INSERT INTO payment_history (
                user_id, plan_id, payment_id, amount, status, 
                currency, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (payment_id) DO NOTHING
        """, (
            user_id, payment_data['plan_db_id'], str(payment_id), 
            payment_data['amount'], 'approved', 'BRL'
        ))
        print("   ✅ Histórico registrado")
    except Exception as e:
        print(f"   ⚠️ Erro no histórico (não crítico): {e}")

def process_payment(payment_id):
    """Função principal - processamento com melhorias para aprovação"""
    print(f"\n🔥 PROCESSANDO PAYMENT ID: {payment_id}")
    
    try:
        # 1. Consultar Mercado Pago
        mp_data = None
        for attempt in range(3):
            mp_data = get_payment_from_mercadopago(payment_id)
            if mp_data:
                break
            time.sleep(2)
        
        if not mp_data:
            return {'status': 'error', 'error': 'Pagamento não encontrado no Mercado Pago'}
        
        if mp_data.get('status') != 'approved':
            return {'status': 'not_approved', 'mp_status': mp_data.get('status')}
        
        # 2. Validar Device ID se presente
        device_info = mp_data.get('additional_info', {})
        device_id = device_info.get('device_id')
        
        if device_id and validate_device_id(device_id):
            print(f"   ✅ Device ID válido: {device_id[:20]}...")
        
        # 3. Extrair dados
        payment_data = extract_payment_data(mp_data)
        
        # 4. Conectar banco
        conn = get_db_connection()
        if not conn:
            return {'status': 'error', 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        
        # Verificar duplicação
        cursor.execute("SELECT id FROM payments WHERE payment_id = %s", (str(payment_id),))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return {'status': 'already_processed'}
        
        # 5. Buscar usuário
        user_data = find_or_create_user(cursor, payment_data)
        # LINHAS 46-49 (CORRIGIDAS):
        if not user_data:
            cursor.close()
            conn.close()
            
            # Mensagem de erro mais informativa
            user_id = payment_data.get('user_id')
            user_email = payment_data.get('user_email')
            
            if user_id:
                error_msg = f'Usuário não encontrado - ID: {user_id}, Email: {user_email}'
            else:
                error_msg = f'Usuário não encontrado - Email: {user_email}'
            
            return {'status': 'error', 'error': error_msg, 'payment_data': payment_data}
        
        # 6. Processar
        ensure_tables_exist(cursor)
        expires_at = calculate_expiration(payment_data['cycle'])
        insert_payment_record(cursor, payment_id, user_data['id'], payment_data, device_id)
        update_user_plan(cursor, user_data['id'], payment_data['plan_db_id'], payment_data['plan_name'], expires_at)
        insert_payment_history(cursor, user_data['id'], payment_data, payment_id)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ PROCESSAMENTO CONCLUÍDO COM SUCESSO!")
        
        return {
            'status': 'success',
            'payment_id': payment_id,
            'user_id': user_data['id'],
            'user_name': user_data['name'],
            'user_email': user_data['email'],
            'plan_name': payment_data['plan_name'],
            'amount': payment_data['amount'],
            'expires_at': expires_at.isoformat(),
            'device_id': device_id,
            'message': f'Plano {payment_data["plan_name"]} ativado com sucesso!'
        }
        
    except Exception as e:
        print(f"❌ ERRO CRÍTICO: {str(e)}")
        return {'status': 'error', 'payment_id': payment_id, 'error': str(e)}

# ===== FUNÇÕES DE AUTENTICAÇÃO =====

def hash_password(password):
    """Criptografar senha"""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_reset_token():
    """Gerar token seguro para reset"""
    return secrets.token_urlsafe(32)

def send_reset_email(user_email, user_name, reset_token):
    """Enviar email de reset de senha"""
    try:
        smtp_server = "smtp.titan.email"
        smtp_port = 465
        smtp_user = os.environ.get('EMAIL_USER')
        smtp_password = os.environ.get('EMAIL_PASSWORD')
        
        if not smtp_user or not smtp_password:
            print("Variáveis de email não configuradas")
            return False
        
        reset_url = f"https://app.geminii.com.br/reset-password?token={reset_token}"
        
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

def validate_coupon(code, plan_name, user_id):
    """Validar cupom de desconto"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'valid': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, discount_percent, discount_type, max_uses, current_uses, 
                   expires_at, applicable_plans, min_amount
            FROM coupons 
            WHERE code = %s AND active = TRUE
        """, (code.upper(),))
        
        coupon = cursor.fetchone()
        
        if not coupon:
            cursor.close()
            conn.close()
            return {'valid': False, 'error': 'Cupom não encontrado ou inativo'}
        
        coupon_id, discount_percent, discount_type, max_uses, current_uses, expires_at, applicable_plans, min_amount = coupon
        
        if expires_at and datetime.now(timezone.utc) > expires_at.replace(tzinfo=timezone.utc):
            cursor.close()
            conn.close()
            return {'valid': False, 'error': 'Cupom expirado'}
        
        if max_uses and current_uses >= max_uses:
            cursor.close()
            conn.close()
            return {'valid': False, 'error': 'Cupom esgotado'}
        
        cursor.execute("""
            SELECT id FROM coupon_uses 
            WHERE coupon_id = %s AND user_id = %s
        """, (coupon_id, user_id))
        
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return {'valid': False, 'error': 'Cupom já utilizado'}
        
        cursor.close()
        conn.close()
        
        return {
            'valid': True,
            'coupon_id': coupon_id,
            'discount_percent': discount_percent,
            'discount_type': discount_type,
            'applicable_plans': applicable_plans.split(',') if applicable_plans else []
        }
        
    except Exception as e:
        return {'valid': False, 'error': f'Erro interno: {str(e)}'}

# ===== DEBUG E INFORMAÇÕES =====

if __name__ == "__main__":
    print("🔥 MercadoPago Service LIMPO E ORGANIZADO!")
    print(f"📋 Planos: {list(PLANS.keys())}")
    print("✅ Device ID validation: Implementado")
    print("✅ SDK optimizations: Configurado") 
    print("✅ Retry logic: Ativo")
    print("✅ Tables management: Automático")
    print("✅ Password reset: Implementado")
    print("✅ Coupon system: Implementado")
    
    if mp_sdk:
        test_result = test_mercadopago_connection()
        if test_result['success']:
            print("✅ Conexão MP: OK")
        else:
            print(f"❌ Conexão MP: {test_result['error']}")
    
    print("\n🎯 SERVIÇO COMPLETO E PRONTO PARA APROVAÇÃO!")

print("🚀 MercadoPago Service carregado completamente!")
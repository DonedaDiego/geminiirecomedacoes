# ============================================
# MERCADOPAGO_SERVICE.PY - VERSÃO CORRIGIDA
# ============================================

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

# ===== FUNÇÃO PRINCIPAL DE PROCESSAMENTO =====

def process_payment(payment_id):
    """
    Processar pagamento do Mercado Pago - VERSÃO SIMPLIFICADA E CORRIGIDA
    """
    print("\n" + "="*60)
    print(f"🔥 INICIANDO PROCESSAMENTO DO PAGAMENTO: {payment_id}")
    print("="*60)
    
    try:
        # 1. CONSULTAR MERCADO PAGO
        print("📡 1. Consultando Mercado Pago...")
        mp_data = get_payment_from_mercadopago(payment_id)
        
        if not mp_data:
            return {'status': 'error', 'error': 'Pagamento não encontrado no Mercado Pago'}
        
        print(f"   Status MP: {mp_data.get('status')}")
        print(f"   Valor: R$ {mp_data.get('transaction_amount')}")
        
        # 2. VERIFICAR SE ESTÁ APROVADO
        if mp_data.get('status') != 'approved':
            print(f"⚠️ Pagamento não aprovado: {mp_data.get('status')}")
            return {'status': 'not_approved', 'mp_status': mp_data.get('status')}
        
        # 3. EXTRAIR DADOS BÁSICOS
        print("📋 2. Extraindo dados...")
        payment_data = extract_payment_data(mp_data)
        print(f"   Email: {payment_data['user_email']}")
        print(f"   Valor: R$ {payment_data['amount']}")
        print(f"   Plano detectado: {payment_data['plan_name']}")
        
        # 4. CONECTAR BANCO E VERIFICAR DUPLICAÇÃO
        print("🗄️ 3. Conectando ao banco...")
        conn = get_db_connection()
        if not conn:
            return {'status': 'error', 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        
        # Verificar se já foi processado
        cursor.execute("SELECT id FROM payments WHERE payment_id = %s", (str(payment_id),))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            print("⚠️ Pagamento já processado anteriormente")
            return {'status': 'already_processed'}
        
        # 5. BUSCAR USUÁRIO
        print("👤 4. Buscando usuário...")
        user_data = find_or_create_user(cursor, payment_data['user_email'])
        
        if not user_data:
            cursor.close()
            conn.close()
            return {'status': 'error', 'error': f'Usuário não encontrado: {payment_data["user_email"]}'}
        
        print(f"   Usuário: {user_data['name']} (ID: {user_data['id']})")
        
        # 6. PREPARAR TABELAS
        print("🔧 5. Preparando estrutura do banco...")
        ensure_tables_exist(cursor)
        
        # 7. CALCULAR EXPIRAÇÃO
        expires_at = calculate_expiration(payment_data['cycle'])
        print(f"   Expira em: {expires_at.strftime('%d/%m/%Y')}")
        
        # 8. INSERIR PAGAMENTO
        print("💾 6. Registrando pagamento...")
        insert_payment_record(cursor, payment_id, user_data['id'], payment_data)
        
        # 9. ATUALIZAR USUÁRIO
        print("🔄 7. Atualizando plano do usuário...")
        update_user_plan(cursor, user_data['id'], payment_data['plan_id'], payment_data['plan_name'], expires_at)
        
        # 10. REGISTRAR HISTÓRICO
        print("📝 8. Registrando histórico...")
        insert_payment_history(cursor, user_data['id'], payment_data, payment_id)
        
        # 11. COMMIT
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ PROCESSAMENTO CONCLUÍDO COM SUCESSO!")
        print(f"   Plano {payment_data['plan_name']} ativado para {user_data['name']}")
        
        return {
            'status': 'success',
            'payment_id': payment_id,
            'user_id': user_data['id'],
            'user_name': user_data['name'],
            'user_email': user_data['email'],
            'plan_name': payment_data['plan_name'],
            'amount': payment_data['amount'],
            'expires_at': expires_at.isoformat(),
            'message': f'Plano {payment_data["plan_name"]} ativado com sucesso!'
        }
        
    except Exception as e:
        print(f"❌ ERRO CRÍTICO: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'status': 'error',
            'payment_id': payment_id,
            'error': str(e)
        }

# ===== FUNÇÕES AUXILIARES =====

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

def extract_payment_data(mp_data):
    """Extrair dados relevantes do pagamento"""
    amount = float(mp_data.get('transaction_amount', 0))
    external_ref = mp_data.get('external_reference', '')
    payer_email = mp_data.get('payer', {}).get('email', '')
    
    # Extrair dados da referência externa
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
        except:
            pass
    
    # Determinar plano baseado no valor se não conseguiu extrair
    if amount >= 130:
        plan_id = 'premium'
        plan_name = 'Premium'
        plan_db_id = 2
    else:
        plan_id = 'pro'
        plan_name = 'Pro'
        plan_db_id = 1
    
    # Se conseguiu extrair da referência, usar os dados dos PLANS
    if plan_id in PLANS:
        plan_data = PLANS[plan_id]
        plan_name = plan_data['name']
        plan_db_id = plan_data['db_id']
    
    return {
        'amount': amount,
        'user_email': user_email,
        'plan_id': plan_id,
        'plan_name': plan_name,
        'plan_db_id': plan_db_id,
        'cycle': cycle,
        'external_reference': external_ref
    }

def find_or_create_user(cursor, email):
    """Buscar usuário por email"""
    cursor.execute("SELECT id, name, email FROM users WHERE email = %s", (email,))
    result = cursor.fetchone()
    
    if result:
        return {
            'id': result[0],
            'name': result[1],
            'email': result[2]
        }
    return None

def ensure_tables_exist(cursor):
    """Garantir que todas as tabelas necessárias existem"""
    try:
        # Tabela payments
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
        
        # Colunas adicionais na tabela users
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(20) DEFAULT 'inactive'")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_plan VARCHAR(50)")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_expires_at TIMESTAMP")
        
        print("   ✅ Estrutura do banco verificada")
        
    except Exception as e:
        print(f"   ⚠️ Erro ao preparar tabelas: {e}")

def calculate_expiration(cycle):
    """Calcular data de expiração"""
    if cycle == 'annual':
        return datetime.now(timezone.utc) + timedelta(days=365)
    else:
        return datetime.now(timezone.utc) + timedelta(days=30)

def insert_payment_record(cursor, payment_id, user_id, payment_data):
    """Inserir registro na tabela payments"""
    cursor.execute("""
        INSERT INTO payments (
            user_id, payment_id, status, amount, plan_id, plan_name, 
            cycle, external_reference, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
    """, (
        user_id, 
        str(payment_id), 
        'approved', 
        payment_data['amount'],
        payment_data['plan_id'], 
        payment_data['plan_name'], 
        payment_data['cycle'], 
        payment_data['external_reference']
    ))
    print("   ✅ Pagamento inserido na tabela payments")

def update_user_plan(cursor, user_id, plan_db_id, plan_name, expires_at):
    """Atualizar plano do usuário"""
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
    print(f"   ✅ Usuário atualizado ({rows_updated} linhas)")
    
    if rows_updated == 0:
        raise Exception("ERRO CRÍTICO: Nenhuma linha foi atualizada na tabela users!")

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
            user_id, 
            payment_data['plan_db_id'], 
            str(payment_id), 
            payment_data['amount'], 
            'approved', 
            'BRL'
        ))
        print("   ✅ Histórico registrado")
    except Exception as e:
        print(f"   ⚠️ Erro no histórico (não crítico): {e}")

# ===== OUTRAS FUNÇÕES (mantidas como estavam) =====

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
                "title": "Teste de Conexão",
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": 1.0
            }]
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

def create_checkout_service(plan, cycle, customer_email, discounted_price=None, coupon_code=None):
    """Serviço para criar checkout"""
    if not mp_sdk or not preference_client:
        return {"success": False, "error": "SDK Mercado Pago não disponível"}
    
    try:
        # Validar plano
        if plan not in PLANS:
            return {"success": False, "error": f"Plano '{plan}' não encontrado"}
        
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
            "items": [{
                "id": plan,
                "title": item_title,
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": float(price)
            }],
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
            preference_data["payer"] = {"email": customer_email}
        
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
        return {"success": False, "error": "Erro interno do servidor", "details": str(e)}

def check_payment_status_service(payment_id):
    """Serviço para verificar status de pagamento"""
    try:
        # Verificar no MP
        mp_data = get_payment_from_mercadopago(payment_id)
        
        mp_status = None
        if mp_data:
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
    print("🔧 Mercado Pago Service CORRIGIDO carregado!")
    print(f"📋 Planos: {list(PLANS.keys())}")

# ============================================
# MERCADOPAGO_ROUTES.PY - VERSÃO CORRIGIDA
# ============================================

from flask import Blueprint, request, jsonify
from datetime import datetime
import mercadopago_service

# ===== CONFIGURAÇÃO DO BLUEPRINT =====
mercadopago_bp = Blueprint('mercadopago', __name__, url_prefix='/api/mercadopago')

# ===== ROTAS =====

@mercadopago_bp.route('/test', methods=['GET'])
def test_connection():
    """Testar conexão com Mercado Pago"""
    result = mercadopago_service.test_mercadopago_connection()
    return jsonify(result)

@mercadopago_bp.route('/plans', methods=['GET'])
def get_plans():
    """Retornar planos disponíveis"""
    result = mercadopago_service.get_plans_service()
    return jsonify(result)

@mercadopago_bp.route('/checkout/create', methods=['POST'])
def create_checkout():
    """Criar checkout do Mercado Pago"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "Dados JSON são obrigatórios"
            }), 400
        
        # Extrair dados
        plan = data.get('plan', 'pro')
        cycle = data.get('cycle', 'monthly')
        customer_email = data.get('customer_email', 'cliente@geminii.com.br')
        discounted_price = data.get('discounted_price')
        coupon_code = data.get('coupon_code')
        
        # Chamar serviço
        result = mercadopago_service.create_checkout_service(
            plan, cycle, customer_email, discounted_price, coupon_code
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Erro interno do servidor",
            "details": str(e)
        }), 500

@mercadopago_bp.route('/webhook', methods=['POST', 'GET'])
def webhook():
    """WEBHOOK PRINCIPAL - VERSÃO SIMPLIFICADA"""
    
    if request.method == 'GET':
        return jsonify({
            'status': 'webhook_active',
            'service': 'mercadopago',
            'timestamp': datetime.now().isoformat()
        })
    
    print("\n" + "🔔" + "="*50)
    print(f"WEBHOOK RECEBIDO - {datetime.now()}")
    print("="*51)
    
    try:
        # 1. OBTER DADOS DO WEBHOOK
        data = request.get_json()
        if not data:
            print("❌ Webhook sem dados JSON")
            return jsonify({"error": "No data"}), 400
        
        print(f"📋 Tipo: {data.get('type')}")
        print(f"📋 Dados: {data}")
        
        # 2. VERIFICAR SE É PAGAMENTO
        webhook_type = data.get("type")
        
        if webhook_type != "payment":
            print(f"⚠️ Webhook ignorado: {webhook_type}")
            return jsonify({
                "success": True, 
                "message": f"Webhook '{webhook_type}' ignorado"
            }), 200
        
        # 3. EXTRAIR ID DO PAGAMENTO
        payment_data = data.get("data", {})
        payment_id = payment_data.get("id")
        
        if not payment_id:
            print("❌ Payment ID ausente")
            return jsonify({"error": "Payment ID missing"}), 400
        
        print(f"💳 Payment ID: {payment_id}")
        
        # 4. PROCESSAR PAGAMENTO
        print("🔄 Iniciando processamento...")
        result = mercadopago_service.process_payment(payment_id)
        
        # 5. RETORNAR RESPOSTA BASEADA NO RESULTADO
        if result['status'] == 'success':
            print("✅ WEBHOOK: Processamento bem-sucedido!")
            return jsonify({
                "success": True,
                "message": "Pagamento processado e plano ativado!",
                "payment_id": payment_id,
                "user_plan": result.get('plan_name'),
                "user_name": result.get('user_name')
            }), 200
        
        elif result['status'] == 'already_processed':
            print("⚠️ WEBHOOK: Pagamento já processado")
            return jsonify({
                "success": True,
                "message": "Pagamento já processado",
                "payment_id": payment_id
            }), 200
        
        elif result['status'] == 'not_approved':
            print(f"⚠️ WEBHOOK: Pagamento não aprovado: {result.get('mp_status')}")
            return jsonify({
                "success": True,
                "message": f"Pagamento não aprovado: {result.get('mp_status')}",
                "payment_id": payment_id
            }), 200
        
        else:
            print(f"❌ WEBHOOK: Erro no processamento: {result.get('error')}")
            return jsonify({
                "success": False,
                "error": result.get('error', 'Erro no processamento'),
                "payment_id": payment_id
            }), 500
        
    except Exception as e:
        print(f"❌ WEBHOOK: ERRO CRÍTICO - {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            "success": False,
            "error": f"Erro interno: {str(e)}"
        }), 500

@mercadopago_bp.route('/payment/status/<payment_id>')
def check_payment_status(payment_id):
    """Verificar status de pagamento"""
    try:
        result = mercadopago_service.check_payment_status_service(payment_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ===== FUNÇÃO DE EXPORT =====

def get_mercadopago_blueprint():
    """Retornar blueprint"""
    return mercadopago_bp

# Para compatibilidade - funções que o main.py ainda pode chamar
def process_payment(payment_id):
    """Wrapper para compatibilidade com main.py"""
    return mercadopago_service.process_payment(payment_id)

def create_payments_table():
    """Função vazia para compatibilidade"""
    print("✅ create_payments_table: Tabela já existe via database.py")
    return True

def add_plan_expires_field():
    """Função vazia para compatibilidade"""
    print("✅ add_plan_expires_field: Campo já existe via database.py")
    return True

# ============================================
# SCRIPT DE TESTE PARA DEBUGGING
# ============================================

def test_webhook_locally():
    """Função para testar o webhook localmente"""
    print("\n🧪 TESTANDO WEBHOOK LOCALMENTE")
    print("="*40)
    
    # Simular dados do webhook
    test_payment_id = "123456789"
    
    print(f"🔄 Testando com Payment ID: {test_payment_id}")
    
    result = mercadopago_service.process_payment(test_payment_id)
    
    print(f"📊 Resultado: {result}")
    
    return result

def debug_database_structure():
    """Verificar estrutura do banco"""
    print("\n🗄️ VERIFICANDO ESTRUTURA DO BANCO")
    print("="*40)
    
    try:
        from database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verificar tabela users
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'users'
            ORDER BY ordinal_position
        """)
        
        print("📋 Colunas da tabela users:")
        for row in cursor.fetchall():
            print(f"   - {row[0]} ({row[1]})")
        
        # Verificar tabela payments
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'payments'
            ORDER BY ordinal_position
        """)
        
        payments_columns = cursor.fetchall()
        print(f"\n📋 Tabela payments existe: {len(payments_columns) > 0}")
        if payments_columns:
            for row in payments_columns:
                print(f"   - {row[0]} ({row[1]})")
        
        # Verificar tabela payment_history
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'payment_history'
            ORDER BY ordinal_position
        """)
        
        history_columns = cursor.fetchall()
        print(f"\n📋 Tabela payment_history existe: {len(history_columns) > 0}")
        if history_columns:
            for row in history_columns:
                print(f"   - {row[0]} ({row[1]})")
        
        cursor.close()
        conn.close()
        
        print("\n✅ Verificação concluída!")
        
    except Exception as e:
        print(f"❌ Erro na verificação: {e}")

# Debug info
if __name__ == "__main__":
    print("🔧 Mercado Pago Routes CORRIGIDO carregado!")
    print("📋 Rotas disponíveis:")
    print("   - POST /api/mercadopago/webhook")
    print("   - GET  /api/mercadopago/test")
    print("   - POST /api/mercadopago/checkout/create")
    print("   - GET  /api/mercadopago/payment/status/<id>")
    
    # Executar testes se necessário
    # debug_database_structure()
    # test_webhook_locally()
# database.py - VERSÃO CORRIGIDA E SINCRONIZADA
# ==================================================

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone

def get_db_connection():
    """Conectar com PostgreSQL (local ou Railway)"""
    try:
        database_url = os.environ.get("DATABASE_URL")
        
        if database_url:
            conn = psycopg2.connect(database_url, sslmode='require')
        else:
            conn = psycopg2.connect(
                host=os.environ.get("DB_HOST", "localhost"),
                database=os.environ.get("DB_NAME", "postgres"),
                user=os.environ.get("DB_USER", "postgres"),
                password=os.environ.get("DB_PASSWORD", "#geminii"),
                port=os.environ.get("DB_PORT", "5432")
            )
        return conn
    except Exception as e:
        print(f"❌ Erro ao conectar no banco: {e}")
        return None

def test_connection():
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            cursor.close()
            conn.close()
            print(f"✅ Conectado no PostgreSQL: {version[0]}")
            return True
        else:
            print("❌ Falha na conexão")
            return False
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        return False

def create_plans_table():
    """🔥 Criar tabela de planos SINCRONIZADA com o service"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) UNIQUE NOT NULL,
                display_name VARCHAR(100) NOT NULL,
                price_monthly DECIMAL(10,2) NOT NULL,
                price_annual DECIMAL(10,2) NOT NULL,
                description TEXT,
                features TEXT[],
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # 🔥 LIMPAR E RECRIAR PLANOS EXATAMENTE COMO NO SERVICE
        cursor.execute("DELETE FROM plans")
        
        cursor.execute("""
            INSERT INTO plans (id, name, display_name, price_monthly, price_annual, description, features) VALUES
            (1, 'pro', 'Pro', 79.00, 72.00, 'Para quem já investe e quer se posicionar melhor', 
             ARRAY['Monitor avançado de ações', 'RSL e análise técnica avançada', 'Backtests automáticos', 'Alertas via WhatsApp', 'Dados históricos ilimitados', 'API para desenvolvedores']),
            (2, 'premium', 'Premium', 149.00, 137.00, 'Para investidores experientes que querem diferenciais', 
             ARRAY['Tudo do Pro +', 'Long & Short strategies', 'IA para recomendações', 'Consultoria personalizada', 'Acesso prioritário', 'Relatórios exclusivos']),
            (3, 'basico', 'Básico', 0.00, 0.00, 'Acesso básico ao sistema', 
             ARRAY['Acesso básico ao sistema', 'Dados limitados', 'Funcionalidades essenciais']);
        """)
        
        # Resetar sequence
        cursor.execute("SELECT setval('plans_id_seq', 3, true)")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Planos sincronizados: Pro (id=1), Premium (id=2), Básico (id=3)")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar planos: {e}")
        return False

def create_users_table():
    """🔥 Criar tabela users COM TODOS OS CAMPOS NECESSÁRIOS PARA O SERVICE"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                plan_id INTEGER DEFAULT 1,
                plan_name VARCHAR(50) DEFAULT 'Pro',
                user_type VARCHAR(20) DEFAULT 'regular',
                
                -- 🔥 CAMPOS NECESSÁRIOS PARA O MERCADO PAGO SERVICE
                subscription_status VARCHAR(20) DEFAULT 'inactive',
                subscription_plan VARCHAR(50),
                plan_expires_at TIMESTAMP,
                
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_type ON users(user_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_subscription ON users(subscription_status);")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Tabela 'users' criada com TODOS os campos necessários!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabela users: {e}")
        return False

def update_users_table_for_service():
    """🔥 Atualizar tabela users existente para compatibilidade com o service"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        print("🔧 Atualizando tabela users para compatibilidade com MercadoPago service...")
        
        # Adicionar campos necessários para o service
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(20) DEFAULT 'inactive'")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_plan VARCHAR(50)")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_expires_at TIMESTAMP")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS user_type VARCHAR(20) DEFAULT 'regular'")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        
        # Atualizar dados existentes
        cursor.execute("""
            UPDATE users 
            SET subscription_plan = plan_name,
                registration_date = COALESCE(registration_date, created_at)
            WHERE subscription_plan IS NULL OR registration_date IS NULL
        """)
        
        # Criar índices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_subscription ON users(subscription_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_type ON users(user_type)")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Tabela users atualizada para compatibilidade com o service!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao atualizar tabela users: {e}")
        return False

def create_payments_table():
    """🔥 Criar tabela payments EXATAMENTE como o service espera"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
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
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_payment_id ON payments(payment_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status)")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Tabela 'payments' criada exatamente como o service espera!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabela payments: {e}")
        return False

def create_payment_history():
    """🔥 Criar tabela payment_history com CONFLICT handling correto"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payment_history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                plan_id INTEGER,
                payment_id VARCHAR(255) UNIQUE,
                amount DECIMAL(10,2) NOT NULL,
                currency VARCHAR(3) DEFAULT 'BRL',
                status VARCHAR(50) NOT NULL,
                payment_method VARCHAR(50),
                coupon_code VARCHAR(50),
                discount_amount DECIMAL(10,2) DEFAULT 0,
                subscription_id VARCHAR(255),
                is_recurring BOOLEAN DEFAULT false,
                next_billing_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_payment_user ON payment_history(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_payment_status ON payment_history(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_payment_payment_id ON payment_history(payment_id)")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Tabela 'payment_history' criada!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar payment_history: {e}")
        return False

def create_coupons_table():
    """🔥 Criar sistema de cupons SINCRONIZADO com o service"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Tabela de cupons
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS coupons (
                id SERIAL PRIMARY KEY,
                code VARCHAR(50) UNIQUE NOT NULL,
                discount_percent DECIMAL(5,2) NOT NULL CHECK (discount_percent > 0 AND discount_percent <= 100),
                discount_type VARCHAR(20) DEFAULT 'percent',
                max_uses INTEGER DEFAULT NULL,
                current_uses INTEGER DEFAULT 0,
                expires_at TIMESTAMP,
                applicable_plans VARCHAR(255),
                min_amount DECIMAL(10,2) DEFAULT 0,
                active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 🔥 TABELA coupon_uses (não coupon_usage) - como o service espera
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS coupon_uses (
                id SERIAL PRIMARY KEY,
                coupon_id INTEGER REFERENCES coupons(id) ON DELETE CASCADE,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                plan_name VARCHAR(50) NOT NULL,
                original_price DECIMAL(10,2) NOT NULL,
                discount_amount DECIMAL(10,2) NOT NULL,
                final_price DECIMAL(10,2) NOT NULL,
                payment_id VARCHAR(255),
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(coupon_id, user_id)
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_coupons_code ON coupons(code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_coupons_active ON coupons(active)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_coupon_uses_user ON coupon_uses(user_id)")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Sistema de cupons criado (sincronizado com service)!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar sistema de cupons: {e}")
        return False

def create_password_reset_table():
    """Criar tabela para tokens de reset de senha"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                token VARCHAR(255) UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reset_tokens_token ON password_reset_tokens(token)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reset_tokens_expires ON password_reset_tokens(expires_at)")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Tabela 'password_reset_tokens' criada!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabela de reset: {e}")
        return False

def create_initial_admin():
    """🔥 Criar admin com dados corretos"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        import hashlib
        admin_email = "diego@geminii.com.br"
        admin_password = hashlib.sha256("@Lice8127".encode()).hexdigest()
        now = datetime.now(timezone.utc)
        
        cursor.execute("""
            INSERT INTO users (name, email, password, plan_id, plan_name, user_type, subscription_status, created_at, updated_at) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (email) DO UPDATE SET 
                plan_id = EXCLUDED.plan_id,
                plan_name = EXCLUDED.plan_name,
                user_type = EXCLUDED.user_type,
                updated_at = EXCLUDED.updated_at
            RETURNING id
        """, (
            "Diego Doneda - Admin", 
            admin_email, 
            admin_password, 
            1,  # Pro
            "Pro", 
            "admin",
            "active",
            now, 
            now
        ))
        
        admin_id = cursor.fetchone()[0]
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("👑 ADMIN CRIADO!")
        print(f"📧 Email: {admin_email}")
        print(f"🔑 Senha: @Lice8127")
        print(f"🆔 ID: {admin_id}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar admin: {e}")
        return False

def setup_enhanced_database():
    """🔥 Configurar banco SINCRONIZADO com MercadoPago Service"""
    print("🚀 Configurando banco sincronizado com MercadoPago Service...")
    
    if test_connection():
        print("\n📋 Criando estrutura base...")
        create_plans_table()
        create_users_table()
        update_users_table_for_service()  # Para compatibilidade com users existentes
        
        print("\n💳 Criando estrutura de pagamentos...")
        create_payments_table()
        create_payment_history()
        
        print("\n🔐 Criando sistema de autenticação...")
        create_password_reset_table()
        
        print("\n🎫 Criando sistema de cupons...")
        create_coupons_table()
        
        print("\n👑 Criando admin...")
        create_initial_admin()
        
        print("\n✅ Banco SINCRONIZADO configurado com sucesso!")
        print("🎯 Compatível com MercadoPago Service!")
        return True
    else:
        print("❌ Falha na configuração do banco")
        return False

def verify_service_compatibility():
    """🔍 Verificar se o banco está compatível com o service"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        print("🔍 VERIFICANDO COMPATIBILIDADE COM MERCADOPAGO SERVICE...")
        
        # 1. Verificar planos
        cursor.execute("SELECT id, name FROM plans ORDER BY id")
        plans = cursor.fetchall()
        print(f"\n📋 Planos encontrados:")
        for plan in plans:
            print(f"   - ID {plan[0]}: {plan[1]}")
        
        # 2. Verificar campos da tabela users
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name IN ('subscription_status', 'subscription_plan', 'plan_expires_at')
        """)
        user_fields = [row[0] for row in cursor.fetchall()]
        print(f"\n👤 Campos necessários na tabela users:")
        required_fields = ['subscription_status', 'subscription_plan', 'plan_expires_at']
        for field in required_fields:
            status = "✅" if field in user_fields else "❌"
            print(f"   {status} {field}")
        
        # 3. Verificar tabela payments
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'payments'
            AND column_name = 'device_id'
        """)
        has_device_id = cursor.fetchone() is not None
        print(f"\n💳 Tabela payments:")
        print(f"   {'✅' if has_device_id else '❌'} device_id")
        
        # 4. Verificar tabela coupon_uses (não coupon_usage)
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name IN ('coupon_uses', 'coupon_usage')
        """)
        coupon_tables = [row[0] for row in cursor.fetchall()]
        print(f"\n🎫 Tabelas de cupons:")
        print(f"   {'✅' if 'coupon_uses' in coupon_tables else '❌'} coupon_uses (necessária)")
        print(f"   {'⚠️' if 'coupon_usage' in coupon_tables else ''} coupon_usage (desnecessária)")
        
        # 5. Verificar usuários de teste
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"\n👥 Total de usuários: {user_count}")
        
        cursor.close()
        conn.close()
        
        # Resultado final
        all_good = (
            len(plans) >= 2 and 
            len(user_fields) == 3 and 
            has_device_id and 
            'coupon_uses' in coupon_tables
        )
        
        print(f"\n🎯 STATUS GERAL: {'✅ COMPATÍVEL' if all_good else '❌ NECESSITA CORREÇÕES'}")
        
        return all_good
        
    except Exception as e:
        print(f"❌ Erro na verificação: {e}")
        return False

def cleanup_expired_tokens():
    """Limpar tokens expirados"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM password_reset_tokens 
            WHERE expires_at < NOW() OR used = TRUE;
        """)
        
        deleted_count = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        
        if deleted_count > 0:
            print(f"✅ {deleted_count} tokens expirados removidos!")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao limpar tokens: {e}")
        return False

# ===== FUNÇÕES AUXILIARES PARA COMPATIBILIDADE =====

def validate_coupon(code, plan_name, user_id):
    """🔥 Validar cupom - CORRIGIDO para usar campos corretos"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'valid': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        
        # ✅ CORREÇÃO: usar 'active' (não 'is_active') e 'current_uses' (não 'used_count')
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
        
        # ✅ USAR OS NOMES CORRETOS DAS COLUNAS
        coupon_id, discount_percent, discount_type, max_uses, current_uses, expires_at, applicable_plans, min_amount = coupon
        
        # ✅ VERIFICAR expires_at (não valid_until)
        if expires_at and datetime.now(timezone.utc) > expires_at.replace(tzinfo=timezone.utc):
            cursor.close()
            conn.close()
            return {'valid': False, 'error': 'Cupom expirado'}
        
        # ✅ USAR current_uses (não used_count)
        if max_uses and current_uses >= max_uses:
            cursor.close()
            conn.close()
            return {'valid': False, 'error': 'Cupom esgotado'}
        
        # Resto da função permanece igual...
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

if __name__ == "__main__":
    print("🔥 CONFIGURANDO BANCO SINCRONIZADO COM MERCADOPAGO SERVICE")
    print("=" * 60)
    
    # Configurar banco completo
    setup_enhanced_database()
    
    print("\n🔍 VERIFICANDO COMPATIBILIDADE...")
    verify_service_compatibility()
    
    print("\n🧹 LIMPANDO DADOS ANTIGOS...")
    cleanup_expired_tokens()
    
    print("\n✅ CONFIGURAÇÃO CONCLUÍDA!")
    print("🎯 Banco pronto para MercadoPago Service!")
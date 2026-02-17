# database.py - VERSÃO OTIMIZADA SEM MUDAR NOMES OU REMOVER FUNÇÕES
# ==================================================

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
from datetime import datetime, timezone
import warnings

#  SUPRIMIR WARNING DE COLLATION
warnings.filterwarnings('ignore', message='.*collation version.*')

#  CONNECTION POOL GLOBAL
_connection_pool = None

def get_connection_pool():
    """Criar connection pool uma única vez"""
    global _connection_pool
    
    if _connection_pool is None:
        database_url = os.environ.get("DATABASE_URL")
        
        if database_url:
            if database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql://", 1)
            
            _connection_pool = pool.SimpleConnectionPool(
                1,  # minconn
                10,  # maxconn
                database_url,
                sslmode='require',
                connect_timeout=10
            )
        else:
            _connection_pool = pool.SimpleConnectionPool(
                1,
                10,
                host=os.environ.get("DB_HOST", "localhost"),
                database=os.environ.get("DB_NAME", "postgres"),
                user=os.environ.get("DB_USER", "postgres"),
                password=os.environ.get("DB_PASSWORD", "#geminii"),
                port=os.environ.get("DB_PORT", "5432"),
                connect_timeout=10
            )
    
    return _connection_pool

def get_db_connection():
    """Conectar com PostgreSQL usando pool"""
    try:
        pool_instance = get_connection_pool()
        conn = pool_instance.getconn()
        return conn
    except Exception as e:
        # Fallback para conexão direta se pool falhar
        database_url = os.environ.get("DATABASE_URL")
        
        if database_url:
            if database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql://", 1)
            
            conn = psycopg2.connect(
                database_url, 
                sslmode='require',
                connect_timeout=10
            )
        else:
            conn = psycopg2.connect(
                host=os.environ.get("DB_HOST", "localhost"),
                database=os.environ.get("DB_NAME", "postgres"),
                user=os.environ.get("DB_USER", "postgres"),
                password=os.environ.get("DB_PASSWORD", "#geminii"),
                port=os.environ.get("DB_PORT", "5432"),
                connect_timeout=10
            )
        
        return conn

def return_db_connection(conn):
    """Devolver conexão ao pool"""
    try:
        pool_instance = get_connection_pool()
        pool_instance.putconn(conn)
    except:
        # Se não tiver pool, apenas fecha
        if conn:
            conn.close()

def test_connection():
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            return_db_connection(conn)
            return True
        else:
            print("❌ Falha na conexão")
            return False
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        return False

def create_plans_table():
    """Criar tabela de planos SINCRONIZADA com o service"""
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
        
        cursor.execute("DELETE FROM plans")
        
        cursor.execute("""
            INSERT INTO plans (id, name, display_name, price_monthly, price_annual, description, features) VALUES
            (3, 'Free', 'Free', 0.00, 0.00, 'Acesso básico ao sistema', 
            ARRAY['Acesso básico ao sistema', 'Dados limitados', 'Funcionalidades essenciais']),
            
            (4, 'community', 'Community', 97.00, 970.00, 'Acesso completo às ferramentas da comunidade', 
            ARRAY['Monitor de Opções completo', 'Machine Learning avançado', 'Todas as ferramentas de análise', 'Suporte prioritário', 'Recomendações exclusivas'])
        """)
        
        cursor.execute("SELECT setval('plans_id_seq', 4, true)")
        
        conn.commit()
        cursor.close()
        return_db_connection(conn)
        
        print(" Planos criados com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar planos: {e}")
        if conn:
            return_db_connection(conn)
        return False

def create_users_table():
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
                phone VARCHAR(20),
                source VARCHAR(50),          
                password VARCHAR(255) NOT NULL,
                
                plan_id INTEGER DEFAULT 3,
                plan_name VARCHAR(50) DEFAULT 'Básico',
                user_type VARCHAR(20) DEFAULT 'regular',
                
                plan_expires_at TIMESTAMP,
                subscription_status VARCHAR(20) DEFAULT 'inactive',
                subscription_plan VARCHAR(50),
                
                email_confirmed BOOLEAN DEFAULT FALSE,
                email_confirmed_at TIMESTAMP,
                
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address VARCHAR(45)
            );
        """)
        
        #  BATCH DE ÍNDICES
        cursor.execute("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_users_email') THEN
                    CREATE INDEX idx_users_email ON users(email);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_users_type') THEN
                    CREATE INDEX idx_users_type ON users(user_type);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_users_subscription') THEN
                    CREATE INDEX idx_users_subscription ON users(subscription_status);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_users_plan_expires') THEN
                    CREATE INDEX idx_users_plan_expires ON users(plan_expires_at);
                END IF;
            END $$;
        """)
        
        conn.commit()
        cursor.close()
        return_db_connection(conn)
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabela users: {e}")
        if conn:
            return_db_connection(conn)
        return False

def update_users_table_for_service():
    """Atualizar tabela users existente para compatibilidade com o service"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        #  BATCH DE ALTER TABLE
        cursor.execute("""
            DO $$ 
            BEGIN
                BEGIN
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(20) DEFAULT 'inactive';
                EXCEPTION WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_plan VARCHAR(50);
                EXCEPTION WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_expires_at TIMESTAMP;
                EXCEPTION WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS user_type VARCHAR(20) DEFAULT 'regular';
                EXCEPTION WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
                EXCEPTION WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS email_confirmed BOOLEAN DEFAULT TRUE;
                EXCEPTION WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45);
                EXCEPTION WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20);
                EXCEPTION WHEN duplicate_column THEN NULL;
                END;
                BEGIN
                    ALTER TABLE users ADD COLUMN IF NOT EXISTS source VARCHAR(50);
                EXCEPTION WHEN duplicate_column THEN NULL;
                END;
            END $$;
        """)
        
        cursor.execute("""
            UPDATE users 
            SET email_confirmed = TRUE, email_confirmed_at = CURRENT_TIMESTAMP
            WHERE email_confirmed IS NULL
        """)
        
        #  ÍNDICES EM BATCH
        cursor.execute("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_users_subscription') THEN
                    CREATE INDEX idx_users_subscription ON users(subscription_status);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_users_type') THEN
                    CREATE INDEX idx_users_type ON users(user_type);
                END IF;
            END $$;
        """)
        
        conn.commit()
        cursor.close()
        return_db_connection(conn)
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao atualizar tabela users: {e}")
        if conn:
            return_db_connection(conn)
        return False

def create_payments_table():
    """Criar tabela payments EXATAMENTE como o service espera"""
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
        
        #  ÍNDICES EM BATCH
        cursor.execute("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_payments_user_id') THEN
                    CREATE INDEX idx_payments_user_id ON payments(user_id);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_payments_payment_id') THEN
                    CREATE INDEX idx_payments_payment_id ON payments(payment_id);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_payments_status') THEN
                    CREATE INDEX idx_payments_status ON payments(status);
                END IF;
            END $$;
        """)
        
        conn.commit()
        cursor.close()
        return_db_connection(conn)
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabela payments: {e}")
        if conn:
            return_db_connection(conn)
        return False

def create_payment_history():
    """Criar tabela payment_history com CONFLICT handling correto"""
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
        
        #  ÍNDICES EM BATCH
        cursor.execute("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_payment_user') THEN
                    CREATE INDEX idx_payment_user ON payment_history(user_id);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_payment_status') THEN
                    CREATE INDEX idx_payment_status ON payment_history(status);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_payment_payment_id') THEN
                    CREATE INDEX idx_payment_payment_id ON payment_history(payment_id);
                END IF;
            END $$;
        """)
        
        conn.commit()
        cursor.close()
        return_db_connection(conn)
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar payment_history: {e}")
        if conn:
            return_db_connection(conn)
        return False

def create_coupons_table():
    """Criar sistema de cupons SINCRONIZADO com o service"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
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
        
        #  ÍNDICES EM BATCH
        cursor.execute("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_coupons_code') THEN
                    CREATE INDEX idx_coupons_code ON coupons(code);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_coupons_active') THEN
                    CREATE INDEX idx_coupons_active ON coupons(active);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_coupon_uses_user') THEN
                    CREATE INDEX idx_coupon_uses_user ON coupon_uses(user_id);
                END IF;
            END $$;
        """)
        
        conn.commit()
        cursor.close()
        return_db_connection(conn)
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar sistema de cupons: {e}")
        if conn:
            return_db_connection(conn)
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
        
        #  ÍNDICES EM BATCH
        cursor.execute("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_reset_tokens_token') THEN
                    CREATE INDEX idx_reset_tokens_token ON password_reset_tokens(token);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_reset_tokens_expires') THEN
                    CREATE INDEX idx_reset_tokens_expires ON password_reset_tokens(expires_at);
                END IF;
            END $$;
        """)
        
        conn.commit()
        cursor.close()
        return_db_connection(conn)
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabela de reset: {e}")
        if conn:
            return_db_connection(conn)
        return False

def create_initial_admin():
    """Criar admin com dados corretos"""
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
            INSERT INTO users (name, email, password, plan_id, plan_name, user_type, 
                              subscription_status, email_confirmed, email_confirmed_at, 
                              created_at, updated_at) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            4,
            "community",
            "admin",
            "active",
            True,
            now,
            now,
            now
        ))
        
        admin_id = cursor.fetchone()[0]
        
        conn.commit()
        cursor.close()
        return_db_connection(conn)
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar admin: {e}")
        if conn:
            return_db_connection(conn)
        return False

def create_opcoes_recommendations_table():
    """Criar tabela de recomendações de opções"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS opcoes_recommendations (
                id SERIAL PRIMARY KEY,
                ativo_spot VARCHAR(10) NOT NULL,
                ticker_opcao VARCHAR(20) NOT NULL,
                strike DECIMAL(10,2) NOT NULL,
                valor_entrada DECIMAL(10,2) NOT NULL,
                vencimento DATE NOT NULL,
                data_recomendacao DATE NOT NULL,
                stop DECIMAL(10,2) NOT NULL,
                gain DECIMAL(10,2) NOT NULL,
                gain_parcial DECIMAL(10,2),
                status VARCHAR(20) DEFAULT 'ATIVA',
                resultado_final DECIMAL(10,2),
                performance DECIMAL(10,4),
                created_by INTEGER,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        #  ÍNDICES EM BATCH
        cursor.execute("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_opcoes_recommendations_ativo') THEN
                    CREATE INDEX idx_opcoes_recommendations_ativo ON opcoes_recommendations(ativo_spot);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_opcoes_recommendations_ticker') THEN
                    CREATE INDEX idx_opcoes_recommendations_ticker ON opcoes_recommendations(ticker_opcao);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_opcoes_recommendations_status') THEN
                    CREATE INDEX idx_opcoes_recommendations_status ON opcoes_recommendations(status);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_opcoes_recommendations_vencimento') THEN
                    CREATE INDEX idx_opcoes_recommendations_vencimento ON opcoes_recommendations(vencimento);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_opcoes_recommendations_data_rec') THEN
                    CREATE INDEX idx_opcoes_recommendations_data_rec ON opcoes_recommendations(data_recomendacao);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_opcoes_recommendations_active') THEN
                    CREATE INDEX idx_opcoes_recommendations_active ON opcoes_recommendations(is_active);
                END IF;
            END $$;
        """)
        
        conn.commit()
        cursor.close()
        return_db_connection(conn)
        
        print(" Tabela opcoes_recommendations criada com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabela opcoes_recommendations: {e}")
        if conn:
            return_db_connection(conn)
        return False

def verify_service_compatibility():
    """ Verificar se o banco está compatível com o service - VERSÃO RÁPIDA"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        print(" VERIFICANDO COMPATIBILIDADE COM MERCADOPAGO SERVICE...")
        
        #  QUERY ÚNICA OTIMIZADA
        cursor.execute("""
            SELECT 
                (SELECT COUNT(*) FROM plans) as plan_count,
                (SELECT COUNT(*) FROM information_schema.columns 
                 WHERE table_name = 'users' 
                 AND column_name IN ('subscription_status', 'subscription_plan', 'plan_expires_at')) as user_fields,
                (SELECT COUNT(*) FROM information_schema.columns 
                 WHERE table_name = 'payments' AND column_name = 'device_id') as has_device_id,
                (SELECT COUNT(*) FROM information_schema.tables 
                 WHERE table_name = 'coupon_uses') as has_coupon_uses,
                (SELECT COUNT(*) FROM users) as user_count
        """)
        
        row = cursor.fetchone()
        plan_count, user_fields, has_device_id, has_coupon_uses, user_count = row
        
        print(f"\n📋 Planos: {plan_count}")
        print(f"👤 Campos users: {user_fields}/3")
        print(f"💳 device_id: {'' if has_device_id else '❌'}")
        print(f"🎫 coupon_uses: {'' if has_coupon_uses else '❌'}")
        print(f"👥 Total usuários: {user_count}")
        
        cursor.close()
        return_db_connection(conn)
        
        all_good = (plan_count >= 2 and user_fields == 3 and has_device_id and has_coupon_uses)
        
        print(f"\n STATUS GERAL: {' COMPATÍVEL' if all_good else '❌ NECESSITA CORREÇÕES'}")
        
        return all_good
        
    except Exception as e:
        print(f"❌ Erro na verificação: {e}")
        if conn:
            return_db_connection(conn)
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
        return_db_connection(conn)
        
        if deleted_count > 0:
            print(f"🗑️ {deleted_count} tokens expirados removidos!")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao limpar tokens: {e}")
        if conn:
            return_db_connection(conn)
        return False

def create_email_confirmations_table():
    """Criar tabela de confirmações de email"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_confirmations (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                token VARCHAR(255) UNIQUE NOT NULL,
                email VARCHAR(255) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                confirmed BOOLEAN DEFAULT FALSE,
                confirmed_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        #  ÍNDICES EM BATCH
        cursor.execute("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_email_confirmations_token') THEN
                    CREATE INDEX idx_email_confirmations_token ON email_confirmations(token);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_email_confirmations_user') THEN
                    CREATE INDEX idx_email_confirmations_user ON email_confirmations(user_id);
                END IF;
            END $$;
        """)
        
        conn.commit()
        cursor.close()
        return_db_connection(conn)
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabela email_confirmations: {e}")
        if conn:
            return_db_connection(conn)
        return False

def validate_coupon(code, plan_name, user_id):
    """Validar cupom usando os campos exatos do Railway - VERSÃO OTIMIZADA"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'valid': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        
        #  QUERY ÚNICA COM JOIN
        cursor.execute("""
            SELECT 
                c.id, c.discount_percent, c.discount_type, c.max_uses, 
                c.used_count, c.valid_until, c.applicable_plans,
                (SELECT COUNT(*) FROM coupon_uses WHERE coupon_id = c.id AND user_id = %s) as user_used
            FROM coupons c
            WHERE c.code = %s AND (c.active = TRUE OR c.is_active = TRUE)
        """, (user_id, code.upper()))
        
        coupon = cursor.fetchone()
        
        cursor.close()
        return_db_connection(conn)
        
        if not coupon:
            return {'valid': False, 'error': 'Cupom não encontrado ou inativo'}
        
        coupon_id, discount_percent, discount_type, max_uses, used_count, valid_until, applicable_plans, user_used = coupon
        
        if valid_until and datetime.now(timezone.utc) > valid_until.replace(tzinfo=timezone.utc):
            return {'valid': False, 'error': 'Cupom expirado'}
        
        if max_uses and used_count and used_count >= max_uses:
            return {'valid': False, 'error': 'Cupom esgotado'}
        
        if user_used > 0:
            return {'valid': False, 'error': 'Cupom já utilizado'}
        
        plans_list = []
        if applicable_plans:
            if isinstance(applicable_plans, list):
                plans_list = applicable_plans
            elif isinstance(applicable_plans, str):
                plans_list = applicable_plans.split(',')
        
        return {
            'valid': True,
            'coupon_id': coupon_id,
            'discount_percent': float(discount_percent),
            'discount_type': discount_type or 'percent',
            'applicable_plans': plans_list
        }
        
    except Exception as e:
        return {'valid': False, 'error': f'Erro interno: {str(e)}'}

def create_portfolio_tables():
    """Criar tabelas do sistema de portfolios"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolios (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) UNIQUE NOT NULL,
                display_name VARCHAR(100) NOT NULL,
                description TEXT,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        cursor.execute("""
            INSERT INTO portfolios (name, display_name, description, is_active)
            VALUES 
                ('smart_bdr', 'Smart BDR', 'Carteira de BDRs inteligentes', true),
                ('growth', 'Growth', 'Carteira de crescimento', true),
                ('smallcaps', 'Small Caps', 'Carteira de pequenas empresas', true),
                ('bluechips', 'Blue Chips', 'Carteira de grandes empresas', true)
            ON CONFLICT (name) DO NOTHING
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_assets (
                id SERIAL PRIMARY KEY,
                portfolio_name VARCHAR(50) NOT NULL,
                ticker VARCHAR(10) NOT NULL,
                weight DECIMAL(5,2) DEFAULT 0,
                sector VARCHAR(100),
                entry_price DECIMAL(10,2),
                current_price DECIMAL(10,2),
                target_price DECIMAL(10,2),
                entry_date DATE,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(portfolio_name, ticker)
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_recommendations (
                id SERIAL PRIMARY KEY,
                portfolio_name VARCHAR(50) NOT NULL,
                ticker VARCHAR(10) NOT NULL,
                action_type VARCHAR(10) NOT NULL CHECK (action_type IN ('BUY', 'SELL', 'HOLD')),
                target_weight DECIMAL(5,2),
                recommendation_date DATE NOT NULL,
                reason TEXT,
                price_target DECIMAL(10,2),
                current_price DECIMAL(10,2),
                entry_price DECIMAL(10,2),
                market_price DECIMAL(10,2),
                is_active BOOLEAN DEFAULT true,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_portfolios (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                portfolio_name VARCHAR(50) NOT NULL,
                is_active BOOLEAN DEFAULT true,
                granted_by INTEGER,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, portfolio_name)
            );
        """)
        
        #  ÍNDICES EM BATCH
        cursor.execute("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_portfolio_assets_portfolio') THEN
                    CREATE INDEX idx_portfolio_assets_portfolio ON portfolio_assets(portfolio_name);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_portfolio_recommendations_portfolio') THEN
                    CREATE INDEX idx_portfolio_recommendations_portfolio ON portfolio_recommendations(portfolio_name);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_user_portfolios_user') THEN
                    CREATE INDEX idx_user_portfolios_user ON user_portfolios(user_id);
                END IF;
            END $$;
        """)
        
        conn.commit()
        cursor.close()
        return_db_connection(conn)
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabelas de portfolio: {e}")
        if conn:
            return_db_connection(conn)
        return False

def get_portfolio_assets(portfolio_name):
    """Buscar ativos de uma carteira específica"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
            
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, ticker, weight, sector, entry_price, current_price, 
                   target_price, entry_date, is_active, created_at, updated_at
            FROM portfolio_assets 
            WHERE portfolio_name = %s AND is_active = true
            ORDER BY weight DESC, ticker ASC
        """, (portfolio_name,))
        
        assets = []
        
        for row in cursor.fetchall():
            asset_id, ticker, weight, sector, entry_price, current_price, target_price, entry_date, is_active, created_at, updated_at = row
            
            assets.append({
                'id': asset_id,
                'ticker': ticker,
                'weight': float(weight) if weight else 0.0,
                'sector': sector or 'N/A',
                'entry_price': float(entry_price) if entry_price else 0.0,
                'current_price': float(current_price) if current_price else 0.0,
                'target_price': float(target_price) if target_price else 0.0,
                'entry_date': entry_date.isoformat() if entry_date else None,
                'is_active': is_active,
                'created_at': created_at.isoformat() if created_at else None,
                'updated_at': updated_at.isoformat() if updated_at else None
            })
        
        cursor.close()
        return_db_connection(conn)
        
        return assets
        
    except Exception as e:
        print(f"❌ Erro em get_portfolio_assets: {e}")
        return []

def setup_enhanced_database():           
    if test_connection():
        #create_plans_table()
        create_users_table()
        update_users_table_for_service()        
        create_payments_table()
        create_payment_history()
        create_password_reset_table()
        create_coupons_table()        
        create_portfolio_tables()  
        create_email_confirmations_table() 
        create_opcoes_recommendations_table()        
        create_initial_admin()
        
        return True
    else:
        print("❌ Falha na configuração do banco")
        return False

if __name__ == "__main__":
    print("=" * 60)
    
    setup_enhanced_database()
    
    verify_service_compatibility()
    
    cleanup_expired_tokens()
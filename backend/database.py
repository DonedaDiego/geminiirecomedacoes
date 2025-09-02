# database.py - VERSÃO CORRIGIDA E SINCRONIZADA
# ==================================================

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone

def get_db_connection():
    """Conectar com PostgreSQL (local ou Railway) - VERSÃO CORRIGIDA"""
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            database_url = os.environ.get("DATABASE_URL")
            
            if database_url:
                # Corrigir URL do Railway/Heroku se necessário
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
                
            
            # Testar conexão
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            
            return conn
            
        except Exception as e:
            print(f"❌ Tentativa {attempt + 1} falhou: {e}")
            
            if attempt < max_retries - 1:
                print(f"⏳ Tentando novamente em {retry_delay}s...")
                import time
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                print("❌ Todas as tentativas falharam")
                return None
    
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
        
        # 🔥 NOVA ESTRUTURA DE PLANOS: APENAS BÁSICO E COMUNIDADE
        cursor.execute("DELETE FROM plans")
        
        # ✅ CORREÇÃO: Adicionada aspa faltante no 'Free'
        cursor.execute("""
            INSERT INTO plans (id, name, display_name, price_monthly, price_annual, description, features) VALUES
            (3, 'Free', 'Free', 0.00, 0.00, 'Acesso básico ao sistema', 
            ARRAY['Acesso básico ao sistema', 'Dados limitados', 'Funcionalidades essenciais']),
            
            (4, 'community', 'Community', 97.00, 970.00, 'Acesso completo às ferramentas da comunidade', 
            ARRAY['Monitor de Opções completo', 'Machine Learning avançado', 'Todas as ferramentas de análise', 'Suporte prioritário', 'Recomendações exclusivas'])
        """)
        
        # Resetar sequence
        cursor.execute("SELECT setval('plans_id_seq', 4, true)")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Planos criados com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar planos: {e}")
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
                password VARCHAR(255) NOT NULL,
                
                -- 🔥 CORREÇÃO: DEFAULT para plano BÁSICO
                plan_id INTEGER DEFAULT 3,
                plan_name VARCHAR(50) DEFAULT 'Básico',
                user_type VARCHAR(20) DEFAULT 'regular',
                
                -- 🔥 CAMPOS OBRIGATÓRIOS PARA TRIAL
                plan_expires_at TIMESTAMP,
                subscription_status VARCHAR(20) DEFAULT 'inactive',
                subscription_plan VARCHAR(50),
                
                -- 🔥 CAMPOS OBRIGATÓRIOS PARA EMAIL
                email_confirmed BOOLEAN DEFAULT FALSE,
                email_confirmed_at TIMESTAMP,
                
                -- DATAS
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address VARCHAR(45)
            );
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_type ON users(user_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_subscription ON users(subscription_status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_plan_expires ON users(plan_expires_at);")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45)")
        
        conn.commit()
        cursor.close()
        conn.close()
        
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
               
        # Adicionar campos necessários para o service
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(20) DEFAULT 'inactive'")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_plan VARCHAR(50)")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_expires_at TIMESTAMP")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS user_type VARCHAR(20) DEFAULT 'regular'")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_confirmed BOOLEAN DEFAULT TRUE")
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45)")

        
        # Atualizar dados existentes
        cursor.execute("""
            UPDATE users 
            SET email_confirmed = TRUE, email_confirmed_at = CURRENT_TIMESTAMP
            WHERE email_confirmed IS NULL
        """)
        
        # Criar índices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_subscription ON users(subscription_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_type ON users(user_type)")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        
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
            "Diego Doneda - Admin",    # name
            admin_email,               # email
            admin_password,            # password
            4,                         
            "community",               
            "admin",                   
            "active",                  
            True,                      # email_confirmed
            now,                       # email_confirmed_at
            now,                       # created_at
            now                        # updated_at
        ))
        
        admin_id = cursor.fetchone()[0]
        
        conn.commit()
        cursor.close()
        conn.close()
           
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar admin: {e}")
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
        
        # Criar índices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_opcoes_recommendations_ativo ON opcoes_recommendations(ativo_spot)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_opcoes_recommendations_ticker ON opcoes_recommendations(ticker_opcao)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_opcoes_recommendations_status ON opcoes_recommendations(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_opcoes_recommendations_vencimento ON opcoes_recommendations(vencimento)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_opcoes_recommendations_data_rec ON opcoes_recommendations(data_recomendacao)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_opcoes_recommendations_active ON opcoes_recommendations(is_active)")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Tabela opcoes_recommendations criada com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabela opcoes_recommendations: {e}")
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
        
        print(f"\n STATUS GERAL: {'✅ COMPATÍVEL' if all_good else '❌ NECESSITA CORREÇÕES'}")
        
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

def create_email_confirmations_table():
    """🔥 Criar tabela de confirmações de email"""
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
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_confirmations_token ON email_confirmations(token)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_confirmations_user ON email_confirmations(user_id)")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabela email_confirmations: {e}")
        return False

def validate_coupon(code, plan_name, user_id):
    """Validar cupom usando os campos exatos do Railway"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'valid': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        
        # Buscar cupom com os campos que existem no Railway
        cursor.execute("""
            SELECT id, discount_percent, discount_type, max_uses, used_count, 
                   valid_until, applicable_plans
            FROM coupons 
            WHERE code = %s AND (active = TRUE OR is_active = TRUE)
        """, (code.upper(),))
        
        coupon = cursor.fetchone()
        
        if not coupon:
            cursor.close()
            conn.close()
            return {'valid': False, 'error': 'Cupom não encontrado ou inativo'}
        
        coupon_id, discount_percent, discount_type, max_uses, used_count, valid_until, applicable_plans = coupon
        
        # Verificar se expirou
        if valid_until and datetime.now(timezone.utc) > valid_until.replace(tzinfo=timezone.utc):
            cursor.close()
            conn.close()
            return {'valid': False, 'error': 'Cupom expirado'}
        
        # Verificar limite de usos
        if max_uses and used_count and used_count >= max_uses:
            cursor.close()
            conn.close()
            return {'valid': False, 'error': 'Cupom esgotado'}
        
        # Verificar se usuário já usou
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
        
        # Processar applicable_plans (é ARRAY no Railway)
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
        
        # 1. Tabela portfolios
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
        
        # 2. Inserir portfolios padrão
        cursor.execute("""
            INSERT INTO portfolios (name, display_name, description, is_active)
            VALUES 
                ('smart_bdr', 'Smart BDR', 'Carteira de BDRs inteligentes', true),
                ('growth', 'Growth', 'Carteira de crescimento', true),
                ('smallcaps', 'Small Caps', 'Carteira de pequenas empresas', true),
                ('bluechips', 'Blue Chips', 'Carteira de grandes empresas', true)
            ON CONFLICT (name) DO NOTHING
        """)
        
        # 3. Tabela portfolio_assets (SEM FOREIGN KEY)
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
        
        # 4. Tabela portfolio_recommendations
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
        
        # 5. Tabela user_portfolios
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
        
        # 6. Criar índices
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_portfolio_assets_portfolio ON portfolio_assets(portfolio_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_portfolio_recommendations_portfolio ON portfolio_recommendations(portfolio_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_portfolios_user ON user_portfolios(user_id)")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabelas de portfolio: {e}")
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
        conn.close()
        
        return assets
        
    except Exception as e:
        print(f"❌ Erro em get_portfolio_assets: {e}")
        return []
  
def create_flow_tracker_tables():
    """🔥 Criar tabelas do Flow Tracker integradas ao sistema"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        print("📊 Criando tabelas do Flow Tracker...")
        
        # 1. Tabela principal de snapshots de flow
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS flow_snapshots (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(10) NOT NULL,
                date DATE NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                call_flow DECIMAL(15,2) DEFAULT 0,
                put_flow DECIMAL(15,2) DEFAULT 0,
                net_flow DECIMAL(15,2) DEFAULT 0,
                call_put_ratio DECIMAL(8,4) DEFAULT 0,
                total_volume INTEGER DEFAULT 0,
                call_volume INTEGER DEFAULT 0,
                put_volume INTEGER DEFAULT 0,
                total_options INTEGER DEFAULT 0,
                call_options INTEGER DEFAULT 0,
                put_options INTEGER DEFAULT 0,
                avg_iv DECIMAL(6,4) DEFAULT 0,
                sentiment VARCHAR(30) DEFAULT 'NEUTRAL',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT unique_ticker_date UNIQUE(ticker, date)
            );
        """)
        
        # 2. Tabela de detalhes das opções
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS option_details (
                id SERIAL PRIMARY KEY,
                snapshot_id INTEGER REFERENCES flow_snapshots(id) ON DELETE CASCADE,
                option_symbol VARCHAR(30) NOT NULL,
                strike DECIMAL(10,2) NOT NULL,
                category VARCHAR(4) NOT NULL CHECK (category IN ('CALL', 'PUT')),
                due_date DATE NOT NULL,
                days_to_maturity INTEGER NOT NULL,
                close_price DECIMAL(8,4) NOT NULL,
                volume INTEGER DEFAULT 0,
                bid DECIMAL(8,4) DEFAULT 0,
                ask DECIMAL(8,4) DEFAULT 0,
                bid_volume INTEGER DEFAULT 0,
                ask_volume INTEGER DEFAULT 0,
                calculated_iv DECIMAL(6,4) DEFAULT 0,
                bs_theoretical DECIMAL(8,4) DEFAULT 0,
                moneyness VARCHAR(10) DEFAULT 'OTM' CHECK (moneyness IN ('ITM', 'ATM', 'OTM')),
                weight DECIMAL(15,4) DEFAULT 0,
                spot_price DECIMAL(10,2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # 3. Tabela de configurações do Flow Tracker
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS flow_tracker_settings (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                watchlist TEXT[], -- Array de tickers favoritos
                alert_threshold DECIMAL(6,4) DEFAULT 2.0, -- Threshold para alertas
                auto_capture BOOLEAN DEFAULT false,
                capture_interval INTEGER DEFAULT 300, -- segundos
                preferred_tickers TEXT[] DEFAULT ARRAY['PETR4', 'VALE3', 'ITUB4'],
                notifications_enabled BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id)
            );
        """)
        
        # 4. Tabela de alertas de flow
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS flow_alerts (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                ticker VARCHAR(10) NOT NULL,
                alert_type VARCHAR(20) NOT NULL, -- 'HIGH_CP_RATIO', 'UNUSUAL_FLOW', etc
                threshold_value DECIMAL(8,4),
                current_value DECIMAL(8,4),
                message TEXT,
                is_read BOOLEAN DEFAULT false,
                snapshot_id INTEGER REFERENCES flow_snapshots(id),
                triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # 5. Índices para performance otimizada
        flow_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_flow_ticker_date ON flow_snapshots(ticker, date);",
            "CREATE INDEX IF NOT EXISTS idx_flow_timestamp ON flow_snapshots(timestamp);",
            "CREATE INDEX IF NOT EXISTS idx_flow_ticker ON flow_snapshots(ticker);",
            "CREATE INDEX IF NOT EXISTS idx_flow_sentiment ON flow_snapshots(sentiment);",
            
            "CREATE INDEX IF NOT EXISTS idx_option_details_snapshot ON option_details(snapshot_id);",
            "CREATE INDEX IF NOT EXISTS idx_option_symbol ON option_details(option_symbol);",
            "CREATE INDEX IF NOT EXISTS idx_option_category ON option_details(category);",
            "CREATE INDEX IF NOT EXISTS idx_option_strike ON option_details(strike);",
            "CREATE INDEX IF NOT EXISTS idx_option_due_date ON option_details(due_date);",
            "CREATE INDEX IF NOT EXISTS idx_option_moneyness ON option_details(moneyness);",
            
            "CREATE INDEX IF NOT EXISTS idx_flow_settings_user ON flow_tracker_settings(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_flow_alerts_user ON flow_alerts(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_flow_alerts_ticker ON flow_alerts(ticker);",
            "CREATE INDEX IF NOT EXISTS idx_flow_alerts_read ON flow_alerts(is_read);"
        ]
        
        print("   🔍 Criando índices de performance...")
        for index in flow_indexes:
            cursor.execute(index)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Tabelas do Flow Tracker criadas com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabelas do Flow Tracker: {e}")
        return False

def get_flow_snapshots(ticker=None, limit=50):
    """Buscar snapshots de flow com filtros"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
            
        cursor = conn.cursor()
        
        if ticker:
            cursor.execute("""
                SELECT id, ticker, date, timestamp, call_flow, put_flow, net_flow,
                       call_put_ratio, total_volume, sentiment, avg_iv
                FROM flow_snapshots 
                WHERE ticker = %s
                ORDER BY timestamp DESC 
                LIMIT %s
            """, (ticker.upper(), limit))
        else:
            cursor.execute("""
                SELECT id, ticker, date, timestamp, call_flow, put_flow, net_flow,
                       call_put_ratio, total_volume, sentiment, avg_iv
                FROM flow_snapshots 
                ORDER BY timestamp DESC 
                LIMIT %s
            """, (limit,))
        
        snapshots = []
        for row in cursor.fetchall():
            snapshots.append({
                'id': row[0],
                'ticker': row[1],
                'date': row[2].isoformat() if row[2] else None,
                'timestamp': row[3].isoformat() if row[3] else None,
                'call_flow': float(row[4]) if row[4] else 0,
                'put_flow': float(row[5]) if row[5] else 0,
                'net_flow': float(row[6]) if row[6] else 0,
                'call_put_ratio': float(row[7]) if row[7] else 0,
                'total_volume': row[8] or 0,
                'sentiment': row[9] or 'NEUTRAL',
                'avg_iv': float(row[10]) if row[10] else 0
            })
        
        cursor.close()
        conn.close()
        
        return snapshots
        
    except Exception as e:
        print(f"❌ Erro em get_flow_snapshots: {e}")
        return []

def get_user_flow_settings(user_id):
    """Buscar configurações do Flow Tracker do usuário"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT watchlist, alert_threshold, auto_capture, capture_interval,
                   preferred_tickers, notifications_enabled
            FROM flow_tracker_settings 
            WHERE user_id = %s
        """, (user_id,))
        
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if row:
            return {
                'watchlist': row[0] or [],
                'alert_threshold': float(row[1]) if row[1] else 2.0,
                'auto_capture': row[2] or False,
                'capture_interval': row[3] or 300,
                'preferred_tickers': row[4] or ['PETR4', 'VALE3', 'ITUB4'],
                'notifications_enabled': row[5] or True
            }
        else:
            # Criar configuração padrão
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO flow_tracker_settings (user_id)
                VALUES (%s)
                RETURNING watchlist, alert_threshold, auto_capture, capture_interval,
                         preferred_tickers, notifications_enabled
            """, (user_id,))
            
            row = cursor.fetchone()
            conn.commit()
            cursor.close()
            conn.close()
            
            return {
                'watchlist': [],
                'alert_threshold': 2.0,
                'auto_capture': False,
                'capture_interval': 300,
                'preferred_tickers': ['PETR4', 'VALE3', 'ITUB4'],
                'notifications_enabled': True
            }
        
    except Exception as e:
        print(f"❌ Erro em get_user_flow_settings: {e}")
        return None

def create_flow_alert(user_id, ticker, alert_type, threshold_value, current_value, message, snapshot_id=None):
    """Criar um alerta de flow"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO flow_alerts (user_id, ticker, alert_type, threshold_value, 
                                   current_value, message, snapshot_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (user_id, ticker.upper(), alert_type, threshold_value, current_value, message, snapshot_id))
        
        alert_id = cursor.fetchone()[0]
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return alert_id
        
    except Exception as e:
        print(f"❌ Erro ao criar alerta: {e}")
        return False 
  
  
  
def setup_enhanced_database():
    """🔥 Configurar banco SINCRONIZADO com MercadoPago Service"""
    
    
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
        create_flow_tracker_tables()
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
    
    
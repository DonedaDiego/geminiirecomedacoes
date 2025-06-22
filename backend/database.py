import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone

def get_db_connection():
    """Conectar com PostgreSQL (local ou Render)"""
    try:
        # Se estiver no Render, usar DATABASE_URL
        database_url = os.environ.get("DATABASE_URL")
        
        if database_url:
            # Produção (Render) - usa a URL completa
            conn = psycopg2.connect(database_url, sslmode='require')
        else:
            # Desenvolvimento local
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
    """Testar conexão com banco"""
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
    """Criar tabela de planos"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Criar tabela plans
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
        
        # Inserir planos padrão se não existirem
        cursor.execute("SELECT COUNT(*) FROM plans;")
        count = cursor.fetchone()[0]
        
        if count == 0:
            cursor.execute("""
                INSERT INTO plans (name, display_name, price_monthly, price_annual, description, features) VALUES
                ('basico', 'Básico', 0.00, 0.00, 'Acesso básico aos indicadores', 
                 ARRAY['Monitor Básico', 'Radar de Setores']),
                ('premium', 'Premium', 49.90, 499.00, 'Análises avançadas e indicadores premium', 
                 ARRAY['Tudo do Básico', 'Long&Short', 'Backtests', 'Alertas']),
                ('estrategico', 'Estratégico', 99.90, 999.00, 'Funcionalidades completas com IA', 
                 ARRAY['Tudo do Premium', 'Carteiras Quantitativas', 'IA Recomendações']);
            """)
            print("✅ Planos padrão inseridos!")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Tabela 'plans' criada com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabela plans: {e}")
        return False

def create_users_table():
    """Criar tabela users"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Criar tabela users
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                plan_id INTEGER DEFAULT 1,
                plan_name VARCHAR(50) DEFAULT 'Básico',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Criar índice para email (busca mais rápida)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Tabela 'users' criada com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabela users: {e}")
        return False

def create_password_reset_table():
    """Criar tabela para tokens de reset de senha"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Criar tabela password_reset_tokens
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
        
        # Criar índices para busca rápida
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reset_tokens_token ON password_reset_tokens(token);
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reset_tokens_expires ON password_reset_tokens(expires_at);
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reset_tokens_user_id ON password_reset_tokens(user_id);
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Tabela 'password_reset_tokens' criada com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabela de reset de senha: {e}")
        return False

def cleanup_expired_tokens():
    """Limpar tokens de reset expirados"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Deletar tokens expirados
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

def setup_database():
    """Configurar banco completo"""
    print("🚀 Configurando banco de dados...")
    
    if test_connection():
        # Criar tabelas na ordem correta (planos primeiro, depois users, depois tokens)
        create_plans_table()
        create_users_table()
        create_password_reset_table()
        
        # Limpar tokens expirados
        cleanup_expired_tokens()
        
        print("✅ Banco configurado com sucesso!")
        return True
    else:
        print("❌ Falha na configuração do banco")
        return False

def get_user_by_email(email):
    """Buscar usuário por email - função auxiliar"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, email, password, plan_id, plan_name 
            FROM users WHERE email = %s
        """, (email,))
        
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return user
        
    except Exception as e:
        print(f"❌ Erro ao buscar usuário: {e}")
        return None

def update_user_password(user_id, new_password_hash):
    """Atualizar senha do usuário - função auxiliar"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users 
            SET password = %s, updated_at = CURRENT_TIMESTAMP 
            WHERE id = %s
        """, (new_password_hash, user_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        cursor.close()
        conn.close()
        
        return success
        
    except Exception as e:
        print(f"❌ Erro ao atualizar senha: {e}")
        return False

# ===== NOVAS FUNCIONALIDADES ENHANCED =====

def create_admin_system():
    """Criar sistema de administração"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Adicionar coluna user_type se não existir
        cursor.execute("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS user_type VARCHAR(20) DEFAULT 'regular'
        """)
        
        # Criar índice para busca rápida por tipo
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_type ON users(user_type);
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Sistema de administração criado!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar sistema admin: {e}")
        return False

def create_coupons_table():
    """Criar tabela de cupons de desconto"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Criar tabela de cupons
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS coupons (
                id SERIAL PRIMARY KEY,
                code VARCHAR(50) UNIQUE NOT NULL,
                discount_percent DECIMAL(5,2) NOT NULL CHECK (discount_percent > 0 AND discount_percent <= 100),
                discount_type VARCHAR(20) DEFAULT 'percent' CHECK (discount_type IN ('percent', 'fixed')),
                discount_value DECIMAL(10,2) DEFAULT 0,
                applicable_plans TEXT[] DEFAULT ARRAY['premium', 'estrategico'],
                max_uses INTEGER DEFAULT NULL,
                used_count INTEGER DEFAULT 0,
                valid_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                valid_until TIMESTAMP,
                is_active BOOLEAN DEFAULT true,
                created_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Criar tabela de uso de cupons
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS coupon_usage (
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
        
        # Cupons serão inseridos depois que o admin for criado
        print("✅ Tabela de cupons criada! (cupons serão inseridos após criação do admin)")
        
        # Criar índices para performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_coupons_code ON coupons(code);
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_coupons_active ON coupons(is_active);
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_coupon_usage_user ON coupon_usage(user_id);
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Sistema de cupons criado com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar sistema de cupons: {e}")
        return False

def create_portfolio_system():
    """Criar sistema de carteiras"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Tabela de carteiras
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolios (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50) UNIQUE NOT NULL,
                display_name VARCHAR(100) NOT NULL,
                description TEXT,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabela de ativos das carteiras
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_assets (
                id SERIAL PRIMARY KEY,
                portfolio_name VARCHAR(50) REFERENCES portfolios(name) ON DELETE CASCADE,
                ticker VARCHAR(20) NOT NULL,
                weight DECIMAL(5,2) NOT NULL CHECK (weight >= 0 AND weight <= 100),
                sector VARCHAR(100),
                entry_price DECIMAL(10,2),
                current_price DECIMAL(10,2),      
                target_price DECIMAL(10,2),       
                entry_date DATE DEFAULT CURRENT_DATE,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(portfolio_name, ticker)
            )
        """)
        
        # Inserir carteiras padrão
        portfolios = [
            ('smart_bdr', 'Smart BDR', 'Carteira de BDRs com análise inteligente'),
            ('growth', 'Growth', 'Ações de empresas em crescimento'),
            ('smallcaps', 'Small Caps', 'Ações de pequenas empresas com potencial'),
            ('bluechips', 'Blue Chips', 'Ações de grandes empresas consolidadas')
        ]
        
        for portfolio in portfolios:
            cursor.execute("""
                INSERT INTO portfolios (name, display_name, description) 
                VALUES (%s, %s, %s) 
                ON CONFLICT (name) DO NOTHING
            """, portfolio)
        
        # Inserir alguns ativos de exemplo para Smart BDR
        cursor.execute("SELECT COUNT(*) FROM portfolio_assets WHERE portfolio_name = 'smart_bdr';")
        count = cursor.fetchone()[0]
        
        if count == 0:
            smart_bdr_assets = [
                ('AAPL34', 15.0, 'Tecnologia'),
                ('MSFT34', 12.0, 'Tecnologia'),
                ('AMZO34', 10.0, 'E-commerce'),
                ('TSLA34', 8.0, 'Automotivo'),
                ('GOOGL34', 10.0, 'Tecnologia'),
                ('META34', 7.0, 'Social Media'),
                ('NVDC34', 12.0, 'Semicondutores'),
                ('NFLX34', 6.0, 'Streaming'),
                ('DISB34', 5.0, 'Entretenimento'),
                ('COCA34', 5.0, 'Bebidas')
            ]
            
            for asset in smart_bdr_assets:
                cursor.execute("""
                    INSERT INTO portfolio_assets (portfolio_name, ticker, weight, sector)
                    VALUES ('smart_bdr', %s, %s, %s)
                    ON CONFLICT (portfolio_name, ticker) DO NOTHING
                """, asset)
            
            print("✅ Ativos de exemplo inseridos na carteira Smart BDR!")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Sistema de carteiras criado com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar sistema de carteiras: {e}")
        return False

def create_payment_history():
    """Criar tabela de histórico de pagamentos"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payment_history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                plan_id INTEGER REFERENCES plans(id),
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
        
        # Criar índices
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_payment_user ON payment_history(user_id);
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_payment_status ON payment_history(status);
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_payment_subscription ON payment_history(subscription_id);
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Histórico de pagamentos criado!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar histórico de pagamentos: {e}")
        return False

def create_initial_admin():
    """Criar usuário admin inicial - VERSÃO PRODUÇÃO"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Verificar se já existe admin
        cursor.execute("SELECT id FROM users WHERE user_type = 'admin'")
        if cursor.fetchone():
            print("👑 Usuário admin já existe!")
            cursor.close()
            conn.close()
            return True
        
        # Importar função de hash
        import hashlib
        def hash_password(password):
            return hashlib.sha256(password.encode()).hexdigest()
        
        # Criar usuário admin com sua senha
        admin_email = "diego@geminii.com.br"
        admin_password = hash_password("@Lice8127")  # Sua senha
        
        cursor.execute("""
            INSERT INTO users (name, email, password, plan_id, plan_name, user_type, created_at) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (email) DO UPDATE SET 
                user_type = 'admin',
                plan_id = 3,
                plan_name = 'Estratégico'
            RETURNING id
        """, ("Diego Doneda - Admin", admin_email, admin_password, 3, "Estratégico", "admin", datetime.now(timezone.utc)))
        
        admin_id = cursor.fetchone()[0]
        
        conn.commit()
        cursor.close()
        conn.close()
        
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar admin: {e}")
        return False

def create_user_portfolios_table():
    """Criar tabela de portfolios por usuário"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Tabela de portfolios que cada usuário pode acessar
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_portfolios (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                portfolio_name VARCHAR(50) REFERENCES portfolios(name) ON DELETE CASCADE,
                granted_by INTEGER REFERENCES users(id),
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT true,
                UNIQUE(user_id, portfolio_name)
            )
        """)
        
        # Criar índices para performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_portfolios_user 
            ON user_portfolios(user_id);
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_portfolios_portfolio 
            ON user_portfolios(portfolio_name);
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_portfolios_active 
            ON user_portfolios(is_active);
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Tabela 'user_portfolios' criada com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabela user_portfolios: {e}")
        return False


def setup_enhanced_database():
    """Configurar banco completo com novos recursos"""
    print("🚀 Configurando banco de dados ENHANCED...")
    
    if test_connection():
        create_plans_table()
        create_users_table()
        create_password_reset_table()
        create_admin_system()
        create_initial_admin()
        create_coupons_table()
        create_portfolio_system()
        create_recommendations_table()
        create_payment_history()
        create_user_portfolios_table()  # ✅ ADICIONAR ESTA LINHA
        
        cleanup_expired_tokens()
        
        print("✅ Banco ENHANCED configurado com sucesso!")
        return True
    else:
        print("❌ Falha na configuração do banco")
        return False

def grant_portfolio_access(user_id, portfolio_name, granted_by_admin_id):
    """Dar acesso a uma carteira para um usuário"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão'}
            
        cursor = conn.cursor()
        
        # Verificar se usuário existe
        cursor.execute("SELECT name, email FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            cursor.close()
            conn.close()
            return {'success': False, 'error': 'Usuário não encontrado'}
        
        # Verificar se portfolio existe
        cursor.execute("SELECT display_name FROM portfolios WHERE name = %s", (portfolio_name,))
        portfolio = cursor.fetchone()
        if not portfolio:
            cursor.close()
            conn.close()
            return {'success': False, 'error': 'Carteira não encontrada'}
        
        # Inserir ou ativar acesso
        cursor.execute("""
            INSERT INTO user_portfolios (user_id, portfolio_name, granted_by, is_active)
            VALUES (%s, %s, %s, true)
            ON CONFLICT (user_id, portfolio_name) 
            DO UPDATE SET 
                is_active = true,
                granted_by = EXCLUDED.granted_by,
                granted_at = CURRENT_TIMESTAMP
        """, (user_id, portfolio_name, granted_by_admin_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'message': f'Acesso à carteira {portfolio[0]} concedido para {user[0]}'
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Erro interno: {str(e)}'}

def revoke_portfolio_access(user_id, portfolio_name):
    """Remover acesso a uma carteira"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão'}
            
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE user_portfolios 
            SET is_active = false 
            WHERE user_id = %s AND portfolio_name = %s
        """, (user_id, portfolio_name))
        
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return {'success': False, 'error': 'Acesso não encontrado'}
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {'success': True, 'message': 'Acesso removido com sucesso'}
        
    except Exception as e:
        return {'success': False, 'error': f'Erro interno: {str(e)}'}

def get_user_portfolios(user_id):
    """Buscar carteiras que um usuário pode acessar"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
            
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT up.portfolio_name, p.display_name, up.granted_at
            FROM user_portfolios up
            JOIN portfolios p ON up.portfolio_name = p.name
            WHERE up.user_id = %s AND up.is_active = true
            ORDER BY p.display_name
        """, (user_id,))
        
        portfolios = []
        for row in cursor.fetchall():
            portfolios.append({
                'name': row[0],
                'display_name': row[1],
                'granted_at': row[2].isoformat() if row[2] else None
            })
        
        cursor.close()
        conn.close()
        
        return portfolios
        
    except Exception as e:
        print(f"❌ Erro ao buscar portfolios do usuário: {e}")
        return []


def create_recommendations_table():
    """Criar tabela de recomendações das carteiras"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Criar tabela de recomendações
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_recommendations (
                id SERIAL PRIMARY KEY,
                portfolio_name VARCHAR(50) NOT NULL,
                ticker VARCHAR(20) NOT NULL,
                action_type VARCHAR(10) NOT NULL CHECK (action_type IN ('BUY', 'SELL', 'HOLD')),
                target_weight DECIMAL(5,2) CHECK (target_weight >= 0 AND target_weight <= 100),
                recommendation_date DATE NOT NULL,
                reason TEXT,
                price_target DECIMAL(10,2),
                current_price DECIMAL(10,2),
                is_active BOOLEAN DEFAULT true,
                created_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Criar índices para performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_portfolio_recommendations_portfolio 
            ON portfolio_recommendations(portfolio_name);
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_portfolio_recommendations_date 
            ON portfolio_recommendations(recommendation_date);
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_portfolio_recommendations_active 
            ON portfolio_recommendations(is_active);
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_portfolio_recommendations_ticker 
            ON portfolio_recommendations(ticker);
        """)
        
        # Inserir algumas recomendações de exemplo para Smart BDR
        cursor.execute("SELECT COUNT(*) FROM portfolio_recommendations WHERE portfolio_name = 'smart_bdr';")
        count = cursor.fetchone()[0]
        
        if count == 0:
            # Buscar ID do admin para associar as recomendações
            cursor.execute("SELECT id FROM users WHERE user_type = 'admin' LIMIT 1;")
            admin_result = cursor.fetchone()
            admin_id = admin_result[0] if admin_result else None
            
            if admin_id:
                # Recomendações de exemplo
                sample_recommendations = [
                    ('smart_bdr', 'AAPL34', 'BUY', 18.0, '2024-06-20', 'Apple apresentou resultados excepcionais no Q2. Recomendamos aumentar posição.', 165.00, 155.50),
                    ('smart_bdr', 'TSLA34', 'HOLD', 8.0, '2024-06-19', 'Tesla mantém fundamentals sólidos. Aguardar próximos resultados.', 180.00, 175.20),
                    ('smart_bdr', 'MSFT34', 'BUY', 15.0, '2024-06-18', 'Microsoft com forte crescimento em cloud computing. Aumentar exposição.', 420.00, 405.30),
                    ('smart_bdr', 'GOOGL34', 'SELL', 5.0, '2024-06-17', 'Google enfrentando pressão regulatória. Reduzir posição temporariamente.', 135.00, 142.80),
                    ('growth', 'NVDC34', 'BUY', 20.0, '2024-06-16', 'NVIDIA líder em IA. Forte potencial de crescimento no setor.', 450.00, 425.60)
                ]
                
                for rec in sample_recommendations:
                    cursor.execute("""
                        INSERT INTO portfolio_recommendations 
                        (portfolio_name, ticker, action_type, target_weight, recommendation_date, 
                         reason, price_target, current_price, created_by)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (*rec, admin_id))
                
                print("✅ Recomendações de exemplo inseridas!")
            else:
                print("⚠️ Admin não encontrado, recomendações de exemplo não inseridas")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Tabela 'portfolio_recommendations' criada com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabela de recomendações: {e}")
        return False


# ===== FUNÇÕES AUXILIARES PARA O SISTEMA =====

def validate_coupon(code, plan_name, user_id):
    """Validar cupom de desconto"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'valid': False, 'error': 'Erro de conexão'}
            
        cursor = conn.cursor()
        
        # Buscar cupom ativo
        cursor.execute("""
            SELECT id, discount_percent, discount_type, discount_value, 
                   applicable_plans, max_uses, used_count, valid_until
            FROM coupons 
            WHERE code = %s AND is_active = true
        """, (code.upper(),))
        
        coupon = cursor.fetchone()
        
        if not coupon:
            cursor.close()
            conn.close()
            return {'valid': False, 'error': 'Cupom não encontrado ou inativo'}
        
        coupon_id, discount_percent, discount_type, discount_value, applicable_plans, max_uses, used_count, valid_until = coupon
        
        # Verificar validade temporal
        if valid_until and valid_until < datetime.now():
            cursor.close()
            conn.close()
            return {'valid': False, 'error': 'Cupom expirado'}
        
        # Verificar limite de uso
        if max_uses and used_count >= max_uses:
            cursor.close()
            conn.close()
            return {'valid': False, 'error': 'Cupom esgotado'}
        
        # Verificar se plano é aplicável
        if applicable_plans and plan_name not in applicable_plans:
            cursor.close()
            conn.close()
            return {'valid': False, 'error': f'Cupom não válido para o plano {plan_name}'}
        
        # Verificar se usuário já usou este cupom
        cursor.execute("""
            SELECT id FROM coupon_usage 
            WHERE coupon_id = %s AND user_id = %s
        """, (coupon_id, user_id))
        
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return {'valid': False, 'error': 'Cupom já utilizado por este usuário'}
        
        cursor.close()
        conn.close()
        
        return {
            'valid': True,
            'coupon_id': coupon_id,
            'discount_percent': discount_percent,
            'discount_type': discount_type,
            'discount_value': discount_value
        }
        
    except Exception as e:
        return {'valid': False, 'error': f'Erro interno: {str(e)}'}

def apply_coupon_discount(original_price, coupon_data):
    """Aplicar desconto do cupom"""
    try:
        if coupon_data['discount_type'] == 'percent':
            discount_amount = original_price * (coupon_data['discount_percent'] / 100)
        else:  # fixed
            discount_amount = coupon_data['discount_value']
        
        # Não permitir desconto maior que o preço original
        discount_amount = min(discount_amount, original_price)
        final_price = original_price - discount_amount
        
        return {
            'original_price': original_price,
            'discount_amount': discount_amount,
            'final_price': final_price,
            'discount_percent': (discount_amount / original_price * 100) if original_price > 0 else 0
        }
        
    except Exception as e:
        return None

def get_portfolio_assets(portfolio_name):
    """Buscar ativos de uma carteira"""
    try:
        conn = get_db_connection()
        if not conn:
            return []
                     
        cursor = conn.cursor()
        
        # ✅ QUERY CORRIGIDA - incluindo todas as colunas necessárias
        cursor.execute("""
            SELECT id, ticker, weight, sector, entry_price, current_price, target_price, entry_date, is_active
            FROM portfolio_assets 
            WHERE portfolio_name = %s AND is_active = true
            ORDER BY weight DESC
        """, (portfolio_name,))
                 
        assets = []
        for row in cursor.fetchall():
            assets.append({
                'id': row[0],                                                    # ✅ ID do ativo
                'ticker': row[1],                                               # ✅ Ticker
                'weight': float(row[2]),                                        # ✅ Peso
                'sector': row[3],                                               # ✅ Setor
                'entry_price': float(row[4]) if row[4] else 0,                  # ✅ Preço entrada
                'current_price': float(row[5]) if row[5] else 0,               # ✅ Preço atual
                'target_price': float(row[6]) if row[6] else 0,                # ✅ Preço alvo
                'entry_date': row[7].isoformat() if row[7] else None,          # ✅ Data entrada
                'is_active': row[8]                                            # ✅ Ativo
            })
                 
        cursor.close()
        conn.close()
                 
        return assets
             
    except Exception as e:
        print(f"❌ Erro ao buscar ativos: {e}")
        return []

def add_portfolio_asset(portfolio_name, ticker, weight, sector, admin_user_id):
    """Adicionar ativo a carteira"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão'}
            
        cursor = conn.cursor()
        
        # Verificar se carteira existe
        cursor.execute("SELECT name FROM portfolios WHERE name = %s", (portfolio_name,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return {'success': False, 'error': 'Carteira não encontrada'}
        
        # Inserir ou atualizar ativo
        cursor.execute("""
            INSERT INTO portfolio_assets (portfolio_name, ticker, weight, sector)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (portfolio_name, ticker) 
            DO UPDATE SET 
                weight = EXCLUDED.weight,
                sector = EXCLUDED.sector,
                updated_at = CURRENT_TIMESTAMP
        """, (portfolio_name, ticker.upper(), weight, sector))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {'success': True, 'message': f'Ativo {ticker} adicionado à carteira {portfolio_name}'}
        
    except Exception as e:
        return {'success': False, 'error': f'Erro interno: {str(e)}'}

def remove_portfolio_asset(portfolio_name, ticker):
    """Remover ativo da carteira"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão'}
            
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM portfolio_assets 
            WHERE portfolio_name = %s AND ticker = %s
        """, (portfolio_name, ticker.upper()))
        
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return {'success': False, 'error': 'Ativo não encontrado'}
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {'success': True, 'message': f'Ativo {ticker} removido da carteira {portfolio_name}'}
        
    except Exception as e:
        return {'success': False, 'error': f'Erro interno: {str(e)}'}

def fix_admin_account():
    """Corrigir conta do admin completamente"""
    try:
        import hashlib
        from datetime import datetime, timezone
        
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Deletar admin antigo
        cursor.execute("DELETE FROM users WHERE user_type = 'admin'")
        print(f"🗑️ {cursor.rowcount} admin(s) antigo(s) deletado(s)")
        
        # Criar admin novo com dados corretos
        admin_email = "diego@geminii.com.br"
        admin_password = "@Lice8127"
        password_hash = hashlib.sha256(admin_password.encode()).hexdigest()
        
        cursor.execute("""
            INSERT INTO users (name, email, password, plan_id, plan_name, user_type, created_at) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            "Diego Doneda - Admin", 
            admin_email, 
            password_hash, 
            3, 
            "Estratégico", 
            "admin", 
            datetime.now(timezone.utc)
        ))
        
        admin_id = cursor.fetchone()[0]
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("👑 ADMIN CRIADO COM SUCESSO!")
        print(f"📧 Email: {admin_email}")
        print(f"🔑 Senha: {admin_password}")
        print(f"🆔 ID: {admin_id}")
        print(f"🔐 Hash: {password_hash}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao corrigir admin: {e}")
        return False


if __name__ == "__main__":
     setup_enhanced_database()
    
    
# if __name__ == "__main__":
#     print("1. Setup completo")
#     print("2. Corrigir admin")
#     choice = input("Escolha (1 ou 2): ")
    
#     if choice == "2":
#         fix_admin_account()
#     else:
#         setup_enhanced_database()
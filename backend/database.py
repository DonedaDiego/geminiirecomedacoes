import os
import psycopg2
from psycopg2.extras import RealDictCursor

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

if __name__ == "__main__":
    setup_database()
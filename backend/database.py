import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    """Conectar com PostgreSQL local"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="postgres", 
            user="postgres",
            password="#geminii",
            port="5432"
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
        print(f"❌ Erro ao criar tabela: {e}")
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

def setup_database():
    """Configurar banco completo"""
    print("🚀 Configurando banco de dados...")
    
    if test_connection():
        create_plans_table()
        create_users_table()
        print("✅ Banco configurado com sucesso!")
        return True
    else:
        print("❌ Falha na configuração do banco")
        return False

if __name__ == "__main__":
    setup_database()
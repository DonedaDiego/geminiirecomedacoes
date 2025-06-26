# database_fix.py - Script para corrigir estrutura do banco

import os
import psycopg2
from datetime import datetime, timezone

def get_db_connection():
    """Conectar com PostgreSQL"""
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

def fix_database_structure():
    """Corrigir estrutura completa do banco"""
    try:
        print("🔧 INICIANDO CORREÇÃO DA ESTRUTURA DO BANCO")
        print("=" * 60)
        
        conn = get_db_connection()
        if not conn:
            print("❌ Falha na conexão com banco")
            return False
        
        cursor = conn.cursor()
        
        # 1. Verificar e corrigir tabela users
        print("👥 Corrigindo tabela users...")
        
        # Adicionar campos que podem não existir
        cursor.execute("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(20) DEFAULT 'inactive'
        """)
        
        cursor.execute("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS subscription_plan VARCHAR(50) DEFAULT 'Básico'
        """)
        
        cursor.execute("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS plan_expires_at TIMESTAMP NULL
        """)
        
        cursor.execute("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS user_type VARCHAR(20) DEFAULT 'regular'
        """)
        
        print("✅ Tabela users corrigida")
        
        # 2. Criar/corrigir tabela payments
        print("💳 Criando/corrigindo tabela payments...")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                payment_id VARCHAR(100) UNIQUE NOT NULL,
                status VARCHAR(50) NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                plan_id VARCHAR(50),
                plan_name VARCHAR(100),
                cycle VARCHAR(20),
                external_reference VARCHAR(200),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        print("✅ Tabela payments criada/corrigida")
        
        # 3. Criar/corrigir tabela payment_history
        print("📋 Criando/corrigindo tabela payment_history...")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payment_history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                plan_id INTEGER,
                payment_id VARCHAR(255),
                amount DECIMAL(10,2) NOT NULL DEFAULT 0,
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
        
        print("✅ Tabela payment_history criada/corrigida")
        
        # 4. Criar índices importantes
        print("🔍 Criando índices...")
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_payments_payment_id 
            ON payments(payment_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_payments_user_id 
            ON payments(user_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_email 
            ON users(email)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_subscription_status 
            ON users(subscription_status)
        """)
        
        print("✅ Índices criados")
        
        # 5. Atualizar planos existentes
        print("📦 Atualizando estrutura de planos...")
        
        cursor.execute("""
            UPDATE users 
            SET plan_id = 1, plan_name = 'Pro'
            WHERE plan_name = 'Básico' OR plan_name IS NULL
        """)
        
        print(f"✅ {cursor.rowcount} usuários migrados para Pro")
        
        # 6. Verificar se admin existe
        print("👑 Verificando usuário admin...")
        
        cursor.execute("SELECT id FROM users WHERE user_type = 'admin'")
        admin_exists = cursor.fetchone()
        
        if not admin_exists:
            import hashlib
            admin_password = hashlib.sha256("@Lice8127".encode()).hexdigest()
            
            cursor.execute("""
                INSERT INTO users (name, email, password, plan_id, plan_name, user_type, subscription_status, created_at) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (email) DO UPDATE SET 
                    user_type = 'admin',
                    plan_id = 2,
                    plan_name = 'Premium'
            """, (
                "Diego Doneda - Admin", 
                "diego@geminii.com.br", 
                admin_password, 
                2, 
                "Premium", 
                "admin",
                "active",
                datetime.now(timezone.utc)
            ))
            
            print("✅ Admin criado/atualizado")
        else:
            print("✅ Admin já existe")
        
        # 7. Commit de todas as alterações
        conn.commit()
        cursor.close()
        conn.close()
        
        print("\n🎉 CORREÇÃO DA ESTRUTURA CONCLUÍDA COM SUCESSO!")
        print("✅ Todos os campos necessários foram adicionados")
        print("✅ Tabelas de pagamento configuradas")
        print("✅ Índices criados para performance")
        print("✅ Sistema pronto para processar pagamentos!")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO na correção: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_payment_flow():
    """Testar fluxo completo de pagamento"""
    try:
        print("\n🧪 TESTANDO FLUXO DE PAGAMENTO")
        print("=" * 40)
        
        conn = get_db_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        # 1. Verificar se usuário teste existe
        test_email = "martha@gmail.com"
        cursor.execute("SELECT id, name, plan_name, subscription_status FROM users WHERE email = %s", (test_email,))
        user = cursor.fetchone()
        
        if user:
            user_id, name, plan_name, sub_status = user
            print(f"👤 Usuário teste: {name}")
            print(f"   📧 Email: {test_email}")
            print(f"   📦 Plano atual: {plan_name}")
            print(f"   🔄 Status: {sub_status}")
        else:
            # Criar usuário teste
            import hashlib
            password_hash = hashlib.sha256("123456".encode()).hexdigest()
            
            cursor.execute("""
                INSERT INTO users (name, email, password, plan_id, plan_name, subscription_status, created_at) 
                VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
            """, (
                "Martha Silva", test_email, password_hash, 1, "Pro", "inactive", datetime.now(timezone.utc)
            ))
            
            user_id = cursor.fetchone()[0]
            print(f"✅ Usuário teste criado: Martha Silva (ID: {user_id})")
        
        # 2. Verificar estrutura da tabela payments
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'payments'
            ORDER BY ordinal_position
        """)
        
        columns = cursor.fetchall()
        print(f"\n📊 Estrutura da tabela payments:")
        for col_name, col_type in columns:
            print(f"   • {col_name}: {col_type}")
        
        # 3. Verificar estrutura da tabela users (campos importantes)
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name IN ('subscription_status', 'subscription_plan', 'plan_expires_at', 'user_type')
        """)
        
        user_columns = [row[0] for row in cursor.fetchall()]
        print(f"\n👥 Campos especiais na tabela users:")
        for col in ['subscription_status', 'subscription_plan', 'plan_expires_at', 'user_type']:
            status = "✅" if col in user_columns else "❌"
            print(f"   {status} {col}")
        
        # 4. Simular inserção de pagamento
        try:
            test_payment_id = f"TEST_{int(datetime.now().timestamp())}"
            
            cursor.execute("""
                INSERT INTO payments (
                    user_id, payment_id, status, amount, plan_id, plan_name, 
                    cycle, external_reference, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                user_id, test_payment_id, "approved", 79.00, "pro", "Pro", "monthly", "test_reference"
            ))
            
            print(f"✅ Pagamento teste inserido: {test_payment_id}")
            
            # Atualizar usuário
            cursor.execute("""
                UPDATE users 
                SET subscription_status = %s, subscription_plan = %s 
                WHERE id = %s
            """, ("active", "Pro", user_id))
            
            print(f"✅ Usuário atualizado com sucesso")
            
            # Limpar teste
            cursor.execute("DELETE FROM payments WHERE payment_id = %s", (test_payment_id,))
            cursor.execute("UPDATE users SET subscription_status = %s WHERE id = %s", ("inactive", user_id))
            
            print(f"🧹 Dados de teste limpos")
            
        except Exception as e:
            print(f"❌ Erro no teste de inserção: {e}")
            return False
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"\n✅ TESTE CONCLUÍDO - Sistema funcionando!")
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        return False

def show_system_status():
    """Mostrar status atual do sistema"""
    try:
        print("\n📊 STATUS ATUAL DO SISTEMA")
        print("=" * 40)
        
        conn = get_db_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        # Contar usuários por plano
        cursor.execute("""
            SELECT plan_name, COUNT(*) 
            FROM users 
            GROUP BY plan_name
            ORDER BY COUNT(*) DESC
        """)
        
        print("👥 Usuários por plano:")
        for plan, count in cursor.fetchall():
            print(f"   • {plan}: {count} usuários")
        
        # Contar pagamentos
        cursor.execute("SELECT COUNT(*) FROM payments")
        payment_count = cursor.fetchone()[0]
        print(f"\n💳 Total de pagamentos: {payment_count}")
        
        # Últimos pagamentos
        cursor.execute("""
            SELECT p.payment_id, p.amount, p.plan_name, u.name, p.created_at
            FROM payments p
            JOIN users u ON p.user_id = u.id
            ORDER BY p.created_at DESC
            LIMIT 5
        """)
        
        print(f"\n📋 Últimos pagamentos:")
        for payment_id, amount, plan, user_name, created in cursor.fetchall():
            print(f"   • {payment_id}: R$ {amount} - {plan} - {user_name}")
        
        # Verificar admin
        cursor.execute("SELECT name, email FROM users WHERE user_type = 'admin'")
        admin = cursor.fetchone()
        
        if admin:
            print(f"\n👑 Admin: {admin[0]} ({admin[1]})")
        else:
            print(f"\n⚠️ Nenhum admin encontrado")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao verificar status: {e}")
        return False

if __name__ == "__main__":
    print("🚀 SCRIPT DE CORREÇÃO DO BANCO DE DADOS")
    print("Este script irá corrigir toda a estrutura necessária")
    print()
    
    # Executar correções
    if fix_database_structure():
        print("\n" + "="*60)
        test_payment_flow()
        print("\n" + "="*60) 
        show_system_status()
        
        print(f"\n🎯 PRÓXIMOS PASSOS:")
        print(f"1. Substitua o arquivo mercadopago_routes.py pelo código corrigido")
        print(f"2. Reinicie a aplicação")
        print(f"3. Teste um pagamento real")
        print(f"4. Verifique os logs do webhook em /webhook/mercadopago")
        print(f"5. Use /api/mercadopago/test-payment/<payment_id> para debug")
    else:
        print("❌ Falha na correção da estrutura")
#!/usr/bin/env python3
# fix_auth_issues.py - Corrigir problemas de autenticação
# ======================================================

import os
import hashlib
from datetime import datetime, timezone
from database import get_db_connection

def hash_password(password):
    """Hash da senha"""
    return hashlib.sha256(password.encode()).hexdigest()

def fix_database_structure():
    """🔧 Corrigir estrutura do banco de dados"""
    try:
        print("🔧 Verificando e corrigindo estrutura do banco...")
        
        conn = get_db_connection()
        if not conn:
            print("❌ Erro de conexão com banco")
            return False
        
        cursor = conn.cursor()
        
        # 1. Verificar se campos de confirmação existem
        print("\n1️⃣ Verificando campos de confirmação de email...")
        
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name IN ('email_confirmed', 'email_confirmed_at')
        """)
        
        existing_columns = [row[0] for row in cursor.fetchall()]
        
        if 'email_confirmed' not in existing_columns:
            print("   ➕ Adicionando campo email_confirmed...")
            cursor.execute("""
                ALTER TABLE users 
                ADD COLUMN email_confirmed BOOLEAN DEFAULT TRUE
            """)
        else:
            print("   ✅ Campo email_confirmed já existe")
        
        if 'email_confirmed_at' not in existing_columns:
            print("   ➕ Adicionando campo email_confirmed_at...")
            cursor.execute("""
                ALTER TABLE users 
                ADD COLUMN email_confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """)
        else:
            print("   ✅ Campo email_confirmed_at já existe")
        
        # 2. Criar tabela email_confirmations se não existir
        print("\n2️⃣ Verificando tabela email_confirmations...")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_confirmations (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                token VARCHAR(255) UNIQUE NOT NULL,
                email VARCHAR(255) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                confirmed BOOLEAN DEFAULT FALSE,
                confirmed_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("   ✅ Tabela email_confirmations verificada")
        
        # 3. Criar tabela password_reset_tokens se não existir
        print("\n3️⃣ Verificando tabela password_reset_tokens...")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                token VARCHAR(255) UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("   ✅ Tabela password_reset_tokens verificada")
        
        # 4. Criar índices
        print("\n4️⃣ Criando índices...")
        
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_confirmations_token ON email_confirmations(token)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_password_reset_token ON password_reset_tokens(token)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email_confirmed ON users(email_confirmed)")
            print("   ✅ Índices criados")
        except Exception as e:
            print(f"   ⚠️ Aviso ao criar índices: {e}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("\n🎉 Estrutura do banco corrigida com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao corrigir estrutura: {e}")
        return False

def confirm_all_existing_users():
    """✅ Confirmar email de todos os usuários existentes"""
    try:
        print("\n✅ Confirmando email de todos os usuários existentes...")
        
        conn = get_db_connection()
        if not conn:
            print("❌ Erro de conexão")
            return False
        
        cursor = conn.cursor()
        
        # Confirmar todos os usuários que ainda não estão confirmados
        cursor.execute("""
            UPDATE users 
            SET email_confirmed = TRUE, 
                email_confirmed_at = COALESCE(email_confirmed_at, CURRENT_TIMESTAMP)
            WHERE email_confirmed IS NULL OR email_confirmed = FALSE
        """)
        
        updated_count = cursor.rowcount
        
        if updated_count > 0:
            print(f"   ✅ {updated_count} usuários confirmados")
        else:
            print("   ℹ️ Todos os usuários já estavam confirmados")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao confirmar usuários: {e}")
        return False

def create_admin_user():
    """👑 Criar usuário administrador padrão"""
    try:
        print("\n👑 Criando usuário administrador...")
        
        admin_email = "diego@geminii.com.br"
        admin_password = "@Lice8127"
        admin_name = "Diego Administrador"
        
        conn = get_db_connection()
        if not conn:
            print("❌ Erro de conexão")
            return False
        
        cursor = conn.cursor()
        
        # Verificar se admin já existe
        cursor.execute("SELECT id, name FROM users WHERE email = %s", (admin_email,))
        existing_admin = cursor.fetchone()
        
        if existing_admin:
            admin_id, name = existing_admin
            print(f"   ℹ️ Admin já existe: {name} (ID: {admin_id})")
            
            # Atualizar para garantir que está confirmado e é admin
            cursor.execute("""
                UPDATE users 
                SET user_type = 'admin', 
                    email_confirmed = TRUE,
                    email_confirmed_at = COALESCE(email_confirmed_at, CURRENT_TIMESTAMP),
                    plan_id = 2,
                    plan_name = 'Premium'
                WHERE email = %s
            """, (admin_email,))
            
            print("   ✅ Privilégios de admin atualizados")
            
        else:
            # Criar novo admin
            hashed_password = hash_password(admin_password)
            
            cursor.execute("""
                INSERT INTO users (
                    name, email, password, user_type, plan_id, plan_name,
                    email_confirmed, email_confirmed_at, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                admin_name, admin_email, hashed_password, 'admin', 2, 'Premium',
                True, datetime.now(timezone.utc), datetime.now(timezone.utc)
            ))
            
            admin_id = cursor.fetchone()[0]
            print(f"   ✅ Admin criado: {admin_name} (ID: {admin_id})")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"\n📋 CREDENCIAIS DO ADMIN:")
        print(f"   Email: {admin_email}")
        print(f"   Senha: {admin_password}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar admin: {e}")
        return False

def verify_auth_flow():
    """🔍 Verificar fluxo completo de autenticação"""
    try:
        print("\n🔍 Verificando fluxo de autenticação...")
        
        # 1. Verificar conexão
        print("1️⃣ Testando conexão com banco...")
        conn = get_db_connection()
        if not conn:
            print("   ❌ Falha na conexão")
            return False
        
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"   ✅ Conexão OK - {user_count} usuários")
        
        # 2. Verificar estrutura
        print("2️⃣ Verificando estrutura da tabela users...")
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'users'
            ORDER BY ordinal_position
        """)
        
        columns = cursor.fetchall()
        required_columns = ['id', 'name', 'email', 'password', 'email_confirmed']
        
        existing_columns = [col[0] for col in columns]
        missing_columns = [col for col in required_columns if col not in existing_columns]
        
        if missing_columns:
            print(f"   ❌ Colunas ausentes: {missing_columns}")
            return False
        else:
            print("   ✅ Estrutura da tabela OK")
        
        # 3. Verificar usuários confirmados
        print("3️⃣ Verificando status de confirmação...")
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN email_confirmed = TRUE THEN 1 END) as confirmed,
                COUNT(CASE WHEN email_confirmed = FALSE OR email_confirmed IS NULL THEN 1 END) as unconfirmed
            FROM users
        """)
        
        total, confirmed, unconfirmed = cursor.fetchone()
        print(f"   📊 Total: {total} | Confirmados: {confirmed} | Não confirmados: {unconfirmed}")
        
        if unconfirmed > 0:
            print(f"   ⚠️ {unconfirmed} usuários não confirmados podem ter problemas de login")
        
        # 4. Testar admin
        print("4️⃣ Verificando usuário admin...")
        cursor.execute("""
            SELECT id, name, email, user_type, email_confirmed
            FROM users 
            WHERE email = 'diego@geminii.com.br'
        """)
        
        admin = cursor.fetchone()
        if admin:
            admin_id, name, email, user_type, email_confirmed = admin
            print(f"   ✅ Admin encontrado: {name}")
            print(f"      Tipo: {user_type}")
            print(f"      Confirmado: {email_confirmed}")
            
            if not email_confirmed:
                print("   ⚠️ Admin não confirmado!")
            if user_type != 'admin':
                print(f"   ⚠️ Tipo incorreto: {user_type}")
        else:
            print("   ❌ Admin não encontrado")
        
        cursor.close()
        conn.close()
        
        print("\n✅ Verificação de fluxo concluída")
        return True
        
    except Exception as e:
        print(f"❌ Erro na verificação: {e}")
        import traceback
        traceback.print_exc()
        return False

def fix_common_issues():
    """🔧 Corrigir problemas comuns"""
    try:
        print("🔧 Iniciando correção de problemas comuns...")
        
        success = True
        
        # 1. Corrigir estrutura do banco
        if not fix_database_structure():
            success = False
        
        # 2. Confirmar usuários existentes
        if not confirm_all_existing_users():
            success = False
        
        # 3. Criar/atualizar admin
        if not create_admin_user():
            success = False
        
        # 4. Verificar fluxo
        if not verify_auth_flow():
            success = False
        
        if success:
            print("\n🎉 TODOS OS PROBLEMAS FORAM CORRIGIDOS!")
            print("\n📋 PRÓXIMOS PASSOS:")
            print("1. Reinicie o servidor Flask")
            print("2. Tente fazer login com: diego@geminii.com.br / @Lice8127")
            print("3. Se ainda houver problemas, execute: python debug_login.py test diego@geminii.com.br @Lice8127")
        else:
            print("\n❌ ALGUNS PROBLEMAS NÃO FORAM RESOLVIDOS")
            print("Execute o debug para mais detalhes: python debug_login.py")
        
        return success
        
    except Exception as e:
        print(f"❌ Erro durante correção: {e}")
        return False

def main():
    """🚀 Menu principal"""
    print("🔧 GEMINII TECH - CORREÇÃO DE PROBLEMAS DE AUTH")
    print("=" * 50)
    
    while True:
        print(f"\n📋 OPÇÕES:")
        print("1. Corrigir todos os problemas (recomendado)")
        print("2. Apenas corrigir estrutura do banco")
        print("3. Apenas confirmar usuários existentes")
        print("4. Apenas criar/atualizar admin")
        print("5. Apenas verificar fluxo")
        print("0. Sair")
        
        choice = input("\n👉 Escolha: ").strip()
        
        if choice == "1":
            fix_common_issues()
        elif choice == "2":
            fix_database_structure()
        elif choice == "3":
            confirm_all_existing_users()
        elif choice == "4":
            create_admin_user()
        elif choice == "5":
            verify_auth_flow()
        elif choice == "0":
            print("👋 Saindo...")
            break
        else:
            print("❌ Opção inválida!")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "auto":
        # Correção automática
        print("🚀 Executando correção automática...")
        fix_common_issues()
    else:
        # Menu interativo
        main()
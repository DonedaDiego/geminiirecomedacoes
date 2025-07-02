#!/usr/bin/env python3
# debug_login.py - Script para debugar problemas de login
# =====================================================

import os
import hashlib
from datetime import datetime, timezone
from database import get_db_connection
from email_service import email_service

def hash_password(password):
    """Hash da senha igual ao auth_routes.py"""
    return hashlib.sha256(password.encode()).hexdigest()

def debug_user_login(email, password=None):
    """🔍 Debug completo de um usuário"""
    try:
        print(f"\n{'='*50}")
        print(f"🔍 DEBUG LOGIN - {email}")
        print(f"{'='*50}")
        
        conn = get_db_connection()
        if not conn:
            print("❌ ERRO: Não foi possível conectar ao banco")
            return False
        
        cursor = conn.cursor()
        
        # 1. Verificar se usuário existe
        print("\n1️⃣ VERIFICANDO EXISTÊNCIA DO USUÁRIO")
        cursor.execute("""
            SELECT id, name, email, password, plan_id, plan_name, user_type, 
                   email_confirmed, email_confirmed_at, created_at
            FROM users WHERE email = %s
        """, (email,))
        
        user = cursor.fetchone()
        
        if not user:
            print(f"❌ USUÁRIO NÃO ENCONTRADO: {email}")
            cursor.close()
            conn.close()
            return False
        
        user_id, name, user_email, stored_password, plan_id, plan_name, user_type, email_confirmed, email_confirmed_at, created_at = user
        
        print(f"✅ Usuário encontrado:")
        print(f"   ID: {user_id}")
        print(f"   Nome: {name}")
        print(f"   Email: {user_email}")
        print(f"   Plano: {plan_name} (ID: {plan_id})")
        print(f"   Tipo: {user_type}")
        print(f"   Criado em: {created_at}")
        print(f"   Email confirmado: {email_confirmed}")
        print(f"   Confirmado em: {email_confirmed_at}")
        
        # 2. Verificar senha (se fornecida)
        if password:
            print(f"\n2️⃣ VERIFICANDO SENHA")
            input_hash = hash_password(password)
            print(f"   Hash da senha informada: {input_hash[:20]}...")
            print(f"   Hash armazenado no banco: {stored_password[:20]}...")
            
            if input_hash == stored_password:
                print("✅ SENHA CORRETA")
            else:
                print("❌ SENHA INCORRETA")
                print("   ⚠️ As senhas não coincidem!")
        
        # 3. Verificar status de confirmação de email
        print(f"\n3️⃣ STATUS DE CONFIRMAÇÃO DE EMAIL")
        if email_confirmed:
            print("✅ EMAIL CONFIRMADO - Login deveria funcionar")
        else:
            print("❌ EMAIL NÃO CONFIRMADO - Login será bloqueado")
            
            # Verificar tokens de confirmação pendentes
            cursor.execute("""
                SELECT token, expires_at, confirmed, created_at
                FROM email_confirmations 
                WHERE user_id = %s 
                ORDER BY created_at DESC
                LIMIT 3
            """, (user_id,))
            
            tokens = cursor.fetchall()
            
            if tokens:
                print("   📧 Tokens de confirmação encontrados:")
                for i, (token, expires_at, confirmed, created_at) in enumerate(tokens, 1):
                    status = "✅ CONFIRMADO" if confirmed else "⏳ PENDENTE"
                    print(f"     {i}. Token: {token[:20]}... - {status}")
                    print(f"        Criado: {created_at}")
                    print(f"        Expira: {expires_at}")
            else:
                print("   ⚠️ Nenhum token de confirmação encontrado")
        
        # 4. Verificar integridade da estrutura do banco
        print(f"\n4️⃣ VERIFICANDO ESTRUTURA DO BANCO")
        
        # Verificar se campos existem
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name IN ('email_confirmed', 'email_confirmed_at')
            ORDER BY column_name
        """)
        
        columns = cursor.fetchall()
        
        if len(columns) == 2:
            print("✅ Campos de confirmação de email existem na tabela users")
            for column_name, data_type, is_nullable in columns:
                print(f"   - {column_name}: {data_type} (nullable: {is_nullable})")
        else:
            print("❌ ERRO: Campos de confirmação de email ausentes!")
            print("   Execute: python email_service.py para criar as tabelas")
        
        # 5. Testar geração de JWT (simulado)
        print(f"\n5️⃣ SIMULANDO GERAÇÃO DE JWT")
        try:
            import jwt
            from datetime import timedelta
            
            # Simular secret key
            secret_key = "test_secret_key_123"
            
            payload = {
                'user_id': user_id,
                'email': user_email,
                'exp': datetime.now(timezone.utc) + timedelta(days=7)
            }
            
            token = jwt.encode(payload, secret_key, algorithm='HS256')
            print(f"✅ JWT gerado com sucesso: {token[:50]}...")
            
            # Testar decodificação
            decoded = jwt.decode(token, secret_key, algorithms=['HS256'])
            print(f"✅ JWT decodificado: user_id={decoded['user_id']}, email={decoded['email']}")
            
        except Exception as e:
            print(f"❌ ERRO ao gerar JWT: {e}")
        
        cursor.close()
        conn.close()
        
        # 6. Resumo final
        print(f"\n6️⃣ RESUMO DO DIAGNÓSTICO")
        
        login_ok = True
        issues = []
        
        if not email_confirmed:
            login_ok = False
            issues.append("Email não confirmado")
        
        if password and hash_password(password) != stored_password:
            login_ok = False
            issues.append("Senha incorreta")
        
        if login_ok:
            print("🎉 LOGIN DEVERIA FUNCIONAR!")
            print("   Todos os requisitos estão atendidos")
        else:
            print("❌ LOGIN NÃO VAI FUNCIONAR!")
            print("   Problemas encontrados:")
            for issue in issues:
                print(f"   - {issue}")
        
        return login_ok
        
    except Exception as e:
        print(f"❌ ERRO DURANTE DEBUG: {e}")
        import traceback
        traceback.print_exc()
        return False

def debug_database_connection():
    """🔍 Debug da conexão com banco"""
    print(f"\n{'='*50}")
    print("🔍 DEBUG CONEXÃO COM BANCO")
    print(f"{'='*50}")
    
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            
            # Testar query simples
            cursor.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
            
            print(f"✅ Conexão OK - {count} usuários na base")
            
            cursor.close()
            conn.close()
            return True
        else:
            print("❌ Falha na conexão")
            return False
            
    except Exception as e:
        print(f"❌ ERRO: {e}")
        return False

def debug_email_service():
    """🔍 Debug do serviço de email"""
    print(f"\n{'='*50}")
    print("🔍 DEBUG EMAIL SERVICE")
    print(f"{'='*50}")
    
    try:
        print(f"Modo teste: {email_service.test_mode}")
        print(f"Base URL: {email_service.base_url}")
        print(f"SMTP Server: {email_service.smtp_server}")
        
        # Verificar se métodos existem
        methods = [
            'generate_confirmation_token',
            'confirm_email_token', 
            'send_confirmation_email',
            'generate_password_reset_token',
            'validate_password_reset_token',
            'reset_password_with_token'
        ]
        
        print("\n📧 Métodos disponíveis:")
        for method in methods:
            if hasattr(email_service, method):
                print(f"   ✅ {method}")
            else:
                print(f"   ❌ {method} - AUSENTE!")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO: {e}")
        return False

def fix_user_email_confirmation(email):
    """🔧 Forçar confirmação de email para um usuário"""
    try:
        print(f"\n🔧 FORÇANDO CONFIRMAÇÃO DE EMAIL PARA: {email}")
        
        conn = get_db_connection()
        if not conn:
            print("❌ Erro de conexão")
            return False
        
        cursor = conn.cursor()
        
        # Verificar se usuário existe
        cursor.execute("SELECT id, name FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if not user:
            print(f"❌ Usuário não encontrado: {email}")
            cursor.close()
            conn.close()
            return False
        
        user_id, name = user
        
        # Forçar confirmação
        cursor.execute("""
            UPDATE users 
            SET email_confirmed = TRUE, email_confirmed_at = %s
            WHERE email = %s
        """, (datetime.now(timezone.utc), email))
        
        # Verificar se foi atualizado
        if cursor.rowcount > 0:
            print(f"✅ Email confirmado forçadamente para: {name}")
            conn.commit()
            result = True
        else:
            print("❌ Falha ao forçar confirmação")
            result = False
        
        cursor.close()
        conn.close()
        return result
        
    except Exception as e:
        print(f"❌ ERRO: {e}")
        return False

def main():
    """🚀 Menu principal de debug"""
    print("🔍 GEMINII TECH - SISTEMA DE DEBUG LOGIN")
    print("="*50)
    
    while True:
        print(f"\n📋 OPÇÕES DISPONÍVEIS:")
        print("1. Debug conexão com banco")
        print("2. Debug email service")
        print("3. Debug login de usuário específico")
        print("4. Forçar confirmação de email")
        print("5. Listar todos os usuários")
        print("0. Sair")
        
        choice = input("\n👉 Escolha uma opção: ").strip()
        
        if choice == "1":
            debug_database_connection()
            
        elif choice == "2":
            debug_email_service()
            
        elif choice == "3":
            email = input("📧 Email do usuário: ").strip().lower()
            password = input("🔑 Senha (opcional, Enter para pular): ").strip()
            if not password:
                password = None
            debug_user_login(email, password)
            
        elif choice == "4":
            email = input("📧 Email para forçar confirmação: ").strip().lower()
            fix_user_email_confirmation(email)
            
        elif choice == "5":
            list_all_users()
            
        elif choice == "5":
            list_all_users()
            
        elif choice == "0":
            print("👋 Saindo do sistema de debug...")
            break
            
        else:
            print("❌ Opção inválida!")

def list_all_users():
    """📋 Listar todos os usuários"""
    try:
        print(f"\n{'='*50}")
        print("📋 LISTA DE TODOS OS USUÁRIOS")
        print(f"{'='*50}")
        
        conn = get_db_connection()
        if not conn:
            print("❌ Erro de conexão")
            return
        
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, email, plan_name, user_type, 
                   email_confirmed, created_at
            FROM users 
            ORDER BY created_at DESC
        """)
        
        users = cursor.fetchall()
        
        if not users:
            print("⚠️ Nenhum usuário encontrado")
        else:
            print(f"📊 Total: {len(users)} usuários\n")
            
            for i, (user_id, name, email, plan_name, user_type, email_confirmed, created_at) in enumerate(users, 1):
                status = "✅" if email_confirmed else "❌"
                print(f"{i:2d}. {status} {name}")
                print(f"     📧 {email}")
                print(f"     🎫 {plan_name} | {user_type}")
                print(f"     📅 {created_at}")
                print()
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ ERRO: {e}")

def quick_test_login(email="diego@geminii.com.br", password="@Lice8127"):
    """⚡ Teste rápido de login com credenciais padrão"""
    print(f"\n⚡ TESTE RÁPIDO DE LOGIN")
    print(f"Email: {email}")
    print(f"Senha: {'*' * len(password)}")
    
    return debug_user_login(email, password)

if __name__ == "__main__":
    # Teste rápido se executado diretamente
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "quick":
            # Teste rápido
            quick_test_login()
        elif sys.argv[1] == "fix":
            # Forçar confirmação para email específico
            email = sys.argv[2] if len(sys.argv) > 2 else "diego@geminii.com.br"
            fix_user_email_confirmation(email)
        elif sys.argv[1] == "test":
            # Debug usuário específico
            email = sys.argv[2] if len(sys.argv) > 2 else "diego@geminii.com.br"
            password = sys.argv[3] if len(sys.argv) > 3 else "@Lice8127"
            debug_user_login(email, password)
    else:
        # Menu interativo
        main()
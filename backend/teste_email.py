# single_email_test.py - Teste de Um Email Específico
# ====================================================

import sys
import os
from datetime import datetime, timezone, timedelta

# Adicionar o diretório backend ao Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from email_service import email_service
from trial_service import send_trial_expiring_email
from control_pay_service import send_renewal_warning_email

def test_single_email():
    """🎯 Testar apenas um email específico"""
    
    # 🔥 SUAS CONFIGURAÇÕES
    test_email = "diedoneda@gmail.com"
    test_name = "Diego Doneda"
    
    print("🎯 TESTE DE EMAIL ESPECÍFICO")
    print("=" * 40)
    print(f"📧 Email: {test_email}")
    print(f"👤 Nome: {test_name}")
    print()
    
    # Escolher tipo de email
    print("Escolha o tipo de email para testar:")
    print("1. 🧪 Email básico de teste")
    print("2. ⏰ Trial expirando em 3 dias")
    print("3. 🚨 Trial expirando HOJE")
    print("4. 🎉 Boas-vindas ao trial")
    print("5. 😔 Trial expirado")
    print("6. 💳 Pagamento expirando em 3 dias")
    print("7. 🚨 Pagamento expirando HOJE")
    print("8. ✅ Pagamento confirmado")
    print("9. ❌ Pagamento falhou")
    print("10. 💡 Assinatura expirada")
    
    try:
        choice = input("\nEscolha (1-10): ").strip()
        
        print(f"\n🚀 Enviando email tipo {choice}...")
        
        result = False
        
        if choice == "1":
            # Email básico
            result = email_service.send_email(
                test_email,
                "🧪 Teste Manual - Geminii Tech",
                f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h1 style="color: #ba39af;">🧪 Teste Manual</h1>
                    <p>Olá <strong>{test_name}</strong>!</p>
                    <p>Este é um email de teste manual enviado em:</p>
                    <p><strong>{datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}</strong></p>
                    <hr>
                    <p>Se você recebeu este email, significa que:</p>
                    <ul>
                        <li>✅ O SMTP está configurado corretamente</li>
                        <li>✅ As credenciais estão funcionando</li>
                        <li>✅ O sistema de emails está operacional</li>
                    </ul>
                    <p style="color: #ba39af;"><strong>Sistema funcionando perfeitamente! 🎉</strong></p>
                </div>
                """
            )
            
        elif choice == "2":
            # Trial 3 dias
            result = email_service.send_trial_reminder_email(test_name, test_email, 3)
            
        elif choice == "3":
            # Trial HOJE
            result = email_service.send_trial_reminder_email(test_name, test_email, 1)
            
        elif choice == "4":
            # Boas-vindas trial
            result = email_service.send_trial_welcome_email(test_name, test_email)
            
        elif choice == "5":
            # Trial expirado
            result = email_service.send_trial_expired_email(test_name, test_email)
            
        elif choice == "6":
            # Pagamento 3 dias
            result = email_service.send_payment_reminder_email(
                test_name, test_email, "Premium", 3, "R$ 89,00"
            )
            
        elif choice == "7":
            # Pagamento HOJE
            result = email_service.send_payment_reminder_email(
                test_name, test_email, "Premium", 1, "R$ 89,00"
            )
            
        elif choice == "8":
            # Pagamento confirmado
            result = email_service.send_payment_success_email(
                test_name, test_email, "Premium", "R$ 89,00"
            )
            
        elif choice == "9":
            # Pagamento falhou
            result = email_service.send_payment_failed_email(
                test_name, test_email, "Premium", "20/01/2025"
            )
            
        elif choice == "10":
            # Assinatura expirada
            result = email_service.send_payment_expired_email(
                test_name, test_email, "Premium"
            )
            
        else:
            print("❌ Opção inválida!")
            return
        
        # Resultado
        print(f"\n📧 Resultado: {'✅ EMAIL ENVIADO!' if result else '❌ FALHA NO ENVIO'}")
        
        if result:
            print(f"📬 Verifique sua caixa de entrada: {test_email}")
            print("📱 Verifique também a pasta de SPAM/Lixo Eletrônico")
            print("⏱️  Pode levar alguns minutos para chegar")
        else:
            print("🔧 Verifique as configurações SMTP:")
            print(f"   Server: {email_service.smtp_server}")
            print(f"   Port: {email_service.smtp_port}")
            print(f"   User: {email_service.smtp_username}")
            print(f"   From: {email_service.from_email}")
            
    except KeyboardInterrupt:
        print("\n🛑 Teste cancelado pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro durante o teste: {e}")

def test_trial_expiring_with_real_data():
    """🎯 Testar com dados reais do banco"""
    
    print("\n🎯 TESTE COM DADOS REAIS DO BANCO")
    print("=" * 40)
    
    try:
        from database import get_db_connection
        
        conn = get_db_connection()
        if not conn:
            print("❌ Erro de conexão com banco")
            return
            
        cursor = conn.cursor()
        
        # Buscar usuários em trial que estão expirando
        cursor.execute("""
            SELECT id, name, email, plan_name, plan_expires_at,
                   EXTRACT(days FROM (plan_expires_at - NOW())) as days_remaining
            FROM users 
            WHERE user_type = 'trial' 
            AND plan_expires_at IS NOT NULL 
            AND plan_expires_at BETWEEN NOW() AND NOW() + INTERVAL '7 days'
            ORDER BY plan_expires_at ASC
            LIMIT 5
        """)
        
        trials = cursor.fetchall()
        
        if not trials:
            print("⚠️ Nenhum trial expirando encontrado no banco")
            print("💡 Criando usuário de teste...")
            
            # Criar usuário de teste
            test_email = "diedoneda@gmail.com"
            test_name = "Diego Doneda - Teste"
            
            import hashlib
            password_hash = hashlib.sha256("teste123".encode()).hexdigest()
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(days=2)
            
            cursor.execute("""
                INSERT INTO users (
                    name, email, password, plan_id, plan_name, user_type,
                    plan_expires_at, created_at, updated_at, email_confirmed
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (email) DO UPDATE SET
                    user_type = 'trial',
                    plan_id = 2,
                    plan_name = 'Premium',
                    plan_expires_at = EXCLUDED.plan_expires_at
            """, (
                test_name, test_email, password_hash,
                2, 'Premium', 'trial',
                expires_at, now, now, True
            ))
            
            conn.commit()
            print(f"✅ Usuário de teste criado: {test_email}")
            
            # Buscar novamente
            cursor.execute("""
                SELECT id, name, email, plan_name, plan_expires_at,
                       EXTRACT(days FROM (plan_expires_at - NOW())) as days_remaining
                FROM users 
                WHERE email = %s
            """, (test_email,))
            
            trials = cursor.fetchall()
        
        print(f"\n📋 Encontrados {len(trials)} usuários:")
        
        for i, (user_id, name, email, plan_name, expires_at, days_remaining) in enumerate(trials, 1):
            days_remaining = int(days_remaining) if days_remaining else 0
            
            print(f"\n{i}. {name} ({email})")
            print(f"   Plano: {plan_name}")
            print(f"   Expira em: {days_remaining} dias")
            print(f"   Data: {expires_at.strftime('%d/%m/%Y') if expires_at else 'N/A'}")
            
            # Enviar email
            user_info = {
                'name': name,
                'email': email,
                'plan_name': plan_name,
                'expires_at': expires_at.strftime('%d/%m/%Y') if expires_at else 'N/A'
            }
            
            result = send_trial_expiring_email(user_info, days_remaining)
            print(f"   📧 Email: {'✅ Enviado' if result else '❌ Falha'}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erro: {e}")

def test_payment_expiring_with_real_data():
    """💳 Testar emails de pagamento com dados reais"""
    
    print("\n💳 TESTE DE PAGAMENTOS COM DADOS REAIS")
    print("=" * 40)
    
    try:
        from database import get_db_connection
        
        conn = get_db_connection()
        if not conn:
            print("❌ Erro de conexão com banco")
            return
            
        cursor = conn.cursor()
        
        # Buscar usuários com assinatura expirando
        cursor.execute("""
            SELECT id, name, email, plan_name, plan_expires_at,
                   EXTRACT(days FROM (plan_expires_at - NOW())) as days_remaining
            FROM users 
            WHERE user_type != 'trial' 
            AND plan_expires_at IS NOT NULL 
            AND plan_expires_at BETWEEN NOW() AND NOW() + INTERVAL '7 days'
            AND plan_id IN (1, 2)
            ORDER BY plan_expires_at ASC
            LIMIT 5
        """)
        
        payments = cursor.fetchall()
        
        if not payments:
            print("⚠️ Nenhuma assinatura expirando encontrada")
            print("💡 Criando usuário de teste...")
            
            # Criar usuário de teste com assinatura
            test_email = "diedoneda@gmail.com"
            test_name = "Diego Doneda - Pagamento Teste"
            
            import hashlib
            password_hash = hashlib.sha256("teste123".encode()).hexdigest()
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(days=3)
            
            cursor.execute("""
                INSERT INTO users (
                    name, email, password, plan_id, plan_name, user_type,
                    plan_expires_at, created_at, updated_at, email_confirmed
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (email) DO UPDATE SET
                    user_type = 'regular',
                    plan_id = 2,
                    plan_name = 'Premium',
                    plan_expires_at = EXCLUDED.plan_expires_at
            """, (
                test_name, test_email, password_hash,
                2, 'Premium', 'regular',
                expires_at, now, now, True
            ))
            
            conn.commit()
            print(f"✅ Usuário de teste criado: {test_email}")
            
            # Buscar novamente
            cursor.execute("""
                SELECT id, name, email, plan_name, plan_expires_at,
                       EXTRACT(days FROM (plan_expires_at - NOW())) as days_remaining
                FROM users 
                WHERE email = %s
            """, (test_email,))
            
            payments = cursor.fetchall()
        
        print(f"\n📋 Encontrados {len(payments)} usuários:")
        
        for i, (user_id, name, email, plan_name, expires_at, days_remaining) in enumerate(payments, 1):
            days_remaining = int(days_remaining) if days_remaining else 0
            
            print(f"\n{i}. {name} ({email})")
            print(f"   Plano: {plan_name}")
            print(f"   Expira em: {days_remaining} dias")
            print(f"   Data: {expires_at.strftime('%d/%m/%Y') if expires_at else 'N/A'}")
            
            # Enviar email
            user_info = {
                'name': name,
                'email': email,
                'plan_name': plan_name,
                'expires_at': expires_at.strftime('%d/%m/%Y') if expires_at else 'N/A'
            }
            
            result = send_renewal_warning_email(user_info, days_remaining)
            print(f"   📧 Email: {'✅ Enviado' if result else '❌ Falha'}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Erro: {e}")

def main():
    """🚀 Menu principal"""
    
    print("🎯 TESTE DE EMAIL ESPECÍFICO")
    print("=" * 40)
    print("1. 📧 Enviar um email específico")
    print("2. 🎯 Testar trial com dados reais do banco")
    print("3. 💳 Testar pagamento com dados reais do banco")
    
    try:
        choice = input("\nEscolha uma opção (1-3): ").strip()
        
        if choice == "1":
            test_single_email()
        elif choice == "2":
            test_trial_expiring_with_real_data()
        elif choice == "3":
            test_payment_expiring_with_real_data()
        else:
            print("❌ Opção inválida!")
            
    except KeyboardInterrupt:
        print("\n🛑 Teste cancelado")

if __name__ == "__main__":
    main()
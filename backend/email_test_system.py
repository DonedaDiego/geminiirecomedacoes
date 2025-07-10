#!/usr/bin/env python3
"""
🧪 TESTE CORRIGIDO DE EMAILS - CONSOLE
Testa todos os emails do sistema enviando para diedoneda@gmail.com
"""

import sys
import os
from datetime import datetime

# Adicionar o diretório do projeto ao path
sys.path.append('.')

from email_service import email_service
from database import get_db_connection

# Email de teste
TEST_EMAIL = "diedoneda@gmail.com"
TEST_NAME = "Diego Doneda"

def print_header(title):
    """Imprime cabeçalho bonito"""
    print(f"\n{'='*60}")
    print(f"🧪 {title}")
    print(f"{'='*60}")

def print_result(test_name, success, message):
    """Imprime resultado do teste"""
    status = "✅ SUCESSO" if success else "❌ ERRO"
    print(f"{status} | {test_name}: {message}")

def ensure_test_user():
    """Garante que o usuário de teste existe"""
    try:
        conn = get_db_connection()
        if not conn:
            print("❌ Erro de conexão com banco")
            return None
        
        cursor = conn.cursor()
        
        # Verificar se usuário existe
        cursor.execute("SELECT id FROM users WHERE email = %s", (TEST_EMAIL,))
        user = cursor.fetchone()
        
        if not user:
            # Criar usuário temporário para teste
            cursor.execute("""
                INSERT INTO users (name, email, password, plan_id, plan_name, user_type, email_confirmed, ip_address)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (TEST_NAME, TEST_EMAIL, "temp_password", 1, "Basico", "basic", True, "127.0.0.1"))
            user_id = cursor.fetchone()[0]
            conn.commit()
            print(f"👤 Usuário temporário criado: {TEST_EMAIL} (ID: {user_id})")
        else:
            user_id = user[0]
            print(f"👤 Usuário encontrado: {TEST_EMAIL} (ID: {user_id})")
        
        cursor.close()
        conn.close()
        
        return user_id
        
    except Exception as e:
        print(f"❌ Erro ao garantir usuário: {str(e)}")
        return None

def test_confirmation_email():
    """Teste de email de confirmação"""
    print_header("TESTE DE EMAIL DE CONFIRMAÇÃO")
    
    try:
        user_id = ensure_test_user()
        if not user_id:
            return False
        
        # Gerar token de confirmação
        token_result = email_service.generate_confirmation_token(user_id, TEST_EMAIL)
        
        if not token_result['success']:
            print_result("Confirmação", False, f"Erro ao gerar token: {token_result['error']}")
            return False
        
        # Enviar email de confirmação
        email_sent = email_service.send_confirmation_email(TEST_NAME, TEST_EMAIL, token_result['token'])
        
        if email_sent:
            print_result("Confirmação", True, f"Email enviado para {TEST_EMAIL}")
            return True
        else:
            print_result("Confirmação", False, "Erro ao enviar email")
            return False
            
    except Exception as e:
        print_result("Confirmação", False, f"Exceção: {str(e)}")
        return False

def test_password_reset_email():
    """Teste de email de reset de senha"""
    print_header("TESTE DE EMAIL DE RESET DE SENHA")
    
    try:
        user_id = ensure_test_user()
        if not user_id:
            return False
        
        # Gerar token de reset
        result = email_service.generate_password_reset_token(TEST_EMAIL)
        
        if not result['success']:
            print_result("Reset Senha", False, f"Erro ao gerar token: {result['error']}")
            return False
        
        # Enviar email de reset
        email_sent = email_service.send_password_reset_email(
            result['user_name'], 
            result['user_email'], 
            result['token']
        )
        
        if email_sent:
            print_result("Reset Senha", True, f"Email enviado para {TEST_EMAIL}")
            return True
        else:
            print_result("Reset Senha", False, "Erro ao enviar email")
            return False
            
    except Exception as e:
        print_result("Reset Senha", False, f"Exceção: {str(e)}")
        return False

def test_trial_emails():
    """Teste de emails de trial"""
    print_header("TESTE DE EMAILS DE TRIAL")
    
    results = []
    
    try:
        user_id = ensure_test_user()
        if not user_id:
            return False
        
        # 1. Teste email de boas-vindas ao trial
        try:
            welcome_sent = email_service.send_trial_welcome_email(TEST_NAME, TEST_EMAIL)
            if welcome_sent:
                print_result("Trial Welcome", True, "Email de boas-vindas enviado!")
                results.append(True)
            else:
                print_result("Trial Welcome", False, "Erro ao enviar email de boas-vindas")
                results.append(False)
        except Exception as e:
            print_result("Trial Welcome", False, f"Erro: {str(e)}")
            results.append(False)
        
        # 2. Teste email de lembrete - 7 dias
        try:
            reminder_7_sent = email_service.send_trial_reminder_email(TEST_NAME, TEST_EMAIL, 7)
            if reminder_7_sent:
                print_result("Trial Reminder 7d", True, "Email de lembrete (7 dias) enviado!")
                results.append(True)
            else:
                print_result("Trial Reminder 7d", False, "Erro ao enviar lembrete 7 dias")
                results.append(False)
        except Exception as e:
            print_result("Trial Reminder 7d", False, f"Erro: {str(e)}")
            results.append(False)
        
        # 3. Teste email de lembrete - 3 dias
        try:
            reminder_3_sent = email_service.send_trial_reminder_email(TEST_NAME, TEST_EMAIL, 3)
            if reminder_3_sent:
                print_result("Trial Reminder 3d", True, "Email de lembrete (3 dias) enviado!")
                results.append(True)
            else:
                print_result("Trial Reminder 3d", False, "Erro ao enviar lembrete 3 dias")
                results.append(False)
        except Exception as e:
            print_result("Trial Reminder 3d", False, f"Erro: {str(e)}")
            results.append(False)
        
        # 4. Teste email de lembrete - 1 dia
        try:
            reminder_1_sent = email_service.send_trial_reminder_email(TEST_NAME, TEST_EMAIL, 1)
            if reminder_1_sent:
                print_result("Trial Reminder 1d", True, "Email de lembrete (1 dia) enviado!")
                results.append(True)
            else:
                print_result("Trial Reminder 1d", False, "Erro ao enviar lembrete 1 dia")
                results.append(False)
        except Exception as e:
            print_result("Trial Reminder 1d", False, f"Erro: {str(e)}")
            results.append(False)
        
        # 5. Teste email de trial expirado
        try:
            expired_sent = email_service.send_trial_expired_email(TEST_NAME, TEST_EMAIL)
            if expired_sent:
                print_result("Trial Expired", True, "Email de trial expirado enviado!")
                results.append(True)
            else:
                print_result("Trial Expired", False, "Erro ao enviar email de trial expirado")
                results.append(False)
        except Exception as e:
            print_result("Trial Expired", False, f"Erro: {str(e)}")
            results.append(False)
        
        # Resultado geral
        success_count = sum(results)
        total_count = len(results)
        
        print(f"\n📊 Trial Emails: {success_count}/{total_count} sucessos")
        return success_count > 0
        
    except Exception as e:
        print_result("Trial Emails", False, f"Exceção geral: {str(e)}")
        return False

def test_payment_emails():
    """Teste de emails de payment"""
    print_header("TESTE DE EMAILS DE PAYMENT")
    
    results = []
    
    try:
        user_id = ensure_test_user()
        if not user_id:
            return False
        
        # 1. Teste email de pagamento confirmado
        try:
            success_sent = email_service.send_payment_success_email(TEST_NAME, TEST_EMAIL, "Premium", "R$ 99,90")
            if success_sent:
                print_result("Payment Success", True, "Email de pagamento confirmado enviado!")
                results.append(True)
            else:
                print_result("Payment Success", False, "Erro ao enviar email de pagamento confirmado")
                results.append(False)
        except Exception as e:
            print_result("Payment Success", False, f"Erro: {str(e)}")
            results.append(False)
        
        # 2. Teste email de lembrete de renovação - 7 dias
        try:
            reminder_7_sent = email_service.send_payment_reminder_email(TEST_NAME, TEST_EMAIL, "Premium", 7, "R$ 99,90")
            if reminder_7_sent:
                print_result("Payment Reminder 7d", True, "Email de lembrete renovação (7 dias) enviado!")
                results.append(True)
            else:
                print_result("Payment Reminder 7d", False, "Erro ao enviar lembrete renovação 7 dias")
                results.append(False)
        except Exception as e:
            print_result("Payment Reminder 7d", False, f"Erro: {str(e)}")
            results.append(False)
        
        # 3. Teste email de lembrete de renovação - 3 dias
        try:
            reminder_3_sent = email_service.send_payment_reminder_email(TEST_NAME, TEST_EMAIL, "Premium", 3, "R$ 99,90")
            if reminder_3_sent:
                print_result("Payment Reminder 3d", True, "Email de lembrete renovação (3 dias) enviado!")
                results.append(True)
            else:
                print_result("Payment Reminder 3d", False, "Erro ao enviar lembrete renovação 3 dias")
                results.append(False)
        except Exception as e:
            print_result("Payment Reminder 3d", False, f"Erro: {str(e)}")
            results.append(False)
        
        # 4. Teste email de lembrete de renovação - 1 dia
        try:
            reminder_1_sent = email_service.send_payment_reminder_email(TEST_NAME, TEST_EMAIL, "Premium", 1, "R$ 99,90")
            if reminder_1_sent:
                print_result("Payment Reminder 1d", True, "Email de lembrete renovação (1 dia) enviado!")
                results.append(True)
            else:
                print_result("Payment Reminder 1d", False, "Erro ao enviar lembrete renovação 1 dia")
                results.append(False)
        except Exception as e:
            print_result("Payment Reminder 1d", False, f"Erro: {str(e)}")
            results.append(False)
        
        # 5. Teste email de assinatura expirada
        try:
            expired_sent = email_service.send_payment_expired_email(TEST_NAME, TEST_EMAIL, "Premium")
            if expired_sent:
                print_result("Payment Expired", True, "Email de assinatura expirada enviado!")
                results.append(True)
            else:
                print_result("Payment Expired", False, "Erro ao enviar email de assinatura expirada")
                results.append(False)
        except Exception as e:
            print_result("Payment Expired", False, f"Erro: {str(e)}")
            results.append(False)
        
        # 6. Teste email de falha no pagamento
        try:
            failed_sent = email_service.send_payment_failed_email(TEST_NAME, TEST_EMAIL, "Premium", "2025-01-15")
            if failed_sent:
                print_result("Payment Failed", True, "Email de falha no pagamento enviado!")
                results.append(True)
            else:
                print_result("Payment Failed", False, "Erro ao enviar email de falha no pagamento")
                results.append(False)
        except Exception as e:
            print_result("Payment Failed", False, f"Erro: {str(e)}")
            results.append(False)
        
        # Resultado geral
        success_count = sum(results)
        total_count = len(results)
        
        print(f"\n📊 Payment Emails: {success_count}/{total_count} sucessos")
        return success_count > 0
        
    except Exception as e:
        print_result("Payment Emails", False, f"Exceção geral: {str(e)}")
        return False

def test_email_service_connection():
    """Teste básico de conexão com o serviço de email"""
    print_header("TESTE DE CONEXÃO COM SERVIÇO DE EMAIL")
    
    try:
        # Verificar se os métodos principais existem
        required_methods = [
            'send_confirmation_email',
            'send_password_reset_email',
            'send_trial_welcome_email',
            'send_trial_reminder_email',
            'send_trial_expired_email',
            'send_payment_success_email',
            'send_payment_reminder_email',
            'send_payment_expired_email',
            'send_payment_failed_email'
        ]
        
        missing_methods = []
        found_methods = []
        
        for method in required_methods:
            if hasattr(email_service, method):
                found_methods.append(method)
                print_result(f"Método {method}", True, "Encontrado")
            else:
                missing_methods.append(method)
                print_result(f"Método {method}", False, "Não encontrado")
        
        if missing_methods:
            print(f"\n❌ Métodos faltando: {', '.join(missing_methods)}")
            return False
        else:
            print(f"\n✅ Todos os {len(found_methods)} métodos encontrados!")
            return True
            
    except Exception as e:
        print_result("Conexão", False, f"Exceção: {str(e)}")
        return False

def run_all_tests():
    """Executa todos os testes"""
    print(f"\n🚀 INICIANDO TESTES DE EMAIL CORRIGIDOS")
    print(f"📧 Email de teste: {TEST_EMAIL}")
    print(f"👤 Nome de teste: {TEST_NAME}")
    print(f"🕐 Horário: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("Conexão Serviço Email", test_email_service_connection),
        ("Email Confirmação", test_confirmation_email),
        ("Email Reset Senha", test_password_reset_email),
        ("Emails Trial", test_trial_emails),
        ("Emails Payment", test_payment_emails)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print_result(test_name, False, f"Erro fatal: {str(e)}")
            results.append((test_name, False))
    
    # Resumo final
    print_header("RESUMO DOS TESTES")
    
    total_tests = len(results)
    passed_tests = sum(1 for _, success in results if success)
    failed_tests = total_tests - passed_tests
    
    for test_name, success in results:
        status = "✅ PASSOU" if success else "❌ FALHOU"
        print(f"{status} | {test_name}")
    
    print(f"\n📊 RESULTADOS FINAIS:")
    print(f"✅ Testes passou: {passed_tests}/{total_tests}")
    print(f"❌ Testes falhou: {failed_tests}/{total_tests}")
    print(f"📈 Taxa de sucesso: {(passed_tests/total_tests)*100:.1f}%")
    
    if failed_tests == 0:
        print(f"\n🎉 TODOS OS TESTES PASSARAM!")
        print(f"📧 Verifique o email {TEST_EMAIL} para ver os emails recebidos!")
    else:
        print(f"\n⚠️  {failed_tests} teste(s) falharam. Verifique os erros acima.")
    
    print(f"\n📝 DICA: Se alguns emails não chegaram, verifique:")
    print(f"   - Pasta de spam/lixo eletrônico")
    print(f"   - Configurações SMTP no email_service.py")
    print(f"   - Logs do servidor SMTP")

if __name__ == "__main__":
    try:
        run_all_tests()
    except KeyboardInterrupt:
        print(f"\n\n⏹️  Testes interrompidos pelo usuário")
    except Exception as e:
        print(f"\n\n💥 ERRO FATAL: {str(e)}")
        import traceback
        traceback.print_exc()
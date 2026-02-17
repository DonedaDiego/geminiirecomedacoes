# payment_scheduler.py - Scheduler Interno para Controle de Pagamentos
# =====================================================================

import threading
import time
import schedule
from datetime import datetime, timezone
from pag.control_pay_service import (
    process_expired_paid_subscriptions,
    send_renewal_warnings
)

class PaymentScheduler:
    def __init__(self):
        self.running = False
        self.scheduler_thread = None
        
    def start(self):
        """Iniciar o scheduler"""
        if self.running:
            
            return
        
        
        # Configurar jobs
        self.setup_jobs()
        
        # Iniciar thread
        self.running = True
        self.scheduler_thread = threading.Thread(target=self.run_scheduler, daemon=True)
        self.scheduler_thread.start()
        

    
    def setup_jobs(self):
        """Configurar os jobs do scheduler"""
        
        # Job 1: Processar assinaturas expiradas (2h da manhã)
        schedule.every().day.at("02:00").do(self.job_process_expired)
        
        # Job 2: Enviar avisos de renovação (10h da manhã)
        schedule.every().day.at("10:00").do(self.job_send_warnings)
        
        # Job 3: Processar trials expirados (3h da manhã)
        schedule.every().day.at("03:00").do(self.job_process_expired_trials)
        
        # Job 4: Verificação de integridade (toda segunda às 9h)
        schedule.every().monday.at("09:00").do(self.job_integrity_check)
    
    def run_scheduler(self):
        """Loop principal do scheduler"""
        print(" Scheduler thread iniciada")
        
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Verificar a cada minuto
                
            except Exception as e:
                print(f" Erro no scheduler: {e}")
                time.sleep(300)  # Se der erro, esperar 5 min
    
    def job_process_expired(self):
        """Job: Processar assinaturas expiradas"""
        try:
            print("\n" + "="*50)
            print(f" JOB INICIADO: Processar Expirados - {datetime.now()}")
            print("="*50)
            
            result = process_expired_paid_subscriptions()
            
            if result['success']:
                processed = result.get('processed_count', 0)
                print(f" Job concluído: {processed} assinaturas processadas")
                
                # Log detalhado se houver processamentos
                if processed > 0:
                    users = result.get('processed_users', [])
                    for user in users:
                        print(f"   - {user['name']} ({user['email']}) - {user['old_plan']} → Básico")
                
            else:
                print(f" Job falhou: {result['error']}")
            
        except Exception as e:
            print(f" Erro crítico no job process_expired: {e}")
    
    def job_process_expired_trials(self):
        """Job: Processar trials expirados"""
        try:
            print("\n" + "="*50)
            print(f" JOB INICIADO: Processar Trials Expirados - {datetime.now()}")
            print("="*50)
            
            from backend.pag.trial_service import process_expired_trials
            
            result = process_expired_trials()
            
            if result['success']:
                processed = result.get('processed_count', 0)
                emails_sent = result.get('emails_sent', 0)
                
                print(f" Job concluído:")
                print(f"   - Trials processados: {processed}")
                print(f"   - Emails enviados: {emails_sent}")
                
                # Log detalhado se houver processamentos
                if processed > 0:
                    users = result.get('processed_users', [])
                    for user in users:
                        print(f"   - {user['name']} ({user['email']}) - Trial → Básico")
                
            else:
                print(f" Job falhou: {result['error']}")
            
        except Exception as e:
            print(f" Erro crítico no job process_expired_trials: {e}")
    
    def job_send_warnings(self):
        """Job: Enviar avisos de renovação"""
        try:
            print("\n" + "="*50)
            print(f"📧 JOB INICIADO: Enviar Avisos - {datetime.now()}")
            print("="*50)
            
            result = send_renewal_warnings()
            
            if result['success']:
                emails_sent = result.get('emails_sent', 0)
                emails_failed = result.get('emails_failed', 0)
                total_expiring = result.get('total_expiring', 0)
                
                print(f" Job concluído:")
                print(f"   - Emails enviados: {emails_sent}")
                print(f"   - Emails falharam: {emails_failed}")
                print(f"   - Total expirando: {total_expiring}")
                
            else:
                print(f" Job falhou: {result['error']}")
            
        except Exception as e:
            print(f" Erro crítico no job send_warnings: {e}")
    
    def job_integrity_check(self):
        """Job: Verificação de integridade (semanal)"""
        try:
            print("\n" + "="*50)
            print(f" JOB INICIADO: Verificação de Integridade - {datetime.now()}")
            print("="*50)
            
            from pag.control_pay_service import verify_payments_integrity
            
            result = verify_payments_integrity()
            
            if result['success']:
                integrity = result['integrity_check']
                summary = integrity.get('summary', {})
                total_issues = summary.get('total_issues', 0)
                
                print(f" Verificação concluída:")
                print(f"   - Total de problemas: {total_issues}")
                print(f"   - Status do sistema: {summary.get('system_health', 'unknown')}")
                
                if total_issues > 0:
                    payment_issues = integrity.get('payment_issues', {})
                    trial_issues = integrity.get('trial_issues', {})
                    
                    print(f"   - Problemas de pagamento: {payment_issues.get('total', 0)}")
                    print(f"   - Problemas de trial: {trial_issues.get('total', 0)}")
                    
                    # Log usuários problemáticos (limitado a 5)
                    users_without_payments = payment_issues.get('users_without_payments', [])[:5]
                    for user in users_without_payments:
                        print(f"      {user['name']} ({user['email']}) - Plano: {user['plan']}")
                
            else:
                print(f" Verificação falhou: {result['error']}")
            
        except Exception as e:
            print(f" Erro crítico no job integrity_check: {e}")
    
    def stop(self):
        """Parar o scheduler"""
        if not self.running:
            print(" Scheduler já está parado")
            return
        
        print("🛑 Parando Payment Scheduler...")
        self.running = False
        
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        schedule.clear()
        print(" Payment Scheduler parado")
    
    def status(self):
        """Retornar status do scheduler"""
        return {
            'running': self.running,
            'jobs_count': len(schedule.get_jobs()),
            'next_jobs': [
                {
                    'job': str(job.job_func.__name__),
                    'next_run': job.next_run.isoformat() if job.next_run else None
                }
                for job in schedule.get_jobs()
            ] if self.running else []
        }
    
    def run_job_now(self, job_name):
        """Executar um job específico imediatamente (para testes)"""
        jobs = {
            'process_expired': self.job_process_expired,
            'send_warnings': self.job_send_warnings,
            'process_expired_trials': self.job_process_expired_trials,
            'integrity_check': self.job_integrity_check
        }
        
        if job_name not in jobs:
            return {
                'success': False, 
                'error': f'Job {job_name} não encontrado. Disponíveis: {list(jobs.keys())}'
            }
        
        try:
            print(f" EXECUÇÃO MANUAL: {job_name}")
            jobs[job_name]()
            return {'success': True, 'message': f'Job {job_name} executado com sucesso'}
            
        except Exception as e:
            return {'success': False, 'error': f'Erro ao executar {job_name}: {str(e)}'}

# ===== INSTÂNCIA GLOBAL DO SCHEDULER =====
payment_scheduler = PaymentScheduler()

# ===== FUNÇÕES DE CONTROLE =====

def start_payment_scheduler():
    """Iniciar o scheduler (chamado no main.py)"""
    payment_scheduler.start()

def stop_payment_scheduler():
    """Parar o scheduler"""
    payment_scheduler.stop()

def get_scheduler_status():
    """Obter status do scheduler"""
    return payment_scheduler.status()

def run_job_manually(job_name):
    """Executar um job específico imediatamente (para testes)"""
    return payment_scheduler.run_job_now(job_name)

# ===== TESTE MANUAL (apenas para desenvolvimento) =====
if __name__ == "__main__":
    print("🧪 TESTE DO PAYMENT SCHEDULER")
    print("="*40)
    
    try:
        # Testar inicialização
        start_payment_scheduler()
        
        # Mostrar status
        status = get_scheduler_status()
        print(f"\n Status: {status}")
        
        # Testar execução manual
        print("\n🧪 Testando execução manual...")
        result = run_job_manually('process_expired')
        print(f"Resultado: {result}")
        
        # Manter rodando por alguns segundos
        print("\n⏳ Aguardando 10 segundos...")
        time.sleep(10)
        
    except KeyboardInterrupt:
        print("\n🛑 Teste interrompido pelo usuário")
    except Exception as e:
        print(f"\n Erro no teste: {e}")
    finally:
        # Parar
        stop_payment_scheduler()
        print("\n Teste concluído!")
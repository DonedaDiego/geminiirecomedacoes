# scheduler_routes.py - Blueprint para Controle do Payment Scheduler
# ===================================================================

from flask import Blueprint, request, jsonify
import jwt
from datetime import datetime, timezone
from payment_scheduler import (
    start_payment_scheduler,
    stop_payment_scheduler,
    get_scheduler_status,
    run_job_manually
)

# ===== BLUEPRINT =====
scheduler_bp = Blueprint('scheduler', __name__, url_prefix='/api/scheduler')

# ===== VERIFICAÇÃO DE AUTENTICAÇÃO =====
def verify_admin_token(token):
    """Verificar se token é de admin"""
    try:
        from flask import current_app
        from database import get_db_connection
        
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload['user_id']
        
        conn = get_db_connection()
        if not conn:
            return None
            
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM users 
            WHERE id = %s AND user_type IN ('admin', 'master')
        """, (user_id,))
        
        admin = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return admin[0] if admin else None
        
    except Exception as e:
        return None

def require_admin(f):
    """Decorator para verificar se usuário é admin"""
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'error': 'Token não fornecido'}), 401
        
        token = auth_header.replace('Bearer ', '')
        admin_id = verify_admin_token(token)
        
        if not admin_id:
            return jsonify({'success': False, 'error': 'Acesso negado - Admin necessário'}), 403
        
        return f(admin_id, *args, **kwargs)
    
    wrapper.__name__ = f.__name__
    return wrapper

# ===== ROTAS DE CONTROLE DO SCHEDULER =====

@scheduler_bp.route('/status')
@require_admin
def get_status(admin_id):
    """Obter status do scheduler"""
    try:
        status = get_scheduler_status()
        
        return jsonify({
            'success': True,
            'data': {
                'scheduler_status': status,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'admin_id': admin_id
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@scheduler_bp.route('/start', methods=['POST'])
@require_admin
def start_scheduler(admin_id):
    """Iniciar scheduler"""
    try:
        start_payment_scheduler()
        
        return jsonify({
            'success': True,
            'message': 'Payment Scheduler iniciado com sucesso',
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@scheduler_bp.route('/stop', methods=['POST'])
@require_admin
def stop_scheduler(admin_id):
    """Parar scheduler"""
    try:
        stop_payment_scheduler()
        
        return jsonify({
            'success': True,
            'message': 'Payment Scheduler parado com sucesso',
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@scheduler_bp.route('/restart', methods=['POST'])
@require_admin
def restart_scheduler(admin_id):
    """Reiniciar scheduler"""
    try:
        stop_payment_scheduler()
        start_payment_scheduler()
        
        return jsonify({
            'success': True,
            'message': 'Payment Scheduler reiniciado com sucesso',
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== ROTAS DE EXECUÇÃO MANUAL =====

@scheduler_bp.route('/run-job', methods=['POST'])
@require_admin
def run_job(admin_id):
    """Executar job específico manualmente"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'Dados JSON necessários'}), 400
        
        job_name = data.get('job_name')
        
        if not job_name:
            return jsonify({'success': False, 'error': 'job_name é obrigatório'}), 400
        
        # Jobs disponíveis
        valid_jobs = ['process_expired', 'send_warnings', 'process_expired_trials', 'integrity_check']
        
        if job_name not in valid_jobs:
            return jsonify({
                'success': False, 
                'error': f'Job inválido. Disponíveis: {valid_jobs}'
            }), 400
        
        # Executar job
        result = run_job_manually(job_name)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message'],
                'job_name': job_name,
                'executed_by': admin_id,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error'],
                'job_name': job_name
            }), 500
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@scheduler_bp.route('/run-all-jobs', methods=['POST'])
@require_admin
def run_all_jobs(admin_id):
    """Executar todos os jobs manualmente"""
    try:
        jobs = ['process_expired', 'send_warnings', 'process_expired_trials', 'integrity_check']
        results = {}
        
        for job_name in jobs:
            try:
                result = run_job_manually(job_name)
                results[job_name] = {
                    'success': result['success'],
                    'message': result.get('message', result.get('error', 'Unknown'))
                }
            except Exception as e:
                results[job_name] = {
                    'success': False,
                    'message': str(e)
                }
        
        # Contar sucessos
        successful_jobs = sum(1 for r in results.values() if r['success'])
        total_jobs = len(jobs)
        
        return jsonify({
            'success': True,
            'message': f'{successful_jobs}/{total_jobs} jobs executados com sucesso',
            'results': results,
            'executed_by': admin_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== ROTAS DE INFORMAÇÃO =====

@scheduler_bp.route('/jobs')
@require_admin
def list_jobs(admin_id):
    """Listar jobs disponíveis"""
    try:
        jobs_info = {
            'process_expired': {
                'name': 'Processar Expirados',
                'description': 'Move usuários com assinatura expirada para plano Básico',
                'schedule': 'Todo dia às 02:00'
            },
            'send_warnings': {
                'name': 'Enviar Avisos',
                'description': 'Envia emails de aviso para assinaturas expirando',
                'schedule': 'Todo dia às 10:00'
            },
            'process_expired_trials': {
                'name': 'Processar Trials',
                'description': 'Move trials expirados para Básico e envia emails',
                'schedule': 'Todo dia às 03:00'
            },
            'integrity_check': {
                'name': 'Verificação de Integridade',
                'description': 'Verifica inconsistências nos dados',
                'schedule': 'Toda segunda às 09:00'
            }
        }
        
        return jsonify({
            'success': True,
            'data': {
                'jobs': jobs_info,
                'total_jobs': len(jobs_info)
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@scheduler_bp.route('/logs')
@require_admin
def get_logs(admin_id):
    """Obter logs do scheduler (placeholder - implementar conforme necessário)"""
    try:
        # TODO: Implementar sistema de logs se necessário
        return jsonify({
            'success': True,
            'message': 'Logs não implementados ainda',
            'data': {
                'logs': [],
                'note': 'Verifique os logs do console/Railway para informações detalhadas'
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== ROTAS DE SAÚDE =====

@scheduler_bp.route('/health')
def health_check():
    """Verificar se o sistema de scheduler está funcionando"""
    try:
        status = get_scheduler_status()
        
        return jsonify({
            'success': True,
            'message': 'Sistema de scheduler funcionando',
            'data': {
                'scheduler_running': status.get('running', False),
                'jobs_count': status.get('jobs_count', 0),
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'version': '1.0.0'
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== FUNÇÃO DE EXPORT =====
def get_scheduler_blueprint():
    """Retornar blueprint para registrar no Flask"""
    return scheduler_bp

# ===== AUTO-START DO SCHEDULER =====
def auto_start_scheduler():
    """Iniciar scheduler automaticamente quando o módulo for importado"""
    try:
        print("🚀 Auto-iniciando Payment Scheduler...")
        start_payment_scheduler()
        print("✅ Payment Scheduler iniciado automaticamente!")
    except Exception as e:
        print(f"❌ Erro ao auto-iniciar scheduler: {e}")

# Iniciar automaticamente quando importado
auto_start_scheduler()

if __name__ == "__main__":
    print("📅 Scheduler Routes - Sistema de controle do Payment Scheduler")
    print("🔗 Rotas disponíveis:")
    print("  - GET  /api/scheduler/status")
    print("  - POST /api/scheduler/start")
    print("  - POST /api/scheduler/stop") 
    print("  - POST /api/scheduler/restart")
    print("  - POST /api/scheduler/run-job")
    print("  - POST /api/scheduler/run-all-jobs")
    print("  - GET  /api/scheduler/jobs")
    print("  - GET  /api/scheduler/logs")
    print("  - GET  /api/scheduler/health")
# control_pay_routes.py - Rotas do Sistema de Controle de Pagamentos
# =========================================================================

from flask import Blueprint, request, jsonify
import jwt
from datetime import datetime, timezone, timedelta
from pag.control_pay_service import (
    check_user_subscription_status,
    get_all_expiring_subscriptions,
    process_expired_paid_subscriptions,
    send_renewal_warnings,
    get_subscription_stats,
    verify_payments_integrity
)

# ===== BLUEPRINT =====
control_pay_bp = Blueprint('control_pay', __name__, url_prefix='/api/subscriptions')

# ===== VERIFICAÇÃO DE AUTENTICAÇÃO =====
def verify_token(token):
    """Verificar e extrair dados do token JWT"""
    try:
        from flask import current_app
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload['user_id']
    except Exception as e:
        return None

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

def require_auth(f):
    """Decorator para verificar autenticação"""
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'error': 'Token não fornecido'}), 401
        
        token = auth_header.replace('Bearer ', '')
        user_id = verify_token(token)
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Token inválido'}), 401
        
        return f(user_id, *args, **kwargs)
    
    wrapper.__name__ = f.__name__
    return wrapper

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

# ===== ROTAS PÚBLICAS (USUÁRIO) =====

@control_pay_bp.route('/my-status')
@require_auth
def get_my_subscription_status(user_id):
    """Obter status da assinatura do usuário logado"""
    try:
        result = check_user_subscription_status(user_id)
        
        if not result['success']:
            return jsonify({'success': False, 'error': result['error']}), 400
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@control_pay_bp.route('/my-renewal-info')
@require_auth
def get_my_renewal_info(user_id):
    """Informações de renovação do usuário (para mostrar no dashboard)"""
    try:
        result = check_user_subscription_status(user_id)
        
        if not result['success']:
            return jsonify({'success': False, 'error': result['error']}), 400
        
        subscription = result['subscription']
        
        # Preparar dados específicos para renovação
        renewal_info = {
            'needs_renewal': subscription['is_expiring_soon'] or subscription['is_expired'],
            'days_remaining': subscription['days_remaining'],
            'expires_at': subscription['expires_at'],
            'current_plan': subscription['current_plan_name'],
            'status': subscription['status'],
            'urgency': subscription['renewal_urgency'],
            'show_banner': subscription['status'] in ['paid_active'] and subscription['is_expiring_soon'],
            'show_expired_modal': subscription['status'] == 'paid_expired'
        }
        
        return jsonify({
            'success': True,
            'data': renewal_info
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@control_pay_bp.route('/check-access/<feature>')
@require_auth
def check_feature_access(user_id, feature):
    """Verificar se usuário tem acesso a uma funcionalidade específica"""
    try:
        result = check_user_subscription_status(user_id)
        
        if not result['success']:
            return jsonify({'success': False, 'error': result['error']}), 400
        
        subscription = result['subscription']
        plan_id = subscription['current_plan_id']
        status = subscription['status']
        
        # Definir níveis de acesso
        feature_access = {
            'pro': [1, 2],      # Pro e Premium
            'premium': [2],     # Apenas Premium
            'basic': [1, 2, 3]  # Todos os planos
        }
        
        # Features específicas
        feature_plans = {
            'long_short': 'pro',
            'opcoes_advanced': 'pro', 
            'machine_learning': 'premium',
            'smart_carteiras': 'premium',
            'ai_recommendations': 'premium',
            'consultoria': 'premium'
        }
        
        required_level = feature_plans.get(feature, 'basic')
        allowed_plans = feature_access.get(required_level, [])
        
        # Verificar acesso
        has_access = False
        
        if status in ['paid_active', 'trial_active']:
            has_access = plan_id in allowed_plans
        elif status == 'basic':
            has_access = required_level == 'basic'
        
        return jsonify({
            'success': True,
            'data': {
                'has_access': has_access,
                'current_plan_id': plan_id,
                'required_level': required_level,
                'subscription_status': status,
                'feature': feature
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== ROTAS ADMINISTRATIVAS =====

@control_pay_bp.route('/admin/stats')
@require_admin
def get_admin_subscription_stats(admin_id):
    """Estatísticas das assinaturas para o painel admin"""
    try:
        result = get_subscription_stats()
        
        if not result['success']:
            return jsonify({'success': False, 'error': result['error']}), 400
        
        return jsonify({
            'success': True,
            'data': result['stats']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@control_pay_bp.route('/admin/expiring')
@require_admin
def get_admin_expiring_subscriptions(admin_id):
    """Listar assinaturas que vão expirar"""
    try:
        days_ahead = request.args.get('days', 7, type=int)
        
        result = get_all_expiring_subscriptions(days_ahead)
        
        if not result['success']:
            return jsonify({'success': False, 'error': result['error']}), 400
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@control_pay_bp.route('/admin/user/<int:target_user_id>/status')
@require_admin
def get_user_subscription_admin(admin_id, target_user_id):
    """Obter status da assinatura de um usuário específico (admin)"""
    try:
        result = check_user_subscription_status(target_user_id)
        
        if not result['success']:
            return jsonify({'success': False, 'error': result['error']}), 400
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@control_pay_bp.route('/admin/process-expired', methods=['POST'])
@require_admin
def process_expired_subscriptions_admin(admin_id):
    """Processar manualmente assinaturas expiradas"""
    try:
        result = process_expired_paid_subscriptions()
        
        if not result['success']:
            return jsonify({'success': False, 'error': result['error']}), 400
        
        return jsonify({
            'success': True,
            'message': result['message'],
            'data': {
                'processed_count': result['processed_count'],
                'processed_users': result.get('processed_users', [])
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@control_pay_bp.route('/admin/send-warnings', methods=['POST'])
@require_admin
def send_renewal_warnings_admin(admin_id):
    """Enviar avisos de renovação manualmente"""
    try:
        result = send_renewal_warnings()
        
        if not result['success']:
            return jsonify({'success': False, 'error': result['error']}), 400
        
        return jsonify({
            'success': True,
            'message': result['message'],
            'data': {
                'emails_sent': result['emails_sent'],
                'emails_failed': result['emails_failed'],
                'total_expiring': result['total_expiring']
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@control_pay_bp.route('/admin/integrity-check')
@require_admin
def check_payments_integrity_admin(admin_id):
    """Verificar integridade dos dados de pagamento"""
    try:
        result = verify_payments_integrity()
        
        if not result['success']:
            return jsonify({'success': False, 'error': result['error']}), 400
        
        return jsonify({
            'success': True,
            'data': result['integrity_check']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@control_pay_bp.route('/admin/user/<int:target_user_id>/extend', methods=['POST'])
@require_admin
def extend_user_subscription_admin(admin_id, target_user_id):
    """Estender assinatura de um usuário (admin)"""
    try:
        data = request.get_json()
        extra_days = data.get('extra_days', 30)
        
        if not isinstance(extra_days, int) or extra_days < 1 or extra_days > 365:
            return jsonify({'success': False, 'error': 'Dias extras deve ser entre 1 e 365'}), 400
        
        from database import get_db_connection
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão com banco'}), 500
        
        cursor = conn.cursor()
        
        # Buscar usuário
        cursor.execute("""
            SELECT plan_expires_at FROM users 
            WHERE id = %s AND plan_id IN (1, 2)
        """, (target_user_id,))
        
        user = cursor.fetchone()
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Usuário não encontrado ou não tem plano pago'}), 404
        
        current_expires = user[0]
        
        # Calcular nova data
        if current_expires and current_expires > datetime.now(timezone.utc):
            # Estender a partir da data atual de expiração
            new_expires = current_expires + timedelta(days=extra_days)
        else:
            # Estender a partir de agora
            new_expires = datetime.now(timezone.utc) + timedelta(days=extra_days)
        
        # Atualizar
        cursor.execute("""
            UPDATE users 
            SET plan_expires_at = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (new_expires, target_user_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Assinatura estendida por {extra_days} dias',
            'data': {
                'new_expires_at': new_expires.isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== ROTAS DE SCHEDULER INTERNO =====

@control_pay_bp.route('/scheduler/status')
@require_admin
def get_scheduler_status_admin(admin_id):
    """Obter status do scheduler interno"""
    try:
        from backend.pag.payment_scheduler import get_scheduler_status
        
        status = get_scheduler_status()
        
        return jsonify({
            'success': True,
            'data': status
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@control_pay_bp.route('/scheduler/start', methods=['POST'])
@require_admin
def start_scheduler_admin(admin_id):
    """Iniciar scheduler interno"""
    try:
        from backend.pag.payment_scheduler import start_payment_scheduler
        
        start_payment_scheduler()
        
        return jsonify({
            'success': True,
            'message': 'Scheduler iniciado com sucesso'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@control_pay_bp.route('/scheduler/stop', methods=['POST'])
@require_admin
def stop_scheduler_admin(admin_id):
    """Parar scheduler interno"""
    try:
        from backend.pag.payment_scheduler import stop_payment_scheduler
        
        stop_payment_scheduler()
        
        return jsonify({
            'success': True,
            'message': 'Scheduler parado com sucesso'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@control_pay_bp.route('/scheduler/run-job', methods=['POST'])
@require_admin
def run_job_manually_admin(admin_id):
    """Executar job específico manualmente"""
    try:
        data = request.get_json()
        job_name = data.get('job_name')
        
        if not job_name:
            return jsonify({'success': False, 'error': 'job_name é obrigatório'}), 400
        
        #  LISTA ATUALIZADA COM NOVO JOB
        valid_jobs = ['process_expired', 'send_warnings', 'process_expired_trials', 'integrity_check']
        if job_name not in valid_jobs:
            return jsonify({
                'success': False, 
                'error': f'Job inválido. Opções: {valid_jobs}'
            }), 400
        
        from backend.pag.payment_scheduler import run_job_manually
        
        result = run_job_manually(job_name)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message']
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== ROTAS DE WEBHOOK/CRON =====

@control_pay_bp.route('/cron/process-expired', methods=['POST'])
def cron_process_expired():
    """Endpoint para job automático processar expirados"""
    try:
        result = process_expired_paid_subscriptions()
        
        return jsonify({
            'success': result['success'],
            'message': result.get('message', ''),
            'processed_count': result.get('processed_count', 0)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@control_pay_bp.route('/cron/send-warnings', methods=['POST'])
def cron_send_warnings():
    """Endpoint para job automático enviar avisos"""
    try:
        result = send_renewal_warnings()
        
        return jsonify({
            'success': result['success'],
            'message': result.get('message', ''),
            'emails_sent': result.get('emails_sent', 0)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== ROTAS DE UTILIDADE =====

@control_pay_bp.route('/health')
def health_check():
    """Verificar se o sistema de controle de pagamentos está funcionando"""
    try:
        return jsonify({
            'success': True,
            'message': 'Sistema de controle de pagamentos funcionando',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'version': '1.0.0'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500




# ===== FUNÇÃO DE EXPORT =====
def get_control_pay_blueprint():
    """Retornar blueprint para registrar no Flask"""
    return control_pay_bp
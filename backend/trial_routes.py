# trial_routes.py - Blueprint de Rotas do Sistema de Trial
# =======================================================

from flask import Blueprint, request, jsonify
import jwt
from datetime import datetime, timezone
from control_pay_service import check_user_subscription_status
from trial_service import (
    extend_user_trial,
    get_all_trial_users,
    process_expired_trials,
    get_trial_stats,
    is_user_trial,
    get_trial_days_remaining,
    can_access_premium_features,
    can_access_pro_features
)

# ===== BLUEPRINT TRIAL =====
trial_bp = Blueprint('trial', __name__, url_prefix='/api/trial')

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

def require_auth():
    """Decorator para verificar autenticação"""
    def decorator(f):
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
    return decorator

def require_admin():
    """Decorator para verificar se usuário é admin"""
    def decorator(f):
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
    return decorator

# ===== ROTAS PÚBLICAS (USUÁRIO) =====

@trial_bp.route('/status')
@require_auth()
def get_trial_status(user_id):
    """Obter status do trial do usuário logado"""
    try:
        result = check_user_subscription_status(user_id)
        
        if not result.get('success', False):
            return jsonify({
                'success': False,
                'error': result.get('error', 'Erro desconhecido')
            }), 400
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@trial_bp.route('/days-remaining')
@require_auth()
def get_days_remaining(user_id):
    """Obter dias restantes do trial (rota rápida)"""
    try:
        days_remaining = get_trial_days_remaining(user_id)
        is_trial = is_user_trial(user_id)
        
        return jsonify({
            'success': True,
            'data': {
                'is_trial': is_trial,
                'days_remaining': days_remaining,
                'message': f'{days_remaining} dias restantes' if is_trial else 'Não está em trial'
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@trial_bp.route('/can-access-premium')
@require_auth()
def check_premium_access(user_id):
    """Verificar se pode acessar recursos Premium"""
    try:
        can_access = can_access_premium_features(user_id)
        
        return jsonify({
            'success': True,
            'data': {
                'can_access': can_access,
                'message': 'Acesso liberado' if can_access else 'Acesso negado'
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@trial_bp.route('/can-access-pro')
@require_auth()
def check_pro_access(user_id):
    """Verificar se pode acessar recursos Pro"""
    try:
        can_access = can_access_pro_features(user_id)
        
        return jsonify({
            'success': True,
            'data': {
                'can_access': can_access,
                'message': 'Acesso liberado' if can_access else 'Acesso negado'
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@trial_bp.route('/info')
@require_auth()
def get_trial_info(user_id):
    """Informações completas do trial para o dashboard"""
    try:
        status = check_user_subscription_status(user_id)
        
        if not status.get('valid', False):
            return jsonify({
                'success': False,
                'error': status.get('error', 'Erro desconhecido')
            }), 400
        
        # Dados para o dashboard
        dashboard_data = {
            'is_trial': status.get('subscription', {}).get('is_trial', False),
            'plan_id': status.get('subscription', {}).get('current_plan_id', 3),
            'plan_name': status.get('subscription', {}).get('current_plan_name', 'Básico'),
            'user_type': status.get('user_info', {}).get('user_type', 'regular'),
            'message': status.get('message', ''),
            'can_access_premium': can_access_premium_features(user_id),
            'can_access_pro': can_access_pro_features(user_id)
        }
        
        # Se é trial, adicionar informações de tempo
        if status.get('is_trial', False):
            dashboard_data.update({
                'days_remaining': status.get('days_remaining', 0),
                'hours_remaining': status.get('hours_remaining', 0),
                'expires_at': status.get('expires_at'),
                'urgency_level': 'high' if status.get('days_remaining', 0) <= 3 else 'medium' if status.get('days_remaining', 0) <= 7 else 'low'
            })
        
        return jsonify({
            'success': True,
            'data': dashboard_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== ROTAS ADMINISTRATIVAS =====

@trial_bp.route('/admin/stats')
@require_admin()
def get_admin_trial_stats(admin_id):
    """Estatísticas dos trials para o painel admin"""
    try:
        result = get_trial_stats()
        
        if not result.get('success', False):
            return jsonify({
                'success': False,
                'error': result.get('error', 'Erro desconhecido')
            }), 400
        
        return jsonify({
            'success': True,
            'data': result['stats']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@trial_bp.route('/admin/users')
@require_admin()
def get_admin_trial_users(admin_id):
    """Listar todos os usuários em trial"""
    try:
        result = get_all_trial_users()
        
        if not result.get('success', False):
            return jsonify({
                'success': False,
                'error': result.get('error', 'Erro desconhecido')
            }), 400
        
        return jsonify({
            'success': True,
            'data': {
                'trial_users': result['trial_users'],
                'total_count': result['total_count']
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@trial_bp.route('/admin/extend', methods=['POST'])
@require_admin()
def extend_trial_admin(admin_id):
    """Estender trial de um usuário"""
    try:
        data = request.get_json()
        
        target_user_id = data.get('user_id')
        extra_days = data.get('extra_days', 7)
        
        if not target_user_id:
            return jsonify({'success': False, 'error': 'ID do usuário é obrigatório'}), 400
        
        if not isinstance(extra_days, int) or extra_days < 1 or extra_days > 30:
            return jsonify({'success': False, 'error': 'Dias extras deve ser entre 1 e 30'}), 400
        
        result = extend_user_trial(target_user_id, extra_days)
        
        if not result.get('success', False):
            return jsonify({
                'success': False,
                'error': result.get('error', 'Erro desconhecido')
            }), 400
        
        return jsonify({
            'success': True,
            'message': result['message'],
            'data': {
                'new_expires_at': result.get('new_expires_at')
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@trial_bp.route('/admin/process-expired', methods=['POST'])
@require_admin()
def process_expired_trials_admin(admin_id):
    """Processar manualmente todos os trials expirados"""
    try:
        result = process_expired_trials()
        
        if not result.get('success', False):
            return jsonify({
                'success': False,
                'error': result.get('error', 'Erro desconhecido')
            }), 400
        
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

@trial_bp.route('/admin/user/<int:user_id>/status')
@require_admin()
def get_user_trial_status_admin(admin_id, user_id):
    """Obter status do trial de um usuário específico (admin)"""
    try:
        result = check_user_subscription_status(user_id)
        
        if not result.get('success', False):
            return jsonify({
                'success': False,
                'error': result.get('error', 'Erro desconhecido')
            }), 400
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@trial_bp.route('/admin/user/<int:user_id>/force-downgrade', methods=['POST'])
@require_admin()
def force_downgrade_user_admin(admin_id, user_id):
    """Forçar downgrade de um usuário em trial (admin)"""
    try:
        from trial_service import downgrade_user_trial
        
        result = downgrade_user_trial(user_id)
        
        if not result.get('success', False):
            return jsonify({
                'success': False,
                'error': result.get('error', 'Erro desconhecido')
            }), 400
        
        return jsonify({
            'success': True,
            'message': result['message']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== ROTAS DE VERIFICAÇÃO (MIDDLEWARE) =====

@trial_bp.route('/verify-premium-access', methods=['POST'])
@require_auth()
def verify_premium_access(user_id):
    """Verificar acesso a recursos Premium (usado como middleware)"""
    try:
        can_access = can_access_premium_features(user_id)
        
        if not can_access:
            return jsonify({
                'success': False,
                'error': 'Acesso negado - Plano Premium necessário',
                'required_plan': 'Premium',
                'upgrade_url': '/planos'
            }), 403
        
        return jsonify({
            'success': True,
            'message': 'Acesso liberado para recursos Premium'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@trial_bp.route('/verify-pro-access', methods=['POST'])
@require_auth()
def verify_pro_access(user_id):
    """Verificar acesso a recursos Pro (usado como middleware)"""
    try:
        can_access = can_access_pro_features(user_id)
        
        if not can_access:
            return jsonify({
                'success': False,
                'error': 'Acesso negado - Plano Pro necessário',
                'required_plan': 'Pro',
                'upgrade_url': '/planos'
            }), 403
        
        return jsonify({
            'success': True,
            'message': 'Acesso liberado para recursos Pro'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== ROTAS DE UTILIDADE =====

@trial_bp.route('/health')
def health_check():
    """Verificar se o sistema de trial está funcionando"""
    try:
        return jsonify({
            'success': True,
            'message': 'Sistema de trial funcionando',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'version': '1.0.0'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== FUNÇÃO DE EXPORT =====
def get_trial_blueprint():
    """Retornar blueprint para registrar no Flask"""
    return trial_bp
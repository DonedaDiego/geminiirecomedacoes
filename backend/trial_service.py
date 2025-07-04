# trial_service.py - Serviço de Gerenciamento de Trial Premium
# ==============================================================

from datetime import datetime, timezone, timedelta
from database import get_db_connection
import hashlib

# ===== CACHE SIMPLES PARA PERFORMANCE =====
trial_cache = {}
CACHE_DURATION = 3600  # 1 hora

def get_cache_key(user_id):
    """Gerar chave do cache para o usuário"""
    return f"trial_status_{user_id}"

def is_cache_valid(cache_entry):
    """Verificar se entrada do cache ainda é válida"""
    if not cache_entry:
        return False
    
    cache_time = cache_entry.get('cached_at')
    if not cache_time:
        return False
    
    return (datetime.now(timezone.utc) - cache_time).total_seconds() < CACHE_DURATION

def set_cache(user_id, trial_status):
    """Salvar status do trial no cache"""
    cache_key = get_cache_key(user_id)
    trial_cache[cache_key] = {
        'status': trial_status,
        'cached_at': datetime.now(timezone.utc)
    }

def get_cache(user_id):
    """Buscar status do trial no cache"""
    cache_key = get_cache_key(user_id)
    cache_entry = trial_cache.get(cache_key)
    
    if is_cache_valid(cache_entry):
        return cache_entry['status']
    
    # Cache expirado, remover
    if cache_key in trial_cache:
        del trial_cache[cache_key]
    
    return None

def clear_cache(user_id):
    """Limpar cache de um usuário específico"""
    cache_key = get_cache_key(user_id)
    if cache_key in trial_cache:
        del trial_cache[cache_key]

# ===== FUNÇÕES PRINCIPAIS DO TRIAL =====

def create_trial_user(name, email, password):
    """
    Criar usuário com trial Premium de 15 dias
    """
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        
        # Verificar se email já existe
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return {'success': False, 'error': 'Email já cadastrado'}
        
        # Hash da senha
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        # Datas
        now = datetime.now(timezone.utc)
        trial_expires = now + timedelta(days=15)
        
        # Inserir usuário com trial Premium
        cursor.execute("""
            INSERT INTO users (
                name, email, password, plan_id, plan_name, user_type,
                plan_expires_at, created_at, updated_at, registration_date,
                email_confirmed, email_confirmed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            name, email, password_hash, 
            2, 'Premium', 'trial',  # 🔥 TRIAL PREMIUM
            trial_expires, now, now, now,
            True, now
        ))
        
        user_id = cursor.fetchone()[0]
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'user_id': user_id,
            'message': 'Usuário criado com trial Premium de 15 dias',
            'trial_expires_at': trial_expires.isoformat()
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Erro ao criar usuário: {str(e)}'}

def check_user_trial_status(user_id):
    """
    Verificar status do trial do usuário
    """
    try:
        # Verificar cache primeiro
        cached_status = get_cache(user_id)
        if cached_status:
            return cached_status
        
        conn = get_db_connection()
        if not conn:
            return {'valid': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        
        # Buscar dados do usuário
        cursor.execute("""
            SELECT id, user_type, plan_id, plan_name, plan_expires_at, created_at
            FROM users 
            WHERE id = %s AND user_type != 'deleted'
        """, (user_id,))
        
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user:
            return {'valid': False, 'error': 'Usuário não encontrado'}
        
        user_id, user_type, plan_id, plan_name, plan_expires_at, created_at = user
        
        # Verificar se é trial
        if user_type != 'trial':
            status = {
                'valid': True,
                'is_trial': False,
                'plan_id': plan_id,
                'plan_name': plan_name,
                'user_type': user_type,
                'message': 'Usuário não está em trial'
            }
            set_cache(user_id, status)
            return status
        
        # Usuário está em trial - verificar se expirou
        now = datetime.now(timezone.utc)
        
        # Se não tem data de expiração, usar created_at + 15 dias
        if not plan_expires_at:
            if created_at:
                plan_expires_at = created_at.replace(tzinfo=timezone.utc) + timedelta(days=15)
            else:
                plan_expires_at = now + timedelta(days=15)
        else:
            # Garantir que tem timezone
            if plan_expires_at.tzinfo is None:
                plan_expires_at = plan_expires_at.replace(tzinfo=timezone.utc)
        
        # Verificar se trial expirou
        if now > plan_expires_at:
            # Trial expirado - fazer downgrade automático
            downgrade_result = downgrade_user_trial(user_id)
            
            if downgrade_result['success']:
                status = {
                    'valid': True,
                    'is_trial': False,
                    'trial_expired': True,
                    'plan_id': 3,
                    'plan_name': 'Básico',
                    'user_type': 'regular',
                    'message': 'Trial expirado - downgrade para Básico'
                }
            else:
                status = {
                    'valid': False,
                    'error': 'Erro ao fazer downgrade do trial'
                }
            
            set_cache(user_id, status)
            return status
        
        # Trial ainda válido
        days_remaining = (plan_expires_at - now).days
        hours_remaining = (plan_expires_at - now).seconds // 3600
        
        status = {
            'valid': True,
            'is_trial': True,
            'trial_expired': False,
            'plan_id': plan_id,
            'plan_name': plan_name,
            'user_type': user_type,
            'expires_at': plan_expires_at.isoformat(),
            'days_remaining': days_remaining,
            'hours_remaining': hours_remaining,
            'message': f'Trial válido - {days_remaining} dias restantes'
        }
        
        set_cache(user_id, status)
        return status
        
    except Exception as e:
        return {'valid': False, 'error': f'Erro ao verificar trial: {str(e)}'}

def downgrade_user_trial(user_id):
    """
    Fazer downgrade de usuário com trial expirado
    """
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        
        # Fazer downgrade para Básico
        cursor.execute("""
            UPDATE users 
            SET plan_id = 3, plan_name = 'Básico', user_type = 'regular',
                plan_expires_at = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND user_type = 'trial'
        """, (user_id,))
        
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return {'success': False, 'error': 'Usuário não encontrado ou não está em trial'}
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Limpar cache
        clear_cache(user_id)
        
        return {
            'success': True,
            'message': 'Usuário foi rebaixado para plano Básico'
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Erro ao fazer downgrade: {str(e)}'}

def extend_user_trial(user_id, extra_days=7):
    """
    Estender trial de um usuário (função admin)
    """
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        
        # Buscar usuário em trial
        cursor.execute("""
            SELECT plan_expires_at FROM users 
            WHERE id = %s AND user_type = 'trial'
        """, (user_id,))
        
        user = cursor.fetchone()
        if not user:
            cursor.close()
            conn.close()
            return {'success': False, 'error': 'Usuário não encontrado ou não está em trial'}
        
        current_expires = user[0]
        
        # Calcular nova data de expiração
        if current_expires:
            if current_expires.tzinfo is None:
                current_expires = current_expires.replace(tzinfo=timezone.utc)
            new_expires = current_expires + timedelta(days=extra_days)
        else:
            new_expires = datetime.now(timezone.utc) + timedelta(days=extra_days)
        
        # Atualizar data de expiração
        cursor.execute("""
            UPDATE users 
            SET plan_expires_at = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (new_expires, user_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Limpar cache
        clear_cache(user_id)
        
        return {
            'success': True,
            'message': f'Trial estendido por {extra_days} dias',
            'new_expires_at': new_expires.isoformat()
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Erro ao estender trial: {str(e)}'}

def get_all_trial_users():
    """
    Buscar todos os usuários em trial (função admin)
    """
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, email, plan_id, plan_name, plan_expires_at, created_at,
                   EXTRACT(days FROM (plan_expires_at - NOW())) as days_remaining
            FROM users 
            WHERE user_type = 'trial'
            ORDER BY plan_expires_at ASC
        """)
        
        trial_users = []
        for row in cursor.fetchall():
            user_id, name, email, plan_id, plan_name, expires_at, created_at, days_remaining = row
            
            # Calcular status
            if days_remaining is not None:
                days_remaining = int(days_remaining)
                if days_remaining < 0:
                    status = 'expired'
                    status_text = 'Expirado'
                elif days_remaining <= 3:
                    status = 'ending_soon'
                    status_text = f'{days_remaining} dias restantes'
                else:
                    status = 'active'
                    status_text = f'{days_remaining} dias restantes'
            else:
                status = 'no_expiry'
                status_text = 'Sem data de expiração'
            
            trial_users.append({
                'id': user_id,
                'name': name,
                'email': email,
                'plan_id': plan_id,
                'plan_name': plan_name,
                'expires_at': expires_at.isoformat() if expires_at else None,
                'created_at': created_at.isoformat() if created_at else None,
                'days_remaining': days_remaining,
                'status': status,
                'status_text': status_text,
                'formatted_expires': expires_at.strftime('%d/%m/%Y') if expires_at else 'N/A'
            })
        
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'trial_users': trial_users,
            'total_count': len(trial_users)
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Erro ao buscar usuários em trial: {str(e)}'}

def process_expired_trials():
    """
    Processar todos os trials expirados (job automático)
    """
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        
        # Buscar trials expirados
        cursor.execute("""
            SELECT id, name, email 
            FROM users 
            WHERE user_type = 'trial' 
            AND plan_expires_at IS NOT NULL 
            AND plan_expires_at < NOW()
        """)
        
        expired_users = cursor.fetchall()
        
        if not expired_users:
            cursor.close()
            conn.close()
            return {
                'success': True,
                'message': 'Nenhum trial expirado encontrado',
                'processed_count': 0
            }
        
        # Fazer downgrade de todos os expirados
        cursor.execute("""
            UPDATE users 
            SET plan_id = 3, plan_name = 'Básico', user_type = 'regular',
                plan_expires_at = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE user_type = 'trial' 
            AND plan_expires_at IS NOT NULL 
            AND plan_expires_at < NOW()
        """)
        
        processed_count = cursor.rowcount
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Limpar cache de todos os usuários processados
        for user_id, name, email in expired_users:
            clear_cache(user_id)
        
        return {
            'success': True,
            'message': f'{processed_count} trials expirados processados',
            'processed_count': processed_count,
            'processed_users': [{'id': u[0], 'name': u[1], 'email': u[2]} for u in expired_users]
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Erro ao processar trials expirados: {str(e)}'}

def get_trial_stats():
    """
    Estatísticas dos trials (para dashboard admin)
    """
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        
        # Total de usuários em trial
        cursor.execute("SELECT COUNT(*) FROM users WHERE user_type = 'trial'")
        total_trials = cursor.fetchone()[0]
        
        # Trials expirando em 3 dias
        cursor.execute("""
            SELECT COUNT(*) FROM users 
            WHERE user_type = 'trial' 
            AND plan_expires_at IS NOT NULL 
            AND plan_expires_at BETWEEN NOW() AND NOW() + INTERVAL '3 days'
        """)
        expiring_soon = cursor.fetchone()[0]
        
        # Trials expirados (ainda não processados)
        cursor.execute("""
            SELECT COUNT(*) FROM users 
            WHERE user_type = 'trial' 
            AND plan_expires_at IS NOT NULL 
            AND plan_expires_at < NOW()
        """)
        expired = cursor.fetchone()[0]
        
        # Usuários que já foram de trial para pagante
        cursor.execute("""
            SELECT COUNT(*) FROM users 
            WHERE user_type IN ('pro', 'premium') 
            AND registration_date >= NOW() - INTERVAL '30 days'
        """)
        converted_this_month = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'stats': {
                'total_trials': total_trials,
                'expiring_soon': expiring_soon,
                'expired': expired,
                'converted_this_month': converted_this_month
            }
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Erro ao buscar estatísticas: {str(e)}'}

# ===== FUNÇÕES AUXILIARES =====

def is_user_trial(user_id):
    """
    Verificar rapidamente se usuário está em trial
    """
    status = check_user_trial_status(user_id)
    return status.get('is_trial', False)

def get_trial_days_remaining(user_id):
    """
    Obter dias restantes do trial
    """
    status = check_user_trial_status(user_id)
    return status.get('days_remaining', 0)

def can_access_premium_features(user_id):
    """
    Verificar se usuário pode acessar recursos Premium
    """
    status = check_user_trial_status(user_id)
    if not status.get('valid', False):
        return False
    
    # Trial válido OU plano Premium/Pro
    return (status.get('is_trial', False) and not status.get('trial_expired', False)) or \
           status.get('plan_id', 3) in [1, 2]

def can_access_pro_features(user_id):
    """
    Verificar se usuário pode acessar recursos Pro
    """
    status = check_user_trial_status(user_id)
    if not status.get('valid', False):
        return False
    
    # Trial válido OU plano Premium/Pro
    return (status.get('is_trial', False) and not status.get('trial_expired', False)) or \
           status.get('plan_id', 3) in [1, 2]
# trial_service.py - Serviço de Gerenciamento de Trial Premium
# ==============================================================

from datetime import datetime, timezone, timedelta
from database import get_db_connection
import hashlib
from email_service import email_service
from control_pay_service import check_email_rate_limit, increment_email_counter

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

def create_trial_user(name, email, password, ip_address=None):

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
                email_confirmed, email_confirmed_at, ip_address
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            name, email, password_hash, 
            2, 'Premium', 'trial',  # 🔥 TRIAL PREMIUM
            trial_expires, now, now, now,
            True, now, ip_address
        ))
        
        user_id = cursor.fetchone()[0]
        
        conn.commit()
        cursor.close()
        conn.close()
        try:
            from email_service import email_service
            email_service.send_trial_welcome_email(name, email)
            print(f"📧 Email de boas-vindas enviado para: {email}")
        except Exception as e:
            print(f"❌ Erro ao enviar boas-vindas: {e}")
                
        return {
            'success': True,
            'user_id': user_id,
            'message': 'Usuário criado com trial Premium de 15 dias',
            'trial_expires_at': trial_expires.isoformat()
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Erro ao criar usuário: {str(e)}'}


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

    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        
        # 🔥 PRIMEIRO: Buscar trials expirados
        cursor.execute("""
            SELECT id, name, email 
            FROM users 
            WHERE user_type = 'trial' 
            AND plan_expires_at IS NOT NULL 
            AND plan_expires_at < NOW()
        """)
        
        expired_users = cursor.fetchall()
        
        # 🔥 SEGUNDO: Fazer downgrade dos expirados
        if expired_users:
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
        else:
            processed_count = 0
        
        cursor.close()
        conn.close()
        
        # 🔥 TERCEIRO: Enviar avisos para os que ainda estão ativos
        print("📧 Enviando avisos de trial expirando...")
        warnings_result = send_trial_expiring_warnings()
        if warnings_result['success']:
            print(f"   ✅ {warnings_result['emails_sent']} emails enviados")
        else:
            print(f"   ❌ Erro nos avisos: {warnings_result['error']}")
        
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
    from control_pay_service import check_user_subscription_status
    status = check_user_subscription_status(user_id)
    return status.get('subscription', {}).get('is_trial', False)

def get_trial_days_remaining(user_id):
    """
    Obter dias restantes do trial
    """
    from control_pay_service import check_user_subscription_status
    status = check_user_subscription_status(user_id)
    subscription = status.get('subscription', {})
    
    # Só retorna dias se for trial ativo
    if subscription.get('is_trial', False) and subscription.get('status') == 'trial_active':
        return subscription.get('days_remaining', 0)
    return 0

def can_access_premium_features(user_id):
    """
    Verificar se usuário pode acessar recursos Premium
    """
    from control_pay_service import check_user_subscription_status
    status = check_user_subscription_status(user_id)
    return status.get('access_permissions', {}).get('can_access_premium', False)

def can_access_pro_features(user_id):
    """
    Verificar se usuário pode acessar recursos Pro
    """
    from control_pay_service import check_user_subscription_status
    status = check_user_subscription_status(user_id)
    return status.get('access_permissions', {}).get('can_access_pro', False)

def send_trial_expiring_email(user_info, days_remaining):
    try:
        from email_service import email_service
        
        user_email = user_info['email']
        
        if not check_email_rate_limit(user_email, 'trial'):
            print(f"🚫 BLOQUEADO: {user_email} excedeu limite de emails de trial hoje")
            return False
        
        user_name = user_info['name']
        
        # 🔥 USAR APENAS O NOVO MÉTODO - SEM HTML
        success = email_service.send_trial_reminder_email(
            user_name=user_name,
            email=user_email,
            days_remaining=days_remaining
        )
        
        if success:
            increment_email_counter(user_email, 'trial')
            print(f"✅ Email enviado: {user_email} ({days_remaining} dias)")
            return True
        else:
            print(f"❌ Falha no envio: {user_email}")
            return False
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def send_trial_expiring_warnings():

    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        
        # Buscar trials que vão expirar em 7, 3 ou 1 dias
        cursor.execute("""
            SELECT id, name, email, plan_name, plan_expires_at,
                   EXTRACT(days FROM (plan_expires_at - NOW())) as days_remaining
            FROM users 
            WHERE user_type = 'trial' 
            AND plan_expires_at IS NOT NULL 
            AND plan_expires_at BETWEEN NOW() AND NOW() + INTERVAL '7 days'
            ORDER BY plan_expires_at ASC
        """)
        
        expiring_trials = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not expiring_trials:
            return {
                'success': True,
                'message': 'Nenhum trial expirando encontrado',
                'emails_sent': 0
            }
        
        sent_count = 0
        failed_count = 0
        
        for trial_data in expiring_trials:
            user_id, name, email, plan_name, expires_at, days_remaining = trial_data
            days_remaining = int(days_remaining) if days_remaining else 0
            
            # Enviar emails apenas em dias específicos: 7, 3, 1
            if days_remaining in [7, 3, 1]:
                user_info = {
                    'name': name,
                    'email': email,
                    'plan_name': plan_name,
                    'expires_at': expires_at.strftime('%d/%m/%Y') if expires_at else 'N/A'
                }
                
                if send_trial_expiring_email(user_info, days_remaining):
                    sent_count += 1
                else:
                    failed_count += 1
        
        return {
            'success': True,
            'message': f'Avisos de trial processados',
            'emails_sent': sent_count,
            'emails_failed': failed_count,
            'total_expiring': len(expiring_trials)
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Erro interno: {str(e)}'}


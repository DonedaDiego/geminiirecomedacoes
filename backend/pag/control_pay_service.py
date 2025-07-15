# control_pay_service.py - Controle de Pagamentos e Assinaturas
# ================================================================

from datetime import datetime, timezone, timedelta
from database import get_db_connection
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# ===== CONFIGURAÇÕES =====
SMTP_SERVER = "smtp.titan.email"
SMTP_PORT = 465
SMTP_USER = os.environ.get('EMAIL_USER', 'contato@geminii.com.br')
SMTP_PASSWORD = os.environ.get('EMAIL_PASSWORD', '#Geminii20')

# ===== CONTROLE DE RATE LIMITING =====
email_rate_limit_cache = {}
MAX_EMAILS_PER_USER_PER_DAY = 10
RATE_LIMIT_CACHE_HOURS = 24

def check_email_rate_limit(user_email, email_type='renewal'):
    try:
        now = datetime.now(timezone.utc)
        cache_key = f"{user_email}_{email_type}_{now.strftime('%Y-%m-%d')}"
        
        # Limpar cache antigo (mais de 24h)
        keys_to_remove = []
        for key, data in email_rate_limit_cache.items():
            if (now - data['timestamp']).total_seconds() > (RATE_LIMIT_CACHE_HOURS * 3600):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del email_rate_limit_cache[key]
        
        # Verificar limite atual
        if cache_key in email_rate_limit_cache:
            current_count = email_rate_limit_cache[cache_key]['count']
            if current_count >= MAX_EMAILS_PER_USER_PER_DAY:
                print(f"⚠️ RATE LIMIT: {user_email} já recebeu {current_count} emails hoje")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no rate limit: {e}")
        return True  # Em caso de erro, permitir envio

def increment_email_counter(user_email, email_type='renewal'):
    """
    Incrementar contador de emails enviados
    """
    try:
        now = datetime.now(timezone.utc)
        cache_key = f"{user_email}_{email_type}_{now.strftime('%Y-%m-%d')}"
        
        if cache_key in email_rate_limit_cache:
            email_rate_limit_cache[cache_key]['count'] += 1
        else:
            email_rate_limit_cache[cache_key] = {
                'count': 1,
                'timestamp': now
            }
        
        print(f"📧 Email counter: {user_email} = {email_rate_limit_cache[cache_key]['count']}")
        
    except Exception as e:
        print(f"❌ Erro ao incrementar contador: {e}")

def get_email_stats():
    """
    Obter estatísticas de emails enviados (para debugging)
    """
    try:
        now = datetime.now(timezone.utc)
        today = now.strftime('%Y-%m-%d')
        
        stats = {
            'total_today': 0,
            'users_today': 0,
            'rate_limited': 0,
            'by_type': {}
        }
        
        for key, data in email_rate_limit_cache.items():
            if today in key:
                stats['total_today'] += data['count']
                stats['users_today'] += 1
                
                if data['count'] >= MAX_EMAILS_PER_USER_PER_DAY:
                    stats['rate_limited'] += 1
                
                # Extrair tipo de email
                parts = key.split('_')
                if len(parts) >= 2:
                    email_type = parts[-2]  # renewal, trial, etc
                    if email_type not in stats['by_type']:
                        stats['by_type'][email_type] = 0
                    stats['by_type'][email_type] += data['count']
        
        return stats
        
    except Exception as e:
        print(f"❌ Erro nas estatísticas: {e}")
        return {}


# ===== FUNÇÕES PRINCIPAIS =====

def check_user_subscription_status(user_id):
    """
    Verificar status da assinatura de um usuário específico
    VERSÃO UNIFICADA - Funciona para trials e pagamentos
    """
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        
        # Buscar dados do usuário
        cursor.execute("""
            SELECT id, name, email, plan_id, plan_name, plan_expires_at, 
                   user_type, created_at, updated_at
            FROM users 
            WHERE id = %s
        """, (user_id,))
        
        user_data = cursor.fetchone()
        if not user_data:
            cursor.close()
            conn.close()
            return {'success': False, 'error': 'Usuário não encontrado'}
        
        user_id, name, email, plan_id, plan_name, plan_expires_at, user_type, created_at, updated_at = user_data
        
        # Buscar último pagamento do usuário
        cursor.execute("""
            SELECT payment_id, status, amount, plan_name as paid_plan, 
                   cycle, created_at, external_reference
            FROM payments 
            WHERE user_id = %s 
            ORDER BY created_at DESC 
            LIMIT 1
        """, (user_id,))
        
        last_payment = cursor.fetchone()
        
        # Buscar histórico de pagamentos
        cursor.execute("""
            SELECT COUNT(*) as total_payments, 
                   SUM(amount) as total_spent
            FROM payments 
            WHERE user_id = %s AND status = 'approved'
        """, (user_id,))
        
        payment_stats = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        # 🔥 LÓGICA UNIFICADA - COMPATÍVEL COM CÓDIGO EXISTENTE
        now = datetime.now(timezone.utc)
        subscription_status = 'inactive'
        days_remaining = 0
        is_expired = False
        is_expiring_soon = False
        
        # Verificar se tem data de expiração
        if plan_expires_at:
            if plan_expires_at.tzinfo is None:
                plan_expires_at = plan_expires_at.replace(tzinfo=timezone.utc)
            
            days_remaining = (plan_expires_at - now).days
            
            if now >= plan_expires_at:
                is_expired = True
            
            # 🔥 LÓGICA UNIFICADA: Trial e Pagamento
            if user_type == 'trial':
                # Usuário em trial
                if now < plan_expires_at:
                    subscription_status = 'trial_active'
                    is_expiring_soon = days_remaining <= 3
                else:
                    subscription_status = 'trial_expired'
            
            elif plan_id in [1, 2]:
                # Usuário com plano pago
                if now < plan_expires_at:
                    subscription_status = 'paid_active'
                    is_expiring_soon = days_remaining <= 5
                else:
                    subscription_status = 'paid_expired'
            
            else:
                subscription_status = 'basic'
        
        else:
            # Sem data de expiração
            if plan_id in [1, 2]:
                print(f"⚠️ INCONSISTÊNCIA: Usuário {user_id} tem plano pago sem data de expiração")
                subscription_status = 'data_inconsistency'
            else:
                subscription_status = 'basic'
        
        # Detectar possíveis ex-trials
        was_trial_user = False
        if user_type == 'regular' and plan_id in [1, 2] and created_at:
            days_since_creation = (now - created_at.replace(tzinfo=timezone.utc)).days
            if days_since_creation <= 30:
                was_trial_user = True
        
        # Preparar resposta (mantendo compatibilidade)
        result = {
            'success': True,
            'user_info': {
                'id': user_id,
                'name': name,
                'email': email,
                'user_type': user_type,
                'created_at': created_at.isoformat() if created_at else None,
                'was_trial_user': was_trial_user
            },
            'subscription': {
                'status': subscription_status,
                'current_plan_id': plan_id,
                'current_plan_name': plan_name,
                'expires_at': plan_expires_at.isoformat() if plan_expires_at else None,
                'days_remaining': days_remaining,
                'is_expired': is_expired,
                'is_expiring_soon': is_expiring_soon,
                'renewal_urgency': 'high' if days_remaining <= 1 else 'medium' if days_remaining <= 3 else 'low',
                # 🔥 NOVOS CAMPOS ÚTEIS
                'is_trial': user_type == 'trial',
                'is_paid': plan_id in [1, 2] and user_type != 'trial'
            },
            'payment_info': {
                'has_payments': last_payment is not None,
                'last_payment': {
                    'payment_id': last_payment[0] if last_payment else None,
                    'status': last_payment[1] if last_payment else None,
                    'amount': float(last_payment[2]) if last_payment and last_payment[2] else 0,
                    'plan_name': last_payment[3] if last_payment else None,
                    'cycle': last_payment[4] if last_payment else None,
                    'date': last_payment[5].isoformat() if last_payment and last_payment[5] else None
                } if last_payment else None,
                'stats': {
                    'total_payments': payment_stats[0] if payment_stats else 0,
                    'total_spent': float(payment_stats[1]) if payment_stats and payment_stats[1] else 0
                }
            },
            # 🔥 NOVO: Permissões de acesso
            'access_permissions': {
                'can_access_pro': subscription_status in ['trial_active', 'paid_active'],
                'can_access_premium': subscription_status in ['trial_active', 'paid_active'] and plan_id == 2,
                'needs_upgrade': subscription_status in ['basic', 'trial_expired', 'paid_expired']
            }
        }
        
        return result
        
    except Exception as e:
        return {'success': False, 'error': f'Erro interno: {str(e)}'}

def get_all_expiring_subscriptions(days_ahead=7):
    """
    Buscar todas as assinaturas que vão expirar nos próximos X dias
    """
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        
        # Data limite para busca
        limit_date = datetime.now(timezone.utc) + timedelta(days=days_ahead)
        
        # Buscar usuários com planos pagos expirando
        cursor.execute("""
            SELECT u.id, u.name, u.email, u.plan_id, u.plan_name, 
                   u.plan_expires_at, u.user_type,
                   EXTRACT(days FROM (u.plan_expires_at - NOW())) as days_remaining,
                   p.payment_id, p.amount, p.cycle
            FROM users u
            LEFT JOIN payments p ON u.id = p.user_id
            WHERE u.plan_expires_at IS NOT NULL 
            AND u.plan_expires_at BETWEEN NOW() AND %s
            AND u.user_type != 'trial'
            AND u.plan_id IN (1, 2)
            ORDER BY u.plan_expires_at ASC
        """, (limit_date,))
        
        expiring_users = []
        
        for row in cursor.fetchall():
            user_id, name, email, plan_id, plan_name, expires_at, user_type, days_remaining, payment_id, amount, cycle = row
            
            # Calcular urgência
            days_remaining = int(days_remaining) if days_remaining else 0
            
            if days_remaining <= 1:
                urgency = 'critical'
                urgency_text = 'URGENTE - Expira hoje/amanhã'
            elif days_remaining <= 3:
                urgency = 'high'
                urgency_text = 'Alta - Expira em breve'
            elif days_remaining <= 5:
                urgency = 'medium'
                urgency_text = 'Média - Avisar usuário'
            else:
                urgency = 'low'
                urgency_text = 'Baixa - Monitorar'
            
            expiring_users.append({
                'user_id': user_id,
                'name': name,
                'email': email,
                'plan_id': plan_id,
                'plan_name': plan_name,
                'expires_at': expires_at.isoformat() if expires_at else None,
                'days_remaining': days_remaining,
                'urgency': urgency,
                'urgency_text': urgency_text,
                'last_payment': {
                    'payment_id': payment_id,
                    'amount': float(amount) if amount else 0,
                    'cycle': cycle
                } if payment_id else None
            })
        
        cursor.close()
        conn.close()
        
        # Agrupar por urgência
        grouped = {
            'critical': [u for u in expiring_users if u['urgency'] == 'critical'],
            'high': [u for u in expiring_users if u['urgency'] == 'high'],
            'medium': [u for u in expiring_users if u['urgency'] == 'medium'],
            'low': [u for u in expiring_users if u['urgency'] == 'low']
        }
        
        return {
            'success': True,
            'expiring_users': expiring_users,
            'grouped_by_urgency': grouped,
            'total_count': len(expiring_users),
            'summary': {
                'critical': len(grouped['critical']),
                'high': len(grouped['high']),
                'medium': len(grouped['medium']),
                'low': len(grouped['low'])
            }
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Erro interno: {str(e)}'}

def process_expired_paid_subscriptions():
    """
    Processar assinaturas pagas expiradas - fazer downgrade para Básico
    """
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        
        # Buscar usuários com planos pagos expirados
        cursor.execute("""
            SELECT id, name, email, plan_id, plan_name, plan_expires_at
            FROM users 
            WHERE plan_expires_at IS NOT NULL 
            AND plan_expires_at < NOW()
            AND user_type != 'trial'
            AND plan_id IN (1, 2)
        """, ())
        
        expired_users = cursor.fetchall()
        
        if not expired_users:
            cursor.close()
            conn.close()
            return {
                'success': True,
                'message': 'Nenhuma assinatura paga expirada encontrada',
                'processed_count': 0
            }
        
        processed_users = []
        
        for user_data in expired_users:
            user_id, name, email, old_plan_id, old_plan_name, expires_at = user_data
            
            try:
                # Fazer downgrade para Básico
                cursor.execute("""
                    UPDATE users 
                    SET plan_id = 3, 
                        plan_name = 'Básico',
                        plan_expires_at = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (user_id,))
                
                # Registrar o downgrade
                processed_users.append({
                    'user_id': user_id,
                    'name': name,
                    'email': email,
                    'old_plan': old_plan_name,
                    'expired_at': expires_at.isoformat() if expires_at else None
                })
                
                print(f"✅ Downgrade realizado: {name} ({email}) - {old_plan_name} → Básico")
                
            except Exception as e:
                print(f"❌ Erro no downgrade do usuário {user_id}: {e}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'message': f'{len(processed_users)} assinaturas expiradas processadas',
            'processed_count': len(processed_users),
            'processed_users': processed_users
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Erro interno: {str(e)}'}

def send_renewal_warning_email(user_info, days_remaining):
    """📧 Enviar email de renovação COM TEMPLATE ANTI-SPAM"""
    try:
        from emails.email_service import email_service
        
        user_email = user_info['email']
        
        if not check_email_rate_limit(user_email, 'renewal'):
            print(f"🚫 BLOQUEADO: {user_email} excedeu limite de emails de renewal hoje")
            return False
        
        user_name = user_info['name']
        plan_name = user_info['plan_name']
        expires_at = user_info['expires_at']
        
        # 🔥 USAR APENAS O NOVO MÉTODO ANTI-SPAM - SEM HTML ANTIGO
        success = email_service.send_payment_reminder_email(
            user_name=user_name,
            email=user_email,
            plan_name=plan_name,
            days_until_renewal=days_remaining
        )
        
        if success:
            increment_email_counter(user_email, 'renewal')
            print(f"✅ Email de renovação enviado para: {user_email} ({days_remaining} dias)")
            return True
        else:
            print(f"❌ Falha no envio para: {user_email}")
            return False
        
    except Exception as e:
        print(f"❌ Erro ao enviar email para {user_email}: {e}")
        return False

def send_renewal_warnings():
    """
    Enviar avisos de renovação para usuários que estão próximos da expiração
    """
    try:
        result = get_all_expiring_subscriptions(days_ahead=5)
        
        if not result['success']:
            return result
        
        expiring_users = result['expiring_users']
        sent_count = 0
        failed_count = 0
        
        for user in expiring_users:
            days_remaining = user['days_remaining']
            
            # Enviar emails apenas em dias específicos: 5, 3, 1
            if days_remaining in [5, 3, 1]:
                user_info = {
                    'name': user['name'],
                    'email': user['email'],
                    'plan_name': user['plan_name'],
                    'expires_at': user['expires_at']
                }
                
                if send_renewal_warning_email(user_info, days_remaining):
                    sent_count += 1
                else:
                    failed_count += 1
        
        return {
            'success': True,
            'message': f'Avisos de renovação processados',
            'emails_sent': sent_count,
            'emails_failed': failed_count,
            'total_expiring': len(expiring_users)
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Erro interno: {str(e)}'}

def get_subscription_stats():
    """
    Estatísticas gerais das assinaturas para o dashboard admin
    """
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        
        # Total de usuários por plano
        cursor.execute("""
            SELECT plan_id, plan_name, COUNT(*) as count
            FROM users 
            WHERE plan_id IS NOT NULL
            GROUP BY plan_id, plan_name
            ORDER BY plan_id
        """)
        users_by_plan = cursor.fetchall()
        
        # Assinaturas expirando em 7 dias
        cursor.execute("""
            SELECT COUNT(*) 
            FROM users 
            WHERE plan_expires_at IS NOT NULL 
            AND plan_expires_at BETWEEN NOW() AND NOW() + INTERVAL '7 days'
            AND user_type != 'trial'
            AND plan_id IN (1, 2)
        """)
        expiring_soon = cursor.fetchone()[0]
        
        # Assinaturas expiradas (ainda não processadas)
        cursor.execute("""
            SELECT COUNT(*) 
            FROM users 
            WHERE plan_expires_at IS NOT NULL 
            AND plan_expires_at < NOW()
            AND user_type != 'trial'
            AND plan_id IN (1, 2)
        """)
        expired = cursor.fetchone()[0]
        
        # Total de pagamentos este mês
        cursor.execute("""
            SELECT COUNT(*), COALESCE(SUM(amount), 0)
            FROM payments 
            WHERE created_at >= DATE_TRUNC('month', NOW())
            AND status = 'approved'
        """)
        monthly_payments = cursor.fetchone()
        
        # Receita total
        cursor.execute("""
            SELECT COUNT(*), COALESCE(SUM(amount), 0)
            FROM payments 
            WHERE status = 'approved'
        """)
        total_payments = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'stats': {
                'users_by_plan': [
                    {'plan_id': row[0], 'plan_name': row[1], 'count': row[2]} 
                    for row in users_by_plan
                ],
                'expiring_soon': expiring_soon,
                'expired': expired,
                'monthly_revenue': {
                    'payments_count': monthly_payments[0],
                    'total_amount': float(monthly_payments[1])
                },
                'total_revenue': {
                    'payments_count': total_payments[0],
                    'total_amount': float(total_payments[1])
                }
            }
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Erro interno: {str(e)}'}

# ===== FUNÇÃO PARA CORRIGIR O MERCADOPAGO_SERVICE =====

def fix_payment_expiration(payment_id, cycle):
    """
    Função para ser chamada pelo mercadopago_service.py
    Calcula a data de expiração correta baseada no ciclo
    """
    try:
        if cycle == 'annual':
            expires_at = datetime.now(timezone.utc) + timedelta(days=365)
        else:  # monthly
            expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        
        print(f"🔥 CONTROL_PAY: Expiração calculada para {cycle}: {expires_at}")
        return expires_at
        
    except Exception as e:
        print(f"❌ Erro ao calcular expiração: {e}")
        return datetime.now(timezone.utc) + timedelta(days=30)  # Fallback para mensal

# ===== VERIFICAÇÕES DE INTEGRIDADE =====

def verify_payments_integrity():
    """
    Verificar integridade dos dados de pagamento E trials
    """
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão com banco'}
        
        cursor = conn.cursor()
        
        # 🔥 VERIFICAÇÕES EXISTENTES (Pagamentos)
        
        # Usuários com planos pagos mas sem data de expiração
        cursor.execute("""
            SELECT COUNT(*) 
            FROM users 
            WHERE plan_id IN (1, 2) 
            AND user_type != 'trial'
            AND plan_expires_at IS NULL
        """)
        missing_expiration = cursor.fetchone()[0]
        
        # Usuários com data de expiração mas sem pagamentos
        cursor.execute("""
            SELECT u.id, u.name, u.email, u.plan_name
            FROM users u
            LEFT JOIN payments p ON u.id = p.user_id
            WHERE u.plan_expires_at IS NOT NULL 
            AND u.user_type != 'trial'
            AND p.id IS NULL
        """)
        no_payments = cursor.fetchall()
        
        # 🔥 NOVAS VERIFICAÇÕES (Trials)
        
        # Trials sem data de expiração
        cursor.execute("""
            SELECT COUNT(*) 
            FROM users 
            WHERE user_type = 'trial' 
            AND plan_expires_at IS NULL
        """)
        trials_missing_expiration = cursor.fetchone()[0]
        
        # Trials com plano básico (inconsistência)
        cursor.execute("""
            SELECT u.id, u.name, u.email, u.plan_name
            FROM users u
            WHERE u.user_type = 'trial' 
            AND u.plan_id = 3
        """)
        trials_with_basic_plan = cursor.fetchall()
        
        # Trials expirados há mais de 30 dias (não processados)
        cursor.execute("""
            SELECT u.id, u.name, u.email, u.plan_expires_at,
                   EXTRACT(days FROM (NOW() - u.plan_expires_at)) as days_expired
            FROM users u
            WHERE u.user_type = 'trial' 
            AND u.plan_expires_at IS NOT NULL
            AND u.plan_expires_at < NOW() - INTERVAL '30 days'
        """)
        old_expired_trials = cursor.fetchall()
        
        # Usuários com user_type inconsistente
        cursor.execute("""
            SELECT u.id, u.name, u.email, u.user_type, u.plan_id, u.plan_name
            FROM users u
            WHERE (u.user_type = 'trial' AND u.plan_id = 3)
            OR (u.user_type = 'regular' AND u.plan_id IN (1,2) AND u.plan_expires_at IS NULL)
        """)
        inconsistent_user_types = cursor.fetchall()
        
        # Usuários duplicados por email
        cursor.execute("""
            SELECT email, COUNT(*) as count
            FROM users 
            WHERE email IS NOT NULL
            GROUP BY email 
            HAVING COUNT(*) > 1
        """)
        duplicate_emails = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # 🔥 CALCULAR TOTAIS
        total_payment_issues = missing_expiration + len(no_payments)
        total_trial_issues = (trials_missing_expiration + len(trials_with_basic_plan) + 
                             len(old_expired_trials) + len(inconsistent_user_types))
        total_general_issues = len(duplicate_emails)
        
        return {
            'success': True,
            'integrity_check': {
                'payment_issues': {
                    'missing_expiration_count': missing_expiration,
                    'users_without_payments': [
                        {'id': row[0], 'name': row[1], 'email': row[2], 'plan': row[3]}
                        for row in no_payments
                    ],
                    'total': total_payment_issues
                },
                'trial_issues': {
                    'missing_expiration_count': trials_missing_expiration,
                    'trials_with_basic_plan': [
                        {'id': row[0], 'name': row[1], 'email': row[2], 'plan': row[3]}
                        for row in trials_with_basic_plan
                    ],
                    'old_expired_trials': [
                        {'id': row[0], 'name': row[1], 'email': row[2], 
                         'expired_at': row[3].isoformat() if row[3] else None,
                         'days_expired': int(row[4]) if row[4] else 0}
                        for row in old_expired_trials
                    ],
                    'inconsistent_user_types': [
                        {'id': row[0], 'name': row[1], 'email': row[2], 
                         'user_type': row[3], 'plan_id': row[4], 'plan_name': row[5]}
                        for row in inconsistent_user_types
                    ],
                    'total': total_trial_issues
                },
                'general_issues': {
                    'duplicate_emails': [
                        {'email': row[0], 'count': row[1]}
                        for row in duplicate_emails
                    ],
                    'total': total_general_issues
                },
                'summary': {
                    'payment_issues': total_payment_issues,
                    'trial_issues': total_trial_issues,
                    'general_issues': total_general_issues,
                    'total_issues': total_payment_issues + total_trial_issues + total_general_issues,
                    'system_health': 'healthy' if (total_payment_issues + total_trial_issues + total_general_issues) == 0 else 'needs_attention'
                }
            }
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Erro interno: {str(e)}'}    
    
    

if __name__ == "__main__":
    print("🔧 Control Pay Service - Sistema de Controle de Pagamentos")
    print("=" * 60)
    
    # Teste das funções principais
    print("📊 Estatísticas:")
    stats = get_subscription_stats()
    if stats['success']:
        print(f"✅ Stats carregadas: {stats['stats']}")
    
    print("\n🔍 Verificação de integridade:")
    integrity = verify_payments_integrity()
    if integrity['success']:
        print(f"✅ Integridade: {integrity['integrity_check']}")
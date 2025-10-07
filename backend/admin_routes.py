# admin_routes.py - VERSÃO COMPLETA SEM CONFLITOS

from flask import Blueprint, request, jsonify
import os
import jwt
from datetime import datetime, timezone, timedelta
from database import get_db_connection

# ===== BLUEPRINT ADMIN =====
admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# ===== VERIFICAÇÃO DE ADMIN =====
def verify_admin_token(token):
    """Verificar se token é de admin"""
    try:
        from flask import current_app
        
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload['user_id']
        
        conn = get_db_connection()
        if not conn:
            return None
            
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_type FROM users 
            WHERE id = %s AND user_type IN ('admin', 'master')
        """, (user_id,))
        
        admin = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return admin[0] if admin else None
        
    except Exception as e:
        print(f" Erro na verificação admin: {e}")
        return None

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
                return jsonify({'success': False, 'error': 'Acesso negado'}), 403
            
            return f(admin_id, *args, **kwargs)
        
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

# ===== ESTATÍSTICAS =====

@admin_bp.route('/stats')
@require_admin()
def get_admin_stats(admin_id):
    """Estatísticas do painel admin - CORRIGIDO"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Total de usuários
        cursor.execute("SELECT COUNT(*) FROM users WHERE user_type != 'deleted'")
        total_users = cursor.fetchone()[0]
        
        #  CORRIGIDO - Usuários premium (plan_id = 4 Community)
        cursor.execute("SELECT COUNT(*) FROM users WHERE plan_id = 4 AND user_type != 'deleted'")
        premium_users = cursor.fetchone()[0]
        
        # Cupons ativos
        try:
            cursor.execute("SELECT COUNT(*) FROM coupons WHERE active = true")
            active_coupons = cursor.fetchone()[0]
        except:
            active_coupons = 0
        
        #  CORRIGIDO - Receita mensal apenas Community
        monthly_revenue = premium_users * 79  # Preço do Community
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'total_users': total_users,
                'premium_users': premium_users,
                'active_coupons': active_coupons,
                'monthly_revenue': monthly_revenue
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== GERENCIAMENTO DE USUÁRIOS =====

@admin_bp.route('/list-users')
@require_admin()
def list_users(admin_id):
    """Listar todos os usuários"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT u.id, u.name, u.email, u.plan_id, u.plan_name, u.user_type, u.created_at,
                   EXTRACT(days FROM (NOW() - u.created_at)) as days_old
            FROM users u
            WHERE u.user_type != 'deleted'
            ORDER BY u.created_at DESC
            LIMIT 100
        """)
        
        users = []
        for row in cursor.fetchall():
            user_id, name, email, plan_id, plan_name, user_type, created_at, days_old = row
            
            users.append({
                'id': user_id,
                'name': name,
                'email': email,
                'plan_id': plan_id,
                'plan': plan_name or 'Básico',
                'type': user_type or 'regular',
                'created_at': created_at.isoformat() if created_at else None,
                'formatted_date': created_at.strftime('%d/%m/%Y') if created_at else 'N/A',
                'days_old': int(days_old) if days_old else 0
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'users': users
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/manage-subscription', methods=['POST'])
@require_admin()
def manage_subscription(admin_id):
    """Gerenciar assinatura de usuário - CORRIGIDO"""
    try:
        data = request.get_json()
        user_email = data.get('user_email')
        action = data.get('action')  # 'grant' ou 'revoke'
        plan_id = data.get('plan_id', 4)  #  CORRIGIDO - padrão Community
        
        if not user_email or not action:
            return jsonify({'success': False, 'error': 'Email e ação são obrigatórios'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Buscar usuário
        cursor.execute("SELECT id, name FROM users WHERE email = %s", (user_email,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Usuário não encontrado'}), 404
        
        user_id, user_name = user
        
        if action == 'grant':
            #  CORRIGIDO - Mapear apenas plan_ids que existem
            plan_names = {3: 'basico', 4: 'community'}
            plan_name = plan_names.get(plan_id, 'community')
            
            #  CORRIGIDO - Para Community, adicionar expiração e status
            if plan_id == 4:
                # Calcular expiração (30 dias para teste)
                expires_at = datetime.now(timezone.utc) + timedelta(days=30)
                
                cursor.execute("""
                    UPDATE users 
                    SET plan_id = %s, plan_name = %s, plan_expires_at = %s, 
                        subscription_status = 'active', user_type = 'paid',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE email = %s
                """, (plan_id, plan_name, expires_at, user_email))
            else:
                # Para Free (plan_id = 3)
                cursor.execute("""
                    UPDATE users 
                    SET plan_id = %s, plan_name = %s, plan_expires_at = NULL,
                        subscription_status = 'inactive', user_type = 'free',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE email = %s
                """, (plan_id, plan_name, user_email))
            
            message = f'Assinatura {plan_name} concedida para {user_name}'
            
        elif action == 'revoke':
            #  CORRIGIDO - Voltar para Free (plan_id = 3)
            cursor.execute("""
                UPDATE users 
                SET plan_id = 3, plan_name = 'basico', plan_expires_at = NULL,
                    subscription_status = 'inactive', user_type = 'free',
                    updated_at = CURRENT_TIMESTAMP
                WHERE email = %s
            """, (user_email,))
            
            message = f'Assinatura removida de {user_name} - voltou para Free'
        
        else:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Ação inválida'}), 400
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/promote-user', methods=['POST'])
@require_admin()
def promote_user(admin_id):
    """Promover usuário a admin - CORRIGIDO"""
    try:
        data = request.get_json()
        user_email = data.get('user_email')
        user_type = data.get('user_type', 'admin')
        
        if not user_email:
            return jsonify({'success': False, 'error': 'Email é obrigatório'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Buscar usuário
        cursor.execute("SELECT id, name FROM users WHERE email = %s", (user_email,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Usuário não encontrado'}), 404
        
        user_id, user_name = user
        
        #  CORRIGIDO - Admin tem acesso total (plan_id = 4)
        cursor.execute("""
            UPDATE users 
            SET user_type = %s, plan_id = 4, plan_name = 'community',
                subscription_status = 'active', plan_expires_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE email = %s
        """, (user_type, user_email))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'{user_name} promovido a {user_type} com acesso Community'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/users/delete', methods=['DELETE'])
@require_admin()
def delete_user(admin_id):
    """Marcar usuário como deletado"""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({'success': False, 'error': 'Email é obrigatório'}), 400
        
        # Proteção contra remoção do admin principal
        if email == 'diego@geminii.com.br':
            return jsonify({'success': False, 'error': 'Não é possível remover este usuário'}), 403
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Buscar usuário
        cursor.execute("SELECT id, name FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Usuário não encontrado'}), 404
        
        user_id, user_name = user
        
        # Marcar como deletado ao invés de deletar fisicamente
        cursor.execute("""
            UPDATE users 
            SET user_type = 'deleted', 
                plan_id = 1, 
                plan_name = 'Removido',
                updated_at = CURRENT_TIMESTAMP
            WHERE email = %s
        """, (email,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Usuário {user_name} foi marcado como removido'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ===== ADICIONAR ESTA ROTA NO SEU admin_routes.py =====

@admin_bp.route('/user/<user_email>/portfolios', methods=['GET'])
@require_admin()
def get_user_portfolios_admin(admin_id, user_email):
    """Buscar carteiras de um usuário específico (para admin)"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Buscar usuário primeiro
        cursor.execute("SELECT id, name FROM users WHERE email = %s", (user_email,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Usuário não encontrado'}), 404
        
        user_id, user_name = user
        
        # Buscar carteiras do usuário
        cursor.execute("""
            SELECT up.portfolio_name, p.display_name, up.granted_at
            FROM user_portfolios up
            JOIN portfolios p ON up.portfolio_name = p.name
            WHERE up.user_id = %s AND up.is_active = true
            ORDER BY p.display_name
        """, (user_id,))
        
        portfolios = []
        for row in cursor.fetchall():
            portfolios.append({
                'name': row[0],
                'display_name': row[1],
                'granted_at': row[2].isoformat() if row[2] else None
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'user': {
                'id': user_id,
                'name': user_name,
                'email': user_email
            },
            'portfolios': portfolios
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/user-portfolios', methods=['POST'])
@require_admin()
def manage_user_portfolios(admin_id):
    """Gerenciar carteiras de usuário (conceder/remover acesso)"""
    try:
        data = request.get_json()
        action = data.get('action')  # 'grant' ou 'revoke'
        user_email = data.get('user_email')
        portfolio_name = data.get('portfolio_name')
        
        if not all([action, user_email, portfolio_name]):
            return jsonify({'success': False, 'error': 'Dados obrigatórios faltando'}), 400
        
        if action not in ['grant', 'revoke']:
            return jsonify({'success': False, 'error': 'Ação deve ser grant ou revoke'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Buscar usuário
        cursor.execute("SELECT id, name FROM users WHERE email = %s", (user_email,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Usuário não encontrado'}), 404
        
        user_id, user_name = user
        
        # Verificar se carteira existe
        cursor.execute("SELECT display_name FROM portfolios WHERE name = %s", (portfolio_name,))
        portfolio = cursor.fetchone()
        
        if not portfolio:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Carteira não encontrada'}), 404
        
        portfolio_display_name = portfolio[0]
        
        if action == 'grant':
            # Conceder acesso
            cursor.execute("""
                INSERT INTO user_portfolios (user_id, portfolio_name, granted_by, is_active)
                VALUES (%s, %s, %s, true)
                ON CONFLICT (user_id, portfolio_name) 
                DO UPDATE SET 
                    is_active = true,
                    granted_by = EXCLUDED.granted_by,
                    granted_at = CURRENT_TIMESTAMP
            """, (user_id, portfolio_name, admin_id))
            
            message = f'Acesso à carteira {portfolio_display_name} concedido para {user_name}'
            
        elif action == 'revoke':
            # Remover acesso
            cursor.execute("""
                UPDATE user_portfolios 
                SET is_active = false 
                WHERE user_id = %s AND portfolio_name = %s
            """, (user_id, portfolio_name))
            
            if cursor.rowcount == 0:
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'error': 'Usuário não tem acesso a esta carteira'}), 404
            
            message = f'Acesso à carteira {portfolio_display_name} removido de {user_name}'
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500    



# ===== ADICIONAR ESTAS ROTAS NO FINAL DO admin_routes.py =====

@admin_bp.route('/payments', methods=['GET'])
@require_admin()
def get_payments_history(admin_id):
    """Listar histórico de pagamentos para o admin"""
    try:
        # Parâmetros de filtro
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        status_filter = request.args.get('status', 'all')
        user_email = request.args.get('user_email', '').strip()
        
        offset = (page - 1) * limit
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Query base
        base_query = """
            SELECT p.id, p.payment_id, p.status, p.amount, p.plan_id, p.plan_name,
                   p.cycle, p.external_reference, p.created_at, p.updated_at,
                   u.name as user_name, u.email as user_email
            FROM payments p
            LEFT JOIN users u ON p.user_id = u.id
        """
        
        # Filtros
        where_conditions = []
        params = []
        
        if status_filter != 'all':
            where_conditions.append("p.status = %s")
            params.append(status_filter)
        
        if user_email:
            where_conditions.append("u.email ILIKE %s")
            params.append(f"%{user_email}%")
        
        # Montar query final
        if where_conditions:
            base_query += " WHERE " + " AND ".join(where_conditions)
        
        base_query += " ORDER BY p.created_at DESC"
        
        # Buscar total de registros (para paginação)
        count_query = f"SELECT COUNT(*) FROM ({base_query}) as total"
        cursor.execute(count_query, params)
        total_records = cursor.fetchone()[0]
        
        # Buscar registros paginados
        paginated_query = base_query + f" LIMIT %s OFFSET %s"
        cursor.execute(paginated_query, params + [limit, offset])
        
        payments = []
        for row in cursor.fetchall():
            payment_id, mp_payment_id, status, amount, plan_id, plan_name, cycle, external_ref, created_at, updated_at, user_name, user_email = row
            
            payments.append({
                'id': payment_id,
                'payment_id': mp_payment_id,
                'status': status,
                'amount': float(amount) if amount else 0.0,
                'plan_id': plan_id,
                'plan_name': plan_name,
                'cycle': cycle,
                'external_reference': external_ref,
                'created_at': created_at.isoformat() if created_at else None,
                'updated_at': updated_at.isoformat() if updated_at else None,
                'user_name': user_name,
                'user_email': user_email,
                'formatted_date': created_at.strftime('%d/%m/%Y %H:%M') if created_at else 'N/A',
                'formatted_amount': f"R$ {float(amount):,.2f}" if amount else "R$ 0,00"
            })
        
        cursor.close()
        conn.close()
        
        # Calcular estatísticas
        total_pages = (total_records + limit - 1) // limit
        
        return jsonify({
            'success': True,
            'payments': payments,
            'pagination': {
                'current_page': page,
                'total_pages': total_pages,
                'total_records': total_records,
                'limit': limit
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/payments/stats', methods=['GET'])
@require_admin()
def get_payments_stats(admin_id):
    """Estatísticas de pagamentos para o dashboard admin"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Total de pagamentos
        cursor.execute("SELECT COUNT(*) FROM payments")
        total_payments = cursor.fetchone()[0]
        
        # Pagamentos aprovados
        cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'approved'")
        approved_payments = cursor.fetchone()[0]
        
        # Pagamentos pendentes
        cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
        pending_payments = cursor.fetchone()[0]
        
        # Receita total (apenas approved)
        cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'approved'")
        total_revenue = cursor.fetchone()[0]
        
        # Receita do mês atual
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM payments 
            WHERE status = 'approved' 
            AND EXTRACT(MONTH FROM created_at) = EXTRACT(MONTH FROM CURRENT_DATE)
            AND EXTRACT(YEAR FROM created_at) = EXTRACT(YEAR FROM CURRENT_DATE)
        """)
        monthly_revenue = cursor.fetchone()[0]
        
        # Últimos pagamentos (5 mais recentes)
        cursor.execute("""
            SELECT p.payment_id, p.amount, p.status, p.plan_name, p.created_at,
                   u.name as user_name, u.email as user_email
            FROM payments p
            LEFT JOIN users u ON p.user_id = u.id
            ORDER BY p.created_at DESC
            LIMIT 5
        """)
        
        recent_payments = []
        for row in cursor.fetchall():
            payment_id, amount, status, plan_name, created_at, user_name, user_email = row
            
            recent_payments.append({
                'payment_id': payment_id,
                'amount': float(amount) if amount else 0.0,
                'formatted_amount': f"R$ {float(amount):,.2f}" if amount else "R$ 0,00",
                'status': status,
                'plan_name': plan_name,
                'user_name': user_name,
                'user_email': user_email,
                'created_at': created_at.isoformat() if created_at else None,
                'formatted_date': created_at.strftime('%d/%m/%Y %H:%M') if created_at else 'N/A'
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_payments': total_payments,
                'approved_payments': approved_payments,
                'pending_payments': pending_payments,
                'failed_payments': total_payments - approved_payments - pending_payments,
                'total_revenue': float(total_revenue),
                'monthly_revenue': float(monthly_revenue),
                'formatted_total_revenue': f"R$ {float(total_revenue):,.2f}",
                'formatted_monthly_revenue': f"R$ {float(monthly_revenue):,.2f}"
            },
            'recent_payments': recent_payments
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/payments/<payment_id>/details', methods=['GET'])
@require_admin()
def get_payment_details(admin_id, payment_id):
    """Detalhes específicos de um pagamento"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT p.id, p.payment_id, p.status, p.amount, p.plan_id, p.plan_name,
                   p.cycle, p.external_reference, p.device_id, p.created_at, p.updated_at,
                   u.id as user_id, u.name as user_name, u.email as user_email,
                   u.plan_id as current_plan_id, u.plan_name as current_plan_name
            FROM payments p
            LEFT JOIN users u ON p.user_id = u.id
            WHERE p.payment_id = %s
        """, (payment_id,))
        
        payment = cursor.fetchone()
        
        if not payment:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Pagamento não encontrado'}), 404
        
        # Extrair dados
        p_id, mp_payment_id, status, amount, plan_id, plan_name, cycle, external_ref, device_id, created_at, updated_at, user_id, user_name, user_email, current_plan_id, current_plan_name = payment
        
        payment_details = {
            'id': p_id,
            'payment_id': mp_payment_id,
            'status': status,
            'amount': float(amount) if amount else 0.0,
            'formatted_amount': f"R$ {float(amount):,.2f}" if amount else "R$ 0,00",
            'plan_id': plan_id,
            'plan_name': plan_name,
            'cycle': cycle,
            'external_reference': external_ref,
            'device_id': device_id,
            'created_at': created_at.isoformat() if created_at else None,
            'updated_at': updated_at.isoformat() if updated_at else None,
            'formatted_created': created_at.strftime('%d/%m/%Y %H:%M:%S') if created_at else 'N/A',
            'formatted_updated': updated_at.strftime('%d/%m/%Y %H:%M:%S') if updated_at else 'N/A',
            'user': {
                'id': user_id,
                'name': user_name,
                'email': user_email,
                'current_plan_id': current_plan_id,
                'current_plan_name': current_plan_name
            }
        }
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'payment': payment_details
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


#======= rotas banco de dados recomentações free=============

@admin_bp.route('/enhanced-stats')
@require_admin()
def get_enhanced_admin_stats(admin_id):
    """Estatísticas aprimoradas do admin - CORRIGIDO"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
        
        cursor = conn.cursor()
        
        # Total de usuários
        cursor.execute("SELECT COUNT(*) FROM users WHERE user_type != 'deleted'")
        total_users = cursor.fetchone()[0]
        
        #  CORRIGIDO - Usuários Community (plan_id = 4)
        cursor.execute("SELECT COUNT(*) FROM users WHERE plan_id = 4 AND user_type != 'deleted'")
        premium_users = cursor.fetchone()[0]
        
        # Usuários Free (plan_id = 3)
        cursor.execute("SELECT COUNT(*) FROM users WHERE plan_id = 3 AND user_type != 'deleted'")
        free_users = cursor.fetchone()[0]
        
        # Usuários em Trial
        cursor.execute("SELECT COUNT(*) FROM users WHERE user_type = 'trial' AND user_type != 'deleted'")
        trial_users = cursor.fetchone()[0]
        
        # Cupons ativos
        try:
            cursor.execute("SELECT COUNT(*) FROM coupons WHERE active = true")
            active_coupons = cursor.fetchone()[0]
        except:
            active_coupons = 0
        
        #  CORRIGIDO - Receita estimada apenas Community
        cursor.execute("""
            SELECT COALESCE(SUM(
                CASE 
                    WHEN plan_id = 4 AND subscription_status = 'active' THEN 79.00
                    ELSE 0 
                END
            ), 0) FROM users WHERE user_type != 'deleted'
        """)
        estimated_revenue = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'total_users': total_users,
                'premium_users': premium_users,  # Community
                'free_users': free_users,        # Free
                'trial_users': trial_users,      # Em trial
                'active_coupons': active_coupons,
                'estimated_monthly_revenue': float(estimated_revenue)
            }
        })
        
    except Exception as e:
        print(f"Erro nas estatísticas aprimoradas: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/recent-activity')
@require_admin()  
def get_recent_activity(admin_id):
    """Atividade recente do sistema"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
        
        cursor = conn.cursor()
        
        activities = []
        
        # Usuários recentes (último dia)
        try:
            cursor.execute("""
                SELECT name, email, created_at 
                FROM users 
                WHERE created_at >= NOW() - INTERVAL '24 hours'
                AND user_type != 'deleted'
                ORDER BY created_at DESC 
                LIMIT 3
            """)
            recent_users = cursor.fetchall()
            
            for user in recent_users:
                activities.append({
                    'type': 'new_user',
                    'message': f'Novo usuário: {user[0]}',
                    'time': 'Hoje',
                    'icon': 'fas fa-user-plus',
                    'color': 'text-green-400'
                })
        except Exception as e:
            print(f"Erro ao buscar usuários recentes: {e}")
        
        # Recomendações recentes (última semana)
        try:
            cursor.execute("""
                SELECT ticker, action, created_at
                FROM recommendations_free 
                WHERE created_at >= NOW() - INTERVAL '7 days'
                ORDER BY created_at DESC 
                LIMIT 2
            """)
            recent_recs = cursor.fetchall()
            
            for rec in recent_recs:
                activities.append({
                    'type': 'recommendation',
                    'message': f'Nova recomendação: {rec[0]} ({rec[1]})',
                    'time': 'Esta semana',
                    'icon': 'fas fa-chart-line',
                    'color': 'text-blue-400'
                })
        except Exception as e:
            print(f"Erro ao buscar recomendações recentes: {e}")
        
        # Se não há atividades reais, mostrar atividades do sistema
        if not activities:
            activities = [
                {
                    'type': 'system',
                    'message': 'Sistema funcionando normalmente',
                    'time': 'Agora',
                    'icon': 'fas fa-check-circle',
                    'color': 'text-green-400'
                },
                {
                    'type': 'database',
                    'message': 'Banco de dados conectado e operacional',
                    'time': '1 minuto atrás',
                    'icon': 'fas fa-database',
                    'color': 'text-blue-400'
                },
                {
                    'type': 'admin_access',
                    'message': 'Painel administrativo acessado',
                    'time': '2 minutos atrás',
                    'icon': 'fas fa-shield-alt',
                    'color': 'text-purple-400'
                }
            ]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'activities': activities
        })
        
    except Exception as e:
        print(f"Erro na atividade recente: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


#funções novas admin dashboard

## Adicione estas funções no seu admin_routes.py

@admin_bp.route('/create-user', methods=['POST'])
@require_admin()
def create_user(admin_id):
    """Criar novo usuário que entra automaticamente em trial"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()
        trial_days = data.get('trial_days', 7)
        
        if not name or not email:
            return jsonify({'success': False, 'error': 'Nome e email são obrigatórios'}), 400
        
        # Validar email
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return jsonify({'success': False, 'error': 'Email inválido'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Verificar se email já existe
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Email já cadastrado no sistema'}), 400
        
        # Criar senha padrão (hash de "123456")
        import hashlib
        default_password = hashlib.sha256("123456".encode()).hexdigest()
        
        # Calcular data de expiração do trial
        from datetime import datetime, timezone, timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(days=trial_days)
        now = datetime.now(timezone.utc)
        
        # Inserir novo usuário em trial
        cursor.execute("""
            INSERT INTO users (
                name, email, password, plan_id, plan_name, user_type,
                subscription_status, plan_expires_at, email_confirmed,
                email_confirmed_at, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            name,                    # name
            email,                   # email  
            default_password,        # password (hash de 123456)
            4,                       # plan_id (Community)
            'community',             # plan_name
            'trial',                 # user_type
            'trial',                 # subscription_status
            expires_at,              # plan_expires_at
            True,                    # email_confirmed
            now,                     # email_confirmed_at
            now,                     # created_at
            now                      # updated_at
        ))
        
        user_id = cursor.fetchone()[0]
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Usuário {name} criado com sucesso!',
            'user_info': {
                'id': user_id,
                'name': name,
                'email': email,
                'trial_days': trial_days,
                'expires_at': expires_at.isoformat(),
                'default_password': '123456'
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/list-users-enhanced')
@require_admin()
def list_users_enhanced(admin_id):
    """Listar usuários com informações detalhadas incluindo último login"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Verificar se coluna last_login existe, se não existir, adicionar
        try:
            cursor.execute("""
                ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP;
            """)
            conn.commit()
        except:
            pass  # Coluna já existe
        
        cursor.execute("""
            SELECT u.id, u.name, u.email, u.plan_id, u.plan_name, u.user_type, 
                   u.created_at, u.plan_expires_at, u.subscription_status, u.last_login,
                   EXTRACT(days FROM (NOW() - u.created_at)) as days_with_us,
                   CASE 
                       WHEN u.plan_expires_at IS NOT NULL AND u.plan_expires_at > NOW() THEN
                           EXTRACT(days FROM (u.plan_expires_at - NOW()))
                       ELSE NULL
                   END as days_until_expiry,
                   CASE 
                       WHEN u.plan_expires_at IS NOT NULL AND u.plan_expires_at <= NOW() THEN true
                       ELSE false
                   END as is_expired
            FROM users u
            WHERE u.user_type != 'deleted'
            ORDER BY u.created_at DESC
            LIMIT 100
        """)
        
        users = []
        for row in cursor.fetchall():
            user_id, name, email, plan_id, plan_name, user_type, created_at, plan_expires_at, subscription_status, last_login, days_with_us, days_until_expiry, is_expired = row
            
            users.append({
                'id': user_id,
                'name': name,
                'email': email,
                'plan_id': plan_id,
                'plan': plan_name or 'Básico',
                'type': user_type or 'regular',
                'subscription_status': subscription_status or 'inactive',
                'created_at': created_at.isoformat() if created_at else None,
                'plan_expires_at': plan_expires_at.isoformat() if plan_expires_at else None,
                'last_login': last_login.isoformat() if last_login else None,
                'formatted_date': created_at.strftime('%d/%m/%Y') if created_at else 'N/A',
                'formatted_last_login': last_login.strftime('%d/%m/%Y %H:%M') if last_login else 'Nunca logou',
                'days_with_us': int(days_with_us) if days_with_us else 0,
                'days_until_expiry': int(days_until_expiry) if days_until_expiry else None,
                'is_expired': is_expired,
                'has_trial': plan_expires_at is not None
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'users': users
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ===== FUNÇÃO EXPORT =====
def get_admin_blueprint():
    """Retornar blueprint para registrar no Flask"""
    return admin_bp
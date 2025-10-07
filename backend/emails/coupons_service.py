# coupons_service.py - SERVIÇO COMPLETO DE CUPONS
# ===================================================

from flask import Blueprint, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime, timezone
import jwt

# ===== BLUEPRINT =====
coupons_bp = Blueprint('coupons', __name__, url_prefix='/api/admin')

# ===== CONFIGURAÇÃO DO BANCO =====
def get_db_connection():
    """Conectar com PostgreSQL (local ou Railway)"""
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            database_url = os.environ.get("DATABASE_URL")
            
            if database_url:
                if database_url.startswith("postgres://"):
                    database_url = database_url.replace("postgres://", "postgresql://", 1)
                conn = psycopg2.connect(database_url, sslmode='require', connect_timeout=10)
            else:
                conn = psycopg2.connect(
                    host=os.environ.get("DB_HOST", "localhost"),
                    database=os.environ.get("DB_NAME", "postgres"),
                    user=os.environ.get("DB_USER", "postgres"),
                    password=os.environ.get("DB_PASSWORD", "#geminii"),
                    port=os.environ.get("DB_PORT", "5432"),
                    connect_timeout=10
                )
            
            # Testar conexão
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            
            return conn
            
        except Exception as e:
            if attempt < max_retries - 1:
                import time
                time.sleep(1)
            else:
                print(f" Todas as tentativas falharam: {e}")
                return None
    
    return None

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
        return None

def is_admin_request():
    """Verificação de admin"""
    auth_header = request.headers.get('Authorization', '')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        return False
    
    token = auth_header.replace('Bearer ', '')
    
    # Tentar verificação JWT
    admin_id = verify_admin_token(token)
    if admin_id:
        return True
    
    # Fallback para desenvolvimento
    return 'admin' in auth_header.lower()

# ===== DETECTAR ESTRUTURA DA TABELA =====
def detect_table_structure():
    """Detectar estrutura da tabela automaticamente"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'coupons'
        """)
        columns = [row[0] for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        # Mapear campos
        structure = {
            'columns': columns,
            'status_field': 'active' if 'active' in columns else 'is_active' if 'is_active' in columns else None,
            'uses_field': 'used_count' if 'used_count' in columns else 'current_uses' if 'current_uses' in columns else None,
            'expires_field': 'valid_until' if 'valid_until' in columns else 'expires_at' if 'expires_at' in columns else None
        }
        
        return structure
        
    except Exception as e:
        print(f" Erro ao detectar estrutura: {e}")
        return None

# ===== SETUP DA TABELA =====
def setup_coupons_table():
    """Configurar tabela de cupons"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Verificar se tabela existe
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'coupons'
            )
        """)
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            # Criar tabela
            cursor.execute("""
                CREATE TABLE coupons (
                    id SERIAL PRIMARY KEY,
                    code VARCHAR(50) UNIQUE NOT NULL,
                    discount_percent DECIMAL(5,2) NOT NULL,
                    discount_type VARCHAR(20) DEFAULT 'percent',
                    applicable_plans TEXT[],
                    max_uses INTEGER,
                    used_count INTEGER DEFAULT 0,
                    valid_until TIMESTAMP,
                    active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print(" Tabela coupons criada")
        
        # Criar tabela de usos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS coupon_uses (
                id SERIAL PRIMARY KEY,
                coupon_id INTEGER REFERENCES coupons(id) ON DELETE CASCADE,
                user_id INTEGER,
                plan_name VARCHAR(50) NOT NULL,
                original_price DECIMAL(10,2) NOT NULL,
                discount_amount DECIMAL(10,2) NOT NULL,
                final_price DECIMAL(10,2) NOT NULL,
                payment_id VARCHAR(255),
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Inserir cupons de teste
        cursor.execute("""
            INSERT INTO coupons (code, discount_percent, applicable_plans, max_uses, active)
            VALUES 
                ('TESTE50', 50.0, ARRAY['pro', 'premium'], 100, true),
                ('PROMO20', 20.0, ARRAY['pro'], 50, true),
                ('DESCONTO30', 30.0, ARRAY['premium'], NULL, true)
            ON CONFLICT (code) DO NOTHING
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(" Tabela de cupons configurada")
        return True
        
    except Exception as e:
        print(f" Erro ao configurar tabela: {e}")
        return False

# ===== ROTAS =====

@coupons_bp.route('/coupons', methods=['GET'])
def get_coupons():
    """Listar cupons"""
    try:
        if not is_admin_request():
            return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
        structure = detect_table_structure()
        if not structure:
            return jsonify({'success': False, 'error': 'Erro ao detectar estrutura'}), 500
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Construir query adaptável
        base_fields = ['id', 'code', 'discount_percent']
        optional_fields = ['discount_type', 'applicable_plans', 'max_uses', 'created_at']
        
        select_fields = base_fields.copy()
        for field in optional_fields:
            if field in structure['columns']:
                select_fields.append(field)
        
        # Adicionar campos mapeados
        if structure['status_field']:
            select_fields.append(f"{structure['status_field']} as active_status")
        
        if structure['uses_field']:
            select_fields.append(f"{structure['uses_field']} as uses_count")
        
        if structure['expires_field']:
            select_fields.append(f"{structure['expires_field']} as expires_date")
        
        query = f"SELECT {', '.join(select_fields)} FROM coupons ORDER BY id DESC"
        cursor.execute(query)
        
        coupons = []
        for row in cursor.fetchall():
            # Processar applicable_plans
            plans = row.get('applicable_plans', [])
            if isinstance(plans, str):
                plans = plans.split(',') if plans else []
            elif not isinstance(plans, list):
                plans = []
            
            coupon_data = {
                'id': row['id'],
                'code': row['code'],
                'discount_percent': float(row['discount_percent']),
                'discount_type': row.get('discount_type', 'percent'),
                'applicable_plans': plans,
                'max_uses': row.get('max_uses'),
                'used_count': row.get('uses_count', 0),
                'valid_until': row['expires_date'].isoformat() if row.get('expires_date') else None,
                'is_active': bool(row.get('active_status', True)),
                'active': bool(row.get('active_status', True)),
                'created_at': row['created_at'].isoformat() if row.get('created_at') else None
            }
            
            coupons.append(coupon_data)
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'coupons': coupons
        })
        
    except Exception as e:
        print(f" Erro ao listar cupons: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@coupons_bp.route('/coupons', methods=['POST'])
def create_coupon():
    """Criar cupom"""
    try:
        if not is_admin_request():
            return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
        data = request.get_json()
        
        code = data.get('code', '').upper().strip()
        discount_percent = data.get('discount_percent')
        applicable_plans = data.get('applicable_plans', [])
        max_uses = data.get('max_uses')
        valid_until = data.get('valid_until')
        
        # Validações
        if not code or not discount_percent or not applicable_plans:
            return jsonify({'success': False, 'error': 'Código, desconto e planos são obrigatórios'}), 400
        
        if discount_percent <= 0 or discount_percent > 100:
            return jsonify({'success': False, 'error': 'Desconto deve ser entre 1 e 100%'}), 400
        
        structure = detect_table_structure()
        if not structure:
            return jsonify({'success': False, 'error': 'Erro ao detectar estrutura'}), 500
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Verificar se código já existe
        cursor.execute("SELECT id FROM coupons WHERE code = %s", (code,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': f'Cupom {code} já existe'}), 400
        
        # Construir INSERT adaptável
        insert_fields = ['code', 'discount_percent']
        insert_values = [code, discount_percent]
        placeholders = ['%s', '%s']
        
        # Campos opcionais
        optional_data = {
            'discount_type': 'percent',
            'applicable_plans': applicable_plans,
            'max_uses': max_uses,
            'created_at': datetime.now(timezone.utc)
        }
        
        for field, value in optional_data.items():
            if field in structure['columns'] and value is not None:
                insert_fields.append(field)
                insert_values.append(value)
                placeholders.append('%s')
        
        # Campos mapeados
        if structure['status_field']:
            insert_fields.append(structure['status_field'])
            insert_values.append(True)
            placeholders.append('%s')
        
        if structure['uses_field']:
            insert_fields.append(structure['uses_field'])
            insert_values.append(0)
            placeholders.append('%s')
        
        if structure['expires_field'] and valid_until:
            insert_fields.append(structure['expires_field'])
            insert_values.append(valid_until)
            placeholders.append('%s')
        
        query = f"""
            INSERT INTO coupons ({', '.join(insert_fields)}) 
            VALUES ({', '.join(placeholders)})
            RETURNING id
        """
        
        cursor.execute(query, insert_values)
        coupon_id = cursor.fetchone()[0]
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Cupom {code} criado com sucesso!',
            'coupon_id': coupon_id
        })
        
    except Exception as e:
        print(f" Erro ao criar cupom: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@coupons_bp.route('/coupons/<coupon_code>/toggle', methods=['PATCH'])
def toggle_coupon(coupon_code):
    """Ativar/desativar cupom"""
    try:
        if not is_admin_request():
            return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
        data = request.get_json()
        is_active = data.get('is_active', True)
        
        structure = detect_table_structure()
        if not structure or not structure['status_field']:
            return jsonify({'success': False, 'error': 'Campo de status não encontrado'}), 500
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Construir UPDATE
        update_fields = [f"{structure['status_field']} = %s"]
        params = [is_active]
        
        if 'updated_at' in structure['columns']:
            update_fields.append("updated_at = %s")
            params.append(datetime.now(timezone.utc))
        
        params.append(coupon_code.upper())
        
        query = f"""
            UPDATE coupons 
            SET {', '.join(update_fields)}
            WHERE code = %s
            RETURNING id, code
        """
        
        cursor.execute(query, params)
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Cupom não encontrado'}), 404
        
        conn.commit()
        cursor.close()
        conn.close()
        
        status_text = 'ativado' if is_active else 'desativado'
        
        return jsonify({
            'success': True,
            'message': f'Cupom {coupon_code} {status_text} com sucesso!'
        })
        
    except Exception as e:
        print(f" Erro ao alterar cupom: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@coupons_bp.route('/coupons/<coupon_code>', methods=['DELETE'])
def delete_coupon(coupon_code):
    """Deletar cupom"""
    try:
        if not is_admin_request():
            return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM coupons WHERE code = %s RETURNING id, code", (coupon_code.upper(),))
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Cupom não encontrado'}), 404
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Cupom {coupon_code} deletado com sucesso!'
        })
        
    except Exception as e:
        print(f" Erro ao deletar cupom: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== VALIDAÇÃO PARA FRONTEND =====
@coupons_bp.route('/validate-coupon/<coupon_code>', methods=['POST'])
def validate_coupon_public(coupon_code):
    """Validar cupom para uso público"""
    try:
        data = request.get_json()
        plan_name = data.get('plan_name', 'pro')
        user_id = data.get('user_id', 1)
        
        structure = detect_table_structure()
        if not structure:
            return jsonify({'success': False, 'error': 'Erro interno'}), 500
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Construir query adaptável
        select_fields = ['id', 'code', 'discount_percent', 'applicable_plans', 'max_uses']
        
        if structure['status_field']:
            select_fields.append(structure['status_field'])
        
        if structure['uses_field']:
            select_fields.append(structure['uses_field'])
        
        if structure['expires_field']:
            select_fields.append(structure['expires_field'])
        
        query = f"SELECT {', '.join(select_fields)} FROM coupons WHERE code = %s"
        cursor.execute(query, (coupon_code.upper(),))
        
        coupon = cursor.fetchone()
        
        if not coupon:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Cupom não encontrado'}), 404
        
        # Verificar se está ativo
        if structure['status_field']:
            is_active = coupon[select_fields.index(structure['status_field'])]
            if not is_active:
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'error': 'Cupom inativo'}), 400
        
        # Verificar se expirou
        if structure['expires_field']:
            valid_until = coupon[select_fields.index(structure['expires_field'])]
            if valid_until and datetime.now(timezone.utc) > valid_until.replace(tzinfo=timezone.utc):
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'error': 'Cupom expirado'}), 400
        
        # Verificar limite de usos
        if structure['uses_field']:
            used_count = coupon[select_fields.index(structure['uses_field'])] or 0
            max_uses = coupon[select_fields.index('max_uses')]
            
            if max_uses and used_count >= max_uses:
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'error': 'Cupom esgotado'}), 400
        
        # Verificar se usuário já usou este cupom
        coupon_id = coupon[0]
        cursor.execute("""
            SELECT id FROM coupon_uses 
            WHERE coupon_id = %s AND user_id = %s
        """, (coupon_id, user_id))
        
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Cupom já utilizado por você'}), 400
        
        # Verificar planos aplicáveis
        applicable_plans = coupon[select_fields.index('applicable_plans')]
        if applicable_plans and plan_name not in applicable_plans:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': f'Cupom não aplicável ao plano {plan_name}'}), 400
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Cupom válido!',
            'data': {
                'id': coupon[0],
                'code': coupon[1],
                'discount_percent': float(coupon[2]),
                'applicable_plans': applicable_plans or []
            }
        })
        
    except Exception as e:
        print(f" Erro ao validar cupom: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== APLICAR USO DO CUPOM =====
@coupons_bp.route('/use-coupon', methods=['POST'])
def use_coupon():
    """Aplicar uso do cupom (para ser chamado após pagamento aprovado)"""
    try:
        data = request.get_json()
        
        coupon_code = data.get('coupon_code', '').upper().strip()
        user_id = data.get('user_id')
        plan_name = data.get('plan_name')
        original_price = data.get('original_price', 0)
        final_price = data.get('final_price', 0)
        payment_id = data.get('payment_id')
        
        if not all([coupon_code, user_id, plan_name]):
            return jsonify({'success': False, 'error': 'Dados obrigatórios faltando'}), 400
        
        structure = detect_table_structure()
        if not structure:
            return jsonify({'success': False, 'error': 'Erro interno'}), 500
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Buscar cupom
        cursor.execute("SELECT id, discount_percent FROM coupons WHERE code = %s", (coupon_code,))
        coupon = cursor.fetchone()
        
        if not coupon:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Cupom não encontrado'}), 404
        
        coupon_id, discount_percent = coupon
        discount_amount = original_price - final_price
        
        # Verificar se já foi usado por este usuário
        cursor.execute("""
            SELECT id FROM coupon_uses 
            WHERE coupon_id = %s AND user_id = %s
        """, (coupon_id, user_id))
        
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Cupom já utilizado'}), 400
        
        # Registrar uso do cupom
        cursor.execute("""
            INSERT INTO coupon_uses (
                coupon_id, user_id, plan_name, original_price, 
                discount_amount, final_price, payment_id, used_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            coupon_id, user_id, plan_name, original_price,
            discount_amount, final_price, payment_id, datetime.now(timezone.utc)
        ))
        
        # Incrementar contador de usos se campo existir
        if structure['uses_field']:
            cursor.execute(f"""
                UPDATE coupons 
                SET {structure['uses_field']} = COALESCE({structure['uses_field']}, 0) + 1,
                    updated_at = %s
                WHERE id = %s
            """, (datetime.now(timezone.utc), coupon_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f" Cupom {coupon_code} usado com sucesso por usuário {user_id}")
        
        return jsonify({
            'success': True,
            'message': f'Cupom {coupon_code} aplicado com sucesso!',
            'discount_applied': discount_amount
        })
        
    except Exception as e:
        print(f" Erro ao aplicar cupom: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== ROTA PARA FRONTEND VALIDAR (COMPATIBILIDADE) =====
# Esta é a rota que o frontend está chamando
@coupons_bp.route('/../validate-coupon', methods=['POST'])
def validate_coupon_frontend():
    """Rota de compatibilidade para validação do frontend"""
    try:
        data = request.get_json()
        coupon_code = data.get('code', '').upper().strip()
        
        if not coupon_code:
            return jsonify({'success': False, 'error': 'Código do cupom é obrigatório'}), 400
        
        # Chamar a função principal de validação
        return validate_coupon_public(coupon_code)
        
    except Exception as e:
        print(f" Erro na validação do frontend: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ===== INICIALIZAÇÃO =====
def init_coupons_service():
    """Inicializar serviço de cupons"""
    print("🎫 Inicializando serviço de cupons...")
    
    if setup_coupons_table():
        print(" Serviço de cupons inicializado!")
        return True
    else:
        print(" Falha na inicialização")
        return False

# ===== EXPORT =====
def get_coupons_blueprint():
    """Retornar blueprint"""
    return coupons_bp

# ===== ROTA ADICIONAL PARA COMPATIBILIDADE =====
# O frontend chama /api/validate-coupon, mas nosso blueprint é /api/admin
# Vamos criar um blueprint adicional para essa rota específica

validate_bp = Blueprint('validate', __name__, url_prefix='/api')

@validate_bp.route('/validate-coupon', methods=['POST'])
def validate_coupon_main():
    """Validar cupom - rota principal para o frontend"""
    try:
        data = request.get_json()
        coupon_code = data.get('code', '').upper().strip()
        plan_name = data.get('plan_name', 'pro')
        user_id = data.get('user_id', 1)
        
        if not coupon_code:
            return jsonify({'success': False, 'error': 'Código do cupom é obrigatório'}), 400
        
        structure = detect_table_structure()
        if not structure:
            return jsonify({'success': False, 'error': 'Erro interno'}), 500
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Erro de conexão'}), 500
            
        cursor = conn.cursor()
        
        # Construir query adaptável
        select_fields = ['id', 'code', 'discount_percent', 'applicable_plans', 'max_uses']
        
        if structure['status_field']:
            select_fields.append(structure['status_field'])
        
        if structure['uses_field']:
            select_fields.append(structure['uses_field'])
        
        if structure['expires_field']:
            select_fields.append(structure['expires_field'])
        
        query = f"SELECT {', '.join(select_fields)} FROM coupons WHERE code = %s"
        cursor.execute(query, (coupon_code,))
        
        coupon = cursor.fetchone()
        
        if not coupon:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Cupom não encontrado'}), 404
        
        coupon_id = coupon[0]
        
        # Verificar se está ativo
        if structure['status_field']:
            is_active = coupon[select_fields.index(structure['status_field'])]
            if not is_active:
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'error': 'Cupom inativo'}), 400
        
        # Verificar se expirou
        if structure['expires_field']:
            valid_until_idx = select_fields.index(structure['expires_field'])
            if valid_until_idx < len(coupon) and coupon[valid_until_idx]:
                valid_until = coupon[valid_until_idx]
                if valid_until and datetime.now(timezone.utc) > valid_until.replace(tzinfo=timezone.utc):
                    cursor.close()
                    conn.close()
                    return jsonify({'success': False, 'error': 'Cupom expirado'}), 400
        
        # Verificar limite de usos
        if structure['uses_field']:
            used_count = coupon[select_fields.index(structure['uses_field'])] or 0
            max_uses = coupon[select_fields.index('max_uses')]
            
            if max_uses and used_count >= max_uses:
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'error': 'Cupom esgotado'}), 400
        
        # Verificar se usuário já usou este cupom
        cursor.execute("""
            SELECT id FROM coupon_uses 
            WHERE coupon_id = %s AND user_id = %s
        """, (coupon_id, user_id))
        
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Cupom já utilizado por você'}), 400
        
        # Verificar planos aplicáveis
        applicable_plans = coupon[select_fields.index('applicable_plans')]
        if applicable_plans and plan_name not in applicable_plans:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': f'Cupom não aplicável ao plano {plan_name}'}), 400
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Cupom válido!',
            'data': {
                'id': coupon_id,
                'code': coupon[1],
                'discount_percent': float(coupon[2]),
                'applicable_plans': applicable_plans or []
            }
        })
        
    except Exception as e:
        print(f" Erro ao validar cupom: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def get_validate_blueprint():
    """Retornar blueprint de validação"""
    return validate_bp
import psycopg2
import secrets
from datetime import datetime, timedelta, timezone

def get_db_connection():
    """Conectar com PostgreSQL local"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="postgres", 
            user="postgres",
            password="#geminii",
            port="5432"
        )
        return conn
    except Exception as e:
        print(f"❌ Erro ao conectar no banco: {e}")
        return None

def create_password_reset_table():
    """Criar tabela para tokens de recuperação"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                token VARCHAR(255) UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)
        
        # Índices para performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reset_token ON password_reset_tokens(token);
            CREATE INDEX IF NOT EXISTS idx_reset_user ON password_reset_tokens(user_id);
            CREATE INDEX IF NOT EXISTS idx_reset_expires ON password_reset_tokens(expires_at);
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Tabela 'password_reset_tokens' criada!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabela: {e}")
        return False

def generate_reset_token(email):
    """Gerar token de recuperação para um email"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão'}
        
        cursor = conn.cursor()
        
        # Verificar se usuário existe
        cursor.execute("SELECT id, name FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            conn.close()
            return {'success': False, 'error': 'E-mail não encontrado'}
        
        user_id, name = user
        
        # Invalidar tokens antigos (marcar como usados)
        cursor.execute("""
            UPDATE password_reset_tokens 
            SET used = TRUE 
            WHERE user_id = %s AND used = FALSE
        """, (user_id,))
        
        # Gerar novo token (32 caracteres aleatórios)
        reset_token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=1)  # Usar horário local
        
        print(f"🕐 Gerando token que expira em: {expires_at}")
        
        # Salvar token no banco
        cursor.execute("""
            INSERT INTO password_reset_tokens (user_id, token, expires_at)
            VALUES (%s, %s, %s)
        """, (user_id, reset_token, expires_at))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'token': reset_token,
            'user_name': name,
            'expires_in': '1 hora',
            'message': 'Token de recuperação gerado!'
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Erro interno: {str(e)}'}

def validate_reset_token(token):
    """Validar se token de recuperação é válido"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão'}
        
        cursor = conn.cursor()
        
        # Buscar token válido
        cursor.execute("""
            SELECT rt.id, rt.user_id, u.email, u.name, rt.expires_at
            FROM password_reset_tokens rt
            JOIN users u ON u.id = rt.user_id
            WHERE rt.token = %s AND rt.used = FALSE
        """, (token,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not result:
            return {'success': False, 'error': 'Token inválido ou já usado'}
        
        token_id, user_id, email, name, expires_at = result
        
        # Debug: Mostrar horários
        now_local = datetime.now()
        print(f"🕐 Agora LOCAL: {now_local}")
        print(f"🕐 Token expira: {expires_at}")
        print(f"🕐 Diferença: {expires_at - now_local}")
        
        # Verificar se não expirou (usar horário local)
        if datetime.now() > expires_at:
            return {'success': False, 'error': 'Token expirado'}
        
        return {
            'success': True,
            'token_id': token_id,
            'user_id': user_id,
            'email': email,
            'name': name,
            'expires_at': expires_at.isoformat()
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Erro interno: {str(e)}'}

def reset_password(token, new_password):
    """Redefinir senha usando token válido"""
    try:
        # Validar token primeiro
        validation = validate_reset_token(token)
        if not validation['success']:
            return validation
        
        user_id = validation['user_id']
        
        # Hash da nova senha
        import hashlib
        hashed_password = hashlib.sha256(new_password.encode()).hexdigest()
        
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão'}
        
        cursor = conn.cursor()
        
        # Atualizar senha do usuário
        cursor.execute("""
            UPDATE users 
            SET password = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (hashed_password, user_id))
        
        # Marcar token como usado
        cursor.execute("""
            UPDATE password_reset_tokens 
            SET used = TRUE
            WHERE token = %s
        """, (token,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'message': 'Senha redefinida com sucesso!',
            'user_name': validation['name']
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Erro interno: {str(e)}'}

def cleanup_expired_tokens():
    """Limpar tokens expirados (executar periodicamente)"""
    try:
        conn = get_db_connection()
        if not conn:
            return {'success': False, 'error': 'Erro de conexão'}
        
        cursor = conn.cursor()
        
        # Deletar tokens expirados
        cursor.execute("""
            DELETE FROM password_reset_tokens 
            WHERE expires_at < NOW() OR used = TRUE
        """)
        
        deleted_count = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'success': True,
            'deleted_tokens': deleted_count,
            'message': f'{deleted_count} tokens expirados removidos'
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Erro interno: {str(e)}'}

if __name__ == "__main__":
    print("🔧 Configurando sistema de recuperação de senha...")
    
    if create_password_reset_table():
        print("✅ Sistema de recuperação configurado!")
        
        # Teste básico
        print("\n🧪 Teste básico:")
        result = generate_reset_token("teste@exemplo.com")
        print(f"Resultado: {result}")
    else:
        print("❌ Falha na configuração")
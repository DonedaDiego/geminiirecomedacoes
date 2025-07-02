import os
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from database import get_db_connection

class EmailService:
    def __init__(self):
        self.smtp_server = "smtp.titan.email"
        self.smtp_port = 465
        self.from_email = os.environ.get('EMAIL_USER', 'contato@geminii.com.br')
        self.password = os.environ.get('EMAIL_PASSWORD', '#Geminii20')
        self.base_url = os.environ.get('BASE_URL', 'http://localhost:5000')
        
        # MODO TESTE - SEM SMTP
        self.test_mode = True

    def setup_tables(self):
        """🔧 Criar tabelas necessárias"""
        try:
            conn = get_db_connection()
            if not conn:
                return False
                
            cursor = conn.cursor()
            
            print("🔧 Configurando tabelas de email...")
            
            # 1. Adicionar campos na tabela users
            try:
                cursor.execute("""
                    ALTER TABLE users 
                    ADD COLUMN IF NOT EXISTS email_confirmed BOOLEAN DEFAULT TRUE,
                    ADD COLUMN IF NOT EXISTS email_confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                """)
                print("✅ Campos adicionados na tabela users")
            except Exception as e:
                print(f"⚠️ Erro ao adicionar campos users: {e}")
            
            # 2. Criar tabela email_confirmations
            try:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS email_confirmations (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        token VARCHAR(255) UNIQUE NOT NULL,
                        email VARCHAR(255) NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        confirmed BOOLEAN DEFAULT FALSE,
                        confirmed_at TIMESTAMP NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                print("✅ Tabela email_confirmations criada")
            except Exception as e:
                print(f"⚠️ Erro ao criar email_confirmations: {e}")
            
            # 3. Criar tabela password_reset_tokens
            try:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS password_reset_tokens (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        token VARCHAR(255) UNIQUE NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        used BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                print("✅ Tabela password_reset_tokens criada")
            except Exception as e:
                print(f"⚠️ Erro ao criar password_reset_tokens: {e}")
            
            # 4. Confirmar usuários existentes
            try:
                cursor.execute("""
                    UPDATE users 
                    SET email_confirmed = TRUE, email_confirmed_at = CURRENT_TIMESTAMP 
                    WHERE email_confirmed IS NULL OR email_confirmed = FALSE
                """)
                updated = cursor.rowcount
                print(f"✅ {updated} usuários marcados como confirmados")
            except Exception as e:
                print(f"⚠️ Erro ao confirmar usuários: {e}")
            
            # 5. Criar índices
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_confirmations_token ON email_confirmations(token)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_password_reset_token ON password_reset_tokens(token)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email_confirmed ON users(email_confirmed)")
                print("✅ Índices criados")
            except Exception as e:
                print(f"⚠️ Erro ao criar índices: {e}")
            
            conn.commit()
            cursor.close()
            conn.close()
            
            print("🎉 Configuração de tabelas concluída!")
            return True
            
        except Exception as e:
            print(f"❌ Erro na configuração de tabelas: {e}")
            return False

    def send_email(self, to_email, subject, html_content):
        """📧 Enviar email (modo teste ou real)"""
        try:
            if self.test_mode:
                print(f"\n📧 [MODO TESTE] Email simulado:")
                print(f"   Para: {to_email}")
                print(f"   Assunto: {subject}")
                print(f"   ✅ Email 'enviado' com sucesso")
                return True
            
            # MODO REAL (quando configurar SMTP)
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(html_content, 'html'))
            
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                server.login(self.from_email, self.password)
                server.send_message(msg)
            
            print(f"✅ Email enviado para {to_email}")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao enviar email: {e}")
            return False

    # ===== MÉTODOS DE CONFIRMAÇÃO DE EMAIL =====

    def generate_confirmation_token(self, user_id, email):
        """🔗 Gerar token de confirmação de email"""
        try:
            conn = get_db_connection()
            if not conn:
                return {'success': False, 'error': 'Erro de conexão'}
            
            cursor = conn.cursor()
            
            # Gerar token único
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
            
            # Salvar no banco
            cursor.execute("""
                INSERT INTO email_confirmations (user_id, token, email, expires_at)
                VALUES (%s, %s, %s, %s)
            """, (user_id, token, email, expires_at))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            # Mostrar link no console (modo teste)
            if self.test_mode:
                link = f"{self.base_url}/auth/confirm-email?token={token}"
                print(f"\n🔗 [LINK DE CONFIRMAÇÃO]:")
                print(f"   {link}")
                print(f"   ⏰ Expira em: 24 horas")
            
            return {'success': True, 'token': token}
            
        except Exception as e:
            print(f"❌ Erro ao gerar token de confirmação: {e}")
            return {'success': False, 'error': str(e)}

    def send_confirmation_email(self, user_name, email, token):
        """📧 Enviar email de confirmação"""
        link = f"{self.base_url}/auth/confirm-email?token={token}"
        
        subject = "Confirme seu email - Geminii Tech"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; }}
                .header {{ background: linear-gradient(135deg, #ba39af, #d946ef); padding: 30px; text-align: center; color: white; }}
                .content {{ padding: 30px; text-align: center; }}
                .button {{ display: inline-block; background: linear-gradient(135deg, #ba39af, #d946ef); color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; margin: 20px 0; }}
                .footer {{ background: #f8f8f8; padding: 20px; text-align: center; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚀 Geminii Tech</h1>
                    <p>Trading Automatizado</p>
                </div>
                
                <div class="content">
                    <h2>Olá, {user_name}!</h2>
                    <p>Bem-vindo à <strong>Geminii Tech</strong>!</p>
                    <p>Para completar seu cadastro, confirme seu email clicando no botão abaixo:</p>
                    
                    <a href="{link}" class="button">✅ Confirmar Email</a>
                    
                    <p><small>Ou acesse: <a href="{link}">{link}</a></small></p>
                    <p><strong>⚠️ Este link expira em 24 horas.</strong></p>
                </div>
                
                <div class="footer">
                    <p>© 2025 Geminii Tech - Trading Automatizado</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(email, subject, html_content)

    def confirm_email_token(self, token):
        """✅ Confirmar email com token - NOME CORRETO"""
        try:
            conn = get_db_connection()
            if not conn:
                return {'success': False, 'error': 'Erro de conexão'}
            
            cursor = conn.cursor()
            
            print(f"🔍 Confirmando token: {token[:20]}...")
            
            # Buscar token válido
            cursor.execute("""
                SELECT ec.id, ec.user_id, ec.email, ec.expires_at, u.name
                FROM email_confirmations ec
                JOIN users u ON u.id = ec.user_id
                WHERE ec.token = %s AND ec.confirmed = FALSE
            """, (token,))
            
            result = cursor.fetchone()
            
            if not result:
                cursor.close()
                conn.close()
                return {'success': False, 'error': 'Token inválido ou já usado'}
            
            confirmation_id, user_id, email, expires_at, user_name = result
            
            # Verificar expiração
            now = datetime.now(timezone.utc)
            if now > expires_at.replace(tzinfo=timezone.utc):
                cursor.close()
                conn.close()
                return {'success': False, 'error': 'Token expirado'}
            
            # CONFIRMAR EMAIL
            # 1. Marcar token como confirmado
            cursor.execute("""
                UPDATE email_confirmations 
                SET confirmed = TRUE, confirmed_at = %s
                WHERE id = %s
            """, (now, confirmation_id))
            
            # 2. Confirmar usuário
            cursor.execute("""
                UPDATE users 
                SET email_confirmed = TRUE, email_confirmed_at = %s
                WHERE id = %s
            """, (now, user_id))
            
            # 3. Verificar se atualizou
            cursor.execute("SELECT email_confirmed FROM users WHERE id = %s", (user_id,))
            is_confirmed = cursor.fetchone()[0]
            
            if not is_confirmed:
                cursor.close()
                conn.close()
                return {'success': False, 'error': 'Erro ao confirmar no banco'}
            
            conn.commit()
            cursor.close()
            conn.close()
            
            print(f"✅ Email confirmado: {user_name} ({email})")
            
            return {
                'success': True,
                'message': 'Email confirmado com sucesso!',
                'user_name': user_name,
                'email': email
            }
            
        except Exception as e:
            print(f"❌ Erro ao confirmar email: {e}")
            return {'success': False, 'error': str(e)}

    # ===== MÉTODOS DE RESET DE SENHA =====

    def generate_password_reset_token(self, email):
        """🔑 Gerar token de reset de senha"""
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
            
            user_id, user_name = user
            
            # Invalidar tokens antigos
            cursor.execute("""
                UPDATE password_reset_tokens 
                SET used = TRUE 
                WHERE user_id = %s AND used = FALSE
            """, (user_id,))
            
            # Gerar novo token
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
            
            # Salvar no banco
            cursor.execute("""
                INSERT INTO password_reset_tokens (user_id, token, expires_at)
                VALUES (%s, %s, %s)
            """, (user_id, token, expires_at))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            # Mostrar link no console (modo teste)
            if self.test_mode:
                link = f"{self.base_url}/reset-password?token={token}"
                print(f"\n🔑 [LINK DE RESET]:")
                print(f"   {link}")
                print(f"   ⏰ Expira em: 1 hora")
            
            return {
                'success': True,
                'token': token,
                'user_name': user_name,
                'user_email': email
            }
            
        except Exception as e:
            print(f"❌ Erro ao gerar token de reset: {e}")
            return {'success': False, 'error': str(e)}

    def send_password_reset_email(self, user_name, email, token):
        """📧 Enviar email de reset"""
        link = f"{self.base_url}/reset-password?token={token}"
        
        subject = "Redefinir senha - Geminii Tech"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; }}
                .header {{ background: linear-gradient(135deg, #ba39af, #d946ef); padding: 30px; text-align: center; color: white; }}
                .content {{ padding: 30px; text-align: center; }}
                .button {{ display: inline-block; background: linear-gradient(135deg, #ba39af, #d946ef); color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; margin: 20px 0; }}
                .footer {{ background: #f8f8f8; padding: 20px; text-align: center; font-size: 12px; color: #666; }}
                .warning {{ background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔐 Geminii Tech</h1>
                    <p>Redefinir Senha</p>
                </div>
                
                <div class="content">
                    <h2>Olá, {user_name}!</h2>
                    <p>Recebemos uma solicitação para redefinir sua senha.</p>
                    
                    <a href="{link}" class="button">🔑 Redefinir Senha</a>
                    
                    <div class="warning">
                        <p><strong>⚠️ Este link expira em 1 hora.</strong></p>
                    </div>
                    
                    <p><small>Se você não solicitou, ignore este email.</small></p>
                </div>
                
                <div class="footer">
                    <p>© 2025 Geminii Tech - Trading Automatizado</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(email, subject, html_content)

    def validate_password_reset_token(self, token):
        """🔍 Validar token de reset"""
        try:
            conn = get_db_connection()
            if not conn:
                return {'success': False, 'error': 'Erro de conexão'}
            
            cursor = conn.cursor()
            
            # Buscar token válido
            cursor.execute("""
                SELECT prt.user_id, u.email, u.name, prt.expires_at
                FROM password_reset_tokens prt
                JOIN users u ON u.id = prt.user_id
                WHERE prt.token = %s AND prt.used = FALSE
            """, (token,))
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if not result:
                return {'success': False, 'error': 'Token inválido ou já usado'}
            
            user_id, email, name, expires_at = result
            
            # Verificar expiração
            if datetime.now(timezone.utc) > expires_at.replace(tzinfo=timezone.utc):
                return {'success': False, 'error': 'Token expirado'}
            
            return {
                'success': True,
                'user_id': user_id,
                'email': email,
                'user_name': name,
                'expires_at': expires_at.isoformat()
            }
            
        except Exception as e:
            print(f"❌ Erro ao validar token: {e}")
            return {'success': False, 'error': str(e)}

    def reset_password_with_token(self, token, new_password):
        """🔐 Redefinir senha com token"""
        try:
            # Validar token
            token_data = self.validate_password_reset_token(token)
            if not token_data['success']:
                return token_data
            
            user_id = token_data['user_id']
            user_name = token_data['user_name']
            
            # Hash da nova senha
            hashed_password = hashlib.sha256(new_password.encode()).hexdigest()
            
            conn = get_db_connection()
            if not conn:
                return {'success': False, 'error': 'Erro de conexão'}
            
            cursor = conn.cursor()
            
            # Atualizar senha
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
            
            print(f"✅ Senha redefinida para: {user_name}")
            
            return {
                'success': True,
                'message': 'Senha redefinida com sucesso!',
                'user_name': user_name
            }
            
        except Exception as e:
            print(f"❌ Erro ao redefinir senha: {e}")
            return {'success': False, 'error': str(e)}

    def debug_user(self, email):
        """🔍 Debug de usuário"""
        try:
            conn = get_db_connection()
            if not conn:
                return
            
            cursor = conn.cursor()
            
            # Status do usuário
            cursor.execute("""
                SELECT id, name, email, email_confirmed, email_confirmed_at, created_at
                FROM users WHERE email = %s
            """, (email,))
            
            user = cursor.fetchone()
            if user:
                user_id, name, email, confirmed, confirmed_at, created_at = user
                print(f"\n🔍 DEBUG - {email}:")
                print(f"   ID: {user_id}")
                print(f"   Nome: {name}")
                print(f"   Confirmado: {confirmed}")
                print(f"   Confirmado em: {confirmed_at}")
                print(f"   Criado em: {created_at}")
            else:
                print(f"❌ Usuário não encontrado: {email}")
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"❌ Erro no debug: {e}")

# INSTÂNCIA GLOBAL
email_service = EmailService()

# FUNÇÃO DE SETUP
def setup_email_system():
    """🚀 Configurar sistema de email"""
    print("🚀 Configurando sistema de email...")
    
    if email_service.setup_tables():
        print("✅ Sistema de email configurado!")
        if email_service.test_mode:
            print("📧 MODO TESTE ativo - Links aparecerão no console")
        return True
    else:
        print("❌ Falha na configuração")
        return False

if __name__ == "__main__":
    setup_email_system()
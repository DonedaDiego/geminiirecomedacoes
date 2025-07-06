import os
import secrets
import hashlib
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone
from database import get_db_connection

class EmailService:
    def __init__(self):
        # 🔥 SMTP CORPORATIVO CONFIG (Titan)
        self.smtp_server = os.environ.get('SMTP_SERVER', 'smtp.titan.email')
        self.smtp_port = int(os.environ.get('SMTP_PORT', '465'))  # 465 para SSL (Titan)
        self.smtp_username = os.environ.get('EMAIL_USER', 'contato@geminii.com.br')
        self.smtp_password = os.environ.get('EMAIL_PASSWORD', '#Geminii20')
        self.from_email = os.environ.get('FROM_EMAIL', 'contato@geminii.com.br')
        self.from_name = 'Geminii Tech'
        self.base_url = os.environ.get('BASE_URL', 'https://app-geminii.railway.app')  
        
        # MODO TESTE - Para desenvolvimento sem SMTP
        self.test_mode = False  # Sempre usar SMTP real com suas credenciais
        
        if self.test_mode:
            print("⚠️ MODO TESTE ativo - Configure EMAIL_PASSWORD para emails reais")
        else:
            print(f"✅ SMTP ativo - Enviando de: {self.from_email}")
            print(f"📡 Servidor: {self.smtp_server}:{self.smtp_port}")
            print(f"🌐 Base URL: {self.base_url}")

    def send_email(self, to_email, subject, html_content):
        """📧 Enviar email via SMTP corporativo"""
        try:
            if self.test_mode:
                print(f"\n📧 [MODO TESTE] Email simulado:")
                print(f"   Para: {to_email}")
                print(f"   Assunto: {subject}")
                print(f"   De: {self.from_email}")
                print(f"   ✅ Email 'enviado' com sucesso")
                return True
            
            # 🔥 ENVIAR VIA SMTP CORPORATIVO
            print(f"📤 Enviando email via SMTP para {to_email}...")
            
            # Criar mensagem
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Adicionar conteúdo HTML
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Conectar e enviar
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                # SSL já está ativo no port 465, não precisa starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            print(f"✅ Email enviado via SMTP!")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            print(f"❌ Erro de autenticação SMTP: {e}")
            print(f"   Verifique SMTP_USERNAME e SMTP_PASSWORD")
            return False
        except smtplib.SMTPRecipientsRefused as e:
            print(f"❌ Destinatário recusado: {e}")
            return False
        except smtplib.SMTPServerDisconnected as e:
            print(f"❌ Servidor SMTP desconectado: {e}")
            return False
        except Exception as e:
            print(f"❌ Erro ao enviar email: {e}")
            return False

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
                    ADD COLUMN IF NOT EXISTS email_confirmed BOOLEAN DEFAULT FALSE,
                    ADD COLUMN IF NOT EXISTS email_confirmed_at TIMESTAMP DEFAULT NULL
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
            
            # 4. IMPORTANTE: Confirmar usuários EXISTENTES (admin, etc)
            try:
                cursor.execute("""
                    UPDATE users 
                    SET email_confirmed = TRUE, email_confirmed_at = CURRENT_TIMESTAMP 
                    WHERE email_confirmed IS NULL AND created_at < NOW() - INTERVAL '1 day'
                """)
                updated = cursor.rowcount
                print(f"✅ {updated} usuários antigos marcados como confirmados")
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
            
            # Mostrar link no console (sempre útil para debug)
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
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ 
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                    margin: 0; 
                    padding: 20px; 
                    background: #f8fafc;
                    line-height: 1.6;
                }}
                .container {{ 
                    max-width: 600px; 
                    margin: 0 auto; 
                    background: white; 
                    border-radius: 16px; 
                    overflow: hidden; 
                    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                }}
                .header {{ 
                    background: linear-gradient(135deg, #ba39af, #d946ef); 
                    padding: 40px 30px; 
                    text-align: center; 
                    color: white; 
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                    font-weight: 700;
                }}
                .header p {{
                    margin: 8px 0 0 0;
                    opacity: 0.9;
                    font-size: 16px;
                }}
                .content {{ 
                    padding: 40px 30px; 
                    text-align: center; 
                    color: #374151;
                }}
                .content h2 {{
                    color: #1f2937;
                    margin-bottom: 16px;
                    font-size: 24px;
                }}
                .button {{ 
                    display: inline-block; 
                    background: linear-gradient(135deg, #ba39af, #d946ef); 
                    color: white !important; 
                    padding: 16px 32px; 
                    text-decoration: none; 
                    border-radius: 8px; 
                    font-weight: 600; 
                    margin: 24px 0;
                    font-size: 16px;
                    transition: transform 0.2s;
                }}
                .button:hover {{
                    transform: translateY(-2px);
                }}
                .link-text {{
                    background: #f3f4f6;
                    padding: 12px;
                    border-radius: 6px;
                    word-break: break-all;
                    font-size: 12px;
                    color: #6b7280;
                    margin: 16px 0;
                }}
                .warning {{
                    background: #fef3c7;
                    border: 1px solid #f59e0b;
                    padding: 16px;
                    border-radius: 8px;
                    margin: 20px 0;
                    color: #92400e;
                }}
                .footer {{ 
                    background: #f9fafb; 
                    padding: 24px; 
                    text-align: center; 
                    font-size: 14px; 
                    color: #6b7280; 
                    border-top: 1px solid #e5e7eb;
                }}
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
                    <p>Bem-vindo à <strong>Geminii Tech</strong>! Estamos muito felizes em tê-lo conosco.</p>
                    <p>Para ativar sua conta e começar a usar nossa plataforma, confirme seu email clicando no botão abaixo:</p>
                    
                    <a href="{link}" class="button">✅ Confirmar Email</a>
                    
                    <div class="warning">
                        <strong>⏰ Importante:</strong> Este link expira em 24 horas por segurança.
                    </div>
                    
                    <p style="font-size: 14px; color: #6b7280;">
                        Se o botão não funcionar, copie e cole este link no seu navegador:
                    </p>
                    <div class="link-text">{link}</div>
                </div>
                
                <div class="footer">
                    <p>© 2025 Geminii Tech - Trading Automatizado</p>
                    <p>Se você não criou esta conta, pode ignorar este email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(email, subject, html_content)

    def confirm_email_token(self, token):
        """✅ Confirmar email com token"""
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
            
            # Mostrar link no console (sempre útil para debug)
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
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ 
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                    margin: 0; 
                    padding: 20px; 
                    background: #f8fafc;
                    line-height: 1.6;
                }}
                .container {{ 
                    max-width: 600px; 
                    margin: 0 auto; 
                    background: white; 
                    border-radius: 16px; 
                    overflow: hidden; 
                    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                }}
                .header {{ 
                    background: linear-gradient(135deg, #ef4444, #dc2626); 
                    padding: 40px 30px; 
                    text-align: center; 
                    color: white; 
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                    font-weight: 700;
                }}
                .header p {{
                    margin: 8px 0 0 0;
                    opacity: 0.9;
                    font-size: 16px;
                }}
                .content {{ 
                    padding: 40px 30px; 
                    text-align: center; 
                    color: #374151;
                }}
                .content h2 {{
                    color: #1f2937;
                    margin-bottom: 16px;
                    font-size: 24px;
                }}
                .button {{ 
                    display: inline-block; 
                    background: linear-gradient(135deg, #ef4444, #dc2626); 
                    color: white !important; 
                    padding: 16px 32px; 
                    text-decoration: none; 
                    border-radius: 8px; 
                    font-weight: 600; 
                    margin: 24px 0;
                    font-size: 16px;
                    transition: transform 0.2s;
                }}
                .button:hover {{
                    transform: translateY(-2px);
                }}
                .link-text {{
                    background: #f3f4f6;
                    padding: 12px;
                    border-radius: 6px;
                    word-break: break-all;
                    font-size: 12px;
                    color: #6b7280;
                    margin: 16px 0;
                }}
                .warning {{
                    background: #fef2f2;
                    border: 1px solid #ef4444;
                    padding: 16px;
                    border-radius: 8px;
                    margin: 20px 0;
                    color: #dc2626;
                }}
                .footer {{ 
                    background: #f9fafb; 
                    padding: 24px; 
                    text-align: center; 
                    font-size: 14px; 
                    color: #6b7280; 
                    border-top: 1px solid #e5e7eb;
                }}
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
                    <p>Recebemos uma solicitação para redefinir a senha da sua conta.</p>
                    <p>Se foi você quem solicitou, clique no botão abaixo para criar uma nova senha:</p>
                    
                    <a href="{link}" class="button">🔑 Redefinir Senha</a>
                    
                    <div class="warning">
                        <strong>⏰ Importante:</strong> Este link expira em 1 hora por segurança.
                    </div>
                    
                    <p style="font-size: 14px; color: #6b7280;">
                        Se o botão não funcionar, copie e cole este link no seu navegador:
                    </p>
                    <div class="link-text">{link}</div>
                    
                    <p style="font-size: 14px; color: #ef4444; margin-top: 24px;">
                        <strong>Se você não solicitou esta alteração, ignore este email.</strong> 
                        Sua senha permanecerá inalterada.
                    </p>
                </div>
                
                <div class="footer">
                    <p>© 2025 Geminii Tech - Trading Automatizado</p>
                    <p>Este é um email automático, não responda.</p>
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
        print("📧 MODO SMTP CORPORATIVO ativo - Emails via Titan")
        return True
    else:
        print("❌ Falha na configuração")
        return False

if __name__ == "__main__":
    setup_email_system()
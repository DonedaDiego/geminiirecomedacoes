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
        
                

    def send_email(self, to_email, subject, html_content):
        """📧 Enviar email via SMTP corporativo"""
        try:
            if self.test_mode:
                print(f"\n📧 [MODO TESTE] Email simulado:")
                print(f"   Para: {to_email}")
                print(f"   Assunto: {subject}")
                print(f"   Conteúdo: {len(html_content)} caracteres")
                return True
        
            # NOVO: Validar campos obrigatórios
            if not to_email or not subject or not html_content:
                print(f"❌ Email inválido: campos obrigatórios em branco")
                return False
                
            # Criar mensagem
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Adicionar conteúdo HTML
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # NOVO: Logs mais detalhados
            print(f"📧 Enviando email para: {to_email}")
            print(f"   Assunto: {subject}")
            
            # Conectar e enviar
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            print(f"✅ Email enviado com sucesso!")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            print(f"❌ Erro de autenticação SMTP: {e}")
            return False
        except smtplib.SMTPRecipientsRefused as e:
            print(f"❌ Destinatário recusado: {e}")
            return False
        except smtplib.SMTPServerDisconnected as e:
            print(f"❌ Servidor desconectado: {e}")
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

   # ===== Emails lembre trial e pagamento =====

    def send_trial_welcome_email(self, user_name, email):
        """🎉 Enviar email de boas-vindas ao trial"""
        subject = "🎉 Bem-vindo ao seu Trial Premium!"
        
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
                .content {{ 
                    padding: 40px 30px; 
                    text-align: center; 
                    color: #374151;
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
                }}
                .feature-list {{
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                    text-align: left;
                }}
                .feature-list li {{
                    margin-bottom: 8px;
                    color: #555;
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
                    <h1>🎉 Trial Premium Ativado!</h1>
                    <p>15 dias de acesso completo</p>
                </div>
                
                <div class="content">
                    <h2>Olá, {user_name}!</h2>
                    <p style="font-size: 18px;">🎊 <strong>Parabéns!</strong> Você ganhou <strong>15 dias</strong> de acesso Premium GRATUITO!</p>
                    
                    <div class="feature-list">
                        <h3 style="color: #ba39af; margin-top: 0;">🚀 Durante o trial você pode:</h3>
                        <ul>
                            <li>✅ Acessar todos os recursos Premium</li>
                            <li>✅ Usar ferramentas avançadas de trading</li>
                            <li>✅ Gerar relatórios completos</li>
                            <li>✅ Suporte prioritário</li>
                            <li>✅ Acesso ilimitado à plataforma</li>
                        </ul>
                    </div>
                    
                    <a href="{self.base_url}/dashboard" class="button">🚀 Acessar Dashboard</a>
                    
                    <p style="font-size: 14px; color: #6b7280; margin-top: 24px;">
                        Aproveite ao máximo seus 15 dias de trial!
                    </p>
                </div>
                
                <div class="footer">
                    <p>© 2025 Geminii Tech - Trading Automatizado</p>
                    <p>Seu trial expira em 15 dias. Não perca tempo!</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(email, subject, html_content)

    def send_trial_reminder_email(self, user_name, email, days_remaining):
        """⏰ Enviar lembrete de trial"""
        if days_remaining <= 1:
            subject = "🔥 ÚLTIMO DIA do seu Trial Premium!"
            urgency = "🔥 ÚLTIMO DIA!"
            color = "#ef4444"
        elif days_remaining <= 3:
            subject = f"🚨 Apenas {days_remaining} dias restantes do Trial!"
            urgency = f"🚨 Apenas {days_remaining} dias!"
            color = "#f59e0b"
        else:
            subject = f"⏰ {days_remaining} dias restantes do seu Trial Premium"
            urgency = f"⏰ {days_remaining} dias restantes"
            color = "#ba39af"
        
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
                    background: linear-gradient(135deg, {color}, {color}); 
                    padding: 40px 30px; 
                    text-align: center; 
                    color: white; 
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                    font-weight: 700;
                }}
                .content {{ 
                    padding: 40px 30px; 
                    text-align: center; 
                    color: #374151;
                }}
                .button {{ 
                    display: inline-block; 
                    background: linear-gradient(135deg, {color}, {color}); 
                    color: white !important; 
                    padding: 16px 32px; 
                    text-decoration: none; 
                    border-radius: 8px; 
                    font-weight: 600; 
                    margin: 24px 0;
                    font-size: 16px;
                }}
                .countdown {{
                    background: #fef3c7;
                    border: 2px solid #f59e0b;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                    color: #92400e;
                    font-size: 18px;
                    font-weight: bold;
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
                    <h1>{urgency}</h1>
                    <p>Seu trial Premium está acabando</p>
                </div>
                
                <div class="content">
                    <h2>Olá, {user_name}!</h2>
                    <p>Seu trial Premium expira em <strong>{days_remaining} {'dia' if days_remaining == 1 else 'dias'}</strong>!</p>
                    
                    <div class="countdown">
                        ⏰ {days_remaining} {'dia' if days_remaining == 1 else 'dias'} restantes
                    </div>
                    
                    <p>Não perca o acesso a todos os recursos Premium:</p>
                    <ul style="text-align: left; max-width: 300px; margin: 0 auto;">
                        <li>🚀 Ferramentas avançadas de trading</li>
                        <li>📊 Relatórios detalhados</li>
                        <li>🎯 Suporte prioritário</li>
                        <li>🔓 Acesso ilimitado</li>
                    </ul>
                    
                    <a href="{self.base_url}/upgrade" class="button">💎 Fazer Upgrade Agora</a>
                    
                    <p style="font-size: 14px; color: #6b7280; margin-top: 24px;">
                        Continue aproveitando todos os recursos Premium!
                    </p>
                </div>
                
                <div class="footer">
                    <p>© 2025 Geminii Tech - Trading Automatizado</p>
                    <p>Não perca a oportunidade de continuar Premium!</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(email, subject, html_content)
    
    def send_trial_expired_email(self, user_name, email):
        """💡 Enviar email de trial expirado"""
        try:
            subject = "💡 Seu Trial Premium expirou"
            
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
                        background: linear-gradient(135deg, #6b7280, #4b5563); 
                        padding: 40px 30px; 
                        text-align: center; 
                        color: white; 
                    }}
                    .header h1 {{
                        margin: 0;
                        font-size: 28px;
                        font-weight: 700;
                    }}
                    .content {{ 
                        padding: 40px 30px; 
                        text-align: center; 
                        color: #374151;
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
                    }}
                    .expired-box {{
                        background: #fef2f2;
                        border: 2px solid #ef4444;
                        padding: 20px;
                        border-radius: 8px;
                        margin: 20px 0;
                        color: #dc2626;
                    }}
                    .basic-features {{
                        background: #f0f9ff;
                        border: 1px solid #0ea5e9;
                        padding: 20px;
                        border-radius: 8px;
                        margin: 20px 0;
                        color: #0369a1;
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
                        <h1>💡 Trial Expirado</h1>
                        <p>Mas você ainda pode acessar recursos básicos</p>
                    </div>
                    
                    <div class="content">
                        <h2>Olá, {user_name}!</h2>
                        <p>Seu trial Premium de 15 dias expirou.</p>
                        
                        <div class="expired-box">
                            <strong>⏰ Trial Premium expirado</strong><br>
                            Upgrade para continuar com acesso total
                        </div>
                        
                        <div class="basic-features">
                            <strong>✅ Você ainda pode acessar:</strong>
                            <ul style="text-align: left; margin-top: 10px;">
                                <li>📊 Recursos básicos</li>
                                <li>📈 Gráficos simples</li>
                                <li>📧 Suporte por email</li>
                            </ul>
                        </div>
                        
                        <p>Que tal fazer upgrade e ter acesso completo?</p>
                        <p><strong>Com Premium você tem:</strong></p>
                        <ul style="text-align: left; max-width: 300px; margin: 0 auto;">
                            <li>🚀 Ferramentas avançadas</li>
                            <li>📊 Relatórios completos</li>
                            <li>🎯 Suporte prioritário</li>
                            <li>🔓 Acesso ilimitado</li>
                        </ul>
                        
                        <a href="{self.base_url}/upgrade" class="button">💎 Fazer Upgrade</a>
                        
                        <p style="font-size: 14px; color: #6b7280; margin-top: 24px;">
                            Continue sua jornada conosco!
                        </p>
                    </div>
                    
                    <div class="footer">
                        <p>© 2025 Geminii Tech - Trading Automatizado</p>
                        <p>Obrigado por experimentar nosso trial!</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            print(f"📧 Enviando email de trial expirado para: {email}")
            return self.send_email(email, subject, html_content)
            
        except Exception as e:
            print(f"❌ Erro ao enviar email de trial expirado: {e}")
            return False
        
     # ===== MÉTODOS DE PAYMENT =====

    def send_payment_success_email(self, user_name, email, plan_name, amount=None):
        """✅ Enviar email de pagamento confirmado"""
        subject = f"✅ Pagamento confirmado - {plan_name}"
        
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
                    background: linear-gradient(135deg, #10b981, #059669); 
                    padding: 40px 30px; 
                    text-align: center; 
                    color: white; 
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                    font-weight: 700;
                }}
                .content {{ 
                    padding: 40px 30px; 
                    text-align: center; 
                    color: #374151;
                }}
                .success-box {{
                    background: #ecfdf5;
                    border: 2px solid #10b981;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                    color: #065f46;
                }}
                .plan-details {{
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                    text-align: left;
                }}
                .button {{ 
                    display: inline-block; 
                    background: linear-gradient(135deg, #10b981, #059669); 
                    color: white !important; 
                    padding: 16px 32px; 
                    text-decoration: none; 
                    border-radius: 8px; 
                    font-weight: 600; 
                    margin: 24px 0;
                    font-size: 16px;
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
                    <h1>✅ Pagamento Confirmado!</h1>
                    <p>Bem-vindo ao {plan_name}</p>
                </div>
                
                <div class="content">
                    <h2>Olá, {user_name}!</h2>
                    <p>Seu pagamento foi <strong>confirmado com sucesso</strong>!</p>
                    
                    <div class="success-box">
                        <strong>🎉 Pagamento Aprovado</strong><br>
                        Agora você tem acesso total ao plano {plan_name}
                    </div>
                    
                    <div class="plan-details">
                        <h3 style="color: #10b981; margin-top: 0;">📦 Detalhes da Assinatura:</h3>
                        <p><strong>Plano:</strong> {plan_name}</p>
                        {'<p><strong>Valor:</strong> ' + str(amount) + '</p>' if amount else ''}
                        <p><strong>Status:</strong> Ativo</p>
                        <p><strong>Renovação:</strong> Automática</p>
                    </div>
                    
                    <p>Agora você pode aproveitar todos os recursos Premium:</p>
                    <ul style="text-align: left; max-width: 300px; margin: 0 auto;">
                        <li>🚀 Ferramentas avançadas</li>
                        <li>📊 Relatórios completos</li>
                        <li>🎯 Suporte prioritário</li>
                        <li>🔓 Acesso ilimitado</li>
                    </ul>
                    
                    <a href="{self.base_url}/dashboard" class="button">🚀 Acessar Dashboard</a>
                    
                    <p style="font-size: 14px; color: #6b7280; margin-top: 24px;">
                        Obrigado por escolher a Geminii Tech!
                    </p>
                </div>
                
                <div class="footer">
                    <p>© 2025 Geminii Tech - Trading Automatizado</p>
                    <p>Precisa de ajuda? Entre em contato conosco!</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(email, subject, html_content)

    def send_payment_reminder_email(self, user_name, email, plan_name, days_until_renewal, amount=None):
        """📅 Enviar lembrete de renovação"""
        if days_until_renewal <= 1:
            subject = f"🔥 Renovação do {plan_name} AMANHÃ!"
            urgency = "🔥 AMANHÃ!"
            color = "#ef4444"
        elif days_until_renewal <= 3:
            subject = f"⚠️ Renovação do {plan_name} em {days_until_renewal} dias"
            urgency = f"⚠️ Em {days_until_renewal} dias"
            color = "#f59e0b"
        else:
            subject = f"📅 Renovação do {plan_name} em {days_until_renewal} dias"
            urgency = f"📅 Em {days_until_renewal} dias"
            color = "#0ea5e9"
        
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
                    background: linear-gradient(135deg, {color}, {color}); 
                    padding: 40px 30px; 
                    text-align: center; 
                    color: white; 
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 28px;
                    font-weight: 700;
                }}
                .content {{ 
                    padding: 40px 30px; 
                    text-align: center; 
                    color: #374151;
                }}
                .renewal-box {{
                    background: #fef3c7;
                    border: 2px solid #f59e0b;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                    color: #92400e;
                }}
                .plan-details {{
                    background: #f8f9fa;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                    text-align: left;
                }}
                .button {{ 
                    display: inline-block; 
                    background: linear-gradient(135deg, {color}, {color}); 
                    color: white !important; 
                    padding: 16px 32px; 
                    text-decoration: none; 
                    border-radius: 8px; 
                    font-weight: 600; 
                    margin: 24px 0;
                    font-size: 16px;
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
                    <h1>Renovação {urgency}</h1>
                    <p>Sua assinatura {plan_name}</p>
                </div>
                
                <div class="content">
                    <h2>Olá, {user_name}!</h2>
                    <p>Sua assinatura <strong>{plan_name}</strong> será renovada em <strong>{days_until_renewal} {'dia' if days_until_renewal == 1 else 'dias'}</strong>.</p>
                    
                    <div class="renewal-box">
                        <strong>📅 Renovação em {days_until_renewal} {'dia' if days_until_renewal == 1 else 'dias'}</strong><br>
                        Tudo certo para a renovação automática!
                    </div>
                    
                    <div class="plan-details">
                        <h3 style="color: {color}; margin-top: 0;">📦 Detalhes da Renovação:</h3>
                        <p><strong>Plano:</strong> {plan_name}</p>
                        {'<p><strong>Valor:</strong> ' + str(amount) + '</p>' if amount else ''}
                        <p><strong>Renovação:</strong> Automática</p>
                        <p><strong>Método:</strong> Cartão cadastrado</p>
                    </div>
                    
                    <p>Continuará aproveitando todos os recursos:</p>
                    <ul style="text-align: left; max-width: 300px; margin: 0 auto;">
                        <li>🚀 Ferramentas avançadas</li>
                        <li>📊 Relatórios completos</li>
                        <li>🎯 Suporte prioritário</li>
                        <li>🔓 Acesso ilimitado</li>
                    </ul>
                    
                    <a href="{self.base_url}/account" class="button">⚙️ Gerenciar Assinatura</a>
                    
                    <p style="font-size: 14px; color: #6b7280; margin-top: 24px;">
                        Precisa alterar algo? Acesse sua conta!
                    </p>
                </div>
                
                <div class="footer">
                    <p>© 2025 Geminii Tech - Trading Automatizado</p>
                    <p>Renovação automática em {days_until_renewal} {'dia' if days_until_renewal == 1 else 'dias'}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(email, subject, html_content)
    
    def send_payment_expired_email(self, user_name, email, plan_name):
        """💡 Enviar email de assinatura expirada"""
        subject = f"💡 Sua assinatura {plan_name} expirou"
        
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
                .content {{ 
                    padding: 40px 30px; 
                    text-align: center; 
                    color: #374151;
                }}
                .expired-box {{
                    background: #fef2f2;
                    border: 2px solid #ef4444;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                    color: #dc2626;
                }}
                .basic-features {{
                    background: #f0f9ff;
                    border: 1px solid #0ea5e9;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                    color: #0369a1;
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
                    <h1>💡 Assinatura Expirada</h1>
                    <p>Renove para continuar Premium</p>
                </div>
                
                <div class="content">
                    <h2>Olá, {user_name}!</h2>
                    <p>Sua assinatura <strong>{plan_name}</strong> expirou.</p>
                    
                    <div class="expired-box">
                        <strong>⏰ Assinatura {plan_name} expirada</strong><br>
                        Renove agora para continuar com acesso total
                    </div>
                    
                    <div class="basic-features">
                        <strong>✅ Você ainda pode acessar:</strong>
                        <ul style="text-align: left; margin-top: 10px;">
                            <li>📊 Recursos básicos</li>
                            <li>📈 Gráficos simples</li>
                            <li>📧 Suporte por email</li>
                        </ul>
                    </div>
                    
                    <p>Renove sua assinatura e volte a ter acesso completo:</p>
                    <ul style="text-align: left; max-width: 300px; margin: 0 auto;">
                        <li>🚀 Ferramentas avançadas</li>
                        <li>📊 Relatórios completos</li>
                        <li>🎯 Suporte prioritário</li>
                        <li>🔓 Acesso ilimitado</li>
                    </ul>
                    
                    <a href="{self.base_url}/renew" class="button">🔄 Renovar Assinatura</a>
                    
                    <p style="font-size: 14px; color: #6b7280; margin-top: 24px;">
                        Sentimos sua falta! Volte para o Premium!
                    </p>
                </div>
                
                <div class="footer">
                    <p>© 2025 Geminii Tech - Trading Automatizado</p>
                    <p>Renove e continue aproveitando todos os recursos!</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(email, subject, html_content)

    def send_payment_failed_email(self, user_name, email, plan_name, retry_date=None):
        """❌ Enviar email de falha no pagamento"""
        subject = f"❌ Problema com pagamento - {plan_name}"
        
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
                .content {{ 
                    padding: 40px 30px; 
                    text-align: center; 
                    color: #374151;
                }}
                .failed-box {{
                    background: #fef2f2;
                    border: 2px solid #ef4444;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                    color: #dc2626;
                }}
                .action-box {{
                    background: #fef3c7;
                    border: 1px solid #f59e0b;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 20px 0;
                    color: #92400e;
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
                    <h1>❌ Falha no Pagamento</h1>
                    <p>Ação necessária para {plan_name}</p>
                </div>
                
                <div class="content">
                    <h2>Olá, {user_name}!</h2>
                    <p>Houve um problema com o pagamento da sua assinatura <strong>{plan_name}</strong>.</p>
                    
                    <div class="failed-box">
                        <strong>❌ Pagamento não processado</strong><br>
                        Verifique seus dados de pagamento
                    </div>
                    
                    <div class="action-box">
                        <strong>🔧 O que fazer:</strong>
                        <ul style="text-align: left; margin-top: 10px;">
                            <li>Verifique o saldo do cartão</li>
                            <li>Confirme os dados de pagamento</li>
                            <li>Atualize o método de pagamento</li>
                            <li>Entre em contato se persistir</li>
                        </ul>
                    </div>
                    
                    <p>Resolva agora para não perder o acesso Premium:</p>
                    <ul style="text-align: left; max-width: 300px; margin: 0 auto;">
                        <li>🚀 Ferramentas avançadas</li>
                        <li>📊 Relatórios completos</li>
                        <li>🎯 Suporte prioritário</li>
                        <li>🔓 Acesso ilimitado</li>
                    </ul>
                    
                    <a href="{self.base_url}/payment/update" class="button">🔧 Atualizar Pagamento</a>
                    
                    {'<p style="font-size: 14px; color: #92400e; margin-top: 24px;"><strong>Próxima tentativa: ' + str(retry_date) + '</strong></p>' if retry_date else ''}
                </div>
                
                <div class="footer">
                    <p>© 2025 Geminii Tech - Trading Automatizado</p>
                    <p>Precisa de ajuda? Entre em contato conosco!</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(email, subject, html_content)
    
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
import os
import secrets
import hashlib
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
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
        
        
        self.test_mode = False  # Sempre usar SMTP real com suas credenciais

    def send_email(self, to_email, subject, html_content, text_content=None):
        """📧 Enviar email via SMTP corporativo COM MELHORIAS ANTI-SPAM"""
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
                
            # 🔥 CRIAR MENSAGEM COM HEADERS ANTI-SPAM
            msg = MIMEMultipart('alternative')
            
            # 🔥 HEADERS ANTI-SPAM MELHORADOS
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            msg['Reply-To'] = self.from_email
            msg['Return-Path'] = self.from_email
            
            # 🔥 HEADERS ADICIONAIS PARA EVITAR SPAM
            msg['Message-ID'] = f"<{secrets.token_urlsafe(16)}@geminii.com.br>"
            msg['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
            msg['X-Mailer'] = 'Geminii Tech Notification System'
            msg['X-Priority'] = '3'
            msg['X-MSMail-Priority'] = 'Normal'
            msg['Importance'] = 'Normal'
            
            # 🔥 HEADERS ESPECÍFICOS PARA TITAN/HOSTINGER
            msg['List-Unsubscribe'] = f'<mailto:{self.from_email}?subject=Unsubscribe>'
            msg['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'
            
            # 🔥 VERSÃO TEXTO SIMPLES (OBRIGATÓRIA PARA ANTI-SPAM)
            if not text_content:
                # Gerar versão texto a partir do HTML
                text_content = self.html_to_text(html_content)
            
            text_part = MIMEText(text_content, 'plain', 'utf-8')
            html_part = MIMEText(html_content, 'html', 'utf-8')
            
            # Adicionar ambas as versões
            msg.attach(text_part)
            msg.attach(html_part)
            
            # NOVO: Logs mais detalhados
            print(f"📧 Enviando email para: {to_email}")
            print(f"   Assunto: {subject}")
            print(f"   Tamanho HTML: {len(html_content)} chars")
            print(f"   Tamanho Texto: {len(text_content)} chars")
            
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

    def html_to_text(self, html_content):
        """🔧 Converter HTML para texto simples (anti-spam)"""
        try:
            import re
            
            # Remover tags HTML
            text = re.sub(r'<[^>]+>', '', html_content)
            
            # Converter entidades HTML
            text = text.replace('&nbsp;', ' ')
            text = text.replace('&amp;', '&')
            text = text.replace('&lt;', '<')
            text = text.replace('&gt;', '>')
            text = text.replace('&quot;', '"')
            
            # Limpar espaços extras
            text = re.sub(r'\s+', ' ', text)
            text = text.strip()
            
            return text
            
        except Exception as e:
            print(f"❌ Erro ao converter HTML para texto: {e}")
            return "Versão texto do email não disponível."

    def create_professional_email_template(self, content_data):
        """🎨 Criar template de email profissional anti-spam"""
        
        title = content_data.get('title', 'Geminii Tech')
        subtitle = content_data.get('subtitle', 'Trading Automatizado')
        main_message = content_data.get('main_message', '')
        user_name = content_data.get('user_name', '')
        urgency_color = content_data.get('urgency_color', '#ba39af')
        button_text = content_data.get('button_text', 'Acessar')
        button_url = content_data.get('button_url', self.base_url)
        details = content_data.get('details', [])
        warning_message = content_data.get('warning_message', '')
        footer_message = content_data.get('footer_message', '')
        
        # 🔥 TEMPLATE HTML PROFISSIONAL E ANTI-SPAM
        html_template = f"""
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="pt-BR">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="x-apple-disable-message-reformatting" />
    <title>{title}</title>
    <!--[if mso]>
    <noscript>
        <xml>
            <o:OfficeDocumentSettings>
                <o:PixelsPerInch>96</o:PixelsPerInch>
            </o:OfficeDocumentSettings>
        </xml>
    </noscript>
    <![endif]-->
    <style type="text/css">
        /* 🔥 CSS ANTI-SPAM OTIMIZADO */
        @media screen and (max-width: 600px) {{
            .container {{ width: 100% !important; }}
            .content {{ padding: 20px !important; }}
        }}
        
        .preheader {{ display: none !important; visibility: hidden; opacity: 0; color: transparent; height: 0; width: 0; }}
        
        body {{ 
            margin: 0; 
            padding: 0; 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, Arial, sans-serif; 
            background-color: #f8fafc;
            line-height: 1.6;
            -webkit-text-size-adjust: 100%;
            -ms-text-size-adjust: 100%;
        }}
        
        table {{ border-collapse: collapse; mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
        img {{ border: 0; height: auto; line-height: 100%; outline: none; text-decoration: none; }}
        
        .container {{ 
            max-width: 600px; 
            margin: 0 auto; 
            background-color: #ffffff; 
            border-radius: 8px;
            overflow: hidden;
        }}
        
        .header {{ 
            background: linear-gradient(135deg, {urgency_color}, {urgency_color}); 
            padding: 30px; 
            text-align: center; 
        }}
        
        .header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 600;
            color: #ffffff;
        }}
        
        .header p {{
            margin: 8px 0 0 0;
            color: #ffffff;
            opacity: 0.9;
            font-size: 14px;
        }}
        
        .content {{ 
            padding: 40px 30px; 
            background-color: #ffffff;
        }}
        
        .button {{ 
            display: inline-block; 
            background: linear-gradient(135deg, {urgency_color}, {urgency_color}); 
            color: #ffffff !important; 
            padding: 14px 28px; 
            text-decoration: none; 
            border-radius: 6px; 
            font-weight: 600; 
            margin: 20px 0;
            font-size: 16px;
            border: none;
        }}
        
        .details-box {{
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 6px;
            margin: 20px 0;
            border-left: 4px solid {urgency_color};
        }}
        
        .warning-box {{
            background-color: #fef3c7;
            border: 1px solid #f59e0b;
            padding: 16px;
            border-radius: 6px;
            margin: 20px 0;
            color: #92400e;
        }}
        
        .footer {{ 
            background-color: #f1f5f9; 
            padding: 20px; 
            text-align: center; 
            font-size: 12px; 
            color: #64748b;
        }}
    </style>
</head>
<body>
    <!-- 🔥 PREHEADER INVISÍVEL PARA PREVIEW -->
    <div class="preheader">
        {main_message[:50]}...
    </div>
    
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
        <tr>
            <td align="center" style="padding: 20px;">
                <div class="container">
                    <!-- Header -->
                    <div class="header">
                        <h1>{title}</h1>
                        <p>{subtitle}</p>
                    </div>
                    
                    <!-- Content -->
                    <div class="content">
                        <h2 style="color: #1f2937; margin-bottom: 16px; font-size: 20px;">
                            Olá, {user_name}!
                        </h2>
                        
                        <p style="color: #374151; margin-bottom: 20px; font-size: 16px;">
                            {main_message}
                        </p>
                        
                        {f'''
                        <div class="details-box">
                            <h3 style="color: #1f2937; margin: 0 0 12px 0; font-size: 16px;">
                                📋 Detalhes:
                            </h3>
                            {"".join([f"<p style='margin: 4px 0; color: #4b5563;'><strong>{detail['label']}:</strong> {detail['value']}</p>" for detail in details])}
                        </div>
                        ''' if details else ''}
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{button_url}" class="button">
                                {button_text}
                            </a>
                        </div>
                        
                        {f'''
                        <div class="warning-box">
                            <strong>⚠️ Importante:</strong> {warning_message}
                        </div>
                        ''' if warning_message else ''}
                        
                        <div style="margin-top: 30px; text-align: center;">
                            <p style="color: #64748b; font-size: 14px; margin: 0;">
                                Dúvidas? Entre em contato: 
                                <a href="mailto:contato@geminii.com.br" style="color: {urgency_color};">contato@geminii.com.br</a>
                            </p>
                        </div>
                    </div>
                    
                    <!-- Footer -->
                    <div class="footer">
                        <p style="margin: 0;">© 2025 Geminii Tech - Trading Automatizado</p>
                        <p style="margin: 8px 0 0 0;">{footer_message}</p>
                        <p style="margin: 8px 0 0 0;">
                            <a href="mailto:contato@geminii.com.br?subject=Cancelar emails" style="color: #64748b; text-decoration: underline;">
                                Cancelar emails
                            </a>
                        </p>
                    </div>
                </div>
            </td>
        </tr>
    </table>
</body>
</html>
        """
        
        return html_template.strip()

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
        """📧 Enviar email de confirmação COM TEMPLATE ANTI-SPAM"""
        
        # 🔥 USAR NOVO TEMPLATE ANTI-SPAM
        content_data = {
            'title': 'Confirme seu Email',
            'subtitle': 'Geminii Tech - Trading Automatizado',
            'main_message': f'Bem-vindo à Geminii Tech! Para ativar sua conta e começar a usar nossa plataforma, confirme seu email clicando no botão abaixo.',
            'user_name': user_name,
            'urgency_color': '#10b981',
            'button_text': '✅ Confirmar Email',
            'button_url': f"{self.base_url}/auth/confirm-email?token={token}",
            'details': [
                {'label': 'Email', 'value': email},
                {'label': 'Validade', 'value': '24 horas'}
            ],
            'warning_message': 'Este link expira em 24 horas por segurança.',
            'footer_message': 'Se você não criou esta conta, pode ignorar este email.'
        }
        
        html_content = self.create_professional_email_template(content_data)
        
        # Versão texto
        text_content = f"""
Geminii Tech - Confirme seu Email

Olá, {user_name}!

Bem-vindo à Geminii Tech! Para ativar sua conta, confirme seu email clicando no link abaixo:

{self.base_url}/auth/confirm-email?token={token}

Este link expira em 24 horas por segurança.

Se você não criou esta conta, pode ignorar este email.

Dúvidas? Entre em contato: contato@geminii.com.br

© 2025 Geminii Tech - Trading Automatizado
        """
        
        return self.send_email(email, "Confirme seu email - Geminii Tech", html_content, text_content)

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
        """📧 Enviar email de reset COM TEMPLATE ANTI-SPAM"""
        
        # 🔥 USAR NOVO TEMPLATE ANTI-SPAM
        content_data = {
            'title': 'Redefinir Senha',
            'subtitle': 'Geminii Tech - Trading Automatizado',
            'main_message': 'Recebemos uma solicitação para redefinir a senha da sua conta. Se foi você quem solicitou, clique no botão abaixo para criar uma nova senha.',
            'user_name': user_name,
            'urgency_color': '#ef4444',
            'button_text': '🔑 Redefinir Senha',
            'button_url': f"{self.base_url}/reset-password?token={token}",
            'details': [
                {'label': 'Email', 'value': email},
                {'label': 'Validade', 'value': '1 hora'}
            ],
            'warning_message': 'Este link expira em 1 hora por segurança.',
            'footer_message': 'Se você não solicitou esta alteração, ignore este email.'
        }
        
        html_content = self.create_professional_email_template(content_data)
        
        # Versão texto
        text_content = f"""
Geminii Tech - Redefinir Senha

Olá, {user_name}!

Recebemos uma solicitação para redefinir a senha da sua conta.

Para criar uma nova senha, clique no link abaixo:
{self.base_url}/reset-password?token={token}

Este link expira em 1 hora por segurança.

Se você não solicitou esta alteração, ignore este email.

Dúvidas? Entre em contato: contato@geminii.com.br

© 2025 Geminii Tech - Trading Automatizado
        """
        
        return self.send_email(email, "Redefinir senha - Geminii Tech", html_content, text_content)

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

    # ===== EMAILS DE TRIAL COM TEMPLATE ANTI-SPAM =====

    def send_trial_welcome_email(self, user_name, email):
        """🎉 Enviar email de boas-vindas ao trial COM TEMPLATE ANTI-SPAM"""
        
        content_data = {
            'title': 'Trial Premium Ativado!',
            'subtitle': '15 dias de acesso completo',
            'main_message': 'Parabéns! Você ganhou 15 dias de acesso Premium GRATUITO! Aproveite ao máximo todos os recursos disponíveis.',
            'user_name': user_name,
            'urgency_color': '#10b981',
            'button_text': '🚀 Acessar Dashboard',
            'button_url': f"{self.base_url}/dashboard",
            'details': [
                {'label': 'Tipo', 'value': 'Trial Premium'},
                {'label': 'Duração', 'value': '15 dias'},
                {'label': 'Acesso', 'value': 'Recursos completos'}
            ],
            'warning_message': 'Aproveite todos os recursos Premium durante seu trial de 15 dias.',
            'footer_message': 'Seu trial expira em 15 dias. Não perca tempo!'
        }
        
        html_content = self.create_professional_email_template(content_data)
        
        text_content = f"""
Geminii Tech - Trial Premium Ativado!

Olá, {user_name}!

Parabéns! Você ganhou 15 dias de acesso Premium GRATUITO!

Durante o trial você pode:
- Acessar todos os recursos Premium
- Usar ferramentas avançadas de trading
- Gerar relatórios completos
- Suporte prioritário
- Acesso ilimitado à plataforma

Acesse agora: {self.base_url}/dashboard

Aproveite ao máximo seus 15 dias de trial!

© 2025 Geminii Tech - Trading Automatizado
        """
        
        return self.send_email(email, "🎉 Trial Premium Ativado - Geminii Tech", html_content, text_content)

    def send_trial_reminder_email(self, user_name, email, days_remaining):
        """⏰ Enviar lembrete de trial COM TEMPLATE ANTI-SPAM"""
        
        if days_remaining <= 1:
            urgency_color = "#ef4444"
            urgency_text = "ÚLTIMO DIA"
        elif days_remaining <= 3:
            urgency_color = "#f59e0b"
            urgency_text = f"Apenas {days_remaining} dias"
        else:
            urgency_color = "#ba39af"
            urgency_text = f"{days_remaining} dias restantes"
        
        content_data = {
            'title': f'Trial: {urgency_text}',
            'subtitle': 'Seu trial Premium está acabando',
            'main_message': f'Seu trial Premium expira em {days_remaining} {"dia" if days_remaining == 1 else "dias"}! Não perca o acesso a todos os recursos Premium.',
            'user_name': user_name,
            'urgency_color': urgency_color,
            'button_text': '💎 Fazer Upgrade Agora',
            'button_url': f"{self.base_url}/planos",
            'details': [
                {'label': 'Dias restantes', 'value': f"{days_remaining} {'dia' if days_remaining == 1 else 'dias'}"},
                {'label': 'Status', 'value': 'Trial Premium'},
                {'label': 'Acesso', 'value': 'Todos os recursos'}
            ],
            'warning_message': f'Após {days_remaining} {"dia" if days_remaining == 1 else "dias"}, sua conta será transferida para o plano Básico.',
            'footer_message': 'Continue aproveitando todos os recursos Premium!'
        }
        
        html_content = self.create_professional_email_template(content_data)
        
        text_content = f"""
Geminii Tech - {urgency_text} do Trial

Olá, {user_name}!

Seu trial Premium expira em {days_remaining} {"dia" if days_remaining == 1 else "dias"}!

Não perca o acesso a:
- Ferramentas avançadas de trading
- Relatórios detalhados
- Suporte prioritário
- Acesso ilimitado

Faça upgrade agora: {self.base_url}/upgrade

Continue aproveitando todos os recursos Premium!

© 2025 Geminii Tech - Trading Automatizado
        """
        
        subject = f"⏰ {urgency_text} do seu Trial Premium - Geminii Tech"
        return self.send_email(email, subject, html_content, text_content)
    
    def send_trial_expired_email(self, user_name, email):
        """💡 Enviar email de trial expirado COM TEMPLATE ANTI-SPAM"""
        
        content_data = {
            'title': 'Trial Expirado',
            'subtitle': 'Mas você ainda pode acessar recursos básicos',
            'main_message': 'Seu trial Premium de 15 dias expirou. Que tal fazer upgrade e ter acesso completo novamente?',
            'user_name': user_name,
            'urgency_color': '#6b7280',
            'button_text': '💎 Fazer Upgrade',
            'button_url': f"{self.base_url}/planos",
            'details': [
                {'label': 'Status', 'value': 'Trial expirado'},
                {'label': 'Plano atual', 'value': 'Básico'},
                {'label': 'Acesso', 'value': 'Recursos limitados'}
            ],
            'warning_message': 'Upgrade para ter acesso completo a todas as funcionalidades.',
            'footer_message': 'Obrigado por experimentar nosso trial!'
        }
        
        html_content = self.create_professional_email_template(content_data)
        
        text_content = f"""
Geminii Tech - Trial Expirado

Olá, {user_name}!

Seu trial Premium de 15 dias expirou.

Você ainda pode acessar:
- Recursos básicos
- Gráficos simples
- Suporte por email

Com Premium você tem:
- Ferramentas avançadas
- Relatórios completos
- Suporte prioritário
- Acesso ilimitado

Fazer upgrade: {self.base_url}/upgrade

Continue sua jornada conosco!

© 2025 Geminii Tech - Trading Automatizado
        """
        
        return self.send_email(email, "💡 Trial expirado - Geminii Tech", html_content, text_content)

    # ===== EMAILS DE PAGAMENTO COM TEMPLATE ANTI-SPAM =====

    def send_payment_success_email(self, user_name, email, plan_name, amount=None):
        """✅ Enviar email de pagamento confirmado COM TEMPLATE ANTI-SPAM"""
        
        content_data = {
            'title': 'Pagamento Confirmado!',
            'subtitle': f'Bem-vindo ao {plan_name}',
            'main_message': f'Seu pagamento foi confirmado com sucesso! Agora você tem acesso total ao plano {plan_name}.',
            'user_name': user_name,
            'urgency_color': '#10b981',
            'button_text': '🚀 Acessar Dashboard',
            'button_url': f"{self.base_url}/dashboard",
            'details': [
                {'label': 'Plano', 'value': plan_name},
                {'label': 'Status', 'value': 'Ativo'},
                {'label': 'Renovação', 'value': 'Automática'}
            ] + ([{'label': 'Valor', 'value': str(amount)}] if amount else []),
            'warning_message': 'Agora você pode aproveitar todos os recursos Premium.',
            'footer_message': 'Obrigado por escolher a Geminii Tech!'
        }
        
        html_content = self.create_professional_email_template(content_data)
        
        text_content = f"""
Geminii Tech - Pagamento Confirmado!

Olá, {user_name}!

Seu pagamento foi confirmado com sucesso!

Detalhes:
- Plano: {plan_name}
- Status: Ativo
- Renovação: Automática
{"- Valor: " + str(amount) if amount else ""}

Agora você pode aproveitar:
- Ferramentas avançadas
- Relatórios completos
- Suporte prioritário
- Acesso ilimitado

Acessar agora: {self.base_url}/dashboard

Obrigado por escolher a Geminii Tech!

© 2025 Geminii Tech - Trading Automatizado
        """
        
        return self.send_email(email, f"✅ Pagamento confirmado - {plan_name} - Geminii Tech", html_content, text_content)

    def send_payment_reminder_email(self, user_name, email, plan_name, days_until_renewal, amount=None):
        """📅 Enviar lembrete de renovação COM TEMPLATE ANTI-SPAM"""
        
        if days_until_renewal <= 1:
            urgency_color = "#ef4444"
            urgency_text = "AMANHÃ"
        elif days_until_renewal <= 3:
            urgency_color = "#f59e0b"
            urgency_text = f"Em {days_until_renewal} dias"
        else:
            urgency_color = "#0ea5e9"
            urgency_text = f"Em {days_until_renewal} dias"
        
        content_data = {
            'title': f'Renovação {urgency_text}',
            'subtitle': f'Sua assinatura {plan_name}',
            'main_message': f'Sua assinatura {plan_name} será renovada em {days_until_renewal} {"dia" if days_until_renewal == 1 else "dias"}. Tudo certo para a renovação automática!',
            'user_name': user_name,
            'urgency_color': urgency_color,
            'button_text': '⚙️ Gerenciar Assinatura',
            'button_url': f"{self.base_url}/planos",
            'details': [
                {'label': 'Plano', 'value': plan_name},
                {'label': 'Renovação', 'value': 'Automática'},
                {'label': 'Método', 'value': 'Cartão cadastrado'}
            ] + ([{'label': 'Valor', 'value': str(amount)}] if amount else []),
            'warning_message': 'A renovação será processada automaticamente.',
            'footer_message': f'Renovação automática em {days_until_renewal} {"dia" if days_until_renewal == 1 else "dias"}'
        }
        
        html_content = self.create_professional_email_template(content_data)
        
        text_content = f"""
Geminii Tech - Renovação {urgency_text}

Olá, {user_name}!

Sua assinatura {plan_name} será renovada em {days_until_renewal} {"dia" if days_until_renewal == 1 else "dias"}.

Detalhes:
- Plano: {plan_name}
- Renovação: Automática
- Método: Cartão cadastrado
{"- Valor: " + str(amount) if amount else ""}

Continuará aproveitando:
- Ferramentas avançadas
- Relatórios completos
- Suporte prioritário
- Acesso ilimitado

Gerenciar conta: {self.base_url}/account

Precisa alterar algo? Acesse sua conta!

© 2025 Geminii Tech - Trading Automatizado
        """
        
        subject = f"📅 Renovação {urgency_text} - {plan_name} - Geminii Tech"
        return self.send_email(email, subject, html_content, text_content)

# INSTÂNCIA GLOBAL
email_service = EmailService()

# FUNÇÃO DE SETUP
def setup_email_system():
    """🚀 Configurar sistema de email"""
    print("🚀 Configurando sistema de email...")
    
    if email_service.setup_tables():
        print("✅ Sistema de email configurado!")
        print("📧 MODO SMTP CORPORATIVO ativo - Emails via Titan")
        print("🛡️ SISTEMA ANTI-SPAM ativado")
        return True
    else:
        print("❌ Falha na configuração")
        return False

if __name__ == "__main__":
    setup_email_system()
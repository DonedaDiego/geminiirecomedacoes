#email_service

import os
import secrets
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone
from database import get_db_connection

class EmailService:
    def __init__(self):
        self.smtp_server = os.environ.get('SMTP_SERVER', 'smtp.titan.email')
        self.smtp_port = int(os.environ.get('SMTP_PORT', '465'))
        self.smtp_username = os.environ.get('EMAIL_USER', 'contato@geminii.com.br')
        self.smtp_password = os.environ.get('EMAIL_PASSWORD', '#Geminii20##')
        self.from_email = os.environ.get('FROM_EMAIL', 'contato@geminii.com.br')
        self.from_name = 'Geminii Tech'
        self.base_url = os.environ.get('BASE_URL', 'http://localhost:5000')
        self.test_mode = False
        

    def send_email(self, to_email, subject, html_content, text_content=None):
        try:
            if self.test_mode:
                print(f"\n[MODO TESTE] Email simulado para: {to_email}")
                return True
        
            if not to_email or not subject or not html_content:
                print(f"❌ Email inválido: campos em branco")
                return False
                
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            msg['Reply-To'] = self.from_email
            msg['Message-ID'] = f"<{secrets.token_urlsafe(16)}@geminii.com.br>"
            msg['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')
            
            if not text_content:
                text_content = self.html_to_text(html_content)
            
            text_part = MIMEText(text_content, 'plain', 'utf-8')
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(text_part)
            msg.attach(html_part)
            
            print(f"\n📧 Tentando enviar email para: {to_email}")
            
            # ✅ SEMPRE PORTA 465 SSL
            import ssl
            context = ssl.create_default_context()
            
            try:
                server = smtplib.SMTP_SSL(
                    self.smtp_server, 
                    465,  # ✅ FIXO
                    timeout=5,  # ⚠️ TIMEOUT CURTO
                    context=context
                )
                server.set_debuglevel(0)  # ✅ SEM DEBUG
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
                server.quit()
                
                print(f"✅ Email enviado para {to_email}!")
                return True
                
            except Exception as smtp_error:
                print(f"❌ Erro SMTP: {smtp_error}")
                # ⚠️ NÃO QUEBRAR - Railway bloqueia SMTP
                return False
            
        except Exception as e:
            print(f"❌ Erro geral: {e}")
            return False

    def html_to_text(self, html_content):
        """Converter HTML para texto simples (anti-spam)"""
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
            print(f" Erro ao converter HTML para texto: {e}")
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
        
        #  TEMPLATE HTML PROFISSIONAL E ANTI-SPAM
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
        /*  CSS ANTI-SPAM OTIMIZADO */
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
    <!--  PREHEADER INVISÍVEL PARA PREVIEW -->
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

    def create_community_email_template(self, content_data, user_name):
        """🎨 Template específico para email da comunidade com benefícios"""
        
        title = content_data.get('title', 'Geminii Tech')
        subtitle = content_data.get('subtitle', '')
        main_message = content_data.get('main_message', '')
        urgency_color = content_data.get('urgency_color', '#ba39af')
        button_text = content_data.get('button_text', 'Acessar')
        button_url = content_data.get('button_url', self.base_url)
        
        html_template = f"""
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="pt-BR">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{title}</title>
    <style type="text/css">
        body {{ 
            margin: 0; 
            padding: 0; 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, Arial, sans-serif; 
            background-color: #f8fafc;
            line-height: 1.6;
        }}
        
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
            padding: 16px 32px; 
            text-decoration: none; 
            border-radius: 8px; 
            font-weight: 600; 
            margin: 20px 0;
            font-size: 18px;
        }}
        
        .benefits-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin: 30px 0;
        }}
        
        .benefit-item {{
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid {urgency_color};
            text-align: center;
        }}
        
        .benefit-icon {{
            width: 48px;
            height: 48px;
            background: {urgency_color};
            border-radius: 50%;
            margin: 0 auto 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 20px;
        }}
        
        .benefit-title {{
            font-weight: 600;
            color: #1f2937;
            margin-bottom: 8px;
            font-size: 16px;
        }}
        
        .benefit-desc {{
            color: #6b7280;
            font-size: 14px;
            line-height: 1.4;
        }}
        
        .footer {{ 
            background-color: #f1f5f9; 
            padding: 20px; 
            text-align: center; 
            font-size: 12px; 
            color: #64748b;
        }}
        
        @media (max-width: 600px) {{
            .benefits-grid {{
                grid-template-columns: 1fr;
            }}
            .content {{
                padding: 20px;
            }}
        }}
    </style>
</head>
<body>
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
                        
                        <h3 style="color: #1f2937; margin: 30px 0 20px 0; font-size: 18px; text-align: center;">
                            O que você terá na Comunidade:
                        </h3>
                        
                        <div class="benefits-grid">
                            <div class="benefit-item">
                                <div class="benefit-icon">🎓</div>
                                <div class="benefit-title">Aulas Online</div>
                                <div class="benefit-desc">2x por semana com conteúdo prático e aplicação real no mercado</div>
                            </div>
                            
                            <div class="benefit-item">
                                <div class="benefit-icon">📹</div>
                                <div class="benefit-title">Aulas Gravadas</div>
                                <div class="benefit-desc">Nivelamento do básico ao avançado, direto ao ponto</div>
                            </div>
                            
                            <div class="benefit-item">
                                <div class="benefit-icon">💬</div>
                                <div class="benefit-title">Grupo WhatsApp</div>
                                <div class="benefit-desc">Fechado para trocas de experiências e discussões</div>
                            </div>
                            
                            <div class="benefit-item">
                                <div class="benefit-icon">🎥</div>
                                <div class="benefit-title">Reuniões Gravadas</div>
                                <div class="benefit-desc">Rever e tirar dúvidas sobre operações quando quiser</div>
                            </div>
                            
                            <div class="benefit-item">
                                <div class="benefit-icon"></div>
                                <div class="benefit-title">Estratégias</div>
                                <div class="benefit-desc">Acompanhamento direto das estratégias do dia a dia</div>
                            </div>
                            
                            <div class="benefit-item">
                                <div class="benefit-icon">💡</div>
                                <div class="benefit-title">Insights</div>
                                <div class="benefit-desc">Análises e insights exclusivos do mercado</div>
                            </div>
                        </div>
                        
                        <div style="text-align: center; margin: 40px 0;">
                            <a href="{button_url}" class="button">
                                {button_text}
                            </a>
                        </div>
                        
                        <div style="background-color: #fef3c7; border: 1px solid #f59e0b; padding: 16px; border-radius: 8px; margin: 20px 0; color: #92400e; text-align: center;">
                            <strong>Não perca:</strong> Continue com acesso completo e receba todas as atualizações!
                        </div>
                        
                        <div style="margin-top: 30px; text-align: center;">
                            <p style="color: #64748b; font-size: 14px; margin: 0;">
                                Dúvidas? Entre em contato: 
                                <a href="mailto:contato@geminii.com.br" style="color: {urgency_color};">contato@geminii.com.br</a>
                            </p>
                        </div>
                    </div>
                    
                    <!-- Footer -->
                    <div class="footer">
                        <p style="margin: 0;">© 2025 Geminii Tech - Comunidade de Opções Estruturadas</p>
                        <p style="margin: 8px 0 0 0;">Transforme seus investimentos com nossa comunidade exclusiva</p>
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
        """Criar tabelas necessárias"""
        try:
            conn = get_db_connection()
            if not conn:
                return False
                
            cursor = conn.cursor()
            
            print("Configurando tabelas de email...")
            
            # 1. Adicionar campos na tabela users
            try:
                cursor.execute("""
                    ALTER TABLE users 
                    ADD COLUMN IF NOT EXISTS email_confirmed BOOLEAN DEFAULT FALSE,
                    ADD COLUMN IF NOT EXISTS email_confirmed_at TIMESTAMP DEFAULT NULL
                """)
                print(" Campos adicionados na tabela users")
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
                print(" Tabela password_reset_tokens criada")
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
                print(f" {updated} usuários antigos marcados como confirmados")
            except Exception as e:
                print(f"⚠️ Erro ao confirmar usuários: {e}")
            
            # 5. Criar índices
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_confirmations_token ON email_confirmations(token)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_password_reset_token ON password_reset_tokens(token)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email_confirmed ON users(email_confirmed)")
                print(" Índices criados")
            except Exception as e:
                print(f"⚠️ Erro ao criar índices: {e}")
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True
            
        except Exception as e:
            print(f" Erro na configuração de tabelas: {e}")
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
            print(f" Erro ao gerar token de confirmação: {e}")
            return {'success': False, 'error': str(e)}

    def send_confirmation_email(self, user_name, email, token):
        """📧 Enviar email de confirmação COM TEMPLATE ANTI-SPAM"""
        
        #  USAR NOVO TEMPLATE ANTI-SPAM
        content_data = {
            'title': 'Confirme seu Email',
            'subtitle': 'Geminii Tech - Trading Automatizado',
            'main_message': f'Bem-vindo à Geminii Tech! Para ativar sua conta e começar a usar nossa plataforma, confirme seu email clicando no botão abaixo.',
            'user_name': user_name,
            'urgency_color': '#10b981',
            'button_text': ' Confirmar Email',
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
            
            # ✅ ENVIAR EMAIL DE BOAS-VINDAS (ESTA LINHA ESTAVA FALTANDO!)
            try:
                print(f"📧 Enviando email de boas-vindas para {email}...")
                welcome_sent = self.send_trial_welcome_community_email(user_name, email)
                
                if welcome_sent:
                    print(f"✅ Email de boas-vindas enviado com sucesso!")
                else:
                    print(f"⚠️ Falha ao enviar email de boas-vindas (mas confirmação OK)")
            except Exception as e:
                print(f"⚠️ Erro ao enviar email de boas-vindas: {e}")
                # Não falhar a confirmação se o email de boas-vindas falhar
            
            return {
                'success': True,
                'message': 'Email confirmado com sucesso!',
                'user_name': user_name,
                'email': email
            }
            
        except Exception as e:
            print(f"❌ Erro ao confirmar email: {e}")
            return {'success': False, 'error': str(e)}
    

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
            
            # ✅ CORREÇÃO - Gerar token com UTC explícito
            token = secrets.token_urlsafe(32)
            now_utc = datetime.now(timezone.utc)
            expires_at_utc = now_utc + timedelta(hours=1)
            
            print(f"\n🔑 Gerando token de reset:")
            print(f"   Usuário: {user_name} ({email})")
            print(f"   Agora (UTC): {now_utc}")
            print(f"   Expira em (UTC): {expires_at_utc}")
            print(f"   Token: {token[:20]}...")
            
            # ✅ IMPORTANTE - Salvar com timezone
            cursor.execute("""
                INSERT INTO password_reset_tokens (user_id, token, expires_at)
                VALUES (%s, %s, %s AT TIME ZONE 'UTC')
            """, (user_id, token, expires_at_utc))
            
            conn.commit()
            
            # ✅ VERIFICAR SE SALVOU CORRETAMENTE
            cursor.execute("""
                SELECT expires_at FROM password_reset_tokens 
                WHERE token = %s
            """, (token,))
            
            saved_expires = cursor.fetchone()[0]
            print(f"   ✅ Salvo no banco como: {saved_expires}")
            
            cursor.close()
            conn.close()
            
            # Mostrar link no console (sempre útil para debug)
            link = f"{self.base_url}/reset-password?token={token}"
            print(f"\n🔑 [LINK DE RESET]:")
            print(f"   {link}")
            print(f"   ⏰ Expira em: 1 hora\n")
            
            return {
                'success': True,
                'token': token,
                'user_name': user_name,
                'user_email': email
            }
            
        except Exception as e:
            print(f"❌ Erro ao gerar token de reset: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}

    def send_password_reset_email(self, user_name, email, token):
        """📧 Enviar email de reset COM TEMPLATE ANTI-SPAM"""
        
        #  USAR NOVO TEMPLATE ANTI-SPAM
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
        
        try:
            print(f"\n{'='*60}")
            print(f"🔍 VALIDANDO TOKEN DE RESET:")
            print(f"{'='*60}")
            print(f"   Token recebido: {token}")
            print(f"   Tamanho: {len(token)} chars")
            
            conn = get_db_connection()
            if not conn:
                return {'success': False, 'error': 'Erro de conexão'}
            
            cursor = conn.cursor()
            
            # Buscar token válido
            cursor.execute("""
                SELECT prt.user_id, u.email, u.name, prt.expires_at, prt.token
                FROM password_reset_tokens prt
                JOIN users u ON u.id = prt.user_id
                WHERE prt.token = %s AND prt.used = FALSE
            """, (token,))
            
            result = cursor.fetchone()
            
            if not result:
                # 🔍 DEBUG - Mostrar tokens recentes
                print(f"\n❌ Token não encontrado no banco!")
                print(f"🔍 Buscando tokens recentes...")
                
                cursor.execute("""
                    SELECT token, expires_at, used, created_at
                    FROM password_reset_tokens 
                    ORDER BY created_at DESC 
                    LIMIT 5
                """)
                
                recent = cursor.fetchall()
                print(f"\n📋 Últimos 5 tokens:")
                for idx, (db_token, exp, used, created) in enumerate(recent, 1):
                    print(f"   {idx}. Token: {db_token[:20]}...")
                    print(f"      Expiração: {exp}")
                    print(f"      Usado: {used}")
                    print(f"      Criado em: {created}")
                    print(f"      Match com recebido? {db_token == token}")
                
                cursor.close()
                conn.close()
                return {'success': False, 'error': 'Token inválido ou já usado'}
            
            user_id, email, name, expires_at, db_token = result
            
            print(f"\n✅ Token encontrado!")
            print(f"   Usuário: {name} ({email})")
            print(f"   Expira em: {expires_at}")
            
            # ✅ CORREÇÃO - Usar UTC consistente
            now_utc = datetime.now(timezone.utc)
            expires_utc = expires_at.replace(tzinfo=timezone.utc) if expires_at.tzinfo is None else expires_at
            
            print(f"   Agora (UTC): {now_utc}")
            print(f"   Expiração (UTC): {expires_utc}")
            print(f"   Tempo restante: {expires_utc - now_utc}")
            
            # Verificar expiração
            if now_utc > expires_utc:
                print(f"❌ Token expirado!")
                cursor.close()
                conn.close()
                return {'success': False, 'error': 'Token expirado'}
            
            print(f"✅ Token válido!")
            print(f"{'='*60}\n")
            
            cursor.close()
            conn.close()
            
            return {
                'success': True,
                'user_id': user_id,
                'email': email,
                'user_name': name,
                'expires_at': expires_utc.isoformat()
            }
            
        except Exception as e:
            print(f"❌ Erro ao validar token: {e}")
            import traceback
            traceback.print_exc()
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
            
            print(f" Senha redefinida para: {user_name}")
            
            return {
                'success': True,
                'message': 'Senha redefinida com sucesso!',
                'user_name': user_name
            }
            
        except Exception as e:
            print(f" Erro ao redefinir senha: {e}")
            return {'success': False, 'error': str(e)}

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

    # ===== NOVOS EMAILS DA COMUNIDADE =====

    def send_trial_welcome_community_email(self, user_name, email):
        """🎉 Email de boas-vindas ao trial - VERSÃO MELHORADA"""
        
        # Template HTML customizado e rico
        html_content = f"""
    <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
    <html xmlns="http://www.w3.org/1999/xhtml" lang="pt-BR">
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <meta name="x-apple-disable-message-reformatting" />
        <title>Bem-vindo à Geminii Tech!</title>
        <style type="text/css">
            @media screen and (max-width: 600px) {{
                .container {{ width: 100% !important; }}
                .content {{ padding: 20px !important; }}
                .benefits-grid {{ grid-template-columns: 1fr !important; }}
            }}
            
            body {{ 
                margin: 0; 
                padding: 0; 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, Arial, sans-serif; 
                background-color: #0a0a0a;
                line-height: 1.6;
            }}
            
            .container {{ 
                max-width: 600px; 
                margin: 0 auto; 
                background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
                border-radius: 16px;
                overflow: hidden;
                border: 1px solid rgba(186, 57, 175, 0.3);
            }}
            
            .header {{ 
                background: linear-gradient(135deg, #ba39af, #d946ef); 
                padding: 40px 30px; 
                text-align: center; 
                position: relative;
            }}
            
            .header::before {{
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 120"><path d="M0,0 L1200,0 L1200,100 Q600,120 0,100 Z" fill="rgba(255,255,255,0.1)"/></svg>');
                background-size: cover;
                opacity: 0.3;
            }}
            
            .header h1 {{
                margin: 0;
                font-size: 32px;
                font-weight: 700;
                color: #ffffff;
                text-shadow: 0 2px 4px rgba(0,0,0,0.3);
                position: relative;
                z-index: 1;
            }}
            
            .header p {{
                margin: 12px 0 0 0;
                color: #ffffff;
                opacity: 0.95;
                font-size: 16px;
                position: relative;
                z-index: 1;
            }}
            
            .content {{ 
                padding: 40px 30px; 
                background: #1a1a1a;
                color: #e5e5e5;
            }}
            
            .welcome-badge {{
                background: linear-gradient(135deg, #10b981, #059669);
                color: white;
                padding: 8px 16px;
                border-radius: 20px;
                display: inline-block;
                font-size: 14px;
                font-weight: 600;
                margin-bottom: 20px;
            }}
            
            .button {{ 
                display: inline-block; 
                background: linear-gradient(135deg, #ba39af, #d946ef); 
                color: #ffffff !important; 
                padding: 16px 32px; 
                text-decoration: none; 
                border-radius: 10px; 
                font-weight: 600; 
                margin: 20px 0;
                font-size: 18px;
                border: none;
                box-shadow: 0 4px 15px rgba(186, 57, 175, 0.4);
                transition: all 0.3s ease;
            }}
            
            .benefits-grid {{
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 15px;
                margin: 30px 0;
            }}
            
            .benefit-item {{
                background: rgba(186, 57, 175, 0.1);
                padding: 20px;
                border-radius: 12px;
                border-left: 4px solid #ba39af;
                text-align: center;
                transition: all 0.3s ease;
            }}
            
            .benefit-icon {{
                font-size: 32px;
                margin-bottom: 10px;
            }}
            
            .benefit-title {{
                font-weight: 600;
                color: #ba39af;
                margin-bottom: 8px;
                font-size: 16px;
            }}
            
            .benefit-desc {{
                color: #a0a0a0;
                font-size: 13px;
                line-height: 1.5;
            }}
            
            .social-links {{
                display: flex;
                justify-content: center;
                gap: 15px;
                margin: 30px 0;
                flex-wrap: wrap;
            }}
            
            .social-link {{
                display: inline-flex;
                align-items: center;
                gap: 8px;
                background: rgba(186, 57, 175, 0.15);
                padding: 10px 16px;
                border-radius: 8px;
                color: #ba39af !important;
                text-decoration: none;
                font-size: 14px;
                font-weight: 500;
                border: 1px solid rgba(186, 57, 175, 0.3);
                transition: all 0.3s ease;
            }}
            
            .whatsapp-btn {{
                background: linear-gradient(135deg, #25D366, #128C7E);
                color: white !important;
                padding: 14px 24px;
                border-radius: 10px;
                text-decoration: none;
                font-weight: 600;
                display: inline-block;
                margin: 20px 0;
                box-shadow: 0 4px 15px rgba(37, 211, 102, 0.3);
            }}
            
            .footer {{ 
                background: #0a0a0a; 
                padding: 30px 20px; 
                text-align: center; 
                font-size: 13px; 
                color: #666;
                border-top: 1px solid rgba(186, 57, 175, 0.2);
            }}
            
            .warning-box {{
                background: rgba(186, 57, 175, 0.1);
                border: 1px solid #ba39af;
                padding: 16px;
                border-radius: 10px;
                margin: 20px 0;
                color: #e5e5e5;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #0a0a0a; padding: 20px;">
            <tr>
                <td align="center">
                    <div class="container">
                        <!-- Header -->
                        <div class="header">
                            <h1>🚀 Bem-vindo à Geminii Tech!</h1>
                            <p>Sua jornada começa agora</p>
                        </div>
                        
                        <!-- Content -->
                        <div class="content">
                            <div style="text-align: center;">
                                <span class="welcome-badge">✨ Trial de 15 dias ativado</span>
                            </div>
                            
                            <h2 style="color: #ba39af; margin-bottom: 16px; font-size: 24px; text-align: center;">
                                Olá, {user_name}! 👋
                            </h2>
                            
                            <p style="color: #e5e5e5; margin-bottom: 20px; font-size: 16px; text-align: center;">
                                Parabéns! Seu trial de 15 dias foi ativado com sucesso. 
                                Aproveite <strong>acesso completo</strong> a todas as ferramentas da nossa plataforma.
                            </p>
                            
                            <h3 style="color: #ba39af; margin: 30px 0 20px 0; font-size: 20px; text-align: center;">
                                🎯 O que você pode fazer:
                            </h3>
                            
                            <div class="benefits-grid">
                                <div class="benefit-item">
                                    <div class="benefit-icon">📊</div>
                                    <div class="benefit-title">Análise Avançada</div>
                                    <div class="benefit-desc">Ferramentas completas de trading automatizado</div>
                                </div>
                                
                                <div class="benefit-item">
                                    <div class="benefit-icon">📈</div>
                                    <div class="benefit-title">Estratégias</div>
                                    <div class="benefit-desc">Acesso a todas as estratégias quantitativas</div>
                                </div>
                                
                                <div class="benefit-item">
                                    <div class="benefit-icon">📱</div>
                                    <div class="benefit-title">Relatórios</div>
                                    <div class="benefit-desc">Gere relatórios profissionais em PDF</div>
                                </div>
                                
                                <div class="benefit-item">
                                    <div class="benefit-icon">💬</div>
                                    <div class="benefit-title">Suporte</div>
                                    <div class="benefit-desc">Email e WhatsApp prioritário</div>
                                </div>
                            </div>
                            
                            <div style="text-align: center; margin: 30px 0;">
                                <a href="{self.base_url}/dashboard" class="button">
                                    🚀 Acessar Plataforma
                                </a>
                            </div>
                            
                            <div class="warning-box">
                                <strong>⏰ Importante:</strong> Seu trial expira em 15 dias. Aproveite ao máximo!
                            </div>
                            
                            <!-- WhatsApp -->
                            <div style="text-align: center; margin: 30px 0;">
                                <p style="color: #a0a0a0; margin-bottom: 10px;">💬 Precisa de ajuda? Fale conosco:</p>
                                <a href="https://wa.me/5541995432873?text=Olá!%20Acabei%20de%20ativar%20meu%20trial%20na%20Geminii%20Tech" class="whatsapp-btn">
                                    📱 WhatsApp: (41) 99543-2873
                                </a>
                            </div>
                            
                            <!-- Redes Sociais -->
                            <div style="border-top: 1px solid rgba(186, 57, 175, 0.2); padding-top: 25px; margin-top: 25px;">
                                <p style="color: #ba39af; text-align: center; margin-bottom: 15px; font-weight: 600;">
                                    🌐 Siga nossas redes sociais:
                                </p>
                                <div class="social-links">
                                    <a href="https://discord.gg/kmsfECUT" class="social-link">
                                        💬 Discord
                                    </a>
                                    <a href="https://instagram.com/geminiiresearch" class="social-link">
                                        📸 Instagram
                                    </a>
                                    <a href="https://linkedin.com/company/geminii-research" class="social-link">
                                        💼 LinkedIn
                                    </a>
                                    <a href="https://t.me/geminiireserach" class="social-link">
                                        ✈️ Telegram
                                    </a>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Footer -->
                        <div class="footer">
                            <p style="margin: 0; color: #ba39af; font-weight: 600;">© 2025 Geminii Tech</p>
                            <p style="margin: 8px 0 0 0;">Trading Automatizado & Análise Quantitativa</p>
                            <p style="margin: 15px 0 0 0;">
                                <a href="mailto:contato@geminii.com.br" style="color: #ba39af; text-decoration: none;">
                                    ✉️ contato@geminii.com.br
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
        
        # Versão texto
        text_content = f"""
    🚀 BEM-VINDO À GEMINII TECH!

    Olá, {user_name}!

    ✨ Seu trial de 15 dias foi ativado com sucesso!

    🎯 O QUE VOCÊ PODE FAZER:

    📊 Análise Avançada
    Ferramentas completas de trading automatizado

    📈 Estratégias
    Acesso a todas as estratégias quantitativas

    📱 Relatórios
    Gere relatórios profissionais em PDF

    💬 Suporte
    Email e WhatsApp prioritário

    🚀 ACESSE AGORA: {self.base_url}/dashboard

    ⏰ IMPORTANTE: Seu trial expira em 15 dias. Aproveite ao máximo!

    💬 PRECISA DE AJUDA?
    WhatsApp: (41) 99543-2873
    https://wa.me/5541995432873

    🌐 REDES SOCIAIS:
    Discord: https://discord.gg/kmsfECUT
    Instagram: https://instagram.com/geminiiresearch
    LinkedIn: https://linkedin.com/company/geminii-research
    Telegram: https://t.me/geminiireserach

    Dúvidas? contato@geminii.com.br

    © 2025 Geminii Tech - Trading Automatizado
        """
        
        return self.send_email(email, "🚀 Bem-vindo à Geminii Tech - Trial ativado!", html_content, text_content)


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
                print(f" Usuário não encontrado: {email}")
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f" Erro no debug: {e}")

# INSTÂNCIA GLOBAL
email_service = EmailService()

# FUNÇÃO DE SETUP
def setup_email_system():
    print("Configurando sistema de emails...")
    if email_service.setup_tables():
        print(" Sistema de emails configurado com sucesso!")
        return True
    else:
        print(" Falha na configuração")
        return False

if __name__ == "__main__":
    setup_email_system()
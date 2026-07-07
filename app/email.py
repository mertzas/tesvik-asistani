import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import os
from app.models import settings


class EmailService:
    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER or os.getenv("SMTP_SERVER")
        self.smtp_port = settings.SMTP_PORT or int(os.getenv("SMTP_PORT", 587))
        self.smtp_user = settings.SMTP_USER or os.getenv("SMTP_USER")
        self.smtp_password = settings.SMTP_PASSWORD or os.getenv("SMTP_PASSWORD")

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ) -> bool:
        """Send email via SMTP"""
        if not all([self.smtp_server, self.smtp_user, self.smtp_password]):
            print("Email service not configured")
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.smtp_user
            msg['To'] = to_email

            # Add text part
            msg.attach(MIMEText(body, 'plain'))

            # Add HTML part
            if html_body:
                msg.attach(MIMEText(html_body, 'html'))

            # Send
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            return True
        except Exception as e:
            print(f"Failed to send email: {e}")
            return False

    def send_welcome_email(self, email: str, name: str) -> bool:
        """Send welcome email to new user"""
        subject = "🎉 Teşvik Asistanı'na Hoş Geldiniz!"
        body = f"""
Merhaba {name},

Teşvik Asistanı'na hoş geldiniz! Devlet teşviklerini keşfetmeye başlamaya hazırsanız:

1. Giriş yapın: {settings.APP_URL}/dashboard
2. Arama yapın: Bir teşvik sorusu sorun
3. Sonuçları alın: Anında relevans sonuçları

Sorularınız için: support@tesvikasistani.com

İyi kullanımlar!
Teşvik Asistanı Ekibi
"""

        html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
    <h2 style="color: #667eea;">🎉 Teşvik Asistanı'na Hoş Geldiniz!</h2>
    <p>Merhaba <strong>{name}</strong>,</p>
    <p>Teşvik Asistanı'na hoş geldiniz! Devlet teşviklerini keşfetmeye başlamaya hazırsanız:</p>
    <ol>
        <li><a href="{settings.APP_URL}/dashboard">Giriş yapın</a></li>
        <li>Bir teşvik sorusu sorun</li>
        <li>Anında relevans sonuçları alın</li>
    </ol>
    <p style="color: #999; font-size: 12px;">
        Sorularınız için: <a href="mailto:support@tesvikasistani.com">support@tesvikasistani.com</a>
    </p>
</body>
</html>
"""

        return self.send_email(email, subject, body, html_body)

    def send_plan_upgrade_email(self, email: str, plan: str) -> bool:
        """Send plan upgrade confirmation"""
        subject = f"✅ Plan Yükseltme Onayı - {plan.upper()}"
        body = f"""
Plan yükseltmeniz başarıyla tamamlandı!

Yeni Plan: {plan.upper()}
Başlangıç Tarihi: Şimdi
Fatura Döngüsü: Her ay

Yeni özelliklerinize erişmek için dashboard'a gidin.

Teşvik Asistanı
"""

        return self.send_email(email, subject, body)

    def send_payment_receipt_email(self, email: str, amount: str, invoice_id: str) -> bool:
        """Send payment receipt"""
        subject = "📄 Ödeme Makbuzu"
        body = f"""
Ödemeniz başarıyla işlenmiştir.

Miktar: {amount}
Fatura No: {invoice_id}
Tarih: Bugün

Makbuz detayları için lütfen dashboard'ınıza gidin.

Teşvik Asistanı
"""

        return self.send_email(email, subject, body)

    def send_password_reset_email(self, email: str, reset_link: str) -> bool:
        """Send password reset email"""
        subject = "🔐 Şifre Sıfırlama Bağlantısı"
        body = f"""
Şifrenizi sıfırlamak için aşağıdaki bağlantıyı kullanın:

{reset_link}

Bu bağlantı 24 saat geçerlidir.

Teşvik Asistanı
"""

        html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
    <h2 style="color: #667eea;">🔐 Şifre Sıfırlama</h2>
    <p>Şifrenizi sıfırlamak için <a href="{reset_link}" style="color: #667eea;">bu bağlantıyı</a> tıklayın.</p>
    <p style="color: #999; font-size: 12px;">Bu bağlantı 24 saat geçerlidir.</p>
</body>
</html>
"""

        return self.send_email(email, subject, body, html_body)

    def send_query_summary_email(self, email: str, results_count: int) -> bool:
        """Send weekly query summary"""
        subject = "📊 Haftalık Teşvik Özeti"
        body = f"""
Merhaba,

Bu hafta yapılan araştırmalarınızın özeti:

Sorgu Sayısı: {results_count}
Bulduğunuz Teşvik: {results_count} sonuç

Daha fazla bilgi için dashboard'ınıza gidin.

Teşvik Asistanı
"""

        return self.send_email(email, subject, body)

    def send_admin_alert_email(self, admin_email: str, subject: str, message: str) -> bool:
        """Send alert email to admin"""
        full_subject = f"⚠️ Admin Alert: {subject}"
        return self.send_email(admin_email, full_subject, message)


# Singleton instance
email_service = EmailService()

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

    def send_password_reset_email(self, email: str, name: str, baglanti: str) -> bool:
        """Parola sıfırlama bağlantısı (1 saat geçerli, tek kullanımlık)."""
        from html import escape
        konu = "Teşvik Asistanı - Parola sıfırlama"
        metin = (f"Merhaba {name},\n\nHesabınız için parola sıfırlama talebi aldık. Yeni parola belirlemek için "
                 f"1 saat içinde şu bağlantıya tıklayın:\n{baglanti}\n\nBu talebi siz yapmadıysanız bu e-postayı yok "
                 f"sayın; parolanız değişmez.\n\nTeşvik Asistanı")
        html = (f"<p>Merhaba <strong>{escape(name)}</strong>,</p><p>Hesabınız için parola sıfırlama talebi aldık. "
                f"Yeni parola belirlemek için 1 saat içinde <a href=\"{escape(baglanti)}\">bu bağlantıya</a> tıklayın.</p>"
                f"<p>Bu talebi siz yapmadıysanız bu e-postayı yok sayın; parolanız değişmez.</p>")
        return self.send_email(email, konu, metin, html)

    def send_verification_email(self, email: str, name: str, baglanti: str) -> bool:
        """E-posta doğrulama bağlantısı (48 saat geçerli, tek kullanımlık)."""
        from html import escape
        konu = "Teşvik Asistanı - E-posta adresinizi doğrulayın"
        metin = (f"Merhaba {name},\n\nE-posta adresinizi doğrulamak için 48 saat içinde şu bağlantıya tıklayın:\n"
                 f"{baglanti}\n\nBu hesabı siz açmadıysanız bu e-postayı yok sayın.\n\nTeşvik Asistanı")
        html = (f"<p>Merhaba <strong>{escape(name)}</strong>,</p><p>E-posta adresinizi doğrulamak için 48 saat içinde "
                f"<a href=\"{escape(baglanti)}\">bu bağlantıya</a> tıklayın.</p>"
                f"<p>Bu hesabı siz açmadıysanız bu e-postayı yok sayın.</p>")
        return self.send_email(email, konu, metin, html)

    def send_existing_account_email(self, email: str, name: str, giris: str, sifirlama: str) -> bool:
        """Var olan bir adresle yeniden kayıt denendiğinde sahibine bildirim. Kayıt yanıtı bu durumu ele
        vermediği için (e-posta numaralandırma yok) bilgi yalnızca adresin sahibine gider."""
        from html import escape
        konu = "Teşvik Asistanı - Bu adresle zaten bir hesabınız var"
        metin = (f"Merhaba {name},\n\nBu e-posta adresiyle yeni bir kayıt denendi, ancak adresinize bağlı bir hesap "
                 f"zaten var. Hesabınızda değişiklik yapılmadı.\n\nGiriş yapmak için: {giris}\nParolanızı "
                 f"hatırlamıyorsanız: {sifirlama}\n\nBu denemeyi siz yapmadıysanız bu e-postayı yok sayabilirsiniz."
                 f"\n\nTeşvik Asistanı")
        html = (f"<p>Merhaba <strong>{escape(name)}</strong>,</p><p>Bu e-posta adresiyle yeni bir kayıt denendi, "
                f"ancak adresinize bağlı bir hesap zaten var. Hesabınızda değişiklik yapılmadı.</p>"
                f"<p><a href=\"{escape(giris)}\">Giriş yapın</a> veya parolanızı hatırlamıyorsanız "
                f"<a href=\"{escape(sifirlama)}\">yeni parola belirleyin</a>.</p>"
                f"<p>Bu denemeyi siz yapmadıysanız bu e-postayı yok sayabilirsiniz.</p>")
        return self.send_email(email, konu, metin, html)

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

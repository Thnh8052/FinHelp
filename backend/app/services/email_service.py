from pathlib import Path
from typing import Optional
from app.core.config import settings
from app.core.logging import logger

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "email"


class EmailService:
    """Service handling transactional emails via SendGrid."""

    def __init__(self):
        self.api_key = settings.SENDGRID_API_KEY
        self.from_email = settings.SENDGRID_FROM_EMAIL or "noreply@finhelp.ai"
        self._client = None

    @property
    def client(self):
        if self._client is None and self.api_key:
            from sendgrid import SendGridAPIClient
            self._client = SendGridAPIClient(self.api_key)
        return self._client

    def _render_template(self, template_name: str, **context) -> str:
        """Render HTML template by replacing {{key}} placeholders."""
        template_file = TEMPLATES_DIR / template_name
        if not template_file.exists():
            raise FileNotFoundError(f"Email template not found: {template_file}")

        content = template_file.read_text(encoding="utf-8")
        for key, value in context.items():
            content = content.replace("{{" + key + "}}", str(value))
            content = content.replace("{{" + key + "|default('15')}}", str(value))
        return content

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """Send an email using SendGrid Web API."""
        if not self.api_key:
            logger.warning("[EmailService] SENDGRID_API_KEY is not set. Email not sent.")
            return False

        try:
            from sendgrid.helpers.mail import Mail

            message = Mail(
                from_email=self.from_email,
                to_emails=to_email,
                subject=subject,
                html_content=html_content,
                plain_text_content=text_content,
            )
            response = self.client.send(message)
            if 200 <= response.status_code < 300:
                logger.info(f"[EmailService] Email sent successfully to {to_email} (status: {response.status_code})")
                return True
            else:
                logger.error(f"[EmailService] Failed to send email to {to_email}, status: {response.status_code}, body: {response.body}")
                return False
        except Exception as e:
            logger.error(f"[EmailService] Error sending email to {to_email}: {e}")
            if hasattr(e, "body"):
                logger.error(f"[EmailService] SendGrid response: {e.body}")
            return False

    def send_password_reset_otp(self, to_email: str, otp_code: str, expire_minutes: int = 15) -> bool:
        """Send password reset OTP email using the responsive template."""
        subject = f"{otp_code} là mã xác thực khôi phục mật khẩu FinHelp của bạn"
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
        reset_url = f"{frontend_url}/reset-password?email={to_email}"  # the code stays in the email body: an address ends up in histories and logs
        
        try:
            html_content = self._render_template(
                "reset_password.html",
                otp_code=otp_code,
                user_email=to_email,
                expire_minutes=expire_minutes,
                reset_url=reset_url,
            )
        except Exception as err:
            logger.warning(f"[EmailService] Template render failed, falling back to minimal HTML: {err}")
            html_content = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 500px; margin: auto; padding: 32px; background: #ffffff; color: #111827; border-radius: 8px; border: 1px solid #e5e7eb;">
                <h2 style="margin: 0 0 16px 0; font-size: 20px;">FinHelp</h2>
                <p style="color: #4b5563; font-size: 14px;">Mã xác thực đặt lại mật khẩu của bạn là:</p>
                <div style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #111827; background: #f3f4f6; padding: 16px; border-radius: 6px; text-align: center; margin: 20px 0; font-family: monospace;">
                    {otp_code}
                </div>
                <p style="color: #6b7280; font-size: 13px;">Mã có hiệu lực trong {expire_minutes} phút. Nếu bạn không yêu cầu, vui lòng bỏ qua email.</p>
            </div>
            """

        text_content = (
            f"Mã xác thực khôi phục mật khẩu FinHelp của bạn là: {otp_code}.\n"
            f"Mã có hiệu lực trong {expire_minutes} phút.\n"
            "Nếu bạn không yêu cầu hành động này, vui lòng bỏ qua email."
        )
        return self.send_email(to_email, subject, html_content, text_content)

    def send_account_confirmation(
        self,
        to_email: str,
        username: str,
        full_name: Optional[str] = None,
        login_url: Optional[str] = None,
    ) -> bool:
        """Send account creation confirmation email using responsive template."""
        subject = "Xác nhận tạo tài khoản thành công - FinHelp"
        display_name = full_name or username
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
        final_login_url = login_url or f"{frontend_url}/login?email={to_email}"
        
        try:
            html_content = self._render_template(
                "account_confirmation.html",
                user_email=to_email,
                username=username,
                full_name=display_name,
                login_url=final_login_url,
            )
        except Exception as err:
            logger.warning(f"[EmailService] Template render failed, falling back to minimal HTML: {err}")
            html_content = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 500px; margin: auto; padding: 32px; background: #ffffff; color: #111827; border-radius: 8px; border: 1px solid #e5e7eb;">
                <h2 style="margin: 0 0 16px 0; font-size: 20px;">FinHelp</h2>
                <h3 style="font-size: 16px; margin-bottom: 12px;">Chào mừng {display_name},</h3>
                <p style="color: #4b5563; font-size: 14px;">Tài khoản FinHelp của bạn ({username} - {to_email}) đã được tạo thành công.</p>
                <p style="margin-top: 20px;"><a href="{final_login_url}" style="display: inline-block; background: #111827; color: #ffffff; padding: 10px 20px; text-decoration: none; border-radius: 6px; font-weight: 600;">Đăng nhập FinHelp</a></p>
            </div>
            """

        text_content = (
            f"Xin chào {display_name},\n\n"
            f"Chúc mừng bạn đã tạo tài khoản thành công tại FinHelp.\n"
            f"- Tên đăng nhập: {username}\n"
            f"- Email: {to_email}\n"
            f"- Link đăng nhập: {final_login_url}\n\n"
            "Đội ngũ FinHelp"
        )
        return self.send_email(to_email, subject, html_content, text_content)

    def send_password_changed_notification(
        self,
        to_email: str,
        full_name: Optional[str] = None,
        changed_at: Optional[str] = None,
        reset_url: Optional[str] = None,
    ) -> bool:
        """Send notification when user's password has been updated."""
        from datetime import datetime, timezone
        
        subject = "Cảnh báo bảo mật: Mật khẩu FinHelp của bạn đã được thay đổi"
        display_name = full_name or to_email.split("@")[0]
        timestamp = changed_at or datetime.now(timezone.utc).strftime("%d/%m/%Y, %H:%M:%S UTC")
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
        final_reset_url = reset_url or f"{frontend_url}/reset-password"

        try:
            html_content = self._render_template(
                "password_changed.html",
                user_email=to_email,
                full_name=display_name,
                changed_at=timestamp,
                reset_url=final_reset_url,
            )
        except Exception as err:
            logger.warning(f"[EmailService] Template render failed, falling back to minimal HTML: {err}")
            html_content = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 500px; margin: auto; padding: 32px; background: #ffffff; color: #111827; border-radius: 8px; border: 1px solid #e5e7eb;">
                <h2 style="margin: 0 0 16px 0; font-size: 20px;">FinHelp</h2>
                <h3 style="font-size: 16px;">Mật khẩu đã được thay đổi</h3>
                <p style="color: #4b5563; font-size: 14px;">Xin chào {display_name}, mật khẩu tài khoản {to_email} vừa được thay đổi lúc {timestamp}.</p>
                <p style="color: #dc2626; font-size: 13px;">Nếu không phải bạn thực hiện, vui lòng truy cập <a href="{reset_url}">FinHelp</a> để khôi phục mật khẩu ngay lập tức.</p>
            </div>
            """

        text_content = (
            f"Xin chào {display_name},\n\n"
            f"Mật khẩu tài khoản FinHelp ({to_email}) của bạn vừa được thay đổi thành công vào lúc {timestamp}.\n\n"
            f"Nếu bạn KHÔNG thực hiện thay đổi này, hãy khôi phục lại mật khẩu ngay lập tức tại: {reset_url}\n\n"
            "Đội ngũ FinHelp"
        )
        return self.send_email(to_email, subject, html_content, text_content)


email_service = EmailService()

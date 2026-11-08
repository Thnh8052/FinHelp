import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load backend/.env file
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


def main():
    parser = argparse.ArgumentParser(description="Test SendGrid email delivery.")
    parser.add_argument(
        "--from-email",
        "-f",
        default=os.environ.get("SENDGRID_FROM_EMAIL"),
        help="Verified sender email address on SendGrid (Settings -> Sender Authentication)",
    )
    parser.add_argument(
        "--to-email",
        "-t",
        help="Recipient email address",
    )
    parser.add_argument(
        "--eu",
        action="store_true",
        help="Enable EU Data Residency (for EU-pinned subusers)",
    )
    parser.add_argument(
        "--template",
        choices=["reset", "confirm", "changed"],
        help="Send test email using a template ('reset' for OTP reset password, 'confirm' for account creation confirmation, 'changed' for password changed alert)",
    )

    args = parser.parse_args()

    api_key = os.environ.get("SENDGRID_API_KEY") or os.environ.get("SEND_GRID_API_KEY")
    if not api_key:
        print("[!] Lỗi: Không tìm thấy SENDGRID_API_KEY trong file .env hoặc biến môi trường.")
        sys.exit(1)

    print(f"[*] API Key detected: {api_key[:6]}...{api_key[-4:]}")

    from_email = args.from_email
    if not from_email:
        print("[!] CẢNH BÁO: Chưa cung cấp sender email (--from-email hoặc SENDGRID_FROM_EMAIL trong .env).")
        from_email = input("Nhập email người gửi (đã verify trên SendGrid): ").strip()
        if not from_email:
            print("[!] Không có email người gửi. Dừng lại.")
            sys.exit(1)

    to_email = args.to_email
    if not to_email:
        to_email = input(f"Nhập email nhận (mặc định gửi về chính {from_email}): ").strip() or from_email

    print(f"[*] Đang gửi email thử nghiệm...")
    print(f"    From: {from_email}")
    print(f"    To:   {to_email}")

    if args.template == "reset":
        template_file = Path(__file__).resolve().parent / "app" / "templates" / "email" / "reset_password.html"
        html_content = template_file.read_text(encoding="utf-8")
        html_content = html_content.replace("{{otp_code}}", "739218")
        html_content = html_content.replace("{{user_email}}", to_email)
        html_content = html_content.replace("{{expire_minutes}}", "15")
        subject = "739218 là mã xác thực khôi phục mật khẩu FinHelp của bạn"
    elif args.template == "confirm":
        template_file = Path(__file__).resolve().parent / "app" / "templates" / "email" / "account_confirmation.html"
        html_content = template_file.read_text(encoding="utf-8")
        html_content = html_content.replace("{{user_email}}", to_email)
        html_content = html_content.replace("{{username}}", to_email.split("@")[0])
        html_content = html_content.replace("{{full_name}}", to_email.split("@")[0].capitalize())
        html_content = html_content.replace("{{login_url}}", "http://localhost:3000")
        subject = "Xác nhận tạo tài khoản thành công - FinHelp"
    elif args.template == "changed":
        template_file = Path(__file__).resolve().parent / "app" / "templates" / "email" / "password_changed.html"
        html_content = template_file.read_text(encoding="utf-8")
        html_content = html_content.replace("{{user_email}}", to_email)
        html_content = html_content.replace("{{full_name}}", to_email.split("@")[0].capitalize())
        html_content = html_content.replace("{{changed_at}}", "08/11/2026, 02:01:08 UTC+7")
        html_content = html_content.replace("{{reset_url}}", "http://localhost:3000")
        subject = "Cảnh báo bảo mật: Mật khẩu FinHelp của bạn đã được thay đổi"
    else:
        subject = "Sending with Twilio SendGrid is Fun - FinHelp Test"
        html_content = "<strong>Chúc mừng! Bạn đã tích hợp Twilio SendGrid thành công vào FinHelp.</strong>"

    message = Mail(
        from_email=from_email,
        to_emails=to_email,
        subject=subject,
        html_content=html_content,
    )

    try:
        sg = SendGridAPIClient(api_key)
        if args.eu:
            sg.set_sendgrid_data_residency("eu")
            print("[*] EU Data Residency enabled.")

        response = sg.send(message)
        print(f"\n[+] Gửi email THÀNH CÔNG!")
        print(f"    Status Code: {response.status_code}")
        print(f"    Response Body: {response.body.decode('utf-8') if response.body else '(empty)'}")
        print(f"    Response Headers: {dict(response.headers)}")
        print("\n-> Bạn có thể quay lại trang Onboarding của Twilio SendGrid và nhấn 'Verify integration'!")
    except Exception as e:
        print(f"\n[-] Lỗi khi gửi email qua SendGrid: {e}")
        if hasattr(e, "body"):
            body_str = e.body.decode("utf-8") if isinstance(e.body, bytes) else str(e.body)
            print(f"    Chi tiết: {body_str}")
        if "Sender Identity" in str(getattr(e, "body", "")):
            print("\n[!] LƯU Ý QUAN TRỌNG TỪ SENDGRID:")
            print("    Địa chỉ 'From' phải là email đã được xác minh trên SendGrid (Single Sender Identity).")
            print("    Truy cập SendGrid Console -> Settings -> Sender Authentication để xác minh email người gửi trước.")


if __name__ == "__main__":
    main()

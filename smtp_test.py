import os
import smtplib
from email.message import EmailMessage

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except Exception:
    pass

SMTP_HOST = os.environ.get("SMTP_HOST") or os.environ.get("EMAIL_HOST") or "smtp.gmail.com"
SMTP_PORT = int(os.environ.get("SMTP_PORT") or os.environ.get("EMAIL_PORT") or "587")
SMTP_USE_SSL = str(os.environ.get("SMTP_USE_SSL") or os.environ.get("EMAIL_USE_SSL") or "false").lower() == "true"
SMTP_USER = (
    os.environ.get("SMTP_EMAIL")
    or os.environ.get("GMAIL_SMTP_USER")
    or os.environ.get("EMAIL_HOST_USER")
    or os.environ.get("SMTP_USERNAME")
    or os.environ.get("MAIL_USERNAME")
)
SMTP_PASSWORD = (
    os.environ.get("SMTP_APP_PASSWORD")
    or os.environ.get("GMAIL_SMTP_PASSWORD")
    or os.environ.get("EMAIL_HOST_PASSWORD")
    or os.environ.get("SMTP_PASSWORD")
    or os.environ.get("MAIL_PASSWORD")
)
TEST_RECIPIENT = os.environ.get("TEST_EMAIL_TO") or os.environ.get("SMTP_TO")

print(f"SMTP host={SMTP_HOST} port={SMTP_PORT} ssl={SMTP_USE_SSL}")
print(f"SMTP user configured={bool(SMTP_USER)} user_len={len(SMTP_USER) if SMTP_USER else 0}")
print(f"SMTP password configured={bool(SMTP_PASSWORD)} password_len={len(SMTP_PASSWORD) if SMTP_PASSWORD else 0}")
print(f"Test recipient configured={bool(TEST_RECIPIENT)}")

if not SMTP_USER or not SMTP_PASSWORD or not TEST_RECIPIENT:
    raise SystemExit(
        "Missing Gmail SMTP configuration. Set SMTP_EMAIL / SMTP_APP_PASSWORD (or GMAIL_SMTP_USER / GMAIL_SMTP_PASSWORD) and TEST_EMAIL_TO before running this test."
    )

msg = EmailMessage()
msg["From"] = SMTP_USER
msg["To"] = TEST_RECIPIENT
msg["Subject"] = "SMTP Test Email"
msg.set_content("This is a test email sent from the app's Gmail SMTP configuration.")

try:
    if SMTP_USE_SSL:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
    print(f"SUCCESS: Test email sent to {TEST_RECIPIENT}")
except Exception as exc:
    print(f"FAILURE: {type(exc).__name__}: {exc}")
    raise

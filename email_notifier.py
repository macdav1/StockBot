import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ---- CONFIG ----
EMAIL_ADDRESS = "davidmacphail54@gmail.com"
EMAIL_PASSWORD = "ofel uagq eljb zufp"  # Your app password
EMAIL_SMTP_SERVER = "smtp.gmail.com"
EMAIL_SMTP_PORT = 465
EMAIL_RECEIVER = "davidmacphail54@gmail.com"
# -----------------

def send_email(subject, body):
    message = MIMEMultipart()
    message["From"] = EMAIL_ADDRESS
    message["To"] = EMAIL_RECEIVER
    message["Subject"] = subject

    message.attach(MIMEText(body, "plain"))

    context = ssl.create_default_context()

    try:
        with smtplib.SMTP_SSL(EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT, context=context) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, EMAIL_RECEIVER, message.as_string())
            print("✅ Email sent successfully.")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")


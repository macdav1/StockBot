import smtplib
import pandas as pd
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import time
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
fh = logging.FileHandler("logs/email.log")
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_SMTP_SERVER = os.getenv("EMAIL_SMTP_SERVER")
EMAIL_SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT"))


def send_email(subject, body, to_email=None, retries=3):
    """
    Send email with optional custom recipient
    
    Args:
        subject: Email subject
        body: Email body text
        to_email: Recipient email (defaults to EMAIL_TO or EMAIL_ADDRESS from .env)
        retries: Number of retry attempts
    """
    # Determine recipient - priority order: argument > EMAIL_TO > EMAIL_ADDRESS
    if to_email is None:
        to_email = os.getenv("EMAIL_TO", EMAIL_ADDRESS)
    
    for attempt in range(retries):
        try:
            msg = MIMEMultipart()
            msg['From'] = EMAIL_ADDRESS
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT) as server:
                server.starttls()
                server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                server.send_message(msg)
            
            logger.info(f"✅ Email sent successfully to {to_email}")
            return
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email} (attempt {attempt+1}): {e}")
            time.sleep(5)
    
    logger.error(f"All email attempts failed for {to_email}")
    print(f"❌ Failed to send email to {to_email} after {retries} attempts.")


def send_prediction_report(extra_message="", to_email=None):
    """
    Send prediction report with optional custom recipient
    
    Args:
        extra_message: Additional message to append
        to_email: Recipient email (optional)
    """
    try:
        predictions = pd.read_csv("predictions.csv")
        report = predictions.to_string(index=False)
        full_message = f"Daily Prediction Report:\n\n{report}\n{extra_message}"
        send_email("Daily Prediction Report", full_message, to_email=to_email)
    except Exception as e:
        logger.error(f"Failed to prepare email report: {e}")
        print(f"❌ Failed to generate report or send email: {e}")

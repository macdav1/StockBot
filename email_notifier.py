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

def send_email(subject, body, retries=3):
    for attempt in range(retries):
        try:
            msg = MIMEMultipart()
            msg['From'] = EMAIL_ADDRESS
            msg['To'] = EMAIL_ADDRESS
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT) as server:
                server.starttls()
                server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                server.send_message(msg)

            logger.info("✅ Email sent successfully.")
            return
        except Exception as e:
            logger.error(f"Failed to send email (attempt {attempt+1}): {e}")
            time.sleep(5)
    logger.error("All email attempts failed.")
    print("❌ Failed to send email after 3 attempts.")  # <--- NEW CONSOLE MESSAGE

def send_prediction_report(extra_message=""):
    try:
        predictions = pd.read_csv("predictions.csv")
        report = predictions.to_string(index=False)
        full_message = f"Daily Prediction Report:\n\n{report}\n{extra_message}"
        send_email("Daily Prediction Report", full_message)
    except Exception as e:
        logger.error(f"Failed to prepare email report: {e}")
        print(f"❌ Failed to generate report or send email: {e}")


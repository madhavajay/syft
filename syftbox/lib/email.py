import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from rich import print as rprint
from jinja2 import Template
from loguru import logger

sender_email = "noreply@openmined.org"
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD","")
SMTP_USER = os.environ.get("SMTP_USER","")
SMTP_SERVER = "smtp.sendgrid.com"
SMTP_PORT = 465

email_template = """
<!doctype html>
<html>
  <head>
    <style>
      body {
        font-family: Arial, sans-serif;
        background-color: #f4f4f4;
        color: #333;
        margin: 0;
        padding: 0;
      }
      .container {
        max-width: 600px;
        margin: 50px auto;
        background-color: #ffffff;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
      }
      h1 {
        color: #333;
        text-align: center;
      }
      p {
        font-size: 16px;
        line-height: 1.5;
      }
      code {
        display: block;
        background-color: #f0f0f0;
        color: #ff8c00;
        padding: 10px;
        font-size: 14px;
        margin: 20px auto;
        border-radius: 4px;
        width: 90%;
        word-wrap: break-word;
      }
      .footer {
        text-align: center;
        font-size: 12px;
        color: #aaa;
        margin-top: 20px;
      }
    </style>
  </head>
  <body>
    <div class="container">
      <h1>Welcome!</h1>
      <p>
        Use the following token in your CLI to complete your registration:
      </p>
      <code> {{ token }} </code>
      <p>If you did not request this, please ignore this email.</p>
    </div>
  </body>
</html>
"""

def send_token_email(user_email: str, token: str):
    template = Template(email_template)
    body = template.render(email=user_email, token=token)
    send_email(
        receiver_email=user_email,
        subject="SyftBox Token",
        body=body,
        mimetype="html",
        log_message="Token Email sent succesfully! Check your email."
    )

def send_email(
    receiver_email: str,
    subject: str,
    body: str,
    mimetype: str = "plain",
    log_message: str = "Email sent successfully!"
):
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, mimetype))
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            logger.debug(f"Logging in ...")
            logger.debug(f"{SMTP_USER=}")
            logger.debug(f"{SMTP_PASSWORD=}")            
            server.login(SMTP_USER, SMTP_PASSWORD)
            logger.debug(f"Logged in!")
            server.sendmail(sender_email, receiver_email, msg.as_string())
        logger.debug(f"{log_message}")
    except Exception as e:
        logger.debug(f"Error: {e}")
        

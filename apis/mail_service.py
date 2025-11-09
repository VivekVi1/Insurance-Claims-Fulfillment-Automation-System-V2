import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
import uvicorn

load_dotenv()

app = FastAPI()

# Email configuration
USERNAME = os.getenv("EMAIL_USERNAME")
APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

class MailRequest(BaseModel):
    mail_id: EmailStr
    subject: str
    mail_content: str

def send_email(to_email: str, subject: str, content: str):
    """Send email using SMTP"""
    try:
        if not USERNAME or not APP_PASSWORD:
            raise Exception("Email credentials not configured")
        
        msg = MIMEMultipart()
        msg['From'] = USERNAME
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(content, 'plain'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(USERNAME, APP_PASSWORD)
        server.sendmail(USERNAME, to_email, msg.as_string())
        server.quit()
        
        return True
        
    except Exception as e:
        raise e

@app.get("/")
def read_root():
    return {"status": "running"}

@app.post("/send-mail")
def send_mail(mail_request: MailRequest):
    """Send email to specified recipient"""
    try:
        send_email(
            to_email=mail_request.mail_id,
            subject=mail_request.subject,
            content=mail_request.mail_content
        )
        
        return {"success": True, "message": "Email sent"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("mail_service:app", host="0.0.0.0", port=8001, reload=True) 
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

class MailRequest(BaseModel):
    mail_id: EmailStr
    subject: str
    mail_content: str

class MailService:
    def __init__(self):
        self.username = os.getenv("EMAIL_USERNAME")
        self.app_password = os.getenv("EMAIL_APP_PASSWORD")
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
    
    def send_email(self, to_email: str, subject: str, content: str):
        """Send email using SMTP"""
        try:
            if not self.username or not self.app_password:
                raise Exception("Email credentials not configured")
            
            msg = MIMEMultipart()
            msg['From'] = self.username
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(content, 'plain'))
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.username, self.app_password)
            server.sendmail(self.username, to_email, msg.as_string())
            server.quit()
            
            return True
            
        except Exception as e:
            raise e

# Initialize mail service
mail_service = MailService()

@app.get("/")
def read_root():
    return {"status": "running"}

@app.post("/send-mail")
def send_mail(mail_request: MailRequest):
    """Send email to specified recipient"""
    try:
        mail_service.send_email(
            to_email=mail_request.mail_id,
            subject=mail_request.subject,
            content=mail_request.mail_content
        )
        
        return {"success": True, "message": "Email sent"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("mail_service:app", host="0.0.0.0", port=8001, reload=True) 
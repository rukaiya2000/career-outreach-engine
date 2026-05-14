import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from pathlib import Path
from src.config import EMAIL_ADDRESS, EMAIL_APP_PASSWORD, RESUMES_DIR


def send_email(to: str, subject: str, body: str, resume_filename: str = "") -> bool:
    try:
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = to

        msg.attach(MIMEText(body, "plain"))

        if resume_filename:
            resume_path = RESUMES_DIR / resume_filename
            if resume_path.exists():
                with open(resume_path, "rb") as f:
                    part = MIMEApplication(f.read(), _subtype="pdf")
                    part.add_header("Content-Disposition", "attachment", filename="rukaiya_khan_resume.pdf")
                    msg.attach(part)
            else:
                print(f"Warning: Resume file not found: {resume_path}")

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, [to], msg.as_string())

        return True
    except Exception as e:
        print(f"Failed to send email to {to}: {e}")
        return False

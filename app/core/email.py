import random
import resend
from .config import settings

# Initialize Resend API
if settings.RESEND_API_KEY:
    resend.api_key = settings.RESEND_API_KEY


def generate_otp() -> str:
    """Generate a 6-digit OTP code."""
    return str(random.randint(100000, 999999))


async def send_otp_email(to_email: str, otp_code: str):
    """Send OTP code via Resend API."""
    if not settings.RESEND_API_KEY:
        print(f"[DEV MODE] OTP for {to_email}: {otp_code}")
        return

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
            .otp-box {{ background: white; border: 2px dashed #667eea; padding: 20px; text-align: center; margin: 20px 0; border-radius: 8px; }}
            .otp-code {{ font-size: 32px; font-weight: bold; color: #667eea; letter-spacing: 5px; font-family: 'Courier New', monospace; }}
            .warning {{ color: #e74c3c; font-size: 14px; margin-top: 20px; }}
            .footer {{ text-align: center; color: #888; font-size: 12px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 Password Reset Request</h1>
            </div>
            <div class="content">
                <p>Hello,</p>
                <p>You have requested to reset your password. Please use the following One-Time Password (OTP) to complete the process:</p>
                
                <div class="otp-box">
                    <div class="otp-code">{otp_code}</div>
                </div>
                
                <p><strong>This code will expire in {settings.OTP_EXPIRE_MINUTES} minutes.</strong></p>
                
                <p class="warning">⚠️ If you did not request this password reset, please ignore this email and your password will remain unchanged.</p>
                
                <div class="footer">
                    <p>---</p>
                    <p>{settings.EMAIL_FROM_NAME}</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    text_body = f"""
Password Reset Request

Your OTP code is: {otp_code}

This code will expire in {settings.OTP_EXPIRE_MINUTES} minutes.

If you did not request this, please ignore this email.

---
{settings.EMAIL_FROM_NAME}
    """

    try:
        # Send email via Resend API
        email_response = resend.Emails.send({
            "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>",
            "to": to_email,
            "subject": "🔐 Password Reset OTP Code",
            "html": html_body,
            "text": text_body,
        })
        
        if email_response.get("id"):
            print(f"[EMAIL SENT] OTP sent to {to_email}, message_id={email_response['id']}")
        else:
            print(f"[EMAIL ERROR] Failed to send to {to_email}: {email_response}")
            print(f"[DEV MODE FALLBACK] OTP for {to_email}: {otp_code}")
            raise Exception(str(email_response))
            
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send to {to_email}: {str(e)}")
        print(f"[DEV MODE FALLBACK] OTP for {to_email}: {otp_code}")
        raise


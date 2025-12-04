import random
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from .config import settings

# Configure Brevo API
sib_api_v3_sdk.configuration.api_key['api-key'] = settings.BREVO_API_KEY


def generate_otp() -> str:
    """Generate a 6-digit OTP code."""
    return str(random.randint(100000, 999999))


async def send_otp_email(to_email: str, otp_code: str):
    """Send OTP code via Brevo API."""
    if not settings.BREVO_API_KEY:
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
        # Create SendSmtpEmail object
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": to_email}],
            sender={"name": settings.EMAIL_FROM_NAME, "email": settings.EMAIL_FROM_ADDRESS},
            subject="🔐 Password Reset OTP Code",
            html_content=html_body,
            text_content=text_body
        )
        
        # Send email via Brevo API
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi()
        email_response = api_instance.send_transac_email(send_smtp_email)
        
        if email_response and hasattr(email_response, 'message_id'):
            print(f"[EMAIL SENT] OTP sent to {to_email}, message_id={email_response.message_id}")
        else:
            print(f"[EMAIL SENT] OTP sent to {to_email}")
            
    except ApiException as e:
        print(f"[EMAIL ERROR] Failed to send to {to_email}: {str(e)}")
        print(f"[DEV MODE FALLBACK] OTP for {to_email}: {otp_code}")
        raise
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send to {to_email}: {str(e)}")
        print(f"[DEV MODE FALLBACK] OTP for {to_email}: {otp_code}")
        raise


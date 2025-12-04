import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Settings:
    APP_NAME: str = "Revit Key Backend"
    SQLALCHEMY_DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./revit_keys.db")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change_this_secret")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")

    # Brevo Email API
    BREVO_API_KEY: str = os.getenv("BREVO_API_KEY", "")
    EMAIL_FROM_ADDRESS: str = os.getenv("EMAIL_FROM_ADDRESS", "noreply@example.com")
    EMAIL_FROM_NAME: str = os.getenv("EMAIL_FROM_NAME", "Revit Key Management")

    OTP_EXPIRE_MINUTES: int = int(os.getenv("OTP_EXPIRE_MINUTES", "10"))

settings = Settings()

def access_token_expires():
    return timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

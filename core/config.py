"""Application configuration"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings loaded from environment variables"""
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    
    # JWT Settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "update-the-secret-key-in-production-use-env")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    
    # App Settings
    APP_TITLE: str = os.getenv("APP_TITLE", "Sandbox Manager")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"


# Global settings instance
settings = Settings()

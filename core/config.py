"""Application configuration"""
import os
import secrets
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def _validate_secret_key() -> str:
    """
    Validate SECRET_KEY is properly configured.
    
    Raises:
        ValueError: If SECRET_KEY is missing or using default insecure value
    """
    secret_key = os.getenv("SECRET_KEY")
    
    if not secret_key:
        raise ValueError(
            "SECRET_KEY is not set. Please set SECRET_KEY environment variable. "
            "Example: SECRET_KEY=$(openssl rand -hex 32)"
        )
    
    # Check if using default/placeholder value
    insecure_defaults = [
        "update-the-secret-key-in-production-use-env",
        "secret",
        "changeme",
        "your-secret-key",
    ]
    
    if secret_key in insecure_defaults:
        raise ValueError(
            f"SECRET_KEY is using an insecure default value. "
            "Please set a secure SECRET_KEY environment variable. "
            "Example: SECRET_KEY=$(openssl rand -hex 32)"
        )
    
    # Warn if key is too short
    if len(secret_key) < 32:
        raise ValueError(
            f"SECRET_KEY is too short ({len(secret_key)} characters). "
            "Use at least 32 characters for security. "
            "Example: SECRET_KEY=$(openssl rand -hex 32)"
        )
    
    return secret_key


class Settings:
    """Application settings loaded from environment variables"""

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")

    # JWT Settings - SECRET_KEY is validated at startup
    SECRET_KEY: str = _validate_secret_key()
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

    # App Settings
    APP_TITLE: str = os.getenv("APP_TITLE", "Sandbox Manager")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # Host IP for SSH jump host
    HOST_SERVER_IP: str = os.getenv("HOST_SERVER_IP", "")

    # Server Configuration
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))
    WORKERS: int = int(os.getenv("WORKERS", "2"))


# Global settings instance
settings = Settings()

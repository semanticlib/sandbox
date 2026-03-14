"""
Unit tests for security utilities.

Tests cover:
- Password hashing and verification
- JWT token creation and validation
- Edge cases and security scenarios
"""
import pytest
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError

from core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
)
from core.config import settings


class TestPasswordHashing:
    """Tests for password hashing functionality."""

    def test_verify_password_success(self):
        """Test that correct password verifies successfully."""
        password = "SecurePassword123!"
        password_hash = get_password_hash(password)
        
        assert verify_password(password, password_hash) is True

    def test_verify_password_failure(self):
        """Test that incorrect password fails verification."""
        password = "SecurePassword123!"
        wrong_password = "WrongPassword456!"
        password_hash = get_password_hash(password)
        
        assert verify_password(wrong_password, password_hash) is False

    def test_verify_password_empty_strings(self):
        """Test verification with empty strings."""
        password_hash = get_password_hash("")
        
        assert verify_password("", password_hash) is True
        assert verify_password("notempty", password_hash) is False

    def test_verify_password_special_characters(self):
        """Test verification with special characters in password."""
        password = "P@$$w0rd!#$%^&*()_+-=[]{}|;':\",./<>?"
        password_hash = get_password_hash(password)
        
        assert verify_password(password, password_hash) is True

    def test_verify_password_unicode(self):
        """Test verification with unicode characters."""
        password = "密码🔐パスワード"
        password_hash = get_password_hash(password)
        
        assert verify_password(password, password_hash) is True

    def test_hash_uniqueness(self):
        """Test that same password produces different hashes (due to salt)."""
        password = "SamePassword"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        # Hashes should be different due to random salt
        assert hash1 != hash2
        
        # But both should verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True

    def test_hash_length(self):
        """Test that hash has expected bcrypt format."""
        password = "TestPassword"
        password_hash = get_password_hash(password)
        
        # bcrypt hashes start with $2b$ or $2a$ and are 60 characters
        assert password_hash.startswith("$2")
        assert len(password_hash) == 60


class TestCreateAccessToken:
    """Tests for JWT token creation."""

    def test_create_access_token_returns_string(self):
        """Test that token is a string."""
        data = {"sub": "testuser"}
        token = create_access_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_contains_username(self):
        """Test that token contains the username in payload."""
        username = "testuser"
        data = {"sub": username}
        token = create_access_token(data)
        
        # Decode token to verify content
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == username

    def test_create_access_token_has_expiry(self):
        """Test that token has expiration claim."""
        data = {"sub": "testuser"}
        token = create_access_token(data)
        
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "exp" in payload

    def test_create_access_token_default_expiry(self):
        """Test that token expires after default time (60 minutes)."""
        data = {"sub": "testuser"}
        token = create_access_token(data)
        
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        
        # Should expire in approximately 60 minutes
        delta = exp_time - now
        assert 59 * 60 < delta.total_seconds() < 61 * 60

    def test_create_access_token_custom_expiry(self):
        """Test that custom expiry is respected."""
        data = {"sub": "testuser"}
        expires_delta = timedelta(minutes=30)
        token = create_access_token(data, expires_delta=expires_delta)
        
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        
        # Should expire in approximately 30 minutes
        delta = exp_time - now
        assert 29 * 60 < delta.total_seconds() < 31 * 60

    def test_create_access_token_additional_claims(self):
        """Test that additional data is included in token."""
        data = {
            "sub": "testuser",
            "role": "admin",
            "email": "test@example.com"
        }
        token = create_access_token(data)
        
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["role"] == "admin"
        assert payload["email"] == "test@example.com"

    def test_invalid_token_raises_error(self):
        """Test that invalid token raises JWTError."""
        with pytest.raises(JWTError):
            jwt.decode("invalid.token.here", settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    def test_tampered_token_raises_error(self):
        """Test that tampered token raises JWTError."""
        data = {"sub": "testuser"}
        token = create_access_token(data)
        
        # Tamper with the token
        tampered_token = token[:-5] + "XXXXX"
        
        with pytest.raises(JWTError):
            jwt.decode(tampered_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    def test_expired_token_validation(self):
        """Test that expired token can be detected."""
        # Create token that expired 1 minute ago
        data = {"sub": "testuser"}
        expires_delta = timedelta(minutes=-1)
        token = create_access_token(data, expires_delta=expires_delta)
        
        # Should raise ExpiredSignatureError
        with pytest.raises(JWTError):
            jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

"""
Unit tests for authentication components.

Tests user schemas, security utilities, and auth service.
"""

import pytest
from datetime import datetime, timedelta

from app.schemas.user import UserCreate, UserLogin, UserResponse, Token, TokenPayload
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    verify_token,
    generate_user_id,
)


# =============================================================================
# User Schema Tests
# =============================================================================


class TestUserCreate:
    """Tests for UserCreate schema."""
    
    def test_valid_user_create(self):
        """Test creating a valid user."""
        user = UserCreate(
            email="test@example.com",
            password="SecurePass123",
            full_name="Test User",
        )
        assert user.email == "test@example.com"
        assert user.password == "SecurePass123"
        assert user.full_name == "Test User"
    
    def test_email_validation(self):
        """Test that invalid email is rejected."""
        with pytest.raises(ValueError):
            UserCreate(
                email="not-an-email",
                password="SecurePass123",
            )
    
    def test_password_min_length(self):
        """Test password minimum length."""
        with pytest.raises(ValueError):
            UserCreate(
                email="test@example.com",
                password="Short1",  # Too short
            )
    
    def test_password_requires_uppercase(self):
        """Test password requires uppercase letter."""
        with pytest.raises(ValueError):
            UserCreate(
                email="test@example.com",
                password="lowercase123",
            )
    
    def test_password_requires_lowercase(self):
        """Test password requires lowercase letter."""
        with pytest.raises(ValueError):
            UserCreate(
                email="test@example.com",
                password="UPPERCASE123",
            )
    
    def test_password_requires_digit(self):
        """Test password requires digit."""
        with pytest.raises(ValueError):
            UserCreate(
                email="test@example.com",
                password="NoDigitsHere",
            )


class TestUserLogin:
    """Tests for UserLogin schema."""
    
    def test_valid_login(self):
        """Test valid login credentials."""
        login = UserLogin(
            email="test@example.com",
            password="anypassword",
        )
        assert login.email == "test@example.com"
        assert login.password == "anypassword"


class TestUserResponse:
    """Tests for UserResponse schema."""
    
    def test_user_response(self):
        """Test user response creation."""
        response = UserResponse(
            id="user_abc123",
            email="test@example.com",
            full_name="Test User",
            is_active=True,
            created_at=datetime.utcnow(),
        )
        assert response.id == "user_abc123"
        assert response.email == "test@example.com"


class TestToken:
    """Tests for Token schema."""
    
    def test_token_creation(self):
        """Test token response creation."""
        token = Token(
            access_token="eyJ...",
            token_type="bearer",
            expires_in=3600,
        )
        assert token.access_token == "eyJ..."
        assert token.token_type == "bearer"
        assert token.expires_in == 3600


# =============================================================================
# Security Utility Tests
# =============================================================================


class TestPasswordHashing:
    """Tests for password hashing utilities."""
    
    def test_hash_password(self):
        """Test password hashing."""
        password = "SecurePassword123"
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert len(hashed) > 0
    
    def test_verify_correct_password(self):
        """Test verifying correct password."""
        password = "SecurePassword123"
        hashed = get_password_hash(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_incorrect_password(self):
        """Test verifying incorrect password."""
        password = "SecurePassword123"
        hashed = get_password_hash(password)
        
        assert verify_password("WrongPassword123", hashed) is False
    
    def test_different_hashes_for_same_password(self):
        """Test that same password produces different hashes (salting)."""
        password = "SecurePassword123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        assert hash1 != hash2
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestJWTTokens:
    """Tests for JWT token utilities."""
    
    def test_create_access_token(self):
        """Test creating access token."""
        token = create_access_token(subject="user_123")
        
        assert token
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_verify_valid_token(self):
        """Test verifying valid token."""
        token = create_access_token(subject="user_123")
        payload = verify_token(token)
        
        assert payload is not None
        assert payload["sub"] == "user_123"
        assert "exp" in payload
        assert "iat" in payload
    
    def test_verify_invalid_token(self):
        """Test verifying invalid token."""
        payload = verify_token("invalid.token.here")
        assert payload is None
    
    def test_token_with_custom_expiry(self):
        """Test creating token with custom expiration."""
        token = create_access_token(
            subject="user_123",
            expires_delta=timedelta(hours=1),
        )
        payload = verify_token(token)
        
        assert payload is not None
        # Token should have an expiration time set
        assert "exp" in payload
        # Verify token expiration is in the future
        exp_time = datetime.fromtimestamp(payload["exp"])
        now = datetime.utcnow()
        assert exp_time > now
    
    def test_token_with_additional_claims(self):
        """Test creating token with additional claims."""
        token = create_access_token(
            subject="user_123",
            additional_claims={"email": "test@example.com", "role": "admin"},
        )
        payload = verify_token(token)
        
        assert payload["email"] == "test@example.com"
        assert payload["role"] == "admin"


class TestUserIdGeneration:
    """Tests for user ID generation."""
    
    def test_generate_user_id(self):
        """Test generating user ID."""
        user_id = generate_user_id()
        
        assert user_id.startswith("user_")
        assert len(user_id) == 17  # "user_" + 12 hex chars
    
    def test_unique_user_ids(self):
        """Test that generated IDs are unique."""
        ids = [generate_user_id() for _ in range(100)]
        assert len(ids) == len(set(ids))  # All unique


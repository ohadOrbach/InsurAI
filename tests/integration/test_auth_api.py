"""
Integration tests for Authentication API endpoints.

Tests user registration, login, and profile management.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base, engine


@pytest.fixture(scope="module")
def client():
    """Create a test client with fresh database."""
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    with TestClient(app) as c:
        yield c
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user_data():
    """Sample user data for testing."""
    return {
        "email": "test@example.com",
        "password": "SecurePass123",
        "full_name": "Test User",
    }


# =============================================================================
# Registration Tests
# =============================================================================


class TestRegistration:
    """Tests for user registration."""
    
    def test_register_success(self, client, test_user_data):
        """Test successful user registration."""
        response = client.post(
            "/api/v1/auth/register",
            json=test_user_data,
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == test_user_data["email"]
        assert data["full_name"] == test_user_data["full_name"]
        assert "id" in data
        assert data["is_active"] is True
    
    def test_register_duplicate_email(self, client, test_user_data):
        """Test registration with duplicate email."""
        # First registration
        client.post("/api/v1/auth/register", json=test_user_data)
        
        # Second registration with same email
        response = client.post(
            "/api/v1/auth/register",
            json=test_user_data,
        )
        
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()
    
    def test_register_invalid_email(self, client):
        """Test registration with invalid email."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "SecurePass123",
            },
        )
        
        assert response.status_code == 422
    
    def test_register_weak_password(self, client):
        """Test registration with weak password."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "weak@example.com",
                "password": "weak",
            },
        )
        
        assert response.status_code == 422


# =============================================================================
# Login Tests
# =============================================================================


class TestLogin:
    """Tests for user login."""
    
    @pytest.fixture(autouse=True)
    def setup_user(self, client):
        """Create a test user before login tests."""
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "login@example.com",
                "password": "SecurePass123",
                "full_name": "Login User",
            },
        )
    
    def test_login_success_form(self, client):
        """Test successful login with form data."""
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "login@example.com",
                "password": "SecurePass123",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
    
    def test_login_success_json(self, client):
        """Test successful login with JSON body."""
        response = client.post(
            "/api/v1/auth/login/json",
            json={
                "email": "login@example.com",
                "password": "SecurePass123",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
    
    def test_login_wrong_password(self, client):
        """Test login with wrong password."""
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "login@example.com",
                "password": "WrongPassword123",
            },
        )
        
        assert response.status_code == 401
    
    def test_login_nonexistent_user(self, client):
        """Test login with nonexistent email."""
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "nonexistent@example.com",
                "password": "SecurePass123",
            },
        )
        
        assert response.status_code == 401


# =============================================================================
# Protected Routes Tests
# =============================================================================


class TestProtectedRoutes:
    """Tests for protected routes requiring authentication."""
    
    @pytest.fixture
    def auth_headers(self, client):
        """Get authentication headers."""
        # Register and login
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "protected@example.com",
                "password": "SecurePass123",
                "full_name": "Protected User",
            },
        )
        
        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "protected@example.com",
                "password": "SecurePass123",
            },
        )
        
        token = login_response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_me_authenticated(self, client, auth_headers):
        """Test getting current user profile when authenticated."""
        response = client.get(
            "/api/v1/auth/me",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "protected@example.com"
        assert data["full_name"] == "Protected User"
    
    def test_get_me_unauthenticated(self, client):
        """Test getting current user without authentication."""
        response = client.get("/api/v1/auth/me")
        
        assert response.status_code == 401
    
    def test_get_me_invalid_token(self, client):
        """Test getting current user with invalid token."""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        
        assert response.status_code == 401
    
    def test_verify_token(self, client, auth_headers):
        """Test token verification endpoint."""
        response = client.get(
            "/api/v1/auth/verify",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert "user_id" in data
    
    def test_logout(self, client, auth_headers):
        """Test logout endpoint."""
        response = client.post(
            "/api/v1/auth/logout",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        assert response.json()["success"] is True


# =============================================================================
# Update Profile Tests
# =============================================================================


class TestUpdateProfile:
    """Tests for updating user profile."""
    
    @pytest.fixture
    def auth_headers(self, client):
        """Get authentication headers."""
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "update@example.com",
                "password": "SecurePass123",
                "full_name": "Original Name",
            },
        )
        
        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "update@example.com",
                "password": "SecurePass123",
            },
        )
        
        token = login_response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_update_full_name(self, client, auth_headers):
        """Test updating user's full name."""
        response = client.put(
            "/api/v1/auth/me",
            headers=auth_headers,
            params={"full_name": "Updated Name"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "Updated Name"


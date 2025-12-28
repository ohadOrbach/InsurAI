"""
Integration tests for Chat API endpoints.

Tests the chat session management, messaging, and quick chat functionality.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


# =============================================================================
# Chat Session Tests
# =============================================================================


class TestChatSessions:
    """Tests for chat session management."""
    
    def test_create_session(self, client):
        """Test creating a new chat session."""
        response = client.post("/api/v1/chat/sessions")
        
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "session_id" in data
        assert "suggested_questions" in data
        assert isinstance(data["suggested_questions"], list)
    
    def test_create_session_with_policy(self, client):
        """Test creating a session with a policy ID."""
        response = client.post(
            "/api/v1/chat/sessions",
            json={"policy_id": "POL-TEST-123"},
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["policy_id"] == "POL-TEST-123"
    
    def test_get_session_history(self, client):
        """Test retrieving session history."""
        # First create a session
        create_response = client.post("/api/v1/chat/sessions")
        session_id = create_response.json()["session_id"]
        
        # Get the session history
        response = client.get(f"/api/v1/chat/sessions/{session_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["session_id"] == session_id
        assert data["message_count"] == 0
        assert data["messages"] == []
    
    def test_get_nonexistent_session(self, client):
        """Test getting a non-existent session."""
        response = client.get("/api/v1/chat/sessions/nonexistent-id")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# =============================================================================
# Chat Message Tests
# =============================================================================


class TestChatMessages:
    """Tests for chat messaging."""
    
    @pytest.fixture
    def session_id(self, client):
        """Create a session and return its ID."""
        response = client.post("/api/v1/chat/sessions")
        return response.json()["session_id"]
    
    def test_send_message(self, client, session_id):
        """Test sending a chat message."""
        response = client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"message": "Hello, what is covered?"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["session_id"] == session_id
        assert "message" in data
        assert data["message"]["role"] == "assistant"
        assert data["message"]["content"]
    
    def test_send_message_updates_history(self, client, session_id):
        """Test that sending a message updates history."""
        # Send a message
        client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"message": "Hello"},
        )
        
        # Check history
        history = client.get(f"/api/v1/chat/sessions/{session_id}").json()
        
        # Should have user message + assistant response
        assert history["message_count"] == 2
        assert history["messages"][0]["role"] == "user"
        assert history["messages"][1]["role"] == "assistant"
    
    def test_send_message_to_invalid_session(self, client):
        """Test sending a message to an invalid session."""
        response = client.post(
            "/api/v1/chat/sessions/invalid-session/messages",
            json={"message": "Hello"},
        )
        
        assert response.status_code == 404
    
    def test_send_empty_message(self, client, session_id):
        """Test sending an empty message."""
        response = client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"message": ""},
        )
        
        # Should fail validation (min_length=1)
        assert response.status_code == 422
    
    def test_conversation_context(self, client, session_id):
        """Test that conversation maintains context."""
        # Send first message
        client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"message": "Is my engine covered?"},
        )
        
        # Send follow-up
        response = client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"message": "What about the transmission?"},
        )
        
        assert response.status_code == 200
        
        # History should have 4 messages now
        history = client.get(f"/api/v1/chat/sessions/{session_id}").json()
        assert history["message_count"] == 4


# =============================================================================
# Quick Chat Tests
# =============================================================================


class TestQuickChat:
    """Tests for quick chat endpoint."""
    
    def test_quick_chat(self, client):
        """Test quick chat without session."""
        response = client.post(
            "/api/v1/chat/ask",
            json={"message": "Is my engine covered?"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["question"] == "Is my engine covered?"
        assert "answer" in data
        assert data["answer"]
    
    def test_quick_chat_coverage_detection(self, client):
        """Test that quick chat detects coverage status."""
        response = client.post(
            "/api/v1/chat/ask",
            json={"message": "Is turbo covered?"},
        )
        
        data = response.json()
        # May or may not have coverage status detected
        assert "coverage_status" in data
    
    def test_quick_chat_empty_message(self, client):
        """Test quick chat with empty message."""
        response = client.post(
            "/api/v1/chat/ask",
            json={"message": ""},
        )
        
        assert response.status_code == 422


# =============================================================================
# Suggestions Tests
# =============================================================================


class TestSuggestions:
    """Tests for suggestions endpoint."""
    
    def test_get_suggestions(self, client):
        """Test getting suggested questions."""
        response = client.get("/api/v1/chat/suggestions")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)
        assert len(data["suggestions"]) > 0


# =============================================================================
# Message Response Format Tests
# =============================================================================


class TestMessageResponseFormat:
    """Tests for message response format."""
    
    @pytest.fixture
    def session_id(self, client):
        """Create a session and return its ID."""
        response = client.post("/api/v1/chat/sessions")
        return response.json()["session_id"]
    
    def test_message_response_structure(self, client, session_id):
        """Test message response has correct structure."""
        response = client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"message": "Hello"},
        )
        
        data = response.json()
        message = data["message"]
        
        assert "id" in message
        assert "role" in message
        assert "content" in message
        assert "timestamp" in message
        assert "metadata" in message
    
    def test_message_timestamp_format(self, client, session_id):
        """Test that timestamp is in ISO format."""
        response = client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"message": "Hello"},
        )
        
        timestamp = response.json()["message"]["timestamp"]
        
        # Should be ISO format
        from datetime import datetime
        # Should not raise
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


# =============================================================================
# Coverage Question Tests
# =============================================================================


class TestCoverageQuestions:
    """Tests for coverage-related questions."""
    
    @pytest.fixture
    def session_id(self, client):
        """Create a session and return its ID."""
        response = client.post("/api/v1/chat/sessions")
        return response.json()["session_id"]
    
    def test_engine_coverage_question(self, client, session_id):
        """Test asking about engine coverage."""
        response = client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"message": "Is my engine covered under the warranty?"},
        )
        
        assert response.status_code == 200
        content = response.json()["message"]["content"]
        # Response should mention coverage or policy
        assert any(
            word in content.lower()
            for word in ["cover", "policy", "engine", "warranty"]
        )
    
    def test_exclusion_question(self, client, session_id):
        """Test asking about exclusions."""
        response = client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"message": "What items are excluded from my coverage?"},
        )
        
        assert response.status_code == 200
        content = response.json()["message"]["content"]
        assert any(
            word in content.lower()
            for word in ["exclusion", "exclude", "not cover", "policy"]
        )
    
    def test_deductible_question(self, client, session_id):
        """Test asking about deductibles."""
        response = client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"message": "What is my deductible for repairs?"},
        )
        
        assert response.status_code == 200
        content = response.json()["message"]["content"]
        assert "deductible" in content.lower()


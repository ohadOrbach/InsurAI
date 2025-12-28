"""
Unit tests for Repository pattern implementation.

Tests the base repository and specialized repositories.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from app.repositories.base import BaseRepository
from app.repositories.user import UserRepository
from app.repositories.policy import PolicyRepository
from app.repositories.chat import ChatSessionRepository, ChatMessageRepository
from app.db.models import User, Policy, ChatSession, ChatMessage
from app.db.base import Base, engine, SessionLocal


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def db_session():
    """Create a database session for testing."""
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    session = SessionLocal()
    yield session
    
    # Cleanup
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def user_repo(db_session):
    """Create a UserRepository instance."""
    return UserRepository(db_session)


@pytest.fixture
def policy_repo(db_session):
    """Create a PolicyRepository instance."""
    return PolicyRepository(db_session)


@pytest.fixture
def chat_session_repo(db_session):
    """Create a ChatSessionRepository instance."""
    return ChatSessionRepository(db_session)


@pytest.fixture
def chat_message_repo(db_session):
    """Create a ChatMessageRepository instance."""
    return ChatMessageRepository(db_session)


# =============================================================================
# UserRepository Tests
# =============================================================================


class TestUserRepository:
    """Tests for UserRepository."""
    
    def test_create_user(self, user_repo):
        """Test creating a new user."""
        user = user_repo.create_user(
            email="repo_test@example.com",
            password="SecurePass123",
            full_name="Repo Test User",
        )
        
        assert user.id is not None
        assert user.email == "repo_test@example.com"
        assert user.full_name == "Repo Test User"
        assert user.is_active is True
        assert user.hashed_password != "SecurePass123"  # Should be hashed
    
    def test_get_by_email(self, user_repo):
        """Test getting user by email."""
        # Create user
        user_repo.create_user(
            email="email_lookup@example.com",
            password="SecurePass123",
        )
        
        # Lookup
        found = user_repo.get_by_email("email_lookup@example.com")
        assert found is not None
        assert found.email == "email_lookup@example.com"
        
        # Case insensitive
        found_upper = user_repo.get_by_email("EMAIL_LOOKUP@EXAMPLE.COM")
        assert found_upper is not None
    
    def test_email_exists(self, user_repo):
        """Test email existence check."""
        user_repo.create_user(
            email="exists_check@example.com",
            password="SecurePass123",
        )
        
        assert user_repo.email_exists("exists_check@example.com") is True
        assert user_repo.email_exists("nonexistent@example.com") is False
    
    def test_duplicate_email_raises(self, user_repo):
        """Test that duplicate email raises error."""
        user_repo.create_user(
            email="duplicate@example.com",
            password="SecurePass123",
        )
        
        with pytest.raises(ValueError) as exc_info:
            user_repo.create_user(
                email="duplicate@example.com",
                password="AnotherPass123",
            )
        
        assert "already registered" in str(exc_info.value)
    
    def test_authenticate_success(self, user_repo):
        """Test successful authentication."""
        user_repo.create_user(
            email="auth_test@example.com",
            password="SecurePass123",
        )
        
        user = user_repo.authenticate("auth_test@example.com", "SecurePass123")
        assert user is not None
        assert user.email == "auth_test@example.com"
    
    def test_authenticate_wrong_password(self, user_repo):
        """Test authentication with wrong password."""
        user_repo.create_user(
            email="auth_wrong@example.com",
            password="SecurePass123",
        )
        
        user = user_repo.authenticate("auth_wrong@example.com", "WrongPass123")
        assert user is None
    
    def test_authenticate_inactive_user(self, user_repo):
        """Test authentication of inactive user."""
        user = user_repo.create_user(
            email="inactive@example.com",
            password="SecurePass123",
        )
        
        user_repo.deactivate_user(user.id)
        
        result = user_repo.authenticate("inactive@example.com", "SecurePass123")
        assert result is None
    
    def test_update_password(self, user_repo):
        """Test password update."""
        user = user_repo.create_user(
            email="password_update@example.com",
            password="OldPassword123",
        )
        
        user_repo.update_password(user.id, "NewPassword123")
        
        # Old password should fail
        assert user_repo.authenticate("password_update@example.com", "OldPassword123") is None
        
        # New password should work
        assert user_repo.authenticate("password_update@example.com", "NewPassword123") is not None
    
    def test_activate_deactivate(self, user_repo):
        """Test user activation and deactivation."""
        user = user_repo.create_user(
            email="activate_test@example.com",
            password="SecurePass123",
        )
        
        assert user.is_active is True
        
        user_repo.deactivate_user(user.id)
        user = user_repo.get_by_id(user.id)
        assert user.is_active is False
        
        user_repo.activate_user(user.id)
        user = user_repo.get_by_id(user.id)
        assert user.is_active is True


# =============================================================================
# PolicyRepository Tests
# =============================================================================


class TestPolicyRepository:
    """Tests for PolicyRepository."""
    
    def test_create_policy(self, policy_repo):
        """Test creating a new policy."""
        policy = policy_repo.create_policy(
            policy_id="POL-REPO-001",
            provider_name="Test Insurance Co.",
            policy_type="Mechanical Warranty",
            policy_data={"coverage": ["engine", "transmission"]},
        )
        
        assert policy.id is not None
        assert policy.policy_id == "POL-REPO-001"
        assert policy.status == "active"
    
    def test_get_by_policy_id(self, policy_repo):
        """Test getting policy by external ID."""
        policy_repo.create_policy(
            policy_id="POL-LOOKUP-001",
            provider_name="Test Insurance",
            policy_type="Warranty",
            policy_data={},
        )
        
        found = policy_repo.get_by_policy_id("POL-LOOKUP-001")
        assert found is not None
        assert found.policy_id == "POL-LOOKUP-001"
    
    def test_policy_id_exists(self, policy_repo):
        """Test policy ID existence check."""
        policy_repo.create_policy(
            policy_id="POL-EXISTS-001",
            provider_name="Test",
            policy_type="Test",
            policy_data={},
        )
        
        assert policy_repo.policy_id_exists("POL-EXISTS-001") is True
        assert policy_repo.policy_id_exists("POL-NONEXISTENT") is False
    
    def test_duplicate_policy_id_raises(self, policy_repo):
        """Test that duplicate policy ID raises error."""
        policy_repo.create_policy(
            policy_id="POL-DUP-001",
            provider_name="Test",
            policy_type="Test",
            policy_data={},
        )
        
        with pytest.raises(ValueError) as exc_info:
            policy_repo.create_policy(
                policy_id="POL-DUP-001",
                provider_name="Other",
                policy_type="Other",
                policy_data={},
            )
        
        assert "already exists" in str(exc_info.value)
    
    def test_update_status(self, policy_repo):
        """Test updating policy status."""
        policy = policy_repo.create_policy(
            policy_id="POL-STATUS-001",
            provider_name="Test",
            policy_type="Test",
            policy_data={},
        )
        
        assert policy.status == "active"
        
        policy_repo.update_status(policy.id, "expired")
        policy = policy_repo.get_by_id(policy.id)
        
        assert policy.status == "expired"
    
    def test_get_active_policies(self, policy_repo):
        """Test getting active policies."""
        # Create active policy
        policy_repo.create_policy(
            policy_id="POL-ACTIVE-001",
            provider_name="Test",
            policy_type="Test",
            policy_data={},
        )
        
        active = policy_repo.get_active_policies()
        assert len(active) >= 1
        assert all(p.status == "active" for p in active)


# =============================================================================
# ChatSessionRepository Tests
# =============================================================================


class TestChatSessionRepository:
    """Tests for ChatSessionRepository."""
    
    def test_create_session(self, chat_session_repo):
        """Test creating a new session."""
        session = chat_session_repo.create_session(
            title="Test Session",
        )
        
        assert session.id is not None
        assert session.title == "Test Session"
        assert session.is_active is True
    
    def test_close_session(self, chat_session_repo):
        """Test closing a session."""
        session = chat_session_repo.create_session()
        
        assert session.is_active is True
        
        chat_session_repo.close_session(session.id)
        session = chat_session_repo.get_by_id(session.id)
        
        assert session.is_active is False
    
    def test_touch_session(self, chat_session_repo):
        """Test updating session timestamp."""
        session = chat_session_repo.create_session()
        original_updated = session.updated_at
        
        import time
        time.sleep(0.1)  # Small delay
        
        chat_session_repo.touch_session(session.id)
        session = chat_session_repo.get_by_id(session.id)
        
        assert session.updated_at >= original_updated


# =============================================================================
# ChatMessageRepository Tests
# =============================================================================


class TestChatMessageRepository:
    """Tests for ChatMessageRepository."""
    
    @pytest.fixture
    def test_session(self, chat_session_repo):
        """Create a test session for message tests."""
        return chat_session_repo.create_session(title="Message Test Session")
    
    def test_add_message(self, chat_message_repo, test_session):
        """Test adding a message."""
        message = chat_message_repo.add_message(
            session_id=test_session.id,
            role="user",
            content="Hello, world!",
        )
        
        assert message.id is not None
        assert message.session_id == test_session.id
        assert message.role == "user"
        assert message.content == "Hello, world!"
    
    def test_add_user_message(self, chat_message_repo, test_session):
        """Test adding a user message."""
        message = chat_message_repo.add_user_message(
            session_id=test_session.id,
            content="User message",
        )
        
        assert message.role == "user"
    
    def test_add_assistant_message(self, chat_message_repo, test_session):
        """Test adding an assistant message."""
        message = chat_message_repo.add_assistant_message(
            session_id=test_session.id,
            content="Assistant response",
            model="gpt-4",
            usage={"tokens": 100},
        )
        
        assert message.role == "assistant"
        assert message.message_metadata["model"] == "gpt-4"
    
    def test_get_by_session(self, chat_message_repo, test_session):
        """Test getting messages by session."""
        chat_message_repo.add_user_message(test_session.id, "First")
        chat_message_repo.add_assistant_message(test_session.id, "Second")
        chat_message_repo.add_user_message(test_session.id, "Third")
        
        messages = chat_message_repo.get_by_session(test_session.id)
        
        assert len(messages) >= 3
        # Should be in chronological order
        assert messages[0].content == "First"
    
    def test_get_last_messages(self, chat_message_repo, test_session):
        """Test getting last N messages."""
        for i in range(5):
            chat_message_repo.add_user_message(test_session.id, f"Message {i}")
        
        last_messages = chat_message_repo.get_last_messages(test_session.id, count=3)
        
        assert len(last_messages) == 3
        # Should be oldest to newest within the selection
        assert "2" in last_messages[0].content or "3" in last_messages[0].content
    
    def test_count_by_session(self, chat_message_repo, test_session):
        """Test counting messages in session."""
        initial_count = chat_message_repo.count_by_session(test_session.id)
        
        chat_message_repo.add_user_message(test_session.id, "Count test 1")
        chat_message_repo.add_user_message(test_session.id, "Count test 2")
        
        new_count = chat_message_repo.count_by_session(test_session.id)
        assert new_count == initial_count + 2
    
    def test_get_by_role(self, chat_message_repo, test_session):
        """Test getting messages by role."""
        chat_message_repo.add_user_message(test_session.id, "User 1")
        chat_message_repo.add_assistant_message(test_session.id, "Assistant 1")
        chat_message_repo.add_user_message(test_session.id, "User 2")
        
        user_messages = chat_message_repo.get_by_role(test_session.id, "user")
        
        assert all(m.role == "user" for m in user_messages)


# =============================================================================
# Base Repository Tests
# =============================================================================


class TestBaseRepositoryOperations:
    """Tests for base repository operations using UserRepository."""
    
    def test_get_by_id(self, user_repo):
        """Test getting by ID."""
        user = user_repo.create_user(
            email="get_by_id@example.com",
            password="SecurePass123",
        )
        
        found = user_repo.get_by_id(user.id)
        assert found is not None
        assert found.id == user.id
    
    def test_get_by_id_not_found(self, user_repo):
        """Test getting non-existent ID."""
        found = user_repo.get_by_id("nonexistent-id")
        assert found is None
    
    def test_exists(self, user_repo):
        """Test existence check."""
        user = user_repo.create_user(
            email="exists_test@example.com",
            password="SecurePass123",
        )
        
        assert user_repo.exists(user.id) is True
        assert user_repo.exists("fake-id") is False
    
    def test_count(self, user_repo):
        """Test counting records."""
        initial_count = user_repo.count()
        
        user_repo.create_user(email="count1@example.com", password="SecurePass123")
        user_repo.create_user(email="count2@example.com", password="SecurePass123")
        
        new_count = user_repo.count()
        assert new_count == initial_count + 2
    
    def test_delete(self, user_repo):
        """Test deleting a record."""
        user = user_repo.create_user(
            email="delete_test@example.com",
            password="SecurePass123",
        )
        
        user_id = user.id
        assert user_repo.exists(user_id) is True
        
        result = user_repo.delete(user_id)
        assert result is True
        assert user_repo.exists(user_id) is False
    
    def test_delete_not_found(self, user_repo):
        """Test deleting non-existent record."""
        result = user_repo.delete("nonexistent-id")
        assert result is False
    
    def test_get_all_with_pagination(self, user_repo):
        """Test getting all with pagination."""
        # Create some users
        for i in range(5):
            user_repo.create_user(
                email=f"pagination{i}@example.com",
                password="SecurePass123",
            )
        
        page1 = user_repo.get_all(skip=0, limit=3)
        page2 = user_repo.get_all(skip=3, limit=3)
        
        assert len(page1) == 3
        # IDs should be different between pages
        page1_ids = {u.id for u in page1}
        page2_ids = {u.id for u in page2}
        assert page1_ids.isdisjoint(page2_ids)


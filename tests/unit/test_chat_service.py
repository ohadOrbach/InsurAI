"""
Unit tests for Chat Service.

Tests the ChatService which integrates RAG, Policy Engine, and LLM
for intelligent insurance policy assistance.
"""

import pytest
from datetime import datetime

from app.services.chat_service import (
    MessageRole,
    ChatMessage,
    ChatSession,
    ChatService,
    get_chat_service,
    INSURANCE_AGENT_SYSTEM_PROMPT,
)
from app.services.llm_service import LLMProvider
from app.services.policy_engine import PolicyEngine


# =============================================================================
# MessageRole Enum Tests
# =============================================================================


class TestMessageRole:
    """Tests for MessageRole enum."""
    
    def test_role_values(self):
        """Test that all expected roles exist."""
        assert MessageRole.USER == "user"
        assert MessageRole.ASSISTANT == "assistant"
        assert MessageRole.SYSTEM == "system"
    
    def test_role_count(self):
        """Test that we have the expected number of roles."""
        assert len(MessageRole) == 3


# =============================================================================
# ChatMessage Tests
# =============================================================================


class TestChatMessage:
    """Tests for ChatMessage dataclass."""
    
    def test_create_user_message(self):
        """Test creating a user message."""
        msg = ChatMessage.create(MessageRole.USER, "Hello")
        
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello"
        assert msg.id
        assert isinstance(msg.timestamp, datetime)
        assert msg.metadata == {}
    
    def test_create_assistant_message(self):
        """Test creating an assistant message."""
        msg = ChatMessage.create(MessageRole.ASSISTANT, "How can I help?")
        
        assert msg.role == MessageRole.ASSISTANT
        assert msg.content == "How can I help?"
    
    def test_create_with_metadata(self):
        """Test creating message with metadata."""
        msg = ChatMessage.create(
            MessageRole.ASSISTANT,
            "Response",
            model="gpt-4",
            tokens=100,
        )
        
        assert msg.metadata["model"] == "gpt-4"
        assert msg.metadata["tokens"] == 100
    
    def test_unique_ids(self):
        """Test that messages have unique IDs."""
        msg1 = ChatMessage.create(MessageRole.USER, "First")
        msg2 = ChatMessage.create(MessageRole.USER, "Second")
        
        assert msg1.id != msg2.id


# =============================================================================
# ChatSession Tests
# =============================================================================


class TestChatSession:
    """Tests for ChatSession dataclass."""
    
    def test_create_session(self):
        """Test creating a basic session."""
        session = ChatSession.create()
        
        assert session.id
        assert session.policy_id is None
        assert session.messages == []
        assert isinstance(session.created_at, datetime)
    
    def test_create_session_with_policy(self):
        """Test creating a session with policy ID."""
        session = ChatSession.create(policy_id="POL-123")
        
        assert session.policy_id == "POL-123"
    
    def test_unique_session_ids(self):
        """Test that sessions have unique IDs."""
        s1 = ChatSession.create()
        s2 = ChatSession.create()
        
        assert s1.id != s2.id


# =============================================================================
# ChatService Tests
# =============================================================================


class TestChatService:
    """Tests for ChatService."""
    
    @pytest.fixture
    def chat_service(self):
        """Create a ChatService instance with mock LLM."""
        return ChatService(llm_provider=LLMProvider.MOCK)
    
    def test_initialization(self, chat_service):
        """Test that chat service initializes correctly."""
        assert chat_service.llm is not None
        assert chat_service.policy_engine is not None
        assert chat_service.vectorizer is not None
    
    def test_create_session(self, chat_service):
        """Test creating a chat session."""
        session = chat_service.create_session()
        
        assert session.id
        assert session.policy_id is None
        assert session in chat_service._sessions.values()
    
    def test_create_session_with_policy(self, chat_service):
        """Test creating a session linked to a policy."""
        session = chat_service.create_session(policy_id="POL-TEST-123")
        
        assert session.policy_id == "POL-TEST-123"
    
    def test_get_session(self, chat_service):
        """Test retrieving a session."""
        session = chat_service.create_session()
        
        retrieved = chat_service.get_session(session.id)
        assert retrieved == session
    
    def test_get_nonexistent_session(self, chat_service):
        """Test retrieving a non-existent session."""
        result = chat_service.get_session("nonexistent-id")
        assert result is None
    
    def test_get_suggested_questions(self, chat_service):
        """Test getting suggested questions."""
        suggestions = chat_service.get_suggested_questions()
        
        assert isinstance(suggestions, list)
        assert len(suggestions) > 0
        assert all(isinstance(q, str) for q in suggestions)
    
    def test_suggested_questions_based_on_categories(self, chat_service):
        """Test that suggestions reflect policy categories."""
        suggestions = chat_service.get_suggested_questions()
        
        # Should have at least some generic questions
        generic_questions = [
            "What is covered under my policy?",
            "What are the main exclusions I should know about?",
        ]
        for q in generic_questions:
            assert q in suggestions
    
    @pytest.mark.asyncio
    async def test_chat_basic(self, chat_service):
        """Test basic chat functionality."""
        session = chat_service.create_session()
        
        response = await chat_service.chat(session.id, "Hello")
        
        assert isinstance(response, ChatMessage)
        assert response.role == MessageRole.ASSISTANT
        assert response.content
    
    @pytest.mark.asyncio
    async def test_chat_adds_messages_to_session(self, chat_service):
        """Test that chat adds messages to session history."""
        session = chat_service.create_session()
        
        await chat_service.chat(session.id, "Hello")
        
        # Should have user message and assistant response
        assert len(session.messages) == 2
        assert session.messages[0].role == MessageRole.USER
        assert session.messages[1].role == MessageRole.ASSISTANT
    
    @pytest.mark.asyncio
    async def test_chat_coverage_question(self, chat_service):
        """Test asking about coverage."""
        session = chat_service.create_session()
        
        response = await chat_service.chat(
            session.id,
            "Is my engine covered under the warranty?"
        )
        
        assert response.content
        # Response should relate to coverage
        assert any(word in response.content.lower() for word in ["cover", "policy", "engine"])
    
    @pytest.mark.asyncio
    async def test_chat_invalid_session(self, chat_service):
        """Test chat with invalid session ID."""
        with pytest.raises(ValueError) as exc_info:
            await chat_service.chat("invalid-session", "Hello")
        
        assert "Session not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_chat_stream(self, chat_service):
        """Test streaming chat response."""
        session = chat_service.create_session()
        
        tokens = []
        async for token in chat_service.chat_stream(session.id, "Hello"):
            tokens.append(token)
        
        # Should receive multiple tokens
        assert len(tokens) > 1
        
        # Session should have messages added
        assert len(session.messages) == 2
    
    @pytest.mark.asyncio
    async def test_chat_stream_invalid_session(self, chat_service):
        """Test streaming chat with invalid session."""
        with pytest.raises(ValueError):
            async for _ in chat_service.chat_stream("invalid", "Hello"):
                pass


# =============================================================================
# Context Building Tests
# =============================================================================


class TestContextBuilding:
    """Tests for chat service context building."""
    
    @pytest.fixture
    def chat_service(self):
        """Create a ChatService instance."""
        return ChatService(llm_provider=LLMProvider.MOCK)
    
    def test_build_context_returns_string(self, chat_service):
        """Test that context building returns a string."""
        context = chat_service._build_context("What is covered?")
        
        assert isinstance(context, str)
        assert len(context) > 0
    
    def test_build_context_includes_policy_info(self, chat_service):
        """Test that context includes policy information."""
        context = chat_service._build_context("Test question")
        
        assert "POLICY INFORMATION" in context
        assert "Policy ID" in context
    
    def test_build_context_for_coverage_question(self, chat_service):
        """Test context building for coverage questions."""
        context = chat_service._build_context("Is my engine covered?")
        
        # Should include coverage check results for 'engine'
        # The mock should detect and check coverage
        assert "engine" in context.lower() or "COVERAGE" in context


# =============================================================================
# Coverage Extraction Tests
# =============================================================================


class TestCoverageExtraction:
    """Tests for coverage extraction from messages."""
    
    @pytest.fixture
    def chat_service(self):
        """Create a ChatService instance."""
        return ChatService(llm_provider=LLMProvider.MOCK)
    
    def test_extract_engine_coverage(self, chat_service):
        """Test extracting and checking engine coverage."""
        results = chat_service._extract_and_check_coverage(
            "Is my engine covered?"
        )
        
        assert len(results) > 0
        # Should find 'engine' item
        items = [r.item_name.lower() for r in results]
        assert "engine" in items
    
    def test_extract_multiple_items(self, chat_service):
        """Test extracting multiple items."""
        results = chat_service._extract_and_check_coverage(
            "Are engine and transmission covered?"
        )
        
        assert len(results) >= 2
        items = [r.item_name.lower() for r in results]
        assert "engine" in items
        assert "transmission" in items
    
    def test_extract_no_items(self, chat_service):
        """Test extraction when no known items present."""
        results = chat_service._extract_and_check_coverage(
            "Hello, how are you?"
        )
        
        assert len(results) == 0
    
    def test_extract_limits_results(self, chat_service):
        """Test that extraction limits to 3 items."""
        results = chat_service._extract_and_check_coverage(
            "Are engine, transmission, turbo, alternator, and battery covered?"
        )
        
        # Should be limited to 3
        assert len(results) <= 3


# =============================================================================
# Global Service Tests
# =============================================================================


class TestGlobalChatService:
    """Tests for global chat service instance."""
    
    def test_get_chat_service_returns_instance(self):
        """Test that get_chat_service returns an instance."""
        service = get_chat_service()
        
        assert isinstance(service, ChatService)
    
    def test_get_chat_service_singleton(self):
        """Test that get_chat_service returns same instance."""
        service1 = get_chat_service()
        service2 = get_chat_service()
        
        assert service1 is service2


# =============================================================================
# System Prompt Tests
# =============================================================================


class TestSystemPrompt:
    """Tests for the insurance agent system prompt."""
    
    def test_prompt_has_context_placeholder(self):
        """Test that prompt has context placeholder."""
        assert "{context}" in INSURANCE_AGENT_SYSTEM_PROMPT
    
    def test_prompt_includes_guidelines(self):
        """Test that prompt includes key guidelines."""
        prompt = INSURANCE_AGENT_SYSTEM_PROMPT.lower()
        
        assert "coverage" in prompt
        assert "exclusion" in prompt or "excluded" in prompt
        assert "deductible" in prompt
        assert "claim" in prompt
    
    def test_prompt_can_be_formatted(self):
        """Test that prompt can be formatted with context."""
        context = "This is test context"
        formatted = INSURANCE_AGENT_SYSTEM_PROMPT.format(context=context)
        
        assert context in formatted
        assert "{context}" not in formatted


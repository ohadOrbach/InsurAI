"""
Unit tests for LLM Service.

Tests the LLM abstraction layer including mock, OpenAI, and Anthropic providers.
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.services.llm_service import (
    LLMProvider,
    LLMMessage,
    LLMResponse,
    BaseLLM,
    MockLLM,
    OpenAILLM,
    AnthropicLLM,
    get_llm,
)


# =============================================================================
# LLMProvider Enum Tests
# =============================================================================


class TestLLMProvider:
    """Tests for LLMProvider enum."""
    
    def test_provider_values(self):
        """Test that all expected providers exist."""
        assert LLMProvider.OPENAI == "openai"
        assert LLMProvider.ANTHROPIC == "anthropic"
        assert LLMProvider.MOCK == "mock"
    
    def test_provider_count(self):
        """Test that we have the expected number of providers."""
        assert len(LLMProvider) == 3


# =============================================================================
# LLMMessage Tests
# =============================================================================


class TestLLMMessage:
    """Tests for LLMMessage dataclass."""
    
    def test_create_user_message(self):
        """Test creating a user message."""
        msg = LLMMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
    
    def test_create_system_message(self):
        """Test creating a system message."""
        msg = LLMMessage(role="system", content="You are helpful")
        assert msg.role == "system"
        assert msg.content == "You are helpful"
    
    def test_create_assistant_message(self):
        """Test creating an assistant message."""
        msg = LLMMessage(role="assistant", content="I can help!")
        assert msg.role == "assistant"
        assert msg.content == "I can help!"


# =============================================================================
# LLMResponse Tests
# =============================================================================


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""
    
    def test_create_response(self):
        """Test creating a basic response."""
        resp = LLMResponse(
            content="Test response",
            model="test-model",
        )
        assert resp.content == "Test response"
        assert resp.model == "test-model"
        assert resp.usage is None
        assert resp.finish_reason is None
    
    def test_create_full_response(self):
        """Test creating a response with all fields."""
        resp = LLMResponse(
            content="Test response",
            model="test-model",
            usage={"prompt_tokens": 10, "completion_tokens": 20},
            finish_reason="stop",
        )
        assert resp.content == "Test response"
        assert resp.model == "test-model"
        assert resp.usage["prompt_tokens"] == 10
        assert resp.finish_reason == "stop"


# =============================================================================
# MockLLM Tests
# =============================================================================


class TestMockLLM:
    """Tests for MockLLM implementation."""
    
    @pytest.fixture
    def mock_llm(self):
        """Create a MockLLM instance."""
        return MockLLM()
    
    def test_model_name(self, mock_llm):
        """Test that mock LLM has correct model name."""
        assert mock_llm.model == "mock-insurance-llm-v1"
    
    @pytest.mark.asyncio
    async def test_generate_default_response(self, mock_llm):
        """Test generating a default response."""
        messages = [
            LLMMessage(role="user", content="Hi there"),
        ]
        response = await mock_llm.generate(messages)
        
        assert isinstance(response, LLMResponse)
        assert response.content
        assert response.model == "mock-insurance-llm-v1"
        assert response.finish_reason == "stop"
    
    @pytest.mark.asyncio
    async def test_generate_coverage_response(self, mock_llm):
        """Test generating a coverage-related response."""
        messages = [
            LLMMessage(role="system", content="You are an insurance assistant."),
            LLMMessage(role="user", content="Is my engine covered?"),
        ]
        response = await mock_llm.generate(messages)
        
        assert "coverage" in response.content.lower() or "cover" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_generate_exclusion_response(self, mock_llm):
        """Test generating an exclusion-related response."""
        messages = [
            LLMMessage(role="user", content="What are the exclusions in my policy?"),
        ]
        response = await mock_llm.generate(messages)
        
        assert "exclusion" in response.content.lower() or "exclude" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_generate_deductible_response(self, mock_llm):
        """Test generating a deductible-related response."""
        messages = [
            LLMMessage(role="user", content="What is my deductible cost?"),
        ]
        response = await mock_llm.generate(messages)
        
        assert "deductible" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_generate_claim_response(self, mock_llm):
        """Test generating a claim-related response."""
        messages = [
            LLMMessage(role="user", content="How do I file a claim?"),
        ]
        response = await mock_llm.generate(messages)
        
        assert "claim" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_generate_with_coverage_context(self, mock_llm):
        """Test generating response with coverage check context."""
        context = """
        ## COVERAGE CHECK RESULTS:
        ✅ **engine**: COVERED
           Reason: Engine is included in the policy
        """
        messages = [
            LLMMessage(role="system", content=context),
            LLMMessage(role="user", content="Is my engine covered?"),
        ]
        response = await mock_llm.generate(messages)
        
        assert response.content
        # Should include coverage status info
        assert "coverage" in response.content.lower() or "engine" in response.content.lower()
    
    @pytest.mark.asyncio
    async def test_generate_stream(self, mock_llm):
        """Test streaming response generation."""
        messages = [
            LLMMessage(role="user", content="Hello"),
        ]
        
        tokens = []
        async for token in mock_llm.generate_stream(messages):
            tokens.append(token)
        
        # Should have multiple tokens
        assert len(tokens) > 1
        # Concatenated tokens should form the response
        full_response = "".join(tokens)
        assert full_response
    
    @pytest.mark.asyncio
    async def test_response_has_usage(self, mock_llm):
        """Test that response includes usage information."""
        messages = [
            LLMMessage(role="user", content="Test message"),
        ]
        response = await mock_llm.generate(messages)
        
        assert response.usage is not None
        assert "prompt_tokens" in response.usage
        assert "completion_tokens" in response.usage


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestGetLLM:
    """Tests for get_llm factory function."""
    
    def test_get_mock_llm(self):
        """Test getting MockLLM."""
        llm = get_llm(LLMProvider.MOCK)
        assert isinstance(llm, MockLLM)
    
    def test_get_openai_llm(self):
        """Test getting OpenAILLM."""
        llm = get_llm(LLMProvider.OPENAI, api_key="test-key")
        assert isinstance(llm, OpenAILLM)
        assert llm.api_key == "test-key"
    
    def test_get_anthropic_llm(self):
        """Test getting AnthropicLLM."""
        llm = get_llm(LLMProvider.ANTHROPIC, api_key="test-key")
        assert isinstance(llm, AnthropicLLM)
        assert llm.api_key == "test-key"
    
    def test_get_llm_with_custom_model(self):
        """Test getting LLM with custom model."""
        llm = get_llm(LLMProvider.OPENAI, api_key="test", model="gpt-4-turbo")
        assert llm.model == "gpt-4-turbo"
    
    def test_invalid_provider(self):
        """Test that invalid provider raises error."""
        with pytest.raises((ValueError, KeyError)):
            get_llm("invalid-provider")
    
    def test_default_provider_is_mock(self):
        """Test that default provider is mock."""
        llm = get_llm()
        assert isinstance(llm, MockLLM)


# =============================================================================
# OpenAI LLM Tests (Without API Calls)
# =============================================================================


class TestOpenAILLM:
    """Tests for OpenAILLM initialization (without actual API calls)."""
    
    def test_initialization_with_api_key(self):
        """Test initialization with API key."""
        llm = OpenAILLM(api_key="test-api-key")
        assert llm.api_key == "test-api-key"
        assert llm.model == "gpt-4o"  # Default model
    
    def test_initialization_with_custom_model(self):
        """Test initialization with custom model."""
        llm = OpenAILLM(api_key="test", model="gpt-4-turbo")
        assert llm.model == "gpt-4-turbo"
    
    def test_client_lazy_initialization(self):
        """Test that client is not initialized immediately."""
        llm = OpenAILLM(api_key="test")
        assert llm._client is None


# =============================================================================
# Anthropic LLM Tests (Without API Calls)
# =============================================================================


class TestAnthropicLLM:
    """Tests for AnthropicLLM initialization (without actual API calls)."""
    
    def test_initialization_with_api_key(self):
        """Test initialization with API key."""
        llm = AnthropicLLM(api_key="test-api-key")
        assert llm.api_key == "test-api-key"
        assert llm.model == "claude-3-5-sonnet-20241022"  # Default model
    
    def test_initialization_with_custom_model(self):
        """Test initialization with custom model."""
        llm = AnthropicLLM(api_key="test", model="claude-3-opus-20240229")
        assert llm.model == "claude-3-opus-20240229"
    
    def test_client_lazy_initialization(self):
        """Test that client is not initialized immediately."""
        llm = AnthropicLLM(api_key="test")
        assert llm._client is None


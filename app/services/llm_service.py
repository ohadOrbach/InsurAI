"""
LLM Service for Universal Insurance AI Agent.

Provides abstraction over LLM providers (OpenAI, Anthropic) with
mock support for development and testing.
"""

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    MOCK = "mock"


@dataclass
class LLMMessage:
    """A message in the conversation."""
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMResponse:
    """Response from LLM."""
    content: str
    model: str
    usage: Optional[dict] = None
    finish_reason: Optional[str] = None


class BaseLLM(ABC):
    """Base class for LLM providers."""
    
    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Generate a response from the LLM."""
        pass
    
    @abstractmethod
    async def generate_stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response from the LLM."""
        pass


class MockLLM(BaseLLM):
    """
    Mock LLM for development and testing.
    
    Generates contextual responses based on the input without
    requiring API keys or network access.
    """
    
    INSURANCE_RESPONSES = {
        "coverage": (
            "Based on the policy documents, I can help you understand your coverage. "
            "Let me check the specific details for you."
        ),
        "exclusion": (
            "I found some important exclusion information in your policy. "
            "Please review these carefully as they affect what's covered."
        ),
        "deductible": (
            "Your policy includes specific deductible amounts that apply to different "
            "categories of coverage. Here's what I found:"
        ),
        "claim": (
            "To file a claim under your policy, you'll need to follow the process "
            "outlined in your coverage documents. Let me guide you through it."
        ),
        "default": (
            "I'm your insurance policy assistant. I can help you understand your "
            "coverage, exclusions, deductibles, and claims process. "
            "What would you like to know about your policy?"
        ),
    }
    
    def __init__(self):
        self.model = "mock-insurance-llm-v1"
    
    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Generate a mock response based on conversation context."""
        # Get the last user message
        user_message = ""
        context = ""
        
        for msg in messages:
            if msg.role == "user":
                user_message = msg.content.lower()
            elif msg.role == "system":
                context = msg.content
        
        # Generate contextual response
        response_content = self._generate_mock_response(user_message, context)
        
        return LLMResponse(
            content=response_content,
            model=self.model,
            usage={"prompt_tokens": len(user_message), "completion_tokens": len(response_content)},
            finish_reason="stop",
        )
    
    async def generate_stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming mock response."""
        import asyncio
        
        response = await self.generate(messages, temperature, max_tokens)
        
        # Simulate streaming by yielding words with delays
        words = response.content.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
            await asyncio.sleep(0.03)  # 30ms delay between words
    
    def _generate_mock_response(self, user_message: str, context: str) -> str:
        """Generate a contextual mock response based on RAG context."""
        response_parts = []
        
        # Check for coverage check results in context
        if "COVERAGE CHECK RESULTS" in context:
            coverage_info = self._extract_coverage_results(context)
            if coverage_info:
                response_parts.append(coverage_info)
        
        # If no direct coverage check, provide general response
        if not response_parts:
            if any(word in user_message for word in ["cover", "covered", "coverage", "include"]):
                response_parts.append(self.INSURANCE_RESPONSES["coverage"])
            elif any(word in user_message for word in ["exclude", "exclusion", "not cover", "exception"]):
                response_parts.append(self.INSURANCE_RESPONSES["exclusion"])
            elif any(word in user_message for word in ["deductible", "copay", "pay", "cost", "price"]):
                response_parts.append(self.INSURANCE_RESPONSES["deductible"])
            elif any(word in user_message for word in ["claim", "file", "report", "submit"]):
                response_parts.append(self.INSURANCE_RESPONSES["claim"])
            else:
                response_parts.append(self.INSURANCE_RESPONSES["default"])
        
        # Add RAG context information
        if context and "RETRIEVED CONTEXT" in context:
            context_info = self._extract_context_info(context)
            if context_info:
                response_parts.append(f"\n**Relevant Policy Details:**\n{context_info}")
        
        # Add policy information summary
        if "POLICY INFORMATION" in context:
            policy_info = self._extract_policy_info(context)
            if policy_info:
                response_parts.append(f"\n**Policy Reference:**\n{policy_info}")
        
        return "\n".join(response_parts)
    
    def _extract_context_info(self, context: str) -> str:
        """Extract relevant info from RAG context."""
        lines = []
        in_context = False
        
        for line in context.split("\n"):
            if "RETRIEVED CONTEXT" in line:
                in_context = True
                continue
            if "COVERAGE CHECK" in line or "POLICY INFORMATION" in line:
                in_context = False
                continue
            if in_context and line.strip():
                clean_line = line.strip()
                if clean_line.startswith("- ["):
                    # Format RAG chunks nicely
                    lines.append(f"• {clean_line[2:]}")
                elif clean_line and not clean_line.startswith("#"):
                    lines.append(f"• {clean_line}")
        
        return "\n".join(lines[:5])  # Limit to 5 context items
    
    def _extract_coverage_results(self, context: str) -> str:
        """Extract coverage check results."""
        lines = []
        in_results = False
        
        for line in context.split("\n"):
            if "COVERAGE CHECK RESULTS" in line:
                in_results = True
                continue
            if in_results:
                if line.startswith("##") or line.startswith("**"):
                    in_results = False
                    continue
                if line.strip():
                    lines.append(line.strip())
        
        if not lines:
            return ""
        
        return "**Coverage Status:**\n" + "\n".join(lines[:6])
    
    def _extract_policy_info(self, context: str) -> str:
        """Extract policy information."""
        lines = []
        in_info = False
        
        for line in context.split("\n"):
            if "POLICY INFORMATION" in line:
                in_info = True
                continue
            if in_info and line.strip().startswith("-"):
                lines.append(line.strip())
        
        return "\n".join(lines[:3]) if lines else ""


class OpenAILLM(BaseLLM):
    """OpenAI GPT-4 implementation."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self._client = None
    
    @property
    def client(self):
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("openai package not installed. Run: pip install openai")
        return self._client
    
    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Generate response using OpenAI API."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            },
            finish_reason=choice.finish_reason,
        )
    
    async def generate_stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response using OpenAI API."""
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class AnthropicLLM(BaseLLM):
    """Anthropic Claude implementation."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self._client = None
    
    @property
    def client(self):
        """Lazy initialization of Anthropic client."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
                self._client = AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")
        return self._client
    
    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Generate response using Anthropic API."""
        # Separate system message from conversation
        system_msg = ""
        conv_messages = []
        
        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            else:
                conv_messages.append({"role": msg.role, "content": msg.content})
        
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_msg,
            messages=conv_messages,
        )
        
        return LLMResponse(
            content=response.content[0].text if response.content else "",
            model=response.model,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
            },
            finish_reason=response.stop_reason,
        )
    
    async def generate_stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response using Anthropic API."""
        system_msg = ""
        conv_messages = []
        
        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            else:
                conv_messages.append({"role": msg.role, "content": msg.content})
        
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=system_msg,
            messages=conv_messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text


class GoogleLLM(BaseLLM):
    """Google Gemini implementation."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.model = model
        self._client = None
    
    @property
    def client(self):
        """Lazy initialization of Google Generative AI client."""
        if self._client is None:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._client = genai.GenerativeModel(self.model)
            except ImportError:
                raise ImportError(
                    "google-generativeai package not installed. "
                    "Run: pip install google-generativeai"
                )
        return self._client
    
    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Generate response using Google Gemini API."""
        import asyncio
        
        # Convert messages to Gemini format
        # Gemini expects a different format - combine system + user messages
        system_content = ""
        chat_history = []
        
        for msg in messages:
            if msg.role == "system":
                system_content = msg.content
            elif msg.role == "user":
                # Prepend system content to first user message if present
                content = msg.content
                if system_content and not chat_history:
                    content = f"[System Instructions]\n{system_content}\n\n[User Query]\n{content}"
                chat_history.append({"role": "user", "parts": [content]})
            elif msg.role == "assistant":
                chat_history.append({"role": "model", "parts": [msg.content]})
        
        # Configure generation
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        
        # Run in executor for async compatibility
        loop = asyncio.get_event_loop()
        
        # Start chat with history (except last message)
        if len(chat_history) > 1:
            chat = self.client.start_chat(history=chat_history[:-1])
            last_message = chat_history[-1]["parts"][0]
            response = await loop.run_in_executor(
                None, 
                lambda: chat.send_message(last_message, generation_config=generation_config)
            )
        else:
            # Single message, use generate_content
            prompt = chat_history[0]["parts"][0] if chat_history else ""
            response = await loop.run_in_executor(
                None,
                lambda: self.client.generate_content(prompt, generation_config=generation_config)
            )
        
        # Extract response
        content = ""
        if response.text:
            content = response.text
        
        # Get usage metadata if available
        usage = {}
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = {
                "prompt_tokens": getattr(response.usage_metadata, 'prompt_token_count', 0),
                "completion_tokens": getattr(response.usage_metadata, 'candidates_token_count', 0),
            }
        
        return LLMResponse(
            content=content,
            model=self.model,
            usage=usage,
            finish_reason="stop",
        )
    
    async def generate_stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response using Google Gemini API."""
        import asyncio
        
        # Convert messages to Gemini format
        system_content = ""
        chat_history = []
        
        for msg in messages:
            if msg.role == "system":
                system_content = msg.content
            elif msg.role == "user":
                content = msg.content
                if system_content and not chat_history:
                    content = f"[System Instructions]\n{system_content}\n\n[User Query]\n{content}"
                chat_history.append({"role": "user", "parts": [content]})
            elif msg.role == "assistant":
                chat_history.append({"role": "model", "parts": [msg.content]})
        
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        
        loop = asyncio.get_event_loop()
        
        # Get streaming response
        if len(chat_history) > 1:
            chat = self.client.start_chat(history=chat_history[:-1])
            last_message = chat_history[-1]["parts"][0]
            response = await loop.run_in_executor(
                None,
                lambda: chat.send_message(last_message, generation_config=generation_config, stream=True)
            )
        else:
            prompt = chat_history[0]["parts"][0] if chat_history else ""
            response = await loop.run_in_executor(
                None,
                lambda: self.client.generate_content(prompt, generation_config=generation_config, stream=True)
            )
        
        # Stream chunks
        for chunk in response:
            if chunk.text:
                yield chunk.text
                await asyncio.sleep(0)  # Allow other tasks to run


def get_llm(provider: LLMProvider = LLMProvider.MOCK, **kwargs) -> BaseLLM:
    """
    Factory function to get an LLM instance.
    
    Args:
        provider: LLM provider to use
        **kwargs: Provider-specific arguments
        
    Returns:
        LLM instance
    """
    from app.core.config import settings
    
    providers = {
        LLMProvider.MOCK: MockLLM,
        LLMProvider.OPENAI: OpenAILLM,
        LLMProvider.ANTHROPIC: AnthropicLLM,
        LLMProvider.GOOGLE: GoogleLLM,
    }
    
    if provider not in providers:
        raise ValueError(f"Unknown provider: {provider}")
    
    # Auto-inject API keys from settings if not provided
    if provider == LLMProvider.GOOGLE and "api_key" not in kwargs:
        kwargs["api_key"] = settings.GOOGLE_API_KEY
    elif provider == LLMProvider.OPENAI and "api_key" not in kwargs:
        kwargs["api_key"] = settings.OPENAI_API_KEY
    elif provider == LLMProvider.ANTHROPIC and "api_key" not in kwargs:
        kwargs["api_key"] = settings.ANTHROPIC_API_KEY
    
    return providers[provider](**kwargs)


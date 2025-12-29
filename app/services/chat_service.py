"""
Chat Service for Universal Insurance AI Agent.

Combines RAG retrieval, Policy Engine coverage checking, and LLM
to provide intelligent, context-aware responses about insurance policies.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import AsyncGenerator, Optional

from app.schema import CoverageStatus
from app.services.llm_service import BaseLLM, LLMMessage, LLMProvider, get_llm
from app.services.policy_engine import PolicyEngine
from app.services.vector_store import PolicyVectorizer

logger = logging.getLogger(__name__)


class MessageRole(str, Enum):
    """Chat message roles."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class ChatMessage:
    """A chat message with metadata."""
    id: str
    role: MessageRole
    content: str
    timestamp: datetime
    metadata: dict = field(default_factory=dict)
    
    @classmethod
    def create(cls, role: MessageRole, content: str, **metadata) -> "ChatMessage":
        """Create a new chat message."""
        return cls(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            timestamp=datetime.now(),
            metadata=metadata,
        )


@dataclass
class ChatSession:
    """A chat session containing conversation history."""
    id: str
    policy_id: Optional[str]
    agent_id: Optional[int] = None  # Link to agent
    user_id: Optional[int] = None   # For B2B limitation context
    messages: list[ChatMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    
    @classmethod
    def create(
        cls, 
        policy_id: Optional[str] = None,
        agent_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> "ChatSession":
        """Create a new chat session."""
        return cls(
            id=str(uuid.uuid4()),
            policy_id=policy_id,
            agent_id=agent_id,
            user_id=user_id,
            messages=[],
        )


# System prompt for the insurance AI agent
INSURANCE_AGENT_SYSTEM_PROMPT = """You are a helpful insurance policy assistant. Your role is to help users understand their coverage, exclusions, and financial terms.

## Your Responsibilities:
1. Answer coverage questions accurately based on policy documents
2. Clearly communicate what is and isn't covered
3. Explain financial terms (deductibles, co-pays, caps)
4. Guide users on claims processes when asked

## Important Guidelines:
- ALWAYS reference the policy document when answering
- Be PRECISE - do not guess or assume coverage
- When something is EXCLUDED, clearly state it's not covered
- Always mention relevant deductibles and coverage limits
- If unsure, recommend contacting the insurance provider

## Response Format:
- Start with a clear verdict (Covered/Not Covered/Conditional/Requires Review)
- Explain reasoning with specific policy references
- Include relevant financial information
- Keep explanations clear and user-friendly
- Add disclaimer that this is not legal advice

{context}
"""


class ChatService:
    """
    Chat service that orchestrates RAG retrieval, policy engine,
    and LLM to provide intelligent insurance assistance.
    """
    
    def __init__(
        self,
        llm_provider: LLMProvider = LLMProvider.MOCK,
        policy_engine: Optional[PolicyEngine] = None,
        vectorizer: Optional[PolicyVectorizer] = None,
    ):
        """
        Initialize the chat service.
        
        Args:
            llm_provider: Which LLM provider to use
            policy_engine: Policy engine for coverage checks
            vectorizer: Policy vectorizer for RAG retrieval
        """
        self.llm = get_llm(llm_provider)
        self.policy_engine = policy_engine or PolicyEngine()
        self.vectorizer = vectorizer or PolicyVectorizer(use_mock=True)
        
        # Ensure the policy is vectorized
        self._ensure_policy_vectorized()
        
        # Store active sessions
        self._sessions: dict[str, ChatSession] = {}
    
    def _ensure_policy_vectorized(self) -> None:
        """Ensure the current policy is vectorized for RAG."""
        policy_id = self.policy_engine.policy.policy_meta.policy_id
        
        if self.vectorizer.vector_store.count_by_policy(policy_id) == 0:
            logger.info(f"Vectorizing policy: {policy_id}")
            self.vectorizer.vectorize_policy(self.policy_engine.policy)
    
    def create_session(
        self, 
        policy_id: Optional[str] = None,
        agent_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> ChatSession:
        """Create a new chat session."""
        session = ChatSession.create(policy_id, agent_id, user_id)
        self._sessions[session.id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get an existing session."""
        return self._sessions.get(session_id)
    
    def _build_context(
        self, 
        user_message: str, 
        policy_id: Optional[str] = None,
        session: Optional[ChatSession] = None,
    ) -> str:
        """
        Build context from RAG retrieval, policy engine, and user limitations.
        
        Args:
            user_message: User's question
            policy_id: Optional policy ID to search within
            session: Optional session for agent/user context
            
        Returns:
            Formatted context string for the LLM
        """
        context_parts = []
        
        # Log policy filtering for audit trail
        if policy_id:
            logger.info(f"RAG Search: policy_id={policy_id}")
        else:
            logger.warning("RAG Search: No policy_id filter - searching all policies")
        
        # 1. RAG Retrieval - Find relevant policy chunks (FILTERED BY POLICY_ID)
        rag_results = self.vectorizer.search(
            query=user_message,
            policy_id=policy_id,  # CRITICAL: This ensures we only search the agent's policy
            top_k=5,
            min_score=0.3,
        )
        
        if rag_results:
            context_parts.append("## RETRIEVED CONTEXT FROM POLICY DOCUMENTS:")
            for result in rag_results:
                chunk = result.chunk
                context_parts.append(
                    f"- [{chunk.chunk_type.value.upper()}] "
                    f"{f'({chunk.category}) ' if chunk.category else ''}"
                    f"{chunk.text}"
                )
        
        # 2. Add policy context - use policy_id from session if available
        if policy_id:
            context_parts.append(f"\n## POLICY INFORMATION:\n- Policy ID: {policy_id}")
        
        # Note: Coverage checks are skipped for dynamic policies
        # The RAG context above provides the relevant policy information
        
        # 4. Add user limitations for B2B (if applicable)
        if session and session.agent_id and session.user_id:
            limitations_context = self._get_user_limitations_context(
                user_id=session.user_id,
                agent_id=session.agent_id,
            )
            if limitations_context:
                context_parts.append(limitations_context)
        
        return "\n".join(context_parts)
    
    def _get_user_limitations_context(
        self, 
        user_id: int, 
        agent_id: int,
    ) -> str:
        """
        Get user-specific limitations for B2B context injection.
        
        This allows shared B2B agents to know about user-specific
        constraints like claim limits, payment status, etc.
        """
        try:
            from app.services.agent_service import get_agent_service
            agent_service = get_agent_service()
            return agent_service.build_limitation_context(user_id, agent_id)
        except Exception as e:
            logger.warning(f"Failed to get user limitations: {e}")
            return ""
    
    def _extract_and_check_coverage(self, message: str) -> list:
        """
        Extract potential items from message and check coverage.
        
        Uses basic keyword extraction to find items to check.
        """
        results = []
        
        # Common insurance coverage items to look for
        common_items = [
            # Auto/property
            "engine", "transmission", "battery", "collision", "comprehensive",
            "liability", "property damage", "theft", "towing",
            # Health/life
            "medical", "hospitalization", "surgery", "prescription",
            "death benefit", "disability",
        ]
        
        message_lower = message.lower()
        
        for item in common_items:
            if item in message_lower:
                result = self.policy_engine.check_coverage(item)
                results.append(result)
        
        return results[:3]  # Limit to top 3 items
    
    def _build_messages(
        self,
        session: ChatSession,
        user_message: str,
        context: str,
    ) -> list[LLMMessage]:
        """Build the message list for the LLM."""
        messages = []
        
        # System prompt with context
        system_prompt = INSURANCE_AGENT_SYSTEM_PROMPT.format(context=context)
        messages.append(LLMMessage(role="system", content=system_prompt))
        
        # Conversation history (last 10 messages for context window management)
        for msg in session.messages[-10:]:
            messages.append(LLMMessage(role=msg.role.value, content=msg.content))
        
        # Current user message
        messages.append(LLMMessage(role="user", content=user_message))
        
        return messages
    
    async def chat(
        self,
        session_id: str,
        user_message: str,
    ) -> ChatMessage:
        """
        Process a chat message and generate a response.
        
        Uses the Coverage Agent (LangGraph reasoning loop) for coverage questions,
        and simple RAG for general questions.
        
        Args:
            session_id: Chat session ID
            user_message: User's message
            
        Returns:
            Assistant's response message
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        # Add user message to session
        user_msg = ChatMessage.create(MessageRole.USER, user_message)
        session.messages.append(user_msg)
        
        # Check if this is a coverage question - use the Coverage Agent (reasoning loop)
        message_lower = user_message.lower()
        is_coverage_question = any(kw in message_lower for kw in [
            "covered", "cover", "coverage", "is my", "am i", "does my",
            "excluded", "exclusion", "not covered", "included", "include",
            "damage", "injury", "medical", "liability", "collision",
            "comprehensive", "surgery", "cosmetic", "deductible",
            "?",  # Any question about policy is likely coverage-related
        ])
        
        if is_coverage_question and session.policy_id:
            # Use Coverage Agent with reasoning loop (Phase B pipeline)
            try:
                from app.services.coverage_agent import get_coverage_agent
                
                coverage_agent = get_coverage_agent()
                result = await coverage_agent.process(
                    user_message=user_message,
                    policy_id=session.policy_id,
                    user_id=session.user_id,
                    agent_id=session.agent_id,
                )
                
                response_content = result["response"]
                
                # Add reasoning trace as metadata for debugging
                metadata = {
                    "reasoning_trace": result.get("reasoning_trace", []),
                    "coverage_checks": result.get("coverage_checks", []),
                    "citations": result.get("citations", []),
                    "pipeline": "coverage_agent_v1",
                }
                
                logger.info(f"Coverage Agent trace: {result.get('reasoning_trace', [])}")
                
            except Exception as e:
                logger.exception(f"Coverage Agent error, falling back to simple RAG: {e}")
                # Fallback to simple RAG
                context = self._build_context(user_message, session.policy_id)
                llm_messages = self._build_messages(session, user_message, context)
                response = await self.llm.generate(llm_messages)
                response_content = response.content
                metadata = {"pipeline": "fallback_rag"}
        else:
            # Use simple RAG pipeline for non-coverage questions
            context = self._build_context(user_message, session.policy_id)
            llm_messages = self._build_messages(session, user_message, context)
            response = await self.llm.generate(llm_messages)
            response_content = response.content
            metadata = {"pipeline": "simple_rag"}
        
        # Create and store assistant message
        assistant_msg = ChatMessage.create(
            MessageRole.ASSISTANT,
            response_content,
            **metadata,
        )
        session.messages.append(assistant_msg)
        
        return assistant_msg
    
    async def chat_stream(
        self,
        session_id: str,
        user_message: str,
    ) -> AsyncGenerator[str, None]:
        """
        Process a chat message and stream the response.
        
        Args:
            session_id: Chat session ID
            user_message: User's message
            
        Yields:
            Response tokens as they're generated
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        # Add user message to session
        user_msg = ChatMessage.create(MessageRole.USER, user_message)
        session.messages.append(user_msg)
        
        # Build context from RAG and policy engine
        context = self._build_context(user_message, session.policy_id)
        
        # Build LLM messages
        llm_messages = self._build_messages(session, user_message, context)
        
        # Stream response
        full_response = []
        async for token in self.llm.generate_stream(llm_messages):
            full_response.append(token)
            yield token
        
        # Store complete response
        assistant_msg = ChatMessage.create(
            MessageRole.ASSISTANT,
            "".join(full_response),
        )
        session.messages.append(assistant_msg)
    
    def get_suggested_questions(self) -> list[str]:
        """Get suggested questions based on the loaded policy."""
        summary = self.policy_engine.get_policy_summary()
        categories = summary.get("coverage_categories", [])
        
        suggestions = [
            "What is covered under my policy?",
            "What are the main exclusions I should know about?",
            "What are the deductible amounts for different repairs?",
        ]
        
        if "Engine" in categories:
            suggestions.append("Is my engine covered? What about the turbo?")
        if "Transmission" in categories:
            suggestions.append("Is transmission repair covered?")
        if "Roadside Assistance" in categories:
            suggestions.append("Does my policy include towing services?")
        
        return suggestions[:5]


# Global chat service instance
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get or create the global chat service instance."""
    global _chat_service
    if _chat_service is None:
        # Read LLM provider from config
        from app.core.config import settings
        from app.services.agent_service import get_agent_service
        
        provider_map = {
            "mock": LLMProvider.MOCK,
            "openai": LLMProvider.OPENAI,
            "anthropic": LLMProvider.ANTHROPIC,
            "google": LLMProvider.GOOGLE,
        }
        provider = provider_map.get(settings.LLM_PROVIDER.lower(), LLMProvider.MOCK)
        
        # Share the vectorizer with AgentService so uploaded policies are searchable
        agent_service = get_agent_service()
        shared_vectorizer = agent_service.vectorizer
        
        logger.info(f"Initializing ChatService with LLM provider: {provider}")
        logger.info(f"Using shared vectorizer with {shared_vectorizer.vector_store.count()} chunks")
        _chat_service = ChatService(
            llm_provider=provider,
            vectorizer=shared_vectorizer,
        )
    return _chat_service


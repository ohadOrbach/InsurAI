"""
Chat API Endpoints for Universal Insurance AI Agent.

Provides conversational AI interface for policy questions with
support for streaming responses.
"""

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, Path, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.chat_service import ChatService, get_chat_service, MessageRole

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================


class CreateSessionRequest(BaseModel):
    """Request to create a new chat session."""
    
    policy_id: Optional[str] = Field(
        default=None,
        description="Optional policy ID to associate with the session",
    )


class CreateSessionResponse(BaseModel):
    """Response with new session details."""
    
    success: bool = True
    session_id: str
    policy_id: Optional[str] = None
    suggested_questions: list[str]


class ChatRequest(BaseModel):
    """Request to send a chat message."""
    
    message: str = Field(
        ...,
        description="User's message",
        min_length=1,
        max_length=2000,
        examples=["Is my engine covered under the warranty?"],
    )
    stream: bool = Field(
        default=False,
        description="Whether to stream the response",
    )


class ChatMessageResponse(BaseModel):
    """A chat message."""
    
    id: str
    role: str
    content: str
    timestamp: str
    metadata: dict = {}


class ReasoningTraceResponse(BaseModel):
    """Reasoning trace from Coverage Agent (for audit/debugging)."""
    
    pipeline: str = "unknown"
    reasoning_trace: list[str] = []
    coverage_checks: list[dict] = []
    citations: list[str] = []


class ChatResponse(BaseModel):
    """Response from a chat message."""
    
    success: bool = True
    session_id: str
    message: ChatMessageResponse
    reasoning: Optional[ReasoningTraceResponse] = None  # Populated for coverage questions


class SessionHistoryResponse(BaseModel):
    """Response with session history."""
    
    success: bool = True
    session_id: str
    policy_id: Optional[str] = None
    message_count: int
    messages: list[ChatMessageResponse]


# =============================================================================
# Chat Session Endpoints
# =============================================================================


@router.post(
    "/sessions",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new chat session",
    description="""
Create a new chat session for conversational interaction.

The session maintains conversation history and context for better responses.
Optionally specify a policy_id to focus the conversation on a specific policy.
    """,
)
async def create_session(request: CreateSessionRequest = CreateSessionRequest()):
    """Create a new chat session."""
    chat_service = get_chat_service()
    session = chat_service.create_session(request.policy_id)
    
    return CreateSessionResponse(
        session_id=session.id,
        policy_id=session.policy_id,
        suggested_questions=chat_service.get_suggested_questions(),
    )


@router.get(
    "/sessions/{session_id}",
    response_model=SessionHistoryResponse,
    summary="Get session history",
    description="Get the conversation history for a chat session.",
)
async def get_session_history(
    session_id: str = Path(..., description="Chat session ID"),
):
    """Get chat session history."""
    chat_service = get_chat_service()
    session = chat_service.get_session(session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )
    
    return SessionHistoryResponse(
        session_id=session.id,
        policy_id=session.policy_id,
        message_count=len(session.messages),
        messages=[
            ChatMessageResponse(
                id=msg.id,
                role=msg.role.value,
                content=msg.content,
                timestamp=msg.timestamp.isoformat(),
                metadata=msg.metadata,
            )
            for msg in session.messages
        ],
    )


# =============================================================================
# Chat Message Endpoints
# =============================================================================


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatResponse,
    summary="Send a chat message",
    description="""
Send a message to the AI assistant and receive a response.

The assistant will:
1. Search the policy documents for relevant information (RAG)
2. Check coverage status for mentioned items
3. Generate a helpful, context-aware response

Set `stream: true` to receive a streaming response (Server-Sent Events).

**Example messages:**
- "Is my engine covered under the warranty?"
- "What's the deductible for transmission repairs?"
- "Are there any exclusions I should know about?"
- "Is turbo replacement covered?"
    """,
)
async def send_message(
    session_id: str = Path(..., description="Chat session ID"),
    request: ChatRequest = ...,
):
    """Send a chat message and get a response."""
    chat_service = get_chat_service()
    
    session = chat_service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )
    
    # Handle streaming response
    if request.stream:
        return StreamingResponse(
            _stream_response(chat_service, session_id, request.message),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    
    # Non-streaming response
    response = await chat_service.chat(session_id, request.message)
    
    # Extract reasoning trace if available (from Coverage Agent)
    reasoning = None
    if response.metadata.get("pipeline") == "coverage_agent_v1":
        reasoning = ReasoningTraceResponse(
            pipeline=response.metadata.get("pipeline", "unknown"),
            reasoning_trace=response.metadata.get("reasoning_trace", []),
            coverage_checks=response.metadata.get("coverage_checks", []),
            citations=response.metadata.get("citations", []),
        )
    
    return ChatResponse(
        session_id=session_id,
        message=ChatMessageResponse(
            id=response.id,
            role=response.role.value,
            content=response.content,
            timestamp=response.timestamp.isoformat(),
            metadata=response.metadata,
        ),
        reasoning=reasoning,
    )


async def _stream_response(
    chat_service: ChatService,
    session_id: str,
    message: str,
):
    """Generate Server-Sent Events for streaming response."""
    try:
        # Send start event
        yield f"event: start\ndata: {{}}\n\n"
        
        # Stream tokens
        async for token in chat_service.chat_stream(session_id, message):
            # Escape newlines and format as SSE
            escaped_token = token.replace("\n", "\\n")
            yield f"event: token\ndata: {escaped_token}\n\n"
        
        # Send done event
        yield f"event: done\ndata: {{}}\n\n"
        
    except Exception as e:
        # Send error event
        yield f"event: error\ndata: {str(e)}\n\n"


# =============================================================================
# Quick Chat Endpoint (No Session Required)
# =============================================================================


class QuickChatRequest(BaseModel):
    """Request for quick one-off chat."""
    
    message: str = Field(
        ...,
        description="Your question about the insurance policy",
        min_length=1,
        max_length=2000,
        examples=["Is turbo replacement covered?"],
    )


class QuickChatResponse(BaseModel):
    """Response from quick chat."""
    
    success: bool = True
    question: str
    answer: str
    coverage_status: Optional[str] = None
    context_used: list[str] = []


@router.post(
    "/ask",
    response_model=QuickChatResponse,
    summary="Quick question (no session)",
    description="""
Ask a quick question without creating a session.

Good for one-off coverage questions. For multi-turn conversations,
create a session with POST /api/v1/chat/sessions first.

**Examples:**
- "Is my turbo covered?"
- "What's the deductible for engine repairs?"
- "Is towing included?"
    """,
)
async def quick_chat(request: QuickChatRequest):
    """Quick one-off chat without session management."""
    chat_service = get_chat_service()
    
    # Create a temporary session
    session = chat_service.create_session()
    
    # Get response
    response = await chat_service.chat(session.id, request.message)
    
    # Extract coverage status from response if present
    coverage_status = None
    if "COVERED" in response.content.upper():
        if "NOT COVERED" in response.content.upper() or "NOT_COVERED" in response.content.upper():
            coverage_status = "not_covered"
        elif "CONDITIONAL" in response.content.upper():
            coverage_status = "conditional"
        else:
            coverage_status = "covered"
    
    return QuickChatResponse(
        question=request.message,
        answer=response.content,
        coverage_status=coverage_status,
        context_used=[],
    )


# =============================================================================
# Suggestions Endpoint
# =============================================================================


@router.get(
    "/suggestions",
    summary="Get suggested questions",
    description="Get suggested questions based on the loaded policy.",
)
async def get_suggestions():
    """Get suggested questions."""
    chat_service = get_chat_service()
    
    return {
        "success": True,
        "suggestions": chat_service.get_suggested_questions(),
    }


"""
Agent API endpoints for Universal Insurance AI Agent.

Provides:
- Agent creation from policy upload
- Agent listing and management
- User limitations for B2B
- Ingestion status tracking (for large documents)
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Query
from pydantic import BaseModel, Field

from app.services.agent_service import (
    AgentService,
    AgentCreate,
    AgentInfo,
    UserLimitationInfo,
    get_agent_service,
)
from app.services.ingestion_status import (
    IngestionStatusService,
    IngestionProgress,
    get_ingestion_status_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


# =============================================================================
# Request/Response Models
# =============================================================================

class AgentCreateRequest(BaseModel):
    """Request to create an agent from text."""
    name: str = Field(..., description="Agent display name")
    policy_text: str = Field(..., description="Policy document text")
    policy_id: Optional[str] = Field(None, description="Custom policy ID")
    description: Optional[str] = Field(None, description="Agent description")
    color: str = Field("#f97316", description="Agent theme color (hex)")
    agent_type: str = Field("personal", description="Agent type: personal (B2C) or shared (B2B)")


class AgentUpdateRequest(BaseModel):
    """Request to update an agent."""
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    status: Optional[str] = None


class AgentResponse(BaseModel):
    """Agent information response."""
    id: int
    name: str
    description: Optional[str]
    agent_type: str
    status: str
    policy_id: str
    policy_type: Optional[str]
    provider_name: Optional[str]
    color: str
    avatar_url: Optional[str]
    created_at: str
    last_used_at: Optional[str]
    total_conversations: int
    total_messages: int
    coverage_summary: dict


class AgentListResponse(BaseModel):
    """List of agents response."""
    success: bool
    agents: List[AgentResponse]
    total: int


class AgentCreateResponse(BaseModel):
    """Agent creation response."""
    success: bool
    message: str
    agent: AgentResponse


class UserLimitationRequest(BaseModel):
    """Request to add a user limitation."""
    limitation_type: str = Field(..., description="Type: claim_limit, payment, coverage_cap, etc.")
    title: str = Field(..., description="Short title")
    description: str = Field(..., description="Detailed description")
    severity: str = Field("info", description="Severity: info, warning, critical")
    current_value: Optional[str] = Field(None, description="Current value (e.g., '3')")
    max_value: Optional[str] = Field(None, description="Maximum value (e.g., '4')")


class UserLimitationResponse(BaseModel):
    """User limitation response."""
    id: int
    limitation_type: str
    title: str
    description: str
    severity: str
    current_value: Optional[str]
    max_value: Optional[str]
    is_active: bool


# =============================================================================
# Helper Functions
# =============================================================================

def agent_info_to_response(info: AgentInfo) -> AgentResponse:
    """Convert AgentInfo to API response."""
    return AgentResponse(
        id=info.id,
        name=info.name,
        description=info.description,
        agent_type=info.agent_type,
        status=info.status,
        policy_id=info.policy_id,
        policy_type=info.policy_type,
        provider_name=info.provider_name,
        color=info.color,
        avatar_url=info.avatar_url,
        created_at=info.created_at.isoformat(),
        last_used_at=info.last_used_at.isoformat() if info.last_used_at else None,
        total_conversations=info.total_conversations,
        total_messages=info.total_messages,
        coverage_summary=info.coverage_summary,
    )


# =============================================================================
# Agent Endpoints
# =============================================================================

@router.post("/create/demo", response_model=AgentCreateResponse)
async def create_demo_agent(
    name: str = Query("My Insurance Agent", description="Agent name"),
    service: AgentService = Depends(get_agent_service),
):
    """
    Create a demo agent with sample policy data.
    
    Quick way to test the agent system.
    """
    try:
        agent_data = AgentCreate(
            name=name,
            description="Demo agent with sample mechanical warranty policy",
            color="#f97316",
            agent_type="personal",
        )
        
        agent_info = await service.create_agent(agent_data, owner_id=1)
        
        return AgentCreateResponse(
            success=True,
            message=f"Demo agent '{name}' created successfully",
            agent=agent_info_to_response(agent_info),
        )
        
    except Exception as e:
        logger.exception(f"Failed to create demo agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create/text", response_model=AgentCreateResponse)
async def create_agent_from_text(
    request: AgentCreateRequest,
    service: AgentService = Depends(get_agent_service),
):
    """
    Create an agent from policy text.
    
    Use this when you already have extracted policy text.
    """
    try:
        agent_data = AgentCreate(
            name=request.name,
            policy_text=request.policy_text,
            policy_id=request.policy_id,
            description=request.description,
            color=request.color,
            agent_type=request.agent_type,
        )
        
        agent_info = await service.create_agent(agent_data, owner_id=1)
        
        return AgentCreateResponse(
            success=True,
            message=f"Agent '{request.name}' created successfully",
            agent=agent_info_to_response(agent_info),
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to create agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create/pdf", response_model=AgentCreateResponse)
async def create_agent_from_pdf(
    file: UploadFile = File(..., description="Policy PDF file"),
    name: str = Form(..., description="Agent name"),
    description: Optional[str] = Form(None, description="Agent description"),
    policy_id: Optional[str] = Form(None, description="Custom policy ID"),
    color: str = Form("#f97316", description="Theme color"),
    agent_type: str = Form("personal", description="Agent type: personal or shared"),
    service: AgentService = Depends(get_agent_service),
):
    """
    Create an agent from a PDF policy document.
    
    The PDF will be processed with OCR and the policy structure extracted.
    """
    try:
        # Read PDF file
        pdf_bytes = await file.read()
        
        agent_data = AgentCreate(
            name=name,
            policy_file=pdf_bytes,
            policy_id=policy_id,
            description=description,
            color=color,
            agent_type=agent_type,
        )
        
        agent_info = await service.create_agent(agent_data, owner_id=1)
        
        return AgentCreateResponse(
            success=True,
            message=f"Agent '{name}' created from PDF successfully",
            agent=agent_info_to_response(agent_info),
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to create agent from PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=AgentListResponse)
async def list_agents(
    agent_type: Optional[str] = Query(None, description="Filter by type: personal or shared"),
    status: Optional[str] = Query(None, description="Filter by status"),
    service: AgentService = Depends(get_agent_service),
):
    """
    List all agents.
    
    Can filter by type (personal/shared) and status.
    """
    agents = service.list_agents(
        owner_id=1,  # TODO: Get from auth
        agent_type=agent_type,
        status=status,
    )
    
    return AgentListResponse(
        success=True,
        agents=[agent_info_to_response(a) for a in agents],
        total=len(agents),
    )


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: int,
    service: AgentService = Depends(get_agent_service),
):
    """Get agent details by ID."""
    agent = service.get_agent(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return agent_info_to_response(agent)


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: int,
    request: AgentUpdateRequest,
    service: AgentService = Depends(get_agent_service),
):
    """Update agent details."""
    agent = service.update_agent(
        agent_id,
        name=request.name,
        description=request.description,
        color=request.color,
        status=request.status,
    )
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return agent_info_to_response(agent)


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: int,
    service: AgentService = Depends(get_agent_service),
):
    """Delete (archive) an agent."""
    success = service.delete_agent(agent_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return {"success": True, "message": "Agent archived successfully"}


# =============================================================================
# Ingestion Status Endpoints (Progress Tracking)
# =============================================================================

class IngestionStatusResponse(BaseModel):
    """Response for ingestion status."""
    job_id: str
    policy_id: str
    stage: str
    progress_percent: float
    current_step: str
    total_chunks: int
    processed_chunks: int
    started_at: str
    estimated_seconds_remaining: Optional[int]
    error_message: Optional[str]


@router.get("/ingestion/status/{job_id}", response_model=IngestionStatusResponse)
async def get_ingestion_status(
    job_id: str,
    status_service: IngestionStatusService = Depends(get_ingestion_status_service),
):
    """
    Get the current status of a policy ingestion job.
    
    Use this endpoint to poll for progress during long-running uploads.
    The frontend should poll every 2-3 seconds.
    
    Stages:
    - pending: Job created, waiting to start
    - reading_pdf: Reading PDF file
    - extracting_text: OCR/text extraction
    - chunking: Splitting text into chunks
    - classifying: LLM classification (slowest stage)
    - embedding: Generating vector embeddings
    - storing: Saving to vector store
    - completed: Done!
    - failed: Error occurred
    """
    progress = status_service.get_progress(job_id)
    
    if not progress:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    
    return IngestionStatusResponse(
        job_id=progress.job_id,
        policy_id=progress.policy_id,
        stage=progress.stage.value,
        progress_percent=progress.progress_percent,
        current_step=progress.current_step,
        total_chunks=progress.total_chunks,
        processed_chunks=progress.processed_chunks,
        started_at=progress.started_at.isoformat(),
        estimated_seconds_remaining=progress.estimated_seconds_remaining,
        error_message=progress.error_message,
    )


@router.get("/ingestion/status/policy/{policy_id}", response_model=IngestionStatusResponse)
async def get_ingestion_status_by_policy(
    policy_id: str,
    status_service: IngestionStatusService = Depends(get_ingestion_status_service),
):
    """
    Get ingestion status by policy ID.
    
    Returns the most recent ingestion job for the given policy.
    """
    progress = status_service.get_job_by_policy(policy_id)
    
    if not progress:
        raise HTTPException(status_code=404, detail="No ingestion job found for this policy")
    
    return IngestionStatusResponse(
        job_id=progress.job_id,
        policy_id=progress.policy_id,
        stage=progress.stage.value,
        progress_percent=progress.progress_percent,
        current_step=progress.current_step,
        total_chunks=progress.total_chunks,
        processed_chunks=progress.processed_chunks,
        started_at=progress.started_at.isoformat(),
        estimated_seconds_remaining=progress.estimated_seconds_remaining,
        error_message=progress.error_message,
    )


# =============================================================================
# User Limitations Endpoints (B2B)
# =============================================================================

@router.post("/{agent_id}/limitations", response_model=UserLimitationResponse)
async def add_user_limitation(
    agent_id: int,
    request: UserLimitationRequest,
    user_id: int = Query(1, description="User ID (from auth in production)"),
    service: AgentService = Depends(get_agent_service),
):
    """
    Add a user-specific limitation for B2B context.
    
    These limitations are injected into the chat context so the agent
    knows about user-specific constraints.
    
    Examples:
    - "User has used 3 of 4 annual roadside assists"
    - "User's deductible increased due to claim history"
    """
    agent = service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    limitation = service.add_user_limitation(
        user_id=user_id,
        agent_id=agent_id,
        limitation_type=request.limitation_type,
        title=request.title,
        description=request.description,
        severity=request.severity,
        current_value=request.current_value,
        max_value=request.max_value,
    )
    
    return UserLimitationResponse(
        id=limitation.id,
        limitation_type=limitation.limitation_type,
        title=limitation.title,
        description=limitation.description,
        severity=limitation.severity,
        current_value=limitation.current_value,
        max_value=limitation.max_value,
        is_active=limitation.is_active,
    )


@router.get("/{agent_id}/limitations", response_model=List[UserLimitationResponse])
async def get_user_limitations(
    agent_id: int,
    user_id: int = Query(1, description="User ID"),
    service: AgentService = Depends(get_agent_service),
):
    """Get all active limitations for a user on an agent."""
    limitations = service.get_user_limitations(user_id, agent_id)
    
    return [
        UserLimitationResponse(
            id=lim.id,
            limitation_type=lim.limitation_type,
            title=lim.title,
            description=lim.description,
            severity=lim.severity,
            current_value=lim.current_value,
            max_value=lim.max_value,
            is_active=lim.is_active,
        )
        for lim in limitations
    ]


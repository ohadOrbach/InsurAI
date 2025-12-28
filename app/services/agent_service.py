"""
Agent Service for Universal Insurance AI Agent.

Handles:
- Agent creation from policy uploads
- Agent management (list, update, delete)
- B2C personal agents
- B2B shared agents with user limitations
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List

from app.db.models import Agent, AgentType, AgentStatus, UserLimitation
from app.schema import PolicyDocument
from app.services.pdf_ingestion import PDFIngestionPipeline
from app.services.policy_engine import PolicyEngine
from app.services.vector_store import PolicyVectorizer

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class AgentCreate:
    """Data for creating a new agent."""
    name: str
    policy_file: Optional[bytes] = None  # PDF bytes
    policy_text: Optional[str] = None    # Raw text
    policy_id: Optional[str] = None      # Custom ID
    description: Optional[str] = None
    color: str = "#f97316"
    agent_type: str = "personal"  # "personal" or "shared"


@dataclass
class AgentInfo:
    """Agent information for display."""
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
    created_at: datetime
    last_used_at: Optional[datetime]
    total_conversations: int
    total_messages: int
    coverage_summary: dict = field(default_factory=dict)


@dataclass
class UserLimitationInfo:
    """User limitation for B2B context."""
    id: int
    limitation_type: str
    title: str
    description: str
    severity: str
    current_value: Optional[str]
    max_value: Optional[str]
    is_active: bool


# =============================================================================
# Agent Service
# =============================================================================

class AgentService:
    """
    Service for managing insurance agents.
    
    Supports:
    - B2C: Personal agents owned by individual users
    - B2B: Shared agents owned by organizations
    """
    
    def __init__(
        self,
        pdf_pipeline: Optional[PDFIngestionPipeline] = None,
        vectorizer: Optional[PolicyVectorizer] = None,
    ):
        self.pdf_pipeline = pdf_pipeline or PDFIngestionPipeline(use_mock=False)
        # Use real embeddings for better semantic search
        self.vectorizer = vectorizer or PolicyVectorizer(use_mock=False)
        
        # In-memory storage (replace with database in production)
        self._agents: dict[int, dict] = {}
        self._user_limitations: dict[int, list[dict]] = {}
        self._next_id = 1
    
    async def create_agent(
        self,
        data: AgentCreate,
        owner_id: Optional[int] = None,
        organization_id: Optional[int] = None,
    ) -> AgentInfo:
        """
        Create a new agent from a policy document.
        
        Args:
            data: Agent creation data
            owner_id: User ID for B2C agents
            organization_id: Organization ID for B2B agents
            
        Returns:
            Created agent info
        """
        import time
        start_time = time.time()
        
        # Generate agent ID
        agent_id = self._next_id
        self._next_id += 1
        
        # Generate policy ID if not provided
        policy_id = data.policy_id or f"POL-{datetime.now().strftime('%Y%m%d')}-{agent_id:04d}"
        
        logger.info(f"Creating agent '{data.name}' with policy {policy_id}")
        
        # Process policy document
        policy_doc = None
        raw_text = None  # Store raw text for RAG
        
        if data.policy_file:
            # Save temp file and process
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(data.policy_file)
                temp_path = f.name
            
            result = self.pdf_pipeline.ingest_pdf(temp_path)
            if result.success:
                policy_doc = result.policy_document
                # Store raw OCR text for RAG
                raw_text = result.ocr_result.full_text if result.ocr_result else None
            else:
                raise ValueError(f"Failed to process PDF: {result.errors}")
                
        elif data.policy_text:
            result = self.pdf_pipeline.ingest_text(data.policy_text)
            if result.success:
                policy_doc = result.policy_document
                raw_text = data.policy_text  # Use provided text
            else:
                raise ValueError(f"Failed to process text: {result.errors}")
        else:
            # Use demo policy
            policy_engine = PolicyEngine()
            policy_doc = policy_engine.policy
        
        # Update policy ID
        if policy_doc:
            policy_doc.policy_meta.policy_id = policy_id
        
        # Create policy engine for this agent
        policy_engine = PolicyEngine(policy=policy_doc)
        
        # Vectorize policy for RAG - use structured chunks
        structured_chunks = self.vectorizer.vectorize_policy(policy_doc)
        
        # Also vectorize raw text for comprehensive RAG coverage
        # This ensures all policy content is searchable, even if structure extraction is incomplete
        raw_chunks = 0
        if raw_text and len(raw_text) > 500:  # Only if we have substantial text
            # Extract page breaks from OCR result for accurate citations
            page_breaks = None
            if result and result.ocr_result and result.ocr_result.pages:
                page_breaks = []
                char_pos = 0
                for page in result.ocr_result.pages:
                    char_pos += len(page.full_text)
                    page_breaks.append(char_pos)
            
            raw_chunks = self.vectorizer.vectorize_raw_text(
                raw_text=raw_text,
                policy_id=policy_id,
                chunk_size=1000,
                chunk_overlap=200,
                page_breaks=page_breaks,
            )
            logger.info(f"Added {raw_chunks} raw text chunks with page numbers for citations")
        
        # Build coverage summary
        coverage_summary = {
            "total_categories": len(policy_doc.coverage_details),
            "total_inclusions": sum(len(c.items_included) for c in policy_doc.coverage_details),
            "total_exclusions": sum(len(c.items_excluded) for c in policy_doc.coverage_details),
            "categories": [c.category for c in policy_doc.coverage_details],
        }
        
        # Determine agent type
        agent_type = AgentType.SHARED if data.agent_type == "shared" else AgentType.PERSONAL
        
        processing_time = (time.time() - start_time) * 1000
        
        # Store agent
        agent_data = {
            "id": agent_id,
            "name": data.name,
            "description": data.description or f"Insurance agent for {policy_doc.policy_meta.policy_type}",
            "agent_type": agent_type.value,
            "status": AgentStatus.ACTIVE.value,
            "policy_id": policy_id,
            "policy_type": policy_doc.policy_meta.policy_type,
            "provider_name": policy_doc.policy_meta.provider_name,
            "color": data.color,
            "avatar_url": None,
            "owner_id": owner_id,
            "organization_id": organization_id,
            "created_at": datetime.now(),
            "last_used_at": None,
            "processing_time_ms": processing_time,
            "total_conversations": 0,
            "total_messages": 0,
            "policy_summary": policy_engine.get_policy_summary(),
            "coverage_categories": coverage_summary,
            "policy_document": policy_doc,  # Store for chat service
        }
        
        self._agents[agent_id] = agent_data
        
        logger.info(f"Agent '{data.name}' created successfully in {processing_time:.0f}ms")
        
        return self._to_agent_info(agent_data)
    
    def get_agent(self, agent_id: int) -> Optional[AgentInfo]:
        """Get agent by ID."""
        agent_data = self._agents.get(agent_id)
        if agent_data:
            return self._to_agent_info(agent_data)
        return None
    
    def get_agent_policy_document(self, agent_id: int) -> Optional[PolicyDocument]:
        """Get the policy document for an agent."""
        agent_data = self._agents.get(agent_id)
        if agent_data:
            return agent_data.get("policy_document")
        return None
    
    def list_agents(
        self,
        owner_id: Optional[int] = None,
        organization_id: Optional[int] = None,
        agent_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[AgentInfo]:
        """
        List agents with optional filters.
        
        Args:
            owner_id: Filter by owner (B2C)
            organization_id: Filter by organization (B2B)
            agent_type: Filter by type ("personal" or "shared")
            status: Filter by status
            
        Returns:
            List of agent info
        """
        agents = []
        
        for agent_data in self._agents.values():
            # Apply filters
            if owner_id and agent_data.get("owner_id") != owner_id:
                continue
            if organization_id and agent_data.get("organization_id") != organization_id:
                continue
            if agent_type and agent_data.get("agent_type") != agent_type:
                continue
            if status and agent_data.get("status") != status:
                continue
            
            agents.append(self._to_agent_info(agent_data))
        
        # Sort by created_at descending
        agents.sort(key=lambda a: a.created_at, reverse=True)
        
        return agents
    
    def update_agent(
        self,
        agent_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Optional[AgentInfo]:
        """Update agent details."""
        agent_data = self._agents.get(agent_id)
        if not agent_data:
            return None
        
        if name:
            agent_data["name"] = name
        if description:
            agent_data["description"] = description
        if color:
            agent_data["color"] = color
        if status:
            agent_data["status"] = status
        
        return self._to_agent_info(agent_data)
    
    def delete_agent(self, agent_id: int) -> bool:
        """Delete (archive) an agent."""
        if agent_id in self._agents:
            self._agents[agent_id]["status"] = AgentStatus.ARCHIVED.value
            return True
        return False
    
    def record_usage(self, agent_id: int, messages: int = 1):
        """Record agent usage (for stats)."""
        agent_data = self._agents.get(agent_id)
        if agent_data:
            agent_data["last_used_at"] = datetime.now()
            agent_data["total_messages"] += messages
    
    def increment_conversations(self, agent_id: int):
        """Increment conversation count."""
        agent_data = self._agents.get(agent_id)
        if agent_data:
            agent_data["total_conversations"] += 1
    
    # =========================================================================
    # User Limitations (B2B)
    # =========================================================================
    
    def add_user_limitation(
        self,
        user_id: int,
        agent_id: int,
        limitation_type: str,
        title: str,
        description: str,
        severity: str = "info",
        current_value: Optional[str] = None,
        max_value: Optional[str] = None,
    ) -> UserLimitationInfo:
        """
        Add a user-specific limitation for B2B context injection.
        
        Examples:
        - "User has used 3 of 4 annual roadside assists"
        - "User's deductible is 600 NIS due to claim history"
        - "User is in 30-day grace period for premium payment"
        """
        limitation_id = len(self._user_limitations.get(user_id, [])) + 1
        
        limitation_data = {
            "id": limitation_id,
            "user_id": user_id,
            "agent_id": agent_id,
            "limitation_type": limitation_type,
            "title": title,
            "description": description,
            "severity": severity,
            "current_value": current_value,
            "max_value": max_value,
            "is_active": True,
            "created_at": datetime.now(),
        }
        
        if user_id not in self._user_limitations:
            self._user_limitations[user_id] = []
        
        self._user_limitations[user_id].append(limitation_data)
        
        return UserLimitationInfo(
            id=limitation_id,
            limitation_type=limitation_type,
            title=title,
            description=description,
            severity=severity,
            current_value=current_value,
            max_value=max_value,
            is_active=True,
        )
    
    def get_user_limitations(
        self,
        user_id: int,
        agent_id: Optional[int] = None,
    ) -> List[UserLimitationInfo]:
        """Get active limitations for a user."""
        limitations = []
        
        for lim in self._user_limitations.get(user_id, []):
            if not lim.get("is_active"):
                continue
            if agent_id and lim.get("agent_id") != agent_id:
                continue
            
            limitations.append(UserLimitationInfo(
                id=lim["id"],
                limitation_type=lim["limitation_type"],
                title=lim["title"],
                description=lim["description"],
                severity=lim["severity"],
                current_value=lim.get("current_value"),
                max_value=lim.get("max_value"),
                is_active=lim["is_active"],
            ))
        
        return limitations
    
    def build_limitation_context(
        self,
        user_id: int,
        agent_id: int,
    ) -> str:
        """
        Build context string with user limitations for B2B chat.
        
        This context is injected into the system prompt so the agent
        knows about user-specific limitations.
        """
        limitations = self.get_user_limitations(user_id, agent_id)
        
        if not limitations:
            return ""
        
        context_parts = [
            "\n## USER-SPECIFIC LIMITATIONS",
            "The following limitations apply specifically to this user:",
            "",
        ]
        
        for lim in limitations:
            severity_emoji = {
                "info": "ℹ️",
                "warning": "⚠️",
                "critical": "🚨",
            }.get(lim.severity, "ℹ️")
            
            context_parts.append(f"{severity_emoji} **{lim.title}**")
            context_parts.append(f"   {lim.description}")
            
            if lim.current_value and lim.max_value:
                context_parts.append(f"   Status: {lim.current_value} / {lim.max_value}")
            
            context_parts.append("")
        
        context_parts.append("Please factor these limitations into your responses.")
        
        return "\n".join(context_parts)
    
    # =========================================================================
    # Helpers
    # =========================================================================
    
    def _to_agent_info(self, data: dict) -> AgentInfo:
        """Convert internal data to AgentInfo."""
        return AgentInfo(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            agent_type=data["agent_type"],
            status=data["status"],
            policy_id=data["policy_id"],
            policy_type=data.get("policy_type"),
            provider_name=data.get("provider_name"),
            color=data.get("color", "#f97316"),
            avatar_url=data.get("avatar_url"),
            created_at=data["created_at"],
            last_used_at=data.get("last_used_at"),
            total_conversations=data.get("total_conversations", 0),
            total_messages=data.get("total_messages", 0),
            coverage_summary=data.get("coverage_categories", {}),
        )


# =============================================================================
# Global Instance
# =============================================================================

_agent_service: Optional[AgentService] = None


def get_agent_service() -> AgentService:
    """Get or create the global agent service instance."""
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service


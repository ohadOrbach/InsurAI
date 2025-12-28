"""
SQLAlchemy database models for Universal Insurance AI Agent.

Includes models for:
- Users and authentication
- Policies and coverage
- Agents (B2C personal and B2B shared)
- Chat sessions and messages
- User limitations for B2B context
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


# =============================================================================
# Enums
# =============================================================================

class AgentType(str, PyEnum):
    """Type of agent."""
    PERSONAL = "personal"  # B2C - one user, one policy
    SHARED = "shared"      # B2B - multiple users, one policy template


class AgentStatus(str, PyEnum):
    """Status of an agent."""
    CREATING = "creating"    # Being processed
    ACTIVE = "active"        # Ready to use
    PAUSED = "paused"        # Temporarily disabled
    ARCHIVED = "archived"    # Soft deleted


# =============================================================================
# User Model
# =============================================================================

class User(Base):
    """User model for authentication and ownership."""
    
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint('email', name='uq_users_email'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # User type for B2C vs B2B
    user_type = Column(String(20), default="b2c")  # "b2c" or "b2b"
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    
    # Relationships
    agents = relationship("Agent", back_populates="owner", foreign_keys="Agent.owner_id")
    chat_sessions = relationship("ChatSession", back_populates="user")
    user_limitations = relationship("UserLimitation", back_populates="user")


# =============================================================================
# Organization Model (for B2B)
# =============================================================================

class Organization(Base):
    """Organization for B2B customers."""
    
    __tablename__ = "organizations"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, index=True)
    logo_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # B2B settings
    default_agent_type = Column(String(20), default="shared")
    max_agents = Column(Integer, default=10)
    
    # Relationships
    agents = relationship("Agent", back_populates="organization")
    members = relationship("User", backref="organization")


# =============================================================================
# Agent Model
# =============================================================================

class Agent(Base):
    """
    Insurance Agent - An AI assistant tied to a specific policy.
    
    B2C (Personal): One user owns the agent, policy has personal details
    B2B (Shared): Organization owns the agent, policy is generic template
    """
    
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Agent identity
    name = Column(String(255), nullable=False)  # e.g., "My Car Insurance", "Health Policy Agent"
    description = Column(Text, nullable=True)
    avatar_url = Column(String(500), nullable=True)
    color = Column(String(20), default="#f97316")  # Brand color for UI
    
    # Agent type and status
    agent_type = Column(Enum(AgentType), default=AgentType.PERSONAL)
    status = Column(Enum(AgentStatus), default=AgentStatus.CREATING)
    
    # Ownership (B2C: user owns, B2B: organization owns)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    
    # Policy reference
    policy_id = Column(String(100), nullable=False, index=True)
    policy_type = Column(String(100), nullable=True)  # "Car Insurance", "Health", etc.
    provider_name = Column(String(255), nullable=True)
    
    # Policy data (stored JSON for quick access)
    policy_summary = Column(JSON, nullable=True)
    coverage_categories = Column(JSON, nullable=True)  # Quick lookup
    
    # Processing info
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    processing_time_ms = Column(Float, nullable=True)
    
    # Stats
    total_conversations = Column(Integer, default=0)
    total_messages = Column(Integer, default=0)
    
    # Relationships
    owner = relationship("User", back_populates="agents", foreign_keys=[owner_id])
    organization = relationship("Organization", back_populates="agents")
    chat_sessions = relationship("ChatSession", back_populates="agent")


# =============================================================================
# User Limitation Model (for B2B context injection)
# =============================================================================

class UserLimitation(Base):
    """
    User-specific limitations for B2B shared agents.
    
    When a B2B user chats with a shared agent, their specific limitations
    are injected into the conversation context.
    
    Examples:
    - "User has reached 3/4 annual claims"
    - "User's deductible is increased due to claim history"
    - "User is in grace period for payment"
    """
    
    __tablename__ = "user_limitations"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Links
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    
    # Limitation details
    limitation_type = Column(String(50), nullable=False)  # "claim_limit", "payment", "coverage_cap"
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(20), default="info")  # "info", "warning", "critical"
    
    # Values
    current_value = Column(String(100), nullable=True)  # e.g., "3"
    max_value = Column(String(100), nullable=True)  # e.g., "4"
    
    # Validity
    is_active = Column(Boolean, default=True)
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="user_limitations")
    agent = relationship("Agent")


# =============================================================================
# Policy Model
# =============================================================================

class Policy(Base):
    """Stored policy document with extracted data."""
    
    __tablename__ = "policies"
    __table_args__ = (
        UniqueConstraint('policy_id', name='uq_policies_policy_id'),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    policy_id = Column(String(100), unique=True, index=True, nullable=False)
    
    # Policy metadata
    provider_name = Column(String(255), nullable=True)
    policy_type = Column(String(100), nullable=True)
    status = Column(String(50), default="active")
    
    # Dates
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    
    # Full policy data (JSON)
    policy_data = Column(JSON, nullable=True)
    raw_text = Column(Text, nullable=True)
    
    # Source info
    source_file = Column(String(500), nullable=True)
    is_template = Column(Boolean, default=False)  # True for B2B generic policies
    
    # Processing
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Owner (optional - for personal policies)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)


# =============================================================================
# Chat Session Model
# =============================================================================

class ChatSession(Base):
    """A chat conversation session."""
    
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, index=True, nullable=False)
    
    # Links
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    policy_id = Column(String(100), nullable=True)
    
    # Session metadata
    title = Column(String(255), nullable=True)  # Auto-generated from first message
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    agent = relationship("Agent", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


# =============================================================================
# Chat Message Model
# =============================================================================

class ChatMessage(Base):
    """A single message in a chat session."""
    
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(100), unique=True, index=True, nullable=False)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    
    # Message content
    role = Column(String(20), nullable=False)  # "user", "assistant", "system"
    content = Column(Text, nullable=False)
    
    # Message metadata (renamed from 'metadata' which is reserved in SQLAlchemy)
    message_metadata = Column(JSON, nullable=True)  # LLM usage, coverage results, etc.
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session = relationship("ChatSession", back_populates="messages")

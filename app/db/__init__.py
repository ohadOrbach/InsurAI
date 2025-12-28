"""
Database module for Universal Insurance AI Agent.

Provides SQLAlchemy models and database session management.
"""

from app.db.base import Base, engine, SessionLocal, get_db
from app.db.models import User, Policy, ChatSession, ChatMessage

__all__ = [
    "Base",
    "engine",
    "SessionLocal",
    "get_db",
    "User",
    "Policy",
    "ChatSession",
    "ChatMessage",
]


"""
Chat Repositories for chat session and message data access.

Provides specialized methods for chat-related database operations.
"""

from typing import Optional, Sequence
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import ChatSession, ChatMessage
from app.repositories.base import BaseRepository


class ChatSessionRepository(BaseRepository[ChatSession]):
    """
    Repository for ChatSession model operations.
    
    Extends BaseRepository with chat session-specific methods.
    """
    
    def __init__(self, db: Session):
        """Initialize the chat session repository."""
        super().__init__(db, ChatSession)
    
    # =========================================================================
    # Session-Specific Read Operations
    # =========================================================================
    
    def get_by_user(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 50,
        active_only: bool = True,
    ) -> Sequence[ChatSession]:
        """
        Get chat sessions for a specific user.
        
        Args:
            user_id: User ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            active_only: Only return active sessions
            
        Returns:
            List of chat sessions
        """
        query = self.db.query(ChatSession).filter(
            ChatSession.user_id == user_id
        )
        
        if active_only:
            query = query.filter(ChatSession.is_active == True)
        
        return query.order_by(
            ChatSession.updated_at.desc()
        ).offset(skip).limit(limit).all()
    
    def get_by_policy(
        self,
        policy_id: str,
        user_id: Optional[str] = None,
    ) -> Sequence[ChatSession]:
        """
        Get chat sessions for a specific policy.
        
        Args:
            policy_id: Policy ID
            user_id: Filter by user (optional)
            
        Returns:
            List of chat sessions
        """
        query = self.db.query(ChatSession).filter(
            ChatSession.policy_id == policy_id
        )
        
        if user_id:
            query = query.filter(ChatSession.user_id == user_id)
        
        return query.order_by(ChatSession.updated_at.desc()).all()
    
    def get_recent_sessions(
        self,
        user_id: Optional[str] = None,
        limit: int = 10,
    ) -> Sequence[ChatSession]:
        """
        Get most recently updated sessions.
        
        Args:
            user_id: Filter by user (optional)
            limit: Maximum number of sessions
            
        Returns:
            List of recent chat sessions
        """
        query = self.db.query(ChatSession).filter(
            ChatSession.is_active == True
        )
        
        if user_id:
            query = query.filter(ChatSession.user_id == user_id)
        
        return query.order_by(ChatSession.updated_at.desc()).limit(limit).all()
    
    def count_by_user(self, user_id: str, active_only: bool = True) -> int:
        """
        Count sessions for a specific user.
        
        Args:
            user_id: User ID
            active_only: Only count active sessions
            
        Returns:
            Number of sessions
        """
        from sqlalchemy import func
        
        query = self.db.query(func.count(ChatSession.id)).filter(
            ChatSession.user_id == user_id
        )
        
        if active_only:
            query = query.filter(ChatSession.is_active == True)
        
        return query.scalar() or 0
    
    # =========================================================================
    # Session-Specific Create/Update Operations
    # =========================================================================
    
    def create_session(
        self,
        user_id: Optional[str] = None,
        policy_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> ChatSession:
        """
        Create a new chat session.
        
        Args:
            user_id: User ID (optional for anonymous)
            policy_id: Associated policy ID (optional)
            title: Session title (optional)
            
        Returns:
            Created session instance
        """
        return self.create(
            user_id=user_id,
            policy_id=policy_id,
            title=title,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    
    def update_title(self, session_id: str, title: str) -> Optional[ChatSession]:
        """
        Update session title.
        
        Args:
            session_id: Session ID
            title: New title
            
        Returns:
            Updated session if found, None otherwise
        """
        return self.update(session_id, title=title)
    
    def close_session(self, session_id: str) -> Optional[ChatSession]:
        """
        Close/deactivate a chat session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Updated session if found, None otherwise
        """
        return self.update(session_id, is_active=False)
    
    def touch_session(self, session_id: str) -> Optional[ChatSession]:
        """
        Update the session's updated_at timestamp.
        
        Args:
            session_id: Session ID
            
        Returns:
            Updated session if found, None otherwise
        """
        return self.update(session_id, updated_at=datetime.utcnow())
    
    # =========================================================================
    # Bulk Operations
    # =========================================================================
    
    def delete_by_user(self, user_id: str) -> int:
        """
        Delete all sessions for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Number of sessions deleted
        """
        result = self.db.query(ChatSession).filter(
            ChatSession.user_id == user_id
        ).delete(synchronize_session=False)
        
        self.db.commit()
        return result
    
    def close_inactive_sessions(self, days: int = 7) -> int:
        """
        Close sessions inactive for a specified number of days.
        
        Args:
            days: Number of days of inactivity
            
        Returns:
            Number of sessions closed
        """
        from datetime import timedelta
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        result = self.db.query(ChatSession).filter(
            ChatSession.is_active == True,
            ChatSession.updated_at < cutoff,
        ).update(
            {"is_active": False, "updated_at": datetime.utcnow()},
            synchronize_session=False,
        )
        
        self.db.commit()
        return result


class ChatMessageRepository(BaseRepository[ChatMessage]):
    """
    Repository for ChatMessage model operations.
    
    Extends BaseRepository with chat message-specific methods.
    """
    
    def __init__(self, db: Session):
        """Initialize the chat message repository."""
        super().__init__(db, ChatMessage)
    
    # =========================================================================
    # Message-Specific Read Operations
    # =========================================================================
    
    def get_by_session(
        self,
        session_id: str,
        skip: int = 0,
        limit: int = 100,
        order_asc: bool = True,
    ) -> Sequence[ChatMessage]:
        """
        Get messages for a specific session.
        
        Args:
            session_id: Session ID
            skip: Number of messages to skip
            limit: Maximum number of messages
            order_asc: Order by created_at ascending (oldest first)
            
        Returns:
            List of messages
        """
        query = self.db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        )
        
        if order_asc:
            query = query.order_by(ChatMessage.created_at.asc())
        else:
            query = query.order_by(ChatMessage.created_at.desc())
        
        return query.offset(skip).limit(limit).all()
    
    def get_last_messages(
        self,
        session_id: str,
        count: int = 10,
    ) -> Sequence[ChatMessage]:
        """
        Get the last N messages from a session.
        
        Args:
            session_id: Session ID
            count: Number of messages to retrieve
            
        Returns:
            List of messages (oldest to newest)
        """
        # Get messages in descending order, then reverse
        messages = self.db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(
            ChatMessage.created_at.desc()
        ).limit(count).all()
        
        return list(reversed(messages))
    
    def get_by_role(
        self,
        session_id: str,
        role: str,
    ) -> Sequence[ChatMessage]:
        """
        Get messages by role for a session.
        
        Args:
            session_id: Session ID
            role: Message role ("user", "assistant", "system")
            
        Returns:
            List of messages with that role
        """
        return self.db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id,
            ChatMessage.role == role,
        ).order_by(ChatMessage.created_at.asc()).all()
    
    def count_by_session(self, session_id: str) -> int:
        """
        Count messages in a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Number of messages
        """
        from sqlalchemy import func
        return self.db.query(func.count(ChatMessage.id)).filter(
            ChatMessage.session_id == session_id
        ).scalar() or 0
    
    # =========================================================================
    # Message-Specific Create Operations
    # =========================================================================
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> ChatMessage:
        """
        Add a message to a session.
        
        Args:
            session_id: Session ID
            role: Message role ("user", "assistant", "system")
            content: Message content
            metadata: Additional metadata (optional)
            
        Returns:
            Created message instance
        """
        return self.create(
            session_id=session_id,
            role=role,
            content=content,
            message_metadata=metadata or {},
            created_at=datetime.utcnow(),
        )
    
    def add_user_message(
        self,
        session_id: str,
        content: str,
    ) -> ChatMessage:
        """
        Add a user message to a session.
        
        Args:
            session_id: Session ID
            content: Message content
            
        Returns:
            Created message instance
        """
        return self.add_message(session_id, "user", content)
    
    def add_assistant_message(
        self,
        session_id: str,
        content: str,
        model: Optional[str] = None,
        usage: Optional[dict] = None,
    ) -> ChatMessage:
        """
        Add an assistant message to a session.
        
        Args:
            session_id: Session ID
            content: Message content
            model: Model used for generation
            usage: Token usage stats
            
        Returns:
            Created message instance
        """
        metadata = {}
        if model:
            metadata["model"] = model
        if usage:
            metadata["usage"] = usage
        
        return self.add_message(session_id, "assistant", content, metadata)
    
    # =========================================================================
    # Bulk Operations
    # =========================================================================
    
    def delete_by_session(self, session_id: str) -> int:
        """
        Delete all messages in a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Number of messages deleted
        """
        result = self.db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).delete(synchronize_session=False)
        
        self.db.commit()
        return result


"""
User Repository for user data access.

Provides specialized methods for user-related database operations.
"""

from typing import Optional, Sequence
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import User
from app.repositories.base import BaseRepository
from app.core.security import get_password_hash, verify_password


class UserRepository(BaseRepository[User]):
    """
    Repository for User model operations.
    
    Extends BaseRepository with user-specific methods like
    authentication and email lookup.
    """
    
    def __init__(self, db: Session):
        """Initialize the user repository."""
        super().__init__(db, User)
    
    # =========================================================================
    # User-Specific Read Operations
    # =========================================================================
    
    def get_by_email(self, email: str) -> Optional[User]:
        """
        Get a user by email address.
        
        Args:
            email: User's email address (case-insensitive)
            
        Returns:
            User if found, None otherwise
        """
        return self.db.query(User).filter(
            User.email == email.lower()
        ).first()
    
    def get_active_users(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[User]:
        """
        Get all active users.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of active users
        """
        return self.db.query(User).filter(
            User.is_active == True
        ).offset(skip).limit(limit).all()
    
    def get_superusers(self) -> Sequence[User]:
        """
        Get all superusers.
        
        Returns:
            List of superusers
        """
        return self.db.query(User).filter(
            User.is_superuser == True
        ).all()
    
    def email_exists(self, email: str) -> bool:
        """
        Check if an email is already registered.
        
        Args:
            email: Email address to check
            
        Returns:
            True if email exists, False otherwise
        """
        return self.db.query(
            self.db.query(User).filter(User.email == email.lower()).exists()
        ).scalar()
    
    # =========================================================================
    # User-Specific Create/Update Operations
    # =========================================================================
    
    def create_user(
        self,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        is_superuser: bool = False,
    ) -> User:
        """
        Create a new user with hashed password.
        
        Args:
            email: User's email address
            password: Plain text password (will be hashed)
            full_name: User's full name
            is_superuser: Whether user is a superuser
            
        Returns:
            Created user instance
            
        Raises:
            ValueError: If email already exists
        """
        if self.email_exists(email):
            raise ValueError(f"Email '{email}' is already registered")
        
        return self.create(
            email=email.lower(),
            hashed_password=get_password_hash(password),
            full_name=full_name,
            is_superuser=is_superuser,
            is_active=True,
            created_at=datetime.utcnow(),
        )
    
    def update_password(self, user_id: str, new_password: str) -> Optional[User]:
        """
        Update a user's password.
        
        Args:
            user_id: User's ID
            new_password: New plain text password (will be hashed)
            
        Returns:
            Updated user if found, None otherwise
        """
        return self.update(
            user_id,
            hashed_password=get_password_hash(new_password),
        )
    
    def update_profile(
        self,
        user_id: str,
        full_name: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Optional[User]:
        """
        Update a user's profile information.
        
        Args:
            user_id: User's ID
            full_name: New full name (optional)
            email: New email (optional)
            
        Returns:
            Updated user if found, None otherwise
            
        Raises:
            ValueError: If new email already exists
        """
        updates = {}
        
        if full_name is not None:
            updates['full_name'] = full_name
        
        if email is not None:
            email = email.lower()
            user = self.get_by_id(user_id)
            if user and user.email != email and self.email_exists(email):
                raise ValueError(f"Email '{email}' is already registered")
            updates['email'] = email
        
        if not updates:
            return self.get_by_id(user_id)
        
        return self.update(user_id, **updates)
    
    def activate_user(self, user_id: str) -> Optional[User]:
        """
        Activate a user account.
        
        Args:
            user_id: User's ID
            
        Returns:
            Updated user if found, None otherwise
        """
        return self.update(user_id, is_active=True)
    
    def deactivate_user(self, user_id: str) -> Optional[User]:
        """
        Deactivate a user account.
        
        Args:
            user_id: User's ID
            
        Returns:
            Updated user if found, None otherwise
        """
        return self.update(user_id, is_active=False)
    
    # =========================================================================
    # Authentication Methods
    # =========================================================================
    
    def authenticate(self, email: str, password: str) -> Optional[User]:
        """
        Authenticate a user with email and password.
        
        Args:
            email: User's email address
            password: Plain text password
            
        Returns:
            User if credentials valid and user is active, None otherwise
        """
        user = self.get_by_email(email)
        
        if not user:
            return None
        
        if not user.is_active:
            return None
        
        if not verify_password(password, user.hashed_password):
            return None
        
        return user


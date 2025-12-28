"""
User-related Pydantic schemas for authentication.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
import re


class UserBase(BaseModel):
    """Base user schema with common fields."""
    
    email: EmailStr = Field(..., description="User's email address")
    full_name: Optional[str] = Field(None, description="User's full name", max_length=100)


class UserCreate(UserBase):
    """Schema for user registration."""
    
    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="User's password (min 8 characters)"
    )
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLogin(BaseModel):
    """Schema for user login."""
    
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


class UserResponse(UserBase):
    """Schema for user response (no sensitive data)."""
    
    id: str = Field(..., description="Unique user ID")
    is_active: bool = Field(default=True, description="Whether user is active")
    created_at: datetime = Field(..., description="Account creation timestamp")
    
    model_config = {"from_attributes": True}


class UserInDB(UserBase):
    """Schema for user stored in database (includes hashed password)."""
    
    id: str
    hashed_password: str
    is_active: bool = True
    is_superuser: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = {"from_attributes": True}


class Token(BaseModel):
    """Schema for JWT token response."""
    
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")


class TokenPayload(BaseModel):
    """Schema for JWT token payload."""
    
    sub: str = Field(..., description="Subject (user ID)")
    exp: int = Field(..., description="Expiration timestamp")
    iat: int = Field(..., description="Issued at timestamp")
    type: str = Field(default="access", description="Token type")


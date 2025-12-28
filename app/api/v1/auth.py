"""
Authentication API endpoints.

Provides user registration, login, and profile management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.security import verify_token
from app.db.base import get_db
from app.db.models import User
from app.schemas.user import UserCreate, UserLogin, UserResponse, Token
from app.services.auth_service import AuthService


router = APIRouter()

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# =============================================================================
# Dependencies
# =============================================================================


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Get the current authenticated user from JWT token.
    
    Args:
        token: JWT access token
        db: Database session
        
    Returns:
        Current user
        
    Raises:
        HTTPException: If token invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = verify_token(token)
    if payload is None:
        raise credentials_exception
    
    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    auth_service = AuthService(db)
    user = auth_service.get_user_by_id(user_id)
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )
    
    return user


async def get_current_user_optional(
    token: str = Depends(OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)),
    db: Session = Depends(get_db),
) -> User | None:
    """
    Get the current user if authenticated, None otherwise.
    
    Useful for endpoints that work both authenticated and anonymously.
    """
    if not token:
        return None
    
    try:
        return await get_current_user(token, db)
    except HTTPException:
        return None


# =============================================================================
# Auth Endpoints
# =============================================================================


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account with email and password.",
)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    """Register a new user account."""
    auth_service = AuthService(db)
    
    try:
        user = auth_service.create_user(user_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post(
    "/login",
    response_model=Token,
    summary="Login and get access token",
    description="Authenticate with email and password to receive a JWT access token.",
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Login and receive access token."""
    auth_service = AuthService(db)
    
    user = auth_service.authenticate_user(form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_data = auth_service.create_token_for_user(user)
    
    return Token(**token_data)


@router.post(
    "/login/json",
    response_model=Token,
    summary="Login with JSON body",
    description="Alternative login endpoint that accepts JSON body instead of form data.",
)
async def login_json(
    credentials: UserLogin,
    db: Session = Depends(get_db),
):
    """Login with JSON body."""
    auth_service = AuthService(db)
    
    user = auth_service.authenticate_user(credentials.email, credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    token_data = auth_service.create_token_for_user(user)
    
    return Token(**token_data)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get the profile of the currently authenticated user.",
)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """Get current user profile."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )


@router.put(
    "/me",
    response_model=UserResponse,
    summary="Update current user",
    description="Update the profile of the currently authenticated user.",
)
async def update_me(
    full_name: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update current user profile."""
    auth_service = AuthService(db)
    
    user = auth_service.update_user(current_user, full_name=full_name)
    
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout",
    description="Logout the current user. Note: Token remains valid until expiration.",
)
async def logout(
    current_user: User = Depends(get_current_user),
):
    """
    Logout endpoint.
    
    Note: Since we use stateless JWT tokens, this endpoint is mainly
    for frontend to clear the token. The token remains valid until expiration.
    For production, consider implementing token blacklisting.
    """
    return {
        "success": True,
        "message": "Successfully logged out",
    }


@router.get(
    "/verify",
    summary="Verify token",
    description="Verify if the current token is valid.",
)
async def verify_auth(
    current_user: User = Depends(get_current_user),
):
    """Verify authentication token."""
    return {
        "valid": True,
        "user_id": current_user.id,
        "email": current_user.email,
    }


"""
FastAPI Application Entry Point for Universal Insurance AI Agent.

A RAG-based conversational platform for insurance policy documents.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import router as api_v1_router
from app.core.config import settings
from app.db.base import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    # Startup
    print("🚀 Starting Universal Insurance AI Agent...")
    print(f"📋 API Version: {settings.API_VERSION}")
    print(f"🗄️  Database: {settings.DATABASE_URL}")
    
    # Initialize database tables
    init_db()
    print("✅ Database initialized")
    
    print(f"📖 Docs: http://localhost:{settings.PORT}/docs")
    
    yield
    
    # Shutdown
    print("👋 Shutting down...")


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="""
## Universal Insurance AI Agent API

A RAG-based conversational platform for insurance policy documents.

### Features

* **Authentication** - Secure user registration and JWT-based login
* **Policy Ingestion** - Upload and process PDF insurance documents
* **Coverage Check** - Query coverage status for specific items
* **Semantic Search** - Find relevant policy information using AI
* **Chat Interface** - Conversational AI for policy questions

### Coverage Guardrail Logic (PRD 3.2)

1. **Check Exclusions First** - If item is excluded, return immediately
2. **Check Inclusions** - Verify item is explicitly covered
3. **Check Conditionals** - Validate usage limits and conditions

### Financial Context (PRD 3.3)

Every positive response includes:
- Deductible amount
- Coverage cap
- Special conditions

### Authentication

Most endpoints require JWT authentication. Use `/api/v1/auth/register` to create
an account and `/api/v1/auth/login` to get an access token.
        """,
        version=settings.API_VERSION,
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API routers
    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)
    
    return app


# Create application instance
app = create_application()


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.API_VERSION,
        "description": "Universal Insurance AI Agent - RAG-based policy assistant",
        "docs": "/docs",
        "health": "/health",
        "api": settings.API_V1_PREFIX,
        "auth": f"{settings.API_V1_PREFIX}/auth",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "version": settings.API_VERSION,
        "database": "connected",
    }

"""
Application configuration settings.
"""

from typing import List, Optional
import secrets

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Project Info
    PROJECT_NAME: str = "Universal Insurance AI Agent"
    API_VERSION: str = "1.0.0"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    
    # CORS
    CORS_ORIGINS: List[str] = ["*"]
    
    # ==========================================================================
    # Authentication & Security
    # ==========================================================================
    SECRET_KEY: str = secrets.token_urlsafe(32)  # Generate random key if not set
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # ==========================================================================
    # Database
    # ==========================================================================
    DATABASE_URL: str = "sqlite:///./insur.db"  # Default to SQLite for development
    # For PostgreSQL: "postgresql://user:password@localhost:5432/insur"
    # For async PostgreSQL: "postgresql+asyncpg://user:password@localhost:5432/insur"
    
    DATABASE_ECHO: bool = False  # Log SQL queries (useful for debugging)
    
    # ==========================================================================
    # File Upload
    # ==========================================================================
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: List[str] = [".pdf", ".png", ".jpg", ".jpeg", ".tiff"]
    
    # Storage
    UPLOAD_DIR: str = "uploads"
    POLICIES_DIR: str = "data/policies"
    
    # ==========================================================================
    # OCR Settings
    # ==========================================================================
    OCR_LANGUAGE: str = "en"
    OCR_USE_GPU: bool = False
    OCR_DPI: int = 200
    
    # Mock mode for development
    USE_MOCK_OCR: bool = True  # Set to False for production with PaddleOCR
    
    # ==========================================================================
    # LLM Settings
    # ==========================================================================
    LLM_PROVIDER: str = "google"  # "mock", "openai", "anthropic", or "google"
    OPENAI_API_KEY: str = ""  # Set via environment variable
    ANTHROPIC_API_KEY: str = ""  # Set via environment variable
    GOOGLE_API_KEY: str = ""  # Set via environment variable (Gemini API)
    LLM_MODEL: str = "gemini-2.5-flash"  # Leave empty to use provider defaults
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 1024
    
    # ==========================================================================
    # RAG Settings
    # ==========================================================================
    RAG_CHUNK_SIZE: int = 512  # Characters per chunk
    RAG_CHUNK_OVERLAP: int = 50  # Overlap between chunks
    RAG_TOP_K: int = 5  # Number of results to retrieve
    RAG_MIN_SCORE: float = 0.3  # Minimum similarity score
    RAG_USE_RERANKING: bool = True  # Enable reranking
    RAG_USE_HYBRID_SEARCH: bool = True  # Enable hybrid (keyword + semantic) search
    RAG_KEYWORD_WEIGHT: float = 0.3  # Weight for keyword search in hybrid mode
    
    # ==========================================================================
    # Vector Store Settings
    # ==========================================================================
    VECTOR_STORE_TYPE: str = "memory"  # "memory" (dev) or "pgvector" (production)
    # For pgvector, uses DATABASE_URL
    
    # ==========================================================================
    # Embedding Settings
    # ==========================================================================
    # Options: "gemini" (recommended), "bge", "openai", "sentence_transformer"
    EMBEDDING_PROVIDER: str = "gemini"  # Uses same GOOGLE_API_KEY
    EMBEDDING_MODEL: str = "models/text-embedding-004"  # Gemini embedding model
    EMBEDDING_DIM: int = 768  # 768 for Gemini, 1024 for BGE, 1536 for OpenAI, 384 for MiniLM
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()

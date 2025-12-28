"""
API Dependencies for dependency injection.
"""

from typing import Generator, Optional
from functools import lru_cache

from app.core.config import settings
from app.services.policy_engine import PolicyEngine
from app.services.pdf_ingestion import PDFIngestionPipeline
from app.services.ocr_engine import MockOCREngine, OCREngine


# In-memory policy store (replace with database in production)
_policy_store: dict[str, PolicyEngine] = {}


def get_policy_store() -> dict[str, PolicyEngine]:
    """Get the in-memory policy store."""
    return _policy_store


@lru_cache()
def get_ingestion_pipeline() -> PDFIngestionPipeline:
    """
    Get the PDF ingestion pipeline.
    
    Uses caching for singleton pattern.
    """
    if settings.USE_MOCK_OCR:
        return PDFIngestionPipeline(use_mock=True)
    else:
        ocr_engine = OCREngine(
            use_gpu=settings.OCR_USE_GPU,
            lang=settings.OCR_LANGUAGE,
        )
        return PDFIngestionPipeline(ocr_engine=ocr_engine)


def get_policy_engine(policy_id: str) -> Optional[PolicyEngine]:
    """
    Get a PolicyEngine instance for a specific policy.
    
    Args:
        policy_id: The policy ID to retrieve
        
    Returns:
        PolicyEngine if found, None otherwise
    """
    return _policy_store.get(policy_id)


def store_policy(policy_id: str, engine: PolicyEngine) -> None:
    """
    Store a PolicyEngine instance.
    
    Args:
        policy_id: The policy ID
        engine: The PolicyEngine instance to store
    """
    _policy_store[policy_id] = engine


def get_default_policy_engine() -> PolicyEngine:
    """
    Get a default PolicyEngine with mock data.
    
    Useful for testing and demonstration.
    """
    if "default" not in _policy_store:
        _policy_store["default"] = PolicyEngine()
    return _policy_store["default"]


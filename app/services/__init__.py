"""
Services module for Universal Insurance AI Agent.
"""

from .policy_engine import PolicyEngine
from .ocr_engine import OCREngine, MockOCREngine, TextBlock, DocumentOCRResult
from .text_classifier import TextClassifier, TextCategory, ClassificationResult
from .pdf_ingestion import PDFIngestionPipeline, IngestionResult, ingest_policy_pdf
from .agent_service import AgentService, AgentCreate, AgentInfo, get_agent_service

__all__ = [
    # Policy Engine
    "PolicyEngine",
    # OCR
    "OCREngine",
    "MockOCREngine",
    "TextBlock",
    "DocumentOCRResult",
    # Classification
    "TextClassifier",
    "TextCategory",
    "ClassificationResult",
    # PDF Ingestion
    "PDFIngestionPipeline",
    "IngestionResult",
    "ingest_policy_pdf",
    # Agent Service
    "AgentService",
    "AgentCreate",
    "AgentInfo",
    "get_agent_service",
]


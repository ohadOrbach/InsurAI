"""
Policy Management API Endpoints.

Handles:
- Policy ingestion (PDF upload and text)
- Policy listing and retrieval
- Policy deletion
"""

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.api.deps import (
    get_default_policy_engine,
    get_ingestion_pipeline,
    get_policy_engine,
    get_policy_store,
    store_policy,
)
from app.api.models import (
    ErrorResponse,
    FileUploadResponse,
    PolicyDetailResponse,
    PolicyIngestRequest,
    PolicyIngestResponse,
    PolicyListResponse,
    PolicySummary,
)
from app.core.config import settings
from app.services.policy_engine import PolicyEngine

router = APIRouter()


# =============================================================================
# Policy Ingestion Endpoints
# =============================================================================


@router.post(
    "/ingest/text",
    response_model=PolicyIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest policy from raw text",
    description="""
Ingest a policy document from raw text content.

This endpoint skips OCR and directly processes the text through
the semantic classification pipeline.

Useful for:
- Testing without PDF files
- Pre-extracted text content
- Integration with other OCR systems
    """,
)
async def ingest_policy_text(request: PolicyIngestRequest):
    """Ingest a policy from raw text content."""
    pipeline = get_ingestion_pipeline()
    
    # Process the text
    result = pipeline.ingest_text(request.raw_text)
    
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Ingestion failed: {'; '.join(result.errors)}",
        )
    
    # Generate or use provided policy ID
    policy_id = request.policy_id or result.policy_document.policy_meta.policy_id
    
    # Create engine and store
    engine = PolicyEngine(policy=result.policy_document)
    store_policy(policy_id, engine)
    
    # Build summary
    summary = engine.get_policy_summary()
    
    return PolicyIngestResponse(
        message="Policy ingested successfully",
        policy_id=policy_id,
        policy_summary=PolicySummary(**summary),
        processing_time_ms=result.processing_time_ms,
        warnings=result.warnings,
    )


@router.post(
    "/ingest/pdf",
    response_model=PolicyIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest policy from PDF file",
    description="""
Upload and ingest a PDF policy document.

The PDF will be processed through:
1. OCR extraction (PaddleOCR)
2. Semantic classification
3. Schema transformation

Note: In development mode, mock OCR is used.
    """,
)
async def ingest_policy_pdf(
    file: UploadFile = File(..., description="PDF file to ingest"),
    policy_id: Optional[str] = None,
):
    """Ingest a policy from PDF upload."""
    # Validate file type
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided",
        )
    
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {settings.ALLOWED_EXTENSIONS}",
        )
    
    # Create upload directory if needed
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Save uploaded file
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = upload_dir / unique_filename
    
    try:
        contents = await file.read()
        
        # Check file size
        if len(contents) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Max size: {settings.MAX_UPLOAD_SIZE_MB}MB",
            )
        
        with open(file_path, "wb") as f:
            f.write(contents)
        
        # Process with pipeline
        pipeline = get_ingestion_pipeline()
        result = pipeline.ingest_pdf(str(file_path), dpi=settings.OCR_DPI)
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Ingestion failed: {'; '.join(result.errors)}",
            )
        
        # Generate or use provided policy ID
        final_policy_id = policy_id or result.policy_document.policy_meta.policy_id
        
        # Create engine and store
        engine = PolicyEngine(policy=result.policy_document)
        store_policy(final_policy_id, engine)
        
        # Build summary
        summary = engine.get_policy_summary()
        
        return PolicyIngestResponse(
            message="PDF policy ingested successfully",
            policy_id=final_policy_id,
            policy_summary=PolicySummary(**summary),
            processing_time_ms=result.processing_time_ms,
            warnings=result.warnings,
        )
    
    finally:
        # Clean up uploaded file
        if file_path.exists():
            os.remove(file_path)


# =============================================================================
# Policy Retrieval Endpoints
# =============================================================================


@router.get(
    "",
    response_model=PolicyListResponse,
    summary="List all policies",
    description="Get a list of all ingested policies with their summaries.",
)
async def list_policies():
    """List all available policies."""
    store = get_policy_store()
    
    policies = []
    for policy_id, engine in store.items():
        summary = engine.get_policy_summary()
        policies.append(PolicySummary(**summary))
    
    return PolicyListResponse(
        policies=policies,
        total=len(policies),
    )


@router.get(
    "/{policy_id}",
    response_model=PolicyDetailResponse,
    summary="Get policy details",
    description="Get detailed information about a specific policy.",
)
async def get_policy(policy_id: str):
    """Get details for a specific policy."""
    engine = get_policy_engine(policy_id)
    
    if not engine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy not found: {policy_id}",
        )
    
    summary = engine.get_policy_summary()
    inclusions = dict(engine.get_all_inclusions())
    exclusions = dict(engine.get_all_exclusions())
    
    # Group by category
    inclusions_by_category: dict[str, list[str]] = {}
    for item, category in engine.get_all_inclusions():
        if category not in inclusions_by_category:
            inclusions_by_category[category] = []
        inclusions_by_category[category].append(item)
    
    exclusions_by_category: dict[str, list[str]] = {}
    for item, category in engine.get_all_exclusions():
        if category not in exclusions_by_category:
            exclusions_by_category[category] = []
        exclusions_by_category[category].append(item)
    
    return PolicyDetailResponse(
        policy=PolicySummary(**summary),
        inclusions=inclusions_by_category,
        exclusions=exclusions_by_category,
    )


@router.delete(
    "/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a policy",
    description="Remove a policy from the system.",
)
async def delete_policy(policy_id: str):
    """Delete a policy."""
    store = get_policy_store()
    
    if policy_id not in store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy not found: {policy_id}",
        )
    
    del store[policy_id]
    return None


# =============================================================================
# Default/Demo Policy
# =============================================================================


@router.post(
    "/demo",
    response_model=PolicyIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Load demo policy",
    description="""
Load a demonstration policy with mock data.

This creates a sample Mechanical Warranty policy with:
- Engine, Transmission, Electrical, Cooling, Roadside coverage
- Sample inclusions and exclusions
- Financial terms (deductibles and caps)

Useful for testing and demonstration purposes.
    """,
)
async def load_demo_policy():
    """Load the demo policy with mock data."""
    engine = get_default_policy_engine()
    policy_id = "demo-policy"
    store_policy(policy_id, engine)
    
    summary = engine.get_policy_summary()
    
    return PolicyIngestResponse(
        message="Demo policy loaded successfully",
        policy_id=policy_id,
        policy_summary=PolicySummary(**summary),
        processing_time_ms=0.0,
    )


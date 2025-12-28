"""
API Request and Response Models.

These models define the API contract for the Universal Insurance AI Agent.
"""

from datetime import datetime
from typing import Optional, Union

from pydantic import BaseModel, Field

from app.schema import CoverageStatus, PolicyStatus


# =============================================================================
# Generic Response Models
# =============================================================================


class APIResponse(BaseModel):
    """Base API response wrapper."""
    
    success: bool = True
    message: str = "OK"
    timestamp: datetime = Field(default_factory=datetime.now)


class ErrorResponse(BaseModel):
    """Error response model."""
    
    success: bool = False
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


# =============================================================================
# Policy Models
# =============================================================================


class PolicySummary(BaseModel):
    """Summary information about a policy."""
    
    policy_id: str
    provider: str
    type: str  # Policy type (e.g., "Mechanical Warranty")
    status: str
    valid_until: str
    coverage_categories: list[str]
    total_inclusions: int
    total_exclusions: int


class PolicyListResponse(APIResponse):
    """Response containing list of policies."""
    
    policies: list[PolicySummary] = []
    total: int = 0


class PolicyDetailResponse(APIResponse):
    """Response containing detailed policy information."""
    
    policy: PolicySummary
    inclusions: dict[str, list[str]] = {}
    exclusions: dict[str, list[str]] = {}


class PolicyIngestRequest(BaseModel):
    """Request model for text-based policy ingestion."""
    
    raw_text: str = Field(
        ...,
        description="Raw text content of the policy document",
        min_length=10,
    )
    policy_id: Optional[str] = Field(
        None,
        description="Optional custom policy ID. Auto-generated if not provided.",
    )


class PolicyIngestResponse(APIResponse):
    """Response after policy ingestion."""
    
    policy_id: str
    policy_summary: PolicySummary
    processing_time_ms: float
    warnings: list[str] = []


# =============================================================================
# Coverage Models
# =============================================================================


class CoverageCheckRequest(BaseModel):
    """Request to check coverage for an item."""
    
    item_name: str = Field(
        ...,
        description="The item or service to check coverage for",
        min_length=1,
        max_length=200,
        examples=["Pistons", "Turbo", "Jumpstart"],
    )


class FinancialContext(BaseModel):
    """Financial context for a coverage check."""
    
    deductible: float = Field(description="Co-pay amount in NIS")
    coverage_cap: Optional[Union[float, str]] = Field(
        None,
        description="Maximum coverage amount or 'Unlimited'",
    )


class CoverageCheckResponse(APIResponse):
    """Response for a coverage check query."""
    
    item_name: str
    status: CoverageStatus
    category: Optional[str] = None
    reason: str
    financial_context: Optional[FinancialContext] = None
    conditions: Optional[list[str]] = None
    source_reference: Optional[str] = None


class BulkCoverageCheckRequest(BaseModel):
    """Request to check coverage for multiple items."""
    
    items: list[str] = Field(
        ...,
        description="List of items to check",
        min_length=1,
        max_length=50,
    )


class BulkCoverageCheckResponse(APIResponse):
    """Response for bulk coverage check."""
    
    results: list[CoverageCheckResponse]
    total_checked: int
    covered_count: int
    not_covered_count: int
    unknown_count: int


# =============================================================================
# File Upload Models
# =============================================================================


class FileUploadResponse(APIResponse):
    """Response after file upload."""
    
    filename: str
    file_size_bytes: int
    content_type: str
    policy_id: Optional[str] = None


# =============================================================================
# Health Models
# =============================================================================


class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str = "healthy"
    version: str
    uptime_seconds: Optional[float] = None
    services: dict[str, str] = {}


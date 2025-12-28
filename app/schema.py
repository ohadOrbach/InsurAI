"""
Pydantic schemas for Universal Insurance AI Agent.

Implements the target JSON structure defined in PRD Section 4.2.
These models represent the structured output from the Policy Ingestion Engine.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class PolicyStatus(str, Enum):
    """Status of an insurance policy."""

    ACTIVE = "Active"
    SUSPENDED = "Suspended"
    EXPIRED = "Expired"


class PaymentFrequency(str, Enum):
    """Frequency of premium payments."""

    MONTHLY = "Monthly"
    ANNUAL = "Annual"


class NetworkType(str, Enum):
    """Type of service provider network."""

    CLOSED = "Closed"  # Specific approved list only
    OPEN = "Open"  # Any provider allowed
    HYBRID = "Hybrid"  # Mix of both


# =============================================================================
# Nested Models - Policy Meta
# =============================================================================


class ValidityPeriod(BaseModel):
    """Validity period for a policy."""

    start_date: datetime = Field(
        ..., description="Policy start date in ISO8601 format"
    )
    end_date_calculated: datetime = Field(
        ..., description="Calculated end date in ISO8601 format"
    )
    termination_condition: Optional[str] = Field(
        None,
        description="Condition for early termination",
        examples=["Earlier of 24 months or 40k km"],
    )


class PolicyMeta(BaseModel):
    """Metadata about the insurance policy."""

    policy_id: str = Field(..., description="Unique policy identifier")
    provider_name: str = Field(..., description="Insurance provider name")
    policy_type: str = Field(
        ...,
        description="Type of policy",
        examples=["Mechanical Warranty", "Health HMO", "Home Insurance"],
    )
    status: PolicyStatus = Field(..., description="Current policy status")
    validity_period: ValidityPeriod = Field(
        ..., description="Policy validity period details"
    )


# =============================================================================
# Nested Models - Client Obligations
# =============================================================================


class MandatoryAction(BaseModel):
    """A mandatory action the client must perform to keep the policy valid."""

    action: str = Field(..., description="The required action")
    condition: str = Field(..., description="Conditions for the action")
    grace_period: Optional[str] = Field(
        None,
        description="Allowed grace period for the action",
        examples=["Up to 1,500km overdue allowed"],
    )
    penalty_for_breach: Optional[str] = Field(
        None,
        description="Penalty if action not performed",
        examples=["Void warranty immediately"],
    )


class PaymentTerms(BaseModel):
    """Payment terms for the policy."""

    amount: float = Field(..., ge=0, description="Payment amount")
    frequency: PaymentFrequency = Field(..., description="Payment frequency")
    method: Optional[str] = Field(
        None,
        description="Payment method",
        examples=["Credit Card Standing Order", "Bank Transfer"],
    )


class ClientObligations(BaseModel):
    """Conditions the client MUST fulfill for the policy to remain valid."""

    description: str = Field(
        default="Conditions the client MUST fulfill for the policy to remain valid.",
        description="Description of client obligations section",
    )
    mandatory_actions: list[MandatoryAction] = Field(
        default_factory=list, description="List of mandatory actions"
    )
    payment_terms: Optional[PaymentTerms] = Field(
        None, description="Payment terms for the policy"
    )
    restrictions: list[str] = Field(
        default_factory=list,
        description="List of restrictions",
        examples=[["Do not install LPG systems", "Do not go to unauthorized providers"]],
    )


# =============================================================================
# Nested Models - Coverage Details
# =============================================================================


class FinancialTerms(BaseModel):
    """Financial terms for a coverage category."""

    deductible: float = Field(
        default=0, ge=0, description="Co-pay amount for this category"
    )
    coverage_cap: Optional[Union[float, str]] = Field(
        None,
        description="Maximum coverage amount or 'Unlimited'",
        examples=["Unlimited", 5000.0],
    )


class CoverageCategory(BaseModel):
    """A category of coverage in the policy."""

    category: str = Field(
        ...,
        description="Coverage category name",
        examples=["Engine", "Dental", "Plumbing", "Roadside Assistance"],
    )
    items_included: list[str] = Field(
        default_factory=list,
        description="List of items/services included in this category",
    )
    items_excluded: list[str] = Field(
        default_factory=list,
        description="List of items/services explicitly excluded from this category",
    )
    specific_limitations: Optional[str] = Field(
        None,
        description="Specific limitations for this category",
        examples=["Excludes damage from overheating due to lack of fluids"],
    )
    financial_terms: FinancialTerms = Field(
        default_factory=FinancialTerms, description="Financial terms for this category"
    )
    usage_limits: Optional[dict[str, Union[int, str]]] = Field(
        None,
        description="Usage limits (e.g., treatments per year)",
        examples=[{"treatments_per_year": 2, "max_mileage": "40000km"}],
    )


# =============================================================================
# Nested Models - Service Network
# =============================================================================


class ApprovedSupplier(BaseModel):
    """An approved service provider in the network."""

    name: str = Field(..., description="Supplier name")
    service_type: str = Field(
        ...,
        description="Type of service provided",
        examples=["Tire Repair", "General Mechanics"],
    )
    contact_info: Optional[str] = Field(None, description="Contact information")


class ServiceNetwork(BaseModel):
    """Approved suppliers and providers network."""

    description: str = Field(
        default="Approved suppliers and providers.",
        description="Description of the service network",
    )
    network_type: NetworkType = Field(..., description="Type of provider network")
    approved_suppliers: list[ApprovedSupplier] = Field(
        default_factory=list, description="List of approved suppliers"
    )
    access_method: Optional[str] = Field(
        None,
        description="How to access the network",
        examples=["Must book via App", "Call *9406"],
    )


# =============================================================================
# Root Model - Policy Document
# =============================================================================


class PolicyDocument(BaseModel):
    """
    Complete structured representation of an insurance policy document.

    This is the target output schema for the Policy Ingestion Engine (ETL).
    It transforms unstructured PDF documents into this queryable structure.
    """

    policy_meta: PolicyMeta = Field(..., description="Policy metadata")
    client_obligations: ClientObligations = Field(
        default_factory=ClientObligations, description="Client obligations"
    )
    coverage_details: list[CoverageCategory] = Field(
        default_factory=list, description="List of coverage categories"
    )
    service_network: Optional[ServiceNetwork] = Field(
        None, description="Service provider network information"
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "policy_meta": {
                    "policy_id": "POL-2024-001234",
                    "provider_name": "Universal Insurance Co.",
                    "policy_type": "Mechanical Warranty",
                    "status": "Active",
                    "validity_period": {
                        "start_date": "2024-01-01T00:00:00Z",
                        "end_date_calculated": "2026-01-01T00:00:00Z",
                        "termination_condition": "Earlier of 24 months or 40,000 km",
                    },
                },
                "client_obligations": {
                    "description": "Conditions the client MUST fulfill for the policy to remain valid.",
                    "mandatory_actions": [
                        {
                            "action": "Routine Maintenance",
                            "condition": "According to manufacturer schedule",
                            "grace_period": "Up to 1,500km overdue allowed",
                            "penalty_for_breach": "Void warranty immediately",
                        }
                    ],
                    "payment_terms": {
                        "amount": 150.0,
                        "frequency": "Monthly",
                        "method": "Credit Card Standing Order",
                    },
                    "restrictions": [
                        "Do not install LPG systems",
                        "Do not go to unauthorized providers",
                    ],
                },
                "coverage_details": [
                    {
                        "category": "Engine",
                        "items_included": ["Pistons", "Cylinder Head", "Crankshaft"],
                        "items_excluded": ["Turbo", "Timing Belt"],
                        "specific_limitations": "Excludes damage from overheating due to lack of fluids",
                        "financial_terms": {"deductible": 400.0, "coverage_cap": 15000.0},
                    }
                ],
                "service_network": {
                    "description": "Approved suppliers and providers.",
                    "network_type": "Closed",
                    "approved_suppliers": [
                        {
                            "name": "Shlomo Service Centers",
                            "service_type": "General Mechanics",
                            "contact_info": "*9406",
                        }
                    ],
                    "access_method": "Call *9406",
                },
            }
        }


# =============================================================================
# Response Models - Coverage Check Results
# =============================================================================


class CoverageStatus(str, Enum):
    """Status of a coverage check."""

    COVERED = "covered"
    NOT_COVERED = "not_covered"
    CONDITIONAL = "conditional"
    UNKNOWN = "unknown"


class CoverageCheckResult(BaseModel):
    """Result of a coverage check for a specific item."""

    item_name: str = Field(..., description="The item that was checked")
    status: CoverageStatus = Field(..., description="Coverage status")
    category: Optional[str] = Field(
        None, description="Coverage category if found"
    )
    reason: str = Field(..., description="Explanation of the coverage decision")
    financial_context: Optional[dict[str, Union[float, str]]] = Field(
        None,
        description="Financial details if covered",
        examples=[{"deductible": 400.0, "coverage_cap": "Unlimited"}],
    )
    conditions: Optional[list[str]] = Field(
        None, description="Conditions that must be met for coverage"
    )
    source_reference: Optional[str] = Field(
        None, description="Reference to the policy section"
    )


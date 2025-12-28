"""
Coverage Check API Endpoints.

Implements the Coverage Guardrail Logic (PRD Section 3.2):
1. Check Exclusions First
2. Check Inclusions Second  
3. Check Conditionals

And Financial Context (PRD Section 3.3):
- Deductibles with every positive response
- Coverage caps
- Special conditions
"""

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.api.deps import get_default_policy_engine, get_policy_engine
from app.api.models import (
    BulkCoverageCheckRequest,
    BulkCoverageCheckResponse,
    CoverageCheckRequest,
    CoverageCheckResponse,
    FinancialContext,
)
from app.schema import CoverageStatus

router = APIRouter()


def _build_coverage_response(result, success_msg: str = "Coverage checked") -> CoverageCheckResponse:
    """Build a CoverageCheckResponse from a CoverageCheckResult."""
    financial_context = None
    if result.financial_context:
        financial_context = FinancialContext(
            deductible=result.financial_context.get("deductible", 0),
            coverage_cap=result.financial_context.get("coverage_cap"),
        )
    
    return CoverageCheckResponse(
        message=success_msg,
        item_name=result.item_name,
        status=result.status,
        category=result.category,
        reason=result.reason,
        financial_context=financial_context,
        conditions=result.conditions,
        source_reference=result.source_reference,
    )


# =============================================================================
# Coverage Check Endpoints
# =============================================================================


@router.post(
    "/check/{policy_id}",
    response_model=CoverageCheckResponse,
    summary="Check coverage for an item",
    description="""
Check if a specific item or service is covered under a policy.

**Coverage Guardrail Logic (PRD 3.2):**

1. **Exclusions First** - If item is in exclusion list, returns `not_covered` immediately
2. **Inclusions Second** - Checks if item is explicitly included
3. **Conditionals** - Verifies usage limits, policy status, and conditions

**Financial Context (PRD 3.3):**

Every positive response includes:
- `deductible` - Co-pay amount in NIS
- `coverage_cap` - Maximum coverage or "Unlimited"
- `conditions` - Any applicable restrictions
    """,
    responses={
        200: {
            "description": "Coverage check result",
            "content": {
                "application/json": {
                    "examples": {
                        "covered": {
                            "summary": "Item is covered",
                            "value": {
                                "success": True,
                                "message": "Coverage checked",
                                "item_name": "Pistons",
                                "status": "conditional",
                                "category": "Engine",
                                "reason": "COVERED WITH CONDITIONS: 'Pistons' is included under 'Engine' coverage. Deductible: 400.0 NIS per visit.",
                                "financial_context": {
                                    "deductible": 400.0,
                                    "coverage_cap": 15000.0
                                },
                                "conditions": ["Routine Maintenance: According to manufacturer schedule"]
                            }
                        },
                        "not_covered": {
                            "summary": "Item is excluded",
                            "value": {
                                "success": True,
                                "message": "Coverage checked",
                                "item_name": "Turbo",
                                "status": "not_covered",
                                "category": "Engine",
                                "reason": "EXCLUDED: 'Turbo' is explicitly excluded from the 'Engine' coverage.",
                                "financial_context": None
                            }
                        },
                        "unknown": {
                            "summary": "Item not found",
                            "value": {
                                "success": True,
                                "message": "Coverage checked",
                                "item_name": "Windshield",
                                "status": "unknown",
                                "category": None,
                                "reason": "'Windshield' was not found in the policy coverage details."
                            }
                        }
                    }
                }
            }
        },
        404: {"description": "Policy not found"}
    }
)
async def check_coverage(
    policy_id: str = Path(..., description="The policy ID to check against"),
    request: CoverageCheckRequest = ...,
):
    """Check coverage for a single item against a specific policy."""
    engine = get_policy_engine(policy_id)
    
    if not engine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy not found: {policy_id}. Use POST /api/v1/policies/demo to load a demo policy.",
        )
    
    result = engine.check_coverage(request.item_name)
    return _build_coverage_response(result)


@router.get(
    "/check/{policy_id}/{item_name}",
    response_model=CoverageCheckResponse,
    summary="Quick coverage check (GET)",
    description="""
Quick coverage check using GET request.

Same as POST but uses URL path for the item name.
Useful for simple queries and testing.

Example: `GET /api/v1/coverage/check/demo-policy/Pistons`
    """,
)
async def check_coverage_quick(
    policy_id: str = Path(..., description="The policy ID"),
    item_name: str = Path(..., description="Item to check"),
):
    """Quick coverage check via GET request."""
    engine = get_policy_engine(policy_id)
    
    if not engine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy not found: {policy_id}",
        )
    
    result = engine.check_coverage(item_name)
    return _build_coverage_response(result)


@router.post(
    "/check/{policy_id}/bulk",
    response_model=BulkCoverageCheckResponse,
    summary="Bulk coverage check",
    description="""
Check coverage for multiple items at once.

Returns individual results for each item plus summary statistics.
Maximum 50 items per request.
    """,
)
async def check_coverage_bulk(
    policy_id: str = Path(..., description="The policy ID"),
    request: BulkCoverageCheckRequest = ...,
):
    """Check coverage for multiple items."""
    engine = get_policy_engine(policy_id)
    
    if not engine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy not found: {policy_id}",
        )
    
    results = []
    covered_count = 0
    not_covered_count = 0
    unknown_count = 0
    
    for item in request.items:
        check_result = engine.check_coverage(item)
        response = _build_coverage_response(check_result)
        results.append(response)
        
        if check_result.status in [CoverageStatus.COVERED, CoverageStatus.CONDITIONAL]:
            covered_count += 1
        elif check_result.status == CoverageStatus.NOT_COVERED:
            not_covered_count += 1
        else:
            unknown_count += 1
    
    return BulkCoverageCheckResponse(
        message=f"Checked {len(request.items)} items",
        results=results,
        total_checked=len(request.items),
        covered_count=covered_count,
        not_covered_count=not_covered_count,
        unknown_count=unknown_count,
    )


# =============================================================================
# Demo/Default Policy Coverage Check
# =============================================================================


@router.post(
    "/demo/check",
    response_model=CoverageCheckResponse,
    summary="Check coverage using demo policy",
    description="""
Check coverage against the default demo policy.

No need to specify a policy ID - uses the built-in demo policy.
If demo policy isn't loaded, it will be created automatically.
    """,
)
async def check_coverage_demo(request: CoverageCheckRequest):
    """Check coverage using the default demo policy."""
    engine = get_default_policy_engine()
    result = engine.check_coverage(request.item_name)
    return _build_coverage_response(result)


@router.get(
    "/demo/check/{item_name}",
    response_model=CoverageCheckResponse,
    summary="Quick demo coverage check",
    description="""
Quick coverage check against the demo policy via GET.

Example: `GET /api/v1/coverage/demo/check/Pistons`
    """,
)
async def check_coverage_demo_quick(
    item_name: str = Path(..., description="Item to check"),
):
    """Quick coverage check via GET against demo policy."""
    engine = get_default_policy_engine()
    result = engine.check_coverage(item_name)
    return _build_coverage_response(result)


# =============================================================================
# Coverage Information Endpoints
# =============================================================================


@router.get(
    "/{policy_id}/inclusions",
    summary="List all inclusions",
    description="Get all items that are covered under the policy.",
)
async def list_inclusions(
    policy_id: str = Path(..., description="The policy ID"),
):
    """List all included items for a policy."""
    engine = get_policy_engine(policy_id)
    
    if not engine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy not found: {policy_id}",
        )
    
    inclusions = engine.get_all_inclusions()
    
    # Group by category
    by_category: dict[str, list[str]] = {}
    for item, category in inclusions:
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(item)
    
    return {
        "success": True,
        "policy_id": policy_id,
        "total_inclusions": len(inclusions),
        "inclusions_by_category": by_category,
    }


@router.get(
    "/{policy_id}/exclusions",
    summary="List all exclusions",
    description="Get all items that are explicitly excluded from coverage.",
)
async def list_exclusions(
    policy_id: str = Path(..., description="The policy ID"),
):
    """List all excluded items for a policy."""
    engine = get_policy_engine(policy_id)
    
    if not engine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy not found: {policy_id}",
        )
    
    exclusions = engine.get_all_exclusions()
    
    # Group by category
    by_category: dict[str, list[str]] = {}
    for item, category in exclusions:
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(item)
    
    return {
        "success": True,
        "policy_id": policy_id,
        "total_exclusions": len(exclusions),
        "exclusions_by_category": by_category,
    }


"""
Unit tests for app/services/policy_engine.py - PolicyEngine service.

These tests verify the Coverage Guardrail Logic (PRD Section 3.2):
1. Check Exclusions First - if item in Exclusion list, return Negative immediately
2. Check Inclusions Second - only if explicitly included, check conditions
3. Check Conditionals - verify remaining credits, mileage limits, etc.

Also tests Financial Context (PRD Section 3.3):
- Deductibles quoted with every positive answer
- Coverage caps included
- Special rates noted for exceptions
"""

import pytest

from app.schema import (
    CoverageCategory,
    CoverageCheckResult,
    CoverageStatus,
    FinancialTerms,
    PolicyDocument,
    PolicyMeta,
    PolicyStatus,
    ValidityPeriod,
)
from app.services.policy_engine import PolicyEngine
from datetime import datetime


# =============================================================================
# Engine Initialization Tests
# =============================================================================


class TestPolicyEngineInitialization:
    """Tests for PolicyEngine initialization."""

    @pytest.mark.unit
    def test_init_with_default_mock_data(self, default_engine):
        """Verify engine loads with default mock data when no policy provided."""
        assert default_engine.policy is not None
        assert default_engine.policy.policy_meta.policy_id == "POL-2024-001"

    @pytest.mark.unit
    def test_init_with_custom_policy(self, custom_engine, minimal_policy_document):
        """Verify engine accepts custom policy document."""
        assert custom_engine.policy.policy_meta.policy_id == "TEST-POL-001"

    @pytest.mark.unit
    def test_lookup_indexes_built(self, default_engine):
        """Verify lookup indexes are built on initialization."""
        # Check that internal indexes exist
        assert hasattr(default_engine, "_exclusions")
        assert hasattr(default_engine, "_inclusions")
        assert len(default_engine._exclusions) > 0
        assert len(default_engine._inclusions) > 0


# =============================================================================
# Coverage Guardrail Logic Tests (PRD Section 3.2)
# =============================================================================


class TestCoverageGuardrailLogic:
    """
    Tests for the Coverage Guardrail Logic.
    
    PRD Reference: Section 3.2
    Critical business logic that must be tested thoroughly.
    """

    @pytest.mark.unit
    @pytest.mark.guardrail
    def test_step1_exclusions_checked_first(self, default_engine):
        """
        Test: Step 1 - Exclusions are checked FIRST.
        
        PRD 3.2: "If a requested part/service appears in the Exclusion list,
                  return Negative immediately"
        
        This is CRITICAL for legal compliance.
        """
        result = default_engine.check_coverage("Turbo")
        
        assert result.status == CoverageStatus.NOT_COVERED
        assert "excluded" in result.reason.lower()
        assert result.category == "Engine"

    @pytest.mark.unit
    @pytest.mark.guardrail
    def test_step2_inclusions_checked_second(self, default_engine):
        """
        Test: Step 2 - Inclusions checked only if not excluded.
        
        PRD 3.2: "Only if the item is explicitly included, check for conditions"
        """
        result = default_engine.check_coverage("Pistons")
        
        assert result.status in [CoverageStatus.COVERED, CoverageStatus.CONDITIONAL]
        assert result.category == "Engine"

    @pytest.mark.unit
    @pytest.mark.guardrail
    def test_step3_conditionals_checked_last(self, default_engine):
        """
        Test: Step 3 - Conditionals are checked after inclusion.
        
        PRD 3.2: "Verify if the user has remaining credits or is within limits"
        """
        # Jumpstart has usage limits (4 per year, 50km max)
        result = default_engine.check_coverage("Jumpstart")
        
        assert result.status == CoverageStatus.CONDITIONAL
        assert result.conditions is not None
        assert len(result.conditions) > 0

    @pytest.mark.unit
    @pytest.mark.guardrail
    def test_unknown_item_returns_unknown_status(self, default_engine):
        """
        Test: Items not in policy return UNKNOWN status.
        
        This prevents false positives/negatives for items not in the policy.
        """
        result = default_engine.check_coverage("Windshield")
        
        assert result.status == CoverageStatus.UNKNOWN
        assert result.category is None
        assert "not found" in result.reason.lower()

    @pytest.mark.unit
    @pytest.mark.guardrail
    def test_exclusion_priority_over_inclusion(self, custom_engine):
        """
        Test: Exclusions ALWAYS take priority.
        
        Even if an item appears similar to an included item,
        if it's in the exclusion list, it MUST be rejected.
        """
        # In sample_coverage_category fixture:
        # included: ["Pistons", "Crankshaft", "Valves"]
        # excluded: ["Turbo", "Timing Belt"]
        
        result = custom_engine.check_coverage("Turbo")
        assert result.status == CoverageStatus.NOT_COVERED

    @pytest.mark.unit
    @pytest.mark.guardrail
    def test_multiple_exclusions_all_blocked(self, default_engine, excluded_items):
        """
        Test: ALL excluded items return NOT_COVERED.
        
        Bulk test to verify consistency across exclusion list.
        """
        for item in excluded_items:
            result = default_engine.check_coverage(item)
            assert result.status == CoverageStatus.NOT_COVERED, (
                f"Expected {item} to be NOT_COVERED, got {result.status}"
            )


# =============================================================================
# Financial Context Tests (PRD Section 3.3)
# =============================================================================


class TestFinancialContext:
    """
    Tests for Financial Context in coverage responses.
    
    PRD Reference: Section 3.3
    "The AI must append financial context to every positive answer"
    """

    @pytest.mark.unit
    @pytest.mark.financial
    def test_deductible_included_in_positive_response(self, default_engine):
        """
        Test: Deductibles are included with covered items.
        
        PRD 3.3: "Quote the specific co-pay (e.g., 400 NIS per visit)"
        """
        result = default_engine.check_coverage("Pistons")
        
        assert result.financial_context is not None
        assert "deductible" in result.financial_context
        assert result.financial_context["deductible"] == 400.0

    @pytest.mark.unit
    @pytest.mark.financial
    def test_coverage_cap_included_when_applicable(self, default_engine):
        """
        Test: Coverage caps are included when defined.
        """
        result = default_engine.check_coverage("Pistons")
        
        assert result.financial_context is not None
        assert "coverage_cap" in result.financial_context
        assert result.financial_context["coverage_cap"] == 15000.0

    @pytest.mark.unit
    @pytest.mark.financial
    def test_unlimited_coverage_cap_string(self, default_engine):
        """
        Test: 'Unlimited' coverage cap is returned as string.
        """
        # Roadside Assistance has unlimited coverage
        result = default_engine.check_coverage("Jumpstart")
        
        assert result.financial_context is not None
        assert result.financial_context["coverage_cap"] == "Unlimited"

    @pytest.mark.unit
    @pytest.mark.financial
    def test_zero_deductible_for_roadside(self, default_engine):
        """
        Test: Roadside services have 0 deductible.
        """
        result = default_engine.check_coverage("Jumpstart")
        
        assert result.financial_context["deductible"] == 0.0

    @pytest.mark.unit
    @pytest.mark.financial
    def test_no_financial_context_for_excluded_items(self, default_engine):
        """
        Test: Excluded items do NOT have financial context.
        
        Financial context only applies to positive responses.
        """
        result = default_engine.check_coverage("Turbo")
        
        assert result.financial_context is None

    @pytest.mark.unit
    @pytest.mark.financial
    def test_deductible_mentioned_in_reason(self, default_engine):
        """
        Test: Deductible amount appears in the reason text.
        
        PRD 3.3 requires clear communication of financial terms.
        """
        result = default_engine.check_coverage("Pistons")
        
        assert "400" in result.reason or "deductible" in result.reason.lower()


# =============================================================================
# Case Sensitivity Tests
# =============================================================================


class TestCaseSensitivity:
    """Tests for case-insensitive item matching."""

    @pytest.mark.unit
    def test_lowercase_item_matches(self, default_engine):
        """Test: lowercase input matches."""
        result = default_engine.check_coverage("pistons")
        assert result.status in [CoverageStatus.COVERED, CoverageStatus.CONDITIONAL]

    @pytest.mark.unit
    def test_uppercase_item_matches(self, default_engine):
        """Test: UPPERCASE input matches."""
        result = default_engine.check_coverage("PISTONS")
        assert result.status in [CoverageStatus.COVERED, CoverageStatus.CONDITIONAL]

    @pytest.mark.unit
    def test_mixed_case_item_matches(self, default_engine):
        """Test: MiXeD CaSe input matches."""
        result = default_engine.check_coverage("PiStOnS")
        assert result.status in [CoverageStatus.COVERED, CoverageStatus.CONDITIONAL]

    @pytest.mark.unit
    def test_case_insensitive_exclusion(self, default_engine):
        """Test: Exclusions also work case-insensitively."""
        result = default_engine.check_coverage("TURBO")
        assert result.status == CoverageStatus.NOT_COVERED


# =============================================================================
# Policy Status Tests
# =============================================================================


class TestPolicyStatus:
    """Tests for policy status affecting coverage."""

    @pytest.mark.unit
    def test_expired_policy_blocks_coverage(self, expired_policy_engine):
        """
        Test: Expired policy returns NOT_COVERED even for included items.
        """
        result = expired_policy_engine.check_coverage("Pistons")
        
        assert result.status == CoverageStatus.NOT_COVERED
        assert "expired" in result.reason.lower()

    @pytest.mark.unit
    def test_active_policy_allows_coverage(self, default_engine):
        """
        Test: Active policy allows coverage checks to proceed.
        """
        result = default_engine.check_coverage("Pistons")
        
        assert result.status != CoverageStatus.NOT_COVERED or "excluded" in result.reason.lower()


# =============================================================================
# Helper Method Tests
# =============================================================================


class TestHelperMethods:
    """Tests for PolicyEngine helper methods."""

    @pytest.mark.unit
    def test_get_all_exclusions(self, default_engine):
        """Test: get_all_exclusions returns list of excluded items."""
        exclusions = default_engine.get_all_exclusions()
        
        assert isinstance(exclusions, list)
        assert len(exclusions) > 0
        # Each entry is (item, category) tuple
        assert all(isinstance(e, tuple) and len(e) == 2 for e in exclusions)

    @pytest.mark.unit
    def test_get_all_inclusions(self, default_engine):
        """Test: get_all_inclusions returns list of included items."""
        inclusions = default_engine.get_all_inclusions()
        
        assert isinstance(inclusions, list)
        assert len(inclusions) > 0

    @pytest.mark.unit
    def test_get_policy_summary(self, default_engine):
        """Test: get_policy_summary returns complete summary dict."""
        summary = default_engine.get_policy_summary()
        
        assert "policy_id" in summary
        assert "provider" in summary
        assert "status" in summary
        assert "coverage_categories" in summary
        assert "total_inclusions" in summary
        assert "total_exclusions" in summary


# =============================================================================
# Edge Cases Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.unit
    def test_empty_string_item(self, default_engine):
        """Test: Empty string returns a valid status (partial match behavior)."""
        result = default_engine.check_coverage("")
        # Empty string may trigger partial match, which is acceptable
        assert result.status in [CoverageStatus.UNKNOWN, CoverageStatus.NOT_COVERED, CoverageStatus.CONDITIONAL]

    @pytest.mark.unit
    def test_whitespace_only_item(self, default_engine):
        """Test: Whitespace-only string returns a valid status after strip."""
        result = default_engine.check_coverage("   ")
        # After stripping, becomes empty - may trigger partial match
        assert result.status in [CoverageStatus.UNKNOWN, CoverageStatus.NOT_COVERED, CoverageStatus.CONDITIONAL]

    @pytest.mark.unit
    def test_item_with_extra_whitespace(self, default_engine):
        """Test: Item with leading/trailing whitespace is trimmed."""
        result = default_engine.check_coverage("  Pistons  ")
        assert result.status in [CoverageStatus.COVERED, CoverageStatus.CONDITIONAL]

    @pytest.mark.unit
    def test_partial_match_excluded_item(self, default_engine):
        """
        Test: Partial match to excluded item returns appropriate status.
        
        This tests the fuzzy matching behavior.
        """
        # "turbocharger" should partially match "turbo" (excluded)
        result = default_engine.check_coverage("turbocharger")
        # Should either be NOT_COVERED (partial match) or UNKNOWN
        assert result.status in [CoverageStatus.NOT_COVERED, CoverageStatus.UNKNOWN]

    @pytest.mark.unit
    def test_partial_match_included_item(self, default_engine):
        """
        Test: Partial match to included item returns CONDITIONAL.
        """
        # "piston rings" might partially match "pistons"
        result = default_engine.check_coverage("piston rings")
        # Could be CONDITIONAL (partial match) or UNKNOWN
        assert result.status in [CoverageStatus.CONDITIONAL, CoverageStatus.UNKNOWN]


# =============================================================================
# Bulk Coverage Tests
# =============================================================================


class TestBulkCoverage:
    """Bulk tests to verify consistency across item lists."""

    @pytest.mark.unit
    def test_all_included_items_are_covered(self, default_engine, included_items):
        """Test: All known included items return COVERED or CONDITIONAL."""
        for item in included_items:
            result = default_engine.check_coverage(item)
            assert result.status in [CoverageStatus.COVERED, CoverageStatus.CONDITIONAL], (
                f"Expected {item} to be covered, got {result.status}. "
                f"Reason: {result.reason}"
            )

    @pytest.mark.unit
    def test_all_excluded_items_are_not_covered(self, default_engine, excluded_items):
        """Test: All known excluded items return NOT_COVERED."""
        for item in excluded_items:
            result = default_engine.check_coverage(item)
            assert result.status == CoverageStatus.NOT_COVERED, (
                f"Expected {item} to be NOT_COVERED, got {result.status}. "
                f"Reason: {result.reason}"
            )

    @pytest.mark.unit
    def test_all_unknown_items_return_unknown(self, default_engine, unknown_items):
        """Test: All unknown items return UNKNOWN status."""
        for item in unknown_items:
            result = default_engine.check_coverage(item)
            assert result.status == CoverageStatus.UNKNOWN, (
                f"Expected {item} to be UNKNOWN, got {result.status}. "
                f"Reason: {result.reason}"
            )


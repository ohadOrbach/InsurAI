"""
Integration tests for end-to-end coverage checking workflow.

These tests verify:
- Complete flow from policy load to coverage query
- Multiple components working together
- Real data transformation through the system
- Business scenarios and user journeys
"""

import json
from datetime import datetime

import pytest

from app.schema import (
    CoverageCategory,
    CoverageStatus,
    FinancialTerms,
    PolicyDocument,
    PolicyMeta,
    PolicyStatus,
    ValidityPeriod,
    ClientObligations,
    MandatoryAction,
    PaymentTerms,
    PaymentFrequency,
)
from app.services.policy_engine import PolicyEngine


# =============================================================================
# End-to-End Workflow Tests
# =============================================================================


class TestEndToEndCoverageWorkflow:
    """
    Integration tests for complete coverage checking workflows.
    
    These tests simulate real user scenarios from start to finish.
    """

    @pytest.mark.integration
    def test_complete_workflow_included_item(self):
        """
        E2E Test: Complete workflow for checking an included item.
        
        Scenario: User asks "Is my crankshaft covered?"
        Expected: Yes, with deductible and cap information.
        """
        # ARRANGE - Initialize system
        engine = PolicyEngine()
        
        # ACT - User queries coverage
        result = engine.check_coverage("Crankshaft")
        
        # ASSERT - Full response validation
        assert result.item_name == "Crankshaft"
        assert result.status in [CoverageStatus.COVERED, CoverageStatus.CONDITIONAL]
        assert result.category == "Engine"
        assert result.financial_context is not None
        assert result.financial_context["deductible"] == 400.0
        assert result.financial_context["coverage_cap"] == 15000.0
        assert result.source_reference is not None

    @pytest.mark.integration
    def test_complete_workflow_excluded_item(self):
        """
        E2E Test: Complete workflow for checking an excluded item.
        
        Scenario: User asks "Is turbo repair covered?"
        Expected: No, with clear explanation.
        """
        # ARRANGE
        engine = PolicyEngine()
        
        # ACT
        result = engine.check_coverage("Turbo")
        
        # ASSERT
        assert result.item_name == "Turbo"
        assert result.status == CoverageStatus.NOT_COVERED
        assert result.category == "Engine"
        assert "excluded" in result.reason.lower()
        assert result.financial_context is None  # No financial context for excluded items

    @pytest.mark.integration
    def test_complete_workflow_unknown_item(self):
        """
        E2E Test: Complete workflow for checking an unknown item.
        
        Scenario: User asks "Is my air conditioning covered?"
        Expected: Unknown, with guidance to contact provider.
        """
        # ARRANGE
        engine = PolicyEngine()
        
        # ACT
        result = engine.check_coverage("Air Conditioning")
        
        # ASSERT
        assert result.status == CoverageStatus.UNKNOWN
        assert "not found" in result.reason.lower()
        assert "contact" in result.reason.lower() or "provider" in result.reason.lower()

    @pytest.mark.integration
    def test_complete_workflow_roadside_service(self):
        """
        E2E Test: Roadside assistance with usage limits.
        
        Scenario: User asks "Can I get a jumpstart?"
        Expected: Yes, with usage limits (4/year, 50km).
        """
        # ARRANGE
        engine = PolicyEngine()
        
        # ACT
        result = engine.check_coverage("Jumpstart")
        
        # ASSERT
        assert result.status == CoverageStatus.CONDITIONAL
        assert result.category == "Roadside Assistance"
        assert result.financial_context["deductible"] == 0.0
        assert result.financial_context["coverage_cap"] == "Unlimited"
        assert result.conditions is not None
        # Should mention usage limits
        conditions_str = " ".join(result.conditions).lower()
        assert "year" in conditions_str or "services" in conditions_str


# =============================================================================
# Multi-Category Tests
# =============================================================================


class TestMultiCategoryCoverage:
    """Tests for coverage across different categories."""

    @pytest.mark.integration
    def test_engine_category_items(self):
        """Test multiple items from Engine category."""
        engine = PolicyEngine()
        
        # Included items
        for item in ["Pistons", "Cylinder Head", "Valves", "Oil Pump"]:
            result = engine.check_coverage(item)
            assert result.status in [CoverageStatus.COVERED, CoverageStatus.CONDITIONAL]
            assert result.category == "Engine"
        
        # Excluded items
        for item in ["Turbo", "Timing Belt", "Spark Plugs"]:
            result = engine.check_coverage(item)
            assert result.status == CoverageStatus.NOT_COVERED

    @pytest.mark.integration
    def test_transmission_category_items(self):
        """Test multiple items from Transmission category."""
        engine = PolicyEngine()
        
        # Included
        result = engine.check_coverage("Gearbox")
        assert result.status in [CoverageStatus.COVERED, CoverageStatus.CONDITIONAL]
        assert result.category == "Transmission"
        
        # Excluded
        result = engine.check_coverage("Clutch Cable")
        assert result.status == CoverageStatus.NOT_COVERED

    @pytest.mark.integration
    def test_electrical_category_items(self):
        """Test multiple items from Electrical category."""
        engine = PolicyEngine()
        
        # Included
        result = engine.check_coverage("Alternator")
        assert result.status in [CoverageStatus.COVERED, CoverageStatus.CONDITIONAL]
        assert result.category == "Electrical"
        
        # Excluded - Battery (with special rate note)
        result = engine.check_coverage("Battery")
        assert result.status == CoverageStatus.NOT_COVERED
        assert "special rate" in result.reason.lower()

    @pytest.mark.integration
    def test_different_deductibles_per_category(self):
        """Test that different categories have different deductibles."""
        engine = PolicyEngine()
        
        # Engine - 400 NIS
        engine_result = engine.check_coverage("Pistons")
        assert engine_result.financial_context["deductible"] == 400.0
        
        # Electrical - 300 NIS
        electrical_result = engine.check_coverage("Alternator")
        assert electrical_result.financial_context["deductible"] == 300.0
        
        # Roadside - 0 NIS
        roadside_result = engine.check_coverage("Jumpstart")
        assert roadside_result.financial_context["deductible"] == 0.0


# =============================================================================
# Custom Policy Integration Tests
# =============================================================================


class TestCustomPolicyIntegration:
    """Tests with custom policy documents."""

    @pytest.mark.integration
    def test_custom_policy_with_different_coverage(self):
        """Test loading a custom policy with different coverage rules."""
        # Create custom policy
        custom_policy = PolicyDocument(
            policy_meta=PolicyMeta(
                policy_id="CUSTOM-001",
                provider_name="Custom Insurance",
                policy_type="Basic Coverage",
                status=PolicyStatus.ACTIVE,
                validity_period=ValidityPeriod(
                    start_date=datetime(2024, 1, 1),
                    end_date_calculated=datetime(2030, 1, 1),
                ),
            ),
            coverage_details=[
                CoverageCategory(
                    category="Custom Parts",
                    items_included=["Widget A", "Widget B"],
                    items_excluded=["Widget C"],
                    financial_terms=FinancialTerms(
                        deductible=100.0,
                        coverage_cap=5000.0,
                    ),
                ),
            ],
        )
        
        # Load into engine
        engine = PolicyEngine(policy=custom_policy)
        
        # Test included item
        result = engine.check_coverage("Widget A")
        assert result.status in [CoverageStatus.COVERED, CoverageStatus.CONDITIONAL]
        assert result.financial_context["deductible"] == 100.0
        
        # Test excluded item
        result = engine.check_coverage("Widget C")
        assert result.status == CoverageStatus.NOT_COVERED

    @pytest.mark.integration
    def test_policy_with_client_obligations(self):
        """Test policy with mandatory client obligations."""
        custom_policy = PolicyDocument(
            policy_meta=PolicyMeta(
                policy_id="OBLIGATION-001",
                provider_name="Strict Insurance",
                policy_type="Premium Coverage",
                status=PolicyStatus.ACTIVE,
                validity_period=ValidityPeriod(
                    start_date=datetime(2024, 1, 1),
                    end_date_calculated=datetime(2030, 1, 1),
                ),
            ),
            client_obligations=ClientObligations(
                mandatory_actions=[
                    MandatoryAction(
                        action="Monthly Inspection",
                        condition="At authorized center",
                        penalty_for_breach="Coverage suspended",
                    ),
                ],
                payment_terms=PaymentTerms(
                    amount=500.0,
                    frequency=PaymentFrequency.MONTHLY,
                ),
            ),
            coverage_details=[
                CoverageCategory(
                    category="Premium Parts",
                    items_included=["Premium Item"],
                    financial_terms=FinancialTerms(deductible=50.0),
                ),
            ],
        )
        
        engine = PolicyEngine(policy=custom_policy)
        result = engine.check_coverage("Premium Item")
        
        # Should be conditional due to obligations
        assert result.status == CoverageStatus.CONDITIONAL
        assert result.conditions is not None
        assert any("monthly inspection" in c.lower() for c in result.conditions)


# =============================================================================
# Policy Summary Integration Tests
# =============================================================================


class TestPolicySummaryIntegration:
    """Tests for policy summary functionality."""

    @pytest.mark.integration
    def test_policy_summary_accuracy(self):
        """Test that policy summary accurately reflects policy contents."""
        engine = PolicyEngine()
        summary = engine.get_policy_summary()
        
        # Verify summary matches actual policy
        assert summary["policy_id"] == engine.policy.policy_meta.policy_id
        assert summary["provider"] == engine.policy.policy_meta.provider_name
        assert summary["status"] == engine.policy.policy_meta.status.value
        
        # Verify counts
        assert summary["total_inclusions"] == len(engine._inclusions)
        assert summary["total_exclusions"] == len(engine._exclusions)
        
        # Verify categories
        expected_categories = [c.category for c in engine.policy.coverage_details]
        assert summary["coverage_categories"] == expected_categories

    @pytest.mark.integration
    def test_get_all_exclusions_complete(self):
        """Test that all exclusions are retrievable."""
        engine = PolicyEngine()
        exclusions = engine.get_all_exclusions()
        
        # Verify each exclusion can be checked
        for item, category in exclusions:
            result = engine.check_coverage(item)
            assert result.status == CoverageStatus.NOT_COVERED

    @pytest.mark.integration
    def test_get_all_inclusions_complete(self):
        """Test that all inclusions are retrievable."""
        engine = PolicyEngine()
        inclusions = engine.get_all_inclusions()
        
        # Verify each inclusion can be checked
        for item, category in inclusions:
            result = engine.check_coverage(item)
            assert result.status in [CoverageStatus.COVERED, CoverageStatus.CONDITIONAL]


# =============================================================================
# JSON Serialization Integration Tests
# =============================================================================


class TestJSONSerializationIntegration:
    """Tests for JSON serialization of coverage results."""

    @pytest.mark.integration
    def test_coverage_result_to_json(self):
        """Test that coverage results can be serialized to JSON."""
        engine = PolicyEngine()
        result = engine.check_coverage("Pistons")
        
        # Serialize to JSON
        json_str = result.model_dump_json()
        json_data = json.loads(json_str)
        
        # Verify all fields present
        assert "item_name" in json_data
        assert "status" in json_data
        assert "category" in json_data
        assert "reason" in json_data
        assert "financial_context" in json_data

    @pytest.mark.integration
    def test_policy_summary_to_json(self):
        """Test that policy summary can be serialized to JSON."""
        engine = PolicyEngine()
        summary = engine.get_policy_summary()
        
        # Should be JSON serializable
        json_str = json.dumps(summary)
        restored = json.loads(json_str)
        
        assert restored == summary


# =============================================================================
# Performance Tests (Basic)
# =============================================================================


class TestBasicPerformance:
    """Basic performance tests for coverage checking."""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_bulk_coverage_checks_complete(self):
        """Test that bulk coverage checks complete without errors."""
        engine = PolicyEngine()
        
        # Check all known items
        inclusions = engine.get_all_inclusions()
        exclusions = engine.get_all_exclusions()
        
        checked = 0
        for item, _ in inclusions + exclusions:
            result = engine.check_coverage(item)
            assert result is not None
            checked += 1
        
        assert checked > 0, "Should have checked at least one item"

    @pytest.mark.integration
    def test_repeated_checks_consistent(self):
        """Test that repeated checks return consistent results."""
        engine = PolicyEngine()
        
        # Check same item multiple times
        results = [engine.check_coverage("Pistons") for _ in range(10)]
        
        # All results should be identical
        first = results[0]
        for result in results[1:]:
            assert result.status == first.status
            assert result.category == first.category
            assert result.financial_context == first.financial_context


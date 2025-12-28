"""
Unit tests for app/schema.py - Pydantic models.

These tests verify:
- Model creation with valid data
- Validation errors with invalid data
- Enum values and behavior
- Default values and optional fields
- JSON serialization/deserialization
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schema import (
    ApprovedSupplier,
    ClientObligations,
    CoverageCategory,
    CoverageCheckResult,
    CoverageStatus,
    FinancialTerms,
    MandatoryAction,
    NetworkType,
    PaymentFrequency,
    PaymentTerms,
    PolicyDocument,
    PolicyMeta,
    PolicyStatus,
    ServiceNetwork,
    ValidityPeriod,
)


# =============================================================================
# Enum Tests
# =============================================================================


class TestPolicyStatusEnum:
    """Tests for PolicyStatus enumeration."""

    @pytest.mark.unit
    def test_policy_status_active_value(self):
        """Verify ACTIVE status has correct string value."""
        assert PolicyStatus.ACTIVE.value == "Active"

    @pytest.mark.unit
    def test_policy_status_suspended_value(self):
        """Verify SUSPENDED status has correct string value."""
        assert PolicyStatus.SUSPENDED.value == "Suspended"

    @pytest.mark.unit
    def test_policy_status_expired_value(self):
        """Verify EXPIRED status has correct string value."""
        assert PolicyStatus.EXPIRED.value == "Expired"

    @pytest.mark.unit
    def test_policy_status_all_values(self):
        """Verify all expected status values exist."""
        expected = {"Active", "Suspended", "Expired"}
        actual = {status.value for status in PolicyStatus}
        assert actual == expected


class TestPaymentFrequencyEnum:
    """Tests for PaymentFrequency enumeration."""

    @pytest.mark.unit
    def test_payment_frequency_monthly(self):
        """Verify MONTHLY frequency value."""
        assert PaymentFrequency.MONTHLY.value == "Monthly"

    @pytest.mark.unit
    def test_payment_frequency_annual(self):
        """Verify ANNUAL frequency value."""
        assert PaymentFrequency.ANNUAL.value == "Annual"


class TestNetworkTypeEnum:
    """Tests for NetworkType enumeration."""

    @pytest.mark.unit
    def test_network_type_closed(self):
        """Verify CLOSED network type - specific approved list only."""
        assert NetworkType.CLOSED.value == "Closed"

    @pytest.mark.unit
    def test_network_type_open(self):
        """Verify OPEN network type - any provider allowed."""
        assert NetworkType.OPEN.value == "Open"

    @pytest.mark.unit
    def test_network_type_hybrid(self):
        """Verify HYBRID network type."""
        assert NetworkType.HYBRID.value == "Hybrid"


class TestCoverageStatusEnum:
    """Tests for CoverageStatus enumeration (response status)."""

    @pytest.mark.unit
    def test_coverage_status_values(self):
        """Verify all coverage status values."""
        assert CoverageStatus.COVERED.value == "covered"
        assert CoverageStatus.NOT_COVERED.value == "not_covered"
        assert CoverageStatus.CONDITIONAL.value == "conditional"
        assert CoverageStatus.UNKNOWN.value == "unknown"


# =============================================================================
# Model Creation Tests - Valid Data
# =============================================================================


class TestValidityPeriodModel:
    """Tests for ValidityPeriod model."""

    @pytest.mark.unit
    def test_create_validity_period_with_all_fields(self):
        """Create ValidityPeriod with all fields populated."""
        period = ValidityPeriod(
            start_date=datetime(2024, 1, 1),
            end_date_calculated=datetime(2026, 1, 1),
            termination_condition="24 months or 40k km",
        )
        assert period.start_date == datetime(2024, 1, 1)
        assert period.end_date_calculated == datetime(2026, 1, 1)
        assert period.termination_condition == "24 months or 40k km"

    @pytest.mark.unit
    def test_create_validity_period_without_termination_condition(self):
        """Create ValidityPeriod without optional termination_condition."""
        period = ValidityPeriod(
            start_date=datetime(2024, 1, 1),
            end_date_calculated=datetime(2025, 1, 1),
        )
        assert period.termination_condition is None


class TestFinancialTermsModel:
    """Tests for FinancialTerms model."""

    @pytest.mark.unit
    @pytest.mark.financial
    def test_create_financial_terms_with_numeric_cap(self):
        """Create FinancialTerms with numeric coverage cap."""
        terms = FinancialTerms(
            deductible=400.0,
            coverage_cap=15000.0,
        )
        assert terms.deductible == 400.0
        assert terms.coverage_cap == 15000.0

    @pytest.mark.unit
    @pytest.mark.financial
    def test_create_financial_terms_with_string_cap(self):
        """Create FinancialTerms with 'Unlimited' coverage cap."""
        terms = FinancialTerms(
            deductible=0.0,
            coverage_cap="Unlimited",
        )
        assert terms.deductible == 0.0
        assert terms.coverage_cap == "Unlimited"

    @pytest.mark.unit
    @pytest.mark.financial
    def test_financial_terms_default_values(self):
        """Verify default values for FinancialTerms."""
        terms = FinancialTerms()
        assert terms.deductible == 0.0
        assert terms.coverage_cap is None


class TestCoverageCategoryModel:
    """Tests for CoverageCategory model."""

    @pytest.mark.unit
    def test_create_coverage_category_full(self, sample_coverage_category):
        """Create CoverageCategory with all fields."""
        assert sample_coverage_category.category == "Engine"
        assert "Pistons" in sample_coverage_category.items_included
        assert "Turbo" in sample_coverage_category.items_excluded
        assert sample_coverage_category.financial_terms.deductible == 400.0

    @pytest.mark.unit
    def test_create_coverage_category_minimal(self):
        """Create CoverageCategory with minimal required fields."""
        category = CoverageCategory(category="Basic")
        assert category.category == "Basic"
        assert category.items_included == []
        assert category.items_excluded == []
        assert category.specific_limitations is None


class TestMandatoryActionModel:
    """Tests for MandatoryAction model."""

    @pytest.mark.unit
    def test_create_mandatory_action_full(self):
        """Create MandatoryAction with all fields."""
        action = MandatoryAction(
            action="Routine Maintenance",
            condition="Every 15,000km",
            grace_period="Up to 1,500km overdue",
            penalty_for_breach="Void warranty",
        )
        assert action.action == "Routine Maintenance"
        assert action.condition == "Every 15,000km"
        assert action.grace_period == "Up to 1,500km overdue"
        assert action.penalty_for_breach == "Void warranty"


class TestPolicyDocumentModel:
    """Tests for PolicyDocument root model."""

    @pytest.mark.unit
    def test_create_policy_document_minimal(self, minimal_policy_document):
        """Create PolicyDocument with minimal required fields."""
        assert minimal_policy_document.policy_meta.policy_id == "TEST-POL-001"
        assert len(minimal_policy_document.coverage_details) == 1

    @pytest.mark.unit
    def test_create_policy_document_full(self, full_policy_document):
        """Create PolicyDocument with all fields populated."""
        assert full_policy_document.policy_meta is not None
        assert full_policy_document.client_obligations is not None
        assert full_policy_document.coverage_details is not None
        assert full_policy_document.service_network is not None


# =============================================================================
# Model Validation Tests - Invalid Data
# =============================================================================


class TestValidationErrors:
    """Tests for validation error handling."""

    @pytest.mark.unit
    def test_policy_meta_missing_required_field(self):
        """Verify ValidationError when required field is missing."""
        with pytest.raises(ValidationError) as exc_info:
            PolicyMeta(
                policy_id="TEST-001",
                # Missing: provider_name, policy_type, status, validity_period
            )
        assert "provider_name" in str(exc_info.value) or "Field required" in str(exc_info.value)

    @pytest.mark.unit
    def test_financial_terms_negative_deductible(self):
        """Verify ValidationError for negative deductible."""
        with pytest.raises(ValidationError) as exc_info:
            FinancialTerms(deductible=-100.0)
        assert "greater than or equal to 0" in str(exc_info.value).lower()

    @pytest.mark.unit
    def test_invalid_policy_status(self):
        """Verify ValidationError for invalid status value."""
        with pytest.raises(ValidationError):
            PolicyMeta(
                policy_id="TEST-001",
                provider_name="Test",
                policy_type="Test",
                status="InvalidStatus",  # Not a valid enum value
                validity_period=ValidityPeriod(
                    start_date=datetime.now(),
                    end_date_calculated=datetime.now(),
                ),
            )


# =============================================================================
# Serialization Tests
# =============================================================================


class TestSerialization:
    """Tests for model serialization to JSON."""

    @pytest.mark.unit
    def test_coverage_category_to_json(self, sample_coverage_category):
        """Verify CoverageCategory serializes to JSON correctly."""
        json_data = sample_coverage_category.model_dump()
        
        assert json_data["category"] == "Engine"
        assert "Pistons" in json_data["items_included"]
        assert "Turbo" in json_data["items_excluded"]
        assert json_data["financial_terms"]["deductible"] == 400.0

    @pytest.mark.unit
    def test_policy_document_to_json(self, minimal_policy_document):
        """Verify PolicyDocument serializes to JSON correctly."""
        json_data = minimal_policy_document.model_dump()
        
        assert "policy_meta" in json_data
        assert "coverage_details" in json_data
        assert json_data["policy_meta"]["status"] == "Active"

    @pytest.mark.unit
    def test_policy_document_json_roundtrip(self, full_policy_document):
        """Verify PolicyDocument survives JSON serialization roundtrip."""
        # Serialize to JSON string
        json_str = full_policy_document.model_dump_json()
        
        # Deserialize back to model
        restored = PolicyDocument.model_validate_json(json_str)
        
        # Verify equality
        assert restored.policy_meta.policy_id == full_policy_document.policy_meta.policy_id
        assert len(restored.coverage_details) == len(full_policy_document.coverage_details)


# =============================================================================
# CoverageCheckResult Tests
# =============================================================================


class TestCoverageCheckResultModel:
    """Tests for CoverageCheckResult response model."""

    @pytest.mark.unit
    def test_create_covered_result(self):
        """Create a COVERED result with financial context."""
        result = CoverageCheckResult(
            item_name="Pistons",
            status=CoverageStatus.COVERED,
            category="Engine",
            reason="COVERED: Pistons is included under Engine coverage.",
            financial_context={"deductible": 400.0, "coverage_cap": 15000.0},
        )
        assert result.status == CoverageStatus.COVERED
        assert result.financial_context["deductible"] == 400.0

    @pytest.mark.unit
    def test_create_not_covered_result(self):
        """Create a NOT_COVERED result."""
        result = CoverageCheckResult(
            item_name="Turbo",
            status=CoverageStatus.NOT_COVERED,
            category="Engine",
            reason="EXCLUDED: Turbo is explicitly excluded.",
        )
        assert result.status == CoverageStatus.NOT_COVERED
        assert result.financial_context is None

    @pytest.mark.unit
    def test_create_conditional_result(self):
        """Create a CONDITIONAL result with conditions list."""
        result = CoverageCheckResult(
            item_name="Jumpstart",
            status=CoverageStatus.CONDITIONAL,
            category="Roadside Assistance",
            reason="COVERED WITH CONDITIONS",
            conditions=["Max 4 services per year", "Within 50km radius"],
        )
        assert result.status == CoverageStatus.CONDITIONAL
        assert len(result.conditions) == 2

    @pytest.mark.unit
    def test_create_unknown_result(self):
        """Create an UNKNOWN result."""
        result = CoverageCheckResult(
            item_name="Windshield",
            status=CoverageStatus.UNKNOWN,
            reason="Item not found in policy.",
        )
        assert result.status == CoverageStatus.UNKNOWN
        assert result.category is None


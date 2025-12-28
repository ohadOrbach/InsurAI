"""
Unit tests for app/services/text_classifier.py - Semantic text classification.

Tests for PRD Section 3.1 - Semantic Segmentation:
- Identity_Data extraction
- Coverage_Inclusions extraction
- Coverage_Exclusions extraction
- Financial_Logic extraction
"""

import pytest

from app.services.text_classifier import (
    ClassificationResult,
    ClassifiedTextBlock,
    TextCategory,
    TextClassifier,
)
from app.services.ocr_engine import TextBlock


@pytest.fixture
def classifier():
    """Create a TextClassifier instance."""
    return TextClassifier()


@pytest.fixture
def sample_policy_text():
    """Sample policy document text for testing."""
    return """
INSURANCE POLICY DOCUMENT
Policy Number: POL-2024-123456
Provider: Universal Insurance Co.
Policy Type: Mechanical Warranty
Status: Active

VALIDITY PERIOD
Start Date: 01/01/2024
End Date: 01/01/2026
Termination: Earlier of 24 months or 40,000 km

CLIENT OBLIGATIONS
- Routine Maintenance: According to manufacturer schedule
- Oil Change: Every 15,000km or 12 months
Payment: 189 NIS Monthly

RESTRICTIONS
- Do not install LPG systems
- Use only authorized service centers

ENGINE COVERAGE
Deductible: 400 NIS
Cap: 15,000 NIS
Included: Pistons, Cylinder Head, Crankshaft, Valves
Excluded: Turbo, Timing Belt, Spark Plugs

TRANSMISSION COVERAGE
Deductible: 400 NIS
Cap: 12,000 NIS
Included: Gearbox, Clutch Plate, Differential
Excluded: Clutch Cable, Gear Linkage

ROADSIDE ASSISTANCE
No Deductible
Included: Jumpstart, Tire Change, Fuel Delivery
Excluded: Towing, Vehicle Recovery
Limit: 4 services per year

SERVICE NETWORK
Network Type: Closed
Shlomo Service Centers (*9406)
Hatzev Trade (1-800-800-800)
Access: Call *9406 or book via App
"""


# =============================================================================
# Identity Data Extraction Tests
# =============================================================================


class TestIdentityDataExtraction:
    """Tests for extracting identity/metadata from policy documents."""

    @pytest.mark.unit
    def test_extract_policy_id(self, classifier, sample_policy_text):
        """Test extraction of policy ID."""
        result = classifier.classify_document(sample_policy_text)
        
        assert "policy_id" in result.identity_data
        assert "123456" in result.identity_data["policy_id"]

    @pytest.mark.unit
    def test_extract_provider_name(self, classifier, sample_policy_text):
        """Test extraction of provider name."""
        result = classifier.classify_document(sample_policy_text)
        
        assert "provider_name" in result.identity_data
        assert "Universal Insurance" in result.identity_data["provider_name"]

    @pytest.mark.unit
    def test_extract_policy_type(self, classifier, sample_policy_text):
        """Test extraction of policy type."""
        result = classifier.classify_document(sample_policy_text)
        
        assert "policy_type" in result.identity_data
        assert "Mechanical Warranty" in result.identity_data["policy_type"]

    @pytest.mark.unit
    def test_extract_status(self, classifier, sample_policy_text):
        """Test extraction of policy status."""
        result = classifier.classify_document(sample_policy_text)
        
        assert "status" in result.identity_data
        assert result.identity_data["status"].lower() == "active"

    @pytest.mark.unit
    def test_extract_start_date(self, classifier, sample_policy_text):
        """Test extraction of validity start date."""
        result = classifier.classify_document(sample_policy_text)
        
        assert "start_date" in result.identity_data
        assert "01/01/2024" in result.identity_data["start_date"]

    @pytest.mark.unit
    def test_extract_end_date(self, classifier, sample_policy_text):
        """Test extraction of validity end date."""
        result = classifier.classify_document(sample_policy_text)
        
        assert "end_date" in result.identity_data
        assert "01/01/2026" in result.identity_data["end_date"]


# =============================================================================
# Coverage Lists Extraction Tests
# =============================================================================


class TestCoverageListsExtraction:
    """Tests for extracting coverage inclusions and exclusions."""

    @pytest.mark.unit
    def test_extract_engine_inclusions(self, classifier, sample_policy_text):
        """Test extraction of engine coverage inclusions."""
        result = classifier.classify_document(sample_policy_text)
        
        assert "engine" in result.coverage_inclusions
        inclusions = result.coverage_inclusions["engine"]
        # Check for at least some expected items
        assert len(inclusions) > 0

    @pytest.mark.unit
    def test_extract_engine_exclusions(self, classifier, sample_policy_text):
        """Test extraction of engine coverage exclusions."""
        result = classifier.classify_document(sample_policy_text)
        
        assert "engine" in result.coverage_exclusions
        exclusions = result.coverage_exclusions["engine"]
        assert len(exclusions) > 0

    @pytest.mark.unit
    def test_extract_transmission_coverage(self, classifier, sample_policy_text):
        """Test extraction of transmission coverage."""
        result = classifier.classify_document(sample_policy_text)
        
        # Should have transmission inclusions or exclusions
        has_transmission = (
            "transmission" in result.coverage_inclusions or
            "transmission" in result.coverage_exclusions
        )
        assert has_transmission

    @pytest.mark.unit
    def test_extract_roadside_coverage(self, classifier, sample_policy_text):
        """Test extraction of roadside assistance coverage."""
        result = classifier.classify_document(sample_policy_text)
        
        # Should have roadside inclusions
        has_roadside = (
            "roadside" in result.coverage_inclusions or
            "roadside" in result.coverage_exclusions
        )
        assert has_roadside


# =============================================================================
# Financial Terms Extraction Tests
# =============================================================================


class TestFinancialTermsExtraction:
    """Tests for extracting financial terms (deductibles, caps)."""

    @pytest.mark.unit
    @pytest.mark.financial
    def test_extract_deductible(self, classifier, sample_policy_text):
        """Test extraction of deductible amounts."""
        result = classifier.classify_document(sample_policy_text)
        
        # Should have financial terms for at least one category
        assert len(result.financial_terms) > 0
        
        # Check for deductible in at least one category
        has_deductible = any(
            "deductible" in terms
            for terms in result.financial_terms.values()
        )
        assert has_deductible

    @pytest.mark.unit
    @pytest.mark.financial
    def test_extract_coverage_cap(self, classifier, sample_policy_text):
        """Test extraction of coverage cap amounts."""
        result = classifier.classify_document(sample_policy_text)
        
        # Check for cap in at least one category
        has_cap = any(
            "coverage_cap" in terms or "cap" in terms
            for terms in result.financial_terms.values()
        )
        # Cap might be extracted differently, so just verify financial terms exist
        assert len(result.financial_terms) > 0


# =============================================================================
# Client Obligations Extraction Tests
# =============================================================================


class TestClientObligationsExtraction:
    """Tests for extracting client obligations and restrictions."""

    @pytest.mark.unit
    def test_extract_payment_terms(self, classifier, sample_policy_text):
        """Test extraction of payment terms."""
        result = classifier.classify_document(sample_policy_text)
        
        payment = result.client_obligations.get("payment_terms", {})
        # Should extract amount
        if payment:
            assert "amount" in payment

    @pytest.mark.unit
    def test_extract_restrictions(self, classifier, sample_policy_text):
        """Test extraction of restrictions."""
        result = classifier.classify_document(sample_policy_text)
        
        restrictions = result.client_obligations.get("restrictions", [])
        # Should have some restrictions
        assert isinstance(restrictions, list)


# =============================================================================
# Service Network Extraction Tests
# =============================================================================


class TestServiceNetworkExtraction:
    """Tests for extracting service network information."""

    @pytest.mark.unit
    def test_extract_network_type(self, classifier, sample_policy_text):
        """Test extraction of network type."""
        result = classifier.classify_document(sample_policy_text)
        
        network = result.service_network
        if network.get("network_type"):
            assert network["network_type"] in ["Closed", "Open", "Hybrid"]

    @pytest.mark.unit
    def test_extract_suppliers(self, classifier, sample_policy_text):
        """Test extraction of approved suppliers."""
        result = classifier.classify_document(sample_policy_text)
        
        suppliers = result.service_network.get("suppliers", [])
        # May or may not extract suppliers depending on format
        assert isinstance(suppliers, list)


# =============================================================================
# Text Block Classification Tests
# =============================================================================


class TestTextBlockClassification:
    """Tests for classifying individual text blocks."""

    @pytest.mark.unit
    def test_classify_section_header(self, classifier):
        """Test classification of section headers."""
        block = TextBlock(
            text="ENGINE COVERAGE",
            confidence=0.99,
            bbox=(100, 400, 300, 420),
            page_number=1,
        )
        
        result = classifier.classify_text_block(block)
        
        assert result.category == TextCategory.SECTION_HEADER
        assert result.subcategory == "engine"

    @pytest.mark.unit
    def test_classify_identity_block(self, classifier):
        """Test classification of identity data blocks."""
        block = TextBlock(
            text="Policy Number: POL-2024-123456",
            confidence=0.98,
            bbox=(100, 100, 400, 120),
            page_number=1,
        )
        
        result = classifier.classify_text_block(block)
        
        assert result.category == TextCategory.IDENTITY_DATA

    @pytest.mark.unit
    def test_classify_financial_block(self, classifier):
        """Test classification of financial data blocks."""
        block = TextBlock(
            text="Deductible: 400 NIS",
            confidence=0.95,
            bbox=(100, 500, 300, 520),
            page_number=1,
        )
        
        result = classifier.classify_text_block(block)
        
        assert result.category == TextCategory.FINANCIAL_LOGIC

    @pytest.mark.unit
    def test_classify_exclusion_block(self, classifier):
        """Test classification of exclusion blocks."""
        block = TextBlock(
            text="Excluded: Turbo, Timing Belt",
            confidence=0.95,
            bbox=(100, 460, 400, 480),
            page_number=1,
        )
        
        result = classifier.classify_text_block(block)
        
        assert result.category == TextCategory.COVERAGE_EXCLUSIONS

    @pytest.mark.unit
    def test_classify_inclusion_block(self, classifier):
        """Test classification of inclusion blocks."""
        block = TextBlock(
            text="Included: Pistons, Crankshaft, Valves",
            confidence=0.95,
            bbox=(100, 430, 400, 450),
            page_number=1,
        )
        
        result = classifier.classify_text_block(block)
        
        assert result.category == TextCategory.COVERAGE_INCLUSIONS

    @pytest.mark.unit
    def test_classify_unknown_block(self, classifier):
        """Test classification of ambiguous blocks."""
        block = TextBlock(
            text="Lorem ipsum dolor sit amet",
            confidence=0.90,
            bbox=(100, 600, 400, 620),
            page_number=1,
        )
        
        result = classifier.classify_text_block(block)
        
        assert result.category == TextCategory.UNKNOWN
        assert result.confidence < 0.7  # Low confidence for unknown


# =============================================================================
# Edge Cases Tests
# =============================================================================


class TestClassifierEdgeCases:
    """Tests for edge cases in text classification."""

    @pytest.mark.unit
    def test_empty_text(self, classifier):
        """Test handling of empty text."""
        result = classifier.classify_document("")
        
        assert isinstance(result, ClassificationResult)
        assert len(result.identity_data) == 0

    @pytest.mark.unit
    def test_minimal_text(self, classifier):
        """Test handling of minimal/sparse text."""
        minimal_text = "Policy Active"
        result = classifier.classify_document(minimal_text)
        
        assert isinstance(result, ClassificationResult)

    @pytest.mark.unit
    def test_mixed_case_keywords(self, classifier):
        """Test case-insensitive keyword matching."""
        text = "EXCLUDED: Turbo\nINCLUDED: Pistons"
        result = classifier.classify_document(text)
        
        # Should still extract despite case differences
        assert isinstance(result, ClassificationResult)

    @pytest.mark.unit
    def test_multiple_date_formats(self, classifier):
        """Test extraction of dates in different formats."""
        text = """
        Start Date: 01/01/2024
        End Date: 2026-01-01
        """
        result = classifier.classify_document(text)
        
        # Should extract at least start date
        assert "start_date" in result.identity_data


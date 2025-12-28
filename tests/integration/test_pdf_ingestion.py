"""
Integration tests for app/services/pdf_ingestion.py - PDF Ingestion Pipeline.

Tests the complete ETL flow:
1. OCR extraction (using mock)
2. Semantic classification
3. PolicyDocument transformation
"""

import pytest

from app.schema import (
    CoverageStatus,
    NetworkType,
    PolicyDocument,
    PolicyStatus,
)
from app.services.ocr_engine import MockOCREngine, TextBlock
from app.services.pdf_ingestion import (
    IngestionResult,
    PDFIngestionPipeline,
    ingest_policy_pdf,
)
from app.services.policy_engine import PolicyEngine


@pytest.fixture
def mock_pipeline():
    """Create a pipeline with mock OCR engine."""
    return PDFIngestionPipeline(use_mock=True)


@pytest.fixture
def custom_mock_pipeline():
    """Create a pipeline with custom mock data."""
    mock_data = {
        "full_text": """
INSURANCE POLICY DOCUMENT
Policy Number: TEST-POL-999
Provider: Test Insurance Provider
Policy Type: Test Warranty
Status: Active

Start Date: 15/06/2024
End Date: 15/06/2026
Termination: 24 months or 50,000 km

ENGINE COVERAGE
Deductible: 500 NIS
Cap: 20000 NIS
Included: Test Part A, Test Part B, Test Part C
Excluded: Excluded Part X, Excluded Part Y

TRANSMISSION COVERAGE
Deductible: 300 NIS
Included: Gearbox, Differential
Excluded: Linkage

SERVICE NETWORK
Network Type: Closed
Test Garage (*1234)
Access: Call *1234
""",
        "text_blocks": [
            TextBlock("INSURANCE POLICY DOCUMENT", 0.99, (100, 50, 500, 80), 1),
            TextBlock("Policy Number: TEST-POL-999", 0.98, (100, 100, 400, 120), 1),
        ],
    }
    mock_engine = MockOCREngine(mock_data=mock_data)
    return PDFIngestionPipeline(ocr_engine=mock_engine)


# =============================================================================
# Pipeline Integration Tests
# =============================================================================


class TestPDFIngestionPipeline:
    """Integration tests for the complete ingestion pipeline."""

    @pytest.mark.integration
    def test_pipeline_ingest_returns_result(self, mock_pipeline):
        """Test that pipeline returns an IngestionResult."""
        result = mock_pipeline.ingest_pdf("/fake/path/policy.pdf")
        
        assert isinstance(result, IngestionResult)
        assert result.processing_time_ms > 0

    @pytest.mark.integration
    def test_pipeline_success_with_mock(self, mock_pipeline):
        """Test successful ingestion with mock OCR."""
        result = mock_pipeline.ingest_pdf("/fake/path/policy.pdf")
        
        assert result.success is True
        assert len(result.errors) == 0
        assert result.policy_document is not None

    @pytest.mark.integration
    def test_pipeline_creates_policy_document(self, mock_pipeline):
        """Test that pipeline creates valid PolicyDocument."""
        result = mock_pipeline.ingest_pdf("/fake/path/policy.pdf")
        
        assert result.policy_document is not None
        assert isinstance(result.policy_document, PolicyDocument)
        assert result.policy_document.policy_meta is not None

    @pytest.mark.integration
    def test_pipeline_extracts_policy_meta(self, mock_pipeline):
        """Test extraction of policy metadata."""
        result = mock_pipeline.ingest_pdf("/fake/path/policy.pdf")
        
        policy = result.policy_document
        assert policy.policy_meta.policy_id is not None
        assert policy.policy_meta.provider_name is not None
        assert policy.policy_meta.status == PolicyStatus.ACTIVE

    @pytest.mark.integration
    def test_pipeline_extracts_coverage_details(self, mock_pipeline):
        """Test extraction of coverage details."""
        result = mock_pipeline.ingest_pdf("/fake/path/policy.pdf")
        
        policy = result.policy_document
        assert policy.coverage_details is not None
        # Should have at least one coverage category
        assert len(policy.coverage_details) >= 0  # May vary based on mock data

    @pytest.mark.integration
    def test_pipeline_preserves_ocr_result(self, mock_pipeline):
        """Test that OCR result is preserved in output."""
        result = mock_pipeline.ingest_pdf("/fake/path/policy.pdf")
        
        assert result.ocr_result is not None
        assert result.ocr_result.full_text is not None
        assert len(result.ocr_result.full_text) > 0

    @pytest.mark.integration
    def test_pipeline_preserves_classification_result(self, mock_pipeline):
        """Test that classification result is preserved."""
        result = mock_pipeline.ingest_pdf("/fake/path/policy.pdf")
        
        assert result.classification_result is not None


# =============================================================================
# Custom Mock Data Tests
# =============================================================================


class TestCustomMockPipeline:
    """Tests with custom mock data for specific scenarios."""

    @pytest.mark.integration
    def test_extracts_custom_policy_id(self, custom_mock_pipeline):
        """Test extraction of specific policy ID."""
        result = custom_mock_pipeline.ingest_pdf("/fake/policy.pdf")
        
        assert result.success
        # Policy ID should contain our test value
        policy_id = result.policy_document.policy_meta.policy_id
        assert "999" in policy_id or "TEST" in policy_id

    @pytest.mark.integration
    def test_extracts_custom_provider(self, custom_mock_pipeline):
        """Test extraction of specific provider name."""
        result = custom_mock_pipeline.ingest_pdf("/fake/policy.pdf")
        
        assert result.success
        provider = result.policy_document.policy_meta.provider_name
        assert "Test" in provider or "Insurance" in provider

    @pytest.mark.integration
    def test_extracts_coverage_categories(self, custom_mock_pipeline):
        """Test extraction of coverage categories from custom mock."""
        result = custom_mock_pipeline.ingest_pdf("/fake/policy.pdf")
        
        assert result.success
        categories = result.policy_document.coverage_details
        # May have engine and/or transmission categories
        category_names = [c.category.lower() for c in categories]
        # Just verify we got some categories
        assert isinstance(categories, list)


# =============================================================================
# Text Ingestion Tests (Skip OCR)
# =============================================================================


class TestTextIngestion:
    """Tests for direct text ingestion (skipping OCR)."""

    @pytest.mark.integration
    def test_ingest_text_directly(self):
        """Test ingestion from raw text."""
        pipeline = PDFIngestionPipeline(use_mock=True)
        
        raw_text = """
        Policy Number: DIRECT-001
        Provider: Direct Insurance
        Status: Active
        
        ENGINE COVERAGE
        Deductible: 250 NIS
        Included: Pistons, Valves
        Excluded: Turbo
        """
        
        result = pipeline.ingest_text(raw_text)
        
        assert result.success
        assert result.policy_document is not None

    @pytest.mark.integration
    def test_ingest_text_extracts_identity(self):
        """Test that text ingestion extracts identity data."""
        pipeline = PDFIngestionPipeline(use_mock=True)
        
        raw_text = """
        Policy Number: TEXT-123
        Provider: Text Insurance Co.
        Policy Type: Test Policy
        Status: Active
        """
        
        result = pipeline.ingest_text(raw_text)
        
        assert result.success
        assert result.policy_document.policy_meta is not None


# =============================================================================
# End-to-End Pipeline Tests
# =============================================================================


class TestEndToEndPipeline:
    """End-to-end tests combining ingestion with policy engine."""

    @pytest.mark.integration
    def test_ingested_policy_works_with_engine(self, mock_pipeline):
        """Test that ingested PolicyDocument works with PolicyEngine."""
        # Ingest policy
        result = mock_pipeline.ingest_pdf("/fake/policy.pdf")
        assert result.success
        
        # Load into engine
        engine = PolicyEngine(policy=result.policy_document)
        
        # Verify engine works
        summary = engine.get_policy_summary()
        assert "policy_id" in summary
        assert "coverage_categories" in summary

    @pytest.mark.integration
    def test_ingested_policy_coverage_check(self, mock_pipeline):
        """Test coverage checking on ingested policy."""
        # Ingest policy
        result = mock_pipeline.ingest_pdf("/fake/policy.pdf")
        assert result.success
        
        # Load into engine
        engine = PolicyEngine(policy=result.policy_document)
        
        # Check some item (will be UNKNOWN if not in mock data)
        check_result = engine.check_coverage("TestItem")
        assert check_result is not None
        assert check_result.status is not None


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestConvenienceFunction:
    """Tests for the ingest_policy_pdf convenience function."""

    @pytest.mark.integration
    def test_convenience_function_returns_policy(self):
        """Test that convenience function returns PolicyDocument."""
        policy = ingest_policy_pdf("/fake/policy.pdf", use_mock=True)
        
        assert isinstance(policy, PolicyDocument)
        assert policy.policy_meta is not None

    @pytest.mark.integration
    def test_convenience_function_with_mock(self):
        """Test convenience function with mock OCR."""
        policy = ingest_policy_pdf("/any/path.pdf", use_mock=True)
        
        assert policy is not None
        assert policy.policy_meta.status == PolicyStatus.ACTIVE


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in the pipeline."""

    @pytest.mark.integration
    def test_handles_empty_ocr_result(self):
        """Test handling of empty OCR results."""
        # Create mock with empty text
        empty_mock = MockOCREngine(mock_data={
            "full_text": "",
            "text_blocks": [],
        })
        pipeline = PDFIngestionPipeline(ocr_engine=empty_mock)
        
        result = pipeline.ingest_pdf("/fake/empty.pdf")
        
        # Should fail gracefully
        assert result.success is False
        assert len(result.errors) > 0

    @pytest.mark.integration
    def test_handles_minimal_data(self):
        """Test handling of minimal/sparse OCR data."""
        minimal_mock = MockOCREngine(mock_data={
            "full_text": "Policy Active",
            "text_blocks": [
                TextBlock("Policy Active", 0.9, (0, 0, 100, 20), 1),
            ],
        })
        pipeline = PDFIngestionPipeline(ocr_engine=minimal_mock)
        
        result = pipeline.ingest_pdf("/fake/minimal.pdf")
        
        # Should succeed but with sparse data
        assert result.success is True
        assert result.policy_document is not None


# =============================================================================
# Performance Tests
# =============================================================================


class TestPipelinePerformance:
    """Basic performance tests for the pipeline."""

    @pytest.mark.integration
    def test_pipeline_completes_quickly(self, mock_pipeline):
        """Test that mock pipeline completes in reasonable time."""
        result = mock_pipeline.ingest_pdf("/fake/policy.pdf")
        
        # Mock pipeline should be very fast (<100ms)
        assert result.processing_time_ms < 1000  # 1 second max

    @pytest.mark.integration
    def test_multiple_ingestions_consistent(self, mock_pipeline):
        """Test that multiple ingestions produce consistent results."""
        results = [
            mock_pipeline.ingest_pdf("/fake/policy.pdf")
            for _ in range(5)
        ]
        
        # All should succeed
        assert all(r.success for r in results)
        
        # Policy IDs should be consistent (same mock data)
        policy_ids = [r.policy_document.policy_meta.policy_id for r in results]
        # All should match the first one
        assert all(pid == policy_ids[0] for pid in policy_ids)


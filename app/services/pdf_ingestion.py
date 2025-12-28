"""
PDF Ingestion Pipeline for Universal Insurance AI Agent.

PRD Section 3.1 - Policy Ingestion Engine (ETL):
- OCR & Layout Preservation
- Semantic Segmentation
- Transform to structured PolicyDocument schema

This pipeline orchestrates:
1. PDF/Image → OCR extraction (PaddleOCR)
2. Text classification (semantic segmentation)
3. Data transformation → PolicyDocument schema
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from app.schema import (
    ApprovedSupplier,
    ClientObligations,
    CoverageCategory,
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
from app.services.ocr_engine import DocumentOCRResult, MockOCREngine, OCREngine
from app.services.text_classifier import ClassificationResult, TextClassifier

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Result of the PDF ingestion pipeline."""

    policy_document: Optional[PolicyDocument] = None
    ocr_result: Optional[DocumentOCRResult] = None
    classification_result: Optional[ClassificationResult] = None
    success: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    processing_time_ms: float = 0.0
    source_path: Optional[str] = None


class PDFIngestionPipeline:
    """
    Main pipeline for ingesting PDF insurance documents.

    Transforms unstructured PDF documents into structured PolicyDocument
    schema using OCR and semantic classification.
    """

    def __init__(
        self,
        ocr_engine: Optional[OCREngine] = None,
        text_classifier: Optional[TextClassifier] = None,
        use_mock: bool = False,
    ):
        """
        Initialize the ingestion pipeline.

        Args:
            ocr_engine: Custom OCR engine (defaults to PaddleOCR)
            text_classifier: Custom text classifier
            use_mock: Use mock OCR engine for testing
        """
        if use_mock:
            self.ocr_engine = MockOCREngine()
        else:
            self.ocr_engine = ocr_engine or OCREngine()

        self.text_classifier = text_classifier or TextClassifier()

    def ingest_pdf(
        self,
        pdf_path: Union[str, Path],
        dpi: int = 200,
    ) -> IngestionResult:
        """
        Ingest a PDF document and extract structured policy data.

        Args:
            pdf_path: Path to the PDF file
            dpi: Resolution for PDF to image conversion

        Returns:
            IngestionResult with PolicyDocument and metadata
        """
        import time

        start_time = time.time()
        result = IngestionResult(source_path=str(pdf_path))

        try:
            # Step 1: OCR Extraction
            logger.info(f"Starting OCR extraction for: {pdf_path}")
            ocr_result = self.ocr_engine.extract_from_pdf(pdf_path, dpi=dpi)
            result.ocr_result = ocr_result

            if not ocr_result.full_text.strip():
                result.errors.append("OCR extraction returned empty text")
                return result

            logger.info(f"OCR extracted {len(ocr_result.full_text)} characters from {ocr_result.total_pages} pages")

            # Step 2: Text Classification
            logger.info("Starting semantic classification")
            classification_result = self.text_classifier.classify_document(
                ocr_result.full_text
            )
            result.classification_result = classification_result

            # Step 3: Transform to PolicyDocument
            logger.info("Transforming to PolicyDocument schema")
            policy_document = self._transform_to_policy_document(
                classification_result, ocr_result.full_text
            )
            result.policy_document = policy_document
            result.success = True

        except FileNotFoundError as e:
            result.errors.append(f"File not found: {e}")
        except Exception as e:
            logger.exception(f"Ingestion failed: {e}")
            result.errors.append(f"Ingestion error: {str(e)}")

        result.processing_time_ms = (time.time() - start_time) * 1000
        return result

    def ingest_image(
        self,
        image_path: Union[str, Path],
    ) -> IngestionResult:
        """
        Ingest an image document (single page).

        Args:
            image_path: Path to the image file

        Returns:
            IngestionResult with PolicyDocument
        """
        import time

        start_time = time.time()
        result = IngestionResult(source_path=str(image_path))

        try:
            # OCR extraction
            ocr_result = self.ocr_engine.extract_from_image(image_path)
            result.ocr_result = ocr_result

            if not ocr_result.full_text.strip():
                result.errors.append("OCR extraction returned empty text")
                return result

            # Classification
            classification_result = self.text_classifier.classify_document(
                ocr_result.full_text
            )
            result.classification_result = classification_result

            # Transform
            policy_document = self._transform_to_policy_document(
                classification_result, ocr_result.full_text
            )
            result.policy_document = policy_document
            result.success = True

        except Exception as e:
            logger.exception(f"Image ingestion failed: {e}")
            result.errors.append(f"Ingestion error: {str(e)}")

        result.processing_time_ms = (time.time() - start_time) * 1000
        return result

    def ingest_text(self, raw_text: str) -> IngestionResult:
        """
        Ingest raw text directly (skip OCR).

        Useful for testing or when text is already extracted.

        Args:
            raw_text: Raw text content of the policy document

        Returns:
            IngestionResult with PolicyDocument
        """
        import time

        start_time = time.time()
        result = IngestionResult()

        try:
            # Classification
            classification_result = self.text_classifier.classify_document(raw_text)
            result.classification_result = classification_result

            # Transform
            policy_document = self._transform_to_policy_document(
                classification_result, raw_text
            )
            result.policy_document = policy_document
            result.success = True

        except Exception as e:
            logger.exception(f"Text ingestion failed: {e}")
            result.errors.append(f"Ingestion error: {str(e)}")

        result.processing_time_ms = (time.time() - start_time) * 1000
        return result

    def _transform_to_policy_document(
        self,
        classification: ClassificationResult,
        raw_text: str,
    ) -> PolicyDocument:
        """
        Transform classification results into PolicyDocument schema.

        Args:
            classification: Semantic classification results
            raw_text: Original raw text for fallback extraction

        Returns:
            PolicyDocument with structured data
        """
        # Build PolicyMeta
        policy_meta = self._build_policy_meta(classification.identity_data, raw_text)

        # Build ClientObligations
        client_obligations = self._build_client_obligations(
            classification.client_obligations
        )

        # Build CoverageDetails
        coverage_details = self._build_coverage_details(
            classification.coverage_inclusions,
            classification.coverage_exclusions,
            classification.financial_terms,
        )

        # Build ServiceNetwork
        service_network = self._build_service_network(classification.service_network)

        return PolicyDocument(
            policy_meta=policy_meta,
            client_obligations=client_obligations,
            coverage_details=coverage_details,
            service_network=service_network,
        )

    def _build_policy_meta(
        self, identity_data: dict, raw_text: str
    ) -> PolicyMeta:
        """Build PolicyMeta from extracted identity data."""
        # Parse policy ID
        policy_id = identity_data.get("policy_id", self._generate_policy_id())

        # Parse provider name
        provider_name = identity_data.get("provider_name", "Unknown Provider")

        # Parse policy type
        policy_type = identity_data.get("policy_type", "Insurance Policy")

        # Parse status
        status_str = identity_data.get("status", "active").lower()
        status_map = {
            "active": PolicyStatus.ACTIVE,
            "suspended": PolicyStatus.SUSPENDED,
            "expired": PolicyStatus.EXPIRED,
        }
        status = status_map.get(status_str, PolicyStatus.ACTIVE)

        # Parse validity period
        validity_period = self._parse_validity_period(identity_data, raw_text)

        return PolicyMeta(
            policy_id=policy_id,
            provider_name=provider_name,
            policy_type=policy_type,
            status=status,
            validity_period=validity_period,
        )

    def _parse_validity_period(
        self, identity_data: dict, raw_text: str
    ) -> ValidityPeriod:
        """Parse validity period from extracted data."""
        # Try to parse start date
        start_date = self._parse_date(identity_data.get("start_date"))
        if not start_date:
            start_date = datetime.now()

        # Try to parse end date
        end_date = self._parse_date(identity_data.get("end_date"))
        if not end_date:
            # Default to 1 year from start
            end_date = datetime(
                start_date.year + 1, start_date.month, start_date.day
            )

        # Get termination condition
        termination = identity_data.get("termination_condition")

        return ValidityPeriod(
            start_date=start_date,
            end_date_calculated=end_date,
            termination_condition=termination,
        )

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date from various formats."""
        if not date_str:
            return None

        # Common date formats
        formats = [
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d/%m/%y",
            "%m/%d/%y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        return None

    def _generate_policy_id(self) -> str:
        """Generate a default policy ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"POL-{timestamp}"

    def _build_client_obligations(self, obligations_data: dict) -> ClientObligations:
        """Build ClientObligations from extracted data."""
        mandatory_actions = []
        for action_data in obligations_data.get("mandatory_actions", []):
            if isinstance(action_data, dict):
                mandatory_actions.append(
                    MandatoryAction(
                        action=action_data.get("action", ""),
                        condition=action_data.get("condition", ""),
                        grace_period=action_data.get("grace_period"),
                        penalty_for_breach=action_data.get("penalty"),
                    )
                )

        # Parse payment terms
        payment_terms = None
        payment_data = obligations_data.get("payment_terms", {})
        if payment_data.get("amount"):
            frequency_str = payment_data.get("frequency", "monthly").lower()
            frequency = (
                PaymentFrequency.ANNUAL
                if "annual" in frequency_str
                else PaymentFrequency.MONTHLY
            )
            payment_terms = PaymentTerms(
                amount=float(payment_data["amount"]),
                frequency=frequency,
                method=payment_data.get("method"),
            )

        # Parse restrictions
        restrictions = obligations_data.get("restrictions", [])
        if isinstance(restrictions, str):
            restrictions = [restrictions]

        return ClientObligations(
            mandatory_actions=mandatory_actions,
            payment_terms=payment_terms,
            restrictions=restrictions,
        )

    def _build_coverage_details(
        self,
        inclusions: dict[str, list[str]],
        exclusions: dict[str, list[str]],
        financial_terms: dict[str, dict],
    ) -> list[CoverageCategory]:
        """Build CoverageCategory list from extracted data."""
        coverage_details = []

        # Get all unique categories
        all_categories = set(inclusions.keys()) | set(exclusions.keys()) | set(
            financial_terms.keys()
        )

        # Category name mapping (normalize section names)
        category_name_map = {
            "engine": "Engine",
            "transmission": "Transmission",
            "electrical": "Electrical",
            "cooling": "Cooling System",
            "roadside": "Roadside Assistance",
            "general": "General Coverage",
        }

        for category_key in all_categories:
            if category_key in ("general", "validity", "obligations", "restrictions"):
                continue

            # Normalize category name
            category_name = category_name_map.get(
                category_key.lower(), category_key.title()
            )

            # Get items
            items_included = inclusions.get(category_key, [])
            items_excluded = exclusions.get(category_key, [])

            # Get financial terms
            fin_data = financial_terms.get(category_key, {})
            deductible = fin_data.get("deductible", 0.0)
            coverage_cap = fin_data.get("coverage_cap")

            # Convert "unlimited" string to proper value
            if isinstance(coverage_cap, str) and "unlimited" in coverage_cap.lower():
                coverage_cap = "Unlimited"

            coverage_details.append(
                CoverageCategory(
                    category=category_name,
                    items_included=items_included,
                    items_excluded=items_excluded,
                    financial_terms=FinancialTerms(
                        deductible=float(deductible) if deductible else 0.0,
                        coverage_cap=coverage_cap,
                    ),
                )
            )

        return coverage_details

    def _build_service_network(self, network_data: dict) -> Optional[ServiceNetwork]:
        """Build ServiceNetwork from extracted data."""
        if not network_data or not any(network_data.values()):
            return None

        # Parse network type
        network_type_str = network_data.get("network_type", "closed").lower()
        network_type_map = {
            "closed": NetworkType.CLOSED,
            "open": NetworkType.OPEN,
            "hybrid": NetworkType.HYBRID,
        }
        network_type = network_type_map.get(network_type_str, NetworkType.CLOSED)

        # Parse suppliers
        approved_suppliers = []
        for supplier_data in network_data.get("suppliers", []):
            if isinstance(supplier_data, dict):
                approved_suppliers.append(
                    ApprovedSupplier(
                        name=supplier_data.get("name", "Unknown"),
                        service_type=supplier_data.get("service_type", "General"),
                        contact_info=supplier_data.get("contact"),
                    )
                )

        return ServiceNetwork(
            network_type=network_type,
            approved_suppliers=approved_suppliers,
            access_method=network_data.get("access_method"),
        )


# Convenience function for quick ingestion
def ingest_policy_pdf(
    pdf_path: Union[str, Path],
    use_mock: bool = False,
) -> PolicyDocument:
    """
    Convenience function to ingest a PDF and return PolicyDocument.

    Args:
        pdf_path: Path to the PDF file
        use_mock: Use mock OCR for testing

    Returns:
        PolicyDocument with extracted data

    Raises:
        ValueError: If ingestion fails
    """
    pipeline = PDFIngestionPipeline(use_mock=use_mock)
    result = pipeline.ingest_pdf(pdf_path)

    if not result.success:
        raise ValueError(f"Ingestion failed: {'; '.join(result.errors)}")

    return result.policy_document


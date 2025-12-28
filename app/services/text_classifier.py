"""
Text Classifier for Semantic Segmentation of Insurance Policy Documents.

PRD Section 3.1 - Semantic Segmentation:
Classify text blocks into:
- Identity_Data (Name, Vehicle, ID)
- Coverage_Inclusions (e.g., Engine, Gearbox)
- Coverage_Exclusions (e.g., Turbo, Timing Belt)
- Financial_Logic (Deductibles, Caps, Expiration)
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.services.ocr_engine import TextBlock


class TextCategory(str, Enum):
    """Categories for semantic text segmentation."""

    IDENTITY_DATA = "identity_data"
    COVERAGE_INCLUSIONS = "coverage_inclusions"
    COVERAGE_EXCLUSIONS = "coverage_exclusions"
    FINANCIAL_LOGIC = "financial_logic"
    CLIENT_OBLIGATIONS = "client_obligations"
    SERVICE_NETWORK = "service_network"
    SECTION_HEADER = "section_header"
    UNKNOWN = "unknown"


@dataclass
class ClassifiedTextBlock:
    """A text block with semantic classification."""

    text: str
    category: TextCategory
    confidence: float
    subcategory: Optional[str] = None  # e.g., "Engine", "Transmission"
    extracted_values: dict = field(default_factory=dict)
    original_block: Optional[TextBlock] = None


@dataclass
class ClassificationResult:
    """Complete classification result for a document."""

    classified_blocks: list[ClassifiedTextBlock] = field(default_factory=list)
    identity_data: dict = field(default_factory=dict)
    coverage_inclusions: dict[str, list[str]] = field(default_factory=dict)
    coverage_exclusions: dict[str, list[str]] = field(default_factory=dict)
    financial_terms: dict[str, dict] = field(default_factory=dict)
    client_obligations: dict = field(default_factory=dict)
    service_network: dict = field(default_factory=dict)


class TextClassifier:
    """
    Rule-based text classifier for insurance policy documents.

    Uses pattern matching and keyword detection to classify text blocks
    into semantic categories defined in PRD Section 3.1.
    """

    # Section header patterns
    SECTION_HEADERS = {
        "engine": r"engine\s*(coverage|warranty|section)?",
        "transmission": r"transmission\s*(coverage|warranty|section)?",
        "electrical": r"electrical\s*(coverage|warranty|section)?",
        "cooling": r"cooling\s*(system)?\s*(coverage|warranty|section)?",
        "roadside": r"roadside\s*(assistance|coverage|section)?",
        "coverage": r"coverage\s*(details|summary)?",
        "exclusions": r"exclusions?\s*(list)?",
        "inclusions": r"inclusions?\s*(list)?|included\s*items?",
        "obligations": r"(client|customer|your)\s*obligations?",
        "restrictions": r"restrictions?",
        "service_network": r"service\s*(network|providers?|centers?)",
        "validity": r"validity\s*(period)?|policy\s*term",
    }

    # Identity data patterns
    IDENTITY_PATTERNS = {
        "policy_id": [
            r"policy\s*(number|no|#|id)[:\s]*([A-Z0-9\-]+)",
            r"(POL|INS|WRN)[:\s\-]*(\d+[\-\d]*)",
        ],
        "provider_name": [
            r"provider[:\s]*(.+?)(?:\n|$)",
            r"insurer[:\s]*(.+?)(?:\n|$)",
            r"company[:\s]*(.+?)(?:\n|$)",
        ],
        "policy_type": [
            r"policy\s*type[:\s]*(.+?)(?:\n|$)",
            r"type[:\s]*(mechanical warranty|health|home|auto)",
        ],
        "status": [
            r"status[:\s]*(active|suspended|expired|pending)",
        ],
        "customer_name": [
            r"(customer|client|insured|policyholder)\s*(name)?[:\s]*([A-Za-z\s]+)",
            r"name[:\s]*([A-Za-z\s]+)",
        ],
        "vehicle_id": [
            r"(vehicle|car|vin)\s*(id|number)?[:\s]*([A-Z0-9]+)",
            r"license\s*(plate)?[:\s]*([A-Z0-9\-]+)",
        ],
    }

    # Financial patterns
    FINANCIAL_PATTERNS = {
        "deductible": [
            r"deductible[:\s]*(\d+[\d,\.]*)\s*(nis|ils|\$|usd)?",
            r"co-?pay[:\s]*(\d+[\d,\.]*)",
            r"self[:\s\-]*participation[:\s]*(\d+[\d,\.]*)",
        ],
        "coverage_cap": [
            r"(cap|limit|maximum|max)[:\s]*(\d+[\d,\.]*|unlimited)",
            r"up\s*to[:\s]*(\d+[\d,\.]*)",
        ],
        "premium": [
            r"premium[:\s]*(\d+[\d,\.]*)\s*(nis|monthly|annual)?",
            r"payment[:\s]*(\d+[\d,\.]*)\s*(nis|monthly|annual)?",
        ],
    }

    # Coverage list patterns
    COVERAGE_PATTERNS = {
        "included": [
            r"included?[:\s]*(.+?)(?:excluded|$)",
            r"covered[:\s]*(.+?)(?:not covered|excluded|$)",
            r"includes?[:\s]*(.+?)(?:excludes?|$)",
        ],
        "excluded": [
            r"excluded?[:\s]*(.+?)(?:included|$)",
            r"not\s*covered[:\s]*(.+?)(?:covered|$)",
            r"excludes?[:\s]*(.+?)(?:includes?|$)",
            r"exceptions?[:\s]*(.+?)(?:\n\n|$)",
        ],
    }

    # Validity/date patterns
    DATE_PATTERNS = {
        "start_date": [
            r"start\s*(date)?[:\s]*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
            r"effective\s*(from|date)?[:\s]*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
            r"begins?[:\s]*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
        ],
        "end_date": [
            r"end\s*(date)?[:\s]*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
            r"expires?[:\s]*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
            r"valid\s*(until|through)[:\s]*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
        ],
        "termination_condition": [
            r"termination[:\s]*(.+?)(?:\n|$)",
            r"earlier\s*of[:\s]*(.+?)(?:\n|$)",
        ],
    }

    # Obligation patterns
    OBLIGATION_PATTERNS = {
        "mandatory_action": [
            r"(routine\s*maintenance|oil\s*change|inspection)[:\s]*(.+?)(?:\n|$)",
            r"must\s+(perform|complete|do)[:\s]*(.+?)(?:\n|$)",
        ],
        "restriction": [
            r"do\s*not[:\s]*(.+?)(?:\n|$)",
            r"prohibited[:\s]*(.+?)(?:\n|$)",
            r"not\s*allowed[:\s]*(.+?)(?:\n|$)",
        ],
    }

    def __init__(self):
        """Initialize the classifier with compiled patterns."""
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns for performance."""
        self._compiled_sections = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.SECTION_HEADERS.items()
        }

    def classify_document(self, full_text: str) -> ClassificationResult:
        """
        Classify the full text of a document into semantic categories.

        Args:
            full_text: Complete OCR text from the document

        Returns:
            ClassificationResult with categorized data
        """
        result = ClassificationResult()

        # Extract identity data
        result.identity_data = self._extract_identity_data(full_text)

        # Extract financial terms per section
        result.financial_terms = self._extract_financial_terms(full_text)

        # Extract coverage inclusions and exclusions
        result.coverage_inclusions, result.coverage_exclusions = (
            self._extract_coverage_lists(full_text)
        )

        # Extract client obligations
        result.client_obligations = self._extract_obligations(full_text)

        # Extract service network info
        result.service_network = self._extract_service_network(full_text)

        return result

    def classify_text_block(
        self, block: TextBlock, context: Optional[str] = None
    ) -> ClassifiedTextBlock:
        """
        Classify a single text block.

        Args:
            block: The TextBlock to classify
            context: Optional surrounding context

        Returns:
            ClassifiedTextBlock with category and extracted values
        """
        text = block.text.lower().strip()

        # Check if it's a section header
        for section_name, pattern in self._compiled_sections.items():
            if pattern.search(text):
                return ClassifiedTextBlock(
                    text=block.text,
                    category=TextCategory.SECTION_HEADER,
                    confidence=0.9,
                    subcategory=section_name,
                    original_block=block,
                )

        # Check for identity data
        for field_name, patterns in self.IDENTITY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return ClassifiedTextBlock(
                        text=block.text,
                        category=TextCategory.IDENTITY_DATA,
                        confidence=0.85,
                        subcategory=field_name,
                        original_block=block,
                    )

        # Check for financial data
        for field_name, patterns in self.FINANCIAL_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return ClassifiedTextBlock(
                        text=block.text,
                        category=TextCategory.FINANCIAL_LOGIC,
                        confidence=0.85,
                        subcategory=field_name,
                        extracted_values={field_name: match.group(1)},
                        original_block=block,
                    )

        # Check for exclusion indicators
        exclusion_keywords = ["excluded", "not covered", "excludes", "exception", "does not"]
        if any(kw in text for kw in exclusion_keywords):
            return ClassifiedTextBlock(
                text=block.text,
                category=TextCategory.COVERAGE_EXCLUSIONS,
                confidence=0.8,
                original_block=block,
            )

        # Check for inclusion indicators
        inclusion_keywords = ["included", "covered", "includes", "coverage"]
        if any(kw in text for kw in inclusion_keywords):
            return ClassifiedTextBlock(
                text=block.text,
                category=TextCategory.COVERAGE_INCLUSIONS,
                confidence=0.8,
                original_block=block,
            )

        # Default to unknown
        return ClassifiedTextBlock(
            text=block.text,
            category=TextCategory.UNKNOWN,
            confidence=0.5,
            original_block=block,
        )

    def _extract_identity_data(self, text: str) -> dict:
        """Extract identity/metadata fields from text."""
        identity = {}

        for field_name, patterns in self.IDENTITY_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    # Get the last captured group (the actual value)
                    value = match.group(match.lastindex) if match.lastindex else match.group(0)
                    identity[field_name] = value.strip()
                    break

        # Extract dates
        for field_name, patterns in self.DATE_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    value = match.group(match.lastindex) if match.lastindex else match.group(0)
                    identity[field_name] = value.strip()
                    break

        return identity

    def _extract_financial_terms(self, text: str) -> dict[str, dict]:
        """Extract financial terms per coverage category."""
        financial = {}
        text_lower = text.lower()

        # Find coverage sections
        sections = self._split_into_sections(text)

        for section_name, section_text in sections.items():
            section_financial = {}

            for field_name, patterns in self.FINANCIAL_PATTERNS.items():
                for pattern in patterns:
                    match = re.search(pattern, section_text, re.IGNORECASE)
                    if match:
                        value = match.group(1)
                        # Convert to number if possible
                        try:
                            value = float(value.replace(",", ""))
                        except (ValueError, AttributeError):
                            pass
                        section_financial[field_name] = value
                        break

            if section_financial:
                financial[section_name] = section_financial

        return financial

    def _extract_coverage_lists(
        self, text: str
    ) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        """Extract included and excluded items per category."""
        inclusions = {}
        exclusions = {}

        # Split into sections
        sections = self._split_into_sections(text)

        for section_name, section_text in sections.items():
            # Extract included items
            included_items = self._extract_list_items(section_text, "included")
            if included_items:
                inclusions[section_name] = included_items

            # Extract excluded items
            excluded_items = self._extract_list_items(section_text, "excluded")
            if excluded_items:
                exclusions[section_name] = excluded_items

        return inclusions, exclusions

    def _extract_list_items(self, text: str, list_type: str) -> list[str]:
        """Extract comma-separated list items after a keyword."""
        items = []

        if list_type == "included":
            patterns = self.COVERAGE_PATTERNS["included"]
        else:
            patterns = self.COVERAGE_PATTERNS["excluded"]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                items_text = match.group(1)
                # Split by common delimiters
                raw_items = re.split(r"[,\n•\-\*]+", items_text)
                items = [
                    item.strip()
                    for item in raw_items
                    if item.strip() and len(item.strip()) > 2
                ]
                break

        return items

    def _extract_obligations(self, text: str) -> dict:
        """Extract client obligations and restrictions."""
        obligations = {
            "mandatory_actions": [],
            "restrictions": [],
            "payment_terms": {},
        }

        # Find obligations section
        obligations_match = re.search(
            r"(client\s*)?obligations?(.+?)(?:coverage|exclusions?|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )

        if obligations_match:
            section_text = obligations_match.group(2)

            # Extract mandatory actions
            for pattern in self.OBLIGATION_PATTERNS["mandatory_action"]:
                matches = re.findall(pattern, section_text, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        obligations["mandatory_actions"].append(
                            {"action": match[0], "condition": match[1] if len(match) > 1 else ""}
                        )
                    else:
                        obligations["mandatory_actions"].append({"action": match})

        # Extract restrictions
        restrictions_match = re.search(
            r"restrictions?(.+?)(?:coverage|$)", text, re.IGNORECASE | re.DOTALL
        )
        if restrictions_match:
            section_text = restrictions_match.group(1)
            for pattern in self.OBLIGATION_PATTERNS["restriction"]:
                matches = re.findall(pattern, section_text, re.IGNORECASE)
                obligations["restrictions"].extend(matches)

        # Extract payment terms
        payment_match = re.search(
            r"payment[:\s]*(\d+[\d,\.]*)\s*(nis|ils|\$)?\s*(monthly|annual)?",
            text,
            re.IGNORECASE,
        )
        if payment_match:
            obligations["payment_terms"] = {
                "amount": float(payment_match.group(1).replace(",", "")),
                "frequency": payment_match.group(3) or "monthly",
            }

        return obligations

    def _extract_service_network(self, text: str) -> dict:
        """Extract service network information."""
        network = {
            "network_type": None,
            "suppliers": [],
            "access_method": None,
        }

        # Find network section
        network_match = re.search(
            r"service\s*(network|providers?)(.+?)(?:\n\n|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )

        if network_match:
            section_text = network_match.group(2)

            # Network type
            type_match = re.search(r"(closed|open|hybrid)", section_text, re.IGNORECASE)
            if type_match:
                network["network_type"] = type_match.group(1).capitalize()

            # Suppliers (look for names with contact info)
            supplier_matches = re.findall(
                r"([A-Za-z\s]+(?:centers?|trade|service|network))\s*\(([^)]+)\)",
                section_text,
                re.IGNORECASE,
            )
            for name, contact in supplier_matches:
                network["suppliers"].append({"name": name.strip(), "contact": contact.strip()})

            # Access method
            access_match = re.search(
                r"(call|book|contact)[:\s]*(.+?)(?:\n|$)", section_text, re.IGNORECASE
            )
            if access_match:
                network["access_method"] = access_match.group(0).strip()

        return network

    def _split_into_sections(self, text: str) -> dict[str, str]:
        """Split document text into sections by headers."""
        sections = {}
        current_section = "general"
        current_text = []

        lines = text.split("\n")

        for line in lines:
            line_lower = line.lower().strip()

            # Check if this line is a section header
            is_header = False
            for section_name, pattern in self._compiled_sections.items():
                if pattern.search(line_lower):
                    # Save previous section
                    if current_text:
                        sections[current_section] = "\n".join(current_text)

                    # Start new section
                    current_section = section_name
                    current_text = [line]
                    is_header = True
                    break

            if not is_header:
                current_text.append(line)

        # Save last section
        if current_text:
            sections[current_section] = "\n".join(current_text)

        return sections


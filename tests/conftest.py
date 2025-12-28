"""
Pytest fixtures and configuration for Universal Insurance AI Agent tests.

This file contains shared fixtures that are automatically available to all tests.
Fixtures provide reusable test data and setup/teardown logic.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Generator

import pytest

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

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
from app.services.policy_engine import PolicyEngine
from app.services.llm_service import LLMProvider, MockLLM
from app.services.chat_service import ChatService


# =============================================================================
# Report Generation Hook
# =============================================================================


def pytest_configure(config):
    """Configure pytest with custom settings."""
    # Create reports directory if it doesn't exist
    reports_dir = Path(__file__).parent / "reports"
    reports_dir.mkdir(exist_ok=True)


def pytest_sessionfinish(session, exitstatus):
    """Generate test report after all tests complete."""
    reports_dir = Path(__file__).parent / "reports"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    
    # Collect test results
    passed = session.testscollected - session.testsfailed - getattr(session, 'testsskipped', 0)
    
    report_data = {
        "timestamp": timestamp,
        "summary": {
            "total": session.testscollected,
            "passed": passed,
            "failed": session.testsfailed,
            "exit_status": exitstatus,
        },
        "duration_seconds": getattr(session, 'duration', 0),
        "environment": {
            "python_version": sys.version,
            "platform": sys.platform,
        }
    }
    
    # Save JSON report
    json_report_path = reports_dir / f"report_{timestamp}.json"
    with open(json_report_path, "w") as f:
        json.dump(report_data, f, indent=2)
    
    # Generate markdown summary
    md_report_path = reports_dir / f"report_{timestamp}.md"
    with open(md_report_path, "w") as f:
        f.write(f"# Test Report - {timestamp}\n\n")
        f.write("## Summary\n\n")
        f.write(f"| Metric | Value |\n")
        f.write(f"|--------|-------|\n")
        f.write(f"| **Total Tests** | {session.testscollected} |\n")
        f.write(f"| **Passed** | ✅ {passed} |\n")
        f.write(f"| **Failed** | ❌ {session.testsfailed} |\n")
        f.write(f"| **Exit Status** | {exitstatus} |\n")
        f.write(f"\n## Environment\n\n")
        f.write(f"- **Python**: {sys.version.split()[0]}\n")
        f.write(f"- **Platform**: {sys.platform}\n")
        f.write(f"- **Timestamp**: {timestamp}\n")
    
    print(f"\n📊 Test reports saved to: {reports_dir}")


# =============================================================================
# Policy Document Fixtures
# =============================================================================


@pytest.fixture
def valid_validity_period() -> ValidityPeriod:
    """Create a valid future validity period."""
    return ValidityPeriod(
        start_date=datetime(2024, 1, 1),
        end_date_calculated=datetime(2026, 1, 1),
        termination_condition="Earlier of 24 months or 40,000 km",
    )


@pytest.fixture
def expired_validity_period() -> ValidityPeriod:
    """Create an expired validity period."""
    return ValidityPeriod(
        start_date=datetime(2020, 1, 1),
        end_date_calculated=datetime(2022, 1, 1),
        termination_condition="Expired",
    )


@pytest.fixture
def valid_policy_meta(valid_validity_period: ValidityPeriod) -> PolicyMeta:
    """Create valid policy metadata with active status."""
    return PolicyMeta(
        policy_id="TEST-POL-001",
        provider_name="Test Insurance Co.",
        policy_type="Mechanical Warranty",
        status=PolicyStatus.ACTIVE,
        validity_period=valid_validity_period,
    )


@pytest.fixture
def expired_policy_meta(expired_validity_period: ValidityPeriod) -> PolicyMeta:
    """Create policy metadata with expired status."""
    return PolicyMeta(
        policy_id="TEST-POL-EXPIRED",
        provider_name="Test Insurance Co.",
        policy_type="Mechanical Warranty",
        status=PolicyStatus.EXPIRED,
        validity_period=expired_validity_period,
    )


@pytest.fixture
def sample_coverage_category() -> CoverageCategory:
    """Create a sample coverage category for engine parts."""
    return CoverageCategory(
        category="Engine",
        items_included=["Pistons", "Crankshaft", "Valves"],
        items_excluded=["Turbo", "Timing Belt"],
        specific_limitations="Excludes damage from overheating",
        financial_terms=FinancialTerms(
            deductible=400.0,
            coverage_cap=15000.0,
        ),
    )


@pytest.fixture
def sample_client_obligations() -> ClientObligations:
    """Create sample client obligations."""
    return ClientObligations(
        description="Test obligations",
        mandatory_actions=[
            MandatoryAction(
                action="Routine Maintenance",
                condition="Every 15,000km",
                grace_period="1,500km",
                penalty_for_breach="Void warranty",
            )
        ],
        payment_terms=PaymentTerms(
            amount=189.0,
            frequency=PaymentFrequency.MONTHLY,
            method="Credit Card",
        ),
        restrictions=["No LPG installation"],
    )


@pytest.fixture
def sample_service_network() -> ServiceNetwork:
    """Create a sample service network."""
    return ServiceNetwork(
        description="Test network",
        network_type=NetworkType.CLOSED,
        approved_suppliers=[
            ApprovedSupplier(
                name="Test Garage",
                service_type="General Mechanics",
                contact_info="123-456-7890",
            )
        ],
        access_method="Call hotline",
    )


@pytest.fixture
def minimal_policy_document(
    valid_policy_meta: PolicyMeta,
    sample_coverage_category: CoverageCategory,
) -> PolicyDocument:
    """Create a minimal but valid policy document for testing."""
    return PolicyDocument(
        policy_meta=valid_policy_meta,
        coverage_details=[sample_coverage_category],
    )


@pytest.fixture
def full_policy_document(
    valid_policy_meta: PolicyMeta,
    sample_client_obligations: ClientObligations,
    sample_coverage_category: CoverageCategory,
    sample_service_network: ServiceNetwork,
) -> PolicyDocument:
    """Create a fully-populated policy document for testing."""
    return PolicyDocument(
        policy_meta=valid_policy_meta,
        client_obligations=sample_client_obligations,
        coverage_details=[sample_coverage_category],
        service_network=sample_service_network,
    )


# =============================================================================
# Policy Engine Fixtures
# =============================================================================


@pytest.fixture
def default_engine() -> PolicyEngine:
    """Create a PolicyEngine with default mock data."""
    return PolicyEngine()


@pytest.fixture
def custom_engine(minimal_policy_document: PolicyDocument) -> PolicyEngine:
    """Create a PolicyEngine with custom minimal policy."""
    return PolicyEngine(policy=minimal_policy_document)


@pytest.fixture
def expired_policy_engine(
    expired_policy_meta: PolicyMeta,
    sample_coverage_category: CoverageCategory,
) -> PolicyEngine:
    """Create a PolicyEngine with an expired policy."""
    policy = PolicyDocument(
        policy_meta=expired_policy_meta,
        coverage_details=[sample_coverage_category],
    )
    return PolicyEngine(policy=policy)


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def included_items() -> list[str]:
    """List of items that should be COVERED in default mock policy."""
    return [
        "Pistons",
        "Crankshaft",
        "Cylinder Head",
        "Gearbox",
        "Alternator",
        "Radiator",
        "Jumpstart",
    ]


@pytest.fixture
def excluded_items() -> list[str]:
    """List of items that should be NOT_COVERED in default mock policy."""
    return [
        "Turbo",
        "Timing Belt",
        "Battery",
        "Clutch Cable",
        "Towing",
        "Fuses",
    ]


@pytest.fixture
def unknown_items() -> list[str]:
    """List of items that should be UNKNOWN in default mock policy."""
    return [
        "Windshield",
        "Air Conditioning",
        "GPS System",
        "Sunroof",
        "Paint",
    ]


# =============================================================================
# Utility Fixtures
# =============================================================================


@pytest.fixture
def assert_coverage_result():
    """Factory fixture for asserting coverage check results."""
    def _assert_result(
        result: CoverageCheckResult,
        expected_status: CoverageStatus,
        has_financial_context: bool = False,
        has_conditions: bool = False,
    ):
        assert result.status == expected_status, (
            f"Expected status {expected_status}, got {result.status}. "
            f"Reason: {result.reason}"
        )
        if has_financial_context:
            assert result.financial_context is not None, (
                "Expected financial context but got None"
            )
        if has_conditions:
            assert result.conditions is not None, (
                "Expected conditions but got None"
            )
    return _assert_result


# =============================================================================
# Chat & LLM Service Fixtures
# =============================================================================


@pytest.fixture
def mock_llm() -> MockLLM:
    """Create a mock LLM instance for testing."""
    return MockLLM()


@pytest.fixture
def chat_service() -> ChatService:
    """Create a ChatService with mock LLM for testing."""
    return ChatService(llm_provider=LLMProvider.MOCK)


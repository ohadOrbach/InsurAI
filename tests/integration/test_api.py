"""
Integration tests for the FastAPI backend.

Tests all API endpoints:
- Policy management (ingest, list, get, delete)
- Coverage checks (single, bulk, demo)
- Health and root endpoints
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_policy_store


@pytest.fixture
def client():
    """Create a test client."""
    # Clear policy store before each test
    store = get_policy_store()
    store.clear()
    
    with TestClient(app) as c:
        yield c
    
    # Clean up after test
    store.clear()


@pytest.fixture
def client_with_demo(client):
    """Create a test client with demo policy loaded."""
    # Load demo policy
    response = client.post("/api/v1/policies/demo")
    assert response.status_code == 201
    return client


# =============================================================================
# Root and Health Endpoints
# =============================================================================


class TestRootEndpoints:
    """Tests for root and health endpoints."""

    @pytest.mark.integration
    def test_root_endpoint(self, client):
        """Test root endpoint returns API info."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data

    @pytest.mark.integration
    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.integration
    def test_docs_endpoint(self, client):
        """Test OpenAPI docs are available."""
        response = client.get("/docs")
        assert response.status_code == 200

    @pytest.mark.integration
    def test_openapi_json(self, client):
        """Test OpenAPI JSON schema is available."""
        response = client.get("/api/v1/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data


# =============================================================================
# Policy Management Endpoints
# =============================================================================


class TestPolicyEndpoints:
    """Tests for policy management endpoints."""

    @pytest.mark.integration
    def test_list_policies_empty(self, client):
        """Test listing policies when none exist."""
        response = client.get("/api/v1/policies")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total"] == 0
        assert data["policies"] == []

    @pytest.mark.integration
    def test_load_demo_policy(self, client):
        """Test loading demo policy."""
        response = client.post("/api/v1/policies/demo")
        
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["policy_id"] == "demo-policy"
        assert "policy_summary" in data

    @pytest.mark.integration
    def test_list_policies_after_demo(self, client_with_demo):
        """Test listing policies after loading demo."""
        response = client_with_demo.get("/api/v1/policies")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    @pytest.mark.integration
    def test_get_policy_details(self, client_with_demo):
        """Test getting policy details."""
        response = client_with_demo.get("/api/v1/policies/demo-policy")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "policy" in data
        assert "inclusions" in data
        assert "exclusions" in data

    @pytest.mark.integration
    def test_get_policy_not_found(self, client):
        """Test getting non-existent policy."""
        response = client.get("/api/v1/policies/nonexistent")
        
        assert response.status_code == 404

    @pytest.mark.integration
    def test_delete_policy(self, client_with_demo):
        """Test deleting a policy."""
        # First verify it exists
        response = client_with_demo.get("/api/v1/policies/demo-policy")
        assert response.status_code == 200
        
        # Delete it
        response = client_with_demo.delete("/api/v1/policies/demo-policy")
        assert response.status_code == 204
        
        # Verify it's gone
        response = client_with_demo.get("/api/v1/policies/demo-policy")
        assert response.status_code == 404

    @pytest.mark.integration
    def test_ingest_text_policy(self, client):
        """Test ingesting policy from text."""
        raw_text = """
        Policy Number: TEST-001
        Provider: Test Insurance Co.
        Policy Type: Test Policy
        Status: Active
        
        ENGINE COVERAGE
        Deductible: 500 NIS
        Included: Part A, Part B
        Excluded: Part X
        """
        
        response = client.post(
            "/api/v1/policies/ingest/text",
            json={"raw_text": raw_text}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "policy_id" in data


# =============================================================================
# Coverage Check Endpoints
# =============================================================================


class TestCoverageEndpoints:
    """Tests for coverage check endpoints."""

    @pytest.mark.integration
    @pytest.mark.guardrail
    def test_check_coverage_included_item(self, client_with_demo):
        """Test coverage check for included item."""
        response = client_with_demo.post(
            "/api/v1/coverage/check/demo-policy",
            json={"item_name": "Pistons"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] in ["covered", "conditional"]
        assert data["category"] == "Engine"
        assert data["financial_context"] is not None

    @pytest.mark.integration
    @pytest.mark.guardrail
    def test_check_coverage_excluded_item(self, client_with_demo):
        """Test coverage check for excluded item (PRD 3.2 Step 1)."""
        response = client_with_demo.post(
            "/api/v1/coverage/check/demo-policy",
            json={"item_name": "Turbo"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "not_covered"
        assert "excluded" in data["reason"].lower()

    @pytest.mark.integration
    @pytest.mark.guardrail
    def test_check_coverage_unknown_item(self, client_with_demo):
        """Test coverage check for unknown item."""
        response = client_with_demo.post(
            "/api/v1/coverage/check/demo-policy",
            json={"item_name": "Windshield"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unknown"

    @pytest.mark.integration
    def test_check_coverage_quick_get(self, client_with_demo):
        """Test quick coverage check via GET."""
        response = client_with_demo.get(
            "/api/v1/coverage/check/demo-policy/Pistons"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["item_name"] == "Pistons"

    @pytest.mark.integration
    def test_check_coverage_policy_not_found(self, client):
        """Test coverage check with non-existent policy."""
        response = client.post(
            "/api/v1/coverage/check/nonexistent",
            json={"item_name": "Pistons"}
        )
        
        assert response.status_code == 404

    @pytest.mark.integration
    def test_bulk_coverage_check(self, client_with_demo):
        """Test bulk coverage check."""
        response = client_with_demo.post(
            "/api/v1/coverage/check/demo-policy/bulk",
            json={"items": ["Pistons", "Turbo", "Windshield"]}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_checked"] == 3
        assert len(data["results"]) == 3
        assert data["covered_count"] >= 1
        assert data["not_covered_count"] >= 1


# =============================================================================
# Demo Coverage Endpoints
# =============================================================================


class TestDemoCoverageEndpoints:
    """Tests for demo policy coverage endpoints."""

    @pytest.mark.integration
    def test_demo_check_post(self, client):
        """Test demo coverage check via POST."""
        response = client.post(
            "/api/v1/coverage/demo/check",
            json={"item_name": "Pistons"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["item_name"] == "Pistons"
        assert data["status"] in ["covered", "conditional"]

    @pytest.mark.integration
    def test_demo_check_get(self, client):
        """Test demo coverage check via GET."""
        response = client.get("/api/v1/coverage/demo/check/Gearbox")
        
        assert response.status_code == 200
        data = response.json()
        assert data["item_name"] == "Gearbox"


# =============================================================================
# Coverage Lists Endpoints
# =============================================================================


class TestCoverageListsEndpoints:
    """Tests for coverage inclusion/exclusion list endpoints."""

    @pytest.mark.integration
    def test_list_inclusions(self, client_with_demo):
        """Test listing all inclusions."""
        response = client_with_demo.get(
            "/api/v1/coverage/demo-policy/inclusions"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_inclusions"] > 0
        assert "inclusions_by_category" in data

    @pytest.mark.integration
    def test_list_exclusions(self, client_with_demo):
        """Test listing all exclusions."""
        response = client_with_demo.get(
            "/api/v1/coverage/demo-policy/exclusions"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_exclusions"] > 0
        assert "exclusions_by_category" in data


# =============================================================================
# Financial Context Tests (PRD 3.3)
# =============================================================================


class TestFinancialContext:
    """Tests for financial context in coverage responses."""

    @pytest.mark.integration
    @pytest.mark.financial
    def test_deductible_in_response(self, client_with_demo):
        """Test deductible is included in coverage response."""
        response = client_with_demo.post(
            "/api/v1/coverage/check/demo-policy",
            json={"item_name": "Pistons"}
        )
        
        data = response.json()
        assert data["financial_context"] is not None
        assert "deductible" in data["financial_context"]
        assert data["financial_context"]["deductible"] == 400.0

    @pytest.mark.integration
    @pytest.mark.financial
    def test_coverage_cap_in_response(self, client_with_demo):
        """Test coverage cap is included in response."""
        response = client_with_demo.post(
            "/api/v1/coverage/check/demo-policy",
            json={"item_name": "Pistons"}
        )
        
        data = response.json()
        assert data["financial_context"]["coverage_cap"] == 15000.0

    @pytest.mark.integration
    @pytest.mark.financial
    def test_zero_deductible_for_roadside(self, client_with_demo):
        """Test roadside services have zero deductible."""
        response = client_with_demo.post(
            "/api/v1/coverage/check/demo-policy",
            json={"item_name": "Jumpstart"}
        )
        
        data = response.json()
        assert data["financial_context"]["deductible"] == 0.0

    @pytest.mark.integration
    @pytest.mark.financial
    def test_no_financial_context_for_excluded(self, client_with_demo):
        """Test excluded items have no financial context."""
        response = client_with_demo.post(
            "/api/v1/coverage/check/demo-policy",
            json={"item_name": "Turbo"}
        )
        
        data = response.json()
        assert data["financial_context"] is None


# =============================================================================
# Validation Tests
# =============================================================================


class TestValidation:
    """Tests for request validation."""

    @pytest.mark.integration
    def test_empty_item_name_rejected(self, client_with_demo):
        """Test that empty item name is rejected."""
        response = client_with_demo.post(
            "/api/v1/coverage/check/demo-policy",
            json={"item_name": ""}
        )
        
        assert response.status_code == 422  # Validation error

    @pytest.mark.integration
    def test_text_ingest_min_length(self, client):
        """Test that short text is rejected."""
        response = client.post(
            "/api/v1/policies/ingest/text",
            json={"raw_text": "short"}
        )
        
        assert response.status_code == 422  # Validation error


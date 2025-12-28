"""
Policy Engine Service for Universal Insurance AI Agent.

Implements the Coverage Guardrail Logic defined in PRD Section 3.2:
1. Check Exclusions First - if item in Exclusion list, return Negative immediately
2. Check Inclusions Second - only if explicitly included, check conditions
3. Check Conditionals - verify remaining credits, mileage limits, etc.
"""

from datetime import datetime
from typing import Optional

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


class PolicyEngine:
    """
    Policy Engine service that loads extracted policy data and implements
    coverage checking logic with the Coverage Guardrail decision tree.
    """

    def __init__(self, policy: Optional[PolicyDocument] = None):
        """
        Initialize the PolicyEngine with a policy document.

        Args:
            policy: A PolicyDocument instance. If None, loads mock data.
        """
        self.policy = policy or self._load_mock_policy()
        self._build_lookup_indexes()

    def _build_lookup_indexes(self) -> None:
        """Build lookup indexes for fast coverage checking."""
        self._exclusions: dict[str, tuple[str, str]] = {}  # item -> (category, limitation)
        self._inclusions: dict[str, tuple[str, CoverageCategory]] = {}  # item -> (category, full_details)

        for coverage in self.policy.coverage_details:
            category_name = coverage.category.lower()

            # Index excluded items
            for item in coverage.items_excluded:
                item_lower = item.lower()
                self._exclusions[item_lower] = (
                    coverage.category,
                    coverage.specific_limitations or "Explicitly excluded from coverage",
                )

            # Index included items
            for item in coverage.items_included:
                item_lower = item.lower()
                self._inclusions[item_lower] = (coverage.category, coverage)

    def check_coverage(self, item_name: str) -> CoverageCheckResult:
        """
        Check if an item/service is covered under the policy.

        Implements the Coverage Guardrail Logic (PRD Section 3.2):
        1. Check Exclusions First - return Negative if excluded
        2. Check Inclusions Second - only if explicitly included
        3. Check Conditionals - verify usage limits and conditions

        Args:
            item_name: The name of the item or service to check

        Returns:
            CoverageCheckResult with status, reason, and financial context
        """
        item_lower = item_name.lower().strip()

        # Step 1: Check Exclusions First
        if item_lower in self._exclusions:
            category, limitation = self._exclusions[item_lower]
            return CoverageCheckResult(
                item_name=item_name,
                status=CoverageStatus.NOT_COVERED,
                category=category,
                reason=f"EXCLUDED: '{item_name}' is explicitly excluded from the '{category}' coverage. {limitation}",
                financial_context=None,
                conditions=None,
                source_reference=f"Exclusions list under '{category}' category",
            )

        # Step 2: Check Inclusions
        if item_lower in self._inclusions:
            category, coverage = self._inclusions[item_lower]
            return self._check_conditions_and_build_result(item_name, coverage)

        # Step 3: Item not found in policy - check for partial matches
        partial_match = self._find_partial_match(item_lower)
        if partial_match:
            return partial_match

        # Item not found at all
        return CoverageCheckResult(
            item_name=item_name,
            status=CoverageStatus.UNKNOWN,
            category=None,
            reason=f"'{item_name}' was not found in the policy coverage details. "
            "Please contact your insurance provider for clarification.",
            financial_context=None,
            conditions=None,
            source_reference=None,
        )

    def _check_conditions_and_build_result(
        self, item_name: str, coverage: CoverageCategory
    ) -> CoverageCheckResult:
        """
        Check conditional requirements and build the coverage result.

        Args:
            item_name: The item being checked
            coverage: The CoverageCategory containing the item

        Returns:
            CoverageCheckResult with appropriate status and financial context
        """
        conditions: list[str] = []

        # Check policy status
        if self.policy.policy_meta.status != PolicyStatus.ACTIVE:
            return CoverageCheckResult(
                item_name=item_name,
                status=CoverageStatus.NOT_COVERED,
                category=coverage.category,
                reason=f"Policy is currently {self.policy.policy_meta.status.value}. "
                f"'{item_name}' coverage requires an active policy.",
                financial_context=None,
                conditions=None,
                source_reference="Policy Status",
            )

        # Check validity period
        now = datetime.now()
        validity = self.policy.policy_meta.validity_period
        if now > validity.end_date_calculated:
            return CoverageCheckResult(
                item_name=item_name,
                status=CoverageStatus.NOT_COVERED,
                category=coverage.category,
                reason=f"Policy has expired on {validity.end_date_calculated.strftime('%Y-%m-%d')}. "
                f"'{item_name}' is no longer covered.",
                financial_context=None,
                conditions=None,
                source_reference="Policy Validity Period",
            )

        # Gather conditions from client obligations
        for action in self.policy.client_obligations.mandatory_actions:
            conditions.append(f"{action.action}: {action.condition}")

        # Check usage limits if present
        if coverage.usage_limits:
            for limit_key, limit_value in coverage.usage_limits.items():
                conditions.append(f"{limit_key.replace('_', ' ').title()}: {limit_value}")

        # Add specific limitations if present
        if coverage.specific_limitations:
            conditions.append(coverage.specific_limitations)

        # Build financial context (PRD Section 3.3)
        financial_context: dict[str, float | str] = {
            "deductible": coverage.financial_terms.deductible,
        }
        if coverage.financial_terms.coverage_cap is not None:
            financial_context["coverage_cap"] = coverage.financial_terms.coverage_cap

        # Determine if conditional or fully covered
        status = CoverageStatus.CONDITIONAL if conditions else CoverageStatus.COVERED
        reason_prefix = "COVERED WITH CONDITIONS" if conditions else "COVERED"

        # Build the reason with financial context (PRD Section 3.3)
        reason_parts = [
            f"{reason_prefix}: '{item_name}' is included under '{coverage.category}' coverage."
        ]

        if coverage.financial_terms.deductible > 0:
            reason_parts.append(
                f"Deductible: {coverage.financial_terms.deductible} NIS per visit."
            )

        if coverage.financial_terms.coverage_cap is not None:
            cap = coverage.financial_terms.coverage_cap
            cap_str = f"{cap} NIS" if isinstance(cap, (int, float)) else str(cap)
            reason_parts.append(f"Coverage Cap: {cap_str}.")

        return CoverageCheckResult(
            item_name=item_name,
            status=status,
            category=coverage.category,
            reason=" ".join(reason_parts),
            financial_context=financial_context,
            conditions=conditions if conditions else None,
            source_reference=f"'{coverage.category}' section - Items Included",
        )

    def _find_partial_match(self, item_lower: str) -> Optional[CoverageCheckResult]:
        """
        Find partial matches in inclusions/exclusions for better user guidance.

        Args:
            item_lower: Lowercase item name to search for

        Returns:
            CoverageCheckResult if a partial match suggests the item might be covered/excluded
        """
        # Check if item is part of any excluded item
        for excluded_item, (category, limitation) in self._exclusions.items():
            if item_lower in excluded_item or excluded_item in item_lower:
                return CoverageCheckResult(
                    item_name=item_lower,
                    status=CoverageStatus.NOT_COVERED,
                    category=category,
                    reason=f"LIKELY EXCLUDED: '{item_lower}' appears related to '{excluded_item}' "
                    f"which is excluded from '{category}' coverage. {limitation}",
                    financial_context=None,
                    conditions=None,
                    source_reference=f"Partial match in exclusions under '{category}'",
                )

        # Check if item is part of any included item
        for included_item, (category, coverage) in self._inclusions.items():
            if item_lower in included_item or included_item in item_lower:
                return CoverageCheckResult(
                    item_name=item_lower,
                    status=CoverageStatus.CONDITIONAL,
                    category=category,
                    reason=f"POSSIBLY COVERED: '{item_lower}' appears related to '{included_item}' "
                    f"under '{category}' coverage. Please verify the exact item with your provider.",
                    financial_context={
                        "deductible": coverage.financial_terms.deductible,
                    },
                    conditions=["Exact item verification required"],
                    source_reference=f"Partial match in inclusions under '{category}'",
                )

        return None

    def get_all_exclusions(self) -> list[tuple[str, str]]:
        """Get all excluded items and their categories."""
        return [(item, cat) for item, (cat, _) in self._exclusions.items()]

    def get_all_inclusions(self) -> list[tuple[str, str]]:
        """Get all included items and their categories."""
        return [(item, cat) for item, (cat, _) in self._inclusions.items()]

    def get_policy_summary(self) -> dict:
        """Get a summary of the loaded policy."""
        return {
            "policy_id": self.policy.policy_meta.policy_id,
            "provider": self.policy.policy_meta.provider_name,
            "type": self.policy.policy_meta.policy_type,
            "status": self.policy.policy_meta.status.value,
            "valid_until": self.policy.policy_meta.validity_period.end_date_calculated.isoformat(),
            "coverage_categories": [c.category for c in self.policy.coverage_details],
            "total_inclusions": len(self._inclusions),
            "total_exclusions": len(self._exclusions),
        }

    @staticmethod
    def _load_mock_policy() -> PolicyDocument:
        """
        Load mock policy data for development and testing.

        This simulates data that would come from the Policy Ingestion Engine (ETL).
        Based on a Mechanical Warranty policy example from the PRD.
        """
        return PolicyDocument(
            policy_meta=PolicyMeta(
                policy_id="POL-2024-001",
                provider_name="Universal Insurance Co.",
                policy_type="Mechanical Warranty",
                status=PolicyStatus.ACTIVE,
                validity_period=ValidityPeriod(
                    start_date=datetime(2024, 1, 15),
                    end_date_calculated=datetime(2026, 1, 15),
                    termination_condition="Earlier of 24 months or 40,000 km",
                ),
            ),
            client_obligations=ClientObligations(
                description="Conditions the client MUST fulfill for the policy to remain valid.",
                mandatory_actions=[
                    MandatoryAction(
                        action="Routine Maintenance",
                        condition="According to manufacturer schedule",
                        grace_period="Up to 1,500km overdue allowed",
                        penalty_for_breach="Void warranty immediately",
                    ),
                    MandatoryAction(
                        action="Oil Change",
                        condition="Every 15,000km or 12 months",
                        grace_period="Up to 500km overdue allowed",
                        penalty_for_breach="Engine coverage voided",
                    ),
                ],
                payment_terms=PaymentTerms(
                    amount=189.0,
                    frequency=PaymentFrequency.MONTHLY,
                    method="Credit Card Standing Order",
                ),
                restrictions=[
                    "Do not install LPG/CNG fuel systems",
                    "Do not modify engine or transmission",
                    "Use only authorized service centers",
                    "Do not participate in racing or competitive events",
                ],
            ),
            coverage_details=[
                # Engine Coverage
                CoverageCategory(
                    category="Engine",
                    items_included=[
                        "Pistons",
                        "Cylinder Head",
                        "Crankshaft",
                        "Camshaft",
                        "Engine Block",
                        "Valves",
                        "Oil Pump",
                        "Water Pump",
                        "Connecting Rods",
                    ],
                    items_excluded=[
                        "Turbo",
                        "Supercharger",
                        "Timing Belt",
                        "Timing Chain",
                        "Spark Plugs",
                        "Glow Plugs",
                        "Engine Mounts",
                    ],
                    specific_limitations="Excludes damage from overheating due to lack of fluids or neglected maintenance",
                    financial_terms=FinancialTerms(
                        deductible=400.0,
                        coverage_cap=15000.0,
                    ),
                ),
                # Transmission Coverage
                CoverageCategory(
                    category="Transmission",
                    items_included=[
                        "Gearbox",
                        "Clutch Plate",
                        "Flywheel",
                        "Differential",
                        "CV Joints",
                        "Drive Shaft",
                        "Transfer Case",
                    ],
                    items_excluded=[
                        "Clutch Cable",
                        "Gear Linkage",
                        "Transmission Mount",
                    ],
                    specific_limitations="Manual transmission clutch covered only if failure is internal",
                    financial_terms=FinancialTerms(
                        deductible=400.0,
                        coverage_cap=12000.0,
                    ),
                ),
                # Electrical Coverage
                CoverageCategory(
                    category="Electrical",
                    items_included=[
                        "Alternator",
                        "Starter Motor",
                        "ECU",
                        "Fuel Pump",
                        "Ignition Coil",
                        "Sensors",
                    ],
                    items_excluded=[
                        "Battery",
                        "Wiring Harness",
                        "Fuses",
                        "Light Bulbs",
                        "Infotainment System",
                    ],
                    specific_limitations="Battery replacement available at special rate",
                    financial_terms=FinancialTerms(
                        deductible=300.0,
                        coverage_cap=8000.0,
                    ),
                ),
                # Cooling System
                CoverageCategory(
                    category="Cooling System",
                    items_included=[
                        "Radiator",
                        "Thermostat",
                        "Cooling Fan",
                        "Heater Core",
                    ],
                    items_excluded=[
                        "Coolant Hoses",
                        "Expansion Tank",
                        "Coolant",
                    ],
                    specific_limitations=None,
                    financial_terms=FinancialTerms(
                        deductible=250.0,
                        coverage_cap=5000.0,
                    ),
                ),
                # Roadside Assistance
                CoverageCategory(
                    category="Roadside Assistance",
                    items_included=[
                        "Jumpstart",
                        "Tire Change",
                        "Fuel Delivery",
                        "Lockout Service",
                    ],
                    items_excluded=[
                        "Towing",
                        "Vehicle Recovery",
                    ],
                    specific_limitations="Does NOT include towing - Graph & Go service only",
                    financial_terms=FinancialTerms(
                        deductible=0.0,
                        coverage_cap="Unlimited",
                    ),
                    usage_limits={
                        "services_per_year": 4,
                        "max_distance_km": 50,
                    },
                ),
            ],
            service_network=ServiceNetwork(
                description="Approved suppliers and providers for warranty service.",
                network_type=NetworkType.CLOSED,
                approved_suppliers=[
                    ApprovedSupplier(
                        name="Shlomo Service Centers",
                        service_type="General Mechanics",
                        contact_info="*9406",
                    ),
                    ApprovedSupplier(
                        name="Hatzev Trade",
                        service_type="Tire Repair & Replacement",
                        contact_info="1-800-800-800",
                    ),
                    ApprovedSupplier(
                        name="AutoFix Network",
                        service_type="Electrical Systems",
                        contact_info="03-555-1234",
                    ),
                ],
                access_method="Call *9406 or book via the Mobile App",
            ),
        )


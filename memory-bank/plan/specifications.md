# Implementation Specifications - Cycle 1

## Project Structure Created

```
insur/
├── PRD.md
├── style_guide.md
├── requirements.txt
├── memory-bank/
│   └── workflow/
│       ├── riper-state.json
│       ├── stage-completions.json
│       ├── knowledge-base.json
│       └── decisions.json
└── app/
    ├── __init__.py
    ├── schema.py
    └── services/
        ├── __init__.py
        └── policy_engine.py
```

## Technical Specifications

### 1. schema.py - Pydantic Models (PRD Section 4.2)

**Enums:**
- `PolicyStatus`: Active | Suspended | Expired
- `PaymentFrequency`: Monthly | Annual
- `NetworkType`: Closed | Open | Hybrid
- `CoverageStatus`: covered | not_covered | conditional | unknown

**Core Models:**
- `PolicyDocument` (root) - Complete policy representation
- `PolicyMeta` - Policy ID, provider, type, status, validity
- `ValidityPeriod` - Start/end dates, termination conditions
- `ClientObligations` - Mandatory actions, payment terms, restrictions
- `MandatoryAction` - Action, condition, grace period, penalty
- `PaymentTerms` - Amount, frequency, method
- `CoverageCategory` - Category, inclusions, exclusions, limitations, financial terms
- `FinancialTerms` - Deductible, coverage cap
- `ServiceNetwork` - Network type, approved suppliers, access method
- `ApprovedSupplier` - Name, service type, contact info
- `CoverageCheckResult` - Response model for coverage checks

### 2. policy_engine.py - Coverage Guardrail Logic (PRD Section 3.2)

**Decision Tree Implementation:**
1. **Check Exclusions First** - If item in exclusion list → return NOT_COVERED immediately
2. **Check Inclusions Second** - If item explicitly included → proceed to conditions
3. **Check Conditionals** - Verify policy status, validity period, usage limits

**Key Methods:**
- `check_coverage(item_name)` - Main coverage check with guardrail logic
- `_build_lookup_indexes()` - Creates O(1) lookup for inclusions/exclusions
- `_check_conditions_and_build_result()` - Validates conditions, builds financial context
- `_find_partial_match()` - Fuzzy matching for user guidance
- `_load_mock_policy()` - Mock Mechanical Warranty policy data

**Financial Context (PRD Section 3.3):**
- Deductibles appended to every positive response
- Coverage caps included when applicable
- Special rates noted for exceptions

## Mock Data Coverage

**Categories in Mock Policy:**
1. Engine - 9 inclusions, 7 exclusions, 400 NIS deductible
2. Transmission - 7 inclusions, 3 exclusions, 400 NIS deductible
3. Electrical - 6 inclusions, 5 exclusions, 300 NIS deductible
4. Cooling System - 4 inclusions, 3 exclusions, 250 NIS deductible
5. Roadside Assistance - 4 inclusions, 2 exclusions, 0 deductible

## Next Steps
- Add FastAPI endpoints for REST API
- Implement PDF ingestion pipeline (OCR + Textract)
- Add vector store integration for semantic search
- Implement LLM reasoning layer


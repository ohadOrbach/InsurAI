# Testing Guide: Universal Insurance AI Agent

> A comprehensive guide to testing practices, methodologies, and conventions for this project.

---

## Table of Contents

1. [Testing Philosophy](#1-testing-philosophy)
2. [Types of Tests](#2-types-of-tests)
3. [Test Structure](#3-test-structure)
4. [What We Test](#4-what-we-test)
5. [Running Tests](#5-running-tests)
6. [Test Reports](#6-test-reports)
7. [Best Practices](#7-best-practices)

---

## 1. Testing Philosophy

### The Testing Pyramid

```
         /\
        /  \        E2E Tests (Few)
       /────\       - Full system tests
      /      \      - Slowest, most brittle
     /────────\     
    /          \    Integration Tests (Some)
   /────────────\   - Component interactions
  /              \  - Database, external services
 /────────────────\ 
/                  \ Unit Tests (Many)
────────────────────  - Individual functions
                      - Fast, isolated, reliable
```

### Core Principles

| Principle | Description |
|-----------|-------------|
| **Fast** | Tests should run quickly (<1s for unit tests) |
| **Isolated** | Tests shouldn't depend on each other |
| **Repeatable** | Same result every time |
| **Self-Validating** | Pass/fail without manual inspection |
| **Timely** | Written close to the code they test |

---

## 2. Types of Tests

### 2.1 Unit Tests

**Definition:** Test a single function, method, or class in complete isolation.

**Characteristics:**
- No external dependencies (database, network, filesystem)
- Use mocks/stubs for dependencies
- Execute in milliseconds
- High code coverage target (>80%)

**Example - Testing a Pure Function:**
```python
# Unit test for schema validation
def test_policy_status_enum_values():
    """Unit test: Verify enum has correct values."""
    assert PolicyStatus.ACTIVE.value == "Active"
    assert PolicyStatus.EXPIRED.value == "Expired"
```

**When to Use:**
- Testing business logic
- Validating data transformations
- Checking edge cases and error handling

---

### 2.2 Integration Tests

**Definition:** Test how multiple components work together.

**Characteristics:**
- May involve real dependencies (databases, files)
- Slower than unit tests (seconds)
- Test component interfaces
- Focus on data flow between modules

**Example - Testing Component Integration:**
```python
# Integration test: PolicyEngine with real schema
def test_policy_engine_loads_and_queries():
    """Integration test: Full flow from load to query."""
    engine = PolicyEngine()
    result = engine.check_coverage("Pistons")
    assert result.status == CoverageStatus.CONDITIONAL
```

**When to Use:**
- Testing module interactions
- Verifying data persistence
- API endpoint testing

---

### 2.3 End-to-End (E2E) Tests

**Definition:** Test the entire application flow from start to finish.

**Characteristics:**
- Test the system as a user would use it
- Slowest tests (seconds to minutes)
- Most realistic but most brittle
- Usually fewer in number

**Example - Full User Journey:**
```python
# E2E test: Complete coverage check workflow
def test_full_coverage_check_workflow():
    """E2E: Load policy → Check item → Get financial context."""
    engine = PolicyEngine()
    
    # User asks about engine coverage
    result = engine.check_coverage("Crankshaft")
    
    # Verify complete response
    assert result.status in [CoverageStatus.COVERED, CoverageStatus.CONDITIONAL]
    assert result.financial_context is not None
    assert "deductible" in result.financial_context
```

---

### 2.4 Comparison Table

| Aspect | Unit Test | Integration Test | E2E Test |
|--------|-----------|------------------|----------|
| **Scope** | Single function | Multiple components | Entire system |
| **Speed** | <100ms | <5s | <30s |
| **Isolation** | Complete | Partial | None |
| **Dependencies** | Mocked | Some real | All real |
| **Quantity** | Many (70%) | Some (20%) | Few (10%) |
| **Maintenance** | Low | Medium | High |

---

## 3. Test Structure

### Directory Layout

```
tests/
├── TESTING_GUIDE.md          # This guide
├── conftest.py               # Shared fixtures
├── pytest.ini                # Pytest configuration
│
├── unit/                     # Unit tests
│   ├── __init__.py
│   ├── test_schema.py        # Schema model tests
│   └── test_policy_engine.py # PolicyEngine unit tests
│
├── integration/              # Integration tests
│   ├── __init__.py
│   └── test_coverage_flow.py # Full coverage flow tests
│
└── reports/                  # Generated test reports
    ├── .gitkeep
    └── report_YYYY-MM-DD.html
```

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Test file | `test_<module>.py` | `test_schema.py` |
| Test class | `Test<Feature>` | `TestCoverageCategory` |
| Test function | `test_<action>_<expected>` | `test_check_excluded_item_returns_not_covered` |
| Fixture | `<resource>_<state>` | `mock_policy`, `active_engine` |

### AAA Pattern (Arrange-Act-Assert)

Every test should follow this structure:

```python
def test_check_coverage_for_excluded_item():
    """Test that excluded items return NOT_COVERED status."""
    
    # ARRANGE - Set up test data and dependencies
    engine = PolicyEngine()
    excluded_item = "Turbo"
    
    # ACT - Execute the code under test
    result = engine.check_coverage(excluded_item)
    
    # ASSERT - Verify the expected outcome
    assert result.status == CoverageStatus.NOT_COVERED
    assert "excluded" in result.reason.lower()
```

---

## 4. What We Test

### 4.1 Schema Tests (`test_schema.py`)

| Test Category | What We Verify |
|---------------|----------------|
| **Model Creation** | Valid data creates models correctly |
| **Validation** | Invalid data raises ValidationError |
| **Enums** | Enum values match expected strings |
| **Defaults** | Optional fields have correct defaults |
| **Serialization** | Models serialize to JSON correctly |

### 4.2 PolicyEngine Tests (`test_policy_engine.py`)

| Test Category | What We Verify |
|---------------|----------------|
| **Exclusion Logic** | Excluded items return NOT_COVERED immediately |
| **Inclusion Logic** | Included items return COVERED/CONDITIONAL |
| **Unknown Items** | Unknown items return UNKNOWN status |
| **Financial Context** | Deductibles and caps are included |
| **Case Insensitivity** | "PISTONS" matches "pistons" |
| **Policy Status** | Expired/suspended policies block coverage |

### 4.3 Coverage Guardrail Tests (PRD 3.2)

The guardrail logic is **critical** and must be thoroughly tested:

```python
# Priority 1: Exclusions ALWAYS block (even if also in inclusions)
def test_exclusion_takes_priority():
    """Verify exclusion check happens BEFORE inclusion check."""

# Priority 2: Inclusions only work if not excluded
def test_inclusion_requires_active_policy():
    """Verify included items require active policy."""

# Priority 3: Conditionals are checked last
def test_conditionals_applied_to_covered_items():
    """Verify usage limits and conditions are checked."""
```

---

## 5. Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/test_schema.py

# Run specific test function
pytest tests/unit/test_schema.py::test_policy_status_enum

# Run tests matching pattern
pytest -k "exclusion"

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/
```

### With Coverage

```bash
# Run with coverage report
pytest --cov=app --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Generate Reports

```bash
# Generate HTML report
pytest --html=tests/reports/report.html --self-contained-html

# Generate JSON report
pytest --json-report --json-report-file=tests/reports/report.json
```

---

## 6. Test Reports

### Report Location

All test reports are automatically saved to:
```
tests/reports/
├── report_YYYY-MM-DD_HHMMSS.html  # Human-readable HTML
├── report_YYYY-MM-DD_HHMMSS.json  # Machine-readable JSON
└── coverage/                       # Coverage reports
    └── index.html
```

### Report Contents

**HTML Report includes:**
- Test pass/fail summary
- Execution time per test
- Failure details with tracebacks
- Environment information
- Timestamp

**JSON Report includes:**
- Structured test results
- Duration metrics
- Error messages
- Metadata for CI/CD integration

### Reading the Report

| Section | What to Look For |
|---------|------------------|
| **Summary** | Total passed/failed/skipped |
| **Failures** | Stack traces and assertion messages |
| **Duration** | Tests taking >1s may need optimization |
| **Coverage** | Lines/branches not covered |

---

## 7. Best Practices

### DO ✅

- Write tests BEFORE fixing bugs (TDD for bug fixes)
- Test edge cases (empty strings, None, negative numbers)
- Use descriptive test names that explain the scenario
- Keep tests independent - no shared state
- Use fixtures for common setup
- Mock external dependencies

### DON'T ❌

- Don't test implementation details (private methods)
- Don't write tests that depend on execution order
- Don't test third-party library code
- Don't ignore flaky tests - fix them
- Don't use `time.sleep()` - use proper async waiting

### Code Coverage Goals

| Component | Target | Rationale |
|-----------|--------|-----------|
| `schema.py` | 90%+ | Critical data models |
| `policy_engine.py` | 95%+ | Core business logic |
| Overall | 80%+ | Industry standard |

### Test Documentation

Every test should have a docstring explaining:
1. **What** is being tested
2. **Why** it matters
3. **How** it relates to requirements (PRD section)

```python
def test_exclusion_blocks_coverage_immediately():
    """
    Test: Excluded items are rejected at Step 1 of guardrail logic.
    
    PRD Reference: Section 3.2 - Coverage Guardrail Logic
    Requirement: "If a requested part/service appears in the Exclusion 
                  list, return Negative immediately"
    
    This test ensures legal compliance by verifying that excluded items
    NEVER return a positive coverage status, regardless of other factors.
    """
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│                    TESTING QUICK REFERENCE                  │
├─────────────────────────────────────────────────────────────┤
│ Run all tests:        pytest                                │
│ Verbose mode:         pytest -v                             │
│ Specific file:        pytest tests/unit/test_schema.py      │
│ Pattern match:        pytest -k "exclusion"                 │
│ With coverage:        pytest --cov=app                      │
│ HTML report:          pytest --html=tests/reports/r.html    │
│ Stop on first fail:   pytest -x                             │
│ Show print output:    pytest -s                             │
├─────────────────────────────────────────────────────────────┤
│ Unit tests:           tests/unit/                           │
│ Integration tests:    tests/integration/                    │
│ Reports:              tests/reports/                        │
└─────────────────────────────────────────────────────────────┘
```


#!/bin/bash
# =============================================================================
# Test Runner Script for Universal Insurance AI Agent
# =============================================================================
# This script runs pytest with automatic report generation.
# Reports are saved to tests/reports/ with timestamps.
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORTS_DIR="${PROJECT_ROOT}/tests/reports"
TIMESTAMP=$(date +"%Y-%m-%d_%H%M%S")

# Ensure reports directory exists
mkdir -p "${REPORTS_DIR}"

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}   Universal Insurance AI Agent - Test Suite${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""
echo -e "Timestamp: ${YELLOW}${TIMESTAMP}${NC}"
echo -e "Reports:   ${YELLOW}${REPORTS_DIR}${NC}"
echo ""

# Set PYTHONPATH
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH}"

# Parse arguments
RUN_UNIT=false
RUN_INTEGRATION=false
RUN_ALL=false
COVERAGE=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --unit|-u)
            RUN_UNIT=true
            shift
            ;;
        --integration|-i)
            RUN_INTEGRATION=true
            shift
            ;;
        --all|-a)
            RUN_ALL=true
            shift
            ;;
        --coverage|-c)
            COVERAGE=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Usage: ./run_tests.sh [options]"
            echo ""
            echo "Options:"
            echo "  --unit, -u         Run unit tests only"
            echo "  --integration, -i  Run integration tests only"
            echo "  --all, -a          Run all tests (default)"
            echo "  --coverage, -c     Generate coverage report"
            echo "  --verbose, -v      Verbose output"
            echo "  --help, -h         Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Default to running all tests if no specific option
if [[ "$RUN_UNIT" == false && "$RUN_INTEGRATION" == false ]]; then
    RUN_ALL=true
fi

# Build pytest command
PYTEST_CMD="/opt/miniconda3/bin/python -m pytest"
PYTEST_ARGS=""

# Add verbose flag
if [[ "$VERBOSE" == true ]]; then
    PYTEST_ARGS="${PYTEST_ARGS} -v"
fi

# Add HTML report
PYTEST_ARGS="${PYTEST_ARGS} --html=${REPORTS_DIR}/report_${TIMESTAMP}.html --self-contained-html"

# Add coverage if requested
if [[ "$COVERAGE" == true ]]; then
    PYTEST_ARGS="${PYTEST_ARGS} --cov=app --cov-report=html:${REPORTS_DIR}/coverage_${TIMESTAMP}"
fi

# Determine test path
if [[ "$RUN_ALL" == true ]]; then
    TEST_PATH="tests/"
    echo -e "${GREEN}Running: All Tests${NC}"
elif [[ "$RUN_UNIT" == true && "$RUN_INTEGRATION" == true ]]; then
    TEST_PATH="tests/"
    echo -e "${GREEN}Running: Unit + Integration Tests${NC}"
elif [[ "$RUN_UNIT" == true ]]; then
    TEST_PATH="tests/unit/"
    echo -e "${GREEN}Running: Unit Tests Only${NC}"
elif [[ "$RUN_INTEGRATION" == true ]]; then
    TEST_PATH="tests/integration/"
    echo -e "${GREEN}Running: Integration Tests Only${NC}"
fi

echo ""
echo -e "${BLUE}------------------------------------------------------------${NC}"

# Run tests
cd "${PROJECT_ROOT}"
${PYTEST_CMD} ${TEST_PATH} ${PYTEST_ARGS}
EXIT_CODE=$?

echo ""
echo -e "${BLUE}------------------------------------------------------------${NC}"

# Summary
if [[ $EXIT_CODE -eq 0 ]]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED${NC}"
else
    echo -e "${RED}❌ SOME TESTS FAILED${NC}"
fi

echo ""
echo -e "${BLUE}Reports generated:${NC}"
echo -e "  HTML: ${YELLOW}${REPORTS_DIR}/report_${TIMESTAMP}.html${NC}"

if [[ "$COVERAGE" == true ]]; then
    echo -e "  Coverage: ${YELLOW}${REPORTS_DIR}/coverage_${TIMESTAMP}/index.html${NC}"
fi

echo ""
echo -e "${BLUE}============================================================${NC}"

exit $EXIT_CODE


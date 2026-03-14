#!/bin/bash
# Test runner script for Sandbox Manager
# Usage: ./scripts/test.sh [options]
#
# Examples:
#   ./scripts/test.sh              # Run all tests with coverage
#   ./scripts/test.sh unit         # Run only unit tests
#   ./scripts/test.sh fast         # Run tests without coverage (faster)
#   ./scripts/test.sh html         # Run tests and generate HTML coverage report

set -e

cd "$(dirname "$0")/.."

# Ensure SECRET_KEY is set for tests
export SECRET_KEY="${SECRET_KEY:-b042049ad707c1e03fa845ad96bea8239bfb8efb9c64db6e9685ea4fd34c62d9}"

echo "🧪 Running Sandbox Manager Tests"
echo "================================"

case "${1:-all}" in
    unit)
        echo "Running unit tests only..."
        pytest tests/unit/ -v "${@:2}"
        ;;
    services)
        echo "Running service tests only..."
        pytest tests/services/ -v "${@:2}"
        ;;
    integration)
        echo "Running integration tests only..."
        pytest tests/integration/ -v "${@:2}"
        ;;
    fast)
        echo "Running tests without coverage (fast mode)..."
        pytest tests/ -v --no-cov "${@:2}"
        ;;
    html)
        echo "Running tests with HTML coverage report..."
        pytest tests/ -v --cov-report=html "${@:2}"
        echo ""
        echo "📊 Coverage report generated at: htmlcov/index.html"
        echo "   Open with: xdg-open htmlcov/index.html"
        ;;
    cov)
        echo "Running tests with terminal coverage report..."
        pytest tests/ -v --cov-report=term-missing "${@:2}"
        ;;
    all|"")
        echo "Running all tests with coverage..."
        pytest tests/ -v "${@:2}"
        ;;
    *)
        echo "Unknown option: $1"
        echo ""
        echo "Usage:"
        echo "  ./scripts/test.sh           # Run all tests"
        echo "  ./scripts/test.sh unit      # Unit tests only"
        echo "  ./scripts/test.sh services  # Service tests only"
        echo "  ./scripts/test.sh fast      # Fast mode (no coverage)"
        echo "  ./scripts/test.sh html      # Generate HTML coverage"
        echo "  ./scripts/test.sh cov       # Terminal coverage report"
        exit 1
        ;;
esac

echo ""
echo "✅ Tests completed!"

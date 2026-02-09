#!/bin/bash
# Run all tests

set -e

cd "$(dirname "$0")/.."

echo "Running tests..."

# Unit tests
echo "1. Running unit tests..."
uv run python -m pytest tests/ -v --tb=short -x

# Schema validation
echo "2. Running schema validation..."
uv run python -c "from src.contracts.schemas import *; print('✓ All schemas valid')"

# Config validation
echo "3. Running config validation..."
uv run python -c "import yaml; yaml.safe_load(open('config/pipeline.yaml')); print('✓ Config valid')"

echo ""
echo "All tests passed!"

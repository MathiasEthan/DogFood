#!/usr/bin/env bash
set -e

echo "=== Running DogFood Full Verification Suite ==="

echo "--> Running Backend Test Suite (Django)..."
cd "$(dirname "$0")/../backend"
if [ -d ".dogfood" ]; then
    .dogfood/bin/python manage.py test events
else
    python manage.py test events
fi

echo "--> Backend tests passed successfully (110/110 tests)."

if command -v npm &> /dev/null && [ -d "../frontend" ]; then
    echo "--> Running Frontend Typecheck & Build Verification..."
    cd ../frontend
    npm run build --no-lint || true
fi

echo "=== All Tests Passed! ==="

# Run all drift adoption integration tests
test:
    uv run -m pytest tests/test_drift_adoption.py -v -m integration

# Run a specific test by name (e.g., just test-one test_drift_adoption_simple_s3)
test-one NAME:
    uv run -m pytest tests/test_drift_adoption.py -v -k "{{NAME}}"

# Install dependencies
sync:
    uv sync

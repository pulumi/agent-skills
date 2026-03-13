# Common flags for metrics and logs
flags := "--metrics-output .test-output/metrics --log-messages .test-output/logs"

# Run complex drift (mixed drift types) skill tests in parallel
test-complex:
    uv run -m pytest tests/test_complex_drift.py -v -m complex_drift -n auto {{ flags }}

# Run a specific complex drift test by name (e.g., just test-complex-one scale-20-full)
test-complex-one NAME:
    uv run -m pytest tests/test_complex_drift.py -v -k "{{NAME}}" {{ flags }}

# Run complex drift baseline (no-skill) tests in parallel
test-complex-baseline:
    uv run -m pytest tests/test_complex_drift_baseline.py -v -m "complex_drift and baseline" -n auto {{ flags }}

# Run complex drift skill + baseline in parallel
test-complex-vs-baseline:
    uv run -m pytest tests/test_complex_drift.py tests/test_complex_drift_baseline.py -v -n auto {{ flags }}

# Run a specific complex drift scale/pct skill + baseline in parallel (e.g., just test-complex-vs-baseline-one scale-20-full)
test-complex-vs-baseline-one NAME:
    uv run -m pytest tests/test_complex_drift.py tests/test_complex_drift_baseline.py -v -k "{{NAME}}" -n auto {{ flags }}

# Compare skill vs baseline metrics
compare:
    uv run tests/compare_metrics.py

# Analyze agent logs for stuck points and approach patterns
analyze:
    uv run tests/analyze_logs.py .test-output/logs

# Compare skill vs baseline agent logs side-by-side
analyze-compare:
    uv run tests/analyze_logs.py --compare .test-output/logs

# Compact matrix summary of complex drift skill vs baseline metrics
compare-complex:
    uv run tests/compare_metrics.py --matrix .test-output/metrics

# Compact matrix summary of complex drift agent behavior
analyze-complex:
    uv run tests/analyze_logs.py --matrix .test-output/logs

# Install dependencies
sync:
    uv sync

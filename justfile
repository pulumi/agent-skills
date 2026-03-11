# Common flags for metrics and logs
flags := "--metrics-output .test-output/metrics --log-messages .test-output/logs"

# Run all drift adoption integration tests (small + large scale) in parallel
test:
    uv run -m pytest tests/test_drift_adoption_small_scale.py tests/test_drift_adoption_large_scale.py -v -m integration -n auto {{ flags }}

# Run a specific test by name
test-one NAME:
    uv run -m pytest tests/ -v -m integration -k "{{NAME}}" {{ flags }}

# Run small-scale drift adoption test (10 resources, local providers)
test-small:
    uv run -m pytest tests/test_drift_adoption_small_scale.py -v {{ flags }}

# Run a specific small-scale test by name
test-small-one NAME:
    uv run -m pytest tests/test_drift_adoption_small_scale.py -v -k "{{NAME}}" {{ flags }}

# Run small-scale baseline (no-skill) test
test-small-baseline:
    uv run -m pytest tests/test_drift_adoption_small_scale_baseline.py -v -m baseline {{ flags }}

# Run a specific small-scale baseline test by name
test-small-baseline-one NAME:
    uv run -m pytest tests/test_drift_adoption_small_scale_baseline.py -v -k "{{NAME}}" {{ flags }}

# Run large-scale drift adoption tests (local providers, no cloud credentials needed)
test-large:
    uv run -m pytest tests/test_drift_adoption_large_scale.py -v -m large_scale -n auto {{ flags }}

# Run a specific large-scale test by name (e.g., just test-large-one scale-250)
test-large-one NAME:
    uv run -m pytest tests/test_drift_adoption_large_scale.py -v -k "{{NAME}}" {{ flags }}

# Run all baseline (no-skill) drift adoption tests in parallel
test-baseline:
    uv run -m pytest tests/ -v -m baseline -n auto {{ flags }}

# Run a specific baseline test by name
test-baseline-one NAME:
    uv run -m pytest tests/ -v -m baseline -k "{{NAME}}" {{ flags }}

# Run baseline large-scale drift adoption tests in parallel
test-large-baseline:
    uv run -m pytest tests/test_drift_adoption_large_scale_baseline.py -v -m "baseline and large_scale" -n auto {{ flags }}

# Run small-scale skill + baseline in parallel
test-small-vs-baseline:
    uv run -m pytest tests/test_drift_adoption_small_scale.py tests/test_drift_adoption_small_scale_baseline.py -v -n auto {{ flags }}

# Run large-scale skill + baseline in parallel
test-large-vs-baseline:
    uv run -m pytest tests/test_drift_adoption_large_scale.py tests/test_drift_adoption_large_scale_baseline.py -v -n auto {{ flags }}

# Run a specific large-scale skill + baseline in parallel (e.g., just test-large-vs-baseline-one 250)
test-large-vs-baseline-one SCALE:
    uv run -m pytest tests/test_drift_adoption_large_scale.py tests/test_drift_adoption_large_scale_baseline.py -v -k "scale-{{SCALE}}" -n auto {{ flags }}

# Run full-drift (all creates) skill tests in parallel
test-full-drift:
    uv run -m pytest tests/test_full_drift.py -v -m full_drift -n auto {{ flags }}

# Run full-drift baseline (no-skill) tests in parallel
test-full-drift-baseline:
    uv run -m pytest tests/test_full_drift_baseline.py -v -m "full_drift and baseline" -n auto {{ flags }}

# Run full-drift skill + baseline in parallel
test-full-drift-vs-baseline:
    uv run -m pytest tests/test_full_drift.py tests/test_full_drift_baseline.py -v -n auto {{ flags }}

# Run a specific full-drift scale skill + baseline in parallel (e.g., just test-full-drift-vs-baseline-one 50)
test-full-drift-vs-baseline-one SCALE:
    uv run -m pytest tests/test_full_drift.py tests/test_full_drift_baseline.py -v -k "scale-{{SCALE}}" -n auto {{ flags }}

# Run all skill + baseline tests in parallel
test-vs-baseline:
    uv run -m pytest tests/test_drift_adoption_small_scale.py tests/test_drift_adoption_small_scale_baseline.py tests/test_drift_adoption_large_scale.py tests/test_drift_adoption_large_scale_baseline.py -v -n auto {{ flags }}

# Compare skill vs baseline metrics
compare:
    uv run tests/compare_metrics.py

# Analyze agent logs for stuck points and approach patterns
analyze:
    uv run tests/analyze_logs.py .test-output/logs

# Compare skill vs baseline agent logs side-by-side
analyze-compare:
    uv run tests/analyze_logs.py --compare .test-output/logs

# Install dependencies
sync:
    uv sync

#!/usr/bin/env python3
"""Compare skill vs baseline metrics from .test-output/metrics/ JSON files.

Usage:
    uv run tests/compare_metrics.py                          # default directory
    uv run tests/compare_metrics.py .test-output/metrics     # explicit directory
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def load_metrics(path: Path) -> dict:
    return json.loads(path.read_text())


def fmt_tokens(m: dict) -> str:
    """Summarize total token usage as a single number."""
    inp = (m.get("input_tokens") or 0) + (m.get("cache_read_input_tokens") or m.get("cache_read_tokens") or 0)
    out = m.get("output_tokens") or 0
    cache_create = m.get("cache_creation_input_tokens") or m.get("cache_creation_tokens") or 0
    return f"{inp + cache_create:,}/{out:,}"


def fmt_time(v: float | None) -> str:
    return f"{v:.1f}" if v is not None else "-"


def fmt_int(v: int | None) -> str:
    return str(v) if v is not None else "-"


def delta(a: float | None, b: float | None) -> str:
    if a is None or b is None or b == 0:
        return "-"
    pct = (a - b) / b * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.0f}%"


def find_pairs(metrics_dir: Path) -> list[tuple[str, dict, dict]]:
    """Find matching skill/baseline test pairs."""
    files = {p.stem: p for p in sorted(metrics_dir.glob("*.json"))}

    pairs: list[tuple[str, dict, dict]] = []

    # Match by naming convention:
    #   test_<name>[param] (skill) vs test_<name>_baseline[param] (baseline)
    #   test_drift_adoption_<name> vs test_baseline_<name>
    for name, path in files.items():
        if "baseline" in name:
            continue

        # Generic pattern: test_X[param] -> test_X_baseline[param]
        if "[" in name:
            base, param = name.split("[", 1)
            baseline_key = f"{base}_baseline[{param}"
            if baseline_key in files:
                label = name.removeprefix("test_drift_adoption_").removeprefix("test_")
                pairs.append((label, load_metrics(path), load_metrics(files[baseline_key])))
                continue

        # Fallback: test_drift_adoption_X -> test_baseline_X
        if name.startswith("test_drift_adoption_"):
            suffix = name[len("test_drift_adoption_"):]
            baseline_key = f"test_baseline_{suffix}"
            if baseline_key in files:
                pairs.append((suffix, load_metrics(path), load_metrics(files[baseline_key])))
                continue

        # Fallback: test_X -> test_X_baseline
        baseline_key = f"{name}_baseline"
        if baseline_key in files:
            label = name.removeprefix("test_")
            pairs.append((label, load_metrics(path), load_metrics(files[baseline_key])))

    return pairs


def print_table(pairs: list[tuple[str, dict, dict]]) -> None:
    if not pairs:
        print("No matching skill/baseline pairs found.")
        return

    header = (
        f"{'Test':<30} {'Metric':<18} {'Skill':>12} {'Baseline':>12} {'Delta':>8}"
    )
    sep = "-" * len(header)

    print(sep)
    print(header)
    print(sep)

    for label, skill, baseline in pairs:
        rows = [
            ("Agent time (s)", fmt_time(skill.get("agent_time_s")), fmt_time(baseline.get("agent_time_s")),
             delta(skill.get("agent_time_s"), baseline.get("agent_time_s"))),
            ("Total time (s)", fmt_time(skill.get("total_time_s")), fmt_time(baseline.get("total_time_s")),
             delta(skill.get("total_time_s"), baseline.get("total_time_s"))),
            ("Iterations", fmt_int(skill.get("iterations")), fmt_int(baseline.get("iterations")),
             delta(skill.get("iterations"), baseline.get("iterations"))),
            ("Output tokens", fmt_int(skill.get("output_tokens")), fmt_int(baseline.get("output_tokens")),
             delta(skill.get("output_tokens"), baseline.get("output_tokens"))),
            ("Tokens (in+cache/out)", fmt_tokens(skill), fmt_tokens(baseline), ""),
            ("Success", "yes" if skill.get("success") else "NO", "yes" if baseline.get("success") else "NO", ""),
        ]

        for i, (metric, s_val, b_val, d) in enumerate(rows):
            test_col = label if i == 0 else ""
            print(f"{test_col:<30} {metric:<18} {s_val:>12} {b_val:>12} {d:>8}")

        print(sep)


def main() -> None:
    if len(sys.argv) > 1:
        metrics_dir = Path(sys.argv[1])
    else:
        metrics_dir = Path(".test-output/metrics")

    if not metrics_dir.is_dir():
        print(f"Metrics directory not found: {metrics_dir}", file=sys.stderr)
        sys.exit(1)

    pairs = find_pairs(metrics_dir)
    print_table(pairs)


if __name__ == "__main__":
    main()

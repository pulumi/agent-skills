#!/usr/bin/env python3
"""Compare skill vs baseline metrics from .test-output/metrics/ JSON files.

Usage:
    uv run tests/compare_metrics.py                          # default directory
    uv run tests/compare_metrics.py .test-output/metrics     # explicit directory
    uv run tests/compare_metrics.py --matrix .test-output/metrics  # compact matrix view
"""

from __future__ import annotations

import json
import re
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
            ("Remaining drift", fmt_int(skill.get("remaining_drift_count")), fmt_int(baseline.get("remaining_drift_count")), ""),
            ("Success", "yes" if skill.get("success") else "NO", "yes" if baseline.get("success") else "NO", ""),
        ]

        for i, (metric, s_val, b_val, d) in enumerate(rows):
            test_col = label if i == 0 else ""
            print(f"{test_col:<30} {metric:<18} {s_val:>12} {b_val:>12} {d:>8}")

        print(sep)


def parse_matrix_key(label: str) -> tuple[int, int] | None:
    """Extract (scale, drift_pct) from a test label.

    Patterns:
        complex_drift[scale-20-full]    → (20, 100)
        complex_drift[scale-20-50pct]   → (20, 50)
        complex_drift[scale-20-15pct]   → (20, 15)
    """
    m = re.search(r"scale-(\d+)-(\w+)", label)
    if not m:
        return None
    scale = int(m.group(1))
    drift_tag = m.group(2)
    if drift_tag == "full":
        drift_pct = 100
    elif drift_tag.endswith("pct"):
        drift_pct = int(drift_tag[:-3])
    else:
        return None
    return (scale, drift_pct)


def fmt_cell_line(m: dict) -> str:
    """Format one line of a matrix cell: pass/fail remaining/initial time iters."""
    success = "\u2713" if m.get("success") else "\u2717"
    remaining = m.get("remaining_drift_count", "?")
    initial = m.get("initial_drift_count", "?")
    time_s = m.get("agent_time_s")
    time_str = f"{time_s:.0f}s" if time_s is not None else "-"
    iters = m.get("iterations", "?")
    return f"{success} {remaining}/{initial} \u2192 {time_str} {iters}it"


def print_matrix(pairs: list[tuple[str, dict, dict]]) -> None:
    """Print a compact matrix grid of skill vs baseline results."""
    # Parse matrix keys and group
    cells: dict[tuple[int, int], tuple[dict, dict]] = {}
    non_matrix: list[tuple[str, dict, dict]] = []

    for label, skill, baseline in pairs:
        key = parse_matrix_key(label)
        if key:
            cells[key] = (skill, baseline)
        else:
            non_matrix.append((label, skill, baseline))

    if not cells:
        print("No complex drift matrix data found.")
        if non_matrix:
            print("Non-matrix pairs found — use without --matrix to view.")
        return

    scales = sorted(set(s for s, _ in cells))
    drift_pcts = sorted(set(d for _, d in cells))

    col_width = 22
    scale_col = 8

    # Header
    print()
    print("Complex Drift: Skill vs Baseline Matrix")
    print("\u2550" * (scale_col + len(drift_pcts) * (col_width + 1) + 1))

    # Drift % header row
    header = " " * scale_col + "\u2502"
    for dp in drift_pcts:
        header += f" {dp}% drift".center(col_width) + "\u2502"
    print(header)

    # Top border of grid
    border = " " * scale_col + "\u250c" + ("\u2500" * col_width + "\u252c") * (len(drift_pcts) - 1) + "\u2500" * col_width + "\u2510"
    print(border)

    # Aggregate tracking
    skill_successes = 0
    baseline_successes = 0
    skill_times: list[float] = []
    baseline_times: list[float] = []
    skill_iters: list[int] = []
    baseline_iters: list[int] = []
    skill_resolved: list[float] = []
    baseline_resolved: list[float] = []
    total_cells = 0

    for si, scale in enumerate(scales):
        # Skill line
        skill_line = f"  {scale:>4}  " + "\u2502"
        baseline_line = " " * scale_col + "\u2502"

        for dp in drift_pcts:
            if (scale, dp) in cells:
                s, b = cells[(scale, dp)]
                total_cells += 1

                skill_line += " " + fmt_cell_line(s).ljust(col_width - 1) + "\u2502"
                baseline_line += " " + fmt_cell_line(b).ljust(col_width - 1) + "\u2502"

                # Aggregate stats
                if s.get("success"):
                    skill_successes += 1
                if b.get("success"):
                    baseline_successes += 1
                if s.get("agent_time_s") is not None:
                    skill_times.append(s["agent_time_s"])
                if b.get("agent_time_s") is not None:
                    baseline_times.append(b["agent_time_s"])
                if s.get("iterations") is not None:
                    skill_iters.append(s["iterations"])
                if b.get("iterations") is not None:
                    baseline_iters.append(b["iterations"])
                # Drift resolution %
                for metrics, resolved_list in [(s, skill_resolved), (b, baseline_resolved)]:
                    initial = metrics.get("initial_drift_count") or 0
                    remaining = metrics.get("remaining_drift_count") or 0
                    if initial > 0:
                        resolved_list.append((initial - remaining) / initial * 100)
            else:
                skill_line += " " + "(no data)".center(col_width - 1) + "\u2502"
                baseline_line += " " + "".center(col_width - 1) + "\u2502"

        print(skill_line)
        print(baseline_line)

        # Row separator
        if si < len(scales) - 1:
            sep = " " * scale_col + "\u251c" + ("\u2500" * col_width + "\u253c") * (len(drift_pcts) - 1) + "\u2500" * col_width + "\u2524"
            print(sep)

    # Bottom border
    bottom = " " * scale_col + "\u2514" + ("\u2500" * col_width + "\u2534") * (len(drift_pcts) - 1) + "\u2500" * col_width + "\u2518"
    print(bottom)

    # Legend
    print(f"\n  Legend: \u2713/\u2717 remaining/initial \u2192 agent_time iterations")
    print(f"  Top line = skill, bottom line = baseline")

    # Aggregates
    if total_cells > 0:
        avg = lambda xs: sum(xs) / len(xs) if xs else 0

        print(f"\n  Aggregates ({total_cells} cells)")
        print(f"  {'':.<30} {'Skill':>10} {'Baseline':>10}")
        s_rate = f"{skill_successes}/{total_cells}"
        b_rate = f"{baseline_successes}/{total_cells}"
        print(f"  {'Success rate':<30} {s_rate:>10} {b_rate:>10}")
        print(f"  {'Avg drift resolved %':<30} {avg(skill_resolved):>9.0f}% {avg(baseline_resolved):>9.0f}%")
        print(f"  {'Avg agent time (s)':<30} {avg(skill_times):>9.0f}s {avg(baseline_times):>9.0f}s")
        print(f"  {'Avg iterations':<30} {avg(skill_iters):>10.1f} {avg(baseline_iters):>10.1f}")

    print()

    # If there are non-matrix pairs, mention them
    if non_matrix:
        print(f"  ({len(non_matrix)} non-matrix pair(s) not shown — run without --matrix)")
        print()


def main() -> None:
    args = sys.argv[1:]
    matrix_mode = "--matrix" in args
    args = [a for a in args if a != "--matrix"]

    if args:
        metrics_dir = Path(args[0])
    else:
        metrics_dir = Path(".test-output/metrics")

    if not metrics_dir.is_dir():
        print(f"Metrics directory not found: {metrics_dir}", file=sys.stderr)
        sys.exit(1)

    pairs = find_pairs(metrics_dir)

    if matrix_mode:
        print_matrix(pairs)
    else:
        print_table(pairs)


if __name__ == "__main__":
    main()

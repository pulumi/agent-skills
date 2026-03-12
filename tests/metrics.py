"""Metrics dataclasses and output helpers for drift adoption tests."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class AgentMetrics:
    """Metrics collected during agent execution."""

    agent_time_s: float = 0.0
    iterations: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    peak_memory_bytes: int = 0


@dataclass
class TestMetrics:
    """Metrics collected for an entire test run."""

    test_name: str = ""
    resource_count: int = 0
    total_time_s: float = 0.0
    agent: AgentMetrics | None = None
    success: bool = False
    initial_drift_count: int | None = None
    remaining_drift_count: int | None = None


def write_metrics(metrics: TestMetrics, output_dir: Path) -> None:
    """Write metrics for a single test to a JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    data = _flatten(metrics)
    path = output_dir / f"{metrics.test_name}.json"
    path.write_text(json.dumps(data, indent=2) + "\n")


def format_summary_table(metrics_list: list[TestMetrics]) -> str:
    """Return a formatted summary table of all test metrics."""
    if not metrics_list:
        return ""

    header = (
        f"{'Test':<45} {'Resources':>9} {'Time(s)':>8} {'Agent(s)':>8} "
        f"{'Iters':>5} {'Tokens(in/out)':>16} {'Mem(MB)':>8} {'Drift':>10} {'Pass':>4}"
    )
    sep = "-" * len(header)
    lines = [sep, header, sep]

    for m in metrics_list:
        a = m.agent
        agent_time = f"{a.agent_time_s:.1f}" if a else "-"
        iters = str(a.iterations) if a else "-"
        tokens = f"{a.input_tokens}/{a.output_tokens}" if a else "-/-"
        mem = f"{a.peak_memory_bytes / (1024 * 1024):.1f}" if a else "-"
        passed = "YES" if m.success else "NO"
        if m.initial_drift_count is not None and m.remaining_drift_count is not None:
            drift = f"{m.remaining_drift_count}/{m.initial_drift_count}"
        else:
            drift = "-"

        lines.append(
            f"{m.test_name:<45} {m.resource_count:>9} {m.total_time_s:>8.1f} "
            f"{agent_time:>8} {iters:>5} {tokens:>16} {mem:>8} {drift:>10} {passed:>4}"
        )

    lines.append(sep)
    return "\n".join(lines)


def read_metrics(metrics_dir: Path) -> list[TestMetrics]:
    """Read all per-test metrics JSON files from a directory."""
    if not metrics_dir.is_dir():
        return []
    results: list[TestMetrics] = []
    for p in sorted(metrics_dir.glob("*.json")):
        data = json.loads(p.read_text())
        agent = None
        if data.get("agent_time_s") is not None:
            agent = AgentMetrics(
                agent_time_s=data.get("agent_time_s", 0.0),
                iterations=data.get("iterations", 0),
                input_tokens=data.get("input_tokens", 0),
                output_tokens=data.get("output_tokens", 0),
                cache_creation_tokens=data.get("cache_creation_tokens", 0),
                cache_read_tokens=data.get("cache_read_tokens", 0),
                peak_memory_bytes=int(data.get("peak_memory_mb", 0) * 1024 * 1024),
            )
        results.append(
            TestMetrics(
                test_name=data.get("test_name", p.stem),
                resource_count=data.get("resource_count", 0),
                total_time_s=data.get("total_time_s", 0.0),
                agent=agent,
                success=data.get("success", False),
                initial_drift_count=data.get("initial_drift_count"),
                remaining_drift_count=data.get("remaining_drift_count"),
            )
        )
    return results


def _flatten(metrics: TestMetrics) -> dict:
    """Flatten TestMetrics into a single-level dict for JSON output."""
    agent = metrics.agent
    return {
        "test_name": metrics.test_name,
        "resource_count": metrics.resource_count,
        "total_time_s": round(metrics.total_time_s, 2),
        "agent_time_s": round(agent.agent_time_s, 2) if agent else None,
        "iterations": agent.iterations if agent else None,
        "input_tokens": agent.input_tokens if agent else None,
        "output_tokens": agent.output_tokens if agent else None,
        "cache_creation_tokens": agent.cache_creation_tokens if agent else None,
        "cache_read_tokens": agent.cache_read_tokens if agent else None,
        "peak_memory_mb": round(agent.peak_memory_bytes / (1024 * 1024), 1) if agent else None,
        "success": metrics.success,
        "initial_drift_count": metrics.initial_drift_count,
        "remaining_drift_count": metrics.remaining_drift_count,
    }

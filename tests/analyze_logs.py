#!/usr/bin/env python3
"""Analyze agent message logs for stuck points, approach patterns, and skill vs baseline comparison.

Usage:
    uv run tests/analyze_logs.py                                                    # all logs in .test-output/logs/
    uv run tests/analyze_logs.py .test-output/logs/test_complex_drift[scale-20-full].log  # single file
    uv run tests/analyze_logs.py --compare                                          # side-by-side skill vs baseline
    uv run tests/analyze_logs.py --compare .test-output/logs                        # explicit directory
    uv run tests/analyze_logs.py --matrix .test-output/logs                         # compact matrix view
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

DELIMITER = "=" * 80
LABEL_RE = re.compile(r"^\[(.+)\]$")
ITER_RE = re.compile(r"\(iter (\d+)\)")
TOOL_CALL_RE = re.compile(r"^TOOL_CALL \(iter \d+\): (.+)$")
TOOL_RESULT_RE = re.compile(r"^TOOL_RESULT: (.+)$")
BASH_CMD_RE = re.compile(r'"command"\s*:\s*"(.+?)"', re.DOTALL)
def _strip_cd_prefix(cmd: str) -> str:
    """Strip 'cd "/path" && ' or 'cd /path && ' prefix from a shell command."""
    cmd = re.sub(r'^cd\s+\\?"[^"]*\\?"\s*&&\s*', "", cmd)
    cmd = re.sub(r'^cd\s+\S+\s*&&\s*', "", cmd)
    return cmd


ERROR_PHRASES = [
    "let me try again",
    "that didn't work",
    "let me try a different",
    "failed",
    "error occurred",
    "try another approach",
    "try something else",
    "doesn't seem to",
    "didn't seem to",
    "not working",
    "let me instead",
    "let me fix",
]


@dataclass
class LogSection:
    label: str
    iteration: int  # 0 for non-iteration sections
    section_type: str  # prompt | assistant | tool_call | tool_result | result | stderr | options | other
    tool_name: str | None
    content: str


@dataclass
class Session:
    sections: list[LogSection] = field(default_factory=list)
    prompt: str = ""
    result_summary: str = ""
    iterations: int = 0


@dataclass
class StuckPoint:
    iteration: int
    reason: str
    detail: str


@dataclass
class IterationInfo:
    number: int
    assistant_text: str = ""
    tool_calls: list[tuple[str, str, str]] = field(default_factory=list)  # (tool_name, brief_content, full_content)
    bash_commands: list[str] = field(default_factory=list)
    phase: str = ""  # understanding | acting | verifying


def parse_log(text: str) -> Session:
    """Parse a log file into a Session of LogSections."""
    session = Session()
    # Split on delimiter lines
    parts = text.split(f"\n{DELIMITER}\n")

    i = 0
    while i < len(parts):
        chunk = parts[i].strip()
        i += 1

        label_match = LABEL_RE.match(chunk)
        if not label_match:
            continue

        label = label_match.group(1)
        content = parts[i].strip() if i < len(parts) else ""
        i += 1

        # Determine iteration
        iter_match = ITER_RE.search(label)
        iteration = int(iter_match.group(1)) if iter_match else 0

        # Classify section type
        tool_name = None
        if label == "PROMPT":
            section_type = "prompt"
        elif label == "RESULT":
            section_type = "result"
        elif label == "STDERR":
            section_type = "stderr"
        elif label == "OPTIONS":
            section_type = "options"
        elif label.startswith("ASSISTANT"):
            section_type = "assistant"
        elif label.startswith("TOOL_CALL"):
            section_type = "tool_call"
            tc_match = TOOL_CALL_RE.match(label)
            tool_name = tc_match.group(1) if tc_match else "unknown"
        elif label.startswith("TOOL_RESULT"):
            section_type = "tool_result"
            tr_match = TOOL_RESULT_RE.match(label)
            tool_name = tr_match.group(1) if tr_match else "unknown"
        else:
            section_type = "other"

        sec = LogSection(
            label=label,
            iteration=iteration,
            section_type=section_type,
            tool_name=tool_name,
            content=content,
        )
        session.sections.append(sec)

        if section_type == "prompt":
            session.prompt = content
        elif section_type == "result":
            session.result_summary = content

    # Compute max iteration
    session.iterations = max((s.iteration for s in session.sections), default=0)
    return session


def build_iterations(session: Session) -> list[IterationInfo]:
    """Group sections into per-iteration info."""
    iters: dict[int, IterationInfo] = {}

    for sec in session.sections:
        if sec.iteration == 0:
            continue
        if sec.iteration not in iters:
            iters[sec.iteration] = IterationInfo(number=sec.iteration)
        info = iters[sec.iteration]

        if sec.section_type == "assistant":
            info.assistant_text = sec.content
        elif sec.section_type == "tool_call":
            brief = sec.content[:120].replace("\n", " ")
            info.tool_calls.append((sec.tool_name or "unknown", brief, sec.content))
            # Extract bash commands
            if sec.tool_name in ("shell__shell_execute", "Bash"):
                cmd_match = BASH_CMD_RE.search(sec.content)
                if cmd_match:
                    cmd = cmd_match.group(1)
                    # Strip cd prefix for readability
                    cmd = _strip_cd_prefix(cmd)
                    info.bash_commands.append(cmd)

    return [iters[k] for k in sorted(iters)]


def classify_phase(info: IterationInfo) -> str:
    """Classify an iteration into a phase."""
    tool_names = [t[0] for t in info.tool_calls]
    cmds = info.bash_commands

    # Check for verification: pulumi preview after edits
    if any("pulumi preview" in c or "pulumi up" in c for c in cmds):
        return "verifying"

    # Check for acting: Edit/Write or drift-adopt commands
    acting_tools = {"Edit", "Write", "NotebookEdit"}
    if any(t in acting_tools for t in tool_names):
        return "acting"
    if any("pulumi-drift-adopt" in c or "drift-adopt" in c for c in cmds):
        return "acting"

    # Check for understanding: Read/Glob/Grep/diagnostic commands
    understanding_tools = {"Read", "Glob", "Grep", "ToolSearch", "TodoWrite"}
    if any(t in understanding_tools for t in tool_names):
        return "understanding"
    if any(t in ("shell__shell_execute", "Bash") for t in tool_names):
        # Shell calls that are diagnostic
        if any(
            c.startswith(("ls", "cat", "head", "tail", "find", "pwd", "pulumi stack", "pulumi config", "npm", "which"))
            for c in cmds
        ):
            return "understanding"
        # Shell calls that are acting (file writes, installs, etc.)
        if any(c.startswith(("echo", "mkdir", "npm install", "pip install", "pulumi import")) for c in cmds):
            return "acting"
        return "understanding"  # default for shell

    return "understanding"


def tool_histogram(session: Session) -> Counter:
    """Count tool usage, sub-classifying Bash by command prefix."""
    counter: Counter = Counter()
    for sec in session.sections:
        if sec.section_type != "tool_call":
            continue
        name = sec.tool_name or "unknown"
        if name in ("shell__shell_execute", "Bash"):
            cmd_match = BASH_CMD_RE.search(sec.content)
            if cmd_match:
                cmd = cmd_match.group(1)
                cmd = _strip_cd_prefix(cmd)
                prefix = cmd.split()[0] if cmd.split() else "unknown"
                # Normalize common prefixes
                if "pulumi-drift-adopt" in prefix or "drift-adopt" in prefix:
                    prefix = "pulumi-drift-adopt"
                elif prefix.startswith("pulumi"):
                    prefix = "pulumi"
                counter[f"Bash({prefix})"] += 1
            else:
                counter["Bash(?)"] += 1
        else:
            counter[name] += 1
    return counter


def detect_stuck_points(iterations: list[IterationInfo]) -> list[StuckPoint]:
    """Detect iterations where the agent appears stuck."""
    stuck: list[StuckPoint] = []

    # Track consecutive patterns
    prev_normalized_calls: list[tuple[str, str]] = []
    consecutive_bash_without_edit = 0
    file_read_counts: Counter = Counter()

    for info in iterations:
        tool_names = [t[0] for t in info.tool_calls]

        # Check for retry loops: same tool+normalized args in consecutive iterations
        # For bash calls, compare the normalized command (cd prefix stripped)
        def _normalize_call(tool: str, full_content: str) -> str:
            if tool in ("shell__shell_execute", "Bash"):
                cmd_match = BASH_CMD_RE.search(full_content)
                if cmd_match:
                    cmd = cmd_match.group(1)
                    return _strip_cd_prefix(cmd)
            return full_content[:200]

        curr_normalized = [(t, _normalize_call(t, full)) for t, _brief, full in info.tool_calls]
        if prev_normalized_calls and curr_normalized:
            prev_set = set(prev_normalized_calls)
            for tool, norm in curr_normalized:
                if (tool, norm) in prev_set:
                    stuck.append(StuckPoint(
                        info.number,
                        "Repeated tool call",
                        f"{tool}: {norm[:100]}",
                    ))

        # Check for error-recovery language
        text_lower = info.assistant_text.lower()
        for phrase in ERROR_PHRASES:
            if phrase in text_lower:
                stuck.append(StuckPoint(
                    info.number,
                    "Error recovery language",
                    f'"{phrase}" found in assistant text',
                ))
                break

        # Consecutive Bash without Edit/Write
        has_edit = any(t in ("Edit", "Write") for t in tool_names)
        has_bash = any(t in ("shell__shell_execute", "Bash") for t in tool_names)
        if has_bash and not has_edit:
            consecutive_bash_without_edit += 1
        else:
            consecutive_bash_without_edit = 0
        if consecutive_bash_without_edit > 3:
            stuck.append(StuckPoint(
                info.number,
                "Diagnostic spinning",
                f"{consecutive_bash_without_edit} consecutive Bash calls without Edit/Write",
            ))

        # Track file reads
        for sec_tool, sec_brief, _sec_full in info.tool_calls:
            if sec_tool == "Read":
                # Try to extract filename
                file_match = re.search(r'"file_path"\s*:\s*"([^"]+)"', sec_brief)
                if file_match:
                    fname = file_match.group(1).rsplit("/", 1)[-1]
                    file_read_counts[fname] += 1
                    if file_read_counts[fname] > 2:
                        stuck.append(StuckPoint(
                            info.number,
                            "Repeated file read",
                            f"{fname} read {file_read_counts[fname]} times",
                        ))

        prev_normalized_calls = curr_normalized

    return stuck


def phase_breakdown(iterations: list[IterationInfo]) -> dict[str, int]:
    """Count iterations per phase."""
    counts: dict[str, int] = Counter()
    for info in iterations:
        info.phase = classify_phase(info)
        counts[info.phase] += 1
    return dict(counts)


# ── Report formatting ──────────────────────────────────────────────────────────


def print_session_report(name: str, session: Session) -> None:
    """Print full analysis for a single log file."""
    iterations = build_iterations(session)
    histogram = tool_histogram(session)
    stuck = detect_stuck_points(iterations)
    phases = phase_breakdown(iterations)

    print(f"\n{'━' * 80}")
    print(f"  {name}")
    print(f"  Iterations: {session.iterations}  |  Sections: {len(session.sections)}")
    print(f"{'━' * 80}")

    # Iteration timeline
    print(f"\n{'─' * 40}")
    print("  ITERATION TIMELINE")
    print(f"{'─' * 40}")
    for info in iterations:
        phase_tag = f"[{info.phase[:3].upper()}]" if info.phase else ""
        tools = ", ".join(t[0] for t in info.tool_calls)
        assistant_brief = info.assistant_text[:100].replace("\n", " ").strip()
        cmds = "; ".join(info.bash_commands[:2])
        if cmds:
            cmds = f"\n         cmds: {cmds[:120]}"
        print(f"  {info.number:>3} {phase_tag:<5} tools: {tools}")
        if assistant_brief:
            print(f"         text: {assistant_brief}")
        if cmds:
            print(cmds)

    # Tool histogram
    print(f"\n{'─' * 40}")
    print("  TOOL USAGE")
    print(f"{'─' * 40}")
    for tool, count in histogram.most_common():
        bar = "█" * count
        print(f"  {tool:<30} {count:>3}  {bar}")

    # Phase breakdown
    print(f"\n{'─' * 40}")
    print("  PHASE BREAKDOWN")
    print(f"{'─' * 40}")
    total = sum(phases.values()) or 1
    for phase in ["understanding", "acting", "verifying"]:
        count = phases.get(phase, 0)
        pct = count / total * 100
        bar = "█" * int(pct / 2)
        print(f"  {phase:<15} {count:>3} ({pct:4.0f}%)  {bar}")

    # Stuck points
    print(f"\n{'─' * 40}")
    print(f"  STUCK POINTS ({len(stuck)})")
    print(f"{'─' * 40}")
    if stuck:
        for sp in stuck:
            print(f"  iter {sp.iteration:>3}: {sp.reason}")
            print(f"           {sp.detail}")
    else:
        print("  None detected")

    print()


def find_pairs(log_dir: Path) -> list[tuple[str, Path, Path]]:
    """Find matching skill/baseline log file pairs.

    Pairing conventions (tried in order):
      1. test_X[param] ↔ test_X_baseline[param]       (generic parameterized)
      2. test_drift_adoption_X ↔ test_baseline_X       (legacy simple tests)
      3. test_X ↔ test_X_baseline                      (generic non-parameterized)
    """
    files = {p.stem: p for p in sorted(log_dir.glob("*.log"))}
    pairs: list[tuple[str, Path, Path]] = []

    for name, path in files.items():
        if "baseline" in name:
            continue

        # Generic pattern: test_X[param] -> test_X_baseline[param]
        if "[" in name:
            base, param = name.split("[", 1)
            baseline_key = f"{base}_baseline[{param}"
            if baseline_key in files:
                label = name.removeprefix("test_drift_adoption_").removeprefix("test_")
                pairs.append((label, path, files[baseline_key]))
                continue

        # Legacy: test_drift_adoption_X -> test_baseline_X
        if name.startswith("test_drift_adoption_"):
            suffix = name[len("test_drift_adoption_"):]
            baseline_key = f"test_baseline_{suffix}"
            if baseline_key in files:
                pairs.append((suffix, path, files[baseline_key]))
                continue

        # Generic non-parameterized: test_X -> test_X_baseline
        baseline_key = f"{name}_baseline"
        if baseline_key in files:
            label = name.removeprefix("test_")
            pairs.append((label, path, files[baseline_key]))

    return pairs


def print_comparison(pairs: list[tuple[str, Path, Path]]) -> None:
    """Print side-by-side comparison of skill vs baseline pairs."""
    if not pairs:
        print("No matching skill/baseline log pairs found.")
        return

    for label, skill_path, baseline_path in pairs:
        skill_session = parse_log(skill_path.read_text())
        baseline_session = parse_log(baseline_path.read_text())

        skill_iters = build_iterations(skill_session)
        baseline_iters = build_iterations(baseline_session)

        skill_stuck = detect_stuck_points(skill_iters)
        baseline_stuck = detect_stuck_points(baseline_iters)

        skill_phases = phase_breakdown(skill_iters)
        baseline_phases = phase_breakdown(baseline_iters)

        skill_hist = tool_histogram(skill_session)
        baseline_hist = tool_histogram(baseline_session)

        print(f"\n{'━' * 80}")
        print(f"  COMPARISON: {label}")
        print(f"{'━' * 80}")

        # Summary table
        header = f"  {'Metric':<25} {'Skill':>12} {'Baseline':>12} {'Delta':>8}"
        print(header)
        print(f"  {'-' * 57}")

        def delta(a: int | float, b: int | float) -> str:
            if b == 0:
                return "-"
            pct = (a - b) / b * 100
            sign = "+" if pct >= 0 else ""
            return f"{sign}{pct:.0f}%"

        rows = [
            ("Iterations", skill_session.iterations, baseline_session.iterations),
            ("Stuck points", len(skill_stuck), len(baseline_stuck)),
        ]
        for phase in ["understanding", "acting", "verifying"]:
            rows.append((
                f"Phase: {phase}",
                skill_phases.get(phase, 0),
                baseline_phases.get(phase, 0),
            ))

        for metric, s_val, b_val in rows:
            print(f"  {metric:<25} {s_val:>12} {b_val:>12} {delta(s_val, b_val):>8}")

        # Tool usage differences
        all_tools = sorted(set(skill_hist) | set(baseline_hist))
        if all_tools:
            print(f"\n  {'Tool':<30} {'Skill':>8} {'Baseline':>8}")
            print(f"  {'-' * 46}")
            for tool in all_tools:
                s = skill_hist.get(tool, 0)
                b = baseline_hist.get(tool, 0)
                marker = " ◄" if abs(s - b) > 2 else ""
                print(f"  {tool:<30} {s:>8} {b:>8}{marker}")

        # Find first divergence point
        print(f"\n  Key divergence:")
        max_common = min(len(skill_iters), len(baseline_iters))
        diverged = False
        for idx in range(max_common):
            s_tools = sorted(t[0] for t in skill_iters[idx].tool_calls)
            b_tools = sorted(t[0] for t in baseline_iters[idx].tool_calls)
            if s_tools != b_tools:
                si = skill_iters[idx]
                bi = baseline_iters[idx]
                print(f"    First at iter {si.number}: skill used {', '.join(s_tools)} vs baseline {', '.join(b_tools)}")
                diverged = True
                break
        if not diverged:
            if len(skill_iters) != len(baseline_iters):
                print(f"    Approaches aligned for {max_common} iters, then skill has {len(skill_iters)} vs baseline {len(baseline_iters)} total")
            else:
                print("    No significant divergence in tool choices")

        print()


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


def _analyze_log_file(path: Path) -> tuple[int, int, dict[str, int]]:
    """Analyze a log file and return (iterations, stuck_count, phases)."""
    session = parse_log(path.read_text())
    iterations = build_iterations(session)
    stuck = detect_stuck_points(iterations)
    phases = phase_breakdown(iterations)
    return session.iterations, len(stuck), phases


def fmt_log_cell(iters: int, stuck: int, phases: dict[str, int]) -> str:
    """Format a compact cell: iters stuck U/A/V phase ratio."""
    u = phases.get("understanding", 0)
    a = phases.get("acting", 0)
    v = phases.get("verifying", 0)
    stuck_str = f"{stuck}stk" if stuck > 0 else "0stk"
    return f"{iters}it {stuck_str} {u}/{a}/{v}"


def print_log_matrix(pairs: list[tuple[str, Path, Path]]) -> None:
    """Print a compact matrix grid of log analysis for skill vs baseline."""
    cells: dict[tuple[int, int], tuple[Path, Path]] = {}
    non_matrix: list[tuple[str, Path, Path]] = []

    for label, skill_path, baseline_path in pairs:
        key = parse_matrix_key(label)
        if key:
            cells[key] = (skill_path, baseline_path)
        else:
            non_matrix.append((label, skill_path, baseline_path))

    if not cells:
        print("No complex drift matrix data found.")
        if non_matrix:
            print("Non-matrix pairs found — use --compare to view.")
        return

    scales = sorted(set(s for s, _ in cells))
    drift_pcts = sorted(set(d for _, d in cells))

    col_width = 22
    scale_col = 8

    # Header
    print()
    print("Complex Drift: Agent Behavior Matrix")
    print("\u2550" * (scale_col + len(drift_pcts) * (col_width + 1) + 1))

    # Drift % header row
    header = " " * scale_col + "\u2502"
    for dp in drift_pcts:
        header += f" {dp}% drift".center(col_width) + "\u2502"
    print(header)

    # Top border
    border = " " * scale_col + "\u250c" + ("\u2500" * col_width + "\u252c") * (len(drift_pcts) - 1) + "\u2500" * col_width + "\u2510"
    print(border)

    # Aggregates
    skill_stuck_total = 0
    baseline_stuck_total = 0
    total_cells = 0

    for si, scale in enumerate(scales):
        skill_line = f"  {scale:>4}  " + "\u2502"
        baseline_line = " " * scale_col + "\u2502"

        for dp in drift_pcts:
            if (scale, dp) in cells:
                s_path, b_path = cells[(scale, dp)]
                total_cells += 1

                s_iters, s_stuck, s_phases = _analyze_log_file(s_path)
                b_iters, b_stuck, b_phases = _analyze_log_file(b_path)

                skill_stuck_total += s_stuck
                baseline_stuck_total += b_stuck

                skill_line += " " + fmt_log_cell(s_iters, s_stuck, s_phases).ljust(col_width - 1) + "\u2502"
                baseline_line += " " + fmt_log_cell(b_iters, b_stuck, b_phases).ljust(col_width - 1) + "\u2502"
            else:
                skill_line += " " + "(no data)".center(col_width - 1) + "\u2502"
                baseline_line += " " + "".center(col_width - 1) + "\u2502"

        print(skill_line)
        print(baseline_line)

        if si < len(scales) - 1:
            sep = " " * scale_col + "\u251c" + ("\u2500" * col_width + "\u253c") * (len(drift_pcts) - 1) + "\u2500" * col_width + "\u2524"
            print(sep)

    # Bottom border
    bottom = " " * scale_col + "\u2514" + ("\u2500" * col_width + "\u2534") * (len(drift_pcts) - 1) + "\u2500" * col_width + "\u2518"
    print(bottom)

    # Legend
    print(f"\n  Legend: iterations stuck_points understanding/acting/verifying")
    print(f"  Top line = skill, bottom line = baseline")

    # Aggregates
    if total_cells > 0:
        print(f"\n  Aggregates ({total_cells} cells)")
        print(f"  {'':.<30} {'Skill':>10} {'Baseline':>10}")
        print(f"  {'Total stuck points':<30} {skill_stuck_total:>10} {baseline_stuck_total:>10}")

    print()

    if non_matrix:
        print(f"  ({len(non_matrix)} non-matrix pair(s) not shown — use --compare)")
        print()


def main() -> None:
    args = sys.argv[1:]
    compare_mode = "--compare" in args
    matrix_mode = "--matrix" in args
    args = [a for a in args if a not in ("--compare", "--matrix")]

    if not args:
        target = Path(".test-output/logs")
    else:
        target = Path(args[0])

    if matrix_mode:
        log_dir = target if target.is_dir() else target.parent
        pairs = find_pairs(log_dir)
        print_log_matrix(pairs)
        return

    if compare_mode:
        log_dir = target if target.is_dir() else target.parent
        pairs = find_pairs(log_dir)
        print_comparison(pairs)
        return

    if target.is_file():
        session = parse_log(target.read_text())
        print_session_report(target.name, session)
    elif target.is_dir():
        log_files = sorted(target.glob("*.log"))
        if not log_files:
            print(f"No .log files found in {target}", file=sys.stderr)
            sys.exit(1)
        for lf in log_files:
            session = parse_log(lf.read_text())
            print_session_report(lf.name, session)
    else:
        print(f"Path not found: {target}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

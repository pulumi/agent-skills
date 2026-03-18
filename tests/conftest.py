"""Pytest configuration for agent-skills drift adoption tests."""

import os
import pathlib
import time

import pytest

from anthropic_agent import Agent
from claude_code_agent import ClaudeCodeAgent
from metrics import TestMetrics, format_summary_table, read_metrics, write_metrics
from sandbox_config import build_sandbox_config

# Collect metrics from all tests for the terminal summary.
# NOTE: When running with pytest-xdist (-n), workers run in separate processes
# so this list will only contain metrics from the local process. The terminal
# summary falls back to reading metrics JSON files from --metrics-output.
_collected_metrics: list[TestMetrics] = []


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--log-messages",
        action="store",
        default=None,
        help="Directory to write agent message logs to (one file per test).",
    )
    parser.addoption(
        "--metrics-output",
        action="store",
        default=None,
        help="Directory to write per-test metrics JSON files.",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Resolve output paths to absolute before test_temp_dir changes cwd."""
    for opt in ("log_messages", "metrics_output"):
        val = config.getoption(opt, default=None)
        if val is not None:
            config.option.__dict__[opt] = str(pathlib.Path(val).resolve())


def pytest_collection_modifyitems(
    session: pytest.Session,
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Clear metrics files only for tests that will run in this session.

    This preserves metrics from other test suites (e.g. a prior run is not
    wiped when you later run a different subset of tests).
    """
    metrics_dir = config.getoption("--metrics-output", default=None)
    if metrics_dir is None:
        return
    d = pathlib.Path(metrics_dir)
    if not d.is_dir():
        return
    collected = {item.name for item in items}
    for f in d.glob("*.json"):
        if f.stem in collected:
            f.unlink(missing_ok=True)


@pytest.fixture()
def testdata_dir() -> pathlib.Path:
    return pathlib.Path(__file__).parent / "data"


@pytest.fixture()
def skill_md_content() -> str:
    """Load SKILL.md content from the authoring directory."""
    skill_path = (
        pathlib.Path(__file__).resolve().parent.parent
        / "authoring"
        / "skills"
        / "pulumi-adopt-drift"
        / "SKILL.md"
    )
    if not skill_path.exists():
        pytest.skip(f"SKILL.md not found at {skill_path}")
    return skill_path.read_text()


@pytest.fixture()
def message_log_path(request: pytest.FixtureRequest) -> pathlib.Path | None:
    """Return a file path to log agent messages, or None if --log-messages not set."""
    log_dir = request.config.getoption("--log-messages")
    if log_dir is None:
        return None
    log_dir_path = pathlib.Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)
    test_name = request.node.name
    return log_dir_path / f"{test_name}.log"


def _make_claude_code_agent(
    message_log_path: pathlib.Path | None,
    skill_md_content: str | None = None,
    baseline: bool = False,
) -> ClaudeCodeAgent:
    """Create a ClaudeCodeAgent with optional skill instructions.

    When baseline=True, the Skill tool and drift-adopter CLI are blocked
    to prevent the agent from discovering tools it shouldn't have access to.

    All tests run inside an srt sandbox (OS-level isolation) and with
    permission rules that block GitHub access. Baseline tests get additional
    deny rules for the drift-adopter CLI.
    """
    sandbox, settings_json = build_sandbox_config(baseline=baseline)

    disallowed_tools: list[str] = []
    custom_instructions: str | None = None
    if baseline:
        # Block the Skill tool (full tool-name match works reliably).
        disallowed_tools = ["Skill"]
        custom_instructions = (
            "IMPORTANT: Stay within the project directory you are given. "
            "Do not browse, search, or read files from sibling directories, parent directories, "
            "or other test fixtures. Only use the project directory and pulumi CLI output."
        )

    agent_instance = ClaudeCodeAgent(
        message_log_path=message_log_path,
        env={
            "PULUMI_ACCESS_TOKEN": os.getenv("PULUMI_ACCESS_TOKEN", ""),
            "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN", ""),
        },
        disallowed_tools=disallowed_tools,
        sandbox=sandbox,
        settings_json=settings_json,
    )
    if skill_md_content:
        agent_instance.custom_instructions = skill_md_content
    elif custom_instructions:
        agent_instance.custom_instructions = custom_instructions
    return agent_instance


@pytest.fixture()
def agent(skill_md_content: str, message_log_path: pathlib.Path | None) -> Agent:
    """Claude Code agent with drift adoption skill loaded."""
    return _make_claude_code_agent(message_log_path, skill_md_content)


@pytest.fixture()
def agent_no_skill(message_log_path: pathlib.Path | None) -> Agent:
    """Claude Code agent without drift adoption skill — for baseline comparison.

    The Skill tool and drift-adopter CLI are blocked to prevent the baseline
    agent from discovering advantages it shouldn't have access to.
    """
    return _make_claude_code_agent(message_log_path, baseline=True)


@pytest.fixture(autouse=True)
def test_temp_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    os.chdir(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# Metrics support
# ---------------------------------------------------------------------------


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> None:  # type: ignore[type-arg]
    """Stash the test outcome on the request node so the fixture can read it."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"_report_{rep.when}", rep)


@pytest.fixture()
def test_metrics(request: pytest.FixtureRequest) -> TestMetrics:
    """Provide a TestMetrics instance; finalise timing and write JSON on teardown."""
    metrics = TestMetrics(test_name=request.node.name)
    t0 = time.perf_counter()

    yield metrics  # type: ignore[misc]

    metrics.total_time_s = time.perf_counter() - t0

    # Determine pass/fail from the stashed report.
    call_report = getattr(request.node, "_report_call", None)
    metrics.success = call_report is not None and call_report.passed

    _collected_metrics.append(metrics)

    metrics_dir = request.config.getoption("--metrics-output")
    if metrics_dir is not None:
        write_metrics(metrics, pathlib.Path(metrics_dir))


def pytest_keyboard_interrupt(excinfo: pytest.ExceptionInfo) -> None:  # type: ignore[type-arg]
    """Attempt graceful stack cleanup on Ctrl+C."""
    from stack_registry import cleanup_all

    cleaned = cleanup_all()
    if cleaned:
        print(f"\n[cleanup] Destroyed {cleaned} stack(s) on keyboard interrupt")


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter,
    exitstatus: int,
    config: pytest.Config,
) -> None:
    """Print a metrics summary table at the end of the test run.

    When running with xdist (-n), in-memory _collected_metrics will be empty on
    the controller.  Fall back to reading the per-test JSON files written to the
    --metrics-output directory, filtered to only tests collected in this session.
    """
    metrics = list(_collected_metrics)

    # If no in-memory metrics (e.g. xdist controller), try loading from disk.
    if not metrics:
        metrics_dir = config.getoption("--metrics-output", default=None)
        if metrics_dir is not None:
            all_metrics = read_metrics(pathlib.Path(metrics_dir))
            # Filter to only tests that ran in this session.
            collected: set[str] = set()
            for key in ("passed", "failed", "error"):
                for report in terminalreporter.stats.get(key, []):
                    # xdist reports use head_line; regular reports use nodeid
                    name = getattr(report, "head_line", "") or report.nodeid
                    # Extract test name (last component, e.g. "test_foo[param]")
                    if "::" in name:
                        name = name.rsplit("::", 1)[-1]
                    collected.add(name)
            if collected:
                metrics = [m for m in all_metrics if m.test_name in collected]
            else:
                metrics = all_metrics

    if not metrics:
        return
    table = format_summary_table(metrics)
    if table:
        terminalreporter.write_line("")
        terminalreporter.write_line("====== Metrics Summary ======")
        for line in table.split("\n"):
            terminalreporter.write_line(line)

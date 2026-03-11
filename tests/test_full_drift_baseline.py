"""
Baseline (no-skill) full-drift adoption integration tests.

Mirrors test_full_drift.py but uses agent_no_skill (no SKILL.md
custom_instructions) and a generic prompt. This measures raw LLM performance
for comparison against skill-assisted runs.

Unlike the skill-assisted tests, baseline tests do NOT require full drift
resolution. Instead they measure drift reduction: how many changes the agent
resolved vs how many it started with.
"""

import pytest
import utils
from drift_adoption_helpers import (
    build_drift_prompt,
    count_drift_changes,
    create_drift_with_program,
    drift_test_context,
    get_total_resource_count,
    scrub_drifted_dirs,
    verify_drift_exists,
)
from metrics import TestMetrics

from anthropic_agent import Agent

FULL_DRIFT_CONFIGS = [
    pytest.param("full-drift-50", 50, id="scale-50"),
    pytest.param("full-drift-100", 100, id="scale-100"),
    pytest.param("full-drift-200", 200, id="scale-200"),
    pytest.param("full-drift-400", 400, id="scale-400"),
    pytest.param("full-drift-800", 800, id="scale-800"),
]


@pytest.mark.integration
@pytest.mark.write_permissions
@pytest.mark.full_drift
@pytest.mark.baseline
@pytest.mark.parametrize("example_name,expected_resources", FULL_DRIFT_CONFIGS)
async def test_full_drift_baseline(
    agent_no_skill: Agent,
    test_metrics: TestMetrics,
    example_name: str,
    expected_resources: int,
) -> None:
    """
    Baseline full-drift adoption test (no skill loaded).

    Measures drift reduction rather than requiring full resolution.
    The baseline captures how well raw Claude handles all-creates drift
    so we can compare against skill-assisted runs.
    """
    with drift_test_context(example_name, skip_esc=True) as ctx:
        # Step 1: Deploy original code (empty program — no resources)
        ctx.program.up()
        test_metrics.resource_count = get_total_resource_count(ctx.program)

        # Step 2: Create drift (deploys drifted code with N resources, then reverts to empty)
        create_drift_with_program(ctx.program, ctx.example_dir)
        test_metrics.resource_count = get_total_resource_count(ctx.program)
        verify_drift_exists(ctx.program)

        # Measure initial drift count before agent runs
        test_metrics.initial_drift_count = count_drift_changes(ctx.program)

        # Remove drifted/ dirs so the agent can't cheat by reading the answers
        scrub_drifted_dirs(ctx.working_dir)

        # Step 3: Agent fixes drift (baseline prompt, no skill)
        agent_no_skill.cwd = ctx.working_dir
        user_prompt = build_drift_prompt(ctx, include_instructions=True, baseline=True)
        agent_branches: list[str] = []
        result, _, agent_metrics = await utils.query_auto_approve(
            agent_no_skill, user_prompt, branch_collector=agent_branches, collect_metrics=True
        )
        ctx.agent_branches = agent_branches
        test_metrics.agent = agent_metrics

        # Step 4: Measure remaining drift (not a hard pass/fail assertion)
        ctx.program.update_source(str(ctx.example_dir))
        test_metrics.remaining_drift_count = count_drift_changes(ctx.program)

        # Baseline passes if the agent reduced drift at all (made some progress).
        assert test_metrics.remaining_drift_count < test_metrics.initial_drift_count, (
            f"Baseline agent made no progress: "
            f"{test_metrics.initial_drift_count} initial changes, "
            f"{test_metrics.remaining_drift_count} remaining"
        )

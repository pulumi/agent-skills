"""
Baseline (no-skill) small-scale drift adoption integration test.

Mirrors test_drift_adoption_small_scale.py but uses agent_no_skill (ClaudeCodeAgent
without skill) and a baseline prompt. This measures Claude Code's raw performance
for comparison against skill-assisted runs.

Verification is deterministic (preview-based).
"""

import pytest
import utils
from drift_adoption_helpers import (
    build_drift_prompt,
    create_drift_with_program,
    drift_test_context,
    get_total_resource_count,
    scrub_drifted_dirs,
    verify_drift_exists,
    verify_drift_resolved,
)
from metrics import TestMetrics

from anthropic_agent import Agent


@pytest.mark.integration
@pytest.mark.write_permissions
@pytest.mark.baseline
async def test_baseline_small_scale(
    agent_no_skill: Agent,
    test_metrics: TestMetrics,
) -> None:
    """Baseline small-scale drift adoption test (no skill loaded).

    Same as test_drift_adoption_small_scale but without SKILL.md custom instructions,
    using Claude Code (via claude-agent-sdk) instead of the minimal Anthropic wrapper.
    """
    with drift_test_context("small-scale-10", skip_esc=True) as ctx:
        ctx.program.up()
        test_metrics.resource_count = get_total_resource_count(ctx.program)

        create_drift_with_program(ctx.program, ctx.example_dir)
        test_metrics.resource_count = get_total_resource_count(ctx.program)
        verify_drift_exists(ctx.program)

        scrub_drifted_dirs(ctx.working_dir)

        # Set Claude Code's working directory to the worktree
        agent_no_skill.cwd = ctx.working_dir

        user_prompt = build_drift_prompt(ctx, include_instructions=True, baseline=True)
        agent_branches: list[str] = []
        result, _, agent_metrics = await utils.query_auto_approve(
            agent_no_skill, user_prompt, branch_collector=agent_branches, collect_metrics=True
        )
        ctx.agent_branches = agent_branches
        test_metrics.agent = agent_metrics

        ctx.program.update_source(str(ctx.example_dir))
        verify_drift_resolved(ctx.program)

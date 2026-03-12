"""
Small-scale drift adoption integration test (10 resources, local providers).

Tests agent performance with the drift adoption skill using local-only providers
(random, command, tls) — no cloud credentials required.

The fixture has ~15% drift distributed across 4 types:
  - Property changes (scattered)
  - Resource deletions
  - Resource creations (extra resources)
  - Clustered property changes
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
async def test_drift_adoption_small_scale(
    agent: Agent,
    test_metrics: TestMetrics,
) -> None:
    """Small-scale drift adoption test (10 resources, all 4 drift types)."""
    with drift_test_context("small-scale-10", skip_esc=True) as ctx:
        ctx.program.up()
        test_metrics.resource_count = get_total_resource_count(ctx.program)

        create_drift_with_program(ctx.program, ctx.example_dir)
        test_metrics.resource_count = get_total_resource_count(ctx.program)
        verify_drift_exists(ctx.program)

        scrub_drifted_dirs(ctx.working_dir)

        agent.cwd = ctx.working_dir
        user_prompt = build_drift_prompt(ctx, include_instructions=True)
        agent_branches: list[str] = []
        result, _, agent_metrics = await utils.query_auto_approve(
            agent, user_prompt, branch_collector=agent_branches, collect_metrics=True
        )
        ctx.agent_branches = agent_branches
        test_metrics.agent = agent_metrics

        ctx.program.update_source(str(ctx.example_dir))
        verify_drift_resolved(ctx.program)

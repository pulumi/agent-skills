"""
Large-scale drift adoption integration tests.

Tests agent performance across 250-1000 resources using local-only providers
(random, command, tls) — no cloud credentials required.

Each scale has ~15% drift distributed across 4 types:
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

LARGE_SCALE_CONFIGS = [
    pytest.param("large-scale-250", 250, id="scale-250"),
    pytest.param("large-scale-500", 500, id="scale-500"),
    pytest.param("large-scale-750", 750, id="scale-750"),
    pytest.param("large-scale-1000", 1000, id="scale-1000"),
]


@pytest.mark.integration
@pytest.mark.write_permissions
@pytest.mark.large_scale
@pytest.mark.parametrize("example_name,expected_resources", LARGE_SCALE_CONFIGS)
async def test_drift_adoption_large_scale(
    agent: Agent,
    test_metrics: TestMetrics,
    example_name: str,
    expected_resources: int,
) -> None:
    """
    Large-scale drift adoption test.

    Deploys N resources using local providers, creates ~15% drift across
    4 drift types, then asks the agent to resolve all drift.
    Verification is deterministic (preview-based), no llm_judge needed.
    """
    with drift_test_context(example_name, skip_esc=True) as ctx:
        # Step 1: Deploy original code
        ctx.program.up()
        test_metrics.resource_count = get_total_resource_count(ctx.program)

        # Step 2: Create drift (deploys drifted code, then reverts source)
        # After this: infra = drifted state, code = original
        # Drifted state has: property changes, deletions, AND extra resources
        create_drift_with_program(ctx.program, ctx.example_dir)
        test_metrics.resource_count = get_total_resource_count(ctx.program)
        verify_drift_exists(ctx.program)

        # Remove drifted/ dirs so the agent can't cheat by reading the answers
        scrub_drifted_dirs(ctx.working_dir)

        # Step 3: Agent fixes drift
        agent.cwd = ctx.working_dir
        user_prompt = build_drift_prompt(ctx, include_instructions=True)
        agent_branches: list[str] = []
        result, _, agent_metrics = await utils.query_auto_approve(
            agent, user_prompt, branch_collector=agent_branches, collect_metrics=True
        )
        ctx.agent_branches = agent_branches
        test_metrics.agent = agent_metrics

        # Step 4: Deterministic verification — no llm_judge needed at scale
        ctx.program.update_source(str(ctx.example_dir))
        verify_drift_resolved(ctx.program)

"""
Full-drift adoption integration tests (all creates).

Tests agent performance across 50-800 resources where the original code is an
empty Pulumi program and all resources show as "creates" in preview. The agent
must adopt every resource into code from scratch.

Uses local-only providers (random, command, tls) — no cloud credentials required.
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
@pytest.mark.parametrize("example_name,expected_resources", FULL_DRIFT_CONFIGS)
async def test_full_drift(
    agent: Agent,
    test_metrics: TestMetrics,
    example_name: str,
    expected_resources: int,
) -> None:
    """
    Full-drift adoption test (all creates).

    Deploys N resources using local providers with an empty original program,
    so all N resources appear as creates in preview. The agent must add every
    resource to code from scratch.
    Verification is deterministic (preview-based), no llm_judge needed.
    """
    with drift_test_context(example_name, skip_esc=True) as ctx:
        # Step 1: Deploy original code (empty program — no resources)
        ctx.program.up()
        test_metrics.resource_count = get_total_resource_count(ctx.program)

        # Step 2: Create drift (deploys drifted code with N resources, then reverts to empty)
        # After this: infra = N resources, code = empty program
        # All N resources show as "creates" in preview
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

"""
Complex drift adoption integration tests (skill-assisted).

Tests agent performance across 20-100 resources with high per-resource complexity:
  - 7+ resource types (not just 3)
  - Cross-resource references (cert chains, command triggers, random keepers)
  - Varied properties per instance (defeats trivial loop strategies)
  - Nested objects and arrays (subjects, allowedUses, dnsNames)
  - Realistic naming (web-ca-key, api-password, not cmd-0)

Uses local-only providers (random, command, tls) — no cloud credentials required.
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
    verify_drift_resolved,
)
from generate_complex_drift import generate_drifted_code
from metrics import TestMetrics

from anthropic_agent import Agent

COMPLEX_DRIFT_CONFIGS = [
    # Full drift (100%): empty original, all resources in drifted
    pytest.param("complex-20-full", 20, 100, id="scale-20-full"),
    pytest.param("complex-40-full", 40, 100, id="scale-40-full"),
    pytest.param("complex-60-full", 60, 100, id="scale-60-full"),
    pytest.param("complex-100-full", 100, 100, id="scale-100-full"),
    # 50% drift: half resources drifted (property changes, cascading deletions, creations)
    pytest.param("complex-20-50pct", 20, 50, id="scale-20-50pct"),
    pytest.param("complex-40-50pct", 40, 50, id="scale-40-50pct"),
    pytest.param("complex-60-50pct", 60, 50, id="scale-60-50pct"),
    pytest.param("complex-100-50pct", 100, 50, id="scale-100-50pct"),
    # 15% drift: light drift across multiple drift types
    pytest.param("complex-20-15pct", 20, 15, id="scale-20-15pct"),
    pytest.param("complex-40-15pct", 40, 15, id="scale-40-15pct"),
    pytest.param("complex-60-15pct", 60, 15, id="scale-60-15pct"),
    pytest.param("complex-100-15pct", 100, 15, id="scale-100-15pct"),
]


@pytest.mark.integration
@pytest.mark.write_permissions
@pytest.mark.complex_drift
@pytest.mark.parametrize("example_name,expected_resources,drift_pct", COMPLEX_DRIFT_CONFIGS)
async def test_complex_drift(
    agent: Agent,
    test_metrics: TestMetrics,
    example_name: str,
    expected_resources: int,
    drift_pct: int,
) -> None:
    """
    Complex drift adoption test (skill-assisted).

    Deploys N resources with high per-resource complexity (varied types,
    cross-references, nested objects), then asks the agent to adopt drift
    into code. For 100% drift, starts from empty original (pure adoption).
    For partial drift, original has all resources and drifted has mutations.
    Verification is deterministic (preview-based), no llm_judge needed.
    """
    with drift_test_context(example_name, skip_esc=True) as ctx:
        # Step 1: Deploy original code (empty program)
        ctx.program.up()
        test_metrics.resource_count = get_total_resource_count(ctx.program)

        # Step 2: Generate drifted code at runtime (never committed to git)
        drifted_dir = ctx.example_dir / "drifted"
        drifted_dir.mkdir(exist_ok=True)
        (drifted_dir / "index.ts").write_text(generate_drifted_code(expected_resources, drift_pct))

        # Deploy drifted code to create drift, then revert source
        # After this: infra = N complex resources, code = empty program
        create_drift_with_program(ctx.program, ctx.example_dir)
        test_metrics.resource_count = get_total_resource_count(ctx.program)
        verify_drift_exists(ctx.program)

        # Measure initial drift count before agent runs
        test_metrics.initial_drift_count = count_drift_changes(ctx.program)

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

        # Step 4: Deterministic verification — no llm_judge needed
        ctx.program.update_source(str(ctx.example_dir))
        test_metrics.remaining_drift_count = count_drift_changes(ctx.program)
        verify_drift_resolved(ctx.program)

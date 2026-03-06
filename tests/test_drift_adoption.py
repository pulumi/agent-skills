"""
Python integration test for drift adoption using pulumitest-python.

This test validates that the agent can successfully adopt infrastructure drift
using git worktrees for isolation and the latest PulumiProgram API.
"""

import pathlib

import pytest
import utils
from drift_adoption_helpers import (
    build_drift_prompt,
    create_drift_with_program,
    drift_test_context,
    evaluate_resource_deletion_drift,
    evaluate_simple_drift_adoption,
    verify_drift_exists,
    verify_resource_count_in_state,
    verify_resource_property_in_state,
)
from pulumi.automation.events import OpType

from anthropic_agent import Agent


def get_drift_adoption_examples() -> pathlib.Path:
    """Get the path to drift adoption examples."""
    test_dir = pathlib.Path(__file__).parent
    # In agent-skills, examples are siblings in tests/drift-adoption/
    examples_dir = test_dir / "drift-adoption"

    if not examples_dir.exists():
        pytest.skip(
            f"Drift adoption examples not found at {examples_dir}. "
            "Examples should be in the tests/drift-adoption/ directory."
        )

    return examples_dir


@pytest.mark.integration
@pytest.mark.write_permissions
async def test_drift_adoption_simple_s3(agent: Agent) -> None:
    """
    Integration test for drift adoption using Python pulumitest.

    This test:
    1. Deploys a simple S3 bucket
    2. Creates drift by modifying tags
    3. Asks the agent to detect and fix the drift
    4. Validates the agent correctly adopted the drift using llm_judge
    """
    examples_dir = get_drift_adoption_examples()
    example_dir = examples_dir / "simple-s3"

    if not example_dir.exists():
        pytest.skip(f"Example directory not found: {example_dir}")

    # Use context manager for complete lifecycle management
    with drift_test_context("simple-s3") as ctx:
        # Step 1: Deploy initial stack
        ctx.program.up()

        # Verify state: should have 1 bucket with no tags initially
        verify_resource_count_in_state(
            ctx.program, "aws:s3/bucket:Bucket", expected_count=1
        )
        verify_resource_property_in_state(
            ctx.program, "aws:s3/bucket:Bucket", "inputs.tags", should_exist=False
        )

        # Step 2: Create drift using drifted program (adds tags)
        create_drift_with_program(ctx.program, ctx.example_dir)

        # Step 3: Verify drift exists via state - tags should now exist
        verify_resource_count_in_state(
            ctx.program, "aws:s3/bucket:Bucket", expected_count=1
        )
        verify_resource_property_in_state(
            ctx.program, "aws:s3/bucket:Bucket", "inputs.tags", should_exist=True
        )

        # Preview should show UPDATE (code has no tags, infrastructure has tags)
        update_count, replace_count = verify_drift_exists(ctx.program)
        assert update_count > 0 or replace_count > 0, "Should have changes detected"

        # Step 4: Ask agent to fix drift
        user_prompt = build_drift_prompt(ctx, include_instructions=True)
        agent_branches: list[str] = []
        result, _ = await utils.query_auto_approve(
            agent, user_prompt, branch_collector=agent_branches
        )
        ctx.agent_branches = agent_branches

        # Step 5: Verify drift was successfully adopted using llm_judge
        # Note: Agent verifies drift resolution with its own preview before returning
        judge_result = evaluate_simple_drift_adoption(
            result, "Environment tag", "production"
        )
        assert judge_result.answer, (
            f"Agent failed to successfully adopt drift.\n\n"
            f"Reasoning: {judge_result.reasoning}"
        )

    # Cleanup is automatic via context manager


@pytest.mark.integration
@pytest.mark.write_permissions
async def test_drift_adoption_multi_resource(agent: Agent) -> None:
    """
    Integration test for multi-resource drift adoption.

    Tests handling of drift where one resource is deleted from infrastructure
    but still exists in code. Agent should remove it from code.
    """
    examples_dir = get_drift_adoption_examples()
    example_dir = examples_dir / "multi-resource"

    if not example_dir.exists():
        pytest.skip(f"Example directory not found: {example_dir}")

    # Use context manager for complete lifecycle management
    with drift_test_context("multi-resource") as ctx:
        # Step 1: Deploy initial stack - should have 3 buckets
        ctx.program.up()
        verify_resource_count_in_state(
            ctx.program, "aws:s3/bucket:Bucket", expected_count=3
        )

        # Step 2: Create drift (deploys drifted version without bucket-b)
        create_drift_with_program(ctx.program, ctx.example_dir)

        # Step 3: Verify drift exists via state (bucket-b was deleted)
        verify_resource_count_in_state(
            ctx.program, "aws:s3/bucket:Bucket", expected_count=2
        )

        # Preview should show CREATE for bucket-b (code has it, infrastructure doesn't)
        preview_result = ctx.program.preview()
        create_count = preview_result.change_summary.get(OpType.CREATE, 0)
        assert create_count > 0, (
            "Should have create operations (bucket-b is in code but not in infrastructure)"
        )

        # Step 4: Ask agent to fix drift
        user_prompt = build_drift_prompt(ctx, include_instructions=True)
        agent_branches: list[str] = []
        result, _ = await utils.query_auto_approve(
            agent, user_prompt, branch_collector=agent_branches
        )
        ctx.agent_branches = agent_branches

        # Step 5: Use llm_judge for overall evaluation
        # Note: Agent verifies drift resolution with its own preview before returning
        judge_result = evaluate_resource_deletion_drift(result, "bucket-b")
        assert judge_result.answer, (
            f"Agent failed to correctly handle resource deletion.\n\n"
            f"Reasoning: {judge_result.reasoning}"
        )

    # Cleanup is automatic via context manager


@pytest.mark.integration
@pytest.mark.write_permissions
async def test_drift_adoption_loop_resources(agent: Agent) -> None:
    """
    Integration test for loop-based resource drift adoption.

    Tests handling of drift where a resource created in a loop is deleted
    from infrastructure. Agent should remove it from the array that drives the loop.
    """
    examples_dir = get_drift_adoption_examples()
    example_dir = examples_dir / "loop-resources"

    if not example_dir.exists():
        pytest.skip(f"Example directory not found: {example_dir}")

    # Use context manager for complete lifecycle management
    with drift_test_context("loop-resources") as ctx:
        # Step 1: Deploy initial stack with 3 buckets created from array
        ctx.program.up()
        verify_resource_count_in_state(
            ctx.program, "aws:s3/bucket:Bucket", expected_count=3
        )

        # Step 2: Create drift (deploys drifted version without data-bucket)
        create_drift_with_program(ctx.program, ctx.example_dir)

        # Step 3: Verify drift exists via state (data-bucket was deleted)
        verify_resource_count_in_state(
            ctx.program, "aws:s3/bucket:Bucket", expected_count=2
        )

        # Preview should show CREATE for data-bucket (code has it, infrastructure doesn't)
        preview_result = ctx.program.preview()
        create_count = preview_result.change_summary.get(OpType.CREATE, 0)
        assert create_count > 0, (
            "Should have create operations (data-bucket is in code but not in infrastructure)"
        )

        # Step 4: Ask agent to fix drift
        user_prompt = build_drift_prompt(ctx, include_instructions=True)
        agent_branches: list[str] = []
        result, _ = await utils.query_auto_approve(
            agent, user_prompt, branch_collector=agent_branches
        )
        ctx.agent_branches = agent_branches

        # Step 5: Use llm_judge for overall evaluation
        # Note: Agent verifies drift resolution with its own preview before returning
        judge_result = evaluate_resource_deletion_drift(result, "data-bucket")
        assert judge_result.answer, (
            f"Agent failed to correctly handle loop-based resource deletion.\n\n"
            f"Reasoning: {judge_result.reasoning}"
        )

    # Cleanup is automatic via context manager

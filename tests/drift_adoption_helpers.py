"""
Helper utilities for drift adoption integration tests.

This module provides reusable components for testing drift adoption capabilities:
- Git worktree management for isolated test environments
- Test context management with automatic cleanup
- Drift creation and verification
- Agent prompt building
- Evaluation helpers with llm_judge integration
"""

import os
import pathlib
import random
import shutil
import string
import subprocess
import tempfile
import uuid
import warnings
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from llm_judge import LLMJudgeBooleanResult
from pulumi.automation.events import OpType
from pulumitest import PulumiProgram
from pulumitest.opttest import stack_name as stack_name_option, use_ambient_backend

# ============================================================================
# Custom Exceptions
# ============================================================================


class GitWorktreeError(Exception):
    """Raised when git worktree operations fail."""

    pass


class DriftCreationError(Exception):
    """Raised when drift creation fails."""

    pass


# ============================================================================
# Git Worktree Management
# ============================================================================


@dataclass
class WorktreeContext:
    """Context for a git worktree created for testing."""

    path: pathlib.Path
    branch_name: str
    base_branch: str
    repo_root: pathlib.Path
    cleanup_required: bool = True


def create_worktree(
    base_branch: str, repo_root: Path, temp_dir: Optional[Path] = None
) -> WorktreeContext:
    """
    Create a git worktree in a temporary directory for isolated testing.

    Creates a new branch from base_branch and checks it out in an external
    temp directory (typically /tmp/drift-test-*).

    Args:
        base_branch: The branch to base the new worktree branch on
        repo_root: The git repository root directory
        temp_dir: Optional temp directory to use (defaults to system temp)

    Returns:
        WorktreeContext with path and branch information

    Raises:
        GitWorktreeError: If worktree creation fails
    """
    # Generate random branch name
    random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    branch_name = f"test-{random_suffix}"

    # Create temp directory for worktree
    if temp_dir is None:
        temp_path = Path(tempfile.mkdtemp(prefix="drift-test-")).resolve()
    else:
        temp_path = temp_dir / f"drift-test-{random_suffix}"
        temp_path.mkdir(parents=True, exist_ok=True)

    worktree_path = temp_path / "worktree"

    try:
        # Create worktree with new branch
        subprocess.run(
            [
                "git",
                "worktree",
                "add",
                "-b",
                branch_name,
                str(worktree_path),
                base_branch,
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )

        return WorktreeContext(
            path=worktree_path,
            branch_name=branch_name,
            base_branch=base_branch,
            repo_root=repo_root,
        )

    except subprocess.CalledProcessError as e:
        # Cleanup temp dir if worktree creation failed
        try:
            shutil.rmtree(temp_path)
        except OSError:
            # Ignore cleanup errors to propagate the original error
            pass
        raise GitWorktreeError(
            f"Failed to create worktree: {e.stderr or e.stdout}"
        ) from e


def cleanup_worktree(context: WorktreeContext) -> None:
    """
    Clean up a git worktree and its temporary directory.

    Args:
        context: The WorktreeContext to clean up

    Note:
        Issues warnings instead of raising exceptions to ensure cleanup
        attempts don't fail test teardown.
    """
    if not context.cleanup_required:
        return

    # Remove worktree
    try:
        subprocess.run(
            ["git", "worktree", "remove", str(context.path), "--force"],
            cwd=context.repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        warnings.warn(
            f"Failed to remove worktree {context.path}: {e.stderr or e.stdout}"
        )

    # Remove temp directory
    temp_parent = context.path.parent
    try:
        if temp_parent.exists() and "drift-test-" in str(temp_parent):
            shutil.rmtree(temp_parent)
    except OSError as e:
        warnings.warn(f"Failed to remove temp directory {temp_parent}: {e}")

    # Delete branch if it still exists
    try:
        subprocess.run(
            ["git", "branch", "-D", context.branch_name],
            cwd=context.repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        # Branch might not exist or already deleted, that's fine
        pass


@contextmanager
def worktree_context(
    base_branch: str, repo_root: Optional[Path] = None
) -> Generator[WorktreeContext, None, None]:
    """
    Context manager for git worktree lifecycle.

    Creates a worktree on enter and ensures cleanup on exit, even if
    exceptions occur.

    Args:
        base_branch: The branch to base the new worktree branch on
        repo_root: Optional git repository root (default: auto-detect)

    Yields:
        WorktreeContext for the created worktree

    Example:
        with worktree_context("main") as wt:
            # Work with worktree at wt.path
            pass
        # Worktree is automatically cleaned up
    """
    # Auto-detect repo root if not provided
    if repo_root is None:
        repo_root = _get_repo_root()

    context = create_worktree(base_branch, repo_root)
    try:
        yield context
    finally:
        cleanup_worktree(context)


def ensure_https_remote(working_dir: Path) -> None:
    """
    Ensure the git remote uses HTTPS instead of SSH.

    This is required for the agent to be able to push to the remote without
    SSH key configuration.

    Args:
        working_dir: The git repository directory

    Raises:
        GitWorktreeError: If remote URL cannot be changed
    """
    try:
        # Get current remote URL
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=working_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        current_url = result.stdout.strip()

        # Convert SSH to HTTPS if needed
        if current_url.startswith("git@github.com:"):
            https_url = current_url.replace(
                "git@github.com:", "https://github.com/"
            ).replace(".git", "")
            if not https_url.endswith(".git"):
                https_url += ".git"

            subprocess.run(
                ["git", "remote", "set-url", "origin", https_url],
                cwd=working_dir,
                capture_output=True,
                text=True,
                check=True,
            )

    except subprocess.CalledProcessError as e:
        raise GitWorktreeError(
            f"Failed to update remote URL: {e.stderr or e.stdout}"
        ) from e


# ============================================================================
# Test Context Management
# ============================================================================


def _get_repo_root() -> Path:
    """
    Get the root of the agents-test-fixtures git repository.

    Returns:
        Path to the repository root

    Raises:
        GitWorktreeError: If the repo root cannot be determined
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        raise GitWorktreeError(
            f"Failed to determine repo root: {e.stderr or e.stdout}"
        ) from e


def _copy_stack_config(example_dir: Path, stack_name: str) -> None:
    """
    Copy the static Pulumi.test.yaml to Pulumi.<stack_name>.yaml so that
    CLI commands pick up the ESC environment for dynamically-named stacks.

    Copies to both the example dir and its drifted/ subdir (if present).
    """
    source = example_dir / "Pulumi.test.yaml"
    if not source.exists():
        return
    dest = example_dir / f"Pulumi.{stack_name}.yaml"
    shutil.copy2(source, dest)

    drifted_source = example_dir / "drifted" / "Pulumi.test.yaml"
    if drifted_source.exists():
        drifted_dest = example_dir / "drifted" / f"Pulumi.{stack_name}.yaml"
        shutil.copy2(drifted_source, drifted_dest)


def _scrub_worktree(worktree_path: Path) -> None:
    """
    Remove test evidence from the worktree so the agent cannot read test
    files and derive expected answers.

    Keeps only:
    - .git/              (needed for git operations)
    - tests/drift-adoption/  (the actual Pulumi fixture programs)
    - authoring/         (contains SKILL.md)
    """
    for entry in sorted(worktree_path.iterdir()):
        rel = entry.name
        # Always keep .git
        if rel == ".git":
            continue
        # Keep authoring/ directory
        if rel == "authoring":
            continue
        # For tests/, selectively keep only drift-adoption/
        if rel == "tests" and entry.is_dir():
            for test_entry in sorted(entry.iterdir()):
                if test_entry.name == "drift-adoption":
                    continue
                if test_entry.is_dir():
                    shutil.rmtree(test_entry)
                else:
                    test_entry.unlink()
            continue
        # Remove everything else
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def _rmtree_onerror(func, path, exc_info):
    """Handle permission errors during rmtree by chmod and retry."""
    import stat

    os.chmod(path, stat.S_IRWXU)
    func(path)


def scrub_drifted_dirs(worktree_path: Path) -> None:
    """Remove all drifted/ subdirs from the worktree so the agent cannot
    read the expected answers.

    Must be called AFTER create_drift_with_program() and verify_drift_exists()
    have completed, but BEFORE the agent is invoked.
    """
    drift_adoption_dir = worktree_path / "tests" / "drift-adoption"
    if not drift_adoption_dir.is_dir():
        return
    for example_entry in drift_adoption_dir.iterdir():
        drifted_subdir = example_entry / "drifted"
        if drifted_subdir.is_dir():
            shutil.rmtree(drifted_subdir, onerror=_rmtree_onerror)
            if drifted_subdir.exists():
                raise RuntimeError(f"Failed to remove {drifted_subdir}")


@dataclass
class DriftTestContext:
    """Complete context for a drift adoption test."""

    program: PulumiProgram
    example_dir: pathlib.Path
    working_dir: pathlib.Path
    worktree: WorktreeContext
    stack_name: str
    skip_esc: bool = False
    agent_branches: list[str] = field(default_factory=list)


def setup_drift_test(
    example_name: str,
    stack_name: str | None = None,
    base_branch: Optional[str] = None,
    skip_esc: bool = False,
) -> DriftTestContext:
    """
    Set up a complete drift test environment.

    Creates a worktree from the agents-test-fixtures repo, initializes PulumiProgram,
    and prepares the test environment with ESC configuration.

    Args:
        example_name: Name of the example directory in drift-adoption/
        stack_name: Name of the Pulumi stack (default: auto-generated unique name)
        base_branch: Branch to base worktree on (default: current branch)
        skip_esc: If True, skip ESC environment setup (for local-only providers)

    Returns:
        DriftTestContext with all necessary components

    Raises:
        GitWorktreeError: If worktree creation fails
    """
    if stack_name is None:
        stack_name = f"test-{uuid.uuid4().hex[:8]}"

    repo_root = _get_repo_root()

    # Determine base branch from the current repo
    if base_branch is None:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        base_branch = result.stdout.strip()
        # Handle detached HEAD state (common in CI)
        if not base_branch:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "origin/HEAD"],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                base_branch = result.stdout.strip().replace("origin/", "")
            else:
                base_branch = "main"

    # Create worktree from agents-test-fixtures repo
    worktree = create_worktree(base_branch, repo_root)

    # Ensure HTTPS remote
    ensure_https_remote(worktree.path)

    # Remove test evidence so the agent can't cheat by reading test files
    _scrub_worktree(worktree.path)

    # Get example directory within the worktree
    # In agent-skills, examples are under tests/drift-adoption/
    example_dir = worktree.path / "tests" / "drift-adoption" / example_name

    # Initialize PulumiProgram with Pulumi Cloud backend
    program = PulumiProgram(
        str(example_dir),
        stack_name_option(stack_name),
        use_ambient_backend(),  # Use Pulumi Cloud backend
    )

    # Add ESC environment for AWS credentials (skip if already available via OIDC in CI)
    if not skip_esc and not os.environ.get("AWS_SESSION_TOKEN"):
        program.add_environments("default/dev-sandbox")

        # Copy the static Pulumi.test.yaml (which contains the ESC env reference)
        # to match the dynamic stack name so CLI commands also pick it up.
        _copy_stack_config(example_dir, stack_name)

    # Copy installed node_modules to the worktree so the agent (and drift-adopter)
    # can run pulumi preview without needing to install dependencies first.
    installed_node_modules = Path(program.working_dir) / "node_modules"
    worktree_node_modules = example_dir / "node_modules"
    if installed_node_modules.is_dir() and not worktree_node_modules.exists():
        shutil.copytree(installed_node_modules, worktree_node_modules)

    return DriftTestContext(
        program=program,
        example_dir=example_dir,
        working_dir=worktree.path,
        worktree=worktree,
        stack_name=stack_name,
        skip_esc=skip_esc,
    )


def cleanup_remote_branches(repo_path: Path, branch_names: list[str]) -> None:
    """
    Delete remote branches created by the agent during tests.

    Args:
        repo_path: Path to a git repository (worktree or main repo)
        branch_names: List of branch names to delete from the remote

    Note:
        Issues warnings instead of raising exceptions so cleanup continues.
    """
    for branch_name in branch_names:
        try:
            subprocess.run(
                ["git", "push", "origin", "--delete", branch_name],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            warnings.warn(
                f"Failed to delete remote branch {branch_name}: {e.stderr or e.stdout}"
            )


def teardown_drift_test(context: DriftTestContext) -> None:
    """
    Clean up a drift test environment.

    Args:
        context: The DriftTestContext to clean up

    Note:
        Handles cleanup errors gracefully to avoid masking test failures.
    """
    # PulumiProgram has its own cleanup, but we need to ensure it happens
    # before we remove the worktree
    try:
        # Try to destroy the stack if it exists
        context.program.destroy()
    except Exception as e:  # noqa: BLE001 - Best effort cleanup
        warnings.warn(f"Failed to destroy stack during cleanup: {e}")

    # Clean up remote branches before removing the worktree (needs git context)
    if context.agent_branches:
        cleanup_remote_branches(context.working_dir, context.agent_branches)

    # Clean up worktree
    cleanup_worktree(context.worktree)


@contextmanager
def drift_test_context(
    example_name: str,
    stack_name: str | None = None,
    base_branch: Optional[str] = None,
    skip_esc: bool = False,
) -> Generator[DriftTestContext, None, None]:
    """
    Context manager for complete drift test lifecycle.

    Handles setup and teardown of all test components, ensuring cleanup
    even if the test fails.

    Args:
        example_name: Name of the example directory
        stack_name: Name of the Pulumi stack (default: auto-generated unique name)
        base_branch: Branch to base worktree on (default: current branch)
        skip_esc: If True, skip ESC environment setup (for local-only providers)

    Yields:
        DriftTestContext with all test components

    Example:
        with drift_test_context("complex-20-full") as ctx:
            ctx.program.up()
            # Run test
        # Automatic cleanup
    """
    from stack_registry import register, unregister

    context = setup_drift_test(example_name, stack_name, base_branch, skip_esc=skip_esc)
    register(context)
    try:
        yield context
    finally:
        teardown_drift_test(context)
        unregister(context)


# ============================================================================
# Drift Creation and Verification
# ============================================================================


def create_drift_with_program(program: PulumiProgram, example_dir: Path) -> None:
    """
    Create drift using source update method.

    This approach:
    1. Updates program source to drifted directory
    2. Deploys the drifted version (modifies infrastructure)
    3. Updates source back to original directory
    4. Now code doesn't match infrastructure = drift!

    Args:
        program: The PulumiProgram instance
        example_dir: Directory containing drifted/ subdirectory with modified code

    Raises:
        DriftCreationError: If drift creation fails
    """
    drifted_dir = example_dir / "drifted"
    if not drifted_dir.exists():
        raise DriftCreationError(f"drifted/ directory not found at {drifted_dir}")

    try:
        # Step 1: Update source to drifted program
        program.update_source(str(drifted_dir))

        # Step 2: Deploy drifted program (modifies infrastructure)
        program.up()

        # Step 3: Update source back to original program
        program.update_source(str(example_dir))

        # Now code doesn't match infrastructure = drift!

    except Exception as e:
        raise DriftCreationError(f"Failed to create drift: {e}") from e


def verify_drift_exists(program: PulumiProgram) -> tuple[int, int]:
    """
    Verify that drift exists in the stack.

    Runs pulumi preview and checks for changes.

    Args:
        program: The PulumiProgram instance

    Returns:
        Tuple of (update_count, replace_count) from preview

    Raises:
        DriftCreationError: If preview fails or no drift detected
    """
    try:
        preview_result = program.preview()

        create_count = preview_result.change_summary.get(OpType.CREATE, 0)
        update_count = preview_result.change_summary.get(OpType.UPDATE, 0)
        replace_count = preview_result.change_summary.get(OpType.REPLACE, 0)
        delete_count = preview_result.change_summary.get(OpType.DELETE, 0)

        if create_count == 0 and update_count == 0 and replace_count == 0 and delete_count == 0:
            raise DriftCreationError("No drift detected after creating drift")

        return (update_count, replace_count)

    except Exception as e:
        if isinstance(e, DriftCreationError):
            raise
        raise DriftCreationError(f"Failed to verify drift: {e}") from e


# ============================================================================
# Agent Prompt Building
# ============================================================================


def build_drift_prompt(
    context: DriftTestContext, include_instructions: bool = True, baseline: bool = False
) -> str:
    """
    Build a structured prompt for the agent to adopt drift.

    Args:
        context: The drift test context
        include_instructions: Whether to include detailed workflow instructions

    Returns:
        Formatted prompt string for the agent
    """
    # Get repository URL
    result = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        cwd=context.working_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    repo_url = result.stdout.strip()

    # Ensure HTTPS URL
    if repo_url.startswith("git@github.com:"):
        repo_url = repo_url.replace("git@github.com:", "https://github.com/")
    if not repo_url.endswith(".git"):
        repo_url += ".git"

    # Build prompt
    prompt_parts = [
        "My Pulumi stack has drifted from the code and I need to adopt the drift.",
        "",
        "I've set up a test environment with a git worktree:",
        f"Working directory: {context.working_dir}",
        f"Branch: {context.worktree.branch_name}",
        f"Pulumi project: {context.example_dir}",
        f"Stack: {context.stack_name}",
    ]

    prompt_parts.extend(
        [
            f"Repository: {repo_url}",
            "",
            "The stack has drifted - the infrastructure has been modified outside of Pulumi.",
        ]
    )

    if include_instructions:
        if baseline:
            instruction_parts = [
                "",
                "Please:",
                f"1. Navigate to the project directory: {context.example_dir}",
                "2. Run `pulumi refresh --yes` to sync the state with the actual infrastructure",
                "3. Run `pulumi preview` to detect what has drifted",
                "4. Modify the code to match the current infrastructure state",
                "5. Run `pulumi preview` again to verify there are no remaining changes",
                "",
                "IMPORTANT: This is a test. Do not create a pull request.",
            ]
        else:
            instruction_parts = [
                "",
                "Please:",
                f"1. Navigate to the project directory: {context.example_dir}",
                "2. Use the adopt-drift skill to detect and fix the drift",
                "",
                "IMPORTANT: This is a test. Do not create a pull request.",
            ]
        prompt_parts.extend(instruction_parts)

    return "\n".join(prompt_parts)


# ============================================================================
# Evaluation Helpers
# ============================================================================


def evaluate_simple_drift_adoption(
    response: str, expected_property: str, expected_value: str
) -> "LLMJudgeBooleanResult":
    """
    Evaluate the agent's response for simple drift adoption.

    Uses llm_judge to determine if the agent successfully adopted the drift.

    Args:
        response: Agent's response text
        expected_property: Name of the property that should be added (e.g., "Environment tag")
        expected_value: Value of the property (e.g., "production")

    Returns:
        LLMJudgeBooleanResult with answer and reasoning
    """
    from llm_judge import llm_judge_boolean

    evaluation_prompt = f"""
    Did the agent successfully adopt the drift by adding the {expected_property}?

    The agent MUST have used the drift-adopter CLI tool (e.g., `pulumi plugin run drift-adopter`).
    The drift-adopter tool handles detection, code modification, and verification internally.

    Look for evidence of:
    - Running the drift-adopter tool to detect and adopt drift
    - The {expected_property} with value '{expected_value}' being adopted into the code
    - A clean/successful status from the drift-adopter tool

    Note: Git operations (branch creation, push, PR) are NOT required for test environments.
    You may not see direct evidence of `pulumi preview` or `pulumi refresh` — the drift-adopter
    tool handles these internally, so their absence is expected.
    """

    return llm_judge_boolean(
        content=response,
        evaluation_prompt=evaluation_prompt,
    )


def evaluate_resource_deletion_drift(
    response: str, deleted_resource: str
) -> "LLMJudgeBooleanResult":
    """
    Evaluate the agent's response for resource deletion drift.

    Args:
        response: Agent's response text
        deleted_resource: Name of the resource that should be removed (e.g., "bucket-b")

    Returns:
        LLMJudgeBooleanResult with answer and reasoning
    """
    from llm_judge import llm_judge_boolean

    evaluation_prompt = f"""
    Did the agent successfully adopt the drift by removing {deleted_resource}?

    The agent MUST have used the drift-adopter CLI tool (e.g., `pulumi plugin run drift-adopter`).
    The drift-adopter tool handles detection, code modification, and verification internally.

    Look for evidence of:
    - Running the drift-adopter tool to detect and adopt drift
    - The {deleted_resource} resource being removed from the code
    - A clean/successful status from the drift-adopter tool

    Note: Git operations (branch creation, push, PR) are NOT required for test environments.
    You may not see direct evidence of `pulumi preview` or `pulumi refresh` — the drift-adopter
    tool handles these internally, so their absence is expected.
    """

    return llm_judge_boolean(
        content=response,
        evaluation_prompt=evaluation_prompt,
    )


def verify_code_changes(working_dir: Path, expected_changes: dict[str, bool]) -> None:
    """
    Verify that expected code changes were made.

    Args:
        working_dir: The git repository directory
        expected_changes: Dict mapping strings to booleans indicating if they
                         should be present in the diff

    Raises:
        AssertionError: If expected changes are not found
    """
    # Get git diff
    result = subprocess.run(
        ["git", "diff", "HEAD~1", "HEAD"],
        cwd=working_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    diff = result.stdout

    for change, should_exist in expected_changes.items():
        if should_exist:
            assert change in diff, (
                f"Expected change '{change}' not found in diff:\n{diff}"
            )
        else:
            assert change not in diff, (
                f"Unexpected change '{change}' found in diff:\n{diff}"
            )


def count_drift_changes(program: "PulumiProgram") -> int:
    """Count the total number of pending changes (creates + updates + replaces + deletes).

    Returns 0 when drift is fully resolved.
    """
    preview_result = program.preview()
    return (
        preview_result.change_summary.get(OpType.CREATE, 0)
        + preview_result.change_summary.get(OpType.UPDATE, 0)
        + preview_result.change_summary.get(OpType.REPLACE, 0)
        + preview_result.change_summary.get(OpType.DELETE, 0)
    )


def verify_drift_resolved(program: "PulumiProgram") -> None:
    """
    Verify that drift has been resolved by running a preview.

    Runs a local preview and asserts that no changes are planned (no creates,
    updates, or replaces).

    Args:
        program: PulumiProgram instance

    Raises:
        AssertionError: If any changes are detected in the preview
    """
    preview_result = program.preview()
    create_count = preview_result.change_summary.get(OpType.CREATE, 0)
    update_count = preview_result.change_summary.get(OpType.UPDATE, 0)
    replace_count = preview_result.change_summary.get(OpType.REPLACE, 0)
    delete_count = preview_result.change_summary.get(OpType.DELETE, 0)

    assert (
        create_count == 0
        and update_count == 0
        and replace_count == 0
        and delete_count == 0
    ), (
        f"Drift should be resolved, but preview shows changes: "
        f"{create_count} creates, {update_count} updates, "
        f"{replace_count} replaces, {delete_count} deletes"
    )


def verify_resource_count_in_state(
    program: "PulumiProgram",
    resource_type: str,
    expected_count: int,
) -> None:
    """
    Verify resource count in Pulumi state.

    Args:
        program: PulumiProgram instance
        resource_type: Resource type to filter (e.g., "aws:s3/bucket:Bucket")
        expected_count: Expected number of resources

    Raises:
        AssertionError: If resource count doesn't match expected
    """
    assert program.current_stack is not None, "Stack not initialized"
    export_result = program.current_stack.export_stack()
    deployment = export_result.deployment
    assert deployment is not None, "No deployment in export"
    resources = deployment["resources"]
    matching_resources = [r for r in resources if r["type"] == resource_type]

    assert len(matching_resources) == expected_count, (
        f"Expected {expected_count} resources of type '{resource_type}' in state, "
        f"got {len(matching_resources)}"
    )


def verify_resource_property_in_state(
    program: "PulumiProgram",
    resource_type: str,
    property_path: str,
    expected_value: Any = None,
    should_exist: bool = True,
    resource_name: str | None = None,
) -> None:
    """
    Verify a property exists (or doesn't exist) in resources matching criteria.

    Args:
        program: PulumiProgram instance
        resource_type: Resource type to filter (e.g., "aws:s3/bucket:Bucket")
        property_path: Dot-separated path to property (e.g., "inputs.tags.Environment")
        expected_value: Expected value of property (None to just check existence)
        should_exist: Whether property should exist
        resource_name: Optional resource name to match (e.g., "bucket-a"). If None, checks all
                      resources of the given type.

    Raises:
        AssertionError: If property validation fails
    """
    assert program.current_stack is not None, "Stack not initialized"
    export_result = program.current_stack.export_stack()
    deployment = export_result.deployment
    assert deployment is not None, "No deployment in export"
    resources = deployment["resources"]

    # Filter by resource type
    matching_resources = [r for r in resources if r["type"] == resource_type]

    # Further filter by resource name if specified
    if resource_name is not None:
        # Match by logical name in URN (e.g., urn:pulumi:test::simple-s3::aws:s3/bucket:Bucket::bucket-a)
        matching_resources = [
            r
            for r in matching_resources
            if r.get("urn", "").endswith(f"::{resource_name}")
        ]
        assert len(matching_resources) > 0, (
            f"No resources found matching type '{resource_type}' and name '{resource_name}'"
        )

    # Verify property in all matching resources
    for resource in matching_resources:
        # Navigate property path
        value = resource
        path_parts = property_path.split(".")
        for part in path_parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = None
                break

        if should_exist:
            assert value is not None, (
                f"Property '{property_path}' should exist in resource but was not found. "
                f"Resource: {resource.get('urn', 'unknown')}"
            )
            if expected_value is not None:
                assert value == expected_value, (
                    f"Property '{property_path}' should be {expected_value}, "
                    f"but got {value}. Resource: {resource.get('urn', 'unknown')}"
                )
        else:
            assert value is None, (
                f"Property '{property_path}' should not exist but was found with value {value}. "
                f"Resource: {resource.get('urn', 'unknown')}"
            )


def get_total_resource_count(program: "PulumiProgram") -> int:
    """Count non-stack resources in current Pulumi state."""
    assert program.current_stack is not None, "Stack not initialized"
    export_result = program.current_stack.export_stack()
    deployment = export_result.deployment
    assert deployment is not None, "No deployment in export"
    resources = deployment["resources"]
    return len([r for r in resources if r["type"] != "pulumi:pulumi:Stack"])

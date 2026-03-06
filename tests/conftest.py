"""Pytest configuration for agent-skills drift adoption tests.

Simplified from agents-test-fixtures, supporting only AnthropicAgent.
"""

import os
import pathlib

import boto3
import boto3.exceptions
import pytest

from anthropic_agent import Agent, AnthropicAgent
from simple_shell_mcp import create_shell_mcp


@pytest.fixture()
def testdata_dir() -> pathlib.Path:
    return pathlib.Path(__file__).parent / "data"


@pytest.fixture()
def skill_md_content() -> str:
    """Load SKILL.md content from the operations directory."""
    skill_path = (
        pathlib.Path(__file__).resolve().parent.parent
        / "operations"
        / "skills"
        / "pulumi-adopt-drift"
        / "SKILL.md"
    )
    if not skill_path.exists():
        pytest.skip(f"SKILL.md not found at {skill_path}")
    return skill_path.read_text()


@pytest.fixture()
def agent(skill_md_content: str) -> Agent:
    """Create an AnthropicAgent with shell MCP and skill instructions."""
    # Check credentials
    if os.getenv("ANTHROPIC_API_KEY") is None:
        try:
            session = boto3.Session()
            credentials = session.get_credentials()
            if credentials is None:
                pytest.skip(
                    "AWS credentials required for Bedrock; set ANTHROPIC_API_KEY to use Anthropic API instead"
                )
        except boto3.exceptions.Boto3Error:
            pytest.skip(
                "AWS credentials required for Bedrock; set ANTHROPIC_API_KEY to use Anthropic API instead"
            )

    agent_instance = AnthropicAgent()

    pulumi_token = os.getenv("PULUMI_ACCESS_TOKEN", "")
    github_token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN", "")

    shell_mcp = create_shell_mcp(
        pulumi_access_token=pulumi_token,
        github_token=github_token,
    )

    agent_instance.mcp_servers = {"shell": shell_mcp}
    agent_instance.custom_instructions = skill_md_content

    return agent_instance


@pytest.fixture(autouse=True)
def test_temp_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    os.chdir(tmp_path)
    return tmp_path


@pytest.fixture(scope="session")
def aws_credentials() -> None:
    sts = boto3.client("sts")
    try:
        sts.get_caller_identity()
    except Exception:  # noqa: BLE001
        pytest.skip("AWS credentials are not available")

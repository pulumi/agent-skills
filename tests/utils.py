"""Test utilities for drift adoption integration tests.

Simplified from agents-test-fixtures, with only the functions needed
by the drift adoption tests.
"""

from anthropic_agent import Agent, AssistantMessage, ToolResponse


async def query_auto_approve(
    agent: Agent,
    prompt: str,
    branch_collector: list[str] | None = None,
) -> tuple[str, list]:
    last_message = None
    async for message in agent.query_stream(prompt):
        last_message = message
        if isinstance(message, ToolResponse) and branch_collector is not None:
            branch = extract_branch_from_tool_response(message)
            if branch is not None:
                branch_collector.append(branch)

    if last_message is None:
        raise ValueError("Expected a message, got None")

    if isinstance(last_message, AssistantMessage):
        return last_message.content, []

    return "", []


def extract_branch_from_tool_response(response: ToolResponse) -> str | None:
    """Extract an agent branch name from a Pulumi tool response."""
    if not response.name.startswith("pulumi_"):
        return None
    content = response.content
    if isinstance(content, dict):
        branch = content.get("branch_name")
        if isinstance(branch, str) and branch.startswith("neo-"):
            return branch
    return None

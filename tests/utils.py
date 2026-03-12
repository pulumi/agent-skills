"""Test utilities for drift adoption integration tests.

Simplified from agents-test-fixtures, with only the functions needed
by the drift adoption tests.
"""

from __future__ import annotations

import time

import psutil

from anthropic_agent import Agent, AssistantMessage, ToolResponse
from metrics import AgentMetrics


async def query_auto_approve(
    agent: Agent,
    prompt: str,
    branch_collector: list[str] | None = None,
    collect_metrics: bool = False,
) -> tuple[str, list, AgentMetrics | None]:
    last_message = None
    iterations = 0
    input_tokens = 0
    output_tokens = 0
    cache_creation_tokens = 0
    cache_read_tokens = 0

    if collect_metrics:
        process = psutil.Process()
        peak_rss = process.memory_info().rss
        t0 = time.perf_counter()

    async for message in agent.query_stream(prompt):
        last_message = message
        if isinstance(message, AssistantMessage):
            iterations += 1
            if collect_metrics:
                for usage in message.token_usage.values():
                    input_tokens += usage.input_tokens
                    output_tokens += usage.output_tokens
                    cache_creation_tokens += usage.cache_creation_input_tokens
                    cache_read_tokens += usage.cache_read_input_tokens
                current_rss = process.memory_info().rss
                if current_rss > peak_rss:
                    peak_rss = current_rss
        if isinstance(message, ToolResponse) and branch_collector is not None:
            branch = extract_branch_from_tool_response(message)
            if branch is not None:
                branch_collector.append(branch)

    # If the last AssistantMessage provided a num_turns_override (e.g. from
    # ClaudeCodeAgent's ResultMessage.num_turns), use it instead of the
    # accumulated iteration counter to avoid off-by-one from the result message.
    if isinstance(last_message, AssistantMessage) and last_message.num_turns_override is not None:
        iterations = last_message.num_turns_override

    agent_metrics: AgentMetrics | None = None
    if collect_metrics:
        agent_metrics = AgentMetrics(
            agent_time_s=time.perf_counter() - t0,
            iterations=iterations,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_tokens=cache_creation_tokens,
            cache_read_tokens=cache_read_tokens,
            peak_memory_bytes=peak_rss,
        )

    if last_message is None:
        raise ValueError("Expected a message, got None")

    if isinstance(last_message, AssistantMessage):
        return last_message.content, [], agent_metrics

    return "", [], agent_metrics


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

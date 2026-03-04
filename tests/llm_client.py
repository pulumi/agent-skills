"""
Shared Anthropic LLM client utilities.

Provides model name constants and a retry-aware wrapper around the Anthropic
messages API so callers don't have to duplicate retry logic.
"""

import asyncio
from dataclasses import dataclass
from typing import Any

import anthropic

HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-6"

MAX_ATTEMPTS = 3
RETRY_BASE_DELAY = 5.0  # seconds


@dataclass
class ToolCall:
    name: str
    input: dict[str, Any]


def get_tool_calls(response: anthropic.types.Message) -> list[ToolCall]:
    """Extract all tool-use blocks from a response as ToolCall objects."""
    return [
        ToolCall(name=block.name, input=block.input)  # type: ignore[arg-type]
        for block in response.content
        if block.type == "tool_use"
    ]


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code in (429, 500, 529)
    return isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError))


async def create_message(**kwargs: Any) -> anthropic.types.Message:
    """Call ``client.messages.create`` with exponential-backoff retry.

    All keyword arguments are forwarded directly to the Anthropic API.
    Transient errors (rate-limit, server errors, connection/timeout) are
    retried up to ``_MAX_ATTEMPTS`` times before re-raising.
    """
    async with anthropic.AsyncAnthropic() as client:
        for attempt in range(MAX_ATTEMPTS):
            try:
                return await client.messages.create(**kwargs)
            except BaseException as exc:
                if not _is_retryable(exc) or attempt == MAX_ATTEMPTS - 1:
                    raise
                await asyncio.sleep(RETRY_BASE_DELAY * (2**attempt))
    raise RuntimeError("unreachable")  # pragma: no cover

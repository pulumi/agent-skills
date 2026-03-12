"""Agent ABC and shared message types for testing."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Mapping


# ---------------------------------------------------------------------------
# Message types
# ---------------------------------------------------------------------------


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class AssistantMessage:
    content: str
    tool_calls: Any = None
    token_usage: dict[str, TokenUsage] = field(default_factory=dict)
    # Optional override for iteration count (used by ClaudeCodeAgent to report
    # ResultMessage.num_turns without inflating the count from query_auto_approve).
    num_turns_override: int | None = None


@dataclass
class ToolResponse:
    tool_call_id: str
    name: str
    content: str | dict
    is_error: bool = False


# Union of message types the agent can yield
AgentMessage = AssistantMessage | ToolResponse


# ---------------------------------------------------------------------------
# Agent ABC
# ---------------------------------------------------------------------------


class Agent(ABC):
    """Minimal agent protocol for testing."""

    @property
    @abstractmethod
    def mcp_servers(self) -> dict[str, Any]: ...

    @mcp_servers.setter
    @abstractmethod
    def mcp_servers(self, value: Mapping[str, Any]) -> None: ...

    @property
    @abstractmethod
    def custom_instructions(self) -> str | None: ...

    @custom_instructions.setter
    @abstractmethod
    def custom_instructions(self, value: str | None) -> None: ...

    @abstractmethod
    def cancel(self) -> None: ...

    @abstractmethod
    async def query(self, prompt: str) -> str: ...

    @abstractmethod
    def query_stream(self, prompt: str) -> AsyncGenerator[AgentMessage, None]: ...

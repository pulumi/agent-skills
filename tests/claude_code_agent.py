"""Claude Code agent adapter for baseline testing.

Wraps the claude-agent-sdk to implement the Agent ABC from anthropic_agent.py,
giving baseline tests access to real Claude Code (Read, Write, Edit, Glob, Grep,
Bash, etc.) without any skills loaded.
"""

import json
import logging
import pathlib
from typing import Any, AsyncGenerator, Mapping

from claude_agent_sdk import AssistantMessage as SdkAssistantMessage
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from claude_agent_sdk.types import TextBlock, ToolUseBlock

from anthropic_agent import (
    Agent,
    AgentMessage,
    AssistantMessage,
    TokenUsage,
    ToolResponse,
)

logger = logging.getLogger(__name__)


class ClaudeCodeAgent(Agent):
    """Agent adapter that runs actual Claude Code via claude-agent-sdk.

    Unlike AnthropicAgent (which is a minimal Anthropic SDK wrapper with a
    single shell_execute MCP tool), this runs the full Claude Code CLI with
    all built-in tools (Read, Write, Edit, Glob, Grep, Bash, etc.).

    Used for baseline tests to provide a fair "no skill + Claude Code" comparison
    against "skill + Claude Code".
    """

    def __init__(
        self,
        message_log_path: pathlib.Path | None = None,
        env: dict[str, str] | None = None,
        model: str | None = None,
        max_turns: int = 200,
        disallowed_tools: list[str] | None = None,
    ) -> None:
        self._message_log_path = message_log_path
        self._env = env or {}
        self._model = model
        self._max_turns = max_turns
        self._disallowed_tools = disallowed_tools or []
        self._cwd: str | None = None
        self._mcp_server_configs: dict[str, Any] = {}
        self._custom_instructions: str | None = None
        self._log_initialized = False

    @property
    def cwd(self) -> str | None:
        return self._cwd

    @cwd.setter
    def cwd(self, value: str | pathlib.Path | None) -> None:
        self._cwd = str(value) if value is not None else None

    @property
    def mcp_servers(self) -> dict[str, Any]:
        return self._mcp_server_configs

    @mcp_servers.setter
    def mcp_servers(self, value: Mapping[str, Any]) -> None:
        self._mcp_server_configs = dict(value)

    @property
    def custom_instructions(self) -> str | None:
        return self._custom_instructions

    @custom_instructions.setter
    def custom_instructions(self, value: str | None) -> None:
        self._custom_instructions = value

    def cancel(self) -> None:
        pass

    def _handle_stderr(self, line: str) -> None:
        """Capture stderr from the Claude Code CLI for debugging."""
        self._log("STDERR", line.rstrip())

    def _log(self, label: str, content: str) -> None:
        if self._message_log_path is None:
            return
        mode = "a"
        if not self._log_initialized:
            mode = "w"
            self._log_initialized = True
        with open(self._message_log_path, mode) as f:
            f.write(f"\n{'=' * 80}\n")
            f.write(f"[{label}]\n")
            f.write(f"{'=' * 80}\n")
            f.write(content)
            f.write("\n")

    def _build_options(self) -> ClaudeAgentOptions:
        system_prompt: Any = {
            "type": "preset",
            "preset": "claude_code",
            "append": "IMPORTANT: NEVER run `pulumi up` or `pulumi destroy`. These commands are forbidden.",
        }
        if self._custom_instructions:
            system_prompt["append"] += f"\n\n{self._custom_instructions}"

        # Unset CLAUDECODE to allow launching from within a Claude Code session
        # (e.g. when running tests interactively via Claude Code).
        env = {**self._env, "CLAUDECODE": ""}

        return ClaudeAgentOptions(
            system_prompt=system_prompt,
            permission_mode="bypassPermissions",
            setting_sources=None,  # No filesystem skills
            disallowed_tools=[
            "Bash(pulumi up)",
            "Bash(pulumi destroy)",
            *self._disallowed_tools,
        ],
            cwd=self._cwd,
            env=env,
            model=self._model,
            max_turns=self._max_turns,
            stderr=self._handle_stderr,
        )

    async def query(self, prompt: str) -> str:
        last_content = ""
        async for message in self.query_stream(prompt):
            if isinstance(message, AssistantMessage) and message.content:
                last_content = message.content
        return last_content

    async def query_stream(self, prompt: str) -> AsyncGenerator[AgentMessage, None]:
        """Run Claude Code via the SDK and yield messages matching the Agent ABC.

        The SDK yields per-turn AssistantMessages (no per-turn token breakdown)
        and a final ResultMessage with aggregated totals + num_turns.

        query_auto_approve counts iterations from AssistantMessage yields and
        accumulates token_usage from each one.  We yield one AssistantMessage
        per SDK turn (for correct iteration counts) with empty token_usage,
        plus one final AssistantMessage from ResultMessage carrying the
        aggregated token totals.  This adds +1 to the iteration count; we
        correct for that by storing num_turns on the final message.
        """
        options = self._build_options()
        self._log("PROMPT", prompt)
        self._log("OPTIONS", f"cwd={options.cwd}, model={options.model}")

        iteration = 0

        async for message in query(prompt=prompt, options=options):
            if isinstance(message, SdkAssistantMessage):
                iteration += 1
                text_parts = []
                tool_uses = []

                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)
                    elif isinstance(block, ToolUseBlock):
                        tool_uses.append(block)

                text_content = "\n".join(text_parts)

                if text_content:
                    self._log(f"ASSISTANT (iter {iteration})", text_content)
                for tu in tool_uses:
                    self._log(
                        f"TOOL_CALL (iter {iteration}): {tu.name}",
                        json.dumps(tu.input, indent=2)
                        if isinstance(tu.input, dict)
                        else str(tu.input),
                    )

                yield AssistantMessage(
                    content=text_content,
                    tool_calls=tool_uses if tool_uses else None,
                    token_usage={},
                )

                # Yield tool responses for branch extraction
                for tu in tool_uses:
                    yield ToolResponse(
                        tool_call_id=tu.id,
                        name=tu.name,
                        content="",  # SDK handles tool execution internally
                    )

            elif isinstance(message, ResultMessage):
                self._log(
                    "RESULT",
                    f"turns={message.num_turns} duration={message.duration_ms}ms "
                    f"cost=${message.total_cost_usd or 0:.4f} "
                    f"error={message.is_error}",
                )

                usage = message.usage or {}
                token_usage = TokenUsage(
                    input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                    cache_creation_input_tokens=usage.get(
                        "cache_creation_input_tokens", 0
                    ),
                    cache_read_input_tokens=usage.get("cache_read_input_tokens", 0),
                )

                yield AssistantMessage(
                    content=message.result or "",
                    tool_calls=None,
                    token_usage={"claude-code": token_usage},
                    num_turns_override=message.num_turns,
                )

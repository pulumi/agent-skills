"""Minimal Anthropic API agent for testing skills.

This agent uses the Anthropic SDK directly with MCP tool support.
Uses fastmcp.Client directly for MCP server communication.
"""

import json
import logging
import os
import pathlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Mapping

import anthropic
from fastmcp import Client as FastMCPClient
from fastmcp import FastMCP

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"
MAX_ITERATIONS = 50
MAX_TOKENS = 16000

SYSTEM_PROMPT = """You are an AI assistant that helps with cloud infrastructure tasks using Pulumi.
You have access to tools for running Pulumi commands, reading/writing files, and executing shell commands.
Use the tools available to you to complete the user's request."""


# ---------------------------------------------------------------------------
# Minimal message types (replaces agents_py.messages)
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


@dataclass
class ToolResponse:
    tool_call_id: str
    name: str
    content: str | dict
    is_error: bool = False


# Union of message types the agent can yield
AgentMessage = AssistantMessage | ToolResponse


# ---------------------------------------------------------------------------
# Minimal Agent ABC (replaces agents_py.agent.Agent)
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


# ---------------------------------------------------------------------------
# Inline MCP tool client (replaces agents_py.mcp_tool_client.MCPToolClient)
# ---------------------------------------------------------------------------


class InlineMCPToolClient:
    """Simplified MCP tool client that works with FastMCP instances directly."""

    def __init__(self, server_configs: dict[str, Any]) -> None:
        self._servers: dict[str, FastMCP] = {}
        self._clients: dict[str, FastMCPClient] = {}
        for name, config in server_configs.items():
            if isinstance(config, FastMCP):
                self._servers[name] = config

    async def get_tools(self) -> list[dict[str, Any]]:
        """Discover tools from all registered MCP servers."""
        all_tools: list[dict[str, Any]] = []
        for server_name, server in self._servers.items():
            client = FastMCPClient(server)
            self._clients[server_name] = client
            async with client:
                tools = await client.list_tools()
                for tool in tools:
                    all_tools.append({
                        "server_name": server_name,
                        "name": tool.name,
                        "description": tool.description or "",
                        "inputSchema": tool.inputSchema,
                    })
        return all_tools

    async def call_tool(
        self,
        tool_name: str,
        server_name: str,
        arguments: dict[str, Any],
    ) -> str:
        """Call a tool on the specified MCP server and return the result as a string."""
        server = self._servers.get(server_name)
        if server is None:
            raise ValueError(f"Unknown MCP server: {server_name}")

        client = FastMCPClient(server)
        async with client:
            result = await client.call_tool(tool_name, arguments)
            # result is a CallToolResult with a .content list of blocks
            parts = []
            for block in result.content:
                if hasattr(block, "text"):
                    parts.append(block.text)
                else:
                    parts.append(str(block))
            return "\n".join(parts)


# ---------------------------------------------------------------------------
# AnthropicAgent implementation
# ---------------------------------------------------------------------------


class AnthropicAgent(Agent):
    """Simple Anthropic API agent with MCP tool support.

    Uses the anthropic SDK directly with MCP tool support.
    Designed for testing that skills work with any Anthropic API client.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        max_tokens: int = MAX_TOKENS,
        max_iterations: int = MAX_ITERATIONS,
        message_log_path: pathlib.Path | None = None,
    ) -> None:
        if os.getenv("ANTHROPIC_API_KEY") is not None:
            self._client = anthropic.AsyncAnthropic()
        else:
            self._client = anthropic.AsyncAnthropicBedrock()
            model = _convert_model_to_bedrock(model)

        self._model = model
        self._max_tokens = max_tokens
        self._max_iterations = max_iterations
        self._mcp_tool_client: InlineMCPToolClient | None = None
        self._mcp_server_configs: dict[str, Any] = {}
        self._custom_instructions: str | None = None
        self._message_log_path = message_log_path
        self._message_log_file = None

    @property
    def mcp_servers(self) -> dict[str, Any]:
        return self._mcp_server_configs

    @mcp_servers.setter
    def mcp_servers(self, value: Mapping[str, Any]) -> None:
        self._mcp_server_configs = dict(value)
        self._mcp_tool_client = InlineMCPToolClient(self._mcp_server_configs)

    @property
    def custom_instructions(self) -> str | None:
        return self._custom_instructions

    @custom_instructions.setter
    def custom_instructions(self, value: str | None) -> None:
        self._custom_instructions = value

    def cancel(self) -> None:
        pass

    def _log(self, label: str, content: str) -> None:
        """Write a labeled message to the log file if logging is enabled."""
        if self._message_log_path is None:
            return
        with open(self._message_log_path, "a") as f:
            f.write(f"\n{'=' * 80}\n")
            f.write(f"[{label}]\n")
            f.write(f"{'=' * 80}\n")
            f.write(content)
            f.write("\n")

    def _build_system_prompt(self) -> str:
        parts = [SYSTEM_PROMPT]
        if self._custom_instructions:
            parts.append(
                f"\n<custom-instructions>\n{self._custom_instructions}\n</custom-instructions>"
            )
        return "\n\n".join(parts)

    async def query(self, prompt: str) -> str:
        last_content = ""
        async for message in self.query_stream(prompt):
            if isinstance(message, AssistantMessage) and message.content:
                last_content = message.content
        return last_content

    async def query_stream(self, prompt: str) -> AsyncGenerator[AgentMessage, None]:
        """Run a tool-use loop with the Anthropic API."""
        if self._mcp_tool_client is None:
            self._mcp_tool_client = InlineMCPToolClient({})

        # Discover tools from MCP servers
        raw_tools = await self._mcp_tool_client.get_tools()
        tools = [
            {
                "name": f"{t['server_name']}__{t['name']}" if t.get("server_name") else t["name"],
                "description": t.get("description", ""),
                "input_schema": t.get("inputSchema", {"type": "object"}),
            }
            for t in raw_tools
        ]

        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]

        for iteration in range(self._max_iterations):
            logger.info(f"Iteration {iteration + 1}/{self._max_iterations}")

            response = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=self._build_system_prompt(),
                messages=messages,
                tools=tools if tools else anthropic.NOT_GIVEN,
            )

            # Track tokens
            token_usage = TokenUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cache_creation_input_tokens=getattr(
                    response.usage, "cache_creation_input_tokens", 0
                )
                or 0,
                cache_read_input_tokens=getattr(
                    response.usage, "cache_read_input_tokens", 0
                )
                or 0,
            )

            # Extract text content
            text_parts = []
            tool_uses = []
            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_uses.append(block)

            text_content = "\n".join(text_parts)

            # Log assistant message
            if text_content:
                self._log(f"ASSISTANT (iter {iteration + 1})", text_content)
            for tu in tool_uses:
                self._log(
                    f"TOOL_CALL (iter {iteration + 1}): {tu.name}",
                    json.dumps(tu.input, indent=2) if isinstance(tu.input, dict) else str(tu.input),
                )

            yield AssistantMessage(
                content=text_content,
                tool_calls=None,
                token_usage={self._model: token_usage},
            )

            # If no tool use, we're done
            if response.stop_reason != "tool_use" or not tool_uses:
                return

            # Add assistant message to history
            messages.append({"role": "assistant", "content": response.content})

            # Execute tool calls
            tool_results = []
            for tool_use in tool_uses:
                # Parse server_name__tool_name
                parts = tool_use.name.split("__", 1)
                if len(parts) == 2:
                    server_name, tool_name = parts
                else:
                    server_name, tool_name = "", tool_use.name

                logger.info(f"Calling tool: {tool_use.name}")

                try:
                    result_content = await self._mcp_tool_client.call_tool(
                        tool_name=tool_name,
                        server_name=server_name,
                        arguments=tool_use.input,
                    )

                    self._log(
                        f"TOOL_RESULT: {tool_use.name}",
                        result_content[:2000] if len(result_content) > 2000 else result_content,
                    )

                    yield ToolResponse(
                        tool_call_id=tool_use.id,
                        name=tool_use.name,
                        content=result_content,
                    )

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": result_content,
                        }
                    )
                except Exception as e:
                    logger.error(f"Tool call failed: {tool_use.name}: {e}")
                    self._log(f"TOOL_ERROR: {tool_use.name}", str(e))
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": f"Error: {e}",
                            "is_error": True,
                        }
                    )

            messages.append({"role": "user", "content": tool_results})

        # Exhausted iterations
        yield AssistantMessage(
            content="Reached maximum iterations.",
            tool_calls=None,
            token_usage={},
        )


def _convert_model_to_bedrock(model: str) -> str:
    """Convert standard model name to Bedrock format."""
    if model.startswith("us.anthropic."):
        return model
    return f"us.anthropic.{model}-v1:0"

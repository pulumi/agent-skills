"""Simple shell MCP server for agent-skills testing.

Provides a shell_execute tool via FastMCP. Runs commands directly
on the host system.
"""

import asyncio
import os
import re

from fastmcp import FastMCP

# Deny patterns to prevent dangerous operations
DEFAULT_DENY_PATTERNS = [
    r"\bpulumi\s+(?!plugin\b).*\bup\b",
    r"\bpulumi\b.*\benv\b.*\brun\b.*\bpulumi\s+(?!plugin\b).*\bup\b",
    r"\bpulumi\s+(?!plugin\b).*\bpreview\b",
    r"\bpulumi\b.*\benv\b.*\brun\b.*\bpulumi\s+(?!plugin\b).*\bpreview\b",
]


def create_shell_mcp(
    pulumi_access_token: str = "",
    github_token: str = "",
    deny_patterns: list[str] | None = None,
) -> FastMCP:
    """Create a simple FastMCP shell server."""
    mcp = FastMCP("shell")
    patterns = deny_patterns if deny_patterns is not None else DEFAULT_DENY_PATTERNS
    compiled = [re.compile(p) for p in patterns]

    @mcp.tool()
    async def shell_execute(command: str, timeout: int = 120) -> str:
        """Execute a shell command and return its output."""
        # Check deny patterns
        for pattern in compiled:
            if pattern.search(command):
                return f"Error: Command blocked by deny pattern: {pattern.pattern}"

        env = {
            **os.environ,
            "PULUMI_ACCESS_TOKEN": pulumi_access_token,
            "GITHUB_TOKEN": github_token,
        }

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            output = stdout.decode()
            if stderr:
                output += "\n" + stderr.decode()
            if proc.returncode != 0:
                output = f"Exit code: {proc.returncode}\n{output}"
            return output
        except asyncio.TimeoutError:
            proc.kill()
            return f"Error: Command timed out after {timeout}s"
        except Exception as e:
            return f"Error: {e}"

    return mcp

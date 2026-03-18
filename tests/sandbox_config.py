"""Sandbox and permission configuration for drift adoption tests.

Builds OS-level (srt) sandbox settings and tool-level permission rules
to prevent agents from cheating during tests — especially baseline runs.
"""

import json
from typing import Any


def build_sandbox_config(
    baseline: bool = False,
) -> tuple[dict[str, Any], str]:
    """Build sandbox settings and permission rules for a drift test.

    Args:
        baseline: If True, add deny rules that block the drift-adopter CLI
            tool so the baseline agent can't discover it.

    Returns:
        A (sandbox_dict, settings_json) tuple:
        - sandbox_dict is passed to ClaudeAgentOptions.sandbox
        - settings_json is passed to ClaudeAgentOptions.settings
    """
    sandbox: dict[str, Any] = {
        "enabled": True,
        "autoAllowBashIfSandboxed": True,
        "allowUnsandboxedCommands": False,
        "network": {
            "allowLocalBinding": True,
        },
    }

    deny_rules: list[str] = [
        "WebFetch(domain:github.com)",
        "WebFetch(domain:api.github.com)",
        "WebFetch(domain:raw.githubusercontent.com)",
    ]

    if baseline:
        deny_rules.extend([
            "Bash(pulumi plugin run drift-adopter*)",
            "Bash(pulumi-drift-adopt*)",
            "Bash(drift-adopt*)",
            "Bash(which pulumi-drift-adopt*)",
            "Bash(which drift-adopt*)",
        ])

    settings = json.dumps({
        "permissions": {
            "deny": deny_rules,
        },
    })

    return sandbox, settings

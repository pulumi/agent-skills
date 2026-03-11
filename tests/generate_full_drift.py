#!/usr/bin/env python3
"""Generate full-drift adoption test fixtures (all creates).

Produces example directories for each scale (50, 100, 200, 400, 800) using
local-only providers (random, command, tls) — no cloud credentials required.

Each directory contains:
  - index.ts:          Empty program (imports only, no resources)
  - drifted/index.ts:  N resource declarations across 3 providers
  - Pulumi.yaml:       Project configuration
  - package.json:      Node.js dependencies
  - tsconfig.json:     TypeScript configuration

The empty original + full drifted means all N resources show as "creates"
in preview — the agent must add every resource to code from scratch.

Usage:
    python tests/generate_full_drift.py
"""

import json
import textwrap
from pathlib import Path

from generate_large_scale import (
    ORIGINAL_GENERATORS,
    compute_resource_counts,
    generate_tsconfig,
    _resource_local_index,
    _resource_type,
)

SCALES = [50, 100, 200, 400, 800]


def generate_empty_index_ts() -> str:
    """Generate an empty TypeScript program — imports only, no resources."""
    lines = [
        'import * as pulumi from "@pulumi/pulumi";',
        'import * as random from "@pulumi/random";',
        'import * as command from "@pulumi/command";',
        'import * as tls from "@pulumi/tls";',
        "",
    ]
    return "\n".join(lines) + "\n"


def generate_full_index_ts(scale: int) -> str:
    """Generate TypeScript source with N resource declarations (no drift mutations)."""
    random_count, command_count, _ = compute_resource_counts(scale)

    lines: list[str] = [
        'import * as pulumi from "@pulumi/pulumi";',
        'import * as random from "@pulumi/random";',
        'import * as command from "@pulumi/command";',
        'import * as tls from "@pulumi/tls";',
        "",
    ]

    for i in range(scale):
        rtype = _resource_type(i, random_count, command_count)
        local_idx = _resource_local_index(i, random_count, command_count)
        lines.append(ORIGINAL_GENERATORS[rtype](local_idx))

    return "\n".join(lines) + "\n"


def generate_pulumi_yaml(scale: int) -> str:
    return textwrap.dedent(f"""\
        name: full-drift-{scale}
        runtime: nodejs
        description: Full-drift adoption test ({scale} resources, all creates)
    """)


def generate_package_json(scale: int) -> str:
    data = {
        "name": f"full-drift-{scale}",
        "version": "1.0.0",
        "main": "index.ts",
        "devDependencies": {
            "@types/node": "^20.0.0",
            "typescript": "^5.0.0",
        },
        "dependencies": {
            "@pulumi/pulumi": "^3.0.0",
            "@pulumi/random": "^4.0.0",
            "@pulumi/command": "^1.0.0",
            "@pulumi/tls": "^5.0.0",
        },
    }
    return json.dumps(data, indent=2) + "\n"


def main() -> None:
    output_base = Path(__file__).resolve().parent / "drift-adoption"

    for scale in SCALES:
        print(f"Generating full-drift-{scale}...")

        out_dir = output_base / f"full-drift-{scale}"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Original index.ts — empty program
        (out_dir / "index.ts").write_text(generate_empty_index_ts())

        # Drifted index.ts — all N resources
        drifted_dir = out_dir / "drifted"
        drifted_dir.mkdir(parents=True, exist_ok=True)
        (drifted_dir / "index.ts").write_text(generate_full_index_ts(scale))

        # Config files
        (out_dir / "Pulumi.yaml").write_text(generate_pulumi_yaml(scale))
        (out_dir / "package.json").write_text(generate_package_json(scale))
        (out_dir / "tsconfig.json").write_text(generate_tsconfig())

        print(f"  {scale} resources (all creates)")

    print("Done!")


if __name__ == "__main__":
    main()

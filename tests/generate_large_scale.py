#!/usr/bin/env python3
"""Generate large-scale drift adoption test fixtures.

Produces example directories for each scale (250, 500, 750, 1000) using
local-only providers (random, command, tls) — no cloud credentials required.

Each directory contains:
  - index.ts:          Original N resource declarations across 3 providers
  - drifted/index.ts:  Same with ~15% drift applied
  - Pulumi.yaml:       Project configuration
  - package.json:      Node.js dependencies
  - tsconfig.json:     TypeScript configuration

Drift types (each ~25% of drift budget):
  - Property changes (scattered)
  - Resource deletions
  - Resource creations (extra resources in drifted only)
  - Clustered property changes (contiguous groups of ~5)

Usage:
    python tests/generate_large_scale.py
"""

import json
import random
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

SCALES = [250, 500, 750, 1000]

# Resource distribution ratios
RANDOM_RATIO = 0.40
COMMAND_RATIO = 0.35
TLS_RATIO = 0.25

# Drift budget: ~15% of total resources
DRIFT_RATIO = 0.15


@dataclass
class DriftConfig:
    """Describes which resources are drifted and how."""

    property_change_indices: list[int] = field(default_factory=list)
    deletion_indices: list[int] = field(default_factory=list)
    creation_extras: dict[str, int] = field(default_factory=dict)  # provider -> count
    clustered_indices: list[int] = field(default_factory=list)


def compute_resource_counts(scale: int) -> tuple[int, int, int]:
    """Return (random_count, command_count, tls_count) for a given scale."""
    random_count = round(scale * RANDOM_RATIO)
    command_count = round(scale * COMMAND_RATIO)
    tls_count = scale - random_count - command_count
    return random_count, command_count, tls_count


def compute_drift_config(scale: int) -> DriftConfig:
    """Compute deterministic drift configuration for a given scale."""
    rng = random.Random(scale)

    random_count, command_count, tls_count = compute_resource_counts(scale)
    total_drift = max(1, round(scale * DRIFT_RATIO))

    # Split drift budget evenly across 4 types
    per_type = total_drift // 4

    # Build index ranges for each provider
    # Layout: [0..random_count-1] = random, [random_count..random_count+command_count-1] = command, etc.
    random_range = list(range(0, random_count))
    command_range = list(range(random_count, random_count + command_count))
    tls_range = list(range(random_count + command_count, scale))

    # === Property changes (scattered) ===
    per_provider = max(1, per_type // 3)
    property_indices: list[int] = []
    for provider_range in [random_range, command_range, tls_range]:
        candidates = list(provider_range)
        rng.shuffle(candidates)
        property_indices.extend(candidates[:per_provider])

    # === Deletions ===
    deletion_indices: list[int] = []
    for provider_range in [random_range, command_range, tls_range]:
        candidates = [i for i in provider_range if i not in property_indices]
        rng.shuffle(candidates)
        deletion_indices.extend(candidates[:per_provider])

    # === Creations ===
    creation_extras = {
        "random": per_provider,
        "command": per_provider,
        "tls": per_provider,
    }

    # === Clustered property changes ===
    cluster_size = 5
    clustered_indices: list[int] = []
    used = set(property_indices) | set(deletion_indices)
    for provider_range in [random_range, command_range, tls_range]:
        candidates = [i for i in provider_range if i not in used]
        if len(candidates) >= cluster_size:
            sorted_candidates = sorted(candidates)
            # Find first contiguous run of cluster_size
            start = None
            for j in range(len(sorted_candidates) - cluster_size + 1):
                if sorted_candidates[j + cluster_size - 1] - sorted_candidates[j] == cluster_size - 1:
                    start = j
                    break
            if start is not None:
                cluster = sorted_candidates[start : start + cluster_size]
                clustered_indices.extend(cluster)
                used.update(cluster)

    return DriftConfig(
        property_change_indices=sorted(property_indices),
        deletion_indices=sorted(deletion_indices),
        creation_extras=creation_extras,
        clustered_indices=sorted(clustered_indices),
    )


def _resource_type(index: int, random_count: int, command_count: int) -> str:
    """Return provider type for a given resource index."""
    if index < random_count:
        return "random"
    elif index < random_count + command_count:
        return "command"
    else:
        return "tls"


def _resource_local_index(index: int, random_count: int, command_count: int) -> int:
    """Return provider-local index for a given global resource index."""
    if index < random_count:
        return index
    elif index < random_count + command_count:
        return index - random_count
    else:
        return index - random_count - command_count


def _random_original(local_idx: int) -> str:
    return (
        f'const randomStr{local_idx} = new random.RandomString("random-str-{local_idx}", {{\n'
        f"    length: 16,\n"
        f"    special: false,\n"
        f"}});\n"
    )


def _random_drifted(local_idx: int) -> str:
    return (
        f'const randomStr{local_idx} = new random.RandomString("random-str-{local_idx}", {{\n'
        f"    length: 32,\n"
        f"    special: true,\n"
        f"}});\n"
    )


def _command_original(local_idx: int) -> str:
    return (
        f'const cmd{local_idx} = new command.local.Command("cmd-{local_idx}", {{\n'
        f'    create: "echo resource-{local_idx}",\n'
        f"}});\n"
    )


def _command_drifted(local_idx: int) -> str:
    return (
        f'const cmd{local_idx} = new command.local.Command("cmd-{local_idx}", {{\n'
        f'    create: "echo resource-{local_idx}-modified",\n'
        f'    environment: {{ DRIFT: "true" }},\n'
        f"}});\n"
    )


def _tls_original(local_idx: int) -> str:
    return (
        f'const tlsKey{local_idx} = new tls.PrivateKey("tls-key-{local_idx}", {{\n'
        f'    algorithm: "RSA",\n'
        f"    rsaBits: 2048,\n"
        f"}});\n"
    )


def _tls_drifted(local_idx: int) -> str:
    return (
        f'const tlsKey{local_idx} = new tls.PrivateKey("tls-key-{local_idx}", {{\n'
        f'    algorithm: "ECDSA",\n'
        f'    ecdsaCurve: "P256",\n'
        f"}});\n"
    )


ORIGINAL_GENERATORS = {
    "random": _random_original,
    "command": _command_original,
    "tls": _tls_original,
}

DRIFTED_GENERATORS = {
    "random": _random_drifted,
    "command": _command_drifted,
    "tls": _tls_drifted,
}

EXTRA_GENERATORS = {
    "random": lambda idx: (
        f'const randomStrExtra{idx} = new random.RandomString("random-str-extra-{idx}", {{\n'
        f"    length: 16,\n"
        f"    special: false,\n"
        f"}});\n"
    ),
    "command": lambda idx: (
        f'const cmdExtra{idx} = new command.local.Command("cmd-extra-{idx}", {{\n'
        f'    create: "echo extra-resource-{idx}",\n'
        f"}});\n"
    ),
    "tls": lambda idx: (
        f'const tlsKeyExtra{idx} = new tls.PrivateKey("tls-key-extra-{idx}", {{\n'
        f'    algorithm: "RSA",\n'
        f"    rsaBits: 2048,\n"
        f"}});\n"
    ),
}


def generate_index_ts(scale: int, drift_config: DriftConfig | None = None) -> str:
    """Generate TypeScript source with individual resource declarations."""
    random_count, command_count, _ = compute_resource_counts(scale)

    lines: list[str] = [
        'import * as pulumi from "@pulumi/pulumi";',
        'import * as random from "@pulumi/random";',
        'import * as command from "@pulumi/command";',
        'import * as tls from "@pulumi/tls";',
        "",
    ]

    drifted_set = set()
    deleted_set = set()
    clustered_set = set()

    if drift_config:
        drifted_set = set(drift_config.property_change_indices)
        deleted_set = set(drift_config.deletion_indices)
        clustered_set = set(drift_config.clustered_indices)

    for i in range(scale):
        rtype = _resource_type(i, random_count, command_count)
        local_idx = _resource_local_index(i, random_count, command_count)

        if drift_config and i in deleted_set:
            continue

        if drift_config and (i in drifted_set or i in clustered_set):
            lines.append(DRIFTED_GENERATORS[rtype](local_idx))
        else:
            lines.append(ORIGINAL_GENERATORS[rtype](local_idx))

    # Add extra resources for creation drift (only in drifted code)
    if drift_config and drift_config.creation_extras:
        lines.append("// Extra resources")
        for provider, count in drift_config.creation_extras.items():
            for idx in range(count):
                lines.append(EXTRA_GENERATORS[provider](idx))

    return "\n".join(lines) + "\n"


def generate_pulumi_yaml(scale: int) -> str:
    return textwrap.dedent(f"""\
        name: large-scale-{scale}
        runtime: nodejs
        description: Large-scale drift adoption test ({scale} resources)
    """)


def generate_package_json(scale: int) -> str:
    data = {
        "name": f"large-scale-{scale}",
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


def generate_tsconfig() -> str:
    data = {
        "compilerOptions": {
            "strict": True,
            "outDir": "bin",
            "target": "es2016",
            "module": "commonjs",
            "moduleResolution": "node",
            "sourceMap": True,
            "experimentalDecorators": True,
            "pretty": True,
            "noFallthroughCasesInSwitch": True,
            "noImplicitReturns": True,
            "forceConsistentCasingInFileNames": True,
        },
        "files": ["index.ts"],
    }
    return json.dumps(data, indent=2) + "\n"


def main() -> None:
    # Output to tests/drift-adoption/ relative to this script
    output_base = Path(__file__).resolve().parent / "drift-adoption"

    for scale in SCALES:
        print(f"Generating large-scale-{scale}...")

        drift_config = compute_drift_config(scale)
        out_dir = output_base / f"large-scale-{scale}"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Original index.ts
        (out_dir / "index.ts").write_text(generate_index_ts(scale))

        # Drifted index.ts
        drifted_dir = out_dir / "drifted"
        drifted_dir.mkdir(parents=True, exist_ok=True)
        (drifted_dir / "index.ts").write_text(
            generate_index_ts(scale, drift_config)
        )

        # Config files
        (out_dir / "Pulumi.yaml").write_text(generate_pulumi_yaml(scale))
        (out_dir / "package.json").write_text(generate_package_json(scale))
        (out_dir / "tsconfig.json").write_text(generate_tsconfig())

        # Print drift summary
        total_drift = (
            len(drift_config.property_change_indices)
            + len(drift_config.deletion_indices)
            + sum(drift_config.creation_extras.values())
            + len(drift_config.clustered_indices)
        )
        print(
            f"  {scale} resources, {total_drift} drifted "
            f"({len(drift_config.property_change_indices)} prop changes, "
            f"{len(drift_config.deletion_indices)} deletions, "
            f"{sum(drift_config.creation_extras.values())} creations, "
            f"{len(drift_config.clustered_indices)} clustered)"
        )

    print("Done!")


if __name__ == "__main__":
    main()

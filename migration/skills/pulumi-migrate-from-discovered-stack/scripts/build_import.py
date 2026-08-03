#!/usr/bin/env python3
"""Build an import.json from a discovered-stacks resources response.

Usage:
    python3 build_import.py <resources-baseline.json> [output-path]

Reads the saved API response and writes import.json containing all Ready
resources (excluding those with annotation overrides). If output-path is
omitted, writes to .migration/import.json relative to the baseline file.

Field mapping:
    type  ← providerType (top-level)
    name  ← name (top-level, CF Logical ID / ARM name)
    id    ← resource.inputs.providerId
"""

import json
import sys
from pathlib import Path


def effective_status(resource: dict[str, object]) -> str:
    annotation = resource.get("annotation")
    if isinstance(annotation, dict) and annotation.get("statusOverride"):
        return str(annotation["statusOverride"])
    return str(resource.get("migrationStatus", "Unknown"))


def main() -> None:
    if len(sys.argv) < 2:
        print(
            f"Usage: {sys.argv[0]} <resources-baseline.json> [output-path]",
            file=sys.stderr,
        )
        sys.exit(1)

    baseline_path = Path(sys.argv[1])
    data = json.loads(baseline_path.read_text())
    resources = data if isinstance(data, list) else data.get("resources", [])

    output_path = (
        Path(sys.argv[2]) if len(sys.argv) > 2 else baseline_path.parent / "import.json"
    )

    import_resources = []
    skipped = {"no_provider_type": 0, "not_ready": 0, "overridden": 0}

    for r in resources:
        status = effective_status(r)
        provider_type = r.get("providerType")
        provider_id = (r.get("resource") or {}).get("inputs", {}).get("providerId")
        name = r.get("name")

        if not provider_type:
            skipped["no_provider_type"] += 1
            continue
        if status not in ("Ready", "NotFound"):
            skipped["not_ready"] += 1
            continue
        annotation = r.get("annotation")
        if annotation and annotation.get("statusOverride") == "Migrated":
            skipped["overridden"] += 1
            continue
        if not provider_id:
            print(
                f"WARNING: {name} has providerType but no providerId, skipping",
                file=sys.stderr,
            )
            continue

        import_resources.append(
            {
                "type": provider_type,
                "name": name,
                "id": provider_id,
            }
        )

    import_json = {"resources": import_resources}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(import_json, indent=2))

    print(f"Wrote {len(import_resources)} resources to {output_path}")
    if any(skipped.values()):
        print(
            f"Skipped: {skipped['not_ready']} not Ready/NotFound, "
            f"{skipped['no_provider_type']} without a provider type, "
            f"{skipped['overridden']} already annotated"
        )


if __name__ == "__main__":
    main()

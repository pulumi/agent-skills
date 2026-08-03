#!/usr/bin/env python3
"""Triage a discovered-stacks resources response.

Usage:
    python3 triage.py <resources-baseline.json>

Reads the saved API response and prints:
- Status counts (accounting for annotation overrides)
- Per-resource table with name, origin type, provider type, status, and annotation
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
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <resources-baseline.json>", file=sys.stderr)
        sys.exit(1)

    data = json.loads(Path(sys.argv[1]).read_text())
    resources = data if isinstance(data, list) else data.get("resources", [])

    counts: dict[str, int] = {}
    rows: list[dict[str, str]] = []

    for r in resources:
        status = effective_status(r)
        counts[status] = counts.get(status, 0) + 1
        annotation = r.get("annotation")
        rows.append(
            {
                "name": r.get("name", ""),
                "originType": r.get("originType", ""),
                "providerType": r.get("providerType") or "(unmapped)",
                "status": status,
                "note": (annotation.get("note", "") if annotation else ""),
            }
        )

    total = len(resources)
    print(f"Total: {total} resources\n")
    for status in [
        "Migrated",
        "Ready",
        "NotFound",
        "NoMatch",
        "PulumiOnly",
        "NotApplicable",
    ]:
        if status in counts:
            print(f"  {status}: {counts[status]}")
    for status in sorted(counts):
        if status not in [
            "Migrated",
            "Ready",
            "NotFound",
            "NoMatch",
            "PulumiOnly",
            "NotApplicable",
        ]:
            print(f"  {status}: {counts[status]}")

    print(f"\n{'Name':<55} {'Origin':<35} {'Provider':<35} {'Status':<15} Note")
    print("-" * 160)
    for row in sorted(rows, key=lambda r: (r["status"], r["name"])):
        note = row["note"][:40] + "..." if len(row["note"]) > 40 else row["note"]
        print(
            f"{row['name']:<55} {row['originType']:<35} {row['providerType']:<35} {row['status']:<15} {note}"
        )


if __name__ == "__main__":
    main()

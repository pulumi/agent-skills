#!/usr/bin/env python3
"""Standalone script to set up drift and capture drift-adopter output.

Sets up the drift test environment (deploy original → deploy drifted → restore
original code → scrub drifted dirs), then runs `pulumi plugin run drift-adopter`
and saves the raw JSON output for analysis.

Usage:
    PULUMI_ACCESS_TOKEN=$JDAVENPORT_PULUMI_CORP_PULUMI_ACCESS_TOKEN \
    GITHUB_TOKEN=$(gh auth token) \
    PULUMI_OPTION_DEFAULT_ORG=pulumi \
    PULUMI_ENABLE_JOURNALING=true \
      python tests/run_drift_setup.py [example-name] 2>&1 | tee .test-output/drift-setup.log

    example-name defaults to small-scale-10
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# Add tests/ to sys.path so we can import helpers
sys.path.insert(0, str(Path(__file__).resolve().parent))

from drift_adoption_helpers import (
    create_drift_with_program,
    drift_test_context,
    get_total_resource_count,
    scrub_drifted_dirs,
    verify_drift_exists,
)

PULUMI_API = "https://api.pulumi.com"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / ".test-output"
OUTPUT_FILE = OUTPUT_DIR / "drift-adopter-raw-output.json"
PREVIEW_FILE = OUTPUT_DIR / "pulumi-preview.json"
DEPLOYMENTS_FILE = OUTPUT_DIR / "small-scale-10-deployments.json"


def _api_request(method: str, path: str, body: dict | None = None) -> dict:
    """Make an authenticated request to the Pulumi Cloud API."""
    token = os.environ["PULUMI_ACCESS_TOKEN"]
    url = f"{PULUMI_API}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"token {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def get_current_branch() -> str:
    """Get current git branch and verify it's pushed to origin."""
    branch = subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True
    ).strip()
    local_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
    try:
        remote_sha = subprocess.check_output(
            ["git", "rev-parse", f"origin/{branch}"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except subprocess.CalledProcessError:
        raise RuntimeError(
            f"Branch '{branch}' has no remote tracking branch. Push it first: git push -u origin {branch}"
        )
    if local_sha != remote_sha:
        raise RuntimeError(
            f"Local HEAD ({local_sha[:8]}) differs from origin/{branch} ({remote_sha[:8]}). "
            f"Push your changes first: git push"
        )
    return branch


def trigger_deployments_preview(org: str, project: str, stack: str, branch: str) -> str:
    """Trigger a Deployments preview and return the deployment ID."""
    path = f"/api/stacks/{org}/{project}/{stack}/deployments"
    body = {
        "operation": "preview",
        "inheritSettings": False,
        "sourceContext": {
            "git": {
                "repoURL": "https://github.com/pulumi/agent-skills.git",
                "branch": branch,
                "repoDir": "tests/drift-adoption/small-scale-10",
            }
        },
        "operationContext": {
            "options": {"refresh": True},
            "preRunCommands": ["npm install"],
        },
    }
    resp = _api_request("POST", path, body)
    return resp["id"]


def wait_for_deployment(org: str, project: str, stack: str, deployment_id: str) -> str:
    """Poll deployment status until terminal, return the update ID."""
    path = f"/api/stacks/{org}/{project}/{stack}/deployments/{deployment_id}"
    while True:
        resp = _api_request("GET", path)
        status = resp.get("status", "")
        print(f"    Deployment status: {status}")
        if status in ("succeeded", "failed"):
            if status == "failed":
                raise RuntimeError(f"Deployment {deployment_id} failed")
            # The deployment response has a "version" field which is the update
            # version number used in the engine events API path.
            version = resp.get("version")
            if version:
                return str(version)
            raise RuntimeError(f"No version found in deployment response: {list(resp.keys())}")
        time.sleep(5)


def download_engine_events(org: str, project: str, stack: str, update_id: str) -> dict:
    """Download all engine events for an update, paginating with continuationToken."""
    all_events: list = []
    continuation_token = None
    while True:
        path = f"/api/stacks/{org}/{project}/{stack}/preview/{update_id}/events"
        if continuation_token:
            path += f"?continuationToken={continuation_token}"
        resp = _api_request("GET", path)
        events = resp.get("events", [])
        all_events.extend(events)
        continuation_token = resp.get("continuationToken")
        if not continuation_token:
            break
    return {"events": all_events}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Set up drift and capture drift-adopter output")
    parser.add_argument("example_name", nargs="?", default="small-scale-10", help="Example name")
    parser.add_argument("--skip-deployments", action="store_true", help="Skip Deployments API preview step")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    example_name = args.example_name

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Setting up drift test for {example_name}...")
    with drift_test_context(example_name, skip_esc=True) as ctx:
        # Step 1: Deploy original code
        print("Step 1: Deploying original code...")
        ctx.program.up()
        resource_count = get_total_resource_count(ctx.program)
        print(f"  Deployed {resource_count} resources")

        # Step 2: Create drift
        print("Step 2: Creating drift (deploy drifted → restore original code)...")
        create_drift_with_program(ctx.program, ctx.example_dir)
        resource_count = get_total_resource_count(ctx.program)
        print(f"  Resources in state after drift: {resource_count}")

        update_count, replace_count = verify_drift_exists(ctx.program)
        print(f"  Drift verified: {update_count} updates, {replace_count} replaces")

        # Step 3: Scrub drifted dirs
        print("Step 3: Scrubbing drifted dirs...")
        scrub_drifted_dirs(ctx.working_dir)

        # Step 4: Run pulumi preview --json and save for unit test fixtures
        program_dir = ctx.program.working_dir
        print("Step 4: Running pulumi preview --json...")
        print(f"  Program working dir: {program_dir}")
        print(f"  Stack: {ctx.stack_name}")

        preview_result = subprocess.run(
            [
                "pulumi",
                "preview",
                "--json",
                "--stack",
                ctx.stack_name,
            ],
            cwd=program_dir,
            capture_output=True,
            text=True,
        )

        print(f"  Return code: {preview_result.returncode}")
        if preview_result.stderr:
            # preview --json writes diagnostics to stderr; only show first few lines
            stderr_lines = preview_result.stderr.strip().splitlines()
            print(f"  Stderr: {len(stderr_lines)} lines (first 5):")
            for line in stderr_lines[:5]:
                print(f"    {line}")

        preview_json = preview_result.stdout
        PREVIEW_FILE.write_text(preview_json)
        print(f"  Preview JSON saved to: {PREVIEW_FILE}")
        print(f"  Output length: {len(preview_json)} chars")

        # Quick summary of preview JSON
        try:
            pdata = json.loads(preview_json)
            steps = pdata.get("steps", [])
            by_op = {}
            for step in steps:
                op = step.get("op", "unknown")
                by_op[op] = by_op.get(op, 0) + 1
            print(f"  Preview steps: {len(steps)} total — {by_op}")
        except json.JSONDecodeError as e:
            print(f"  Warning: preview output is not valid JSON: {e}")

        # Step 4b: Run Deployments preview and download engine events
        if not args.skip_deployments:
            print("\nStep 4b: Running Deployments preview...")
            try:
                branch = get_current_branch()
                org = os.environ.get("PULUMI_OPTION_DEFAULT_ORG", "pulumi")
                project = "small-scale-10"  # from Pulumi.yaml
                print(f"  Branch: {branch}, Org: {org}, Project: {project}, Stack: {ctx.stack_name}")
                deployment_id = trigger_deployments_preview(org, project, ctx.stack_name, branch)
                print(f"  Deployment ID: {deployment_id}")
                update_id = wait_for_deployment(org, project, ctx.stack_name, deployment_id)
                print(f"  Update ID: {update_id}")
                events = download_engine_events(org, project, ctx.stack_name, update_id)
                DEPLOYMENTS_FILE.write_text(json.dumps(events, indent=2))
                print(f"  Engine events saved to: {DEPLOYMENTS_FILE}")
                print(f"  Total events: {len(events['events'])}")
            except Exception as e:
                print(f"  Warning: Deployments step failed: {e}")
                print("  (continuing with remaining steps)")
        else:
            print("\nStep 4b: Skipping Deployments preview (--skip-deployments)")

        # Step 5: Run drift-adopter and capture output
        print("\nStep 5: Running drift-adopter...")
        print(f"  Program working dir: {program_dir}")
        print(f"  Stack: {ctx.stack_name}")

        result = subprocess.run(
            [
                "pulumi",
                "plugin",
                "run",
                "drift-adopter",
                "--",
                "next",
                "--max-resources",
                "0",
                "--stack",
                ctx.stack_name,
            ],
            cwd=program_dir,
            capture_output=True,
            text=True,
        )

        print(f"  Return code: {result.returncode}")

        if result.stderr:
            print(f"  Stderr:\n{result.stderr}")

        # Save raw stdout
        raw_output = result.stdout
        OUTPUT_FILE.write_text(raw_output)
        print(f"  Raw output saved to: {OUTPUT_FILE}")
        print(f"  Output length: {len(raw_output)} chars")

        # Try to parse as JSON for a summary
        try:
            data = json.loads(raw_output)
            print(f"\n  JSON parsed successfully. Top-level keys: {list(data.keys())}")
            if isinstance(data, dict):
                # Print structure summary
                for key, value in data.items():
                    if isinstance(value, list):
                        print(f"    {key}: list with {len(value)} items")
                        if value:
                            first = value[0]
                            if isinstance(first, dict):
                                print(f"      First item keys: {list(first.keys())}")
                    elif isinstance(value, dict):
                        print(f"    {key}: dict with keys {list(value.keys())}")
                    else:
                        print(f"    {key}: {value}")
        except json.JSONDecodeError as e:
            print(f"\n  Warning: output is not valid JSON: {e}")
            # Save raw text anyway
            print(f"  First 500 chars:\n{raw_output[:500]}")

        print(f"\nDone! Inspect the output at: {OUTPUT_FILE}")
        print(f"Working dir: {ctx.example_dir}")
        print(f"Stack: {ctx.stack_name}")

        # Keep context alive for manual inspection — wait for user
        print("\nPress Enter to tear down (destroy stack + cleanup worktree)...")
        try:
            input()
        except EOFError:
            print("  (non-interactive, tearing down immediately)")


if __name__ == "__main__":
    main()

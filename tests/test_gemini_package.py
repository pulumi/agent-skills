"""Validate Gemini packaging, skill discovery, and release workflow decisions.

Archive and workflow tests run without network access. Set GEMINI_CLI to a CLI
executable to also check installation and discovery in a temporary profile.
Release tests execute the workflow's shell with fake gh and git commands; they
do not publish releases or exercise GitHub's API.
"""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import textwrap

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_SCRIPT = REPO_ROOT / "scripts/build_gemini_extension.py"
RELEASE_WORKFLOW = REPO_ROOT / ".github/workflows/release-gemini.yml"


@pytest.fixture
def packages(tmp_path: Path) -> list[Path]:
    # Exercise the production builder so archive checks cover what CI will ship.
    output = tmp_path / "packages"
    subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--output-dir", str(output)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return sorted(output.glob("*.tar.gz"))


def test_release_assets_preserve_all_end_user_skills(packages: list[Path]) -> None:
    # The contents are portable, but Gemini needs platform prefixes to select
    # its archive when a release also contains assets for other plugin systems.
    assert {path.name for path in packages} == {
        "darwin.pulumi-gemini.tar.gz",
        "linux.pulumi-gemini.tar.gz",
        "win32.pulumi-gemini.tar.gz",
    }
    assert len({path.read_bytes() for path in packages}) == 1
    # Keep the expected groups independent of the builder's manifest lookup.
    # Comparing every file catches missing references and unwanted extra skills.
    expected = {
        "gemini-extension.json": (REPO_ROOT / "gemini-extension.json").read_bytes(),
        "LICENSE": (REPO_ROOT / "LICENSE").read_bytes(),
    }
    for group in ("pulumi", "migration", "delegation"):
        for skill in (REPO_ROOT / group / "skills").iterdir():
            for source in skill.rglob("*"):
                if source.is_file():
                    expected[f"skills/{skill.name}/{source.relative_to(skill)}"] = (
                        source.read_bytes()
                    )
    with tarfile.open(packages[0]) as archive:
        actual = {
            member.name: archive.extractfile(member).read()
            for member in archive.getmembers()
            if member.isfile()
        }
    assert actual == expected


def test_release_tag_must_match_manifest(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(BUILD_SCRIPT),
            "--output-dir",
            str(tmp_path),
            "--release-tag",
            "v0.0.0-wrong-version",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert "Release tag must match" in result.stderr
    assert not list(tmp_path.glob("*.tar.gz"))


@pytest.mark.parametrize("version", ["invalid", "01.2.3", "2.0.6-beta", "2.0.6\n"])
def test_package_rejects_unreleasable_versions(tmp_path: Path, version: str) -> None:
    # The builder locates its repository relative to __file__. Copy it into an
    # otherwise valid fixture repository so only the version causes rejection.
    script = tmp_path / "scripts/build_gemini_extension.py"
    script.parent.mkdir()
    shutil.copyfile(BUILD_SCRIPT, script)
    manifest = json.loads((REPO_ROOT / "gemini-extension.json").read_text())
    manifest["version"] = version
    (tmp_path / "gemini-extension.json").write_text(json.dumps(manifest))
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / ".claude-plugin/plugin.json").write_text(
        json.dumps({"skills": ["pulumi/skills"]})
    )
    skill = tmp_path / "pulumi/skills/example"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("fixture")
    (tmp_path / "LICENSE").write_text("fixture")
    result = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, timeout=30
    )
    assert result.returncode != 0
    assert "Gemini version must be a stable major.minor.patch version" in result.stderr
    assert not list(tmp_path.rglob("*.tar.gz"))


@pytest.mark.skipif(not os.environ.get("GEMINI_CLI"), reason="GEMINI_CLI is not set")
def test_gemini_discovers_packaged_skills(packages: list[Path], tmp_path: Path) -> None:
    package = tmp_path / "extension"
    package.mkdir()
    with tarfile.open(packages[0]) as archive:
        archive.extractall(package, filter="data")
    # An untrusted temporary folder makes Gemini skip extension skills. Disable
    # that check only in this isolated profile, leaving the user's settings alone.
    profile = tmp_path / "profile"
    settings = profile / ".gemini/settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({
        "telemetry": {"enabled": False},
        "security": {"folderTrust": {"enabled": False}},
    }))
    env = {
        **os.environ,
        "GEMINI_CLI_HOME": str(profile),
        "GEMINI_CLI_SYSTEM_SETTINGS_PATH": str(tmp_path / "system-settings.json"),
        "GEMINI_CLI_NO_RELAUNCH": "1",
        "NO_COLOR": "1",
    }
    # Inherited Node preload hooks could replace the CLI behavior under test.
    env.pop("NODE_OPTIONS", None)
    cli = os.environ["GEMINI_CLI"]
    result = subprocess.run(
        [cli, "extensions", "install", str(package), "--consent"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    result = subprocess.run(
        [cli, "skills", "list"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    # Installation can succeed even when Gemini discovers no skills. Require
    # every packaged skill to be enabled, with no skills leaking from the user.
    expected = {path.parent.name for path in (package / "skills").glob("*/SKILL.md")}
    discovered = set(re.findall(r"^([a-z0-9-]+) \[Enabled\]", result.stdout, re.M))
    assert discovered == expected, result.stdout + result.stderr


# A newline must not let a manifest value inject another GITHUB_ENV assignment.
@pytest.mark.parametrize("version", ["2.0.6", "invalid", "2.0.6\nRELEASE_TAG=v9.0.0"])
def test_release_version_comes_from_merged_manifest(tmp_path: Path, version: str) -> None:
    # BaseLoader preserves the Actions key "on", which YAML 1.1 treats as True.
    workflow = yaml.load(RELEASE_WORKFLOW.read_text(), Loader=yaml.BaseLoader)
    assert workflow["on"]["push"] == {
        "branches": ["main"],
        "paths": ["gemini-extension.json"],
    }
    assert workflow["jobs"]["release"]["if"] == "github.ref == 'refs/heads/main'"
    step = next(
        step for step in workflow["jobs"]["release"]["steps"]
        if step.get("name") == "Read release version"
    )
    (tmp_path / "gemini-extension.json").write_text(json.dumps({"version": version}))
    output = tmp_path / "env"
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", step["run"]],
        cwd=tmp_path,
        env={**os.environ, "GITHUB_ENV": str(output)},
        capture_output=True,
        text=True,
        timeout=30,
    )
    if version == "2.0.6":
        assert result.returncode == 0, result.stderr
        assert output.read_text() == "RELEASE_TAG=v2.0.6\n"
    else:
        assert result.returncode != 0
        assert not output.exists()


# Each operations list specifies the allowed GitHub writes, in order. Failed
# uploads or lookups must stop before the draft can be published.
@pytest.mark.parametrize(
    ("scenario", "succeeds", "operations"),
    [
        ("new", True, ["create", "upload", "edit"]),
        ("matching-tag", True, ["create", "upload", "edit"]),
        ("draft", True, ["upload", "edit"]),
        ("published", True, []),
        ("published-missing-assets", False, []),
        ("published-empty-assets", False, []),
        ("older-release", True, ["create", "upload", "edit"]),
        ("newer-release", True, ["create", "upload", "edit"]),
        ("latest-api-error", False, ["create", "upload"]),
        ("api-error", False, []),
        ("conflicting-tag", False, []),
        ("conflicting-draft", False, []),
        ("create-fails", False, ["create"]),
        ("upload-fails", False, ["upload"]),
    ],
)
def test_release_publication(
    tmp_path: Path, scenario: str, succeeds: bool, operations: list[str]
) -> None:
    # Run the actual workflow block so changes to its shell logic are tested.
    workflow = yaml.safe_load(RELEASE_WORKFLOW.read_text())
    step = next(
        step for step in workflow["jobs"]["release"]["steps"]
        if step.get("name") == "Publish release with Gemini assets"
    )
    commands = tmp_path / "commands.jsonl"
    binaries = tmp_path / "bin"
    binaries.mkdir()
    # PATH points gh and git at this stub. It models release and tag states and
    # records commands without making API calls or changing repository refs.
    stub = f"#!{sys.executable}\n" + textwrap.dedent("""\
        import json
        import os
        from pathlib import Path
        import sys

        scenario = os.environ["RELEASE_SCENARIO"]
        args = sys.argv[1:]
        if Path(sys.argv[0]).name == "git":
            assert args == ["rev-parse", "--verify", "-q", "refs/tags/v2.0.6^{commit}"]
            if scenario == "matching-tag":
                print(os.environ["GITHUB_SHA"])
            elif scenario == "conflicting-tag":
                print("b" * 40)
            else:
                sys.exit(1)
            sys.exit(0)

        with open(os.environ["RELEASE_COMMANDS"], "a") as log:
            log.write(json.dumps(args) + "\\n")
        if args[:2] == ["release", "view"]:
            # A view without a tag asks for Latest, used to prevent downgrades.
            if args[2] == "--json":
                if scenario == "older-release":
                    print("v2.0.7")
                elif scenario == "newer-release":
                    print("v2.0.5")
                elif scenario == "latest-api-error":
                    print("gh: Forbidden (HTTP 403)", file=sys.stderr)
                    sys.exit(1)
                else:
                    print("release not found", file=sys.stderr)
                    sys.exit(1)
                sys.exit(0)
            assert args[2] == "v2.0.6"
            if scenario == "api-error":
                print("gh: Forbidden (HTTP 403)", file=sys.stderr)
                sys.exit(1)
            if scenario.startswith("published") or scenario in {"draft", "conflicting-draft", "upload-fails"}:
                print(json.dumps({
                    "isDraft": not scenario.startswith("published"),
                    "targetCommitish": (
                        "b" * 40 if scenario == "conflicting-draft" else os.environ["GITHUB_SHA"]
                    ),
                    "assets": [
                        {
                            "name": f"{platform}.pulumi-gemini.tar.gz",
                            "size": 0 if scenario == "published-empty-assets" else 100,
                        }
                        for platform in ("darwin", "linux", "win32")
                        if scenario != "published-missing-assets" or platform != "win32"
                    ],
                }))
                sys.exit(0)
            print("release not found", file=sys.stderr)
            sys.exit(1)
        assert args[0] == "release"
        if (scenario, args[1]) in {("create-fails", "create"), ("upload-fails", "upload")}:
            sys.exit(1)
        """)
    for name in ("gh", "git"):
        path = binaries / name
        path.write_text(stub)
        path.chmod(0o755)
    assets = tmp_path / "dist/gemini"
    assets.mkdir(parents=True)
    # Only filenames matter to the upload command; archive contents are checked
    # by test_release_assets_preserve_all_end_user_skills above.
    for platform in ("darwin", "linux", "win32"):
        (assets / f"{platform}.pulumi-gemini.tar.gz").touch()
    sha = "a" * 40
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", step["run"]],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
            "RELEASE_SCENARIO": scenario,
            "RELEASE_COMMANDS": str(commands),
            "RUNNER_TEMP": str(tmp_path),
            "GH_REPO": "pulumi/agent-skills",
            "GITHUB_SHA": sha,
            "RELEASE_TAG": "v2.0.6",
        },
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert (result.returncode == 0) == succeeds, result.stdout + result.stderr
    calls = [json.loads(line) for line in commands.read_text().splitlines()]
    assert calls[0][:2] == ["release", "view"]
    writes = [args for args in calls if args[:2] != ["release", "view"]]
    assert [args[1] for args in writes] == operations
    for args in writes:
        assert args[2] == "v2.0.6"
        if args[1] == "create":
            assert args[args.index("--target") + 1] == sha
            assert "--draft" in args
        elif args[1] == "upload":
            assert sorted(arg for arg in args if arg.endswith(".tar.gz")) == [
                f"dist/gemini/{platform}.pulumi-gemini.tar.gz"
                for platform in ("darwin", "linux", "win32")
            ]
        elif args[1] == "edit":
            assert "--draft=false" in args
            if scenario == "older-release":
                assert "--latest=false" in args
            else:
                assert "--latest" in args or "--latest=true" in args

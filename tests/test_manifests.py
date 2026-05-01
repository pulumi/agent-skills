"""
Validate plugin manifests for Claude Code and Codex.

Checks that every plugin.json parses, has the fields each ecosystem requires,
and that marketplace catalogs reference plugin directories that actually exist.

Run with:
    uv run pytest tests/test_manifests.py -v
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent

CODEX_REQUIRED_FIELDS = ("name", "version", "description", "skills")
CLAUDE_REQUIRED_FIELDS = ("name", "version", "description")


def _codex_manifests() -> list[Path]:
    return sorted(REPO_ROOT.glob("*/.codex-plugin/plugin.json"))


def _claude_manifests() -> list[Path]:
    return sorted(REPO_ROOT.glob("*/.claude-plugin/plugin.json"))


def _rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


@pytest.mark.parametrize("manifest", _codex_manifests(), ids=_rel)
def test_codex_plugin_manifest(manifest: Path) -> None:
    data = json.loads(manifest.read_text())
    for field in CODEX_REQUIRED_FIELDS:
        assert field in data, f"{_rel(manifest)}: missing field `{field}`"
    skills_path = (manifest.parent.parent / data["skills"].lstrip("./")).resolve()
    assert skills_path.is_dir(), (
        f"{_rel(manifest)}: skills path `{data['skills']}` does not resolve to a directory"
    )


@pytest.mark.parametrize("manifest", _claude_manifests(), ids=_rel)
def test_claude_plugin_manifest(manifest: Path) -> None:
    data = json.loads(manifest.read_text())
    for field in CLAUDE_REQUIRED_FIELDS:
        assert field in data, f"{_rel(manifest)}: missing field `{field}`"


def test_codex_marketplace() -> None:
    marketplace = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
    if not marketplace.exists():
        pytest.skip("Codex marketplace.json not present")
    data = json.loads(marketplace.read_text())
    plugins = data.get("plugins", [])
    assert plugins, f"{_rel(marketplace)}: no plugins listed"
    for entry in plugins:
        name = entry["name"]
        source = entry["source"]
        assert source.get("source") == "local", (
            f"{_rel(marketplace)}: plugin {name} uses unsupported source `{source.get('source')}`; "
            "this test only validates `local` sources"
        )
        plugin_dir = (REPO_ROOT / source["path"].lstrip("./")).resolve()
        plugin_manifest = plugin_dir / ".codex-plugin" / "plugin.json"
        assert plugin_manifest.exists(), (
            f"{_rel(marketplace)}: plugin {name} points at `{source['path']}` "
            f"but `{plugin_manifest.relative_to(REPO_ROOT)}` does not exist"
        )
        manifest_name = json.loads(plugin_manifest.read_text())["name"]
        assert manifest_name == name, (
            f"{_rel(marketplace)}: plugin name `{name}` does not match "
            f"`{plugin_manifest.relative_to(REPO_ROOT)}` name `{manifest_name}`"
        )


def test_claude_marketplace() -> None:
    marketplace = REPO_ROOT / ".claude-plugin" / "marketplace.json"
    if not marketplace.exists():
        pytest.skip("Claude marketplace.json not present")
    data = json.loads(marketplace.read_text())
    plugins = data.get("plugins", [])
    assert plugins, f"{_rel(marketplace)}: no plugins listed"
    for entry in plugins:
        name = entry["name"]
        source = entry["source"]
        plugin_dir = (REPO_ROOT / source.lstrip("./")).resolve()
        plugin_manifest = plugin_dir / ".claude-plugin" / "plugin.json"
        assert plugin_manifest.exists(), (
            f"{_rel(marketplace)}: plugin {name} points at `{source}` "
            f"but `{plugin_manifest.relative_to(REPO_ROOT)}` does not exist"
        )
        manifest_name = json.loads(plugin_manifest.read_text())["name"]
        assert manifest_name == name, (
            f"{_rel(marketplace)}: plugin name `{name}` does not match "
            f"`{plugin_manifest.relative_to(REPO_ROOT)}` name `{manifest_name}`"
        )

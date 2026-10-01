"""
Validate plugin manifests for Claude Code, Codex, and Cursor.

Checks that every plugin.json parses, has the fields each ecosystem requires,
and that marketplace catalogs reference plugin directories that actually exist.

Run with:
    uv run pytest tests/test_manifests.py -v
"""

import json
import re
from pathlib import Path

import frontmatter
import pytest

REPO_ROOT = Path(__file__).parent.parent

CODEX_REQUIRED_FIELDS = ("name", "version", "description", "skills")
CLAUDE_REQUIRED_FIELDS = ("name", "version", "description")


def _codex_manifests() -> list[Path]:
    return sorted(REPO_ROOT.glob(".codex-plugin/plugin.json")) + sorted(
        REPO_ROOT.glob("*/.codex-plugin/plugin.json")
    )


def _claude_manifests() -> list[Path]:
    return sorted(REPO_ROOT.glob(".claude-plugin/plugin.json")) + sorted(
        REPO_ROOT.glob("*/.claude-plugin/plugin.json")
    )


def _rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


@pytest.mark.parametrize("manifest", _codex_manifests(), ids=_rel)
def test_codex_plugin_manifest(manifest: Path) -> None:
    data = json.loads(manifest.read_text())
    for field in CODEX_REQUIRED_FIELDS:
        assert field in data, f"{_rel(manifest)}: missing field `{field}`"
    skills = data["skills"]
    for skills_entry in skills if isinstance(skills, list) else [skills]:
        skills_path = (manifest.parent.parent / skills_entry.lstrip("./")).resolve()
        assert skills_path.is_dir(), (
            f"{_rel(manifest)}: skills path `{skills_entry}` does not resolve to a directory"
        )


@pytest.mark.parametrize("manifest", _claude_manifests(), ids=_rel)
def test_claude_plugin_manifest(manifest: Path) -> None:
    data = json.loads(manifest.read_text())
    for field in CLAUDE_REQUIRED_FIELDS:
        assert field in data, f"{_rel(manifest)}: missing field `{field}`"


def test_cursor_plugin_manifest() -> None:
    manifest = REPO_ROOT / ".cursor-plugin" / "plugin.json"
    data = json.loads(manifest.read_text())
    for field in ("name", "version", "description", "author", "license", "skills", "logo"):
        assert data.get(field), f"{_rel(manifest)}: missing or empty field `{field}`"
    assert re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", data["name"])
    assert data["author"]["name"]
    assert isinstance(data["skills"], list) and data["skills"]
    for entry in [*data["skills"], data["logo"]]:
        path = Path(entry)
        assert not path.is_absolute() and ".." not in path.parts, (
            f"{_rel(manifest)}: path must stay inside the plugin: `{entry}`"
        )
        resolved = (REPO_ROOT / path).resolve()
        assert resolved.is_relative_to(REPO_ROOT.resolve()), (
            f"{_rel(manifest)}: path resolves outside the plugin: `{entry}`"
        )
        assert resolved.exists(), f"{_rel(manifest)}: missing path `{entry}`"
    assert (REPO_ROOT / data["logo"]).is_file()


def test_cursor_skills() -> None:
    data = json.loads((REPO_ROOT / ".cursor-plugin" / "plugin.json").read_text())
    names = set()
    for entry in data["skills"]:
        skills_dir = REPO_ROOT / entry
        assert skills_dir.is_dir(), f"Not a skills directory: `{entry}`"
        skill_files = sorted(skills_dir.glob("*/SKILL.md"))
        assert skill_files, f"No skills found in `{entry}`"
        for skill_file in skill_files:
            skill = frontmatter.loads(skill_file.read_text())
            name = skill.get("name")
            assert name == skill_file.parent.name, f"{_rel(skill_file)}: name must match directory"
            assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)
            assert name not in names, f"Duplicate Cursor skill: `{name}`"
            names.add(name)
            assert isinstance(skill.get("description"), str) and skill["description"].strip(), (
                f"{_rel(skill_file)}: missing or empty description"
            )
            assert skill.content.strip(), f"{_rel(skill_file)}: missing instructions"


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

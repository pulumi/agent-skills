"""Build Gemini release assets from the combined Pulumi plugin's skill directories."""

import argparse
import io
import json
from pathlib import Path
import re
import shutil
import tarfile

REPO_ROOT = Path(__file__).resolve().parent.parent
PLATFORMS = ("darwin", "linux", "win32")


def build_packages(
    repo_root: Path, output_dir: Path, release_tag: str | None = None
) -> list[Path]:
    """Package existing skills without changing their source directories."""
    plugin = json.loads((repo_root / ".claude-plugin/plugin.json").read_text())
    manifest_path = repo_root / "gemini/gemini-extension.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["version"] = plugin.get("version")
    for field in ("name", "version", "description"):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            raise ValueError(f"Gemini manifest requires {field}")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", manifest["name"]):
        raise ValueError("Gemini extension name must be lowercase kebab-case")
    if not re.fullmatch(
        r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", manifest["version"]
    ):
        raise ValueError("Combined plugin version must be a stable major.minor.patch version")
    if release_tag is not None and release_tag != f"v{manifest['version']}":
        raise ValueError("Release tag must match the Gemini manifest version")

    skills: dict[str, Path] = {}
    for group in plugin["skills"]:
        group_path = repo_root / group
        found = sorted(group_path.glob("*/SKILL.md"))
        if not found:
            raise ValueError(f"No skills found in {group}")
        for skill_file in found:
            name = skill_file.parent.name
            if name in skills:
                raise ValueError(f"Duplicate skill directory: {name}")
            skills[name] = skill_file.parent

    output_dir.mkdir(parents=True, exist_ok=True)
    archives = [
        output_dir / f"{platform}.{manifest['name']}-gemini.tar.gz"
        for platform in PLATFORMS
    ]
    with tarfile.open(archives[0], "w:gz") as archive:
        manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode()
        manifest_entry = tarfile.TarInfo("gemini-extension.json")
        manifest_entry.size = len(manifest_bytes)
        archive.addfile(manifest_entry, io.BytesIO(manifest_bytes))
        archive.add(repo_root / "LICENSE", arcname="LICENSE")
        for name, directory in sorted(skills.items()):
            archive.add(directory, arcname=f"skills/{name}")
    # Gemini needs platform prefixes when other assets share the release.
    for archive in archives[1:]:
        shutil.copyfile(archives[0], archive)
    return archives


def main() -> None:
    """Build the platform-named archives for a local check or GitHub release."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "dist/gemini")
    parser.add_argument("--release-tag")
    args = parser.parse_args()
    for archive in build_packages(REPO_ROOT, args.output_dir, args.release_tag):
        print(archive)


if __name__ == "__main__":
    main()

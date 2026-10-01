# Cursor plugin release guide

The root Cursor plugin packages the same end-user skills as the root Claude Code and Codex plugins.
It reads `pulumi/skills`, `migration/skills`, and `delegation/skills` directly.
The provider maintenance group is separate and is not included in this plugin.

## Validate the package

Run from the repository root:

```bash
uv sync --locked --group dev
uv run pytest tests/test_manifests.py -v --tb=short
git diff --check
```

The offline tests check manifest paths, skill names and frontmatter, the logo, and matching versions
and skill directories across the three root manifests. They do not test skill loading in Cursor.

## Install locally

Run from the repository root. This copies the plugin files and refuses to overwrite an existing local install:

```bash
(
  set -e
  cursor_plugin_dir="$HOME/.cursor/plugins/local/pulumi"
  mkdir -p "$HOME/.cursor/plugins/local"
  mkdir "$cursor_plugin_dir"
  cp -R .cursor-plugin assets pulumi migration delegation docs "$cursor_plugin_dir/"
  cp README.md LICENSE AGENTS.md CONTRIBUTING.md "$cursor_plugin_dir/"
)
```

To test another revision, move the previous local copy outside `~/.cursor/plugins/local`, then repeat the copy.
Use a copy because Cursor skips symlinks that point outside its local plugin folder.

Restart Cursor, or run **Developer: Reload Window**. Open **Customize** and check that Pulumi's skills appear.
Local imports must be allowed by the team's **Allow Local Plugin Imports** setting.
An installed marketplace plugin with the same name takes precedence over this local copy.
See [Cursor's local testing instructions](https://cursor.com/docs/plugins#test-plugins-locally).

## Test in Cursor

Use a scratch workspace without another Pulumi skill installation. Confirm that every skill directory
in the three groups appears in **Customize**. The initial package contains 15 skills.

Run each prompt in a new Agent conversation. Check which skill Cursor loads and whether it reads the
skill's reference files when needed. These prompts require no deployment or Pulumi Cloud login.

| Prompt | Expected skill and result |
| --- | --- |
| Use the pulumi-best-practices skill to explain how to pass an S3 bucket output to another resource. Show a TypeScript example. Do not run commands. | `pulumi-best-practices`; explains Pulumi outputs and shows code. |
| Use the pulumi-terraform-to-pulumi skill to outline how to migrate a Terraform module. Read its reference files as needed. Do not run commands. | `pulumi-terraform-to-pulumi`; outlines the migration workflow without changing state. |
| Use the pulumi-neo-handoff skill to explain what context and access you need before handing work to Neo. Do not create a task or run commands. | `pulumi-neo-handoff`; explains the required handoff context and access. |

Record the Git commit, Cursor version, discovered skill count, and prompt results in the release review.

### Initial release validation

Validation for plugin version `2.0.7`, completed on 2026-10-01:

| Check | Result |
| --- | --- |
| Offline manifest tests | All 15 tests passed. |
| Local package copy | Verified all 15 skills, 56 skill and reference files, and the logo. A repeat install correctly refused to overwrite the existing package. |
| Cursor installation and invocation | Mark confirmed that the local installation and test sequence worked. |

## Submit the first release

Complete the local test before submission. Cursor requires a public repository, valid component files,
relative manifest paths, and a README with usage and configuration details.
See [Cursor's submission checklist](https://cursor.com/docs/reference/plugins#submission-checklist).

| Item | Value or action |
| --- | --- |
| Repository | `https://github.com/pulumi/agent-skills` |
| Plugin name | `pulumi`; confirm availability during submission. |
| Manifest | `.cursor-plugin/plugin.json` at the repository root. |
| Version | Read `version` from the manifest. |
| Publisher and license | Pulumi; Apache-2.0. |
| Logo | `assets/logo.png`, already in the repository. |
| Public source | Merge the reviewed change into the public repository before submitting its URL. |
| Submission | A Pulumi maintainer opens [Publish a plugin](https://cursor.com/marketplace/publish), signs in, completes the publisher application, and submits the repository URL. The application fields require sign-in to inspect. |
| Review | Respond to Cursor's review requests. Record the accepted version and listing URL. |
| After approval | Install from the marketplace in a clean workspace and repeat the smoke test. Replace the pending notice in the README with the verified listing and installation steps. |

This is one Cursor plugin, so it does not need a Cursor marketplace catalog for multiple plugins.

## Release updates

1. Update the shared skill files or Cursor metadata.
2. Bump the version in all three root plugin manifests. For skill changes, also bump the affected group's
   Claude Code and Codex manifests as described in [AGENTS.md](../AGENTS.md#adding-a-new-skill).
3. Run the offline tests and repeat the local Cursor test with a fresh copy.
4. Merge the reviewed change and use the submission's review channel to request an updated listing.
5. Verify the approved version from the marketplace before announcing it.

Cursor reviews each public marketplace update. A source commit alone does not publish an update.
See [Cursor's update review policy](https://cursor.com/help/security-and-privacy/marketplace-security#are-plugin-updates-reviewed).

Cursor documentation checked on 2026-10-01. Confirm the live submission form and update instructions before release.

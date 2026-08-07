# Pulumi Agent Skills

This repository contains official Pulumi agent skills for infrastructure as code workflows.

## Repository Structure

Skills are organized into four plugin groups:

### Migration Plugin (`migration/`)

Skills for converting and importing infrastructure from other tools to Pulumi:

- **pulumi-terraform-to-pulumi**: Migrate Terraform projects to Pulumi
- **pulumi-cdk-to-pulumi**: Migrate AWS CDK applications to Pulumi
- **cloudformation-to-pulumi**: Migrate AWS CloudFormation stacks/templates to Pulumi
- **pulumi-arm-to-pulumi**: Migrate Azure ARM templates and Bicep to Pulumi
- **pulumi-migrate-from-discovered-stack**: Migrate a CloudFormation or ARM stack that Pulumi Cloud's Discovery feature has already found, using the discovered-stacks API

### Pulumi Plugin (`pulumi/`)

Entry-point and specialized skills for writing and operating Pulumi infrastructure:

- **pulumi-overview**: Entry-point skill across `pulumi do`, IaC projects, and Pulumi Cloud; routes to specialized skills
- **pulumi-best-practices**: Best practices for writing reliable Pulumi programs
- **pulumi-component**: Guide for authoring ComponentResource classes
- **pulumi-automation-api**: Best practices for using Pulumi Automation API
- **pulumi-esc**: Guidance for working with Pulumi ESC (Environments, Secrets, and Configuration)
- **pulumi-debug-failed-operation**: Debug a failed `pulumi up` or `pulumi preview` from the failure Pulumi already recorded
- **provider-upgrade**: Safe workflows for upgrading Pulumi providers without unintended infrastructure changes
- **package-usage**: Track which stacks across an organization use a package and at what versions

### Package Maintenance Plugin (`package-maintenance/`)

Skills for maintaining Pulumi provider repositories (provider authors and bridge maintainers):

- **pulumi-upgrade-provider**: Automate Pulumi provider repo upgrades with the upgrade-provider tool
- **upstream-patches**: Create, amend, remove, and rebase patches for Terraform provider submodules

### Delegation Plugin (`delegation/`)

Skills for handing off in-progress work from coding agents to Pulumi Neo for delegated execution:

- **pulumi-neo-handoff**: Transfer the current work to a new Pulumi Neo task with goal, repository pointers, and a compacted conversation summary

## Installation

### Claude Code Plugin System

```bash
/plugin marketplace add pulumi/agent-skills
/plugin install pulumi                        # all end-user skills (authoring + migration + Neo handoff)
```

The `pulumi` plugin is the combined plugin defined at the repo root: `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json` list `pulumi/skills/`, `migration/skills/`, and `delegation/skills/` in their `skills` fields. Granular alternatives (do not combine with `pulumi`, which already includes the first two):

```bash
/plugin install pulumi-migration              # migration skills only
/plugin install pulumi-delegation             # Neo handoff skill only
/plugin install pulumi-package-maintenance    # provider-repo maintenance skills
```

### OpenAI Codex

```bash
codex plugin marketplace add pulumi/agent-skills
```

After the marketplace registers, install plugins from the Codex TUI: run `codex`, open the plugin marketplace with `/plugins`, and pick `pulumi-migration`, `pulumi`, `pulumi-delegation`, or `pulumi-package-maintenance`. As in Claude Code, `pulumi` is the combined plugin with all end-user skills; do not combine it with `pulumi-migration` or `pulumi-delegation`.

### Universal (all agents)

Install all skills:

```bash
npx skills add pulumi/agent-skills --skill '*'
```

Or install individual plugin groups:

```bash
npx skills add pulumi/agent-skills/migration --skill '*'             # 5 migration skills
npx skills add pulumi/agent-skills/pulumi --skill '*'                # 8 pulumi skills (overview + specialized)
npx skills add pulumi/agent-skills/delegation --skill '*'            # 1 delegation skill
npx skills add pulumi/agent-skills/package-maintenance --skill '*'   # 2 package-maintenance skills
```

This works with Claude Code, Cursor, Copilot, Codex, and other agent tools.

## Skill Writing Conventions

### Skill Name Format

Skill names follow the pattern: `pulumi-<feature>`. The entry-point router is **`pulumi-overview`** (install via the `pulumi` plugin).

### Trigger Phrases

Skill descriptions should include keywords and phrases that trigger automatic activation. Use "MUST be loaded when" or "Use when" to clarify activation criteria.

Example:
```yaml
description: Convert an AWS CDK application to Pulumi. This skill MUST be loaded whenever a user requests migration or conversion of a CDK application to Pulumi.
```

### Progressive Disclosure

Keep the main SKILL.md file focused and concise (under 500 lines recommended). For detailed reference material, add additional markdown files in the skill directory with meaningful names.

Example structure:
```
pulumi-cdk-to-pulumi/
├── SKILL.md              # Main skill file
├── cdk-convert.md        # Reference: cdk2pulumi tool usage
├── cdk-importer.md       # Reference: cdk-importer tool usage
└── cloudformation-id-lookup.md  # Reference: import ID lookup
```

Reference these files from the main SKILL.md using relative links:
```markdown
For detailed tool usage, see [cdk-convert.md](cdk-convert.md).
```

### Cross-Skill References

When one skill references another, use the pattern: `Use skill <skill-name>`.

Example:
- "Use skill `pulumi-component` for in-depth component authoring guidance"

## Testing

The `tests/` directory contains three pytest-based test suites that run automatically on every pull request via `.github/workflows/tests.yml`. Two require `ANTHROPIC_API_KEY`; the manifest test runs offline.

### Manifest validation (`test_manifests.py`)

Validates that each plugin manifest (`<plugin>/.claude-plugin/plugin.json` and `<plugin>/.codex-plugin/plugin.json`) parses, has the required fields, and that the marketplace catalogs reference plugin directories that actually exist. Runs offline and gates PRs from forks before the LLM-driven jobs.

### Skill routing accuracy (`test_skill_selection_accuracy.py`)

Each skill directory contains a `use_cases.yaml` file with a `queries:` list of user prompts that are expected to activate that skill:

```yaml
# <skill-name>/use_cases.yaml
queries:
  - "Convert my Terraform code to Pulumi TypeScript"
  - "Migrate our Terraform state to Pulumi"
```

The test loads every `use_cases.yaml` across the tree and asserts that each query triggers the owning skill.

**When adding or modifying a skill**, update (or create) `use_cases.yaml` with representative prompts that should activate it.

### Skill quality review (`test_skill_quality.py`)

An LLM judge reads each `SKILL.md` and checks it against a quality rubric (description clarity and trigger precision, lean body, explains WHY not just what, progressive disclosure). The test fails on HIGH-severity findings and prints all issues (including medium and low) for visibility.

### Running locally

```bash
uv sync --group dev

# Routing accuracy
uv run pytest tests/test_skill_selection_accuracy.py -v

# Quality review (use -s to see the full critique)
uv run pytest tests/test_skill_quality.py -v -s

# All tests
uv run pytest tests/ -v
```

## Adding a New Skill

1. Determine which plugin group the skill belongs to (migration, pulumi, delegation, or package-maintenance)
2. Create the skill directory: `<plugin>/skills/<skill-name>/`
3. Write the `SKILL.md` file with proper frontmatter:
   ```yaml
   ---
   name: skill-name
   description: Clear description with activation triggers
   ---
   ```
4. Add `use_cases.yaml` with representative trigger queries (see [Testing](#testing) above)
5. Update this AGENTS.md file to list the new skill in the appropriate plugin section
6. Update [README.md](README.md) to add the skill to the skills table
7. Bump the containing plugin's patch version in both `<plugin>/.claude-plugin/plugin.json` and `<plugin>/.codex-plugin/plugin.json`. For skills in an end-user group (`pulumi/`, `migration/`, `delegation/`), also bump the root combined manifests `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`, which ship the same skill
8. Submit a pull request

The skill will automatically be included in its plugin group, but installed plugin users need a plugin version bump to receive changed plugin contents. Any change under an existing plugin directory that affects shipped skills, references, agents, hooks, MCP config, or install-surface metadata must bump that plugin's version in both ecosystem manifests. Use a patch bump for skill-content and routing changes unless the change is intentionally breaking or feature-sized.

Examples:

- Editing `package-maintenance/skills/pulumi-upgrade-provider/SKILL.md` requires bumping both `package-maintenance/.claude-plugin/plugin.json` and `package-maintenance/.codex-plugin/plugin.json`.
- Adding `pulumi/skills/new-skill/` requires bumping both `pulumi/.claude-plugin/plugin.json` and `pulumi/.codex-plugin/plugin.json`.
- Creating a brand-new plugin group starts with its initial manifest version; no additional bump is needed in the same PR.

## Creating a New Plugin Group

Each plugin group ships a manifest for both Claude Code and OpenAI Codex. The skill content is shared; only the per-ecosystem manifest files differ.

If the new group is end-user facing (not maintainer tooling), also add its `skills/` directory to the `skills` lists in both root combined plugin manifests, [.claude-plugin/plugin.json](.claude-plugin/plugin.json) and [.codex-plugin/plugin.json](.codex-plugin/plugin.json), so installing `pulumi` picks it up in both ecosystems.

1. Create the plugin directory structure:
   ```
   <plugin-name>/
   ├── .claude-plugin/
   │   └── plugin.json
   ├── .codex-plugin/
   │   └── plugin.json
   └── skills/
   ```

2. Create the Claude manifest at `<plugin-name>/.claude-plugin/plugin.json`:
   ```json
   {
     "name": "pulumi-<plugin-name>",
     "version": "1.0.0",
     "description": "Plugin description",
     "author": { "name": "Pulumi", "url": "https://github.com/pulumi" },
     "homepage": "https://www.pulumi.com/docs/",
     "repository": "https://github.com/pulumi/agent-skills",
     "license": "Apache-2.0",
     "keywords": ["pulumi", "..."]
   }
   ```

3. Create the Codex manifest at `<plugin-name>/.codex-plugin/plugin.json`. The fields mirror the Claude manifest with two additions: `skills` points at the skills directory, and `interface` holds TUI presentation metadata.
   ```json
   {
     "name": "pulumi-<plugin-name>",
     "version": "1.0.0",
     "description": "Plugin description",
     "skills": "./skills/",
     "author": { "name": "Pulumi", "url": "https://github.com/pulumi" },
     "homepage": "https://www.pulumi.com/docs/",
     "repository": "https://github.com/pulumi/agent-skills",
     "license": "Apache-2.0",
     "keywords": ["pulumi", "..."],
     "interface": {
       "displayName": "Display Name",
       "shortDescription": "One-line summary",
       "developerName": "Pulumi",
       "category": "Coding"
     }
   }
   ```

4. Add an entry to [.claude-plugin/marketplace.json](.claude-plugin/marketplace.json):
   ```json
   {
     "name": "pulumi-<plugin-name>",
     "source": "./<plugin-name>",
     "description": "Plugin description",
     "category": "appropriate-category"
   }
   ```

5. Add an entry to [.agents/plugins/marketplace.json](.agents/plugins/marketplace.json) (the Codex marketplace catalog):
   ```json
   {
     "name": "pulumi-<plugin-name>",
     "source": { "source": "local", "path": "./<plugin-name>" },
     "policy": { "installation": "AVAILABLE" },
     "category": "Coding"
   }
   ```

6. Add skills to `<plugin-name>/skills/`
7. Update this AGENTS.md and README.md
8. Submit a pull request

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed contribution guidelines, including skill quality standards, formatting requirements, and the review process.

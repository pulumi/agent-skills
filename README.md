# Pulumi Agent Skills

A collection of [Agent Skills](https://agentskills.io) for infrastructure as code workflows with Pulumi. These skills teach AI coding assistants how to help with infrastructure migrations, secret management, and code translation.

## What are Agent Skills?

Agent Skills are reusable knowledge packages that teach AI coding assistants domain-specific workflows. They follow the [agentskills.io](https://agentskills.io) open standard and work with:

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- [GitHub Copilot](https://docs.github.com/en/copilot)
- [Cursor](https://cursor.sh)
- [VS Code](https://code.visualstudio.com/docs/copilot)
- [OpenAI Codex](https://openai.com/api/)

## Repository Structure

Skills are organized into four plugin groups:

```
pulumi-agent-skills/
├── migration/             # Convert and import from other tools
├── pulumi/                # Entry-point and specialized Pulumi skills
├── package-maintenance/   # Maintain Pulumi provider repositories
└── delegation/            # Hand off work to Pulumi Neo
```

## Available Skills

### Migration Skills

Convert and import infrastructure from other tools to Pulumi:

| Skill | Description |
|-------|-------------|
| [pulumi-terraform-to-pulumi](migration/skills/pulumi-terraform-to-pulumi) | Migrate Terraform projects to Pulumi |
| [pulumi-cdk-to-pulumi](migration/skills/pulumi-cdk-to-pulumi) | Migrate AWS CDK applications to Pulumi |
| [cloudformation-to-pulumi](migration/skills/cloudformation-to-pulumi) | Migrate AWS CloudFormation stacks/templates to Pulumi |
| [pulumi-arm-to-pulumi](migration/skills/pulumi-arm-to-pulumi) | Migrate Azure ARM templates and Bicep to Pulumi |
| [pulumi-migrate-from-discovered-stack](migration/skills/pulumi-migrate-from-discovered-stack) | Migrate a CloudFormation or ARM stack that Pulumi Cloud's Discovery feature has already found, using the discovered-stacks API |

### Pulumi Skills

Entry-point and specialized skills for writing and operating Pulumi infrastructure:

| Skill | Description |
|-------|-------------|
| [pulumi-overview](pulumi/skills/pulumi-overview) | Entry-point across `pulumi do`, IaC projects, and Pulumi Cloud; routes to specialized skills |
| [pulumi-best-practices](pulumi/skills/pulumi-best-practices) | Best practices for writing reliable Pulumi programs |
| [pulumi-component](pulumi/skills/pulumi-component) | Guide for authoring ComponentResource classes |
| [pulumi-automation-api](pulumi/skills/pulumi-automation-api) | Best practices for using Pulumi Automation API |
| [pulumi-esc](pulumi/skills/pulumi-esc) | Guidance for working with Pulumi ESC (Environments, Secrets, and Configuration) |
| [pulumi-debug-failed-operation](pulumi/skills/pulumi-debug-failed-operation) | Debug a failed `pulumi up` or `pulumi preview` from the failure Pulumi already recorded |
| [provider-upgrade](pulumi/skills/provider-upgrade) | Safe workflows for upgrading Pulumi providers without unintended infrastructure changes |
| [package-usage](pulumi/skills/package-usage) | Track which stacks across an organization use a package and at what versions |

### Package Maintenance Skills

Maintain Pulumi provider repositories (provider authors and bridge maintainers):

| Skill | Description |
|-------|-------------|
| [pulumi-upgrade-provider](package-maintenance/skills/pulumi-upgrade-provider) | Automate Pulumi provider repo upgrades |
| [upstream-patches](package-maintenance/skills/upstream-patches) | Manage upstream Terraform patch stacks in provider repos |

### Delegation Skills

Hand off in-progress work from coding agents to Pulumi Neo:

| Skill | Description |
|-------|-------------|
| [pulumi-neo-handoff](delegation/skills/pulumi-neo-handoff) | Transfer the current work to a Pulumi Neo task with goal, repository pointers, and a compacted conversation summary |

## Installation

### Claude Code Plugin System

```bash
/plugin marketplace add pulumi/agent-skills
/plugin install pulumi                        # All end-user skills: authoring, migration, and Neo handoff
```

The `pulumi` plugin bundles the authoring, migration, and delegation skill groups in one install. Prefer a subset? Install `pulumi-migration` or `pulumi-delegation` instead (not alongside `pulumi`, which already includes both). `pulumi-package-maintenance` is separate: it targets provider authors and combines fine with any of the others.

```bash
/plugin install pulumi-migration              # Migration skills only
/plugin install pulumi-delegation             # Neo handoff skill only
/plugin install pulumi-package-maintenance    # Provider-repo maintenance skills (for provider authors)
```

#### Declarative install via `settings.json`

To register the marketplace and enable plugins automatically (for a team or CI), add this to `.claude/settings.json`. The marketplace key **must** be `pulumi-agent-skills`: it has to match the `name` field in this repo's [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json), and the same name is used as the `@<marketplace>` suffix in `enabledPlugins`:

```json
{
  "extraKnownMarketplaces": {
    "pulumi-agent-skills": {
      "source": { "source": "github", "repo": "pulumi/agent-skills" }
    }
  },
  "enabledPlugins": {
    "pulumi@pulumi-agent-skills": true
  }
}
```

The `pulumi` plugin covers authoring, migration, and delegation. Swap in `pulumi-migration` or `pulumi-delegation` for a subset, or add `pulumi-package-maintenance` for provider-repo maintenance.

If you name the marketplace anything else (e.g. `pulumi-skills`), the plugins fail to resolve with `Plugin '…' not found in marketplace '…'`.

### OpenAI Codex

```bash
codex plugin marketplace add pulumi/agent-skills
```

Once the marketplace is registered, install plugins from the Codex TUI: run `codex`, open the plugin marketplace with `/plugins`, and pick `pulumi-migration`, `pulumi`, `pulumi-delegation`, or `pulumi-package-maintenance`. As in Claude Code, `pulumi` is the combined plugin with all end-user skills; do not combine it with `pulumi-migration` or `pulumi-delegation`.

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

## Usage Examples

### General Pulumi Infrastructure

Ask your AI assistant:

```text
Use pulumi do to create an S3 bucket and a Cloudflare DNS record
```

The assistant will use the `pulumi-overview` skill and route to specialized skills when needed.

### Terraform to Pulumi Migration

Ask your AI assistant:
> "Convert this Terraform configuration to Pulumi TypeScript"

The assistant will use the `pulumi-terraform-to-pulumi` skill to produce idiomatic Pulumi code.

### CDK to Pulumi Migration

Ask your AI assistant:

```text
Help me migrate my CDK application to Pulumi
```

The assistant will use the `pulumi-cdk-to-pulumi` skill to guide you through the complete migration workflow.

### Managing Secrets with ESC

Ask your AI assistant:

```text
Set up AWS OIDC credentials using Pulumi ESC
```

The assistant will use the `pulumi-esc` skill to help configure dynamic credentials.

### Writing Components

Ask your AI assistant:

```text
Help me create a reusable Pulumi component for a web service
```

The assistant will use the `pulumi-component` skill to guide you through component authoring best practices.

### Upgrading Providers

Ask your AI assistant:

```text
Help me upgrade the Pulumi AWS provider safely without changing real infrastructure
```

The assistant will use the `provider-upgrade` skill to guide you through a low-risk upgrade workflow.

### Handing Off Work to Pulumi Neo

Ask your AI assistant:

```text
Hand this off to Neo to apply the staging migration in production
```

The assistant will use the `pulumi-neo-handoff` skill to package the goal, repository state, and conversation summary into a new Pulumi Neo task and return a task URL.

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:

- Writing new skills
- Improving existing skills
- Reporting issues

Also see [AGENTS.md](AGENTS.md) for agent-specific documentation on skill conventions, cross-skill references, and plugin structure.

## License

Apache 2.0 - See [LICENSE](LICENSE) for details.

## Resources

- [Pulumi Documentation](https://www.pulumi.com/docs/)
- [Agent Skills Specification](https://agentskills.io/specification)
- [Pulumi ESC Documentation](https://www.pulumi.com/docs/esc/)

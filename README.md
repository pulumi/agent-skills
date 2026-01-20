# Pulumi Agent Skills

A collection of [Agent Skills](https://agentskills.io) for infrastructure as code workflows with Pulumi. These skills teach AI coding assistants how to help with infrastructure migrations, secret management, and code translation.

## What are Agent Skills?

Agent Skills are reusable knowledge packages that teach AI coding assistants domain-specific workflows. They follow the [agentskills.io](https://agentskills.io) open standard and work with:

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- [GitHub Copilot](https://docs.github.com/en/copilot)
- [Cursor](https://cursor.sh)
- [VS Code](https://code.visualstudio.com/docs/copilot)

## Available Skills

| Skill | Description | Prerequisites |
|-------|-------------|---------------|
| **terraform-translation** | Convert Terraform HCL to Pulumi TypeScript | Pulumi CLI, Node.js |
| **cdk-to-pulumi** | Migrate AWS CDK applications to Pulumi | Pulumi CLI, AWS CDK, cdk2pulumi plugin |
| **cdk-convert** | Convert CDK Cloud Assemblies to Pulumi YAML | Pulumi CLI, cdk2pulumi plugin |
| **cdk-importer** | Import CDK-managed infrastructure into Pulumi state | Pulumi CLI, cdk-importer plugin, AWS credentials |
| **cloudformation-id-lookup** | Look up Pulumi import ID formats for AWS resources | Pulumi CLI, cdk2pulumi plugin |
| **esc** | Manage Pulumi ESC (Environments, Secrets, Configuration) | Pulumi CLI |

## Installation

### Claude Code

Add to your Claude Code settings (`~/.claude/settings.json`):

```json
{
  "skills": [
    "pulumi/skills"
  ]
}
```

Or add to a project's `.claude/settings.json` for project-specific skills.

### GitHub Copilot / VS Code

Clone or download skills to your project's `.github/skills/` directory:

```bash
git clone https://github.com/pulumi/skills.git .github/skills/pulumi
```

Or to your personal skills directory:

```bash
git clone https://github.com/pulumi/skills.git ~/.copilot/skills/pulumi
```

### Cursor

Add to your project's `.cursor/skills/` directory:

```bash
git clone https://github.com/pulumi/skills.git .cursor/skills/pulumi
```

## Usage Examples

### Terraform to Pulumi Migration

Ask your Aagent:
> "Convert this Terraform configuration to Pulumi TypeScript"

The assistant will use the `terraform-translation` skill to produce idiomatic Pulumi code.

### CDK to Pulumi Migration

Ask your AI assistant:

```text
Help me migrate my CDK application to Pulumi
```

The assistant will use the `cdk-to-pulumi` skill to guide you through the complete migration workflow.

### Managing Secrets with ESC

Ask your AI assistant:

```text
Set up AWS OIDC credentials using Pulumi ESC"
```

The assistant will use the `esc` skill to help configure dynamic credentials.

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:

- Writing new skills
- Improving existing skills
- Reporting issues

## License

Apache 2.0 - See [LICENSE](LICENSE) for details.

## Resources

- [Pulumi Documentation](https://www.pulumi.com/docs/)
- [Agent Skills Specification](https://agentskills.io/specification)
- [Pulumi ESC Documentation](https://www.pulumi.com/docs/esc/)
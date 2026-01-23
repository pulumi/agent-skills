# Contributing to Pulumi Agent Skills

Thank you for your interest in contributing to Pulumi's Agent Skills! This guide covers how to write, improve, and submit skills.

## What is a Skill?

A skill is a markdown file (`SKILL.md`) that teaches AI coding assistants how to help users with specific tasks. Skills follow the [agentskills.io](https://agentskills.io) open standard.

## Skill Format

Each skill lives in its own directory with a `SKILL.md` file:

```text
skills/
└── skill-name/
    └── SKILL.md
```

### SKILL.md Structure

```text
---
name: your-skill-name
description: A concise description of when this skill should be used. This helps the AI decide when to apply the skill.
---

# Skill Title

Skill content here...
```

### Required Frontmatter

| Field | Description |
|-------|-------------|
| `name` | Lowercase with hyphens, must match directory name |
| `description` | When the AI should use this skill (1-2 sentences) |

### Optional Frontmatter

| Field | Description |
|-------|-------------|
| `version` | Semantic version (e.g., "1.0.0") |
| `author` | Author name or organization |
| `license` | License identifier (defaults to repository license) |

## Writing Guidelines

### Be Directive

Use imperative voice. Tell the AI what to do, not what it could do.

```markdown
<!-- ✅ Good -->
Run `pulumi preview` to validate the changes.

<!-- ❌ Avoid -->
You might want to run `pulumi preview` to validate the changes.
```

### Be Specific

Provide exact commands, flags, and examples.

```markdown
<!-- ✅ Good -->
Install the plugin:

pulumi plugin install tool cdk2pulumi
```

```markdown
<!-- ❌ Avoid -->
Make sure the required plugins are installed.
```

### Show Before/After Examples

For transformation skills, show clear input/output pairs:

```markdown
## Terraform

resource "aws_s3_bucket" "example" {
  bucket = "my-bucket"
}
```

```markdown
## Pulumi TypeScript

const bucket = new aws.s3.Bucket("example", {
    bucket: "my-bucket",
});
```

### Explain Decision Points

When multiple approaches exist, explain the trade-offs:

```markdown
## Provider Selection

- **Use `@pulumi/aws-native`** when the resource type is available and you need CloudFormation parity
- **Use `@pulumi/aws`** when aws-native doesn't support the resource or you need Terraform-style behavior
```

### Document Prerequisites

List required tools, versions, and setup steps:

```markdown
## Prerequisites

- Pulumi CLI v3.0+
- Node.js 18+
- AWS credentials configured
```

### Include Error Handling

Guide users through common failure scenarios:

```markdown
## Troubleshooting

### "Resource not found" during import

This usually means the resource ID format is incorrect. Use `pulumi plugin run cdk2pulumi -- ids <resource-type>` to find the correct format.
```


## Standalone Requirement

**Skills must work without proprietary tools or internal APIs.**

### Do
- Reference publicly available CLI tools
- Link to public documentation
- Use standard credential methods (env vars, config files)

### Don't
- Reference internal APIs or tools
- Assume specific organizational context
- Require proprietary services not available to all users

### Example: Credential Handling

```markdown
<!-- ✅ Good - Multiple options -->
## Credentials

Configure AWS credentials using any standard method:
- Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
- AWS credentials file (`~/.aws/credentials`)
- IAM roles (for EC2, ECS, Lambda)
- Pulumi ESC environment

<!-- ❌ Avoid - Internal-only -->
## Credentials

Use the `call_internal_tool()` tool to authenticate.
```

## Quality Checklist

Before submitting a skill, verify:

- [ ] **Format**: YAML frontmatter has `name` and `description`
- [ ] **Naming**: `name` matches directory name, lowercase with hyphens
- [ ] **Standalone**: No references to internal tools or APIs
- [ ] **Public URLs**: All documentation links are publicly accessible
- [ ] **Examples**: Code examples are syntactically correct
- [ ] **Prerequisites**: Required tools and versions are documented
- [ ] **Tested**: Skill produces helpful results when used with an AI assistant

## Security Requirements

- [ ] No API keys, tokens, or credentials in skill content
- [ ] No internal URLs or staging environments
- [ ] No real AWS account IDs in examples (use placeholders like `123456789012`)
- [ ] No destructive commands without clear warnings
- [ ] No personal information or internal references

## Submitting Changes

### New Skills

1. Create a new directory under `skills/` with the skill name
2. Add a `SKILL.md` file following the format above
3. Test the skill with at least one AI coding assistant
4. Submit a pull request with:
   - Description of what the skill does
   - Example prompts that trigger the skill
   - Testing notes

### Improving Existing Skills

1. Fork the repository
2. Make your changes
3. Test the changes with an AI coding assistant
4. Submit a pull request with:
   - What you changed and why
   - Before/after examples if applicable

### Reporting Issues

Open an issue with:
- Which skill has the problem
- What you expected to happen
- What actually happened
- Example prompt you used

## Style Guide

### Markdown

- Use ATX-style headers (`#`, `##`, `###`)
- Use fenced code blocks with language identifiers
- Use tables for structured comparisons
- Keep lines under 120 characters when practical

### Code Examples

- Use realistic but simple examples
- Include necessary imports
- Add comments for non-obvious behavior
- Prefer TypeScript for Pulumi examples (most common)

## Getting Help

- [Pulumi Community Slack](https://slack.pulumi.com)
- [GitHub Discussions](https://github.com/pulumi/skills/discussions)
- [Pulumi Documentation](https://www.pulumi.com/docs/)

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.

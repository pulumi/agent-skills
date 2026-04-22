---
name: package-usage
description: Track which stacks across a Pulumi organization use a specific package and at what versions. Use for cross-stack audits, identifying outdated or unmaintained package versions across many stacks, finding affected stacks before publishing breaking changes to a component package, or planning coordinated upgrade rollouts. Do NOT use for upgrading a cloud provider package (pulumi-aws, pulumi-azure-native, pulumi-gcp, pulumi-kubernetes, etc.) in a single project — use skill `provider-upgrade` instead. Do NOT use for general infrastructure creation, resource provisioning, or how-to questions about a package.
---

## API Reference

### Get the latest version of a package

`GET /api/registry/packages?name={package_name}&orgLogin={orgName}`

You must include the `orgLogin` parameter with the user's organization name. The response contains a `packages` array. Each entry has a `version` field (the latest version), plus `name`, `publisher`, `source`, and `packageStatus`.

### Get stack usage for a package

`GET /api/orgs/{orgName}/packages/usage?packageName={package_name}`

Replace `{orgName}` with the org name from context, `PULUMI_ORG`, or ask the user.

Response fields:
- `packageName`: The queried package
- `stacks`: Array of `{stackName, projectName, version, lastUpdate}`
- `totalStacks`: Total count

## Workflow: Find outdated stacks

Use when the user wants to know which stacks are using an outdated version of a package.

1. Get the latest version of the package
2. Get stack usage for the package
3. Compare each stack's `version` against the latest to identify outdated stacks
4. Present results using the output format below

## Output Format

Present results as a markdown table followed by a summary line:

```
| Project | Stack | Current Version | Latest Version | Status |
|---------|-------|-----------------|----------------|--------|
| my-app  | dev   | 6.40.0          | 6.52.0         | Outdated |
| my-app  | prod  | 6.52.0          | 6.52.0         | Up-to-date |

2 of 2 stacks checked. 1 outdated.
```

## Out of scope: upgrading a specific stack

This skill identifies outdated stacks. It does not perform the upgrade itself. For actually bumping a package version in a project — editing `package.json`, `requirements.txt`, `pyproject.toml`, `go.mod`, or `Pulumi.yaml`, running `pulumi preview`, and reconciling the diff — hand off to the `provider-upgrade` skill.

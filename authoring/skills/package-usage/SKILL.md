---
name: package-usage
description: Track which stacks use a specific Pulumi package and at what versions, or upgrade a stack to the latest version of a package. Use when users ask about package version tracking, outdated package versions across stacks, upgrade candidates, or package usage audits. Also use when users want to upgrade/update a specific package version in a stack or project. Do NOT use for general infrastructure creation, resource provisioning, or questions about how to use a package.
---

## API Reference

### Get the latest version of a package

`GET /api/registry/packages?name={package_name}&orgLogin={orgName}`

You must include the `orgLogin` parameter with the user's organization name. The response contains a `packages` array. Each entry has a `version` field (the latest version), plus `name`, `publisher`, `source`, and `packageStatus`.

### Get stack usage for a package

`GET /api/orgs/{orgName}/packages/usage?packageName={package_name}`

Replace `{orgName}` with the organization name from context or the `PULUMI_ORG` environment variable.

Response fields:
- `packageName`: The queried package
- `stacks`: Array of `{stackName, projectName, version, lastUpdate}`
- `totalStacks`: Total count

## Workflow: Find outdated stacks

Use when the user wants to know which stacks are using an outdated version of a package.

1. Get the latest version of the package
2. Get stack usage for the package
3. Compare each stack's `version` against the latest to identify outdated stacks

## Workflow: Upgrade a package in a stack

Use when the user wants to upgrade a specific stack/project to the latest version of a package.

1. Get the latest version of the package
2. Clone the stack's project repository. If the repository cannot be cloned or the agent lacks filesystem/git access, surface the required change as a diff or instruction set for the user to apply manually.
3. Detect the project language from the `runtime` field in `Pulumi.yaml`, then update the correct dependency file:
   - `nodejs` → `package.json`
   - `python` → `requirements.txt` or `pyproject.toml`
   - `go` → `go.mod`
   - `yaml` → `Pulumi.yaml`
4. Run `pulumi preview` to catch any breaking changes introduced by the version bump before merging.
5. Open a pull request with the change

---
name: package-usage
description: Get information about which stacks are using a specific package and at what versions. Use to check which stacks use a component package, see what versions are deployed, identify stacks needing upgrades, or audit package usage before making changes.
---

# Understanding Pulumi Package Usage

When users ask about outdated component packages or versions:

1. List available component packages and their latest versions from the private registry using `list_private_registry_components`
2. For each package, query the package usage API endpoint to fetch stack usage and current versions
3. Match stack versions against the latest registry versions
4. Identify stacks using outdated versions

## Querying Package Usage via API

**Endpoint**: `GET /api/orgs/{orgName}/packages/usage?packageName={packageName}`

To resolve `{orgName}`: You have the organization name in your context (provided at the start of the conversation). If you're unsure, you can read it from the `PULUMI_ORG` environment variable using a shell tool.

Call `call_pulumi_cloud_api` with the URL `/api/orgs/{orgName}/packages/usage?packageName={packageName}`, replacing `{orgName}` with the actual organization name and `{packageName}` with the package name.

**Response includes**:

- `packageName`: The package being queried
- `stacks`: Array with stack usage information
  - `stackName`, `projectName`: Stack and project names
  - `version`: Package version currently in use
  - `lastUpdate`: When stack was last updated
- `totalStacks`: Total number of stacks using the package
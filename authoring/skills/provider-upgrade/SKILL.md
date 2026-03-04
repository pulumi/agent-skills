---
name: provider-upgrade
description: Upgrade Pulumi providers to newer versions. Use when users need to upgrade providers (pulumi-aws, pulumi-azure-native, pulumi-gcp, pulumi-kubernetes), update dependencies, check for breaking changes, or update provider versions across stacks.
---

# Upgrading Pulumi Providers

## Pre-Upgrade Assessment

1. **Get the latest version** via `call_pulumi_cloud_api`:
   `GET /api/registry/packages?name={package_name}&orgLogin={orgName}`
   The response `packages[].version` field has the latest version.

2. **Find affected stacks** via `call_pulumi_cloud_api`:
   `GET /api/orgs/{orgName}/packages/usage?packageName={package_name}`
   Returns `stacks[]` with `{stackName, projectName, version, lastUpdate}`.

3. **Determine upgrade type**:
   - **Major version** (e.g., v6 to v7): Likely has breaking changes, requires migration guide review
   - **Minor/patch version** (e.g., v7.1 to v7.2): Usually backwards-compatible, lower risk

## Finding Breaking Change Documentation

For major version upgrades, search for a migration guide using `web_search`:

```
site:pulumi.com {provider} migration guide v{major}
```

Example: `site:pulumi.com pulumi-aws migration guide v7`

If no migration guide is found, search more broadly:

```
site:pulumi.com {provider} v{major} upgrade breaking changes
```

Migration guides exist for some major provider versions but not all. If no guide is found, note this in the upgrade summary and rely on preview results to identify breaking changes.

## Present Upgrade Summary

Present a summary to the user:

```
## Upgrade Summary: {provider} {current_version} -> {target_version}

### Affected Stacks

| Project | Stack | Current Version | Target Version |
|---------|-------|-----------------|----------------|
| ... | ... | ... | ... |

### Breaking Changes

{Summary from migration guide, or "No migration guide found. Preview results will be used to identify any issues."}

### Actions Required

For each stack:
- {project}/{stack}: {anticipated actions, e.g., "Update import paths", "Add alias for renamed resource", "No code changes expected"}
```

You must ask for user confirmation before proceeding with the upgrade.

## Upgrade Workflow

**Important**: Process stacks one at a time. Complete the entire workflow for one stack (including opening a PR) before moving to the next. Work through all stacks in a given environment tier (e.g., all dev stacks) before moving to the next tier (staging, then production).

**Exception**: If stacks have dependencies on each other (e.g., a shared infrastructure stack that other stacks reference), upgrade and test them together in a single PR.

For each stack:

### 1. Update Dependencies

Update the provider dependency using the appropriate package manager:

- **TypeScript/JavaScript**: `npm install @pulumi/{provider}@^{version}` or `yarn add @pulumi/{provider}@^{version}`
- **Python**: Update `pyproject.toml` or `requirements.txt` with `pulumi_{provider} >= {version}` (note: underscore, not hyphen), then `pip install -e .` or equivalent
- **Go**: `go get github.com/pulumi/pulumi-{provider}/sdk/v{major}@latest` — also update all import paths (e.g., `v6` to `v7`) and run `go mod tidy`
- **.NET**: `dotnet add package Pulumi.{Provider} --version {version}`
- **Java**: Update `pom.xml` or `build.gradle` dependency version
- **YAML**: Provider versions are set as resource options on the default provider or as explicit provider configuration. See https://www.pulumi.com/docs/iac/languages-sdks/yaml/yaml-language-reference/#providers-and-provider-versions for examples.

### 2. Run Preview

Use `pulumi_preview` to see what changes would be made. Review the `update_summary` for:
- **Resource replacements**: May indicate breaking changes in resource schemas
- **Property changes**: Check if defaults changed or properties were renamed
- **Import errors**: Type or property name changes

Present any diagnostics (warnings or errors) to the user.

When presenting preview results, explain whether changes are expected based on the breaking changes research.

If the preview contains diagnostic warnings or errors, stop and ask the user if they want to address them before proceeding. Do not ask to create a PR without first asking the user if they would like to address any warnings or errors.

### 3. Address Breaking Changes

Common breaking change patterns:

**Resource renames** — Use aliases to preserve state:
```typescript
const bucket = new aws.s3.Bucket("my-bucket", { /* ... */ }, {
    aliases: [{ type: "aws:s3:BucketV2" }]  // old type name
});
```

**Property renames** — Update code to use new property names. Check migration guide if available.

**Removed properties** — Some properties may be removed or moved to separate resources. Check migration guide if available.

### 4. Iterate Until Clean

Repeat `pulumi_preview` and fix issues until the preview shows no unexpected changes and no errors. Provider version metadata diffs are acceptable.

### 5. Open Pull Request

Once clean, create a pull request for this stack's changes. Then proceed to the next stack.

**Do not run `pulumi_up`**. Deployments happen through the PR/merge process, not directly.

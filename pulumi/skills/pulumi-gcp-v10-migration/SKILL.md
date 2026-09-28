---
name: pulumi-gcp-v10-migration
description: >
  Upgrade a Pulumi program from the GCP provider v9 (pulumi-gcp, @pulumi/gcp, Pulumi.Gcp,
  com.pulumi:gcp) to v10, or fix a program or preview that broke after that upgrade. Use when
  the user asks to migrate, upgrade, or bump pulumi-gcp to v10 or 10.x, asks about GCP v10
  breaking changes, or hits a v10 error such as a missing gcp.notebooks or gcp.iap.Brand type,
  a required secretDataWoVersion, or an unexpected replace after moving to v10. Do NOT use for
  other providers or other GCP major versions; use skill `provider-upgrade` for those.
---

# Migrate a Pulumi program to GCP provider v10

## The principle

An upgrade is a translation. The user's cloud resources must not change: a correct migration
ends in a `pulumi preview` where every resource is `same` except the provider version. A few
v10 changes cannot be translated away in code (a removed resource type, a `count: 0`
accelerator that now replaces an instance). Those need a state edit or a user decision, and a
wrong order destroys live infrastructure. That is why this skill finds affected resources
**before** bumping the dependency.

Use skill `provider-upgrade` for the generic diff checkpoint (categorizing every non-`same`
resource) and the upgrade summary format. This skill adds what is specific to GCP v10.

The authoritative source is the v10 migration guide:
https://www.pulumi.com/registry/packages/gcp/how-to-guides/10-0-migration/
Cite it by section title when you justify a change or an accepted diff.

## Hard rules

- **Never run `pulumi up`, `pulumi refresh`, `pulumi destroy`, `pulumi state delete` or
  `pulumi import` yourself.** Write them out for the user to run. They change the stack or the
  cloud; `pulumi preview` (including `--refresh` and `--run-program`) and `pulumi stack export`
  do not, so run those freely.
- **No `replace` or `delete` in the final preview** unless the user explicitly chose it after
  you explained what gets destroyed.
- **Do not remove a removed resource type from code while it is still in state.** The engine
  sends the delete to the v9 provider recorded in state, which destroys the live resource
  without a warning. Take it out of state first (user runs `pulumi state delete`).
- Fix only what v10 breaks. Leave deprecated but working code alone.

## Step 1: Detect the program and its current major

Find every Pulumi project (`Pulumi.yaml`) and its language (`runtime:`), then the GCP
dependency:

| Language | Where to look | Current major |
|---|---|---|
| TypeScript/JavaScript | `package.json`, lockfile: `@pulumi/gcp` | semver major |
| Python | `requirements.txt`, `pyproject.toml`, `uv.lock`/`poetry.lock`: `pulumi-gcp` / `pulumi_gcp` | semver major |
| Go | `go.mod`: `github.com/pulumi/pulumi-gcp/sdk/vN` | the `/vN` suffix |
| .NET | `*.csproj`: `PackageReference Include="Pulumi.Gcp"` | semver major |
| Java | `pom.xml` or `build.gradle`: `com.pulumi:gcp` | semver major |
| YAML | `Pulumi.yaml` `packages:`/`plugins:`, or resource `options.version` | semver major, else the state |

The deployed version is authoritative for what state holds:

```bash
pulumi stack export | jq -r '.deployment.resources[] | select(.type == "pulumi:providers:gcp") | "\(.urn) \(.inputs.version)"'
```

- Already on 10.x: skip to Step 4 and work from the preview errors.
- On 9.x: continue.
- On 8.x or older: stop and tell the user to complete the v9 migration first
  (https://www.pulumi.com/registry/packages/gcp/how-to-guides/9-0-migration/). Do not jump two
  majors in one step.

## Step 2: Establish a clean v9 baseline and find affected resources

Still on v9, run `pulumi preview --refresh` for each stack. If it is not clean, stop: diffs that
exist before the bump will be blamed on v10. The guide recommends the user run
`pulumi up --refresh` on v9 to settle them; ask them to.

Then find what v10 touches, in two passes, using
[references/breaking-changes.md](references/breaking-changes.md):

1. **State pass** (read-only): run the one-line type scan in the reference against each stack.
   It finds removed types and every resource type with a breaking change, including resources
   the code builds indirectly (loops, components).
2. **Code pass**: run each row's grep pattern over the program source (`grep -rniE` or `rg -i`).
   Patterns tolerate camelCase, snake_case and PascalCase. A hit is a candidate; read the code
   to confirm the resource and property match the row.

Present the affected list to the user, grouped by risk (`REPLACE`, `DELETE`, `UPDATE`,
`BUILD`, `NONE`), before editing anything. For each `REPLACE` or `DELETE` row, state what is
destroyed and get the user's choice.

## Step 3: Bump the dependency to v10

| Language | Command |
|---|---|
| TypeScript/JavaScript | `npm install @pulumi/gcp@^10.0.0` (or the yarn/pnpm equivalent) |
| Python | set `pulumi-gcp>=10.0.0,<11.0.0` in the requirements file, then reinstall |
| Go | `go get github.com/pulumi/pulumi-gcp/sdk/v10@latest`, rewrite every import from `.../sdk/v9/...` to `.../sdk/v10/...`, then `go mod tidy` |
| .NET | `dotnet add package Pulumi.Gcp --version 10.*` |
| Java | set the `com.pulumi:gcp` version to `10.0.0` in `pom.xml` or `build.gradle` |
| YAML | `pulumi package add gcp 10.0.0`, and update any `version:` resource option pinning 9.x |

Confirm the resolved version in the lockfile (or `go.sum`) is 10.x.

## Step 4: Apply fixes

Work through the affected rows. Each row in the reference gives the action; the guide section
it links has the per-language before/after code. Make the smallest edit that keeps the live
resource unchanged. The rows that most often go wrong:

- **Removed types** (`gcp.notebooks.*`, `gcp.iap.Brand`/`Client`, `gcp.beyondcorp.App*`,
  `gcp.ml.EngineModel`, `gcp.vertex.AiSchedule`): write out `pulumi state delete` commands for
  the user, dependents first, and only then remove the code. Adopt a successor resource with
  `pulumi import`, never with a create.
- **`gcp.compute.Instance` with `guestAccelerators` `count: 0`**: omit the list instead of
  sending a zero count. A replace destroys the boot disk and local SSD data.
- **`gcp.secretmanager.SecretVersion` without `secretDataWoVersion`**: set it to `""`. Any
  other value, including `"0"`, replaces the secret version.
- **Default changes** (`gcp.bigquery.Dataset.defaultCollation`,
  `loadBalancingScheme` on `gcp.compute.BackendService`/`GlobalForwardingRule`): pin the value
  the live resource has today, read from state, so v10 does not change it.

## Step 5: Verify with preview

Run `pulumi preview --refresh --run-program` per stack. Loop until clean:

- Build or validation errors: fix and re-run. New errors after a fix are progress.
- Any `replace` or `delete`: find the row that explains it and fix the code, or stop and ask
  the user. Never accept one silently.
- Any `update` other than `pulumi:providers:gcp`: accept it only if the guide documents it
  (cite the section), otherwise fix it.

Finish with the upgrade summary from skill `provider-upgrade`, listing the manual commands
(`pulumi state delete`, `pulumi import`, and when to run `pulumi up`) for the user to run
themselves.

## References

- [references/breaking-changes.md](references/breaking-changes.md): every v10 breaking change
  as a table of resource, state type, grep pattern, action, and risk.
- v10 guide (detection commands and per-language code for each change):
  https://www.pulumi.com/registry/packages/gcp/how-to-guides/10-0-migration/
- Upstream companion (google-beta v8):
  https://registry.terraform.io/providers/hashicorp/google-beta/latest/docs/guides/version_8_upgrade

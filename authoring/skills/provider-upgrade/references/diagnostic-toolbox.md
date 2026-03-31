# Diagnostic Toolbox

Use these tools to investigate diffs - especially Category B diffs (resources you didn't
change code for). Reach for whichever tool fits the situation.

For major version upgrades, check the upgrade guide early - even alongside the first
preview. Upgrade guides contain sequencing requirements and edge cases that no other
tool can surface.

## Upgrade Guide (Pulumi or Terraform)

The most valuable resource for major version bumps. Contains migration patterns,
sequencing requirements, and documents which diffs are known preview artifacts.

The upgrade guide is the ONLY authoritative source for classifying a diff as a "known
no-op" - a diff that shows in preview but resolves on `pulumi up` without affecting
real infrastructure.

**Pulumi upgrade guide:**
Search for `site:pulumi.com {provider} migration guide v{major}`.

**Terraform upgrade guide** (for Terraform-based providers):
Check `https://registry.terraform.io/providers/{org}/{tf-provider}/latest/docs/guides/version-{major}-upgrade`
or search for `site:registry.terraform.io {tf-provider} version {major} upgrade`.

**When to use:** For any major version upgrade. Check it early.

## schema-tools - structured diff between versions

A structured diff of every schema change between provider versions. For large providers,
the diff can contain thousands of changes - always cross-reference with the resource
types actually present in the stack.

**Install** (if not available):

This example is intentionally lightweight and may drift over time. If the pinned version
below is stale, use the latest available `schema-tools` release instead of treating the
example version as authoritative.

```shell
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)
case "$ARCH" in x86_64) ARCH="amd64" ;; aarch64|arm64) ARCH="arm64" ;; esac
VERSION="v0.7.0"
curl -fsSL "https://github.com/pulumi/schema-tools/releases/download/${VERSION}/schema-tools-${VERSION}-${OS}-${ARCH}.tar.gz" \
  -o /tmp/schema-tools.tar.gz
tar -xzf /tmp/schema-tools.tar.gz -C /tmp/
chmod +x /tmp/schema-tools
```

**Run and save to a file:**

```shell
/tmp/schema-tools compare -p {provider} -o v{current_version} -n v{target_version} --json > /tmp/{provider}-schema-diff.json
```

The `-o` and `-n` flags must be full version tags (e.g., `v6.0.0`, `v7.0.0`), not just
major numbers. Use the exact versions from the lockfile.

**Useful queries:**

```shell
# Summary of all breaking change categories
jq '.summary' /tmp/{provider}-schema-diff.json

# Changes for a specific resource
jq '.grouped.resources["aws:s3/bucket:Bucket"]' /tmp/{provider}-schema-diff.json

# All changes of a specific type
jq '[.changes[] | select(.kind == "missing-input")]' /tmp/{provider}-schema-diff.json

# All breaking changes matching a pattern
jq '[.changes[] | select(.token | test("apigateway"))]' /tmp/{provider}-schema-diff.json

# List all affected resource tokens
jq '[.changes[] | .token] | unique' /tmp/{provider}-schema-diff.json
```

Each change entry has `kind`, `token`, `severity`, and `message` fields. The change
kinds you'll encounter most often during upgrades:

- **missing-input** - a property was removed from inputs. Usually renamed or replaced by
  a different property with a different shape. The schema diff says it's gone but doesn't
  say what replaced it - check the upgrade guide or new schema for the replacement.
- **type-changed** - a property's type changed. The most common pattern is a MaxItemsOne
  flip: a property is renamed AND changes between single object and array (or vice versa).
  Example: `certificateAuthorities` (array) -> `certificateAuthority` (single object).
- **token-remapped** - a resource or function was renamed. If "deprecated," the old name
  still works (don't chase it). If "remapped," the old name is gone - rename in code and
  add an alias to preserve state: `aliases: [{ type: "old:token:Name" }]`.

**When to use:** When preview errors mention unknown properties, missing fields, type
mismatches, or unrecognized resource types. The schema diff tells you exactly what was
renamed, removed, or reshaped.

## Stack state inspection - scope changes to this stack

Inspect the stack's deployed resource types. Essential for large providers - filter the
schema diff to only resources that matter. Use whatever state inspection tooling is
available in the environment, such as `pulumi stack --show-urns`, `pulumi stack export`,
state files, or backend resource inventory APIs.

```shell
# Example: list resource types from a stack export
pulumi stack export > /tmp/stack.json
jq -r '.deployment.resources[].type' /tmp/stack.json | sort -u

# Then filter schema diff to only resource types in the stack
jq '[.changes[] | select(.token | test("ZoneSettingsOverride|PageRule|Record|Zone"))]' \
  /tmp/{provider}-schema-diff.json
```

**When to use:** Always use alongside schema-tools.

## SDK type definitions - inspect the new API shape

For TypeScript and Python projects, the installed package's type definitions show the
exact new API - property names, types, required vs. optional.

**TypeScript:** read `node_modules/@pulumi/{provider}/*.d.ts` for the resource type
**Python:** read the installed package source

Faster than schema-tools for answering "what does this resource look like now?"

## GitHub issues

Search `pulumi/pulumi-{provider}` and `hashicorp/terraform-provider-{tf-name}` for
specific error messages or resource names.

**When to use:** When upgrade guides don't cover an edge case, or when you're seeing
unexpected behavior that might be a known bug.

---
name: pulumi-adopt-drift
description: >
  Adopt infrastructure drift into Pulumi code using the drift-adopter CLI tool.
  Use when: (1) User mentions drift adoption,
  (2) User wants code updated to match infrastructure state.
  Do NOT use if user wants to revert drift - that requires pulumi up.
---

# Adopt Drift Skill

Adopt infrastructure drift back into Pulumi code using the `drift-adopter` CLI tool. The tool analyzes engine events from previews and tells you exactly what code changes to make.

## When to Use This Skill

**Use this skill ONLY when the user wants to adopt drift** - update Pulumi code to match deployed infrastructure.

**DO NOT use this skill if:**
- User wants to overwrite drift (update infrastructure to match code) - use `pulumi up`
- User wants to revert infrastructure changes - use `pulumi up`

**Decision guide:**
- "Adopt the drift" / "Update code to match infrastructure" → Use this skill ✓
- "Fix the drift" / "Overwrite the drift" / "Revert the changes" → Use `pulumi up` ✗

## Prerequisites

Install the CLI tool (RC version):

```bash
pulumi plugin install tool drift-adopter --server github://api.github.com/pulumi-labs --version v0.1.0-rc
```

## Scale Strategy

**For all drift (any scale) — read before you write:**

1. Read the **complete** `outputFile` before writing any code. The outputFile is a single
   non-paginated file containing all resources. For large files, use multiple Read tool
   calls with increasing `offset` values until you reach the end.
2. While reading, build a mental inventory: note each resource's `type`, `name`, and
   `dependencyLevel` (absent means 0). Flag all bare `dependsOn` entries (no `outputProperty`).
3. Write code in dependency order: write `dependencyLevel: 0` resources first, then
   `dependencyLevel: 1`, and so on. Each referenced variable will already be declared.
4. For bare `dependsOn` (no `outputProperty`): the tool knows which resource the property
   depends on but could not determine the exact output property (e.g., encrypted value,
   structural type mismatch). Use the referenced resource's type from your inventory to
   infer which output is appropriate for the property you are setting.

**For large-scale drift (20+ resources):**
5. If resources share the same type, properties, and sequential naming → write loops
6. Use `--max-resources` if you want to limit batch size for intentional batching.

**Editing strategy:**
- For **update_code** changes to an existing file: if more than ~10 resources need changes,
  rewrite the entire file with the Write tool rather than making individual Edit calls.
  A single Write is faster and less error-prone than many sequential Edits.
- For **add_to_code** to an existing file with unchanged resources: use Edit to append
  new resources, or Write if the file needs significant restructuring.
- For **full adoption** (empty/minimal starting code): always use Write.

## Workflow

### Step 1: Run drift-adopter CLI

```bash
pulumi plugin run drift-adopter -- next --stack <stack>
```

**Available flags:**

| Flag | Description |
|------|-------------|
| `--stack` | Pulumi stack name (default: current stack) |
| `--max-resources` | Max resources per batch (-1 = unlimited, default) |
| `--exclude-urns` | Comma-separated URNs to exclude from results |
| `--skip-refresh` | Omit `--refresh` from pulumi preview (use on subsequent calls) |
| `--state-file` | Path to cached state file (use value from prior `stateFilePath` output) |
| `--output-file` | Path for full output file (default: auto-generated temp file) |

**Two-phase output:** The CLI prints a compact summary to stdout and writes full resource details to a file.

**Stdout** returns a `NextSummaryOutput`:
```json
{
  "status": "changes_needed",
  "summary": { "total": 250, "byAction": {...}, "byType": {...} },
  "outputFile": "/tmp/drift-adopter-output-123.json",
  "stateFilePath": "/tmp/drift-adopter-state-456.json",
  "skippedCount": 3
}
```

**To get resource details:** Use the Read tool on the `outputFile` path. The file contains the full `NextOutput` with `resources[]`, `skipped[]`, and all property data.

On subsequent calls, pass both flags to skip redundant work:
```bash
pulumi plugin run drift-adopter -- next --stack <stack> --skip-refresh --state-file <stateFilePath>
```

### Step 2: Process output and make changes

The CLI stdout JSON has one of these statuses:

| Status | Meaning | Action |
|--------|---------|--------|
| `"clean"` | All drift adopted | Create PR and finish |
| `"error"` | Code error in preview | Fix error, repeat from Step 1 |
| `"changes_needed"` | Resources need updates | Make changes per instructions |
| `"stop_with_skipped"` | No actionable resources remain, but some were skipped | Review `skipped` array, create PR or address skipped resources |

**`stop_with_skipped` details:** Resources are skipped when:
- **`"excluded"`**: Explicitly excluded via `--exclude-urns`
- **`"missing_properties"`**: Resource needs changes but the CLI couldn't extract property details

Review the `skipped` array to decide whether to address these manually or accept them as-is.

For `"changes_needed"`, read the `outputFile` and process each resource in the `resources` array:

- **`update_code`**: Update properties from `currentValue` to `desiredValue`
- **`delete_from_code`**: Remove the resource definition entirely
- **`add_to_code`**: Add the resource back to code

**Pattern recognition:** When the summary shows many resources of the same type:
- Examine 2-3 resources to identify shared property patterns
- If names are sequential (e.g., `bucket-0` through `bucket-99`) and properties are uniform, write a loop:

  ```typescript
  for (let i = 0; i < 100; i++) {
      new aws.s3.Bucket(`bucket-${i}`, { tags: { Env: "prod" } });
  }
  ```

- Only write individual declarations when resources have unique properties

If the user specifies only certain resources or properties should have their drift adopted, only address those resources or properties.

### Step 3: Verify and iterate

Re-run `drift-adopter next` to check for remaining drift. Do not commit changes until verification passes — committing before verification wastes an iteration. If status is `"clean"` or `"stop_with_skipped"`, create PR. Otherwise repeat from Step 2.

## CLI Output Reference

### update_code response

```json
{
  "action": "update_code",
  "urn": "urn:pulumi:dev::app::aws:s3/bucket:Bucket::my-bucket",
  "type": "aws:s3/bucket:Bucket",
  "name": "my-bucket",
  "properties": [
    {
      "path": "tags.Environment",
      "currentValue": "dev",
      "desiredValue": "production",
      "kind": "update"
    }
  ]
}
```

**Key fields:**
- `action`: What to do (update_code, delete_from_code, add_to_code)
- `name`: Resource name to find in code
- `type`: Resource type (e.g., "aws:s3/bucket:Bucket")
- `properties`: Array of property changes
  - `path`: Property path (e.g., "tags.Environment")
  - `currentValue`: What's in code now
  - `desiredValue`: What it should be (from infrastructure)

### add_to_code response

```json
{
  "action": "add_to_code",
  "urn": "urn:pulumi:dev::app::aws:s3/bucket:Bucket::missing-bucket",
  "type": "aws:s3/bucket:Bucket",
  "name": "missing-bucket",
  "inputProperties": {
    "bucket": "missing-bucket",
    "tags": {"Environment": "production"}
  }
}
```

`inputProperties` is a flat map of property names to values — use these directly when writing the resource declaration.

**`dependencyLevel`**: When present, this resource references other resources in the batch.
Write level-0 resources (field absent) first, then level 1, etc.

### Runtime Values

`inputProperties` values, `currentValue`, and `desiredValue` are all **runtime values** —
the actual string/number/object that exists in infrastructure or that code evaluates to.
Your code must be an expression that evaluates to this exact value at runtime.

For strings containing backslash sequences: a JSON `\\n` in the tool output means the
runtime string contains a literal backslash followed by `n` (two characters), not a
newline. Write the appropriate escape for your language:

| Language   | Literal `\n` in code                                    |
|------------|--------------------------------------------------------|
| TypeScript | `'...\\n...'` or `` `...\\n...` `` (NOT `` `...\n...` ``) |
| Python     | `r'...\n...'` or `'...\\n...'`                          |
| Go         | `` `...\n...` `` (raw) or `"...\\n..."`                  |
| C#         | `@"...\n..."` (verbatim) or `"...\\n..."`               |

### Cross-Resource References

When a property depends on another resource's output, `inputProperties` includes
`dependsOn` metadata instead of the literal value:

```json
{
  "privateKeyPem": {
    "dependsOn": {
      "resourceName": "ca-key",
      "resourceType": "tls:index/privateKey:PrivateKey",
      "outputProperty": "privateKeyPem"
    }
  }
}
```

**When you see `dependsOn`:** ALWAYS use a resource reference — there is no literal value provided.
Write `caKey.privateKeyPem` (not a literal value). The `resourceName` tells you which
resource variable to reference, and `outputProperty` tells you which output.

#### Bare dependsOn (no outputProperty)

When the tool cannot determine the exact output property, `outputProperty` is omitted:

```json
"triggers": {
  "dependsOn": {
    "resourceName": "api-pass-5",
    "resourceType": "random:index/randomPassword:RandomPassword"
  }
}
```

**When you see bare `dependsOn`:** The tool knows the dependency but could not match the
value to a specific output — commonly because the value is encrypted or the property is
an array or map whose values are resource outputs. The referenced resource's type is in
your inventory. Use it to infer the correct output for the property you are setting.

For example, `RandomPassword` → `result`, so `triggers: [apiPass5.result]`;
a map property `keepers: {"ref": {"dependsOn": ...}}` → `keepers: { ref: someRes.id }`.

Properties without `dependsOn` are plain values — use them as-is.

## CRITICAL SUCCESS REQUIREMENTS

The task is NOT complete until ALL of the following are true:

1. **drift-adopter CLI returns `status: "clean"` or `status: "stop_with_skipped"`** — no remaining actionable drift (the tool runs preview internally, so a separate `pulumi preview` is not needed)
2. **PR created with code changes** - all modifications committed and submitted for review

## Stack Config vs Hardcoding

Before hardcoding values, evaluate if the property should use stack config instead.

**Use config for:** Environment-specific values, feature flags, thresholds/limits, deployment-specific settings

**Decision Logic:**
- Is value already from stack config? → Update the config value, NOT the code
- Is it environment-specific? → Use config
- Is it structural? (resource name/type/relationships) → Update code

**Example (TypeScript):**
```typescript
const config = new pulumi.Config();

// Before (hardcoded)
versioning: { enabled: false }

// After (config with default)
versioning: { enabled: config.getBoolean("bucketVersioning") ?? false }
```

Then: `pulumi config set bucketVersioning true`

## Important Notes

- **Edit files in place**: DO NOT copy or move project files
- **Batch processing**: Use `--max-resources` to limit batch size if needed - expect multiple iterations for large drift
- **Reading output**: Always read `outputFile` from the summary to get full resource details — stdout only contains the summary

## Troubleshooting

| Issue | Solution |
|-------|----------|
| CLI returns `status: "error"` | Read error message, fix code error, repeat from Step 1 |
| Can't find resource in code | Search for resource name or type (e.g., "s3.Bucket") |
| Same resource appears again | Verify you committed/pushed, used `desiredValue`, updated correct property |
| Multiple iterations needed | Expected - CLI batches changes, continue until `status: "clean"` |

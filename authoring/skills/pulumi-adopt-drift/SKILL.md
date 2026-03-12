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

## Scale Strategy

Before starting, estimate the drift scope from Step 1 output.

**For large-scale drift (20+ resources):**
1. Read the `summary` field first — it shows resource counts by type and action
2. Group resources by type: examine a few from each group to spot patterns
3. If resources share the same type, properties, and sequential naming → write loops
4. ALWAYS use `--max-resources 50` to limit output size (keeps output under 50KB for reliable parsing)

## Workflow

### Step 1: Run drift-adopter CLI

```bash
pulumi plugin run drift-adopter -- next --stack <stack>
```

**Available flags:**

| Flag | Description |
|------|-------------|
| `--stack` | Pulumi stack name (default: current stack) |
| `--max-resources` | Max resources per batch (default: unlimited, set >0 to limit) |
| `--exclude-urns` | Comma-separated URNs to exclude from results |
**Do NOT run `pulumi stack export` manually.** The drift-adopter tool handles state export internally for dependency resolution. Running it yourself wastes iterations.

### Step 2: Process output and make changes

The CLI outputs JSON with one of these statuses:

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

For `"changes_needed"`, process each resource in the `resources` array:

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

Re-run `drift-adopter next` to check for remaining drift. If status is `"clean"` or `"stop_with_skipped"`, create PR. Otherwise repeat from Step 2.

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

Look up the resource type to determine which output to reference. For example,
`RandomPassword` → `result`, so write `triggers: [apiPass5.result]`.

Properties without `dependsOn` are plain values — use them as-is.

## CRITICAL SUCCESS REQUIREMENTS

The task is NOT complete until ALL of the following are true:

1. **drift-adopter CLI returns `status: "clean"` or `status: "stop_with_skipped"`** — no remaining actionable drift
2. **`pulumi preview` shows no changes** - code fully matches infrastructure state
3. **PR created with code changes** - all modifications committed and submitted for review

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

## Troubleshooting

| Issue | Solution |
|-------|----------|
| CLI returns `status: "error"` | Read error message, fix code error, repeat from Step 1 |
| Can't find resource in code | Search for resource name or type (e.g., "s3.Bucket") |
| Same resource appears again | Verify you committed/pushed, used `desiredValue`, updated correct property |
| Multiple iterations needed | Expected - CLI batches changes, continue until `status: "clean"` |

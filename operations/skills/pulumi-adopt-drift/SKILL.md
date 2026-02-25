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

Install the CLI tool:

```bash
pulumi plugin install tool drift-adopter --server github://api.github.com/pulumi-labs
```

## Workflow

Create a todo list to track your progress through iterations.

### Step 1: Run drift-adopter CLI

```bash
pulumi plugin run drift-adopter -- next --stack <stack>
```

**Available flags:**

| Flag | Description |
|------|-------------|
| `--stack` | Pulumi stack name (default: current stack) |
| `--max-resources` | Max resources per batch (default: 10, 0 = unlimited) |

### Step 2: Process output and make changes

The CLI outputs JSON with one of three statuses:

| Status | Meaning | Action |
|--------|---------|--------|
| `"clean"` | All drift adopted | Create PR and finish |
| `"error"` | Code error in preview | Fix error, repeat from Step 1 |
| `"changes_needed"` | Resources need updates | Make changes per instructions |

For `"changes_needed"`, process each resource in the `resources` array:

- **`update_code`**: Update properties from `currentValue` to `desiredValue`
- **`delete_from_code`**: Remove the resource definition entirely
- **`add_to_code`**: Add the resource back to code

If the user specifies only certain resources or properties should have their drift adopted, only address those resources or properties.

### Step 3: Iterate

**Repeat from Step 1** until CLI returns `status: "clean"`, then create PR.

## CLI Output Reference

### changes_needed response

```json
{
  "status": "changes_needed",
  "resources": [
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

## CRITICAL SUCCESS REQUIREMENTS

The task is NOT complete until ALL of the following are true:

1. **drift-adopter CLI returns `status: "clean"`** - no remaining drift detected
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
- **Batch processing**: CLI limits to 10 resources per batch by default - expect multiple iterations

## Troubleshooting

| Issue | Solution |
|-------|----------|
| CLI returns `status: "error"` | Read error message, fix code error, repeat from Step 1 |
| Can't find resource in code | Search for resource name or type (e.g., "s3.Bucket") |
| Same resource appears again | Verify you committed/pushed, used `desiredValue`, updated correct property |
| Multiple iterations needed | Expected - CLI batches changes, continue until `status: "clean"` |

---
name: pulumi-drift-adopt
version: 1.0.0
description: Helps adopt infrastructure drift back into Pulumi code using the pulumi-drift-adopt tool. Use when (1) Infrastructure has drifted from Pulumi code and needs to be synchronized, (2) Running pulumi preview shows differences between actual infrastructure and code, (3) Need to systematically update Pulumi code to match real infrastructure state, (4) Working with the pulumi-drift-adopt CLI tool to fix drift issues, (5) User asks to "adopt drift" or "fix drift" in their Pulumi project.
---

# Drift Adopt

## Overview

The pulumi-drift-adopt tool automatically detects drift between actual infrastructure and Pulumi code by running `pulumi preview --refresh`. It provides structured guidance on what code changes are needed to align code with the actual infrastructure state.

## Workflow

Follow this iterative process to adopt drift:

### 1. Run the Drift Adoption Tool

Execute the tool in the Pulumi project directory:

```bash
pulumi-drift-adopt next

# Or specify a stack if needed
pulumi-drift-adopt next --stack dev

# If you're struggling to fix resources, reduce the batch size
pulumi-drift-adopt next --max-resources 5
```

The tool will:
- Automatically refresh state to match actual infrastructure
- Run preview to compare code vs state
- Return JSON with needed code changes (limited to 10 resources by default)

**Handling difficult drift:**
The tool returns up to 10 resources by default. If you're having trouble fixing resources (same resources keep getting returned because you can't fix them correctly), use `--max-resources 5` or `--max-resources 3` to work with fewer resources at a time. This makes the problem more manageable.

### 2. Parse the JSON Output

The tool returns JSON with one of three statuses:

#### Status: "error"
Preview failed (likely a code error).

**Action:** Read the error message, identify the issue (syntax error, missing import, etc.), fix the code, and run again.

#### Status: "clean"
No drift detected. Code matches state.

**Action:** You're done! Inform the user that drift adoption is complete.

#### Status: "changes_needed"
Drift detected. The tool provides a list of resources and properties to change.

**Action:** Proceed to step 3.

### 3. Process Each Resource Change

For each resource in the output, look at the `action` field:

#### Action: "update_code"
The resource exists in both code and state but has property differences.

**What to do:**
- Find the resource in the code (use the `name` and `type` to locate it)
- For each property change:
  - `path`: The property path (e.g., "tags.Environment")
  - `currentValue`: What's currently in the code (wrong)
  - `desiredValue`: What should be in the code (from state)
- Update the code to change `currentValue` to `desiredValue`

**Example:**
```json
{
  "action": "update_code",
  "name": "my-bucket",
  "type": "aws:s3/bucket:Bucket",
  "properties": [{
    "path": "tags.Environment",
    "currentValue": "dev",
    "desiredValue": "production"
  }]
}
```

Find the bucket resource and change `tags: { Environment: "dev" }` to `tags: { Environment: "production" }`.

#### Action: "delete_from_code"
The resource is in code but not in state (it doesn't exist in actual infrastructure).

**What to do:**
- Find the resource in the code
- Delete it completely
- Also remove any references to this resource from other resources

#### Action: "add_to_code"
The resource is in state but not in code (it exists in infrastructure but isn't defined in code).

**What to do:**
- Add the resource definition to the code
- Use the `type` and `name` from the output
- You may need to look at the `urn` to understand the resource's configuration
- Add appropriate properties based on the resource type

### 3.5. Consider Stack Config Instead of Hardcoding

**Before updating code with hardcoded values, evaluate whether the property should come from stack config instead.**

Stack config is preferable when properties:
- Vary by environment (dev vs prod vs staging)
- Are feature flags (enabled/disabled boolean values)
- Are thresholds or limits (maxSize, timeout, retryCount)
- Are deployment-specific (region, accountId, domainName)

**Decision logic:**
```
Property drift detected →
├─ Is value already from stack config? → Update the config value, NOT the code
├─ Is it environment-specific? (different in dev/prod) → Use config
├─ Is it a feature flag? (boolean enabled/disabled) → Use config
├─ Is it a threshold/limit? (max/min/timeout) → Use config
└─ Is it structural? (resource name/type/relationships) → Update code
```

**Examples:**

*Already using config (update config, not code):*
```typescript
// Code currently has:
const config = new pulumi.Config();
versioning: { enabled: config.requireBoolean("bucketVersioning") }

// Drift shows enabled should be true
// DON'T change code to: versioning: { enabled: true }
// DO update stack config: pulumi config set bucketVersioning true
```

*Boolean flag drift (prefer config):*
```typescript
// Instead of hardcoding:
versioning: { enabled: true }

// Use stack config:
const config = new pulumi.Config();
versioning: { enabled: config.requireBoolean("bucketVersioning") }
```

*Threshold drift (prefer config):*
```typescript
// Instead of hardcoding:
maxSize: 1000

// Use stack config:
const config = new pulumi.Config();
maxSize: config.requireNumber("maxBucketSize")
```

*Structural change (use hardcoded value):*
```typescript
// Hardcode is fine for resource names, types, relationships:
bucket: "my-app-bucket"  // This is structural, hardcode it
```

**When in doubt:** If the property might reasonably differ between stacks or environments, prefer config over hardcoding.

### 4. Run the Tool Again

After making code changes, run the tool again:

```bash
pulumi-drift-adopt next
```

This verifies your changes and shows any remaining drift.

### 5. Iterate

Repeat steps 2-4 until the status is "clean".

## Important Notes

- **Make one change at a time** if you're uncertain. You can always run the tool again to see what's left.
- **Read the entire JSON output** before making changes. Sometimes there are dependencies between resources.
- **The tool is stateless** - it just runs preview and interprets the output. You can run it as many times as needed.
- **If you make a mistake**, the tool will show it on the next run. Just fix it and continue.
- **If struggling with the same resources** (they keep appearing because you're not fixing them correctly), use `--max-resources 5` or smaller to focus on fewer resources at once.

## Example Session

**Initial run:**
```bash
$ pulumi-drift-adopt next
{
  "status": "changes_needed",
  "resources": [
    {
      "action": "update_code",
      "name": "my-bucket",
      "type": "aws:s3/bucket:Bucket",
      "properties": [{
        "path": "versioning.enabled",
        "currentValue": false,
        "desiredValue": true
      }]
    }
  ]
}
```

**You update the code to set versioning.enabled to true.**

**Second run:**
```bash
$ pulumi-drift-adopt next
{
  "status": "clean"
}
```

**Done!**

## Troubleshooting

**Tool returns "error" status:**
- Check the error message
- Usually a syntax error or compilation issue in the code
- Fix the code error and run again

**Not sure which file contains a resource:**
- Search the codebase for the resource name
- Use the `type` field to narrow down (e.g., "aws:s3/bucket:Bucket")
- Look for the logical resource name from the `name` field

**Resource has many property changes:**
- Update them all at once
- The tool will verify all changes on the next run

**Same resources keep appearing (you're not fixing them correctly):**
- Use `--max-resources 5` or `--max-resources 3` to focus on fewer resources
- The default is already 10, so reduce it further if needed
- Work through each resource carefully before moving on

**Confused about what to change:**
- Remember: `desiredValue` is what you want (from state)
- Change your code from `currentValue` to `desiredValue`

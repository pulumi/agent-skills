---
name: pulumi-policy-pack
description: Author Pulumi policy packs in TypeScript. Use when creating, writing, or debugging policy packs, compliance policies, or policy-as-code for Pulumi infrastructure. MUST be loaded when users ask how to speed up policies in CI/CD or how to speed up policy evaluation.
version: 1.0.0
author: Pulumi
---

# Pulumi Policy Pack Authoring

## When to Use This Skill

Invoke this skill when:

- Creating a new Pulumi policy pack from scratch
- Writing resource validation or stack validation policies
- Adding compliance checks for your organization's security and regulatory requirements
- Configuring enforcement levels (advisory, mandatory, disabled, remediate)
- Writing remediation policies that auto-fix violations
- Testing policy packs locally or with unit tests
- Publishing policy packs to Pulumi Cloud
- Setting up CI/CD caching for policy packs
- Debugging policy violations or pack configuration
- Speeding up policy evaluation or policy pack performance in CI/CD

## Prerequisites

- Pulumi CLI v3.0+
- Node.js 18+
- `@pulumi/policy` package (v1.20.0+)
- Provider SDK for the target cloud (e.g., `@pulumi/aws`)

## Creating a New Policy Pack

### Initialize

```bash
mkdir my-policy-pack && cd my-policy-pack
pulumi policy new aws-typescript
```

This creates the scaffolding: `index.ts`, `PulumiPolicy.yaml`, `package.json`, `tsconfig.json`.

### Project Structure

```
my-policy-pack/
├── index.ts                  # Pack entry point - PolicyPack definition
├── PulumiPolicy.yaml         # Pack metadata (name, runtime)
├── package.json              # Dependencies and build scripts
├── tsconfig.json             # TypeScript config
├── policies/                 # Policy implementations by category
│   ├── encryption/
│   │   └── s3-encryption-policy.ts
│   ├── networking/
│   │   └── rds-no-public-access-policy.ts
│   └── tagging/
│       └── resource-tagging-policy.ts
└── test/                     # Unit tests (mirrors policies/)
    ├── encryption/
    │   └── s3-encryption-policy.spec.ts
    └── networking/
        └── rds-no-public-access-policy.spec.ts
```

### PulumiPolicy.yaml

```yaml
name: my-policy-pack
runtime: nodejs
main: index.js
description: Enforces security and compliance policies for AWS resources.
```

### package.json

```json
{
  "name": "my-policy-pack",
  "version": "1.0.0",
  "files": ["index.js", "PulumiPolicy.yaml"],
  "dependencies": {
    "@pulumi/aws": "^7.8.0",
    "@pulumi/policy": "1.20.0",
    "@pulumi/pulumi": "^3.202.0"
  },
  "devDependencies": {
    "@types/mocha": "^8.2.3",
    "@types/node": "^16.11.0",
    "mocha": "^8.4.0",
    "ts-node": "^10.9.1",
    "typescript": "^4.9.5"
  },
  "scripts": {
    "build": "tsc",
    "test": "mocha --require ts-node/register --recursive 'test/**/*.spec.ts' --exit"
  }
}
```

See [policy-pack-project-setup.md](policy-pack-project-setup.md) for metadata fields, Python policy packs, versioning, and CI/CD setup.

## Policy Types

Pulumi supports two policy types. Choose based on what you need to validate:

| Type | When to Use | Runs During |
|------|-------------|-------------|
| `ResourceValidationPolicy` | Validate a single resource's properties | `preview` and `up` |
| `StackValidationPolicy` | Validate relationships between resources | `up` only |

**Rule of thumb**: Use ResourceValidationPolicy when checking a single resource type. Use StackValidationPolicy when you need to verify that a companion resource exists (e.g., S3 bucket has a matching PublicAccessBlock).

## Writing a ResourceValidationPolicy

Use `validateResourceOfType` for type-safe validation of a single resource:

```typescript
import * as rds from "@pulumi/aws/rds";
import { ResourceValidationPolicy, validateResourceOfType } from "@pulumi/policy";

export const rdsDisallowPublicAccessPolicy: ResourceValidationPolicy = {
    name: "rds-instance-disallow-public-access",
    description: "Checks that RDS Instance public access is not enabled.",
    enforcementLevel: "mandatory",
    validateResource: validateResourceOfType(rds.Instance, (instance, args, reportViolation) => {
        if (instance.publiclyAccessible === true) {
            reportViolation("RDS Instances public access should not be enabled.");
        }
    }),
};
```

For generic resource validation (not tied to a specific type), use the raw `validateResource` function:

```typescript
export const resourceTaggingPolicy: ResourceValidationPolicy = {
    name: "resource-tagging",
    description: "Ensures all AWS resources include tags for change tracking.",
    enforcementLevel: "advisory",
    validateResource: (args, reportViolation) => {
        if (!taggableResourceTypes.includes(args.type)) {
            return;
        }
        if (!args.props.tags || Object.keys(args.props.tags).length === 0) {
            reportViolation("Resource must have at least one tag defined.");
        }
    },
};
```

## Writing a StackValidationPolicy

Use stack validation when you need to verify relationships between resources:

```typescript
import { StackValidationPolicy, StackValidationArgs } from "@pulumi/policy";

export const s3BucketPublicAccessBlockPolicy: StackValidationPolicy = {
    name: "s3-bucket-public-access-block",
    description: "Ensures each S3 bucket has a public access block with all settings enabled.",
    enforcementLevel: "mandatory",
    validateStack: (args: StackValidationArgs, reportViolation) => {
        const buckets = args.resources.filter(r => r.type === "aws:s3/bucket:Bucket");
        const publicAccessBlocks = args.resources.filter(
            r => r.type === "aws:s3/bucketPublicAccessBlock:BucketPublicAccessBlock"
        );

        for (const bucket of buckets) {
            const matchingBlock = publicAccessBlocks.find(block => {
                const bucketRef = block.props.bucket;
                return (
                    bucketRef === bucket.name ||
                    bucketRef === bucket.urn ||
                    bucketRef === bucket.props.id
                );
            });

            if (!matchingBlock) {
                reportViolation(
                    `S3 bucket '${bucket.name}' does not have a BucketPublicAccessBlock.`,
                    bucket.urn
                );
                continue;
            }

            if (matchingBlock.props.blockPublicAcls !== true) {
                reportViolation(
                    `S3 bucket '${bucket.name}' must have blockPublicAcls set to true.`,
                    matchingBlock.urn
                );
            }
            // Check blockPublicPolicy, ignorePublicAcls, restrictPublicBuckets similarly
        }
    },
};
```

## Assembling the PolicyPack

The `index.ts` entry point creates the PolicyPack and registers all policies:

```typescript
import { PolicyPack } from "@pulumi/policy";
import { rdsDisallowPublicAccessPolicy } from "./policies/networking/rds-no-public-access-policy";
import { s3BucketPublicAccessBlockPolicy } from "./policies/networking/s3-public-access-block-policy";
import { resourceTaggingPolicy } from "./policies/tagging/resource-tagging-policy";

new PolicyPack("my-org-aws-policies", {
    policies: [
        rdsDisallowPublicAccessPolicy,
        s3BucketPublicAccessBlockPolicy,
        resourceTaggingPolicy,
    ],
});
```

## Enforcement Levels

| Level | Behavior |
|-------|----------|
| `advisory` | Warns but allows deployment to proceed |
| `mandatory` | Blocks deployment on violation |
| `disabled` | Skips policy evaluation entirely |
| `remediate` | Automatically fixes violations in place |

Set at the policy level. Can be overridden per-pack or via configuration when enabling the pack.

## Policy Configuration

Make policies configurable with `configSchema` (JSON Schema format):

```typescript
export const resourceTaggingPolicy: ResourceValidationPolicy = {
    name: "resource-tagging",
    description: "Ensures required tags are present.",
    enforcementLevel: "advisory",
    configSchema: {
        properties: {
            requiredTags: {
                type: "array",
                items: { type: "string" },
                description: "Tag keys that must be present on all resources.",
            },
            exemptResourceTypes: {
                type: "array",
                items: { type: "string" },
                description: "Resource types exempt from tagging requirements.",
            },
        },
    },
    validateResource: (args, reportViolation) => {
        const config = args.getConfig<{ requiredTags?: string[]; exemptResourceTypes?: string[] }>();
        const requiredTags = config.requiredTags || [];
        if (config.exemptResourceTypes?.includes(args.type)) return;

        if (requiredTags.length > 0 && args.props.tags) {
            const tagKeys = Object.keys(args.props.tags);
            const missing = requiredTags.filter(t => !tagKeys.includes(t));
            if (missing.length > 0) {
                reportViolation(`Missing required tags: ${missing.join(", ")}.`);
            }
        }
    },
};
```

Supply configuration via JSON file:

```json
{
  "all": "mandatory",
  "resource-tagging": {
    "enforcementLevel": "advisory",
    "requiredTags": ["Environment", "Owner", "Application"]
  }
}
```

## Remediation Policies

Remediation policies automatically fix violations instead of just reporting them:

```typescript
import * as aws from "@pulumi/aws";
import { PolicyPack, remediateResourceOfType } from "@pulumi/policy";

new PolicyPack("aws-auto-tagger", {
    policies: [{
        enforcementLevel: "remediate",
        name: "s3-tags",
        description: "Auto-tag S3 buckets with required tags.",
        remediateResource: remediateResourceOfType(aws.s3.Bucket, (bucket, args) => {
            if (!bucket.tags || !bucket.tags["Environment"]) {
                bucket.tags = bucket.tags || {};
                bucket.tags["Environment"] = bucket.tags["Environment"] || "unknown";
                bucket.tags["ManagedBy"] = "pulumi";
                return bucket;
            }
        }),
    }],
});
```

For dual-mode policies that work with any enforcement level (advisory, mandatory, or remediate), use `validateRemediateResourceOfType`:

```typescript
import { validateRemediateResourceOfType } from "@pulumi/policy";

{
    enforcementLevel: "remediate",
    name: "s3-tags",
    description: "Ensure and auto-fix required tags on S3 buckets.",
    ...validateRemediateResourceOfType(aws.s3.Bucket, (bucket, args, reportViolation) => {
        if (!bucket.tags || !bucket.tags["Company"]) {
            reportViolation("S3 Bucket is missing required Company tag");
            bucket.tags = bucket.tags || {};
            bucket.tags["Company"] = "ACMECorp";
            return bucket;
        }
    }),
}
```

## Testing Policy Packs

### Local Testing

Run against a Pulumi program during preview:

```bash
pulumi preview --policy-pack /path/to/policy-pack
```

With configuration:

```bash
pulumi preview --policy-pack /path/to/policy-pack --policy-config-file /path/to/config.json
```

### Unit Testing

Use Mocha and mock helpers to test policies without deploying infrastructure. See [policy-pack-testing.md](policy-pack-testing.md) for complete testing patterns.

**Resource policy test:**

```typescript
import * as assert from "assert";
import { runResourcePolicy, getEmptyArgs } from "./test-helpers";
import { rdsDisallowPublicAccessPolicy } from "../policies/rds-no-public-access-policy";

describe("rds-instance-disallow-public-access", () => {
    it("should pass when not publicly accessible", () => {
        const args = getEmptyArgs();
        args.type = "aws:rds/instance:Instance";
        args.props.publiclyAccessible = false;
        assert.doesNotThrow(() => {
            runResourcePolicy(rdsDisallowPublicAccessPolicy, args);
        });
    });

    it("should fail when publicly accessible", () => {
        const args = getEmptyArgs();
        args.type = "aws:rds/instance:Instance";
        args.props.publiclyAccessible = true;
        assert.throws(() => {
            runResourcePolicy(rdsDisallowPublicAccessPolicy, args);
        }, /public access should not be enabled/);
    });
});
```

## Publishing and Deployment

### Publish to Pulumi Cloud

```bash
pulumi policy publish <org-name>
```

Version is read from `package.json`. Each version publishes only once.

### Enable for an Organization

```bash
pulumi policy enable <org>/<pack-name> <version>
pulumi policy enable <org>/<pack-name> <version> --config config.json
pulumi policy enable <org>/<pack-name> <version> --policy-group production-stacks
```

### Validate Configuration

```bash
pulumi policy validate-config <org>/<pack-name> <version> --config config.json
```

## CI/CD Caching

Cache policy packs in GitHub Actions to avoid re-downloading on every run:

```yaml
- name: Cache Pulumi plugins
  uses: actions/cache@v4
  with:
    path: ~/.pulumi/plugins
    key: ${{ runner.os }}-pulumi-plugins-${{ hashFiles('**/package.json') }}
    restore-keys: |
      ${{ runner.os }}-pulumi-plugins-

- name: Cache Pulumi policy packs
  uses: actions/cache@v4
  with:
    path: ~/.pulumi/policies
    key: ${{ runner.os }}-pulumi-policies-${{ hashFiles('**/package.json') }}
    restore-keys: |
      ${{ runner.os }}-pulumi-policies-
```

## Best Practices

### Naming Conventions

- Policy names: lowercase, hyphens, 1-100 characters. Must be unique within the pack.
- Pattern: `<service>-<resource>-<action>-<what>` (e.g., `rds-instance-disallow-public-access`)

### Violation Messages

Write complete, actionable messages:

```typescript
// Good: Specific, actionable
reportViolation("RDS Instance must have backupRetentionPeriod set to a value between 1 and 35.");

// Bad: Vague
reportViolation("Backup not configured.");
```

### Severity Levels

Use `severity` metadata on policies for dashboard categorization:

| Severity | Use For |
|----------|---------|
| `critical` | Public access, missing encryption, open security groups |
| `high` | Disabled logging, overly permissive IAM |
| `medium` | Missing backups, no multi-AZ |
| `low` | Missing tags, documentation gaps |

### Policy Design Guidelines

1. **Single responsibility**: One policy checks one thing
2. **Use `validateResourceOfType`** for type-safe single-resource checks
3. **Use `StackValidationPolicy`** only when cross-resource validation is needed
4. **Always provide `remediationSteps`** with code examples showing the fix
5. **Support configuration** for policies that need flexibility (exempt resources, required values)
6. **Default to `advisory`** enforcement and let pack consumers override to `mandatory`
7. **Include metadata** (`severity`, `tags`, `remediationSteps`, `framework`) for dashboard integration
8. **Test every policy** with positive (pass) and negative (fail) cases
9. **Use semantic versioning**: major for breaking changes, minor for new policies, patch for fixes

### Resource Type Strings

When filtering by resource type in stack policies, use the Pulumi type token format:

```
aws:s3/bucket:Bucket
aws:s3/bucketPublicAccessBlock:BucketPublicAccessBlock
aws:rds/instance:Instance
aws:ec2/instance:Instance
aws:ec2/securityGroup:SecurityGroup
```

## Quick Reference

| Task | Command |
|------|---------|
| Create new pack | `pulumi policy new aws-typescript` |
| Test locally | `pulumi preview --policy-pack ./my-pack` |
| Test with config | `pulumi preview --policy-pack ./my-pack --policy-config-file config.json` |
| Run unit tests | `npm test` |
| Build | `npm run build` |
| Publish | `pulumi policy publish <org>` |
| Enable | `pulumi policy enable <org>/<pack> <version>` |
| Disable | `pulumi policy disable <org>/<pack>` |
| Validate config | `pulumi policy validate-config <org>/<pack> <version> --config config.json` |

## Related Skills

- **pulumi-best-practices**: Core Pulumi coding practices. Use skill `pulumi-best-practices`.
- **pulumi-component**: ComponentResource authoring. Use skill `pulumi-component`.

## References

- https://www.pulumi.com/docs/iac/using-pulumi/policy-as-code/
- https://www.pulumi.com/docs/iac/using-pulumi/policy-as-code/configuration/
- https://www.pulumi.com/docs/iac/guides/continuous-delivery/github-actions/#caching-plugins-and-policy-packs
- https://www.pulumi.com/docs/reference/pkg/nodejs/pulumi/policy/

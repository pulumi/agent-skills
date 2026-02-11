# Policy Pack Testing Reference

## Test Helpers

Create a `test-helpers.ts` file with mock utilities for unit testing policies without deploying infrastructure:

```typescript
import * as policy from "@pulumi/policy";

function getEmptyOptions(): policy.PolicyResourceOptions {
    return {
        protect: false,
        ignoreChanges: [],
        deleteBeforeReplace: false,
        aliases: [],
        customTimeouts: { createSeconds: 0, updateSeconds: 0, deleteSeconds: 0 },
        additionalSecretOutputs: [],
    };
}

function reportThrow(message: string, urn?: string): never {
    throw new Error(message);
}

export function getEmptyArgs(): policy.ResourceValidationArgs {
    const args: policy.ResourceValidationArgs = {
        type: "",
        props: {},
        urn: "unknown",
        name: "unknown",
        opts: getEmptyOptions(),
        isType: (checkType: any) => checkType && checkType.__pulumiType === args.type,
        asType: (checkType: any) =>
            checkType?.__pulumiType === args.type ? args.props : undefined,
        getConfig: <T>() => <T>{},
        stackTags: new Map<string, string>(),
        notApplicable: (reason?: string): never => {
            throw new Error(reason || "Not applicable");
        },
    };
    return args;
}

export function runResourcePolicy(
    resourcePolicy: policy.ResourceValidationPolicy,
    args: policy.ResourceValidationArgs,
    report = reportThrow
) {
    const validations = Array.isArray(resourcePolicy.validateResource)
        ? resourcePolicy.validateResource
        : [resourcePolicy.validateResource];

    for (const validation of validations) {
        if (validation) {
            try {
                validation(args, report);
            } catch (e: any) {
                if (e.message?.includes("Policy only applies to resources of type")) {
                    continue;
                }
                throw e;
            }
        }
    }
}

export function createPolicyResource(
    type: string,
    name: string,
    props: any
): policy.PolicyResource {
    return {
        type,
        name,
        props,
        urn: `urn:pulumi:stack::project::${type}::${name}`,
        opts: getEmptyOptions(),
        dependencies: [],
        propertyDependencies: {},
        isType: (t: any) => t?.__pulumiType === type,
        asType: (t: any) => (t?.__pulumiType === type ? props : undefined),
    };
}

export function createStackValidationArgs(
    resources: policy.PolicyResource[]
): policy.StackValidationArgs {
    return {
        resources,
        getConfig: <T>() => <T>{},
    };
}

export function runStackPolicy(
    stackPolicy: policy.StackValidationPolicy,
    args: policy.StackValidationArgs,
    report = reportThrow
) {
    if (stackPolicy.validateStack) {
        stackPolicy.validateStack(args, report);
    }
}
```

## Testing Resource Validation Policies

### Basic Pattern

```typescript
import * as assert from "assert";
import { runResourcePolicy, getEmptyArgs } from "../test-helpers";
import { myPolicy } from "../../policies/my-policy";

describe("my-policy", () => {
    it("should pass when resource is compliant", () => {
        const args = getEmptyArgs();
        args.type = "aws:rds/instance:Instance";
        args.props.publiclyAccessible = false;

        assert.doesNotThrow(() => {
            runResourcePolicy(myPolicy, args);
        });
    });

    it("should fail when resource violates policy", () => {
        const args = getEmptyArgs();
        args.type = "aws:rds/instance:Instance";
        args.props.publiclyAccessible = true;

        assert.throws(() => {
            runResourcePolicy(myPolicy, args);
        }, /public access should not be enabled/);
    });

    it("should pass when property is undefined (safe default)", () => {
        const args = getEmptyArgs();
        args.type = "aws:rds/instance:Instance";
        // publiclyAccessible not set

        assert.doesNotThrow(() => {
            runResourcePolicy(myPolicy, args);
        });
    });
});
```

### Testing with Configuration

Override `getConfig` to supply configuration values:

```typescript
it("should respect exempt resource types", () => {
    const args = getEmptyArgs();
    args.type = "aws:s3/bucket:Bucket";
    args.props.tags = {};
    args.getConfig = <T>() => ({
        exemptResourceTypes: ["aws:s3/bucket:Bucket"],
    }) as T;

    assert.doesNotThrow(() => {
        runResourcePolicy(resourceTaggingPolicy, args);
    });
});

it("should check required tags from configuration", () => {
    const args = getEmptyArgs();
    args.type = "aws:ec2/instance:Instance";
    args.props.tags = { Owner: "team-a" };
    args.getConfig = <T>() => ({
        requiredTags: ["Owner", "Environment"],
    }) as T;

    assert.throws(() => {
        runResourcePolicy(resourceTaggingPolicy, args);
    }, /Missing required tags: Environment/);
});
```

## Testing Stack Validation Policies

### Pattern for Cross-Resource Validation

```typescript
import * as assert from "assert";
import { runStackPolicy, createPolicyResource, createStackValidationArgs } from "../test-helpers";
import { s3BucketPublicAccessBlockPolicy } from "../../policies/s3-public-access-block-policy";

describe("s3-bucket-public-access-block", () => {
    it("should fail when bucket has no public access block", () => {
        const stackArgs = createStackValidationArgs([
            createPolicyResource("aws:s3/bucket:Bucket", "test-bucket", {
                id: "test-bucket",
            }),
        ]);

        assert.throws(() => {
            runStackPolicy(s3BucketPublicAccessBlockPolicy, stackArgs);
        }, /does not have a BucketPublicAccessBlock/);
    });

    it("should fail when blockPublicAcls is false", () => {
        const stackArgs = createStackValidationArgs([
            createPolicyResource("aws:s3/bucket:Bucket", "test-bucket", {
                id: "test-bucket",
            }),
            createPolicyResource(
                "aws:s3/bucketPublicAccessBlock:BucketPublicAccessBlock",
                "test-pab",
                {
                    bucket: "test-bucket",
                    blockPublicAcls: false,
                    blockPublicPolicy: true,
                    ignorePublicAcls: true,
                    restrictPublicBuckets: true,
                }
            ),
        ]);

        assert.throws(() => {
            runStackPolicy(s3BucketPublicAccessBlockPolicy, stackArgs);
        }, /blockPublicAcls/);
    });

    it("should pass when all settings are enabled", () => {
        const stackArgs = createStackValidationArgs([
            createPolicyResource("aws:s3/bucket:Bucket", "test-bucket", {
                id: "test-bucket",
            }),
            createPolicyResource(
                "aws:s3/bucketPublicAccessBlock:BucketPublicAccessBlock",
                "test-pab",
                {
                    bucket: "test-bucket",
                    blockPublicAcls: true,
                    blockPublicPolicy: true,
                    ignorePublicAcls: true,
                    restrictPublicBuckets: true,
                }
            ),
        ]);

        assert.doesNotThrow(() => {
            runStackPolicy(s3BucketPublicAccessBlockPolicy, stackArgs);
        });
    });

    it("should handle multiple buckets", () => {
        const stackArgs = createStackValidationArgs([
            createPolicyResource("aws:s3/bucket:Bucket", "bucket-1", { id: "bucket-1" }),
            createPolicyResource(
                "aws:s3/bucketPublicAccessBlock:BucketPublicAccessBlock",
                "pab-1",
                {
                    bucket: "bucket-1",
                    blockPublicAcls: true,
                    blockPublicPolicy: true,
                    ignorePublicAcls: true,
                    restrictPublicBuckets: true,
                }
            ),
            createPolicyResource("aws:s3/bucket:Bucket", "bucket-2", { id: "bucket-2" }),
            createPolicyResource(
                "aws:s3/bucketPublicAccessBlock:BucketPublicAccessBlock",
                "pab-2",
                {
                    bucket: "bucket-2",
                    blockPublicAcls: true,
                    blockPublicPolicy: true,
                    ignorePublicAcls: true,
                    restrictPublicBuckets: true,
                }
            ),
        ]);

        assert.doesNotThrow(() => {
            runStackPolicy(s3BucketPublicAccessBlockPolicy, stackArgs);
        });
    });
});
```

## Test Runner Configuration

### .mocharc.json

```json
{
  "require": ["ts-node/register"],
  "extensions": ["ts"],
  "spec": "test/**/*.spec.ts",
  "exit": true
}
```

### Running Tests

```bash
# Run all tests
npm test

# Run a specific test file
npx mocha --require ts-node/register test/networking/rds-no-public-access-policy.spec.ts --exit

# Run with verbose output
npx mocha --require ts-node/register --recursive 'test/**/*.spec.ts' --reporter spec --exit
```

## Test Coverage Checklist

For each policy, test:

- [ ] Compliant resource passes (no violation)
- [ ] Non-compliant resource fails (violation reported)
- [ ] Undefined/missing properties handled safely
- [ ] Multiple violation scenarios if the policy checks multiple properties
- [ ] Configuration overrides work (if policy is configurable)
- [ ] Edge cases: empty values, null, unexpected types
- [ ] Multiple resources in stack (for stack validation policies)

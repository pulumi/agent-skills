# Policy Pack Project Setup Reference

## Production Build Configuration

For production policy packs, use Rollup to bundle all policy code into a single `index.js`. This simplifies publishing and ensures all dependencies are resolved.

### rollup.config.mjs

```javascript
import typescript from "@rollup/plugin-typescript";
import resolve from "@rollup/plugin-node-resolve";
import commonjs from "@rollup/plugin-commonjs";
import json from "@rollup/plugin-json";

export default {
    input: "index.ts",
    output: {
        file: "index.js",
        format: "cjs",
        sourcemap: false,
    },
    external: [
        "@pulumi/policy",
        "@pulumi/pulumi",
        "@pulumi/aws",
    ],
    plugins: [
        resolve({
            preferBuiltins: true,
            extensions: [".ts", ".js", ".json"],
        }),
        typescript({
            tsconfig: "./tsconfig.json",
            noEmitOnError: true,
            sourceMap: false,
            declaration: false,
            module: "esnext",
        }),
        json(),
        commonjs(),
    ],
};
```

Pulumi provider SDKs (`@pulumi/aws`, `@pulumi/policy`, `@pulumi/pulumi`) are listed as `external` because they are injected at runtime by the Pulumi engine. Do not bundle them.

### tsconfig.json

```json
{
    "compilerOptions": {
        "outDir": "bin",
        "target": "es6",
        "module": "commonjs",
        "moduleResolution": "node",
        "declaration": true,
        "sourceMap": false,
        "stripInternal": true,
        "experimentalDecorators": true,
        "pretty": true,
        "noFallthroughCasesInSwitch": true,
        "noImplicitAny": true,
        "noImplicitReturns": true,
        "forceConsistentCasingInFileNames": true,
        "strictNullChecks": true
    },
    "files": ["index.ts"],
    "include": [
        "policies/**/*.ts",
        "test/**/*.ts"
    ]
}
```

### package.json (Production)

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
    "@rollup/plugin-commonjs": "^28.0.2",
    "@rollup/plugin-json": "^6.1.0",
    "@rollup/plugin-node-resolve": "^16.0.0",
    "@rollup/plugin-typescript": "^12.1.2",
    "@types/mocha": "^8.2.3",
    "@types/node": "^16.11.0",
    "mocha": "^8.4.0",
    "rollup": "^4.31.0",
    "ts-node": "^10.9.1",
    "typescript": "^4.9.5"
  },
  "scripts": {
    "build": "rollup -c",
    "test": "mocha --require ts-node/register --recursive 'test/**/*.spec.ts' --exit"
  },
  "ts-node": {
    "compilerOptions": {
      "module": "commonjs"
    }
  }
}
```

### Makefile

```makefile
.PHONY: build clean install test publish ensure all

build:
	npm run build

install:
	npm install

clean:
	rm -f index.js

ensure:
	npm ci

test: ensure
	npm test

publish: build
	@if [ -z "$(ORG)" ]; then \
		echo "Error: ORG is not set. Usage: make publish ORG=your-org-name"; \
		exit 1; \
	fi
	pulumi policy publish $(ORG)

all: clean install build
```

## Framework Configuration Pattern

For compliance frameworks that map controls to policies, use the framework configuration builder pattern. This works for any framework (internal standards, regulatory requirements, security baselines):

### types/framework-config.ts

```typescript
import { ResourceValidationPolicy, StackValidationPolicy } from "@pulumi/policy";

export type Policy = ResourceValidationPolicy | StackValidationPolicy;

export interface PolicyConfig {
    policy: Policy;
    enforcementLevel?: "advisory" | "mandatory" | "disabled";
    severity?: "low" | "medium" | "high" | "critical";
}

export interface FrameworkControlConfig {
    specification: string;
    policies: PolicyConfig[];
}

export interface FrameworkConfig {
    framework: string;
    version: string;
    controls: Record<string, FrameworkControlConfig>;
}
```

### utils/framework-policy-builder.ts

```typescript
import { FrameworkConfig, Policy } from "../types/framework-config";

export function buildPolicyPackFromFrameworkConfig(config: FrameworkConfig): Policy[] {
    const processedPolicies = new Map<string, Policy>();

    for (const [controlReference, controlConfig] of Object.entries(config.controls)) {
        for (const policyConfig of controlConfig.policies) {
            const policy = policyConfig.policy;
            const policyName = policy.name;

            if (processedPolicies.has(policyName)) {
                const existingPolicy = processedPolicies.get(policyName)!;
                if (existingPolicy.framework) {
                    existingPolicy.framework.reference += `; ${controlReference}`;
                    existingPolicy.framework.specification += `; ${controlConfig.specification}`;
                }
            } else {
                const processedPolicy: Policy = {
                    ...policy,
                    enforcementLevel: policyConfig.enforcementLevel ?? policy.enforcementLevel,
                    severity: policyConfig.severity ?? policy.severity,
                    framework: {
                        name: config.framework,
                        version: config.version,
                        reference: controlReference,
                        specification: controlConfig.specification,
                    },
                };
                processedPolicies.set(policyName, processedPolicy);
            }
        }
    }

    return Array.from(processedPolicies.values());
}
```

### Usage in index.ts

```typescript
import { PolicyPack } from "@pulumi/policy";
import { buildPolicyPackFromFrameworkConfig } from "./utils/framework-policy-builder";
import { rdsDisallowPublicAccessPolicy } from "./policies/networking/rds-no-public-access-policy";
import { s3EncryptionPolicy } from "./policies/encryption/s3-encryption-policy";

const config = {
    framework: "My Compliance Framework",
    version: "1.0",
    controls: {
        "3.1 Encryption at Rest": {
            specification: "All stored data must be encrypted.",
            policies: [
                { policy: s3EncryptionPolicy, enforcementLevel: "mandatory", severity: "critical" },
            ],
        },
        "4.2 Network Security": {
            specification: "Databases must not be publicly accessible.",
            policies: [
                { policy: rdsDisallowPublicAccessPolicy, enforcementLevel: "mandatory", severity: "critical" },
            ],
        },
    },
};

new PolicyPack("my-compliance-pack", {
    policies: buildPolicyPackFromFrameworkConfig(config),
});
```

This pattern deduplicates policies that appear in multiple controls and merges framework references.

## JSDoc Metadata Annotations

Add metadata annotations to policies for dashboard integration and discoverability:

```typescript
/*
 * @framework my-security-standard
 * @version 1.0
 * @reference 4.2 Network Controls
 * @severity critical
 * @topics network, security
 * @services rds
 * @platform aws
 * @requirement Require RDS instances to disable public access
 * @specification Networks shall be managed and controlled to protect the organization.
 * @link https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_VPC.html
 * @displayName RDS Instance Disallow Public Access
 */
```

**Valid topic values**: `authentication`, `availability`, `backup`, `container`, `cost`, `documentation`, `encryption`, `kubernetes`, `logging`, `network`, `performance`, `permissions`, `resilience`, `runtime`, `security`, `storage`, `usability`, `vulnerability`

## Remediation Steps Template

Include `remediationSteps` in every policy for clear guidance on fixing violations:

```typescript
export const myPolicy: ResourceValidationPolicy = {
    name: "rds-instance-enable-backup-retention",
    description: "Checks that RDS instances have backup retention enabled.",
    enforcementLevel: "advisory",
    severity: "medium",
    remediationSteps: `## Fix: Enable Backup Retention for RDS Instance

Set the \`backupRetentionPeriod\` to a value between 1 and 35 days:

\`\`\`typescript
const dbInstance = new aws.rds.Instance("my-db", {
    engine: "mysql",
    instanceClass: "db.t3.micro",
    allocatedStorage: 20,
    backupRetentionPeriod: 7, // Enable backup retention (1-35 days)
    username: "admin",
    password: dbPassword,
});
\`\`\``,
    validateResource: validateResourceOfType(rds.Instance, (instance, args, reportViolation) => {
        if (!instance.backupRetentionPeriod) {
            reportViolation("RDS Instance backup retention should be enabled.");
        }
    }),
};
```

## CI/CD Integration

### GitHub Actions Workflow

Complete workflow with caching, testing, and policy enforcement:

```yaml
name: Pulumi Policy Pack CI

on:
  pull_request:
  push:
    branches: [main]

jobs:
  test:
    name: Test Policy Pack
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version-file: package.json
      - run: npm ci
      - run: npm test

  preview:
    name: Preview with Policies
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version-file: package.json
      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-region: ${{ secrets.AWS_REGION }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
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
      - run: npm ci
      - uses: pulumi/actions@v6
        with:
          command: preview
          stack-name: org-name/stack-name
        env:
          PULUMI_ACCESS_TOKEN: ${{ secrets.PULUMI_ACCESS_TOKEN }}

  publish:
    name: Publish Policy Pack
    needs: [test, preview]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version-file: package.json
      - run: npm ci && npm run build
      - run: pulumi policy publish my-org
        env:
          PULUMI_ACCESS_TOKEN: ${{ secrets.PULUMI_ACCESS_TOKEN }}
```

## Version Management

Use semantic versioning in `package.json`:

- **Major** (1.0.0 -> 2.0.0): Breaking policy behavior changes (e.g., advisory -> mandatory default)
- **Minor** (1.0.0 -> 1.1.0): New policies added
- **Patch** (1.0.0 -> 1.0.1): Bug fixes in existing policies

Each version publishes only once. Attempting to republish the same version produces an error:

```
error: [400] Bad Request: Policy Pack "my-pack" (Version 1.0.0)
has already been published. Please specify a new version tag.
```

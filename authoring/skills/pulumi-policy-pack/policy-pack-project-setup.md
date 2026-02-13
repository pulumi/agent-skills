# Policy Pack Project Setup Reference

## TypeScript Configuration

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

## Policy Metadata

Policies support metadata fields for display, categorization, and compliance mapping. These are defined directly on the policy object:

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique identifier within the pack (1-100 chars) |
| `description` | Yes | Short summary of what the policy checks |
| `enforcementLevel` | No | `advisory`, `mandatory`, `remediate`, or `disabled` |
| `severity` | No | `low`, `medium`, `high`, or `critical` |
| `displayName` | No | Human-readable name for dashboards |
| `remediationSteps` | No | Guidance for fixing violations (supports markdown) |
| `url` | No | Link to external documentation |
| `tags` | No | Array of labels for grouping and filtering |
| `framework` | No | Compliance framework association (requires `name`, `version`, `reference`, `specification`) |
| `configSchema` | No | JSON Schema for user-configurable parameters |

## Remediation Steps

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

  publish:
    name: Publish Policy Pack
    needs: test
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

Use semantic versioning (`package.json` for TypeScript, `PulumiPolicy.yaml` for Python):

- **Major** (1.0.0 -> 2.0.0): Breaking policy behavior changes (e.g., advisory -> mandatory default)
- **Minor** (1.0.0 -> 1.1.0): New policies added
- **Patch** (1.0.0 -> 1.0.1): Bug fixes in existing policies

Each version publishes only once. Attempting to republish the same version produces an error:

```
error: [400] Bad Request: Policy Pack "my-pack" (Version 1.0.0)
has already been published. Please specify a new version tag.
```

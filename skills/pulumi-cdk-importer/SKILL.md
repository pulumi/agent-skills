---
name: pulumi-cdk-importer
description: Automated import of CDK-managed AWS infrastructure into Pulumi state
---

# Pulumi CDK Importer Tool

This tool assists migrating CDK-managed infrastructure to Pulumi. It imports existing AWS resources from CloudFormation stacks into Pulumi state.

## Installation

```shell
pulumi plugin install tool cdk-importer
```

## Credentials

Running the `cdk-importer` tool requires credentials loaded via Pulumi ESC.

- If the user has already provided an ESC environment, use it.
- If no ESC environment is specified, **ask the user which ESC environment to use** before proceeding with using the tool.

You MUST confirm the AWS region with the user. The results may be incorrect if ran with the wrong AWS Region. The region can be set with the `AWS_REGION` environment variable

## Commands

### program import

Import into the selected Pulumi stack using an existing generated Pulumi program.

```shell
pulumi plugin run cdk-importer -- program import \
  --program-dir ./generated \
  --stack MyStack
```

**Required flags:**

- `--program-dir`: Path to an existing Pulumi program generated from a CDK app
- `--stack`: CloudFormation stack name (can be specified multiple times or comma-separated)

**Optional flags:**

- `--import-file`: Path to write a Pulumi bulk import file with failing resources (defaults to `import.json` when provided without a value)
- `--debug`: Enable line by line logging of imported resources

**Behavior:**

- Runs against the selected Pulumi stack.
- With `--import-file`, writes the bulk import file after import. The file will only contain entries for resources that failed to import with `<PLACEHOLDER>` ids.
- Can be run iteratively to progressively import resources.

**Example Output:**

```shell
[INFO] Getting stack resources component="cdk-importer" stack=NeoExample-Dev
[INFO] Starting up providers... component="cdk-importer"
[INFO] Importing stack... component="cdk-importer"
[INFO] Run complete component="cdk-importer" status="success" resourcesImported=50 resourcesFailedToImport=0 stack="NeoExample-Dev" importFile="/workspace/pulumi-example-app-neo/import.json" importFileExists=true
```

## Import File Output

The generated `import.json` includes:

- Full AWS resource metadata (type, logical name, provider reference, component bit, provider version)
- Property subsets captured during provider interception

Resources with composite identifiers may show `<PLACEHOLDER>` IDs that need manual completion before running `pulumi import --file import.json`.

## Unsupported Resources

**Resources that cannot be imported:**

- CFN Custom Resources (`aws-native:cloudformation:CustomResourceEmulator`)

## Example Workflow

1. Generate a Pulumi program from your CDK app using `cdk2pulumi`

2. Import into your real stack:

   ```shell
   pulumi plugin run cdk-importer -- program import \
     --program-dir ./pulumi-program-dir \
     --stack CdkStack
   ```

## Handling Failures

This tool may not support 100% of the CloudFormation resources in the stack. For unsupported resources it is necessary to find the import ID and import manually.

**Example output:**

```shell
[INFO] Getting stack resources component="cdk-importer" stack=NeoExample-Dev
[INFO] Starting up providers... component="cdk-importer"
[INFO] Importing stack... component="cdk-importer"
[INFO] Pulumi errors component="cdk-importer" details=urn:pulumi:dev::cdk-convert-example::aws:rds/proxyDefaultTargetGroup:ProxyDefaultTargetGroup::DatabaseDbClusterDbProxyProxyTargetGroupA552DCC1: Don't have an ID!: aws:rds/proxyDefaultTargetGroup:ProxyDefaultTargetGroup neo-example-dev-database-db-cluster-db-proxy-eede4daa urn:pulumi:dev::cdk-convert-example::aws:rds/proxyDefaultTargetGroup:ProxyDefaultTargetGroup::DatabaseDbClusterDbProxyProxyTargetGroupA552DCC1

update failed
[INFO] Run complete component="cdk-importer" status="failed" resourcesImported=69 resourcesFailedToImport=1 stack="NeoExample-Dev"
- operation failed
```

**Example Failure Workflow:**

1. Import ran with error

2. Review failures and run `pulumi preview`.
   - Any resources that fail to import should appear as creations in the preview.
   - Optionally run `program import` with the `--import-file` flag to generate a `import.json` file with the failing resources.

3. Manually import remaining resources

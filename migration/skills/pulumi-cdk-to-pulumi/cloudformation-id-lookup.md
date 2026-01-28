# Pulumi Import ID Lookup (`cdk2pulumi ids`)

This tool looks up the required Pulumi import ID format for AWS resources, helping you understand what identifier shape is needed when importing existing AWS resources into Pulumi.

## Prerequisites

- The tool must be installed: `pulumi plugin install tool cdk2pulumi`
- Run via: `pulumi plugin run cdk2pulumi -- ids <resource-type>`

## Usage

### Look Up by Pulumi Resource Token or CloudFormation type

```bash
pulumi plugin run cdk2pulumi -- ids aws-native:s3:Bucket
pulumi plugin run cdk2pulumi -- ids AWS::S3::Bucket
```

## Understanding the Output

The tool returns two key pieces of information:

### 1. Import ID Format

Shows the structure of the ID required by Pulumi's `import` command. Examples:

- **Single-part ID**: `<BucketName>` - Just the bucket name
- **Composite ID**: `<FunctionName>|<StatementId>` - Multiple parts separated by delimiters
- **Complex ID**: `<CertificateAuthorityArn>|<CertificateArn>` - ARNs or other identifiers

### 2. Finding the ID Hint

Provides guidance on how to obtain the actual ID value from AWS:

- **Single-part IDs**: "Use the CloudFormation PhysicalResourceId"
  - Find this in CloudFormation via `aws cloudformation describe-stack-resources` or `aws cloudformation list-stack-resources`
- **Composite IDs**: Shows an `aws cloudcontrol list-resources` command example
  - May include `--resource-model '{...}'` when the Cloud Control API requires input parameters
  - Example: `aws cloudcontrol list-resources --type-name AWS::Lambda::Permission --resource-model '{"FunctionName":"my-function"}'`

## Examples

### Simple Resource (S3 Bucket)

```bash
$ pulumi plugin run cdk2pulumi -- ids AWS::S3::Bucket
Import ID format: <BucketName>
Finding the ID: Use the CloudFormation PhysicalResourceId
```

### Composite ID (Lambda Permission)

```bash
$ pulumi plugin run cdk2pulumi -- ids AWS::Lambda::Permission
Import ID format: <FunctionName>|<StatementId>
Finding the ID: aws cloudcontrol list-resources --type-name AWS::Lambda::Permission --resource-model '{"FunctionName":"<function-name>"}'
```

### Complex Resource (ACM PCA Certificate)

```bash
$ pulumi plugin run cdk2pulumi -- ids AWS::ACMPCA::Certificate
Import ID format: <CertificateAuthorityArn>|<CertificateArn>
Finding the ID: aws cloudcontrol list-resources --type-name AWS::ACMPCA::Certificate --resource-model '{"CertificateAuthorityArn":"<ca-arn>"}'
```

## Tips for Running

- Always use `--` to separate Pulumi CLI arguments from plugin arguments
- For composite IDs, pay attention to the delimiter (usually `|`, `/`, or `:`)
- When the hint shows `--resource-model`, you'll need to provide known properties to list the resources
- The PhysicalResourceId from CloudFormation is often the simplest way to find single-part IDs
- Some resources may require multiple API calls to construct the full composite ID

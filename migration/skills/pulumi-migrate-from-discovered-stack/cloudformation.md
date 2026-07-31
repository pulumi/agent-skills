# CloudFormation Reference

Reference material for the `pulumi-migrate-from-discovered-stack` skill when working with CloudFormation (or CDK-synthesized CF) discovered stacks. Use this file for:

- AWS credentials and CLI setup (Phase 0 / 2)
- Looking up resource details, verifying existence, finding import IDs (Phase 4 / 5 troubleshooting)
- Provider choice (`aws` classic vs `aws-native`)
- Custom resource handler replacements (CDK-synthesized stacks)
- Reading the original CF template during the optional refactor phase

> **Important:** this is reference, **not a workflow**. The main `SKILL.md` (Phase 0–6) is the workflow. The public `cloudformation-to-pulumi` skill prescribes a template-first, `aws-native`-mandatory approach driven by `cdk-importer` — that conflicts with our cloud-state-first import flow. Do not load it alongside this skill.

---

## 1. AWS credentials

Sanity-check credentials before running imports:

```bash
aws sts get-caller-identity   # confirm credentials are alive and identify the account
aws configure get region      # confirm region matches the discovered stack
```

STS session tokens expire in 1–12 h — if `pulumi import` fails with `ExpiredToken`, ask for fresh creds.

---

## 2. AWS-specific project setup

After creating the Pulumi project (see SKILL.md Phase 2):

```bash
pulumi config set aws:region <region>
# If using aws-native provider, also set aws-native:region

npm install @pulumi/aws
```

---

## 3. Querying CloudFormation and AWS

These help during Phase 5 (NotFound / NoMatch triage) when you need to verify a resource exists or look up an ID our API didn't already capture, and during Phase 7 (optional refactor) to fetch the original template as a structural reference.

### Get the original CF template
```bash
aws cloudformation get-template \
  --region <region> \
  --stack-name <cfn-stack-name> \
  --query 'TemplateBody' \
  --output json > .migration/template.json
```

Two uses:
- **Phase 5 triage**: when `NoMatch`, see what a resource was *supposed* to be (original type, properties, relationships).
- **Phase 7 refactor**: a concrete reference for resource grouping, parameters, conditional logic, intrinsic-function references. Save it in `.migration/` so it's committed alongside the code.

### Verify a single resource
```bash
aws cloudformation describe-stack-resource \
  --region <region> \
  --stack-name <cfn-stack-name> \
  --logical-resource-id <id>
```

If this returns `ResourceStatus: DELETE_COMPLETE` or 404, the resource is gone — annotate `statusOverride=Migrated` with a note.

### General AWS lookup

For composite-ID resources (e.g. `aws:lambda/permission:Permission`) or when our API doesn't have the details, use AWS Cloud Control:

```bash
aws cloudcontrol get-resource --type-name <CFN-type> --identifier <id>
aws cloudcontrol list-resources --type-name <CFN-type>
```

Works for any CloudFormation resource type. For the Pulumi type's expected import-ID shape, check the resource's registry page at https://www.pulumi.com/registry/packages/aws/api-docs/ (the "Import" section is on each resource page).

---

## 4. Provider choice — `aws` (classic) vs `aws-native`

**Default to `aws` (classic)** for our flow. The discovered-stacks API maps most CF types to classic provider tokens (e.g. `AWS::S3::Bucket` → `aws:s3/bucket:Bucket`), and that's what we trust by default.

**Use `aws-native` when:**
- The classic provider doesn't expose the resource (e.g. some recent AWS service launches).
- The classic provider has a known import bug for that type (rare; document in the migration report when you hit one).
- The user specifically requests it for downstream consistency.

**Don't mix providers for the same logical resource.** If you migrate an S3 bucket via `aws.s3.Bucket`, don't migrate its policy as `aws-native.s3.BucketPolicy` — pick one provider per logical group.

---

## 5. CDK-synthesized stacks

When the discovered CF stack was produced by AWS CDK, there are a few extra signals and patterns the agent should know. This section only applies to CDK stacks; plain CF stacks skip it.

**Detection:** resources synthesized by CDK carry an `inputs.cdkPath` field in our API response (e.g. `CdkExampleStack-Dev/Messaging/SnsTopic/Resource`). If you see `cdkPath` on multiple resources, you're looking at a CDK-synthesized stack.

### 5.1 `cdkPath` as a structural signal

`cdkPath` is the CDK construct path. It's hierarchical and groups resources by the construct that created them. In Phase 7 (refactor) it's the most reliable way to find natural component boundaries:

```
CdkExampleStack-Dev/Messaging/SnsTopic/Resource    → group "Messaging"
CdkExampleStack-Dev/Messaging/KinesisStream/Resource → group "Messaging"
CdkExampleStack-Dev/Database/DbCluster/Resource    → group "Database"
```

Extract the group from the second path segment:

```bash
jq '[.resources[] | {name, group: (.resource.inputs.cdkPath // "" | split("/")[1] // "root")}] | group_by(.group)' \
  .migration/resources-baseline.json
```

Use this when consolidating into ComponentResources or splitting into files — the CDK author already decided the boundaries, and the imported program should reflect them when that's what the user wants.

### 5.2 CDK custom resources

CDK uses Lambda-backed custom resources for things CloudFormation doesn't natively support. In our discovered data they appear as `AWS::CloudFormation::CustomResource` or `Custom::*`, often with a `cdkPath` like `aws-s3/auto-delete-objects-handler`. Many have native Pulumi replacements:

| CDK handler | Pulumi replacement |
|---|---|
| `aws-certificatemanager/dns-validated-certificate-handler` | `aws.acm.Certificate` + `aws.route53.Record` + `aws.acm.CertificateValidation` |
| `aws-ec2/restrict-default-security-group-handler` | `aws.ec2.DefaultSecurityGroup` with empty ingress/egress |
| `aws-ecr/auto-delete-images-handler` | `aws.ecr.Repository` with `forceDelete: true` |
| `aws-s3/auto-delete-objects-handler` | `aws.s3.Bucket` with `forceDestroy: true` |
| `aws-s3/notifications-resource-handler` | `aws.s3.BucketNotification` |
| `aws-logs/log-retention-handler` | `aws.cloudwatch.LogGroup` with `retentionInDays` |
| `aws-iam/oidc-handler` | `aws.iam.OpenIdConnectProvider` |
| `aws-route53/delete-existing-record-set-handler` | `aws.route53.Record` with `allowOverwrite: true` |
| `aws-dynamodb/replica-handler` | `aws.dynamodb.TableReplica` |
| `aws-cloudfront/edge-function` | `aws.lambda.Function` with `region: "us-east-1"` |

**For unknown handlers:** surface to the user with a note describing what the handler does. Don't annotate `Migrated` without user confirmation — the custom resource may be doing something important. If the user wants the same behaviour, recommend the equivalent native resource and add it to the Pulumi program directly.

**When the handler Lambda itself is deleted** (common for old stacks): the custom resource is dangling. Annotate `statusOverride=Migrated` with a note.

---

## 6. Common AWS diff patterns

The generic removed/added/changed diagnostic workflow is in SKILL.md Phase 6. Below are AWS-specific patterns:

- **Deprecated fields** — the classic provider sometimes generates deprecated property names (e.g. `is_enabled` instead of `state` on EventRule). Replace with the current equivalent.
- **Missing optional blocks** — some resources import without sub-blocks that the provider expects (e.g. `destination_config` on event source mappings). Add the block with values from `aws describe-*`, or remove if truly optional.
- **Provider-computed defaults** — fields like `recoveryWindowInDays`, `confirmationTimeoutInMinutes`, `forceOverwriteReplicaSecret` often differ between the provider default and the cloud value. Set explicitly in code, or `ignoreChanges` if genuinely provider-managed.
- **Value range mismatches** — CF metadata can carry values outside the classic provider's accepted range. Verify against the actual resource state with `aws describe-*` and use the real value.

---

## 7. CF types with multiple Pulumi mappings

A single CF type sometimes maps to several valid Pulumi classic types. Our discovery service picks a **primary** mapping, but it can be wrong for your specific resource. When `pulumi import` fails with a schema mismatch for a NotFound resource, consult this table before giving up — the alternative is often the right answer.

| CF type | Primary (what the API returns) | Alternative | When to use the alternative |
|---|---|---|---|
| `AWS::EC2::VPCGatewayAttachment` | `aws:ec2/internetGatewayAttachment:InternetGatewayAttachment` | `aws:ec2/vpnGatewayAttachment:VpnGatewayAttachment` | attachment is a virtual private gateway (VGW) |
| `AWS::EC2::VPCCidrBlock` | `aws:ec2/vpcIpv4CidrBlockAssociation:VpcIpv4CidrBlockAssociation` | `aws:ec2/vpcIpv6CidrBlockAssociation:VpcIpv6CidrBlockAssociation` | the associated block is IPv6 |
| `AWS::RDS::DBInstance` | `aws:rds/instance:Instance` | `aws:rds/clusterInstance:ClusterInstance` | instance is a member of an Aurora cluster (writer/reader) |
| `AWS::S3::Bucket` | `aws:s3/bucket:Bucket` | `aws:s3control/bucket:Bucket`, or any `aws:s3/bucket<Aspect>` resource | S3 on Outposts; or managing a single facet (ACL, CORS, lifecycle, logging, notification, versioning, website, replication, SSE, etc.) separately |
| `AWS::S3::BucketPolicy` | `aws:s3/bucketPolicy:BucketPolicy` | `aws:s3control/bucketPolicy:BucketPolicy` | S3 on Outposts bucket policy |
| `AWS::SES::ConfigurationSet` | `aws:sesv2/configurationSet:ConfigurationSet` | `aws:ses/configurationSet:ConfigurationSet` | existing code base uses SES v1 (legacy) |
| `AWS::SES::EmailIdentity` | `aws:sesv2/emailIdentity:EmailIdentity` | `aws:ses/emailIdentity:EmailIdentity` | existing code base uses SES v1 (legacy) |
| `AWS::APS::Workspace` | `aws:amp/workspace:Workspace` | `aws:amp/workspaceConfiguration:WorkspaceConfiguration` | managing per-workspace logging/labels as a separate resource |
| `AWS::ElasticLoadBalancingV2::*` | `aws:lb/*` | `aws:alb/*` | `alb` is an alias of `lb` with identical behavior — only relevant when matching an existing code base |

**Troubleshooting flow:** when a NotFound import fails with a schema mismatch or produces unexpected diffs:

1. Look up the resource's `originType` in this table.
2. If an alternative matches your scenario, override `providerType` in `import.json` and retry.
3. A corrected mapping will appear as `PulumiOnly` on the next `compareTo`. Annotate the original NotFound as `statusOverride=Migrated` with `linkedResourceUrn` pointing to the PulumiOnly URN (see SKILL.md Phase 5).

---

## 8. Reading a CF template (refactor phase only)

After Phase 6 (zero-diff achieved, PR created), if the user wants the imported program to *look* like the original CF/CDK code (component grouping, parameterization, references), the template is the reference. **This is optional polish, not part of the migration itself.**

### CF intrinsic functions → Pulumi equivalents

| CloudFormation | Pulumi |
|---|---|
| `!Ref <resource>` | resource output (e.g. `bucket.id`) |
| `!Ref <param>` | Pulumi config (`config.require(...)`) |
| `!GetAtt <resource>.<attr>` | resource property (e.g. `bucket.arn`) |
| `!Sub "...${X}..."` | `pulumi.interpolate\`...${x}...\`` |
| `!Join [delim, [...]]` | template literal or `.apply(parts => parts.join(delim))` |
| `!If [cond, true, false]` | `cond ? a : b` |
| `!Equals [a, b]` | `a === b` |
| `!Select [idx, list]` | `list.apply(l => l[idx])` |
| `!Split [delim, str]` | `str.apply(s => s.split(delim))` |
| `Fn::ImportValue` | stack reference or config |

### CF Parameters → Pulumi config

```ts
// CF: "Parameters": {"InstanceType": {"Type": "String", "Default": "t3.micro"}}
const config = new pulumi.Config();
const instanceType = config.get("instanceType") || "t3.micro";
```

### CF Mappings → TS objects

```ts
const regionMap: Record<string, {ami: string}> = {
  "us-east-1": {ami: "ami-12345"},
  "us-west-2": {ami: "ami-67890"},
};
const ami = regionMap[aws.config.region!].ami;
```

### CF Conditions → TS conditionals

```ts
const createProdResources = environment === "prod";
if (createProdResources) {
  // ...
}
```

**Important:** the goal of the refactor phase is to make the program more maintainable, not to reproduce the template literally. Don't refactor away from a clean zero-diff state without re-validating with `pulumi preview` after each change.

---

## 9. Further reading

- [Pulumi AWS provider](https://www.pulumi.com/registry/packages/aws/)
- [Pulumi AWS Native provider](https://www.pulumi.com/registry/packages/aws-native/)
- [Migrating to Pulumi from AWS](https://www.pulumi.com/docs/iac/adopting-pulumi/migrating-to-pulumi/from-aws/)
- [Finding AWS import IDs](https://www.pulumi.com/docs/iac/guides/migration/aws-import-ids/)

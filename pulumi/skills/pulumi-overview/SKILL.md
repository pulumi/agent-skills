---
name: pulumi-overview
description: Use this skill for any task that creates, modifies, inspects, or destroys cloud infrastructure or SaaS configuration, from one-off CLI operations to full multi-resource projects, across providers in the Pulumi ecosystem. A typical project spans many providers (AWS or Azure or GCP, Kubernetes, Cloudflare, Auth0, Datadog, Vercel, and others), and Pulumi drives them through one CLI, one state model, and one credential layer. Trigger even when the user does not name Pulumi; phrasings like "deploy this app," "provision a database," "stand up a VPC," "configure Auth0," "set up Datadog monitoring," or "tear down staging" qualify. Also trigger for tasks that migrate, port, or convert existing infrastructure code (Terraform, CloudFormation, CDK, Bicep, ARM) to Pulumi. Do not trigger for application runtime code that reads or writes data via cloud SDKs; that is application code, not infrastructure.
---

# Pulumi

Pulumi is a tool for creating and managing cloud infrastructure: virtual machines, storage, Kubernetes clusters, databases, anything from any provider. You write code or run CLI commands, Pulumi previews what would change, then applies it. This skill walks three levels of working with Pulumi, from a single CLI command up to a project with policies and scheduled drift. Start at the smallest level that fits the task.

## The three levels

Level 1 is `pulumi do`, a CLI for direct CRUD against any provider, with no project files or programming language. Level 2 is a Pulumi project in Python, TypeScript, Go, C#, or Java, used once the work involves multiple related resources, loops or conditionals, reusable abstractions, or environment-specific variants. Level 3 layers Pulumi Cloud onto a project for ESC credentials and configuration, policy, hosted execution, drift detection, schedules, and audit.

| Level | Surface | When to use |
|-------|---------|-------------|
| 1 | `pulumi do` | Single resource or multi-vendor bootstrapping |
| 2 | Pulumi project (Python, TS, Go, C#, Java) | Multiple resources, abstractions, environments |
| 3 | ESC, policy, deployments, drift, schedules | Governance, secrets, scheduled and hosted runs |

When the directory has no existing Pulumi project, a user asking to create a single bucket is a Level 1 task; do not scaffold a new project for it. A request to provision a VPC with subnets and a Kubernetes cluster is Level 2 from the start. A request for nightly drift detection on an existing stack is Level 3.

Converting existing infrastructure code from another tool (Terraform, CloudFormation, CDK, ARM, or Bicep) is a separate path: route straight to the migration skills listed in the table at the end, independent of the level model.

Picking the right level requires knowing what is already in the directory. If you can inspect the filesystem, do so. If you cannot (restricted agent contexts), ask the user before any Pulumi command runs whether there is an existing Pulumi project in the directory. Don't run a Pulumi command to find out: commands that would otherwise require a login silently provision a new agent account, parallel to one the user may already own.

---

## Level 1: `pulumi do` for direct resource operations

Use `pulumi do` for one-shot resource operations against any provider. Examples: create a Cloudflare DNS record, create an S3 bucket for backups, create a GCP storage bucket for image uploads, stand up an Azure virtual machine, configure a Datadog monitor, register a Vercel deployment's domain in Cloudflare DNS. There is no project file, directory layout, or programming language involved.

`pulumi do` is stateless. Each command runs once and operates directly against the cloud provider: `create` provisions a resource and prints its cloud-side identifier, while `read`, `patch`, and `delete` act on a resource addressed by that identifier. Nothing is written to a Pulumi state file, so there is no resource graph and no `${...}` wiring between commands. To connect two resources, capture an output from one command and pass it as a literal value to the next.

When a Pulumi project (`Pulumi.yaml`) already exists in the directory, do not use `pulumi do` to mutate resources the project manages. Changes go through the program instead.

### First invocation and signup

The canonical invocation is `npx pulumi <command>`. It works on any machine with Node.js installed and requires no prior Pulumi setup. If `pulumi` is on PATH, the `npx` shim defers to it; otherwise the command runs from the npm registry. To confirm the CLI is available before any command that would trigger signup, run `npx pulumi version`; it does not touch Pulumi Cloud. The resource verbs (`create`, `read`, `patch`, `delete`, `list`) require CLI v3.243.0 or newer, where `pulumi do` gained resource support. `npx pulumi` fetches a current release, but a `pulumi` already on PATH may be older, so confirm the version is recent.

`pulumi do` writes no Pulumi state, but it resolves provider packages through the Pulumi registry, which can reach Pulumi Cloud. In an agent context without saved credentials, that means a first `pulumi do` may silently provision an ephemeral agent account and print a claim banner.

The CLI prints one line to stderr noting the new account and a claim URL. Surface that claim URL to the user immediately and again in the final response, since it is the only way the user takes ownership of the account; a session that ends without it leaves resources stranded in the cloud. The access token expires in 3 days and the claim URL stays valid for 30 days; Pulumi Cloud sets both, so surface whatever validity the banner reports.

If the account-creation banner appears more than once in the same session, credentials may not have been cached. Agent credentials are written to `/tmp/.pulumi/credentials.json` and the claim metadata to `/tmp/.pulumi/agent-claim.json`, but the claim URL itself is printed in the banner, not stored in those files. Capture it from each banner and surface the most recent one before doing more work.

If authentication fails, ask the user to run `pulumi login`. Never fall back to `pulumi login --local` or set `PULUMI_CONFIG_PASSPHRASE`; both silently change the user's setup.

Provider credentials are separate from Pulumi Cloud credentials. `pulumi do` reads them from the same environment variables the provider's native CLI uses (`AWS_PROFILE`, `CLOUDFLARE_API_TOKEN`, `GOOGLE_APPLICATION_CREDENTIALS`). If they aren't set, ask the user before invoking commands that call out to the cloud. If a command fails with a provider authorization error, look up that provider's required credentials or configuration and have the user supply them rather than guessing at the cause. ESC (Level 3) is the durable place to keep them once a project exists.

### Command shape

Here are two invocations: create an S3 bucket, then read it back by the cloud id the create printed.

```bash
npx pulumi do aws:s3:Bucket create --yes --bucket my-data
npx pulumi do aws:s3:Bucket read my-data
```

The shape is:

```text
pulumi do <pkg:mod:type> create [flags]
pulumi do <pkg:mod:type> read|patch|delete <id> [flags]
pulumi do <pkg:mod:type> list [flags]
```

- `<pkg>` is the provider package (`aws`, `azure-native`, `gcp`, `cloudflare`, `kubernetes`, etc.).
- `<mod>` is the module within the package (`compute`, `storage`, `dns`); optional when the module is `index`. For example, `cloudflare:index/record:Record` invokes as `cloudflare:Record`.
- `<type>` is the resource type (`VirtualMachine`, `Bucket`, `Record`).
- `<id>` is the cloud provider's identifier for an existing resource, the value `create` prints as `id`. `create` and `list` take no positional argument; `read`, `patch`, and `delete` each take exactly one `<id>`.
- `[flags]` set resource properties, or you pass a body file via `--input-file <file>`. See Property input below for how flags and files combine, and which values must come from a file.

There is no Pulumi logical name to choose. The CLI derives an internal name from the resource type, and you address existing resources by their cloud id.

### Verbs

- `create` provisions the resource and prints its properties, including the cloud `id`, as JSON. Capture that `id` to read, patch, or delete the resource later. Pass `--yes` in non-interactive contexts; `read` and `list` never need it.
- `read <id>` fetches the resource's current state from the provider and prints it as JSON. It writes nothing.
- `patch <id>` reads the resource's current inputs, overlays the top-level properties you pass as flags or in `--input-file`, and updates the resource in place. The overlay is shallow: properties you do not mention are left as they are. `patch` only updates; it cannot replace a resource, so a change that would require replacement fails rather than recreating it. The command makes you confirm by typing the resource id; pass `--yes` to skip that prompt in non-interactive contexts.
- `delete <id>` removes the resource from the cloud. This is irreversible. Get explicit user confirmation for the specific resource before invoking; use `--yes` only after that confirmation, not as a default for non-interactive runs.

`pulumi do` also supports two non-CRUD operations. `pulumi do <pkg:mod:type> list [flags]` enumerates existing instances of a resource type, but only for types that implement listing. Native providers support it broadly. The Terraform-bridged providers (`aws`, `azure`, `gcp`) support it too, but coverage varies by resource type, so a type that lacks it rejects the verb. `pulumi do <pkg:mod:function> [flags]` invokes a stateless function the provider exposes alongside its resources.

### Property input

Properties come from per-property flags, a body file, or both; flags overlay the body. Flags set top-level scalar properties only, so nested or structured values (`tags`, nested blocks) must come from the body file. The body defaults to PCL, written as flat `name = value` attributes; pass `--input yaml` (which needs the YAML converter plugin) to use YAML instead.

```bash
cat > bucket.pcl <<'EOF'
bucket = "my-data"
tags = {
  Environment = "dev"
}
EOF
npx pulumi do aws:s3:Bucket create --yes --input-file bucket.pcl
```

Before authoring properties for a resource new to this session, run `npx pulumi package info <pkg> --module <mod> --resource <Type>` to list its inputs and outputs with descriptions, scoped to that one resource. Reach for `npx pulumi package get-schema <pkg>` only when you need the full machine-readable schema with the nested type definitions `info` does not expand; for a large provider it runs to tens of MB, so do not read it whole. Property names are camelCase (flags are the kebab-case form). To discover names, run `npx pulumi package info <pkg>` with no module to list its modules and resources, or browse the catalog at https://www.pulumi.com/registry/.

### Connecting resources

`pulumi do` keeps no state and has no resource graph, so there is no `${...}` reference syntax between commands. To feed one resource's output into another, read a field from the first command's JSON output and pass it as a literal flag to the next.

```bash
# create prints JSON containing "id": "vpc-0abc123"
npx pulumi do aws:ec2:Vpc create --yes --cidr-block 10.0.0.0/16

# pass that id to the subnet
npx pulumi do aws:ec2:Subnet create --yes --vpc-id vpc-0abc123 --cidr-block 10.0.1.0/24
```

The same pattern connects resources across providers. Here a value from the `random` provider feeds an AWS resource name, a common way to get globally-unique names.

```bash
# RandomPet prints JSON containing "id": "artistic-bull"
npx pulumi do random:RandomPet create --yes

# use it in the bucket name
npx pulumi do aws:s3:Bucket create --yes --bucket assets-artistic-bull
```

When a command needs a value the chain does not produce, like an existing resource id or an API zone id, get it from a provider function, a `list` where the provider supports it, or the user. Do not invent it.

### Output

By default, `create`, `read`, and `patch` each write one JSON object to stdout for the affected resource. Check the exit code on every invocation.

```json
{
  "id":     "my-data",
  "bucket": "my-data",
  "arn":    "arn:aws:s3:::my-data"
}
```

The resource's properties are top-level, alongside an `id` field holding the cloud identifier. There is no nested `outputs` object, no `urn`, and the type token you passed in is not echoed back. `list` instead writes a JSON array of `{id, name}` entries, and a function writes its declared result shape.

### Graduating to Level 2

Eject to Level 2 when one-shot commands stop fitting. Because `pulumi do` leaves no Pulumi state behind, the resources it created are ordinary cloud resources, so you adopt them into a project with `pulumi import`. From inside a Pulumi project, run `pulumi import` with each resource's full type token, a logical name, and the cloud `id` that `create` returned. Import records the resource in the stack's state and, by default, generates its program code.

```bash
# the import type token is the full pkg:mod/type:Type form, not pulumi do's short aws:s3:Bucket
npx pulumi import aws:s3/bucket:Bucket assets my-data
```

Move the generated code into your program, then manage the resource there instead of with `pulumi do`. To adopt several at once, pass them in a bulk `--file`.

---

## Level 2: full infrastructure as code

Level 2 is a Pulumi project: code in Python, TypeScript, Go, C#, or Java that describes a set of related resources and their dependencies. Start here when the task involves multiple related resources, loops or conditionals, reusable abstractions, or environment-specific variants. It is also the right level when ad-hoc work at Level 1 has grown past what a few CLI invocations should carry. Match the user's existing codebase language when one is present; default to TypeScript otherwise.

Before writing any non-trivial program, use skill `pulumi-best-practices`, which covers `Output<T>` and `apply()` usage, passing outputs directly as inputs, component structure and parenting, secrets hygiene, and safe refactoring with `aliases`.

### Bootstrapping

The quickest way to start a project is with a template, though you can scaffold one by hand if you prefer:

```bash
npx pulumi new aws-typescript
npx pulumi new gcp-go
```

Templates set up the working directory, `Pulumi.yaml`, an initial stack, the language's package manifest, and a starter program. Browse the full catalog with `npx pulumi template list`, or filter by name with `npx pulumi template list --name <filter>`.

### Core lifecycle

The lifecycle commands work the same across languages:

```bash
npx pulumi preview      # show what would change
npx pulumi up           # apply
npx pulumi refresh      # reconcile state with cloud reality
```

Always run `preview` before `up`; it shows what will change and costs nothing.

`pulumi destroy` tears down every resource in the stack. The Pulumi docs call it "generally irreversible"; never invoke without explicit user confirmation of the stack name.

### Stacks and config

A stack is an isolated instance of a project. A common pattern is one stack per environment, named `dev`, `staging`, and `prod`.

```bash
npx pulumi stack init dev
npx pulumi stack select prod

npx pulumi config set aws:region us-west-2
npx pulumi config set --secret dbPassword "..."
```

Read configuration values from inside the program with the SDK's `Config` object; the exact operation names vary by language, so refer to the per-language examples at https://www.pulumi.com/docs/iac/concepts/config/#code. Use skill `pulumi-best-practices` for `Output<T>` / `apply()` usage and broader secrets hygiene.

A stack only touches resources tracked in its state, so removing a resource from your program causes `pulumi up` to delete it from the cloud. Set `protect: true` on anything you cannot afford to lose.

For the full IaC reference, see https://www.pulumi.com/docs/iac/.

---

## Level 3: governance and operations

Level 3 uses Pulumi Cloud for more than state. ESC holds the credentials for every provider a project touches and brokers them into runs and shells. Policy enforcement, hosted execution, drift detection, scheduled operations, and audit round out the surface.

### ESC: environments, secrets, configuration

An ESC environment composes secrets and configuration from cloud secret managers, OIDC-vended credentials, and other ESC environments into a single resolved bundle that programs and stacks consume.

```bash
npx pulumi env init my_org/aws/prod
npx pulumi env set my_org/aws/prod aws.region us-west-2
npx pulumi env open my_org/aws/prod
npx pulumi env run my_org/aws/prod -- aws s3 ls
```

**Where the provider supports it, vend cloud credentials through OIDC rather than static keys in environment YAML.** OIDC trust policies, IdP registration, and rotation patterns live in `pulumi-esc`; use skill `pulumi-esc` rather than invent ESC YAML by hand.

`env open` resolves and prints live credentials, so avoid capturing its output into logs or transcripts. Prefer `env run -- <command>`, which injects the credentials into the child process rather than printing them.

### Policy

Pulumi Policies runs policy packs against the resource graph at preview and update time. A policy can reject the deployment, require approval, or annotate resources with findings; enforcement happens before any cloud API call.

```bash
npx pulumi policy new aws-typescript          # scaffold a pack from a policy template
npx pulumi policy publish my_org              # the pack name comes from PulumiPolicy.yaml
npx pulumi policy enable my_org/<pack-name> latest --policy-group production
```

Policies are written in TypeScript or Python, the same languages you use for programs.

### Deployments

Pulumi Deployments runs `pulumi up`, `preview`, and `destroy` in Pulumi-managed infrastructure rather than on the local machine. Use it for CI without maintaining your own runners and for any operation that needs to run server-side.

```bash
npx pulumi deployment run update --stack my_org/proj/prod
```

The target stack must already exist; a wrong `--stack` value can prompt to create a new stack rather than fail.

### Drift detection and scheduled operations

Drift detection compares stack state against the cloud and reports anything that has diverged. For an ad-hoc local check, run a refresh in preview-only mode. Pulumi Cloud schedules operations on a cron (times are UTC), including a purpose-built drift kind.

```bash
# Ad-hoc local drift check
npx pulumi refresh --preview-only

# Scheduled drift detection (detection only)
npx pulumi stack schedule new --kind drift --cron "0 0 * * *"

# Scheduled secret rotation for an ESC environment
npx pulumi env schedule new my_org/aws/prod --cron "0 0 1 * *"
```

A schedule is standing automation that keeps running after the session ends, so confirm the operation, cadence, and stack with the user before creating one. Two kinds act without a human in the loop: `--kind drift --auto-remediate` runs `pulumi up` on detected drift, and `--kind ttl` destroys the stack at a set time. Default to detection-only unless the user asks for remediation.

### Further reading

- ESC: https://www.pulumi.com/docs/esc/
- Pulumi Policies: https://www.pulumi.com/docs/insights/policy/
- Deployments: https://www.pulumi.com/docs/pulumi-cloud/deployments/
- Drift detection: https://www.pulumi.com/docs/pulumi-cloud/deployments/drift/

---

## Reference

When you are uncertain about a CLI flag, command shape, or resource property, look it up rather than guess. `npx pulumi <command> --help` documents every flag and subcommand from the CLI itself. The full reference, provider catalog, and conceptual documentation live at https://www.pulumi.com/docs.

---

## Routing to specialized skills

When the work moves into territory another skill covers in depth, hand off to that skill rather than reinvent its content.

| Skill | Load when |
|---|---|
| `pulumi-best-practices` | Writing any non-trivial Level 2 program |
| `pulumi-component` | Packaging or consuming `ComponentResource` abstractions |
| `pulumi-esc` | Defining ESC environments, OIDC trust policies, or rotation |
| `pulumi-automation-api` | Embedding Pulumi inside another program (IDP, custom CI) |
| `provider-upgrade` | Upgrading a provider package version in a stack without unintended changes |
| `package-usage` | Auditing which stacks across the org use a package and at what versions |
| `pulumi-terraform-to-pulumi`, `pulumi-cdk-to-pulumi`, `cloudformation-to-pulumi`, `pulumi-arm-to-pulumi` | Migrating from those tools |

An agent only sees the skills the user installed, so a referenced skill may not be present. `pulumi-best-practices`, `pulumi-component`, `pulumi-esc`, `pulumi-automation-api`, `provider-upgrade`, and `package-usage` ship in the same `pulumi` plugin as this skill, so they are available whenever this one is. The migration skills install separately through the `pulumi-migration` plugin and may be absent. When a referenced skill is available, load it. When it is not, do not stall or treat the gap as an error: continue with the guidance in this skill and the docs at https://www.pulumi.com/docs, and tell the user which skill or plugin covers the work in depth.

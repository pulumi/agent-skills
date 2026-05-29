---
name: pulumi-overview
description: Use this skill for any task that creates, modifies, inspects, or destroys cloud infrastructure or SaaS configuration — from one-off CLI operations to full multi-resource projects — across providers in the Pulumi ecosystem. A typical project spans many providers (AWS or Azure or GCP, Kubernetes, Cloudflare, Auth0, Datadog, Vercel, and others), and Pulumi drives them through one CLI, one state model, and one credential layer. Trigger even when the user does not name Pulumi; phrasings like "deploy this app," "provision a database," "stand up a VPC," "configure Auth0," "set up Datadog monitoring," or "tear down staging" qualify. Also trigger for tasks that migrate, port, or convert existing infrastructure code (Terraform, CloudFormation, CDK, Bicep, ARM) to Pulumi. Do not trigger for application runtime code that reads or writes data via cloud SDKs; that is application code, not infrastructure.
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

Picking the right level requires knowing what is already in the directory. If you can inspect the filesystem, do so. If you cannot (restricted agent contexts), ask the user before any Pulumi command runs whether there is an existing Pulumi project in the directory. Don't run a Pulumi command to find out: commands that would otherwise require a login silently provision a new agent account, parallel to one the user may already own.

---

## Level 1: `pulumi do` for direct resource operations

Use `pulumi do` for ad-hoc resource operations. Examples: create a Cloudflare DNS record, create an S3 bucket for backups, create a GCP storage bucket for image uploads, stand up an Azure virtual machine, configure a Datadog monitor, register a Vercel deployment's domain in Cloudflare DNS. State persists automatically; no project file or directory layout to set up.

When a Pulumi project (`Pulumi.yaml`) already exists in the directory, do not use `pulumi do` to mutate resources the project manages. Changes go through the program instead.

### First invocation and signup

The canonical invocation is `npx pulumi <command>`. It works on any machine with Node.js installed and requires no prior Pulumi setup. If `pulumi` is on PATH, the `npx` shim defers to it; otherwise the command runs from the npm registry. To confirm the CLI is available before any command that would trigger signup, run `npx pulumi version`; it does not touch Pulumi Cloud.

The first command that touches Pulumi Cloud silently provisions an ephemeral agent account there, making Pulumi Cloud the state backend for the rest of the session. This happens any time a command would otherwise prompt a human to log in: `pulumi stack init`, `pulumi up`, `pulumi do <pkg> <type> create`, anything in that family.

The CLI prints one line to stderr noting the new account and a claim URL. Surface that claim URL to the user immediately and again in the final response, since it is the only way the user takes ownership of the account; a session that ends without it leaves resources stranded in the cloud. The access token expires in 3 days; the claim URL stays valid for 30 days.

If the account-creation banner appears more than once in the same session, credentials may not have been cached at `~/.pulumi/credentials.json`. Inspect the file; if it does not contain the URL from the first banner, surface the URL from the second banner before doing more work.

When credentials already exist, default to whatever backend they point at; for accounts created via silent signup, that is Pulumi Cloud. If authentication fails, ask the user to run `pulumi login`. Never fall back to `pulumi login --local` or set `PULUMI_CONFIG_PASSPHRASE`; both silently change the user's setup.

Provider credentials are separate from Pulumi Cloud credentials. `pulumi do` reads them from the same environment variables the provider's native CLI uses (`AWS_PROFILE`, `CLOUDFLARE_API_TOKEN`, `GOOGLE_APPLICATION_CREDENTIALS`). If those aren't set, ask the user before invoking commands that call out to the cloud. ESC (Level 3) is the durable answer once a project exists.

### Command shape

Here is a complete invocation, creating an S3 bucket:

```bash
npx pulumi do aws s3 Bucket create my_bucket --bucket my-data --tags.Environment dev
```

The shape is:

```text
pulumi do <pkg> [<mod>] <type> <verb> <name> [args]
```

- `<pkg>` is the provider package (`aws`, `azure-native`, `gcp`, `cloudflare`, `kubernetes`, etc.).
- `<mod>` is the module within the package (`compute`, `storage`, `dns`); optional when the type has no module segment, or when the module is `index`. For example, `cloudflare:index/record:Record` invokes as `cloudflare Record`.
- `<type>` is the resource type (`VirtualMachine`, `Bucket`, `Record`).
- `<verb>` is `create`, `read`, `patch`, or `delete`.
- `<name>` is the Pulumi logical name for the resource within the stack. Use an identifier with alphanumeric characters and underscores (`my_bucket`, not `my-bucket`).
- `[args]` are per-property flags synthesized from the provider schema, or a YAML body via `-f <file>` or stdin.

### Verbs

- `create` provisions the resource and fails if a resource with the same logical name already exists in the stack; use `patch` to modify an existing one.
- `read` has two forms. `read <name>` refreshes the named resource's outputs from the provider and updates them in the snapshot. `read --id <cloud-id>` is a contextless lookup against any cloud-side ID, returns the resource as JSON, and writes nothing to state.
- `patch` updates a resource already in stack state. The CLI merges flags and `-f` body via JSON Merge Patch (`null` deletes a property from the input); the provider may still require a replace or a prior `read <name>` to get current values. Pass `--yes` in non-interactive contexts.
- `delete` removes the resource from both state and the cloud. This is irreversible. Get explicit user confirmation for the specific resource before invoking; use `--yes` only after that confirmation, not as a default for non-interactive runs.

`pulumi do` also supports two non-CRUD operations. `pulumi do <pkg> [<mod>] <type> list [args]` enumerates existing instances of a resource type from the cloud. `pulumi do <pkg> [<mod>] <function> [args]` invokes a stateless function the provider exposes alongside its resources.

### Property input

Properties come from per-property flags, a PCL or YAML body, or both; flags overlay the body via JSON Merge Patch. When the YAML body contains `${...}` interpolations, use a quoted heredoc so the shell does not expand them.

```bash
# YAML body form (same resource as the opening example)
cat <<'EOF' | npx pulumi do aws s3 Bucket create my_bucket -f -
properties:
  bucket: my-data
  tags:
    Environment: dev
options:
  protect: true
EOF

# Mixed: YAML body plus a flag overlay
npx pulumi do aws s3 Bucket create my_bucket -f base.yaml --tags.Environment prod
```

Resource options live under `options:` in YAML or as `--option-name` flags.

Before authoring properties for a provider package new to this session, run `npx pulumi package get-schema <pkg>` once and read the resource's schema. Pulumi providers use camelCase property names, which differs from the snake_case used by some other tools. If you don't know the package name, browse the catalog at https://www.pulumi.com/registry/.

### Cross-resource references

Reference outputs of resources already in the stack as `${name.output}`. In shell, single-quote the interpolation or use a quoted heredoc with `<<'EOF'` so bash does not expand `$`. In a YAML body the value is already a string and the CLI parses the interpolation; no quoting is needed.

```bash
npx pulumi do aws ec2 Vpc create main_vpc --cidr-block 10.0.0.0/16

npx pulumi do aws ec2 Subnet create app_subnet \
  --vpc-id '${main_vpc.id}' \
  --cidr-block 10.0.1.0/24
```

Outputs from one provider flow into inputs to another, so an S3 bucket and a Cloudflare DNS record can be connected in one session.

```bash
npx pulumi do aws s3 Bucket create assets --bucket my-app-assets

npx pulumi do cloudflare Record create assets_dns \
  --zone-id <your-zone-id> \
  --name assets \
  --type CNAME \
  --content '${assets.bucketDomainName}'
```

If the referenced resource was created by another mechanism (a Pulumi program in the same stack, an imported resource) and its logical name has hyphens or other non-identifier characters, use the quoted form: `${"my-vpc".id}`.

### Output

By default, `pulumi do` writes one structured JSON record to stdout for the affected resource. Check the exit code on every invocation.

```json
{
  "urn":     "urn:pulumi:dev::do-default::aws:s3/bucket:Bucket::my_bucket",
  "id":      "my-data",
  "type":    "aws:s3/bucket:Bucket",
  "name":    "my_bucket",
  "outputs": { "arn": "arn:aws:s3:::my-data", "...": "..." }
}
```

### Graduating to Level 2

Eject to Level 2 when Level 1 stops fitting. Resources created via `pulumi do` already live in stack state; use `pulumi state move` to relocate them into a named project and continue in code.

---

## Level 2: full infrastructure as code

Level 2 is a Pulumi project: code in Python, TypeScript, Go, C#, or Java that describes a set of related resources and their dependencies. Start here when the task involves multiple related resources, loops or conditionals, reusable abstractions, or environment-specific variants. It is also the right level when ad-hoc work at Level 1 has grown past what a few CLI invocations should carry. Match the user's existing codebase language when one is present; default to TypeScript otherwise.

Before writing any non-trivial program, load the `pulumi-best-practices` skill, which covers `Output<T>` and `apply()` usage, passing outputs directly as inputs, component structure and parenting, secrets hygiene, and safe refactoring with `aliases`.

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

Read configuration values from inside the program with the SDK's `Config` object; the exact operation names vary by language, so refer to the per-language examples at https://www.pulumi.com/docs/iac/concepts/config/#code. See `pulumi-best-practices` for `Output<T>` / `apply()` usage and broader secrets hygiene.

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

**Always vend cloud credentials through OIDC, not as static keys in environment YAML.** OIDC trust policies, IdP registration, and rotation patterns live in `pulumi-esc`; load that skill rather than invent ESC YAML by hand.

### Policy

Pulumi Policies runs policy packs against the resource graph at preview and update time. A policy can reject the deployment, require approval, or annotate resources with findings; enforcement happens before any cloud API call.

```bash
npx pulumi policy new my-policy-pack
npx pulumi policy publish my_org
npx pulumi policy enable my_org/my-policy-pack latest --policy-group production
```

Policies are written in TypeScript or Python, the same languages you use for programs.

### Deployments

Pulumi Deployments runs `pulumi up`, `preview`, and `destroy` in Pulumi-managed infrastructure rather than on the local machine. Use it for CI without maintaining your own runners and for any operation that needs to run server-side.

```bash
npx pulumi deployment run update --stack my_org/proj/prod
```

### Drift detection and scheduled operations

Drift detection compares stack state against the cloud and reports anything that has diverged; the canonical mechanism is a refresh in preview-only mode. Schedules run a Pulumi operation on a cron; cron times are UTC.

```bash
npx pulumi refresh --preview-only
npx pulumi stack schedule new --operation refresh --cron "0 0 * * *"
npx pulumi env schedule new <project> <name> --action rotate --cron "0 0 1 * *"
```

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
| `pulumi-terraform-to-pulumi`, `pulumi-cdk-to-pulumi`, `cloudformation-to-pulumi`, `pulumi-arm-to-pulumi` | Migrating from those tools |

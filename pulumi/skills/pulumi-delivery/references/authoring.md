# Author and register a delivery pipeline

## 1. Discover what exists

Collect these facts before you write code. Do not ask the user for what you can read.

- **Repository and forge.** `git remote -v`. Record the forge and the `repository` form it needs:
  - GitHub `owner/repo`
  - GitLab `group/subgroup/repo` (full path)
  - Bitbucket `workspace/repo`
  - Azure DevOps `org/project/repo`
- **Default branch.** `git symbolic-ref refs/remotes/origin/HEAD`.
- **Pulumi projects.** Find every `Pulumi.yaml` (`git ls-files '*Pulumi.yaml'`). For each, record the directory, the project `name` and the stack config files (`Pulumi.<stack>.yaml`). These are the candidate target stacks.
- **Existing stacks.** `pulumi stack ls --organization <org> --project <project>` or `pulumi api ListUserStacks`. A target stack must exist before the first run.
- **An existing pipeline.** A `Pulumi.<stack>.yaml` with a `delivery:source` key belongs to a pipeline stack. Read `operating.md` to see whether it is registered.
- **Credentials.** Look for an `environment:` import in each `Pulumi.<stack>.yaml`. That ESC environment gives the update its cloud credentials. If it has none, see "Credentials" below.
- **Existing CI and Deployments.** `.github/workflows/`, `.gitlab-ci.yml`, `azure-pipelines.yml`, `bitbucket-pipelines.yml`, and Deployment settings (`pulumi api GetDeploymentSettings`). If any of these deploys Pulumi stacks, read `migrating.md`.

## 2. Agree on the design with the user

Confirm in one short message:

- The stages and their order, for example `dev` then `staging` then `prod`.
- The stacks that each stage updates.
- The gate of each stage: none, `manual()`, `approval()` with named Pulumi users or teams, or `decision()` with questions about the planned changes.
- Checks after a deploy (smoke tests) as `Job` members.
- The trigger: every push to the branch, or only pushes that change some paths.

Do not invent approver names. Use `approval()` only when the organization has the Approvals feature (Pro and Enterprise editions); otherwise use `manual()`.

Do not set an identity unless the user asks for one. Without `servicePrincipal`, Delivery generates a service principal for the pipeline (see "Identity").

## 3. Write the program

Layout (the convention; any directory works):

```
delivery/            the pipeline program
  Pulumi.yaml
  Pulumi.main.yaml   config of the pipeline stack, with delivery:source
  package.json
  tsconfig.json
  index.ts
  smoke.sh           optional job scripts
infra/               an existing project of the target stacks
```

`delivery/Pulumi.yaml`:

```yaml
name: shop-delivery
runtime: nodejs
```

`delivery/Pulumi.main.yaml` says where the program lives. `url` is the clone URL with no credentials. `branch` and `directory` are optional; `directory` is relative to the repository root.

```yaml
config:
  delivery:source:
    url: https://github.com/acme/shop
    branch: main
    directory: delivery
```

Install the SDK in `delivery/` with the package manager of the language:

| Language | Install |
| --- | --- |
| TypeScript | `npm install @pulumi/delivery` |
| Python | Add `pulumi_delivery` to `requirements.txt`, then `pulumi install` |
| Go | `go get github.com/pulumi/pulumi-delivery/sdk` |
| C# | `dotnet add package Pulumi.Delivery` |
| Java | Add the dependency `com.pulumi:delivery` to `pom.xml` |
| YAML | `pulumi package add delivery`, which writes a `packages` entry to `Pulumi.yaml` |

Commit the dependency file and its lock file (for example `package.json` and `package-lock.json`). The hosted runner runs `pulumi install` and installs the SDK from them. The CLI downloads the provider plugin when a program needs it.

If the install fails, stop after one attempt (hard rule 14 in `SKILL.md`). Write the program against the names in `schema.md`, tell the user that it is not type-checked, and leave this step to the user in step 5.

Use TypeScript unless the repository already uses another Pulumi language. In Python, the names are `pulumi_delivery`, `from_`, `StacksEntryArgs` and `SourceTriggerArgs`, and a rule is a plain `delivery.RuleArgs(kind="approval", approvers=[...])`. In Go, a rule is `delivery.RuleArgs{Kind: pulumi.String(delivery.RuleKindManual), ...}`. Read the installed SDK for other names.

### Patterns

**One stage per environment.** Use a helper when environments differ only in a few values. Build resource names from the environment name; names must be unique.

```typescript
import * as delivery from "@pulumi/delivery";

const repo = new delivery.GitHubSource("repo", {
    repository: "acme/shop",
    branch: "main",
    trigger: { paths: ["app/**", "delivery/**"] },
});
const pipeline = new delivery.Pipeline("shop");

function deploy(stage: delivery.Stage, env: string) {
    const app = new delivery.Stacks(env, {
        stage,
        stacks: { app: { stack: `shop-app/${env}`, source: repo, directory: "app" } },
    });
    new delivery.Job(`smoke-${env}`, {
        stage,
        source: repo,
        directory: "delivery",
        command: "sh smoke.sh",
        environment: { ENDPOINT: app.outputs.apply(o => String(o["app"]["endpoint"])) },
    });
}

const dev = new delivery.Stage("dev", { pipeline });
deploy(dev, "dev");
const staging = new delivery.Stage("staging", { pipeline, from: [dev] });
deploy(staging, "staging");
const prod = new delivery.Stage("prod", { pipeline, from: [staging], when: delivery.approval() });
deploy(prod, "prod");
```

Per-environment settings such as the cloud region belong in the target stack's config file (`Pulumi.<stack>.yaml`), not in the pipeline.

**Smoke test.** Put the `Job` in the same stage as the `Stacks` member whose outputs it reads. A non-zero exit fails the job and its stage. Retry inside the script:

```sh
set -eu
for attempt in 1 2 3 4 5; do
  if curl -fsS "$ENDPOINT/health" > /dev/null; then
    echo "{\"checked\": \"$ENDPOINT\"}" > "$DELIVERY_OUTPUTS"
    exit 0
  fi
  sleep 10
done
echo "Smoke test failed for $ENDPOINT" >&2
exit 1
```

**Stacks that deploy together.** Put dependent stacks in one `Stacks` group. The entries run together and read each other's new outputs through stack references. A group is one unit for dependencies and retry, and each entry uses one concurrency slot. Keep groups small.

```typescript
new delivery.Stacks("platform", {
    stage: dev,
    stacks: {
        network: { stack: "shop-network/dev", source: repo, directory: "network" },
        app: { stack: "shop-app/dev", source: repo, directory: "app" },
    },
});
```

**Combined gates.** Inside `allOf`/`anyOf`, use the `Output` forms of the rule functions:

```typescript
when: delivery.allOfOutput({
    rules: [
        delivery.approvalOutput({ approvers: ["platform-team"] }),
        delivery.manualOutput({ name: "dashboards", description: "Check the dashboards first." }),
    ],
}),
```

**Upstream and downstream pipelines.** The upstream pipeline publishes an `Artifact`; the downstream pipeline reads it with a `PipelineSource`. Both pipelines are in the same organization.

```typescript
// upstream: publish an output of a Stacks member in the same stage
const prodCluster = new delivery.Stacks("prod-cluster", {
    stage: prod,
    stacks: { cluster: { stack: "platform-cluster/prod", source: repo, directory: "cluster" } },
});
new delivery.Artifact("clusterEndpoint", { stage: prod, value: prodCluster.outputs.apply(o => o["cluster"]["endpoint"]) });

// downstream
const platform = new delivery.PipelineSource("platform", { pipeline: "platform-delivery/main", stage: "prod", trigger: true });
// use platform.artifacts["clusterEndpoint"] in config (not secret) or environment (secret)
```

**Monorepo with several pipelines.** Give each pipeline its own program directory, its own pipeline stack and a source whose `trigger.paths` cover only its own directories. Set `directory` in the `delivery:source` of each pipeline stack to the directory of its program, and register each one in its own directory.

**Custom agent in a stage.** An `Agent` member runs a custom agent of the organization once for each release and gives its answer as the `response` output. Use it only when the user names the custom agent. See `schema.md`.

### Rules for the program

- One `Pipeline` per program. Stage names are unique.
- Each member names `stage`; `Stacks` entries and `Job` name `source` and `directory`.
- `config` and `environment` values are strings. `config` holds no secrets.
- Normal code (`if`, loops, `.apply` on member outputs) decides which stages and members a run has.
- `dependsOn` orders only Delivery members. A non-Delivery resource waits for a member through a member output.
- Keep cloud resources out of the pipeline program. Put them in target stacks.
- Do not add error hooks to members. Do not derive names from `pulumi.getStack()` (it is the run stack name in a run).
- `DELIVERY_*` variables are not set outside a member. Use a fallback such as `process.env.DELIVERY_RUN ?? "manual"`.

### Identity

Every stack update and job of a run acts as the identity of the pipeline. The person who starts or approves a run does not lend the run their access.

| The `Pipeline` sets | The pipeline runs as | Access that Delivery grants |
| --- | --- | --- |
| Nothing (the default) | A service principal that Delivery generates, named `Delivery <project> <stack>` | Stack Write on the pipeline stack and on each target stack, Stack Read on each upstream pipeline stack |
| `servicePrincipal: { userId }` | A service principal of the organization, by ID or login | Stack Write on the pipeline stack only |
| `servicePrincipal: { teamName }` | A team, with the roles of the team | Write on the pipeline stack only |

- Delivery makes the grants for the generated principal when a person registers, with the permissions of that person. Where the person cannot grant access, the registration warns, and the pipeline fails at that stack until a stack admin grants it.
- Delivery never grants access to ESC environments or to stacks that a program reads with a stack reference. A person grants the identity Environment Open or Stack Read there.
- A push that adds a target stack does not grant access to it. The user registers again or grants Stack Write on the new target.
- Only `pulumi delivery register` by a person sets or changes the identity. A push that changes it fails to register.
- On the Free edition, every pipeline runs as the admin of the organization, and the program cannot set `servicePrincipal`.

### Credentials

Delivery does not use Deployment settings and does not do its own OIDC exchange. Give a member cloud credentials in one of two ways:

- An ESC environment with OIDC, imported in the target stack's config file:

  ```yaml
  # infra/Pulumi.dev.yaml
  environment:
    - aws-login/dev-sandbox
  ```

  The update runs as the identity of the pipeline. A person must give that identity Environment Open on the environment. The user's own access is not enough.
- Secret values in the member's `environment`.

A `Job` has no stack config file, so it imports no ESC environment. Give a job that calls a cloud API its credentials as secret values in `environment`. Never rely on what the runner has.

## 4. Create the stacks

Ask the user first. Then:

```sh
# each target stack, in its project directory
pulumi stack init <org>/<project>/<stack>

# the pipeline stack, in delivery/
pulumi stack init <org>/<pipeline project>/main
```

Commit the config file of the pipeline stack. The runner reads it from the repository.

## 5. Register

Registration is `pulumi delivery register` in the directory of the pipeline program, with CLI v3.277.0 or later. It stores the pipeline in Pulumi Cloud and starts no run. Run it from a clean checkout at a commit that is pushed to the tracked branch.

Register only after the user agrees: registration grants the identity of the pipeline access with the permissions of the person who registers. The program must be on the tracked branch first, so open a pull request and wait until the user merges it. Then run this in `delivery/` on an up-to-date checkout of the branch:

```sh
npm install                        # or the install step of the language
pulumi stack select <org>/<pipeline project>/main
pulumi delivery register
```

The command accepts the flags of `pulumi up`, for example `--yes`. If you cannot run it (an older CLI, or no access), give these commands to the user.

Read the output:

| Output | Meaning and next step |
| --- | --- |
| "Registered the pipeline of `<stack>`." and a link | Done. No run starts. The next push that matches a trigger starts a run, or dispatch one (`operating.md`). |
| "Wrote delivery:source (...) to `<file>`; commit it." | The stack config had no `delivery:source`, so the command detected it from the checkout. Commit and push the file. |
| A warning that names access it could not grant | The generated principal has no access to that stack. A stack admin grants it, or a person with enough access registers again. |
| A warning about the checkout or the commit | The definition comes from a tree that the next push to the tracked branch replaces. Commit, push and merge, then register again. |
| An error | Nothing registered. Read `debugging.md`. |

### Run from a checkout

A plain `pulumi up` on the pipeline stack starts a run from the checkout and waits until it ends. It needs no registration. The stack updates and jobs run in Pulumi Cloud, as the person, at the latest pushed commit of their sources. The stages, gates and approvals of the pipeline apply. A member whose inputs and source commits did not change since the last `pulumi up` does not run again. Ctrl-C stops the run: members that already run finish, and no new member starts.

This is a deployment. Do it only when the user asks to try a pipeline from a branch, and say which stacks it updates. The service refuses it for a credential that is not the user's own access token (an agent token, an OIDC token or a scoped token). A pipeline that is not registered has no triggers and cannot be dispatched.

### Change a registered pipeline

- **Push.** A push to the tracked branch updates the pipeline: Delivery registers the pushed commit, then starts the run that the push triggers. This is the normal way. Open a pull request and let the user merge it.
- **`pulumi delivery register`.** It registers the checkout at once and starts no run. Use it for the first registration, to set or change the identity, to change the repository, branch or directory in `delivery:source`, to grant the generated principal access to new target stacks, and after a pipeline stack is restored.

A run never changes the pipeline definition.

## 6. Verify

Check the registration through the API with the `/tmp/dapi` wrapper from `SKILL.md`. This works when the user registered, because you cannot see their CLI output:

```sh
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/program" \
  | jq '{registered, registering, registration, lastFailedRegistration, latestRegistration}'
```

`registered: true` means an active registration. `lastFailedRegistration` carries the `reason` and `warnings` of a failed one: read `debugging.md`. Give the user the console link. After the first run starts, read it (`operating.md`). A first run is healthy when the entry stage is admitted and its members start.

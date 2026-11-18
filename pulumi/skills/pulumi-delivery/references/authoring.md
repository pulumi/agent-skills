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
- **Credentials.** Look for an `environment:` import in each `Pulumi.<stack>.yaml`. That ESC environment gives the update its cloud credentials. If it has none, see "Credentials" below.
- **Existing CI and Deployments.** `.github/workflows/`, `.gitlab-ci.yml`, `azure-pipelines.yml`, `bitbucket-pipelines.yml`, and Deployment settings (`pulumi api GetDeploymentSettings`). If any of these deploys Pulumi stacks, read `migrating.md`.

## 2. Agree on the design with the user

Confirm in one short message:

- The stages and their order, for example `dev` then `staging` then `prod`.
- The stacks that each stage updates.
- The gate of each stage: none, `manual()`, or `approval()` with named Pulumi users or teams.
- Checks after a deploy (smoke tests) as `Job` members.
- The trigger: every push to the branch, or only pushes that change some paths.

Do not invent approver names. Use `approval()` only when the organization has the Approvals feature; otherwise use `manual()`.

## 3. Write the program

Layout (the convention; any directory works):

```
delivery/        the pipeline program
  Pulumi.yaml
  package.json
  tsconfig.json
  index.ts
  smoke.sh       optional job scripts
infra/           an existing project of the target stacks
```

`delivery/Pulumi.yaml`:

```yaml
name: shop-delivery
runtime: nodejs
```

Then add the SDK in `delivery/`, only if `pulumi version` is 3.272.0 or later:

```sh
pulumi package add delivery
npm install
```

`pulumi package add delivery` writes a `delivery` entry under `packages` in `Pulumi.yaml` (`delivery: pulumi/pulumi/delivery@<version>`) and generates the SDK. Keep that entry: the hosted runner reads it and runs `pulumi install`. Do not add `@pulumi/delivery` to `package.json` from npm by hand.

With an older CLI, do not run `pulumi package add`: older versions fail or generate a broken SDK. If the command fails for any reason, stop after one attempt (hard rule 14 in `SKILL.md`). In both cases, write the program against the names in `schema.md`, tell the user that it is not type-checked, and leave this step to the user in step 5. The version in your shell is not the version on the user's machine, so do not report it as theirs.

Use TypeScript unless the repository already uses another Pulumi language. Other languages use the SDK that `pulumi package add` generates; read its types for the names (Python `pulumi_delivery`, functions `approval`, `manual`, `all_of`, `any_of` and their `_output` forms; Go `delivery.NewStage`, rules as `delivery.RuleArgs`).

### Patterns

**One stage per environment.** Use a helper when environments differ only in a few values. Build resource names from the environment name; names must be unique.

```typescript
import * as delivery from "@pulumi/delivery";

const repo = new delivery.GitHubSource("repo", {
    repository: "acme/shop",
    branch: "main",
    trigger: { paths: ["app/**", "delivery/**"] },
});
const pipeline = new delivery.Pipeline("shop", { program: { source: repo, directory: "delivery" } });

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

**Monorepo with several pipelines.** Give each pipeline its own program directory, its own pipeline stack and a source whose `trigger.paths` cover only its own directories.

### Rules for the program

- One `Pipeline` per program. Stage names are unique.
- Each member names `stage`; `Stacks` entries and `Job` name `source` and `directory`.
- `config` and `environment` values are strings. `config` holds no secrets.
- Normal code (`if`, loops, `.apply` on member outputs) decides which stages and members a run has.
- `dependsOn` orders only Delivery members. A non-Delivery resource waits for a member through a member output.
- Do not add error hooks to members. Do not derive names from `pulumi.getStack()` (it is the run stack name).
- `DELIVERY_*` variables are not set in a manual `pulumi up`. Use a fallback such as `process.env.DELIVERY_RUN ?? "manual"`.

### Credentials

Delivery does not use Deployment settings and does not do its own OIDC exchange. Give a member cloud credentials in one of two ways:

- An ESC environment with OIDC, imported in the target stack's config file:

  ```yaml
  # infra/Pulumi.dev.yaml
  environment:
    - aws-login/dev-sandbox
  ```

  The update runs with a short-lived token that has the organization's default deployment role. That role must be allowed to open the environment.
- Secret values in the member's `environment`.

A `Job` cannot import an ESC environment. Give a job that calls a cloud API its credentials as secret values in `environment`. A job with no credentials has only what the runner has, so never rely on that.

## 4. Create the stacks

Ask the user first. Then:

```sh
# each target stack, in its project directory
pulumi stack init <org>/<project>/<stack>

# the pipeline stack, in delivery/
pulumi stack init <org>/<pipeline project>/main
```

Commit the config file of the pipeline stack if it has one. The runner reads it from the repository.

## 5. Register

Registration is `pulumi up` on the pipeline stack, with CLI v3.272.0 or later, from a checkout at the head of the source branch with no uncommitted changes.

**In Neo** you cannot run it (see the hard rules in `SKILL.md`). Open a pull request with the program. Tell the user to merge it, then to run this in `delivery/` on an up-to-date checkout of the branch:

```sh
pulumi package add delivery        # only if Pulumi.yaml has no `packages: delivery` entry yet; commit and push it
pulumi stack select <org>/<pipeline project>/main
pulumi up
```

**Elsewhere**, with the user's agreement, commit and push to the source branch, then run `pulumi up --yes` in `delivery/`.

`pulumi up` exits with code 10. Read the message:

| Message | Meaning and next step |
| --- | --- |
| "Registered. A run starts for commit abc1234 when this update finishes." | Done. Watch the run. |
| "Registered. No run starts because commit abc1234 is not the head of branch main." | Push the commit, or pull the latest commit and register again. |
| "Registered. No run starts because the checkout has uncommitted changes." | Commit and push. The push starts a run if the source has a trigger. |
| "Registered. No run starts because the update has no git commit." | Run `pulumi up` from a Git checkout. |

Any other non-zero exit code is a real failure. Read `debugging.md`.

### Change a registered pipeline

There are two ways, and users mix them up. Pick one for each change and tell the user which one you use.

- **Push.** Each run executes the program at the run's commit, so a pushed change to the pipeline program takes effect in the run that the push starts. This is the normal way, and the only way in Neo.
- **`pulumi up` on the pipeline stack.** It registers the change at once. It starts a run only from a clean checkout at the head of the branch; read the message in the table above. Use it to register a change without a run, or after a pipeline stack is restored.

Do not do both for one change: the push already starts a run with the new program.

## 6. Verify

Check the registration through the API. This works when the user registered, because you cannot see their CLI output:

```sh
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/program" \
  | jq '{registered, registering, registration, lastFailedRegistration}'
```

`registered: true` means an active registration. `lastFailedRegistration` carries the `reason` and `warnings` of a failed one: read `debugging.md`. Then read the first run (`operating.md`) and give the user the console link. A first run is healthy when the entry stage is admitted and its members start.

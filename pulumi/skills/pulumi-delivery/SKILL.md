---
name: pulumi-delivery
description: Author, register, run, operate, debug and migrate to Pulumi Delivery pipelines (delivery as code), which are Pulumi programs that use the `delivery` package to declare sources, stages, stacks, jobs and approval or manual gates. Use when the user asks to set up or change a delivery pipeline; promote releases between environments with Pulumi Delivery; register a pipeline with `pulumi delivery register`; dispatch a delivery run; continue or approve a gate; retry, cancel, roll back, redeploy, promote, pause or resume a stage; find why a delivery run or registration failed; or move GitHub Actions, other CI or Deployment settings to Pulumi Delivery. Do NOT use for a plain `pulumi up` of one stack or for Pulumi Deployments the user does not want to migrate.
---

# Pulumi Delivery

Pulumi Delivery runs a delivery pipeline as a Pulumi program. The program declares sources, stages, members and gates. Pulumi Cloud runs each release through the stages in order.

Delivery is in **public preview**. Resource inputs, API routes and behavior can change. When the installed SDK and this skill disagree, the SDK is correct: read the generated types in the installed package (for example `node_modules/@pulumi/delivery/*.d.ts`). The user documentation is at `https://www.pulumi.com/docs/delivery/`.

## Requirements

- The organization has Delivery enabled. Ask the user if you are not sure.
- Any edition of Pulumi Cloud. The Free edition has one pipeline. `approval()` gates need the Pro or Enterprise edition.
- Pulumi CLI v3.277.0 or later, for `pulumi delivery register` and for a run from a checkout. Check with `pulumi version`.
- A Pulumi Cloud backend. Delivery does not work with a file backend or self-hosted Pulumi Cloud.
- A version control integration (GitHub app, GitLab, Bitbucket or Azure DevOps) with access to every repository that a source names, including the repository of the pipeline program.

## Concepts

- **Pipeline program and pipeline stack.** The pipeline is an ordinary Pulumi program, usually in a `delivery/` directory, that declares one `Pipeline`. Its stack is the pipeline stack, for example `acme/shop-delivery/main`. The stack config key `delivery:source` says where the program lives (repository URL, branch, directory).
- **Registration.** `pulumi delivery register` on the pipeline stack stores the pipeline in Pulumi Cloud. It starts no run. After that, triggers start runs, and a push to the tracked branch updates the pipeline.
- **Run from a checkout.** A plain `pulumi up` on the pipeline stack does not register. It starts a run from the checkout and waits until the run ends. The members run in Pulumi Cloud as the person who started it.
- **Run and run stack.** A run takes one release through the stages. Each run in Pulumi Cloud has a hidden run stack `<pipeline stack>-r<run number>`. The service executes the program on it many times; each execution is a **pass**.
- **Stage.** A step of the pipeline. `from` lists the stages it waits for. `when` is its gate. A stage deploys one run at a time. A newer release replaces a run that waits at the gate or in the queue of a stage: that run ends as `superseded`. A paused stage admits no new run.
- **Member.** A resource that does work in a stage: `Stacks` (updates existing target stacks), `Job` (runs a shell command), `Artifact` (publishes a value for other pipelines), `Agent` (runs a custom agent).
- **Source and release.** A source is a repository and branch (`GitHubSource`, `GitLabSource`, `BitbucketSource`, `AzureDevOpsSource`) or another pipeline's stage (`PipelineSource`). A run locks the commit of each source. The sources form the release.
- **Trigger.** `trigger: true` or `trigger: { paths: [...] }` on a source starts a run on push. A source without `trigger` never starts a run.
- **Gate.** The `when` rule of a stage: `approval()`, `manual()`, `allOf()`, `anyOf()`.
- **Identity.** A pipeline runs as one identity, by default a service principal that Delivery generates at registration. Every stack update and job acts with the access of that identity, not with the access of the person who started the run.

## Hard rules

Follow these. Each one prevents a failure that users hit.

1. Register a pipeline with `pulumi delivery register`, never with `pulumi up`. A plain `pulumi up` on a pipeline stack starts a run, and that run deploys.
2. In Neo, you cannot register or run a pipeline. `pulumi up` is blocked in your shell, and the service refuses a run that an agent credential starts, so never use `pulumi_up` on a pipeline stack. Do not run `pulumi delivery register` either: registration sets the identity of the pipeline and grants it access with the permissions of the person who registers, so a person does it. Open a pull request and hand registration to the user (`references/authoring.md`, step 5).
3. Never run `pulumi up`, `pulumi refresh` or `pulumi destroy` on a run stack (`<pipeline stack>-r<N>`).
4. Create every target stack before the first run (`pulumi stack init <org>/<project>/<stack>`). A target cannot be a pipeline stack or a run stack.
5. Write `stack` in a `Stacks` entry and `pipeline` in a `PipelineSource` as `project/stack`, in the organization of the pipeline. The provider adds the organization, so service messages show `organization/project/stack`.
6. Put no secrets in `config`. Registration rejects them. Pass secrets in `environment`, or keep them in the target stack's config file or ESC environment.
7. Declare every source at the top level of the program, not inside an `apply`.
8. A stage reads only the outputs of its own members, its sources and its `PipelineSource`s. Never pass a member output from one stage to a member in another stage. For a value from an earlier stage, read it in the target stack's own program with a stack reference, or put the `Job` in the same stage as the member it checks.
9. Omit `trigger` to disable it. `trigger: false` is an error.
10. Do not use `http()` rules. The service rejects them at registration.
11. Do not set `PULUMI_ACCESS_TOKEN`, `PULUMI_BACKEND_URL` or any `DELIVERY_*` name in `environment`.
12. Commit and push the pipeline program, its dependency files and the config file of the pipeline stack before the pipeline is registered. A run checks out the program from the repository.
13. Delivery does not use Deployment settings. Give members cloud credentials through `environment` or an ESC environment that the target stack imports. The identity of the pipeline needs Environment Open on that environment.
14. If the SDK install fails (for example `npm install @pulumi/delivery`), stop after one attempt. Do not install it another way and do not write your own types for `@pulumi/delivery`. Write the program from `references/schema.md`, say that it is not type-checked, and leave the SDK step to the user.
15. Send `$PULUMI_ACCESS_TOKEN` only to the host in `$PULUMI_API`. Never put another host in a `curl` command that carries the token.

## Call the Delivery API

The only `pulumi delivery` command is `register`. Runs, gates and stages have no CLI command, and `pulumi api` does not resolve the Delivery routes, because they are preview routes that are not in the public API specification. Call them with `curl`.

To keep the headers in one place, write this small `curl` wrapper once in a task. The references call it as `/tmp/dapi`:

```sh
cat > /tmp/dapi <<'EOF'
#!/usr/bin/env bash
# usage: dapi METHOD PATH [JSON_BODY]
curl -sS --fail-with-body -X "$1" \
  -H "Authorization: token $PULUMI_ACCESS_TOKEN" \
  -H "Accept: application/vnd.pulumi+8" -H "Content-Type: application/json" \
  ${3:+-d "$3"} "${PULUMI_API:-https://api.pulumi.com}$2"
EOF
chmod +x /tmp/dapi
```

- `/tmp/dapi` is not a Pulumi tool. It is only this script. If the file is missing, write it again.
- The wrapper needs `bash`, `curl` and `PULUMI_ACCESS_TOKEN` in the environment. If the token is not set, ask the user to export a Pulumi access token.
- The path starts with `/api/preview/`. Put filters in the query string.
- On a 4xx or 5xx status, the wrapper prints the response body, which carries the message, and exits with a non-zero code.

## What to read

Read the reference for the job before you start it. Paths are relative to this file.

| Job | Read |
| --- | --- |
| Write a new pipeline, change one, or register it | `references/authoring.md` |
| Start a run, continue or approve a gate, retry, cancel, roll back, redeploy, promote, pause or resume | `references/operating.md` |
| A registration, run, stage, gate or member failed or is stuck | `references/debugging.md` |
| Move GitHub Actions, other CI, or Deployment settings to Delivery | `references/migrating.md`, then `references/authoring.md` |
| Exact inputs, outputs, rule functions, environment variables and limits | `references/schema.md` |

## Minimal pipeline (TypeScript)

```typescript
import * as delivery from "@pulumi/delivery";

const app = new delivery.GitHubSource("app", { repository: "acme/shop", branch: "main", trigger: true });
const pipeline = new delivery.Pipeline("shop");

const dev = new delivery.Stage("dev", { pipeline });
const prod = new delivery.Stage("prod", { pipeline, from: [dev], when: delivery.manual({ description: "Check dev first." }) });

new delivery.Stacks("dev", {
    stage: dev,
    stacks: { app: { stack: "shop-infra/dev", source: app, directory: "infra" } },
});
new delivery.Stacks("prod", {
    stage: prod,
    stacks: { app: { stack: "shop-infra/prod", source: app, directory: "infra" } },
});
```

The config file of the pipeline stack (`delivery/Pulumi.main.yaml`) names the program:

```yaml
config:
  delivery:source:
    url: https://github.com/acme/shop
    branch: main
    directory: delivery
```

## Working with the user

- Before you write a pipeline, confirm the environments, their order and the gate of each stage. Do not invent approvers: ask for Pulumi user or team names.
- Show the program and the list of stacks you will create before you create stacks, push commits or register.
- Ask before each action that deploys or stops a deployment: a run from a checkout, a dispatch, a retry, a cancel and each stage action.
- Link the user to the console: the pipeline at `https://app.pulumi.com/<org>/delivery/<project>/<stack>`, a run at `.../runs/<run number>`, the approvals inbox at `https://app.pulumi.com/<org>/delivery/approvals`.

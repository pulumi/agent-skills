---
name: pulumi-delivery
description: Author, register, run, operate, debug and migrate to Pulumi Delivery pipelines (delivery as code), which are Pulumi programs that use the `delivery` package to declare sources, stages, stacks, jobs and approval or manual gates. Use when the user asks to set up or change a delivery pipeline; promote releases between environments with Pulumi Delivery; dispatch a delivery run; continue or approve a gate; retry, cancel, roll back, redeploy or promote a stage; find why a delivery run or registration failed; or move GitHub Actions, other CI or Deployment settings to Pulumi Delivery. Do NOT use for a plain `pulumi up` of one stack or for Pulumi Deployments the user does not want to migrate.
---

# Pulumi Delivery

Pulumi Delivery runs a delivery pipeline as a Pulumi program. The program declares sources, stages, members and gates. Pulumi Cloud runs each release through the stages in order.

Delivery is in **preview**. Resource inputs, API routes and behavior can change. When the installed SDK and this skill disagree, the SDK is correct: read the generated types in the installed package (for example `node_modules/@pulumi/delivery/*.d.ts`).

## Requirements

- The organization has Delivery enabled. Ask the user if you are not sure.
- Pulumi CLI v3.272.0 or later to add the SDK and to register. Check with `pulumi version`.
- Linux or macOS. The provider has no Windows build.
- Pulumi Cloud. Delivery does not work with a file backend or self-hosted Pulumi Cloud.
- A version control integration (GitHub app, GitLab, Bitbucket or Azure DevOps) with access to every repository that a source names, including the repository of the pipeline program.

## Concepts

- **Pipeline program and pipeline stack.** The pipeline is an ordinary Pulumi program, usually in a `delivery/` directory. You register it with `pulumi up` on its pipeline stack, for example `acme/shop-delivery/main`.
- **Registration.** `pulumi up` on the pipeline stack ends with **exit code 10** and a "Registered." message. Exit code 10 is success: the members wait for a run.
- **Run and run stack.** A run takes one release through the stages. Each run has a hidden run stack `<pipeline stack>-r<run number>`. The service executes the program on it many times; each execution is a **pass**.
- **Stage.** A step of the pipeline. `from` lists the stages it waits for. `when` is its gate. A stage deploys one run at a time. A newer release replaces a run that waits at the gate or in the queue of a stage: that run ends as `superseded`.
- **Member.** A resource that does work in a stage: `Stacks` (updates existing target stacks), `Job` (runs a shell command), `Artifact` (publishes a value for other pipelines).
- **Source and release.** A source is a repository and branch (`GitHubSource`, `GitLabSource`, `BitbucketSource`, `AzureDevOpsSource`) or another pipeline's stage (`PipelineSource`). A run locks the commit of each source. The sources form the release.
- **Trigger.** `trigger: true` or `trigger: { paths: [...] }` on a source starts a run on push. A source without `trigger` never starts a run.
- **Gate.** The `when` rule of a stage: `approval()`, `manual()`, `allOf()`, `anyOf()`.

## Hard rules

Follow these. Each one prevents a failure that users hit.

1. Treat exit code 10 from `pulumi up` on a pipeline stack as success. Read the "Registered." message to learn whether a run starts.
2. In Neo, you cannot register a pipeline: `pulumi up` is blocked in your shell, and the `pulumi_up` tool starts a Pulumi Deployment, which does not register. Never use `pulumi_up` on a pipeline stack. Open a pull request and hand registration to the user (`references/authoring.md`, step 5).
3. Never run `pulumi up`, `pulumi refresh` or `pulumi destroy` on a run stack (`<pipeline stack>-r<N>`).
4. Create every target stack before the first run (`pulumi stack init <org>/<project>/<stack>`). A target cannot be a pipeline stack or a run stack.
5. Write `stack` in a `Stacks` entry and `pipeline` in a `PipelineSource` as `project/stack`, in the organization of the pipeline. The provider adds the organization, so service messages show `organization/project/stack`.
6. Put no secrets in `config`. Registration rejects them. Pass secrets in `environment`, or keep them in the target stack's config file or ESC environment.
7. Declare every source at the top level of the program, not inside an `apply`.
8. A stage reads only the outputs of its own members, its sources and its `PipelineSource`s. Never pass a member output from one stage to a member in another stage. For a value from an earlier stage, read it in the target stack's own program with a stack reference, or put the `Job` in the same stage as the member it checks.
9. Omit `trigger` to disable it. `trigger: false` is an error.
10. Do not use `http()` rules. The preview rejects them at registration.
11. Do not set `PULUMI_ACCESS_TOKEN`, `PULUMI_BACKEND_URL` or any `DELIVERY_*` name in `environment`.
12. Commit and push the pipeline program before you register it. A run checks out the program from the repository, and registration starts no run for uncommitted or unpushed code.
13. Delivery does not use Deployment settings. Give members cloud credentials through `environment` or an ESC environment that the target stack imports.
14. If `pulumi package add delivery` fails, stop after one attempt. Do not search for the package, do not install it another way and do not write your own types for `@pulumi/delivery`. Write the program from `references/schema.md`, say that it is not type-checked, and leave the SDK step to the user.
15. Send `$PULUMI_ACCESS_TOKEN` only to the host in `$PULUMI_API`. Never put another host in a `curl` command that carries the token.

## What to read

Read the reference for the job before you start it. Paths are relative to this file.

| Job | Read |
| --- | --- |
| Write a new pipeline, change one, or register it | `references/authoring.md` |
| Start a run, continue or approve a gate, retry, cancel, roll back, redeploy, promote | `references/operating.md` |
| A registration, run, stage, gate or member failed or is stuck | `references/debugging.md` |
| Move GitHub Actions, other CI, or Deployment settings to Delivery | `references/migrating.md`, then `references/authoring.md` |
| Exact inputs, outputs, rule functions, environment variables and limits | `references/schema.md` |

## Minimal pipeline (TypeScript)

```typescript
import * as delivery from "@pulumi/delivery";

const app = new delivery.GitHubSource("app", { repository: "acme/shop", branch: "main", trigger: true });
const pipeline = new delivery.Pipeline("shop", { program: { source: app, directory: "delivery" } });

const dev = new delivery.Stage("dev", { pipeline });
const prod = new delivery.Stage("prod", { pipeline, from: [dev], when: delivery.approval({ approvers: ["alice"] }) });

new delivery.Stacks("dev", {
    stage: dev,
    stacks: { app: { stack: "shop-infra/dev", source: app, directory: "infra" } },
});
new delivery.Stacks("prod", {
    stage: prod,
    stacks: { app: { stack: "shop-infra/prod", source: app, directory: "infra" } },
});
```

## Working with the user

- Before you write a pipeline, confirm the environments, their order and the gate of each stage. Do not invent approvers: ask for Pulumi user or team names.
- Show the program and the list of stacks you will create before you create stacks, push commits or register.
- Call the Delivery API with `curl` (see `references/operating.md`). There is no `pulumi delivery` command, and `pulumi api` does not resolve the Delivery routes.
- Link the user to the console: the pipeline at `https://app.pulumi.com/<org>/delivery/<project>/<stack>`, a run at `.../runs/<run number>`, the approvals inbox at `https://app.pulumi.com/<org>/delivery/approvals`.

# Delivery package reference

The `delivery` package: `@pulumi/delivery` on npm, `pulumi_delivery` on PyPI, `Pulumi.Delivery` on NuGet, `com.pulumi:delivery` on Maven and the Go module `github.com/pulumi/pulumi-delivery/sdk`. Type tokens are `delivery:index:<Name>`. `*` marks a required input. This reference matches SDK 0.2.0 of the public preview; the installed SDK is the final authority.

## Stack config

| Key | Type | Notes |
| --- | --- | --- |
| `delivery:source` | `{ url*, branch, directory }` | Where the pipeline program lives. `url` is the clone URL, with no credentials. `branch` is the tracked branch; without it, the default branch of the repository. `directory` holds the `Pulumi.yaml` of the pipeline, relative to the repository root. Set it in the config file of the pipeline stack. `pulumi delivery register` writes it from the Git checkout when it is missing. |

## Sources

### `GitHubSource`, `GitLabSource`, `BitbucketSource`, `AzureDevOpsSource`

| Input | Type | Notes |
| --- | --- | --- |
| `repository`* | string | GitHub `owner/repo`; GitLab `group/subgroup/repo`; Bitbucket `workspace/repo`; Azure DevOps `org/project/repo`. |
| `branch`* | string | Without `refs/heads/`. |
| `trigger` | `true` or `{ paths: string[] }` | Omit for a source that is part of the release but never starts a run. `false` is an error. |

Output: `commit` (unknown during registration and preview).

### `PipelineSource`

| Input | Type | Notes |
| --- | --- | --- |
| `pipeline`* | string | Upstream pipeline stack as `project/stack`, same organization. |
| `stage`* | string | Stage of the upstream pipeline. |
| `trigger` | boolean | `true` starts a run when that stage deploys a new release. |

Outputs: `artifacts` (map by name; secret as a whole if one artifact is secret), `releaseNumber`, `runNumber`. A job cannot check out a pipeline source.

## `Pipeline`

| Input | Type | Notes |
| --- | --- | --- |
| `servicePrincipal` | `{ userId }` or `{ teamName }` | The identity that the pipeline runs as. `userId` is the ID or login of a service principal of the organization. `teamName` is a team. Set one, not both. Omit it to let Delivery generate a service principal. Not available on the Free edition. |
| `runtime` | `WorkflowsRuntime` | Pool that runs the pipeline program. Omit for the hosted pool. |

Output: `releaseNumber` (unknown during registration and preview). One `Pipeline` per program. It has no `program` input: `delivery:source` in the stack config names the program.

## `Stage`

| Input | Type | Notes |
| --- | --- | --- |
| `pipeline`* | `Pipeline` | |
| `from` | `Stage[]` | Upstream stages. Omit for an entry stage. A stage with several upstream stages waits until the same release converges in all of them. |
| `when` | Rule | Gate before the release enters the stage. |

## Members

### `Stacks`

| Input | Type | Notes |
| --- | --- | --- |
| `stage`* | `Stage` | |
| `stacks`* | map of entry name to entry | Entry names: letters, digits, `_`, `-`. Each entry updates one target stack. |

Entry:

| Field | Type | Notes |
| --- | --- | --- |
| `stack`* | string | Target stack as `project/stack`. Must exist before the first run. |
| `source`* | repository source | The update uses the run's commit of this source. |
| `directory`* | string | Directory of the stack's project, from the repository root. |
| `config` | map of string | Set on the stack before the update. Plain strings only; secrets are rejected. At most 100 keys and 64 KiB. |
| `environment` | map of string | Environment variables for the update. Secrets stay secret. |
| `timeout` | string | Go duration such as `30m`, in whole seconds from `5m` to `24h`. Default `2h`. |
| `image` | `{ reference, credentials }` | Container image of the runner. Omit for the Pulumi image. See "Runner settings". |
| `preRunCommands` | list of string | Bash commands that run before the update or the command. See "Runner settings". |
| `runtime` | `WorkflowsRuntime` | Pool that runs the update. Omit for the hosted pool. |

Output: `outputs` (map of entry name to the stack's outputs; unknown until the group runs).

### `Job`

| Input | Type | Notes |
| --- | --- | --- |
| `stage`* | `Stage` | |
| `source`* | repository source | Checked out at the run's commit. |
| `directory`* | string | Working directory, from the repository root. |
| `command`* | string | Run with `sh -c`. |
| `environment` | map of string | Secrets stay secret. |
| `timeout` | string | Go duration such as `30m`, in whole seconds from `5m` to `24h`. Default `2h`. |
| `image` | `{ reference, credentials }` | Container image of the runner. Omit for the Pulumi image. See "Runner settings". |
| `preRunCommands` | list of string | Bash commands that run before the update or the command. See "Runner settings". |
| `runtime` | `WorkflowsRuntime` | Pool that runs the job. Omit for the hosted pool. |

Output: `outputs` (what the command wrote to `$DELIVERY_OUTPUTS`).

Job outputs: write one JSON object, at most 1 MiB, to the file that `DELIVERY_OUTPUTS` names. Each key is one output. `{"value": ..., "secret": true}` marks an output secret. An output that contains a secret environment value is secret too.

### Runner settings

A `Job` and each `Stacks` entry accept `image`, `preRunCommands` and `runtime`.

- `image.reference`* is the image, for example `pulumi/pulumi-nodejs:3.272.0`. Use it to pin the Pulumi CLI or a language version. The image needs `bash`, `curl`, `gzip` and the Pulumi CLI on `PATH`.
- `image.credentials` is `{ username*, password* }` for a private registry. The password is a secret.
- `preRunCommands` run in the project directory, after the dependencies are installed and before the Pulumi command or the job's command. Each command is its own step: environment changes (`export`, `cd`) do not carry over to the next command. A pre-run command cannot be a secret.
- `runtime` is a `WorkflowsRuntime` resource: `new delivery.WorkflowsRuntime("pool", { agentPool: "<pool ID>" })`.

### `Artifact`

| Input | Type | Notes |
| --- | --- | --- |
| `stage`* | `Stage` | |
| `value`* | any | Any value, including a secret or a structure. Read downstream through `PipelineSource.artifacts`. |

The artifact has the name of the resource. Artifact names are unique in a pipeline.

### `Agent`

Runs a custom agent of the organization once for each release, after the stage admits the release and the dependencies of the member are ready. Each run counts toward the Pulumi Agents usage of the organization.

| Input | Type | Notes |
| --- | --- | --- |
| `stage`* | `Stage` | |
| `agentDefinitionId`* | string | ID of the custom agent. The run uses its saved role, integrations and instructions. |
| `prompt`* | string | The one message that the agent gets for each release. It can use outputs of other members of the stage. |
| `responseSchema`* | JSON Schema object | The final answer must satisfy it. No `$ref`. |

Output: `response` (the structured answer). The person who registers must be allowed to run that agent.

## Rules (`when`)

| Function | Inputs | Notes |
| --- | --- | --- |
| `approval()` | `approvers` (users or teams), `count` (default 1), `name` | Needs the Approvals feature (Pro and Enterprise editions); registration rejects it otherwise. Empty `approvers`: anyone with `pipeline:approve` on the pipeline stack. Registration rejects names that are not users or teams of the organization. Uses change requests. |
| `manual()` | `name` (default `manual`), `description` | Waits until someone with `pipeline:approve` continues the gate. Works on every edition. |
| `decision()` | `questions`* (map of a name to `{ instructions*, maximumRisk* }`), `context`, `description`, `name` | Needs the Pro edition or higher. Delivery evaluates the previews of the stacks of the stage against each question. The gate passes when the risk of every question is at most its `maximumRisk` (0 to 1). A denied decision fails the run. The stage needs a `Stacks` member. `context` is JSON-like data for the evaluation: no secrets, at most 16 KiB. |
| `allOf()` | `rules`*, `name` | All rules pass. |
| `anyOf()` | `rules`*, `name` | One rule passes. |
| `http()` | `url`*, `successExpression`*, ... | Rejected at registration. Do not use. |

Rules nest up to three levels. Rule names are unique within a gate, so name each rule when a gate has two of the same kind. In TypeScript, `rules` takes the `Output` forms (`approvalOutput`, `manualOutput`, `decisionOutput`, `allOfOutput`, `anyOfOutput`). In Python, build a rule as `delivery.RuleArgs(kind="manual", ...)`. In Go, build a rule as `delivery.RuleArgs{Kind: pulumi.String(delivery.RuleKindManual), ...}`. The kinds are `approval`, `manual`, `decision`, `all` and `any`.

A decision gate asks narrow questions about the planned changes:

```typescript
when: delivery.decision({
    questions: {
        dataLoss: { instructions: "Does the preview delete or replace a database or a bucket?", maximumRisk: 0.05 },
    },
}),
```

SDK 0.1.0 has no `decision` function. If the installed SDK does not export it, upgrade the SDK to 0.2.0 or later.

## Environment variables in members

| Variable | Value |
| --- | --- |
| `DELIVERY_RUN` | Run number |
| `DELIVERY_RELEASE` | Release number |
| `DELIVERY_STAGE` | Stage name |
| `DELIVERY_COMMIT` | Commit of the member's source |
| `DELIVERY_PIPELINE` | Pipeline stack |
| `DELIVERY_STACK` | Target stack of a member update |
| `DELIVERY_OUTPUTS` | Path of the job outputs file (jobs) |

Reserved: `PULUMI_ACCESS_TOKEN`, `PULUMI_BACKEND_URL`, every `DELIVERY_*` name. A stack update and a job get a temporary Pulumi token that acts as the identity of the pipeline. The token cannot create tokens, approve, or cancel, retry or operate the pipeline. Do not write the run number into a value that changes a resource on every run (for example Lambda environment variables).

## Permissions on the pipeline stack

| Action | Permission |
| --- | --- |
| Start a run | `pipeline:dispatch` (with a `ref` or source pins, also `stack:write`) |
| Cancel a run | `pipeline:cancel` |
| Retry a run | `pipeline:retry` |
| Redeploy a stage | `pipeline:redeploy` |
| Roll back a stage | `pipeline:rollback` |
| Force-promote a release to a stage | `pipeline:force_promote` |
| Continue a manual gate | `pipeline:approve` |
| Pause or resume a stage | `pipeline:pause` |

No permission implies another. The Stack Write and Stack Admin roles grant all eight, and Stack Read grants none. `stack:write` in a custom role grants none of them. Approving needs a user token; organization and team tokens cannot approve.

## Limits

| Limit | Value |
| --- | --- |
| Pipelines in an organization on the Free edition | 1 |
| Members in a pipeline | 1,000 (each `Stacks` entry counts as one) |
| Stages in a pipeline | 1,000 |
| Sources in a pipeline | 100 |
| Config of a `Stacks` entry | 100 keys and 64 KiB |
| Passes in a run | 5,000, then the run fails |
| Time of a pass | 1 hour; a failed pass restarts up to 3 times in a row |
| Time of a member | 2 hours by default. `timeout` on a `Stacks` entry or a `Job` sets 5 minutes to 24 hours. |
| Job outputs | 1 MiB |
| `PipelineSource` chain | Depth 10 |
| Run stacks | Deleted 90 days after the run ends, or when the pipeline stack is deleted |

Each `Stacks` entry uses one concurrency slot. A group larger than the organization's concurrency limit blocks itself; registration warns about it.

## Known limitations of the preview

- No `CustomVCSSource`, no forges without webhooks.
- No Windows runners.
- No self-hosted Pulumi Cloud and no file backend.
- Passes get no policy packs; target stacks keep their own policy groups.
- The pipeline stack's config comes from its committed config file.
- No cycle detection between stages: such a run waits until canceled.
- No time-based triggers, no ESC triggers, and no dispatch inputs other than a key, a ref and source pins.
- The only `pulumi delivery` command is `register`. Runs, gates and stages are in the console and the API.
- A deleted run stack is not destroyed: non-Delivery resources in the pipeline program stay in the cloud without state. Keep cloud resources in target stacks, not in the pipeline program.
- A pipeline stack cannot move to another organization; a run stack cannot be renamed or moved. Deleting a pipeline stack stops the pipeline and deletes its run stacks. After a restore, a person registers the pipeline again.

# Delivery package reference

The `delivery` package (`pulumi package add delivery`). Type tokens are `delivery:index:<Name>`. `*` marks a required input. This reference matches the preview schema; the installed SDK is the final authority.

## Sources

### `GitHubSource`, `GitLabSource`, `BitbucketSource`, `AzureDevOpsSource`

| Input | Type | Notes |
| --- | --- | --- |
| `repository`* | string | GitHub `owner/repo`; GitLab `group/subgroup/repo`; Bitbucket `workspace/repo`; Azure DevOps `org/project/repo`. |
| `branch`* | string | |
| `trigger` | `true` or `{ paths: string[] }` | Omit for a source that is part of the release but never starts a run. `false` is an error. |

Output: `commit` (unknown during registration and preview).

### `PipelineSource`

| Input | Type | Notes |
| --- | --- | --- |
| `pipeline`* | string | Upstream pipeline stack as `project/stack`, same organization. |
| `stage`* | string | Stage of the upstream pipeline. |
| `trigger` | boolean | `true` starts a run when that stage deploys a new release. |

Outputs: `artifacts` (map by name; secret as a whole if one artifact is secret), `releaseNumber`, `runNumber`.

## `Pipeline`

| Input | Type | Notes |
| --- | --- | --- |
| `program`* | `{ source, directory }` | Source and directory (with `Pulumi.yaml`) of this pipeline program. |

Output: `releaseNumber` (unknown during registration and preview). One `Pipeline` per program.

## `Stage`

| Input | Type | Notes |
| --- | --- | --- |
| `pipeline`* | `Pipeline` | |
| `from` | `Stage[]` | Upstream stages. Omit for an entry stage. |
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
| `config` | map of string | Set on the stack before the update. Plain strings only; secrets are rejected. |
| `environment` | map of string | Environment variables for the update. Secrets stay secret. |
| `timeout` | integer | Seconds, from 300 (5 minutes) to 86400 (24 hours). Default 7200 (2 hours). |
| `image` | `{ reference, credentials }` | Container image of the runner. Omit for the Pulumi image. See "Runner settings". |
| `preRunCommands` | list of string | Bash commands that run before the update or the command. See "Runner settings". |
| `runtime` | `WorkflowsRuntime` | Omit. The preview runs everything on the hosted pool. |

Output: `outputs` (map of entry name to the stack's outputs; unknown until the group runs).

### `Job`

| Input | Type | Notes |
| --- | --- | --- |
| `stage`* | `Stage` | |
| `source`* | repository source | Checked out at the run's commit. |
| `directory`* | string | Working directory, from the repository root. |
| `command`* | string | Run with `sh -c`. |
| `environment` | map of string | Secrets stay secret. The job gets no Pulumi token. |
| `timeout` | string | Go duration. Not applied in the preview; a job stops after 2 hours. |
| `image` | `{ reference, credentials }` | Container image of the runner. Omit for the Pulumi image. See "Runner settings". |
| `preRunCommands` | list of string | Bash commands that run before the update or the command. See "Runner settings". |
| `runtime` | `WorkflowsRuntime` | Omit. The preview runs everything on the hosted pool. |

Output: `outputs` (what the command wrote to `$DELIVERY_OUTPUTS`).

Job outputs: write one JSON object, at most 1 MiB, to the file that `DELIVERY_OUTPUTS` names. Each key is one output. `{"value": ..., "secret": true}` marks an output secret. An output that contains a secret environment value is secret too.

### Runner settings

A `Job` and each `Stacks` entry accept `image` and `preRunCommands`.

- `image.reference`* is the image, for example `pulumi/pulumi-nodejs:3.272.0`. Use it to pin the Pulumi CLI or a language version. The image needs `bash`, `curl`, `gzip` and the Pulumi CLI on `PATH`.
- `image.credentials` is `{ username*, password* }` for a private registry. The password is a secret.
- `preRunCommands` run in the project directory, after the dependencies are installed and before the Pulumi command or the job's command. Each command is its own step: environment changes (`export`, `cd`) do not carry over to the next command.

### `Artifact`

| Input | Type | Notes |
| --- | --- | --- |
| `stage`* | `Stage` | |
| `value`* | any | Any value, including a secret or a structure. Read downstream through `PipelineSource.artifacts`. |

## Rules (`when`)

| Function | Inputs | Notes |
| --- | --- | --- |
| `approval()` | `approvers` (users or teams), `count` (default 1), `name` | Needs the Approvals feature; registration rejects it otherwise. Empty `approvers`: anyone with org update permission. Registration rejects names that are not users or teams of the organization. Uses change requests. |
| `manual()` | `name` (default `manual`), `description` | Waits until someone continues the gate. Works on every plan. |
| `allOf()` | `rules`*, `name` | All rules pass. |
| `anyOf()` | `rules`*, `name` | One rule passes. |
| `http()` | `url`*, `successExpression`*, ... | Rejected at registration in the preview. Do not use. |

Rules nest up to three levels, at most 50 conditions and 100 approvers. Rule names are unique within a gate. In TypeScript, `rules` takes the `Output` forms (`approvalOutput`, `manualOutput`, `allOfOutput`, `anyOfOutput`). In Go, build a rule as `delivery.RuleArgs{Kind: pulumi.String("manual"), ...}`.

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

Reserved: `PULUMI_ACCESS_TOKEN`, `PULUMI_BACKEND_URL`, every `DELIVERY_*` name. A `Stacks` update gets a Pulumi token for its stack; a job gets none. Do not write the run number into a value that changes a resource on every run (for example Lambda environment variables).

## Limits

| Limit | Value |
| --- | --- |
| Members in a pipeline | 1,000 (each `Stacks` entry counts as one) |
| Passes in a run | 5,000, then the run fails |
| Time of a pass | 1 hour; a failed pass restarts up to 3 times in a row |
| Time of a member | 2 hours by default. `timeout` on a `Stacks` entry sets 5 minutes to 24 hours. |
| Job outputs | 1 MiB |
| `PipelineSource` chain | Depth 10 |

Each `Stacks` entry uses one concurrency slot. A group larger than the organization's concurrency limit blocks itself; registration warns about it.

## Known limitations of the preview

- No `CustomVCSSource`, no forges without webhooks.
- Hosted runners only: no agent pools, no Windows.
- Passes get no policy packs; target stacks keep their own policy groups.
- The pipeline stack's config comes from its committed config file.
- No cycle detection between stages: such a run waits until canceled.
- No time-based triggers, ESC triggers, dispatch inputs or `pulumi delivery` command.
- A deleted run stack is not destroyed: non-Delivery resources in the pipeline program stay in the cloud without state. Keep cloud resources in target stacks, not in the pipeline program.
- A pipeline stack cannot move to another organization; a run stack cannot be renamed or moved. Deleting a pipeline stack stops the pipeline and deletes its run stacks.

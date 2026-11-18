# Debug a delivery pipeline

Find the failing layer first, then read its logs, then match the symptom below.

The commands use `/tmp/dapi`. It is not a Pulumi tool: it is the small `curl` wrapper that `SKILL.md` defines ("Call the Delivery API"). Write it before the first call. `operating.md` has the other commands.

## 1. Find the failing layer

| Layer | Where it shows | First read |
| --- | --- | --- |
| Registration | `pulumi delivery register`; the program, `.../delivery/program` (`registered`, `lastFailedRegistration.reason`, `warnings`); the list, `.../delivery/registrations` | The full CLI output, or the registration fields when the user or a push registered |
| Run | The run detail, `.../delivery/runs/<n>`: `failureReason`, `summary.status` | `currentPass`, then the members |
| Pass (one execution of the program on the run stack) | `currentPass.outcome = failed`, `currentPass.failureReason` | Pass logs |
| Member (a `Stacks` entry, `Job`, `Artifact` or `Agent`) | `members[].status`, `members[].failureReason`, `currentAttempt` | Attempt logs; for `Stacks`, the update of the target stack |
| Gate | `stages[].gate.status`, `conditions[].state` | The gate and its conditions |

A status `waiting` with a `waitKind` (`approval`, `manual`, `queue`, `stage`, `dependency`, `target`, `paused`) is a wait, not a failure.

## 2. Read the logs

```sh
# passes of a run, then the logs of one pass
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/runs/12/passes" | jq -c '.passes[] | {number, status, outcome, failureReason}'
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/runs/12/passes/3/logs" | jq -r '.lines[] | "\(.step // ""): \(.text)"' > /tmp/pass.log

# attempts of a member, then the logs of one attempt
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/runs/12/members/<member id>/attempts" | jq -c '.attempts[] | {number, status, failureReason, updateVersion}'
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/runs/12/members/<member id>/attempts/1/logs" | jq -r '.lines[].text' > /tmp/attempt.log

# registrations of a pipeline (by a person and by a push), then the log of a registration that a push made
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/registrations" | jq -c '.registrations[] | {id, state, active, source, commit, branch, dirty, message}'
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/registrations/<id>/logs" | jq -r '.lines[].text' > /tmp/registration.log
```

Logs are paginated: add `?continuationToken=<token>` from the previous page to the path. `gone: true` means the log was deleted. Write logs to a file and search it (`grep -n -i error /tmp/pass.log`); do not print a whole log.

For a failed `Stacks` member, `currentAttempt.updateId` and `updateVersion` identify the update of the target stack. Read it like any stack update (use skill `pulumi-debug-failed-operation`, or `pulumi stack history` in the target stack's project).

## 3. Match the symptom

### Registration

| Symptom | Cause | Fix |
| --- | --- | --- |
| `pulumi delivery` is an unknown command | CLI older than 3.277.0 | Upgrade the Pulumi CLI. In Neo, hand registration to the user. |
| `pulumi up` on the pipeline stack starts a run, or is refused with a message to register | A plain `pulumi up` does not register | Register with `pulumi delivery register`. |
| The service says to upgrade the Delivery provider package | The installed SDK is older than the service accepts | Update the SDK (for example `npm install @pulumi/delivery@latest`), commit the dependency files, register again. |
| The program sets `program` on the `Pipeline` and fails to compile | The `program` input was removed | Remove it. Set `delivery:source` in the config of the pipeline stack. |
| "could not detect the pipeline source from git" | No `delivery:source` in the stack config, and no Git remote that the command can read | Set `delivery:source` (`url`, optional `branch` and `directory`) in `Pulumi.<stack>.yaml`. |
| "Pulumi Cloud cannot read the repository ..." or "... cannot read branch ..." | The integration of the forge has no access to the repository, or the branch does not exist | Give the integration access to the repository, or fix `branch`. Write the branch without `refs/heads/`. |
| "No ... integration of the organization holds the repository ..." | The organization has no integration for that account, group or workspace | Ask the user to set up the version control integration. |
| A warning or an error about uncommitted changes, a commit that is not on the tracked branch, or no git commit | The registration did not come from a clean, pushed checkout of the tracked branch | Commit, push and merge, then register again from that checkout. |
| A push changed the pipeline, but the definition did not change | The registration of the push failed | Read the registrations list and the log of the failed entry. |
| A push that changes `servicePrincipal`, or the repository, branch or directory of the program, fails to register | Only a registration by a person can change them | A person runs `pulumi delivery register`. |
| A warning that the service principal has no access to a stack | The person who registered cannot grant access to that stack | A stack admin grants the principal Stack Write (a target) or Stack Read (an upstream pipeline), or a person with enough access registers again. |
| "You do not have enough permissions to run ... as this service principal" | The person does not hold every permission that the named principal or team holds | A person with that access registers, or the program names another identity. |
| The first registration of a pipeline is refused because the organization already has one | The Free edition and a single-user organization have one pipeline | Change the registered pipeline, or upgrade the edition. |
| "This organization is on the Free plan, where pipelines run as its admin. Remove servicePrincipal from the pipeline." | The Free edition has no pipeline identities | Remove `servicePrincipal`. |
| "Starting a run of this agent requires holding the agent's role, or permission to manage the organization." | The person who registers cannot run the custom agent of an `Agent` member | A person who holds the role of the agent registers, or the program names another agent. |
| A secret value in `config` is rejected | `config` takes plain strings | Move the value to `environment` or to the target stack's config or ESC environment. |
| "the rule kind ... is not one of approval, decision, manual, all, any" | An `http()` rule | Use `manual()` or `approval()`. |
| "The approver ... is not a user or a team of this organization." | An `approvers` name is wrong | Use Pulumi user logins or team names of the organization. |
| A message that says to use `delivery.manual()` or to upgrade for named approvers | The organization has no Approvals feature | Use `manual()`. |
| A dispatch returns 409 "The pipeline has no active registration." | No successful registration. A pipeline that was registered with `pulumi up` before `pulumi delivery register` existed has none. | A person runs `pulumi delivery register`. |
| The SDK install fails | Network, registry or toolchain problem | Stop after one attempt (hard rule 14). Do not write your own types. |

### Run and pass

| Symptom | Cause | Fix |
| --- | --- | --- |
| "The target stack ... does not exist. Create it first." | A `Stacks` entry names a missing stack | `pulumi stack init <org>/<project>/<stack>`, then retry the run. |
| Every pass fails in about a second with "The work could not be launched." | The forge integration cannot access the repository (common with a public repository outside the GitHub App installation) | Add the repository to the integration, then retry. |
| "This pipeline has no service principal to run as ..." or "The service principal cannot be used ..." | The pipeline has no usable identity: its service principal or team was deleted, or the organization left the Free edition | A person names another identity or removes `servicePrincipal`, then runs `pulumi delivery register`. |
| A pass fails because a source was created after the first pass | A source is declared inside an `apply` or depends on a member output | Declare every source at the top level. Push the fix; a retry does not pick it up. |
| "The step pass failed." with no detail | Generic failure line | Read the pass logs. |
| A downstream run waits or fails with "has no deployed release" | The upstream stage of a `PipelineSource` has not deployed yet | Let the upstream pipeline deploy that stage first. |
| "The service principal ... of this pipeline cannot read the pipeline ..." | The identity of the pipeline has no Stack Read on the upstream pipeline stack. The user's own access is not enough. | A stack admin of the upstream grants Stack Read, or a person with that access runs `pulumi delivery register` on this pipeline. Then retry. |
| A run has the status `superseded` | A newer release reached the gate or the queue of the stage where this run waited | Nothing to fix. Follow the newer run. To deploy the older release anyway, promote it (`operating.md`). |
| A run fails at an approval gate with no failed member | Someone rejected the approval (closed its change request) | Ask who rejected it and why. A retry asks for a new approval. |
| "The stack <name>-r<N> already exists" | A run stack name is taken | Tell the user; do not delete stacks to clear it without asking. |
| A `pulumi up` on the pipeline stack fails with "The update ended before the run finished." or "The update stopped responding." | A run from a checkout ends when its update ends | Start it again. A run from a checkout cannot be retried. |

### Member

| Symptom | Cause | Fix |
| --- | --- | --- |
| A `Stacks` update fails with an error that names the service principal (or team) and the target stack | The identity of the pipeline has no write access to the target. A push that adds a target grants nothing. | A stack admin grants Stack Write on the target, or a person runs `pulumi delivery register`. Then retry. |
| "you do not have permission to open environment '<org>/<project>/<env>'" | The identity of the pipeline cannot open the ESC environment that the target stack imports. Delivery never grants this. | A person gives the identity Environment Open on the environment, then retry. |
| Cloud authentication errors in a `Stacks` update | No credentials: Delivery ignores Deployment settings | Import an ESC environment with OIDC in the target stack config, or pass secrets in `environment`. |
| A job fails with a non-zero exit | The command failed | Read the attempt logs. Retry inside smoke scripts (`curl -fsS` with a loop). |
| Job outputs are missing | Nothing written to `$DELIVERY_OUTPUTS`, invalid JSON, or larger than 1 MiB | Write one JSON object to the file. |
| A member update was canceled and the next update fails | The stack state is out of date | Wait for the canceled update to end, then `pulumi refresh` on the target stack (ask first). |
| A `Stacks` group does not start, and the run fails after 2 hours | The group has more entries than the organization's concurrency limit (registration warns). A group with no progress for 2 hours fails. | Split the group. |
| A `Stacks` update fails on policy violations | The policy groups of the target stack apply to the update | Fix the violation in the stack's program and push, or ask the user to get a policy exception, then retry. |
| A job reaches cloud resources that you did not give it access to, or fails cloud authentication | A `Job` imports no ESC environment. With no credentials in `environment`, it has only what the runner has. | Pass the credentials the job needs as secret values in `environment`. Never rely on the runner's own identity. |
| A member runs for 2 hours and stops | Default member time limit | Raise `timeout` on the `Stacks` entry or `Job` (a Go duration from `5m` to `24h`). Otherwise split the work, or set a lower `timeout` to fail faster. |
| "The timeout of ... must be a whole number of seconds from 300 (5 minutes) to 86400 (24 hours)." | `timeout` is out of range | Write a duration from `5m` to `24h`, such as `30m`. |

### Waiting forever

| Symptom | Cause | Fix |
| --- | --- | --- |
| An approval gate never passes | No eligible person approved, or an approver left the organization after registration | Check `eligibleApprovers`, `approvals` and `requiredApprovals`; ask an eligible user to approve, or fix the names and push. |
| Two stages wait for each other | A cycle in `from`; Delivery does not detect it | Cancel the run, fix `from`, push. |
| A run waits at a stage | Another run holds the stage (`stage.lockRunNumber` in `.../delivery/stages/<name>`), or runs ahead of it in the queue (the runs list with `queued=true` and `stage`) | Let the runs ahead finish, or cancel the one that blocks. |
| A run waits at a stage with the wait kind `paused` | The stage is paused. A rollback pauses its stage. | Ask the user, then resume the stage (`operating.md`). |
| The run says "Waiting to retry" and retry is disabled | An automatic pass restart is in progress | Wait; retry becomes available only after the run fails. |

## 4. Fix and recover

1. Fix the cause. For a cause in the repository, push the fix: a **new run** picks it up, a retry does not.
2. For a cause outside the repository (a missing stack, a permission, an integration), retry the failed run (`operating.md`).
3. If a newer release already deployed to the stage, use rollback or redeploy instead of retry.
4. Tell the user what failed, the evidence (the log line or field), what you changed and the console link to the run.

# Operate a delivery pipeline

Runs, gates and stages have no CLI command, and `pulumi api` does not resolve the Delivery routes. Call the routes with the `/tmp/dapi` wrapper. It is a small `curl` script that `SKILL.md` defines ("Call the Delivery API"). Write it once in a task before the first call.

In the examples, `<org>/<project>/<stack>` is the pipeline stack, for example `acme/shop-delivery/main`.

## Who can do what

Your token is the Pulumi access token of the user. Each action needs its own permission on the pipeline stack. The Stack Write and Stack Admin roles grant all of them, and Stack Read grants none. A custom role has only the permissions that someone added to it.

| Action | Permission | Can you do it? |
| --- | --- | --- |
| Read pipelines, runs, stages, gates, members, logs | Read access to the pipeline stack | Yes |
| Dispatch a run | `pipeline:dispatch` (a `ref` or source pins also need `stack:write`) | Yes |
| Cancel a run | `pipeline:cancel` | Yes |
| Retry a run | `pipeline:retry` | Yes |
| Continue a manual gate | `pipeline:approve` | Yes |
| Redeploy, roll back or force-promote a stage | `pipeline:redeploy`, `pipeline:rollback`, `pipeline:force_promote` | Yes |
| Pause or resume a stage | `pipeline:pause` | Yes |
| Approve or reject an approval gate | Named in `approvers`, or `pipeline:approve` when the gate names nobody | **No.** A person approves or rejects. Give the user the console link to the gate or the approvals inbox. |
| Register the pipeline, or run it with `pulumi up` | See `authoring.md` | Only with the agreement of the user |

These actions deploy infrastructure or stop deployments. Ask the user before each one, and say which stage, release and stacks it affects. A 403 names the missing permission; tell the user, do not retry.

## Find the pipeline and its runs

```sh
/tmp/dapi GET "/api/preview/delivery/<org>/programs" \
  | jq -c '.programs[] | {project, stack, registered, stages, pendingApprovals, lastRun: .lastRun.number}'
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/runs?maxResults=10" \
  | jq -c '.runs[] | {number, status: .status.status, stage: .status.stageName, reason: .status.reason, release: .releaseNumber, triggerKind, local}'
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/program"
```

Filters of the runs list: `status`, `stage`, `release`, `queued=true` with `stage` (runs that wait for that stage, in order).

A run with `local: true` is a run from a checkout (`pulumi up` on the pipeline stack). The update of that person drives it. You cannot retry or cancel it through the API, and its release cannot be redeployed, rolled back to or promoted.

## Read a run

```sh
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/runs/12" > /tmp/run.json
jq '{failureReason, kind: .summary.kind, status: .summary.status, actions, pass: .currentPass}' /tmp/run.json
jq -c '.stages[] | {name, from, admittedAt, convergedAt, gate: (.gate | {id, status, conditions: [.conditions[]? | {name, kind, state, changeRequestId, eligibleApprovers}]})}' /tmp/run.json
jq -c '.members[] | {id, name, type, stageName, status: .status.status, reason: .status.reason, failureReason, attempt: .currentAttempt.number}' /tmp/run.json
```

`actions.retry.allowed` and `actions.cancel.allowed` say whether you can retry or cancel now, and `reason` says why not.

## Start a run

A push to a triggered source starts a run. To start one by hand:

```sh
/tmp/dapi POST "/api/preview/stacks/<org>/<project>/<stack>/delivery/dispatch" '{"key": "<unique key>"}'
```

Check `dispatch.allowed` and `dispatch.reason` in the program (the `.../delivery/program` call above) first. Use a fresh `key` for each intended run. A second dispatch with the same key returns the first run; this makes a retried request safe. A 409 "The pipeline has no active registration." means the pipeline is not registered: see `debugging.md`.

A dispatch can run the program at another ref and pin sources. Use this only when the user asks for it:

```sh
/tmp/dapi POST "/api/preview/stacks/<org>/<project>/<stack>/delivery/dispatch" \
  '{"key": "hotfix-1", "ref": "release/1.4", "sources": [{"name": "app", "value": "v1.4.2"}]}'
```

- `ref` is a branch, a tag or a full commit SHA of the program repository. The run uses the program code at that commit. The stages, gates and sources stay those of the registered definition.
- `sources` pins a repository source, by the name of its resource, to a branch, a tag or a full SHA. Other sources get their latest value. A source on the program repository is not pinned by `ref`; pin it in `sources`.

## Gates

Get the gate ID from `stages[].gate.id` in the run detail, or:

```sh
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/runs/12/gates/<gate id>"
```

**Manual gate.** Check `conditions[].canContinue.allowed` (and `reason`) in the run detail, then continue it:

```sh
/tmp/dapi POST "/api/preview/stacks/<org>/<project>/<stack>/delivery/runs/12/gates/<gate id>/continue" '{}'
# a gate with several manual conditions needs the condition name:
/tmp/dapi POST "/api/preview/stacks/<org>/<project>/<stack>/delivery/runs/12/gates/<gate id>/continue" '{"condition": "dashboards", "comment": "Checked."}'
```

Always send a JSON body; no body gives a 400. A 409 "The gate is not open." means someone already continued it.

**Approval gate.** Report who can approve (`eligibleApprovers`; empty means anyone with `pipeline:approve` on the pipeline stack), how many approvals it needs (`requiredApprovals`) and has (`approvals`). Anyone eligible can approve, including the person who started the run. Show the planned changes:

```sh
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/runs/12/gates/<gate id>/changes/<member id>"
```

Closing the change request rejects the approval: the run fails at once, and a retry asks for a new approval. Only someone the approval accepts can reject it. Do not reject an approval yourself.

A run that waits at a gate or in a stage queue ends as `superseded` when a newer release arrives there. Tell the user when an approval they expect is for a superseded run: the newer run has its own gate.

"Not available" in a preview is not the same as "no changes". Then send the user the gate link, `https://app.pulumi.com/<org>/delivery/<project>/<stack>/runs/<run number>/gates/<gate id>`, or the approvals inbox, `https://app.pulumi.com/<org>/delivery/approvals`.

## Recover a run

**Retry** a failed run after you fix the cause. It runs only the failed members again (a whole `Stacks` group if one entry failed), with the same commit, recorded values and release. A pushed fix does not reach a retry; a fix outside the repository (a created stack, a granted permission) does.

```sh
/tmp/dapi POST "/api/preview/stacks/<org>/<project>/<stack>/delivery/runs/12/retry"
```

Only a failed run can be retried. A retry returns 409 when a newer release already reached the failed stage, a newer run waits for it, or the run stack no longer exists; use rollback or redeploy then.

**Cancel** an active run (a gate waits or a member runs):

```sh
/tmp/dapi POST "/api/preview/stacks/<org>/<project>/<stack>/delivery/runs/12/cancel"
```

The run shows "canceled" at once, but a running update can take minutes to stop. Wait until it ends before you touch its stack; the stack can need `pulumi refresh`.

## Operate a stage

Rollback, redeploy and promote create a new run for one stage from an earlier run's release, recorded values and outputs. They skip the stage's gate.

```sh
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/stages/prod"      # deployed release, lock, pause, queue, allowed actions
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/releases"

/tmp/dapi POST "/api/preview/stacks/<org>/<project>/<stack>/delivery/stages/prod/rollback" '{"releaseNumber": 41}'
/tmp/dapi POST "/api/preview/stacks/<org>/<project>/<stack>/delivery/stages/prod/redeploy"
/tmp/dapi POST "/api/preview/stacks/<org>/<project>/<stack>/delivery/stages/prod/promote" '{"releaseNumber": 42}'
/tmp/dapi POST "/api/preview/stacks/<org>/<project>/<stack>/delivery/stages/prod/pause"
/tmp/dapi POST "/api/preview/stacks/<org>/<project>/<stack>/delivery/stages/prod/resume"
```

- **Rollback** deploys an earlier release that converged this stage and is older than the release deployed now. List the candidates with `/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/releases?rollbackStage=prod"`. A rollback pauses the stage, so newer runs wait until someone resumes it. Tell the user to resume the stage after the cause is fixed.
- **Redeploy** deploys the stage's current release again.
- **Promote** (force-promote) moves a ready release to the stage without its gate. The upstream stages of that stage must have converged for the release. It also skips an `approval()` gate, so never use it there unless the user asks (hard rule 16 in `SKILL.md`).
- **Pause** stops the stage from admitting new runs. A run that holds the stage keeps it. **Resume** lets the stage admit runs again.

The stage call returns `stage` (with `paused`, `lockRunNumber` and `queueLength`) and `actions.rollback`, `actions.redeploy`, `actions.forcePromote`, `actions.pause` and `actions.resume` with `allowed` and `reason`. Check them first.

## Events

```sh
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/events?runNumber=12" | jq -c '.events[] | {kind, stageName, actorKind, actor, createdAt, detail}'
```

Filters: `runNumber`, `stage`, `kind`, `actorKind`, `approvalStatus`.

# Operate a delivery pipeline

There is no `pulumi delivery` command, and `pulumi api` does not work for Delivery: the Delivery routes are preview routes that are not in the public API specification, so `pulumi api` resolves neither their operation IDs nor their paths. Call the routes with `curl`.

Write this helper once in a task, then use it for every call:

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

- The helper needs `PULUMI_ACCESS_TOKEN` in the environment. If it is not set, ask the user to export a Pulumi access token.
- The path starts with `/api/preview/`. Put filters in the query string.
- On a 4xx or 5xx status, the helper prints the response body, which carries the message, and exits with a non-zero code.
- In the examples, `<org>/<project>/<stack>` is the pipeline stack, for example `acme/shop-delivery/main`.

## Who can do what

Your token acts on behalf of the user who started the task.

| Action | Can you do it? |
| --- | --- |
| Read pipelines, runs, stages, gates, members, logs | Yes, with read access to the pipeline stack |
| Dispatch, continue a manual gate, retry, cancel, roll back, redeploy, promote | Yes, with write access to the pipeline stack, and not in read-only mode |
| Approve an approval gate | **No.** Approving needs a real user. Give the user the console link to the gate or the approvals inbox. |

These actions deploy infrastructure or stop deployments. Ask the user before each one, and say which stage, release and stacks it affects. A 403 means the user lacks write access to the pipeline stack or the task is read-only; tell the user, do not retry.

## Find the pipeline and its runs

```sh
/tmp/dapi GET "/api/preview/delivery/<org>/programs" \
  | jq -c '.programs[] | {project, stack, stages, pendingApprovals, lastRun: .lastRun.number}'
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/runs?maxResults=10" \
  | jq -c '.runs[] | {number, status: .status.status, stage: .status.stageName, reason: .status.reason, release: .releaseNumber}'
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/program"
```

Filters of the runs list: `status`, `stage`, `release`, `queued=true` with `stage` (runs that wait for that stage, in order).

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

Check `dispatch.allowed` and `dispatch.reason` in the program (the `.../delivery/program` call above) first. Use a fresh `key` for each intended run. A second dispatch with the same key returns the first run; this makes a retried request safe. The preview has no dispatch inputs. A 409 "no active registration" means the pipeline is not registered: see `debugging.md`.

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

Always send a JSON body; no body gives a 400. A 409 "the gate is not open" means someone already continued it.

**Approval gate.** Report who can approve (`eligibleApprovers`; empty means anyone with organization update permission), how many approvals it needs (`requiredApprovals`) and has (`approvals`). Show the planned changes:

```sh
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/runs/12/gates/<gate id>/changes/<member id>"
```

Closing the change request rejects the approval: the run fails at once, and a retry asks for a new approval. Anyone who can read the pipeline stack can close it. Do not close a change request yourself unless the user asks you to reject the release.

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

These create a new run for one stage from an earlier run's release, recorded values and outputs. They skip the stage's gate.

```sh
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/stages/prod"      # deployed release, lock, queue, allowed actions
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/releases"

/tmp/dapi POST "/api/preview/stacks/<org>/<project>/<stack>/delivery/stages/prod/rollback" '{"releaseNumber": 41}'
/tmp/dapi POST "/api/preview/stacks/<org>/<project>/<stack>/delivery/stages/prod/redeploy"
/tmp/dapi POST "/api/preview/stacks/<org>/<project>/<stack>/delivery/stages/prod/promote" '{"releaseNumber": 42}'
```

- **Rollback** deploys an earlier release that converged this stage and is older than the release deployed now. List the candidates with `/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/releases?rollbackStage=prod"`. The rollback run waits in the stage queue like any run.
- **Redeploy** deploys the stage's current release again.
- **Promote** moves a ready release to the stage without its gate. The upstream stages of that stage must have converged for the release.

The stage call returns `actions.rollback`, `actions.redeploy` and `actions.forcePromote` with `allowed` and `reason`. Check them first.

A stage has no pause. To hold a stage until a person says go, give it a `manual()` gate.

## Events

```sh
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/events?runNumber=12" | jq -c '.events[] | {kind, stageName, actorKind, actor, createdAt, detail}'
```

Filters: `runNumber`, `stage`, `kind`, `actorKind`, `approvalStatus`.

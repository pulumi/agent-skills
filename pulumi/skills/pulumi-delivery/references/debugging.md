# Debug a delivery pipeline

Find the failing layer first, then read its logs, then match the symptom below. Use the `/tmp/dapi` helper and the commands from `operating.md`.

## 1. Find the failing layer

| Layer | Where it shows | First read |
| --- | --- | --- |
| Registration | `pulumi up` on the pipeline stack; the program, `.../delivery/program` (`registered`, `lastFailedRegistration.reason`, `warnings`) | The full CLI output, or the registration fields when the user registered |
| Run | The run detail, `.../delivery/runs/<n>`: `failureReason`, `summary.status` | `currentPass`, then the members |
| Pass (one execution of the program on the run stack) | `currentPass.outcome = failed`, `currentPass.failureReason` | Pass logs |
| Member (a `Stacks` entry, `Job` or `Artifact`) | `members[].status`, `members[].failureReason`, `currentAttempt` | Attempt logs; for `Stacks`, the update of the target stack |
| Gate | `stages[].gate.status`, `conditions[].state` | The gate and its conditions |

A status `waiting` with a `waitKind` (`approval`, `manual`, `queue`, `stage`, `dependency`, `target`) is a wait, not a failure.

## 2. Read the logs

```sh
# passes of a run, then the logs of one pass
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/runs/12/passes" | jq -c '.passes[] | {number, status, outcome, failureReason}'
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/runs/12/passes/3/logs" | jq -r '.lines[] | "\(.step // ""): \(.text)"' > /tmp/pass.log

# attempts of a member, then the logs of one attempt
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/runs/12/members/<member id>/attempts" | jq -c '.attempts[] | {number, status, failureReason, updateVersion}'
/tmp/dapi GET "/api/preview/stacks/<org>/<project>/<stack>/delivery/runs/12/members/<member id>/attempts/1/logs" | jq -r '.lines[].text' > /tmp/attempt.log
```

Logs are paginated: add `?continuationToken=<token>` from the previous page to the path. `gone: true` means the log was deleted. Write logs to a file and search it (`grep -n -i error /tmp/pass.log`); do not print a whole log.

For a failed `Stacks` member, `currentAttempt.updateId` and `updateVersion` identify the update of the target stack. Read it like any stack update (use skill `pulumi-debug-failed-operation`, or `pulumi stack history` in the target stack's project).

## 3. Match the symptom

### Registration

| Symptom | Cause | Fix |
| --- | --- | --- |
| `pulumi up` exits 10 with "Registered. ..." | Expected | Not a failure. Read which "Registered." message it is (`authoring.md`). |
| The update shows as failed in the stack history, says the resource "is awaiting", or offers a Neo explanation | Known preview display issue | Ignore if the output has a "Registered." line. |
| "Registered." appears, then a later error in the same output | The message prints before the whole program registered | Fix the later error and register again. |
| `pulumi package add delivery` fails with "installing dependencies: exit status 1" | CLI older than 3.265, or an older `pulumi-language-nodejs` earlier on `PATH` | Use CLI 3.272.0 or later. Check `which -a pulumi-language-nodejs`. In Neo, hand this step to the user. |
| `pulumi package add delivery` fails with "package delivery not found" | The registry of this Pulumi Cloud instance does not have the `delivery` package | Stop. Do not search for the package or write your own types. Write the program from `schema.md` and tell the user that the instance has no `delivery` package. |
| `package add` installs an old prototype plugin | A stale local plugin has a higher version | `pulumi plugin rm resource delivery --all --yes`, then add the package again. |
| Python: `NameError: SourceTriggerArgs` (or another `*Args` name) | Known bug in the preview Python SDK: `_inputs` and the resource modules import each other | Prefer TypeScript. If the program must be Python, see "Python SDK workaround" below. |
| TypeScript: a second `npm ci` fails with TS5055 "would overwrite input file" | Known open issue in the generated SDK | No fix yet. The first install after `pulumi package add delivery` works. Tell the user. |
| A secret value in `config` is rejected | `config` takes plain strings | Move the value to `environment` or to the target stack's config or ESC environment. |
| A stage with an `http()` rule is rejected | Not available in the preview | Use `manual()` or `approval()`. |
| "The approver ... is not a user or a team of this organization." | An `approvers` name is wrong | Use Pulumi user logins or team names of the organization. |
| "Approval gates need the Approvals feature." | The organization has no Approvals feature | Use `manual()`. |
| A dispatch returns 409 "no active registration" | No successful registration (or an old CLI recorded it as failed) | Register again with CLI 3.272.0 or later from a clean, pushed checkout. |

### Run and pass

| Symptom | Cause | Fix |
| --- | --- | --- |
| "The target stack ... does not exist. Create it first." | A `Stacks` entry names a missing stack | `pulumi stack init <org>/<project>/<stack>`, then retry the run. |
| Every pass fails in about a second with "The work could not be launched." | The forge integration cannot access the repository (common with a public repository outside the GitHub App installation) | Add the repository to the integration, then retry. |
| A pass fails because a source was created after the first pass | A source is declared inside an `apply` or depends on a member output | Declare every source at the top level. Push the fix; a retry does not pick it up. |
| "The step pass failed." with no detail | Generic failure line | Read the pass logs. |
| A downstream run waits or fails with "has no deployed release" | The upstream stage of a `PipelineSource` has not deployed yet | Let the upstream pipeline deploy that stage first. |
| A pass fails with "cannot read the pipeline" for a `PipelineSource` | The Delivery identity of the organization (the default deployment role) has no read access to the upstream pipeline stack. The user's own access is not enough. | Ask the user to grant that role read access to the upstream pipeline stack, then retry. |
| A run has the status `superseded` | A newer release reached the gate or the queue of the stage where this run waited | Nothing to fix. Follow the newer run. To deploy the older release anyway, promote it (`operating.md`). |
| A run fails at an approval gate with no failed member | Someone closed the change request of the approval, which rejects it | Ask who rejected it and why. A retry asks for a new approval. |
| "The stack <name>-r<N> already exists" | A run stack name is taken | Tell the user; do not delete stacks to clear it without asking. |

### Member

| Symptom | Cause | Fix |
| --- | --- | --- |
| "you do not have permission to open environment '<org>/<project>/<env>'" | The default deployment role cannot open the ESC environment that the target stack imports | Grant that role open access on the environment, then retry. |
| Cloud authentication errors in a `Stacks` update | No credentials: Delivery ignores Deployment settings | Import an ESC environment with OIDC in the target stack config, or pass secrets in `environment`. |
| A job fails with a non-zero exit | The command failed | Read the attempt logs. Retry inside smoke scripts (`curl -fsS` with a loop). |
| A job needs Pulumi access and fails to authenticate | A job gets no Pulumi token | Do Pulumi work in a `Stacks` member, or pass a token as a secret in `environment` (ask the user first). |
| Job outputs are missing | Nothing written to `$DELIVERY_OUTPUTS`, invalid JSON, or larger than 1 MiB | Write one JSON object to the file. |
| A member update was canceled and the next update fails | The stack state is out of date | Wait for the canceled update to end, then `pulumi refresh` on the target stack (ask first). |
| A `Stacks` group does not start, and the run fails after 2 hours | The group has more entries than the organization's concurrency limit (registration warns). A group with no progress for 2 hours fails. | Split the group. |
| A `Stacks` update fails on policy violations | The policy groups of the target stack apply to the update | Fix the violation in the stack's program and push, or ask the user to get a policy exception, then retry. |
| A job reaches cloud resources that you did not give it access to, or fails cloud authentication | A `Job` cannot import an ESC environment. With no credentials in `environment`, it has only what the runner has. | Pass the credentials the job needs as secret values in `environment`. Never rely on the runner's own identity. |
| A member runs for 2 hours and stops | Default member time limit | For a `Stacks` entry that needs longer, raise `timeout` (up to 24 hours). Otherwise split the work, or set a lower `timeout` to fail faster. |

### Waiting forever

| Symptom | Cause | Fix |
| --- | --- | --- |
| An approval gate never passes | No eligible person approved, or an approver left the organization after registration | Check `eligibleApprovers`, `approvals` and `requiredApprovals`; ask an eligible user to approve, or fix the names and push. |
| Two stages wait for each other | A cycle in `from`; the preview does not detect it | Cancel the run, fix `from`, push. |
| A run waits at a stage | Another run holds the stage (`lockRunNumber` in the stage, `.../delivery/stages/<name>`), or runs ahead of it in the queue (the runs list with `queued=true` and `stage`) | Let the runs ahead finish, or cancel the one that blocks. |
| The run says "Waiting to retry" and retry is disabled | An automatic pass restart is in progress | Wait; retry becomes available only after the run fails. |

## Python SDK workaround

This workaround was reported to work with SDK 0.0.1a3. Put it at the top of a Python pipeline program, after the imports, until the SDK is fixed:

```python
import sys

import pulumi_delivery as delivery
from pulumi_delivery import _inputs

for _name, _mod in list(sys.modules.items()):
    if _name.startswith("pulumi_delivery.") and _mod is not None:
        for _attr in getattr(_inputs, "__all__", []):
            if not hasattr(_mod, _attr):
                setattr(_mod, _attr, getattr(_inputs, _attr))
```

## 4. Fix and recover

1. Fix the cause. For a cause in the repository, push the fix: a **new run** picks it up, a retry does not.
2. For a cause outside the repository (a missing stack, a permission, an integration), retry the failed run (`operating.md`).
3. If a newer release already deployed to the stage, use rollback or redeploy instead of retry.
4. Tell the user what failed, the evidence (the log line or field), what you changed and the console link to the run.

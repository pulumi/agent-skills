# Automation recovery

Retain the verified agent and known automation IDs. Do not recreate resources, delete as rollback, broaden access, or switch identities. Report only successful reads actually present in the command history. Authentication/authorization errors are not proof that no automation exists or the operation is unsupported.

## Saved configuration differs

Report the exact requested versus saved values, resource ID, and actual active/paused state. An active automation may run with the saved settings. Do not repair, pause, resume, delete, or recreate unless that specific action is already authorized. If an active resource needs a recovery decision, ask whether to pause its actual ID. Do not act on silence. If pausing is authorized, use skill `pulumi-setup-agent-automation` for its pause/resume procedure. If that skill is unavailable, retain the IDs and pending pause request, and report the missing skill before any mutation.

## Create response was lost

Reconcile through supported list and GET reads before considering a retry. Follow relevant pagination. Establish list scope and authoritative visibility before relying on absence. A configuration match alone does not establish that this attempt created it. Use operation-bound returned identity when available. While ownership is uncertain, do not retry, duplicate, adopt, or automatically pause candidates.

Prominently report each candidate ID and active/paused state, say ownership is uncertain, and explain that active candidates may keep running. Ask whether to pause each active candidate by ID; pausing requires that specific authorization and the pause/resume procedure.

If uncertainty remains, stop with that outcome. Do not claim confirmed creation or generate/rotate a webhook secret to recover from a missing response. Secret recovery follows [Secret handling](automation-webhook-secrets.md).

## Pending information or later setup

Follow the workflow’s pending-decision reporting rule, including in headless runs. Retain a Markdown draft and confirmed IDs. Sender setup, event delivery, credential access, and actual task execution remain separate from saved configuration. Resume only the incomplete step under the user's existing scope.

---
name: pulumi-debug-failed-operation
version: 1.0.0
description: |
    Debug a Pulumi update or preview that failed: read the failure Pulumi already
    recorded, find what caused it, and fix it. Load this skill when the user asks
    to debug, diagnose, or fix a failed update or preview, or points at a failing
    `pulumi up` or `pulumi preview`. Don't load it for authoring new
    infrastructure, migrations, or provider upgrades; those have their own skills.
---

# Debug a failed Pulumi operation

A Pulumi operation has failed. Find what caused it and fix it. The user usually
points you at it, so start by working out which operation to debug, and confirm it
with the user before doing anything else. Pulumi recorded the error when the
operation failed, so once you know which operation it is you can read the error from
that record without running anything again.

The commands below reach Pulumi Cloud with `pulumi api`, a subcommand of the Pulumi
CLI that you run in your shell. Each one targets a stack by the explicit
`{orgName}/{projectName}/{stackName}` path you pass it, so you do not need that
stack selected locally to read its record. Selecting the stack matters later, when
you go to apply a fix.

## Start from the operation the user gave you

The user usually supplies the operation as a set of fields: the org, project, stack,
and update version (or preview id) — most often stated in prose, for example "debug
update 161 of vvm-dev". You need these to address the API: `{orgName}`,
`{projectName}`, `{stackName}`, and the version or preview id.

Fill any missing field from context. Take the org, project, or stack from the
currently selected stack (`pulumi stack --show-name`, `pulumi stack ls`) or
`Pulumi.yaml`. A missing version means the most recent update on that stack.

Briefly confirm which operation you landed on, its version or preview id and the
stack, before reading further. Keep it lightweight; they already told you.

## Read what failed

A failed update and a failed preview both record engine events, and the error is in
the diagnostic messages inside those events. Using the fields you settled on above,
fetch the events and pull the messages out.

For a failed update, use the `update` path with the version number:

```
pulumi api /api/stacks/{orgName}/{projectName}/{stackName}/update/<version>/events \
  | jq -r '.events[].diagnosticEvent | select(. != null) | "[\(.severity)] \(.message)"' \
  | sed 's/<{%reset%}>//g'
```

For a failed preview, use the `preview` path with the preview id:

```
pulumi api /api/stacks/{orgName}/{projectName}/{stackName}/preview/<preview-id>/events \
  | jq -r '.events[].diagnosticEvent | select(. != null) | "[\(.severity)] \(.message)"' \
  | sed 's/<{%reset%}>//g'
```

Read every message, not only the ones tagged `severity == "error"`. A provider
error carries that `error` tag, but a program error, which is the common case when
a preview fails, arrives as a stderr diagnostic tagged `info#err`. The trailing
`sed` strips terminal color codes that Pulumi embeds in the text, which otherwise
show up as `<{%reset%}>`.

## Find the cause and where the fix belongs

An operation can fail with errors from more than one resource, so read all of the
diagnostics first, then work through each error. Trace every error back to the
resource that raised it (its URN and type), to where that resource is declared in
the program, and to the inputs that feed it.

The error text tells you what kind of problem it is, and that points to where the
fix belongs. A Pulumi fix lands in one of three places, and naming the right one
keeps you from editing code that was never the problem.

- **The program.** The code is wrong: a bad reference, a wrong type, an input the
  provider rejected, or a value used before it had resolved. This is what a failed
  preview usually reports, because the plan could not be built. Fix it by editing
  the code.
- **The state.** The code is correct, but the stored state and the real cloud
  resources disagree. Reconcile drift with `pulumi refresh`, and bring a resource
  that already exists outside the state under management with `pulumi import`
  rather than recreating it. Note that an operation which failed partway through
  applying may have already changed some resources, so check the current state
  before you decide.
- **The environment.** The problem is outside Pulumi: credentials, permissions,
  OIDC, or a quota. Fix the role, the ESC environment, or the capacity that the
  provider rejected, rather than the resource code.

## Fix the cause

Make the smallest change that addresses the root cause. How you confirm the fix,
and how you deliver it, whether as a local edit or as a pull request, follow your
mode's workflow, not this skill.

## If the user didn't say which operation

When the user gives you nothing to go on, debug their most recent operation on the
stack. The update list does not record who ran each update, so find it through the
API:

1. Run `pulumi whoami` to get the current user's login.
2. Read the latest update and who requested it with
   `pulumi api /api/stacks/{orgName}/{projectName}/{stackName}/updates/latest`, and
   compare its `requestedBy.githubLogin` to the login from step 1.
3. If they match, that update is the one to debug. If they do not, walk back one
   version at a time with
   `pulumi api /api/stacks/{orgName}/{projectName}/{stackName}/updates/<n>` until
   `requestedBy.githubLogin` matches the user.

Tell the user which operation you landed on, its version, kind, and result, and
confirm it is the one they mean before going further.

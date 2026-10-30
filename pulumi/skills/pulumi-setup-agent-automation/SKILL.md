---
name: pulumi-setup-agent-automation
description: Create a schedule or event trigger for a verified Pulumi Agent through supported Pulumi CLI operations, or pause or resume an existing automation. Use when a user accepts automation setup, requests recurring or event-driven work, or asks to pause or resume an automation. Not for creating another agent or starting an immediate task.
---

# Set up agent automation

An automation is separate from its saved agent. For an accepted schedule or event trigger, read [Configure automation](references/configure-automation.md). Reuse resolved choices and existing authorization; honor explicit requests for a proposal and resolve missing material choices before mutation.

For an explicit pause or resume request, follow the pause/resume procedure below. If the user declined automation, acknowledge the manual-only choice without asking again or mutating anything. If their choice is unanswered, ask whether they want a schedule, an event trigger, or no automation.

When blocked on a decision, report verified IDs and state, explain unfinished work, and ask the actual unresolved question, including in headless output. Retain the agent and draft. Silence does not authorize mutation.

Automation references: [API contract](references/cli-contract.md) for supported request fields; [webhook handling](references/webhook-secrets.md) before preparing a webhook; [recovery](references/recovery.md) after an uncertain response or differing readback. Load these only for the relevant automation step.

## Pause or resume an existing automation

1. Read [CLI contract](references/cli-contract.md). Discover supported operations with `pulumi api list --filter AgentAutomation --refresh-spec --output=json`, then run `pulumi api describe <operation> --output=json` for each required read and pause/resume operation before invoking it. Do not require create support or recreate resources to change an existing automation's state.
2. GET the supplied organization and automation ID to verify identity, current state, binding, and rule. For an authorized pause, do not require the bound agent to be active or readable: pausing disables future recurrence. Report a missing, deleted, or unreadable agent separately if observed. For resume, verify the bound agent with GET and active roster membership and resolve any required invocation authority before enabling future work.
3. If the requested state is already saved, report it without mutation. Otherwise serialize only the described paused boolean. Inspect the request body for the requested boolean and absence of rule changes; correct any mismatch before submission. If the target, desired state, or authorization is unresolved, ask before mutation. Honor an explicit request to show the change first; otherwise, perform one authorized state-change call without another approval.
4. GET the automation to verify its new state and unchanged rule. For a failed read, differing readback, or uncertain response, follow [Recovery](references/recovery.md) before any further mutation. Pause stops future recurrence; resume enables future dispatch. Neither cancels already started tasks.

## Report the result

Return the verified organization and automation ID, the requested action, and the observed state. For creation, include the saved agent binding and schedule or trigger, distinguishing saved configuration from tested execution. For pause/resume, say whether the state changed or was already set, and whether readback confirmed the rule was unchanged. Example: "Automation automation-123 in example-org is paused; readback confirms the rule is unchanged. Already started tasks were not cancelled."

If blocked or uncertain, state what is verified, what remains unfinished or unverified, and the next check or actual unresolved question. Do not report success from a failed call or read.

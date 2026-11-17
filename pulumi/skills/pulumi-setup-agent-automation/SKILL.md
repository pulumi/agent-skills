---
name: pulumi-setup-agent-automation
description: Create a schedule or event trigger for an existing Pulumi Agent, or pause or resume an automation. Use when the user requests recurring or event-driven agent work, says yes to a proposed schedule or trigger, or asks to pause or resume an automation.
---

# Set up agent automation

An automation runs a saved Pulumi Agent on a schedule or in response to events. Creating an automation does not create a new agent or start a one-time task.

## Create a schedule or event trigger

Read [Configure automation](references/configure-automation.md).

Confirm the organization, saved agent, per-run instructions, schedule or event, and CLI connections. Reuse choices the user already supplied and ask about anything needed to complete the request. If the user declined automation, leave the agent available for manual invocation.

Check the agent's `pausedAt` field. A paused agent starts no new runs even when its automation is active. Setting up or resuming an automation must not resume the agent.

Use the [API contract](references/cli-contract.md) for operations and request fields. For webhooks, read [Webhook secrets](references/webhook-secrets.md) before creating the automation.

## Pause or resume an existing automation

1. Discover and describe the read and pause operations in the [API contract](references/cli-contract.md). Read the automation by organization and ID.
2. For resume, verify the bound agent, its pause state, and the caller's invocation access. A missing or unreadable agent does not prevent an authorized automation pause.
3. If the automation already has the requested state, report it. Otherwise call `UpdateAgentAutomationV2Paused` with only the requested `paused` value.
4. Read back the automation to verify its state and unchanged rule. After resume, also report whether the agent is paused.

Pausing stops future recurrence; it does not cancel tasks already created. Resuming an automation does not resume its agent.

## Verify and report

Return the automation ID, bound agent, saved schedule or trigger, and automation state. If the agent is paused, say that it cannot start new runs.

Saving configuration does not prove that a webhook was delivered or a task completed. Do not trigger a test run unless requested.

For an uncertain create response or mismatched saved configuration, follow [Recovery](references/recovery.md). If a required API or decision is unavailable, preserve the draft and explain what is needed to continue.

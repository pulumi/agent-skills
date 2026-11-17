---
name: pulumi-create-agent
description: Create a reusable Pulumi Agent with saved instructions, a role, and selected integrations. Use when the user asks to create, define, or set up a new Pulumi Agent.
---

# Create a Pulumi Agent

Create a saved agent definition. Starting a task or configuring automation is a separate action.

## Discover and resolve

Confirm the target organization and current login with `pulumi whoami -v`. Do not infer the organization from the current stack or repository. Read [CLI contract](references/cli-contract.md) for operation discovery, request fields, and integration selection.

Check existing agents before choosing a name. If the name is taken, show the existing agent and ask how to proceed.

Resolve these settings from the user's request and project context:

- Name, display name, responsibility, resource scope, and expected output.
- Saved instructions, including relevant team requirements. These replace organization AI preferences, so include requirements the agent must retain.
- An organization role the caller may assign. Check its grants and exclude built-in Admin and Billing Manager roles. Instructions and deprecated `permissionMode` do not restrict authority.
- Connected MCP integrations. Set the selection explicitly, including `[]` for none; omission inherits all organization integrations.
- Approval mode. If unresolved, propose manual approval and explain that unattended runs may wait for a person.

Local files and uncommitted changes are not automatically available to the remote agent. Check that it can reach the repositories and connections needed for its responsibility. MCP selection does not control separate CLI credentials.

Ask only for missing choices. If a required API is unavailable or access cannot be verified, save a local draft with the known settings, complete instructions, and remaining questions. Explain the blocker without changing the requested access.

## Tell the user, then create

Show the complete configuration and literal instructions that will be saved:

```text
Organization:
Name and display name:
Responsibility and resource scope:
Role:
MCP integrations:
Approval mode:
Saved instructions:
[complete text]
```

Keep the instructions within the requested responsibility and resource boundary. For work outside that boundary, tell the agent to report the dependency and request a revised responsibility.

Submit exactly the displayed values using the request-file workflow in [CLI contract](references/cli-contract.md). If creation is already authorized and all choices are resolved, proceed without asking again.

## Verify the result

Read the returned agent ID and check active roster membership. Compare the saved name, display name, purpose, instructions, role, integrations, and approval mode with the proposal.

If values differ, report the saved result and the mismatch before making another change. Do not recreate or delete the agent as a rollback.

If the create response is lost, check the agent list and retrieve candidates before retrying. Follow all pages. A matching name alone does not prove the agent came from this request; use returned resource or request identifiers where available. If the outcome remains uncertain, report it rather than creating another agent. Do not treat a failed or incomplete listing as proof that creation failed.

Return the verified agent ID, organization, and saved configuration. Creation confirms the settings, not that the agent has successfully completed a task.

## Address automation

After creation, ask unless the user already supplied a preference:

“Would you like to set up automation for this agent: a schedule, an event trigger, or no automation for now?”

An unanswered automation choice does not block agent creation. Leave that choice pending if no answer is available.

If the user requested a schedule or trigger, continue with [Configure automation](references/configure-automation.md). If they declined, acknowledge manual invocation without asking again. Keep the created agent if automation setup fails.

For an explicitly requested first task, read [Requested immediate task](references/additional-outcomes.md). A one-time task does not answer the recurring-automation question.

Load automation details only when needed: [API contract](references/automation-cli-contract.md) for commands, [webhook secrets](references/automation-webhook-secrets.md) before webhook creation, and [recovery](references/automation-recovery.md) after an uncertain or mismatched result.

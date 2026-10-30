---
name: pulumi-create-agent
description: Prepare and create a reusable Pulumi Agent through supported Pulumi CLI operations, with saved instructions, a verified role, and explicit integrations. Use for creating a new Pulumi Agent, not a coding-harness subagent, Pulumi program, task assignment, or update to an existing agent.
---

# Create a Pulumi Agent

Follow this sequence: discover support and access, **tell the user exactly what you will save**, serialize that text, create once, verify the result, and address whether the user wants automation.

Read [CLI contract](references/cli-contract.md). The October 30, 2026 public schema check found no discoverable definition operations. Recheck the target backend; do not assume availability or absence.

## Discover and resolve

Run `pulumi version`, `pulumi api --help`, and `pulumi whoami -v`. Identify the backend, account, and intended organization. A current stack, repository owner, or default organization does not select the target. If installation or authentication is missing, report that prerequisite and stop before organization reads. Do not inspect credentials, install software, change accounts, or change backends silently.

List operations with `pulumi api list --filter AgentDefinition --output=json`. If none appear, refresh once with `--refresh-spec`. Run `pulumi api describe OPERATION --output=json` for every operation before using its parameters or response fields. A listing, even if it includes metadata, does not replace describe. Required capabilities are definition create/list/get and the reads needed to verify access: `ListRolesByOrgIDAndUXPurpose` (`uxPurpose=role`), `GetRole` (`roleID`), and `ListConfiguredAgentIntegrations`. Raw paths still require a matching supported schema. Do not substitute internal HTTP or task creation.

Read the target organization's active agents, assignable roles and grants, and configured integration IDs. Use returned IDs and explicit organization parameters. If the name is taken, show the existing agent and leave the naming decision open. Do not replace it or invent a suffix. Verify supplied IDs too.

Use the request and relevant project instructions to resolve:

- Name, display name, responsibility, exact resource scope, and expected output.
- Reusable instructions including applicable team requirements, evidence standards, and when to ask for help. Saved instructions replace organization AI preferences. Obtain missing requirements from the user if no supported read exists. Keep one-time incident IDs in task assignments.
- An assignable role with verified grants. Instructions and deprecated `permissionMode` do not enforce authority. Pulumi roles do not establish the scope of separate external credentials.
- Explicit integration IDs, including `[]` for none. Omission can inherit all organization MCP integrations. MCP selection does not bound CLI connections or ESC access.
- Explicit approval mode. Propose manual if unresolved, explaining unattended work may wait for a person; do not silently select auto. If approval mode remains unresolved and no human is available, stop without creating.
- Direct assignment or the user's requested event/schedule. Record any explicit automation preference. Creation alone does not authorize a task or automation.

Local files, tools, credentials, and uncommitted changes are not automatically available to the remote agent. Verify relevant connections or report the gap. Never embed secrets.

Ask only about unresolved material choices. Reuse supplied facts and authorization. If a material choice is unresolved and no human is available, or required CLI capabilities are absent, stop without mutation. Fully specified, authorized requests can proceed non-interactively. Save a Markdown draft with confirmed settings, literal draft instructions, unresolved choices, and the blocker in a dedicated local directory or the user's chosen location. Do not overwrite files or call an incomplete draft submit-ready. Resume by revalidating capabilities and IDs.

## Tell the user, then write

Before preparing the create request, show the complete configuration and literal saved instructions in an assistant message. Serialize those exact values; show a revised complete proposal if they change. Continue without another approval when creation is already authorized. Use this template:

```text
I will create:
Organization: ...
Name: ...
Display name: ...
Responsibility: ...
Role: ... (verified ID and scope)
MCP integrations: ... (verified IDs, or none)
Approval: ...
Invocation: ...
Saved instructions:
[complete literal instruction text]
```

Generate only instructions within the requested responsibility. When the user specifies a fixed resource boundary, preserve it without exceptions that let a future task expand it. For work outside that boundary, instruct the agent to report the dependency and ask for an explicitly revised responsibility, rather than investigate outside its scope. Before saving, compare the generated instructions with that boundary as well as the role and integrations. Serialize the displayed settings and instructions with a proper JSON serializer into a local file. Use CLI file input, not shell interpolation. If dry-run is supported, inspect it and compare it to the proposal message you sent. Dry-run checks request construction, not server authorization or agent readiness.

## Create and verify

Before submitting, confirm the complete proposal was shown in assistant text; if absent, show it now.

Submit one request. Retain the returned identity, GET it, and check active roster membership; GET may include deleted records. Compare name, display name, purpose, literal instructions, role, integrations, and approval mode. If persisted values differ, report exactly what was saved and what failed verification. Do not silently repair, recreate, broaden access, or delete as rollback.

After a timeout, creation is uncertain. Reconcile the intended name and exact configuration through supported reads before considering a retry. A match alone does not establish that this attempt created it. Use returned request/resource identifiers when available. If identity remains uncertain, show the candidate and ask whether to use it, or leave that choice open when headless. If no candidate appears, establish that the roster read is authoritative before considering a retry. Stop while uncertainty remains. Name uniqueness is not durable idempotency: deletion can release a name. A 409 does not authorize updates or renaming. A permission rejection does not authorize a fallback role.

Report the verified ID, organization, settings, and saved instructions or a link to the complete configuration. Use a service-returned URL only. Separate saved configuration from tested access and task success. Describe only actions actually observed in the command history and assistant messages.

## Always address automation

An unanswered automation preference does not block independently authorized agent creation. Keep that separate choice pending until the agent is verified. After verified creation, always address the automation choice. If the user has not already answered it, ask in your assistant response:

“Would you like to set up automation for this agent: a schedule, an event trigger, or no automation for now?”

Do not finish an ordinary agent-creation request without this question. It does not authorize automation by itself. If no human can answer, still include the question in the final response, leave the choice pending, and retain the verified agent without configuring automation.

An explicit schedule or event request already answers yes; read [Configure automation](references/configure-automation.md) and continue with the verified organization and saved agent ID. Keep the created agent if automation is blocked. An explicit decline already answers no; acknowledge manual invocation without asking again. Never treat silence as consent or decline. Defer automation-specific discovery and preparation until the agent is verified. Do not configure automation for an uncertain agent identity. For an explicitly requested immediate task, follow [additional outcomes](references/additional-outcomes.md); a one-time task does not answer the recurring-automation question.

Automation references: [API contract](references/automation-cli-contract.md) for supported request fields; [webhook handling](references/automation-webhook-secrets.md) before preparing a webhook; [recovery](references/automation-recovery.md) after an uncertain response or differing readback. Load these only for the relevant automation step.

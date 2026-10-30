# Configure automation

## 1. Verify the saved agent and supported route

Use the organization, returned agent ID/name, role, approval mode, and automation preference verified by the creation workflow. Do not recreate the agent or bind an uncertain or deleted identity.

Read [CLI contract](automation-cli-contract.md). Discover through `pulumi api list --filter AgentAutomation --output=json`, refreshing once if operations are absent. Describe every operation before using it. Require supported create, get, and list operations with explicit saved-agent binding. Never substitute internal HTTP, guessed commands, or an older operation with a different execution identity.

If support or authentication is missing, retain the verified agent and a Markdown automation draft with known settings, unresolved choices, and the exact blocker. A failed read does not prove absence. Do not claim a draft is configured automation.

## 2. Resolve the rule and access

Reuse supplied choices and authorization. Ask only for missing material choices:

- Schedule: frequency, time, named time zone, and fixed UTC versus local wall-clock behavior through daylight-saving changes. Validate cadence against the discovered contract. Ask if either is unresolved; do not guess a conversion.
- Event: source/type, organization/project/stack/repository identifiers, filters, and quiet period. Verify identifiers and sender readiness through supported reads. Do not substitute polling or a schedule. For the supported stack-operation contract, the first matching event dispatches immediately; the quiet period bounds event association with one task, not the first dispatch. Resolve unclear or conflicting expectations about first-event timing before activation. For an already specified, authorized rule, report these semantics with the result.
- Invocation: exact per-run task instructions, expected output, event-provided context, and requested notification destinations. Keep per-run text separate from the agent's reusable instructions. Event delivery does not establish investigation access.
- Activation: determine whether creation is active. If the user requires initially paused setup and create is active-only, stop before creation. Creating and immediately pausing exposes a firing window and does not meet that requirement. Manual approval can leave unattended work waiting for a person.
- CLI credentials: explicit selection is separate from MCP integrations and roles. The published V2 automation request accepts `task.cliIntegrations`: omitted inherits configured organization handles; `[]` selects none. Verify backend support, disclose inheritance, and resolve narrower-access requirements before creation. Do not broaden access or claim credentials were exercised merely because they were selected.

For webhooks, read [Secret handling](automation-webhook-secrets.md) before preparing any request. If protected request/response handling or required sender setup is unavailable, preserve a draft and stop before secret-bearing creation.

## 3. Check duplicates and prepare the request

List automations and follow all relevant pages within the authorized scope. An existing same-name automation does not authorize adoption or changes; report its ID and state and leave the decision open. Do not overwrite it or invent a suffix. Honor a request to report a duplicate and stop.

Serialize the resolved configuration using a proper JSON serializer and CLI file input. Include the nonempty returned `task.agentDefinitionId`, full literal task message, and resolved CLI selection. Omit task-level role, approval, permission-mode, and MCP overrides because they do not narrow the bound definition's settings. Dry-run if supported and compare the actual body with the user's request. Local preparation does not save an automation or establish server authorization. Stop if a material difference is unexplained. For webhooks, follow the protected request procedure; neither secrets nor the dry-run body may appear in the transcript.

## 4. Create the authorized automation once

Honor any explicit request to show the configuration before saving it. If the configuration is fully specified and already authorized, submit the prepared request once without requiring a repeated proposal or another approval. Retain the returned identity for verification.

If a material choice or authorization is missing, show the proposed configuration and ask before mutation. Include the actual saved agent identity, literal task instructions, rule, credential selection, notifications, and activation behavior needed to decide. Resolve any behavior that conflicts with the request, including first-event timing or an initially paused requirement. Never display secrets, broaden access, or treat silence as consent.

## 5. Verify and report observed results

GET the returned ID and verify list membership, bound agent, mode, literal task message, CLI selection, exact rule, notifications, and active/paused state. For a timeout, uncertain ownership, or differing readback, follow [Recovery](automation-recovery.md) before any further mutation.

Report actual agent/automation IDs, saved rule/state, remaining setup, and service-returned links only. Separate saved configuration from sender setup, event delivery, credential access, and task execution. Do not start a task, send an event, or wait for future execution unless requested.

When blocked on a decision, report verified IDs and state, explain unfinished work, and ask the actual unresolved question, including in headless output. Retain the agent and draft, and resume only the incomplete step. Silence does not authorize mutation.

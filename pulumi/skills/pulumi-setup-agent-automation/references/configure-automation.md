# Configure automation

## 1. Verify the agent

Confirm the organization and saved agent ID. Read the agent and check active roster membership; do not bind an uncertain or deleted identity. Reuse the creation workflow's verified settings when available.

Check `pausedAt`. A paused agent starts no new runs even when its automation is active. Report that state without resuming the agent.

Read [API contract](cli-contract.md) and discover the operations needed for setup. If a required API or access is unavailable, keep the agent and save an automation draft explaining the blocker.

## 2. Resolve the rule

Use the user's choices and ask for missing details:

- **Schedule:** cadence, time, and named time zone. The API uses UTC cron, so resolve whether the user wants fixed UTC time or local wall-clock time through daylight-saving changes.
- **Event:** source, target stacks or other identifiers, filters, and quiet period. For stack events, the first matching event dispatches immediately; `quietPeriodSeconds` groups later events with that task rather than delaying the first dispatch.
- **Task:** per-run instructions, expected output, event context, and notification destinations. Keep these instructions separate from the agent's reusable instructions.
- **CLI connections:** set `task.cliIntegrations` to the requested connections. Omission enables all organization CLI connections; `[]` enables none. This is separate from the agent's role and MCP integrations.

Check creation's activation behavior. If the user requires an initially paused automation and the API creates active resources only, save a draft instead. Creating and immediately pausing leaves a window in which it can run. A paused agent is not a substitute for a paused automation. Manual approval can also leave unattended work waiting for a person.

For webhooks, read [Webhook secrets](webhook-secrets.md) before preparing the request. Event delivery credentials do not establish the agent's access to investigate the event.

## 3. Prepare and create

List existing automations, following pagination. If the name is already used, show the existing ID and state and resolve whether the user means that automation or a new one.

Build the JSON request using the [API contract](cli-contract.md). Include the saved agent ID, complete task message, selected CLI connections, rule, and notifications. The agent supplies its role, approval mode, and MCP integrations; task-level overrides do not narrow those settings.

Inspect the dry-run request before submission, except for secret-bearing webhook requests, which use protected handling. Show a proposal if choices remain unresolved or the user asked to review it. Otherwise, create the already-authorized automation once and retain its ID.

## 4. Verify and report

Read the automation and verify list membership, agent binding, task message, CLI selection, rule, notifications, and paused state. Check the agent's pause state separately. If a field is not returned, report that verification limit.

Return the IDs and saved configuration, plus any remaining sender setup. Do not report successful execution from configuration alone or send a test event unless requested.

For a lost response or differing saved values, follow [Recovery](recovery.md). Keep the agent if automation setup fails.

# Automation API

Discover operations with `pulumi api list --filter AgentAutomation --output=json`. Refresh once with `--refresh-spec` if one is missing. Describe each operation needed for the task before using its fields.

| Operation | Purpose |
| --- | --- |
| `CreateAgentAutomationV2` | Create a schedule or trigger |
| `GetAgentAutomationV2` | Read saved configuration by `orgName` and `automationID` |
| `ListAgentAutomationsV2` | Check existing automations; follow continuation tokens |
| `UpdateAgentAutomationV2Paused` | Pause or resume future recurrence |

## Request fields

| Field | Meaning |
| --- | --- |
| `orgName` | Explicit organization parameter |
| `task.agentDefinitionId` | Saved agent ID; omission or an empty value can select another execution identity |
| `task.message` | A `user_message` event containing the literal task instructions; use the described schema for required event fields |
| `kind` | `scheduled` or `triggered` |
| `scheduleCron` | Five-field UTC cron; production minimum interval is ten minutes |
| `trigger` | Typed event rule. For `stack_operation`, supply operations, results, stacks, and `quietPeriodSeconds` |
| `task.cliIntegrations` | Omitted enables all organization CLI connections; `[]` enables none; a populated list selects connection instances by `catalogId` and `name` |
| `notificationTargets` | Destinations for run notifications |

Confirm accepted values and limits with describe. The bound agent supplies its role, approval mode, and MCP integrations on each turn. CLI connections are separate. If the API cannot express the requested cadence, access selection, or activation state, retain a draft rather than substituting another configuration.

## Create and read back

Write the resolved settings to `automation.json` using a JSON serializer. For schedules and stack-event triggers:

```sh
pulumi api CreateAgentAutomationV2 -F orgName=ORG --input automation.json --dry-run --output=json
```

Replace `ORG` with the verified organization. Compare the request with the chosen settings, then omit `--dry-run` to create. Use the returned ID with `GetAgentAutomationV2`, passing `orgName` and `automationID`.

Webhook requests and responses may contain secrets. Use [Webhook secrets](automation-webhook-secrets.md) instead of displaying their dry-run output.

## Pause or resume

Write `{"paused": true}` to a request file to pause, or `{"paused": false}` to resume. Call `UpdateAgentAutomationV2Paused` with that file and the verified `orgName` and `automationID`, then read back the state and unchanged rule.

This changes future recurrence, not tasks already created. It does not make an active-only create operation initially paused.

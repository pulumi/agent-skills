# Automation capability contract

On October 30, 2026, refreshed public API discovery exposed `CreateAgentAutomationV2`, `GetAgentAutomationV2`, `ListAgentAutomationsV2`, and `UpdateAgentAutomationV2Paused`. Describe confirmed the create and pause request shapes below. This verifies published schema availability, not organization entitlement, authorization, credential dispatch, or successful execution. Recheck the target backend before use.

Discover and describe the actual supported operations on the target backend. Never invoke an unsupported route merely because its name is known.

For a usable supported route, verify these semantics through describe and readback:

| Concern | Published contract to recheck |
| --- | --- |
| Organization | Explicit `orgName` parameter |
| Saved agent | Nonempty `task.agentDefinitionId`; omission or an empty value can select a different execution identity |
| Invocation instructions | `task.message` with a `user_message` type and literal content |
| Mode | `kind` selects scheduled or triggered; creation supplies the corresponding rule |
| Schedule | Five-field UTC `scheduleCron`, with a production minimum interval of ten minutes; no time-zone field in this request |
| Event | A typed `trigger` contract; discover accepted types and per-source settings rather than inventing them |
| Activation | The inspected create requests have no paused field and create active resources; pausing afterward leaves a real execution window |
| Reconciliation | Verify list scope, pagination, identity, and matching configuration; name matching is not durable idempotency |
| Execution access | The definition supplies role, approval, and MCP integrations each turn. CLI credentials are separate: the published V2 request accepts `task.cliIntegrations`. Omission inherits configured organization CLI handles; an explicit empty list selects none. Runtime dispatch was not exercised by the schema check. Do not claim the agent MCP selection bounds those credentials. |
| Webhook | Creation may include a one-time secret; later reads cannot be assumed to recover it |

A fixed UTC schedule can shift local execution time across daylight-saving changes. Resolve that choice rather than assuming the API supports a local time zone. If the user's cadence or initially paused requirement cannot be represented, preserve the draft and report the limitation.

Only after a supported operation family is discoverable should the harness construct a submission payload. Do not place guessed fields in an executable command. A saved automation does not demonstrate source delivery, external access, or completed work.

## Conditional CLI workflow

After the target backend lists these operations, describe each operation before use:

```sh
pulumi api list --filter AgentAutomation --refresh-spec --output=json
pulumi api describe CreateAgentAutomationV2 --output=json
pulumi api describe GetAgentAutomationV2 --output=json
pulumi api describe ListAgentAutomationsV2 --output=json
pulumi api describe UpdateAgentAutomationV2Paused --output=json
```

Serialize the resolved rule to a JSON file using the discovered schema, with a nonempty `task.agentDefinitionId` and `task.message` containing `type: user_message` and literal `content`. A scheduled rule uses `kind: scheduled` and `scheduleCron`; a stack event rule uses `kind: triggered` and a `stack_operation` trigger with operations, results, stacks, and `quietPeriodSeconds`. Follow [Configure automation](configure-automation.md) for existing-resource checks, secret handling, and when a proposal is required before mutation.

For schedules and stack-operation triggers, use `pulumi api CreateAgentAutomationV2 -F orgName=ORG --input automation.json --dry-run --output=json` to inspect the request, then omit `--dry-run` only when authorized to start active recurrence. Read back using `GetAgentAutomationV2` with `orgName` and `automationID`, and verify membership with `ListAgentAutomationsV2`, following continuation tokens. These are command templates; substitute only verified values.

Pause or resume through `UpdateAgentAutomationV2Paused` with the same identity parameters and a file containing `{"paused": true}` or `{"paused": false}`. Pausing stops future recurrence; it does not cancel tasks already created. It cannot provide an initially paused create.

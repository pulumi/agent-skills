# CLI contract and required capabilities

Discover the target backend's supported definition operations before constructing a request. Confirm `CreateAgentDefinition`, `GetAgentDefinition`, and `ListAgentDefinitions` through the public catalog and describe each available operation. Schema discovery does not establish caller authorization or successful creation.

```sh
pulumi api list --filter AgentDefinition --output=json --refresh-spec
pulumi api describe CreateAgentDefinition --output=json
pulumi api describe GetAgentDefinition --output=json
pulumi api describe ListAgentDefinitions --output=json
```

Recheck the target backend each time. Do not infer support from a newer CLI version, a task-creation operation, or an undocumented route. If discovery still lacks a required operation, preserve a Markdown draft and report the missing capability without mutation.

## Required reads and mutations

Discover and describe supported operations for each capability before using parameters or response fields:

| Capability | Required verification |
| --- | --- |
| List active agent definitions | Explicit organization scope, pagination if present, and treatment of deleted definitions |
| Create an agent definition | Supported request fields and response identity |
| Get an agent definition | Organization and definition identity, including active versus deleted state |
| List assignable roles and read grants | Exclude built-in Admin and Billing Manager; verify organization membership, caller assignment authority, returned role IDs, and actual grants |
| List configured MCP integrations | `ListAgentIntegrations` with explicit `orgName`; select entries from `integrations` where `configured` is true and use their `integrationId` |

The main skill names the role and integration read operations it requires. Describe them on the target backend; operation names alone do not establish availability or authorization. Obtain applicable team instructions from the user when no supported read exists. Requested tasks and triggers need separate capability checks.

## Integration selection

Discover `ListAgentIntegrations` in the target backend's public catalog and describe it before use. Refresh the catalog once if it is missing. After discovery confirms support, read it with the verified organization:

```sh
pulumi api describe ListAgentIntegrations --output=json
pulumi api ListAgentIntegrations -F orgName=ORG --output=json
```

The response includes the full catalog, not just connected tools. Filter `integrations` to entries with `configured: true`. Present their names to the user and serialize selected `integrationId` values as `enabledIntegrations: [{"id": "SELECTED_ID"}]`, using only verified IDs. An explicit selection of none is `enabledIntegrations: []`. Credential-field labels, placeholders, and help text describe connection setup; they are not credential values and do not establish that an integration is connected. Do not enable or configure a new connection as part of selecting existing integrations.

### If integration discovery is unavailable

If `ListAgentIntegrations` is still absent after one catalog refresh, or discovery, describe, or the read fails, stop before creating the agent. Preserve a local Markdown draft containing the resolved settings, complete saved instructions, requested integration selection, unresolved choices, and the exact failed operation. Do not discard completed preparation or call the draft a created agent.

Explain the observed failure precisely: an operation absent from the refreshed catalog is unavailable through that backend's published API; an authentication or permission error means the read could not be authorized; a timeout or other service error leaves connection status unverified. None of these establishes that the organization has no connected integrations. Do not guess IDs, substitute internal HTTP, omit `enabledIntegrations` to inherit all connections, or replace the requested selection with `[]`.

Report the saved draft location and the next step appropriate to the failure: retry discovery after API availability changes, resolve authentication or access, or retry the read after a transient failure. Resume from integration verification under the existing authorization, revalidating the organization and IDs before submission. Do not repeatedly retry during the same attempt.

For an operation missing from the refreshed catalog, use wording such as:

> I prepared the agent configuration, but this backend's public API does not currently expose the operation needed to list connected integrations. No agent was created. I saved the draft at [local path], including your requested integrations. Once the operation is available, I can verify those connections and continue from this step.

Adapt the explanation to the actual error; do not use the availability wording for an access failure or timeout.

## Request construction

Serialize the configuration using the discovered schema and CLI `--input` with a JSON file, not shell interpolation or `--body-file`.

Verify that the supported request can express the exact name, display name, responsibility, reusable instructions, eligible role, explicit MCP integration selection, and approval mode required by the main skill. Check limits, defaults, and accepted values through describe. If the contract cannot preserve a required setting or restriction, retain the draft and stop instead of guessing a field or dropping the restriction.

Do not assume omitted and empty integration selections mean the same thing. Resolve and serialize the intended selection. A role or instruction does not restrict separate external credentials or ESC access, and an empty MCP integration list does not disable CLI credentials.

If dry-run is supported, compare its body with the configuration and literal instructions already shown in assistant text. Dry-run checks request construction, not server authorization or agent readiness.

Parse the CLI’s actual response envelope rather than assuming a top-level ID. Use the returned identity for GET and compare persisted settings. Read the active roster again after creation; a successful GET alone does not establish that a definition is active. Follow the main skill’s recovery procedure after an uncertain response.

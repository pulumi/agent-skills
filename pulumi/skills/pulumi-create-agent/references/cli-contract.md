# Agent creation API

## Discover operations

Check `pulumi version` and `pulumi api --help`. Confirm the backend and account with `pulumi whoami -v`; if authentication is missing, resolve it before reading organization data.

Use `pulumi api list` to discover operations and `pulumi api describe OPERATION --output=json` to inspect their parameters and response fields. Refresh the catalog once with `--refresh-spec` if an operation is missing.

| Operation | Purpose |
| --- | --- |
| `ListAgentDefinitions` | Find existing names and verify active roster membership |
| `CreateAgentDefinition` | Create the saved agent |
| `GetAgentDefinition` | Read the returned ID and verify saved settings |
| `ListRolesByOrgIDAndUXPurpose` | Read organization roles with `uxPurpose=role` |
| `GetRole` | Check the selected role's grants using `roleID` |
| `ListAgentIntegrations` | Find connected MCP integrations |

Use explicit `orgName` parameters. Follow pagination where present. Exclude built-in Admin and Billing Manager roles and verify the caller may assign the selected role; holding a role alone does not establish assignment authority.

## Select integrations

Read `ListAgentIntegrations` for the organization. Its `integrations` array includes unconnected catalog entries too: offer only entries with `configured: true`.

Map selected `integrationId` values to `enabledIntegrations: [{"id": "SELECTED_ID"}]`. Set `enabledIntegrations: []` for no MCP integrations. Omitting the field inherits all organization integrations. Credential-field labels and help text describe connection setup; they do not mean an integration is connected.

This workflow selects existing connections. It does not configure new ones.

### If integration discovery is unavailable

If discovery, describe, or the integration read fails, stop before creation and save the configuration as a local draft. Preserve the requested selection, identify the failed operation, and explain what is needed to continue. A missing operation, denied access, and a timeout are different failures; none means the organization has no integrations.

Do not substitute internal endpoints, guessed IDs, all integrations, or an empty selection. Resume from verification when the API or access is available.

## Build and submit the request

Use the described schema to map the proposal to `name`, `displayName`, `purpose`, `customInstructions`, `roleId`, `enabledIntegrations`, and `approvalMode`. Check accepted values and limits. Obtain missing team instructions from the user when no supported read exists.

Write the exact displayed values to a JSON file with a JSON serializer, then pass it through `--input`:

```sh
pulumi api CreateAgentDefinition -F orgName=ORG --input agent.json --dry-run --output=json
```

Replace `ORG` with the verified organization. Compare the dry-run body with the proposal, then omit `--dry-run` to create the agent. Dry-run checks request construction, not server authorization.

Read the response using the described response shape, retain the returned agent ID, and verify it with `GetAgentDefinition` and the active roster. A GET alone may return a deleted definition. Follow the creation skill's recovery guidance if the request times out or saved values differ.

# CLI contract and required capabilities

On October 30, 2026, refreshed `AgentDefinition` discovery returned zero operations on the checked public schema. Task creation and V2 automation operations are discoverable, but they do not supply reusable-agent definition create/get/list. The complete creation workflow must remain blocked until the target backend exposes those capabilities.

```sh
pulumi api list --filter AgentDefinition --output=json --refresh-spec
```

Recheck the target backend each time. Do not infer support from a newer CLI version, a task-creation operation, or an undocumented route. If discovery still lacks a required operation, preserve a Markdown draft and report the missing capability without mutation.

## Required reads and mutations

Discover and describe supported operations for each capability before using parameters or response fields:

| Capability | Required verification |
| --- | --- |
| List active agent definitions | Explicit organization scope, pagination if present, and treatment of deleted definitions |
| Create an agent definition | Supported request fields and response identity |
| Get an agent definition | Organization and definition identity, including active versus deleted state |
| List assignable roles and read grants | Caller eligibility, returned role IDs, and actual grants |
| List configured MCP integrations | Returned integration IDs and accepted reference shape |

The main skill names the role and integration read operations it requires. Describe them on the target backend; operation names alone do not establish availability or authorization. Obtain applicable team instructions from the user when no supported read exists. Requested tasks and triggers need separate capability checks.

## Request construction

Serialize the configuration using the discovered schema and CLI `--input` with a JSON file, not shell interpolation or `--body-file`.

Verify that the supported request can express the exact name, display name, responsibility, reusable instructions, eligible role, explicit MCP integration selection, and approval mode required by the main skill. Check limits, defaults, and accepted values through describe. If the contract cannot preserve a required setting or restriction, retain the draft and stop instead of guessing a field or dropping the restriction.

Do not assume omitted and empty integration selections mean the same thing. Resolve and serialize the intended selection. A role or instruction does not restrict separate external credentials or ESC access, and an empty MCP integration list does not disable CLI credentials.

If dry-run is supported, compare its body with the configuration and literal instructions already shown in assistant text. Dry-run checks request construction, not server authorization or agent readiness.

Parse the CLI’s actual response envelope rather than assuming a top-level ID. Use the returned identity for GET and compare persisted settings. Read the active roster again after creation; a successful GET alone does not establish that a definition is active. Follow the main skill’s recovery procedure after an uncertain response.

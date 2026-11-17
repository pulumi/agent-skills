# Start a first task

Use this procedure only when the user asks for an immediate task in addition to creating the agent.

Discover and describe `CreateTasks`, `GetTask`, `ListTasks`, and `GetTaskEvents` on the target backend. Use the verified organization and saved agent ID. Keep the task within the agent's responsibility.

Choose which CLI connections the task may use, separately from the agent's role and MCP integrations. Set `cliIntegrations` explicitly: omitting it enables all configured CLI connections; `[]` enables none. Use the requested connections and explain this default before submission. If the API cannot apply the selection, keep the task as a draft.

Write the task message, agent ID, and CLI selection to a JSON request file using the described schema. Submit with `--input` and retain the returned `taskId`.

Read the task back to verify its agent binding and status. Use task events to check the initial message if `GetTask` does not expose it. Report any field, such as CLI selection, that the API does not return rather than claiming it was verified. Check execution within a bounded wait and distinguish task creation from successful completion.

If creation times out, use task list and get operations to reconcile the outcome before retrying. Follow all pages and use returned identifiers where available; matching text alone does not establish which request created a task. If the result remains uncertain, report the candidate IDs and states without retrying or cancelling them.

Keep the created agent if task setup fails. Resume only the unfinished step. A first task does not replace the creation skill's question about recurring automation.

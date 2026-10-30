# Requested immediate task

Read this when the user explicitly asks for a first task in addition to creating the agent. Creation alone does not authorize a task.

Discover and describe the supported task creation and read operations. Use the verified organization and saved agent ID; do not switch execution identity. Resolve the literal task instructions and required access before submission. Keep the task within the agent’s saved responsibility.

Verify the supported task operation’s CLI credential-selection semantics separately from MCP integrations and roles. Reuse an explicit user selection and serialize the resolved selection, including an explicit empty list for no CLI credentials when supported. If a required restriction cannot be expressed or verified through the supported contract, retain the agent and task draft and stop before creating the task. Use a proper JSON serializer and CLI file input. Inspect the prepared request, and honor any explicit request to show it first without requiring another approval for fully specified, already-authorized work.

On October 30, 2026, the public catalog exposed `CreateTasks`, `GetTask`, `ListTasks`, and `GetTaskEvents`. `CreateTasks` documents the CLI selection semantics above and returns `taskId`. `GetTask` exposes the agent binding and status, but not CLI selection or the initial message. Use supported event reads for the visible initial message and report the CLI-selection readback limit. Recheck these contracts on the target backend.

Before submission, state the resolved CLI selection and explain that omitting it inherits configured organization handles when that is the supported contract. Do not silently inherit credentials.

Submit once, retain the returned task ID, and use supported reads to verify the saved agent binding, literal task instructions, and CLI selection where exposed. If readback does not expose a field, report that verification limit instead of claiming it was verified. Check execution within a bounded wait. Task creation does not establish task success or usable credentials. Report access errors without broadening permissions automatically.

After a timeout or lost create response, creation is uncertain, not a confirmed failure. Do not repeat the create call. Reconcile through supported task reads for the verified organization and agent, following relevant pagination. Use operation-bound returned identifiers when available; matching instructions or timing alone do not establish ownership. Report candidate IDs and states without adopting, cancelling, or retrying while identity remains uncertain. If supported reads cannot resolve the outcome, stop and retain that uncertainty, including in a headless final response. Before considering a retry after finding no candidate, establish that the reads have authoritative scope and visibility; absence from an incomplete listing is not proof of failure.

Retain the created agent ID if task setup fails. Resume only a known incomplete step under existing authorization; do not recreate the agent, delete it as rollback, or resubmit uncertain task creation. If an operation is unsupported, report the capability gap without substituting internal HTTP.

An immediate task is separate from recurring automation. Still address the schedule/event/no-automation choice in the parent skill. For schedules and triggers, read [Configure automation](configure-automation.md), or use skill `pulumi-setup-agent-automation` when it is available.

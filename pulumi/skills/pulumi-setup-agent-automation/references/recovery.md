# Automation recovery

Keep the agent and known automation IDs. Fix only the unfinished step; do not recreate the agent or delete it as a rollback.

## Saved settings differ

Report the automation ID, requested versus saved values, and active or paused state. An active automation may run with the saved settings. Ask whether to pause that ID unless the pause is already authorized.

For an authorized pause, follow [Pause or resume](../SKILL.md#pause-or-resume-an-existing-automation).

## Create response was lost

Use `ListAgentAutomationsV2` and `GetAgentAutomationV2` to check whether creation succeeded. Follow all relevant pages. Use returned request or resource identifiers where available; a matching name or configuration alone does not establish which request created it.

If the outcome remains uncertain, report candidate IDs and states without retrying, adopting, or automatically pausing them. Explain that active candidates may run and ask whether the user wants a specific ID paused. A failed or incomplete read is not proof that nothing was created.

## Resume later

Retain the draft, confirmed IDs, and unresolved choices. Resume the incomplete step after the required decision or access is available. Distinguish saved configuration from sender setup and actual task execution.

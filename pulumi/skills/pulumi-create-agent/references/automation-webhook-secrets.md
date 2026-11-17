# Webhook secrets

Arrange delivery of webhook credentials to the sender before creating the automation.

Keep signing credentials and response secrets out of chat, command arguments, and dry-run output. Read request credentials directly from an authorized private source into a protected request file.

## Capture the response

Disable shell tracing, set `umask 077`, and create a unique directory with `mktemp -d`. Redirect create stdout to a new file there. Extract only the ID and other nonsecret fields for reporting; transfer the secret directly to the authorized sender configuration without printing the complete response.

If protected capture or required sender setup is unavailable, keep a draft and explain what is missing before creation.

Report which sender setup steps are complete. Delivery permission is separate from the agent's access to investigate the event.

# Webhook secrets

Read this before preparing a webhook request. Keep request signing credentials and response secrets outside chat, model-visible reads or writes, command arguments, and dry-run output. Inject request credentials from an authorized private source directly into a protected request file. If protected construction or required sender setup is unavailable, retain a draft and stop before creation.

## Protected response capture

Webhook creation may return a one-time secret. Verify protected capture with nonsecret fixture data first. A shell harness can set `umask 077`, create a unique private directory with `mktemp -d`, and redirect create stdout into a new response file inside it. Disable shell tracing. Keep the file path private and never print or read the whole file through model-visible tools. Extract only allowlisted nonsecret fields for reporting, and transfer the secret directly to the authorized sender configuration.

If the harness cannot ensure capture and direct transfer, stop before creating the webhook. Do not display secret-bearing dry-run output, automatically retry after a response error, regenerate or rotate a secret, or recreate the resource to recover a missing response. Reconcile uncertain creation through supported nonsecret reads.

Webhook capture and sender setup remain unvalidated. Sender delivery permission does not establish investigation access.

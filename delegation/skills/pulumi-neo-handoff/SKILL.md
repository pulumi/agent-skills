---
name: pulumi-neo-handoff
description: Hand off the current thread to a new Pulumi Neo task as a one-way transfer. Use when the user explicitly asks to hand off, send, transfer, or continue current work in Pulumi Neo (e.g. "hand this to Neo", "continue in Neo", "/neo-handoff"). Do not load when the user only mentions Neo, asks what Neo can do, asks for an AI-written PR or preview explanation, or hands off to a different agent.
---

# Pulumi Neo Handoff

Transfer the current in-progress work to a new Pulumi Neo task. This is a one-way handoff: control passes to Neo and does not return to the calling agent.

## Calling agent behavior

When this skill activates, act as a handoff coordinator, not the operator:

- Do not narrate the handoff turn-by-turn. The user has decided; carry it out quietly.
- Do not paste the assembled prompt body into chat. Show only the temp file path so the user can inspect on demand.
- Do not continue working on the task after launching. Exit cleanly once the task URL is returned.

## What gets transferred

The Neo task receives a single opening prompt with three sections:

1. **Goal** — one sentence describing what Neo should do next.
2. **Repository pointers** — repo root, branch, working directory, working-tree state, and 3 to 5 files most relevant to the in-progress work.
3. **Conversation summary** — a compact account of what has been discussed, decided, and left open.

Do not include diffs, full file contents, or tool output. Neo sees the local working tree directly (including uncommitted changes); duplicating that content wastes Neo's opening context.

## Workflow

### 0. Preflight

Verify the CLI is available before drafting anything:

```bash
command -v pulumi >/dev/null || { echo "pulumi CLI not installed"; exit 1; }
pulumi neo --help >/dev/null 2>&1 || { echo "pulumi neo unavailable — run 'pulumi login' or upgrade the CLI"; exit 1; }
```

If preflight fails, surface the error to the user and stop. Do not assemble the prompt only to fail at launch.

### 1. Determine the goal

The goal is one sentence describing what Neo should do next. If the user's handoff message contains it ("hand this off to Neo and apply the staging migration"), use it directly. Otherwise ask once: "What would you like Neo to do next?"

Do not restate the goal back for confirmation — the handoff should feel seamless, and if Neo receives a misread goal the user can redirect inside the Neo task.

### 2. Gather repository context

Capture the canonical repo pointer and branch state:

```bash
git rev-parse --show-toplevel    # repo root (canonical pointer)
git rev-parse --abbrev-ref HEAD  # branch; returns "HEAD" if detached
git status --short               # working-tree summary
```

If `git rev-parse --show-toplevel` fails the directory is not a git repo — omit the Repository section and note the working directory only. Neo can still operate, but its repo context will be limited.

If the branch reads `HEAD`, record the commit SHA and label the entry "detached at `<sha>`".

Identify 3 to 5 files most relevant to the in-progress work from the conversation (files read, edited, or repeatedly discussed). If the conversation does not clearly identify files, list none rather than guessing — wrong files mislead Neo more than missing files do.

### 3. Draft the conversation summary

Write a compact summary against the structure below. Sections with nothing useful to say should be omitted, not padded.

```
## What's been done
<bullets: decisions made, code changed, dead ends ruled out>

## Open questions
<bullets: things the user has not resolved>

## Next step
<one or two sentences describing what Neo should do first>
```

Target ~400 words for the summary. Compress aggressively. The goal is to give Neo enough to pick up cleanly, not to replay the conversation.

### 4. Assemble the prompt and write to a temp file

Combine the three sections into a single markdown document. Use `mktemp` for a portable temp path:

```bash
PROMPT_FILE="$(mktemp -t neo-handoff.XXXXXX.md)"
```

Shape:

```markdown
# Goal
<one-sentence goal>

# Repository
- Root: <repo root>
- Branch: <branch or "detached at <sha>">
- Working directory: <cwd>
- Working tree: <clean | dirty>
- Files in play:
  - <file 1>
  - <file 2>

# Conversation summary
<summary from step 3>
```

### 5. Launch

Print the temp file path with a one-line size summary so the user can inspect on demand:

```
Prompt written to <PROMPT_FILE> (<line count> lines, <byte count> bytes).
Launching Neo task...
```

Invoke the CLI:

```bash
pulumi neo "$(cat "$PROMPT_FILE")"
```

`pulumi neo` accepts the prompt as a single positional argument; it has no `--file` flag, and stdin redirection launches the TUI instead of consuming the prompt. The `"$(cat ...)"` form captures the file's bytes as data (the shell does not re-evaluate `$`, backticks, or `\` inside command substitution) and passes them as one argument. Do not "fix" this to `pulumi neo --file ...` or `pulumi neo < ...` — both forms are broken against the current CLI.

If the CLI exits non-zero, surface its stderr verbatim and leave the prompt file in place so the user can retry. Do not pretend the handoff succeeded.

### 6. Surface the task URL

The CLI prints a task URL on success. Echo it verbatim. Then stop.

## What not to do

- **Do not invoke this skill without explicit handoff intent.** Detecting infrastructure-shaped work is not a trigger; capability questions like "can Neo do X" are not handoffs. Activating on those would make the skill noisy and incorrect.
- **Do not include diffs, file contents, or command output in the prompt.** Neo sees the local working tree directly, so duplicating that content wastes its opening context.
- **Do not paste the assembled prompt into chat for confirmation.** Summaries can be long; the file path is sufficient for the user to inspect when they care.
- **Do not commit, push, or modify the working tree on the user's behalf.** The user owns their git state — the skill is a context handoff, not a workflow controller.

## Notes

- One-way handoff. Control passes to the Neo task and does not return to the calling agent.
- Neo tasks are interruptible. If the summary turns out to be wrong, the user can redirect inside the Neo task; the skill does not need to guard against summary errors at launch time.
- Surfacing the task URL is the skill's success criterion, not successful completion of the underlying work. Neo may decline or redirect the request inside the task.

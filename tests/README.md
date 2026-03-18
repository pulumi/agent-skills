# Drift Adoption Test Framework

## Overview

This test framework evaluates how well an AI agent performs **infrastructure drift adoption** — detecting when deployed cloud resources have diverged from their Pulumi source code, then modifying the code to match the actual infrastructure state.

Tests run in two modes:

- **Skill-assisted**: The agent receives `SKILL.md` with instructions to use the `drift-adopter` CLI tool
- **Baseline**: The agent receives no skill — it must figure out how to detect and fix drift on its own

Both modes use the same agent implementation (`ClaudeCodeAgent`) and the same sandboxing setup.

## Directory Structure

```
tests/
├── conftest.py                          # Pytest fixtures, hooks, agent construction
├── sandbox_config.py                    # srt + permission deny rule configuration
├── claude_code_agent.py                 # ClaudeCodeAgent: SDK wrapper for Claude Code CLI
├── anthropic_agent.py                   # Agent ABC (interface shared by all agent implementations)
├── drift_adoption_helpers.py            # Worktree management, drift creation, evaluation
├── utils.py                             # query_auto_approve() for running agent with auto-approval
├── metrics.py                           # TestMetrics/AgentMetrics dataclasses, JSON output, summary table
├── generate_complex_drift.py            # Generates drifted TypeScript at test time (random seed)
├── llm_judge.py                         # LLM-based semantic evaluation (Claude Sonnet)
├── analyze_logs.py                      # Agent message log analyzer (timelines, tool usage, stuck points)
├── compare_metrics.py                   # Skill vs baseline metrics comparison table
│
├── test_complex_drift.py                # Skill-assisted complex drift tests (parametrized matrix)
├── test_complex_drift_baseline.py       # Baseline complex drift tests (same matrix, no skill)
│
└── drift-adoption/                      # Static test fixtures (Pulumi projects)
    ├── complex-20-full/                 # 20-resource project, 100% drift (empty original)
    ├── complex-40-full/
    ├── complex-60-full/
    ├── complex-100-full/
    ├── complex-20-50pct/                # 20-resource project, 50% drift
    ...                                  # etc. — 12 fixtures total (4 scales × 3 drift levels)
```

## Complex Drift Tests

All active tests are **complex drift** tests: local-only providers (`random`, `command`, `tls`) across a matrix of scales and drift levels. No cloud credentials required.

### Test matrix

| Scale | Full (100%) | 50% | 15% |
|-------|-------------|-----|-----|
| 20 resources | `scale-20-full` | `scale-20-50pct` | `scale-20-15pct` |
| 40 resources | `scale-40-full` | `scale-40-50pct` | `scale-40-15pct` |
| 60 resources | `scale-60-full` | `scale-60-50pct` | `scale-60-15pct` |
| 100 resources | `scale-100-full` | `scale-100-50pct` | `scale-100-15pct` |

**Drift levels:**
- **100% ("full")**: Original program is empty — all resources exist only in infrastructure. Pure adoption.
- **50%**: Half the resources have drift (property changes, deletions, creations).
- **15%**: Light drift scattered across multiple types.

**Complexity vectors** (what makes these fixtures harder than simple tests):
- 12 resource types across 3 providers (not uniform)
- Cross-resource references: cert chains, command triggers, random keepers
- Varied properties per instance (different lengths, optional fields)
- Nested objects and arrays (`subjects`, `allowedUses`, `dnsNames`)
- Realistic naming (`web-ca-key`, `api-password`, not `cmd-0`)

### Drifted code is generated at test time

Unlike static `drifted/index.ts` fixtures, complex drift tests call `generate_drifted_code(scale, drift_pct)` at runtime with a random seed. The generated code is written to a temporary `drifted/` directory, deployed to create infrastructure drift, then **deleted before the agent runs** so the agent can't read the answers.

## How Drift Testing Works

Every test follows this lifecycle:

```
1. Create git worktree          ← Isolated copy of the repo on a fresh branch
2. pulumi up (original)         ← Deploy original program (empty for 100% drift)
3. Generate drifted code        ← Runtime-generated TypeScript written to drifted/
4. Swap source → drifted/       ← Replace index.ts with drifted version
5. pulumi up (drifted)          ← Infrastructure now matches drifted code
6. Revert source → original     ← Code says one thing, infra says another = DRIFT
7. Delete drifted/ dirs         ← Remove generated answers so agent can't cheat
8. Invoke agent                 ← Agent detects and fixes drift
9. Evaluate results             ← Deterministic preview verification
10. Teardown                    ← Destroy stack, cleanup worktree
```

Steps 1–7 are handled by `drift_test_context()` and `create_drift_with_program()` in `drift_adoption_helpers.py`.

## Agent Implementation

### `ClaudeCodeAgent` (`claude_code_agent.py`)

Both skill and baseline tests use `ClaudeCodeAgent`, which wraps the `claude-agent-sdk` to run the full **Claude Code CLI** with all built-in tools: Read, Write, Edit, Glob, Grep, Bash, WebFetch, WebSearch, Skill.

Unlike `AnthropicAgent` (a minimal Anthropic SDK wrapper), `ClaudeCodeAgent` gives the agent the same tool set it would have in a real Claude Code session.

Key options passed to the SDK:
- `permission_mode="bypassPermissions"` — tool calls don't prompt for approval
- `setting_sources=None` — no filesystem skills loaded (skills must be injected via `custom_instructions`)
- `disallowed_tools=["Bash(pulumi up)", "Bash(pulumi destroy)"]` — hard-blocked for all tests
- `sandbox=...` and `settings=...` — sandbox and deny rules (see below)

### Agent construction (`conftest.py`)

`_make_claude_code_agent(baseline=False)` creates the agent:

**Skill test** (`agent` fixture):
- Loads `SKILL.md` as `custom_instructions`
- No extra `disallowed_tools`

**Baseline test** (`agent_no_skill` fixture):
- No skill instructions; only a directory-scoping instruction
- `disallowed_tools=["Skill"]` — prevents loading skills at runtime
- Extra Bash deny rules blocking the drift-adopter CLI (see Sandbox section)

## Sandbox and Permission Configuration

Both skill and baseline tests run with two layers of isolation, configured in `sandbox_config.py`.

### Layer 1: srt — OS-level sandbox (macOS Seatbelt)

Configured via `ClaudeAgentOptions.sandbox`:

```python
{
    "enabled": True,               # Wrap every Bash call in a Seatbelt profile
    "autoAllowBashIfSandboxed": True,   # Don't prompt for Bash in bypassPermissions mode
    "allowUnsandboxedCommands": False,  # Disable the dangerouslyDisableSandbox escape hatch
    "network": {
        "allowLocalBinding": True,      # Allow localhost binding for pulumi's local gRPC server
    },
}
```

srt restricts filesystem access and blocks outbound network at the **syscall level**, covering anything that goes through a shell — `curl`, `cat`, `which`, `git log`, etc.

### Layer 2: Permission deny rules — tool-level blocks

Configured via `ClaudeAgentOptions.settings` (JSON string merged with sandbox config by the SDK):

**Applied to all tests (skill + baseline):**
```json
{ "permissions": { "deny": [
    "WebFetch(domain:github.com)",
    "WebFetch(domain:api.github.com)",
    "WebFetch(domain:raw.githubusercontent.com)"
]}}
```
Blocks the agent from fetching the agent-skills repo, browsing commits, or reading raw files from GitHub via Claude Code's built-in WebFetch tool.

**Baseline tests only — additional deny rules:**
```json
{ "permissions": { "deny": [
    "Bash(pulumi plugin run drift-adopter*)",
    "Bash(pulumi-drift-adopt*)",
    "Bash(drift-adopt*)",
    "Bash(which pulumi-drift-adopt*)",
    "Bash(which drift-adopt*)"
]}}
```
Blocks the drift-adopter CLI tool and its discovery (`which`) so the baseline agent can't find and use the tool it isn't supposed to have.

### Why two layers?

| Cheat vector | srt (OS-level) | Deny rule (tool-level) |
|---|---|---|
| `pulumi-drift-adopt` via Bash | ✓ | ✓ |
| `which pulumi-drift-adopt` | ✓ | ✓ |
| `curl github.com` via Bash | ✓ | — |
| WebFetch to github.com | — | ✓ |

srt catches shell-level escapes; deny rules catch Claude Code's built-in tools (WebFetch, etc.) which bypass the shell.

## Logging

### Agent message log (`.test-output/logs/<test>.log`)

Enabled with `--log-messages DIR`. Captures per-turn:
- `[PROMPT]` — the initial user prompt
- `[OPTIONS]` — cwd, model, sandbox_enabled, settings JSON
- `[ASSISTANT (iter N)]` — assistant text
- `[TOOL_CALL (iter N): ToolName]` — tool call inputs
- `[RESULT]` — final turn count, duration, cost, error status
- `[STDERR]` — any stderr from the Claude Code CLI process

### Tool results log (`.test-output/logs/<test>.results.log`)

Companion file capturing tool return values — logged separately because results can be very large (full file contents, command outputs). Each entry is labeled `[TOOL_RESULT: <tool_use_id>]` or `[TOOL_RESULT [ERROR]: <tool_use_id>]`.

Cross-reference with the `.log` file by `tool_use_id` to trace a specific tool call end-to-end.

## Evaluation

### Skill tests — deterministic preview

After the agent finishes, `pulumi preview` is run. The test asserts zero pending changes. If the agent correctly adopted all drift into code, the preview shows no updates, creates, or deletes.

### Baseline tests — drift reduction

Baseline tests do **not** require full drift resolution. Instead they measure how much drift was reduced: `remaining_drift_count / initial_drift_count`. The test passes if zero remaining changes (same bar as skill), but partial reduction is tracked in metrics for comparison.

## Running Tests

### Prerequisites

| Variable | Description |
|----------|-------------|
| `PULUMI_ACCESS_TOKEN` | Pulumi Cloud access token |
| `GITHUB_TOKEN` | GitHub token (for git worktree operations) |
| `ANTHROPIC_API_KEY` | Anthropic API key (for the agent) |

Complex drift tests use local providers only — no AWS or cloud credentials required.

### Commands

```bash
# Install dependencies
just sync

# Run complex drift skill + baseline in parallel
just test-complex-vs-baseline

# Run a specific scale/pct pair (skill + baseline)
just test-complex-vs-baseline-one scale-20-full
just test-complex-vs-baseline-one scale-40-50pct

# Run skill tests only
just test-complex

# Run baseline tests only
just test-complex-baseline

# Run a specific skill test
just test-complex-one scale-60-full

# Compare skill vs baseline metrics
just compare-complex

# Analyze agent behavior
just analyze-complex
```

With env vars (as required by `CLAUDE.local.md`):

```bash
PULUMI_ACCESS_TOKEN=$JDAVENPORT_PULUMI_CORP_PULUMI_ACCESS_TOKEN \
GITHUB_TOKEN=$(gh auth token) \
ANTHROPIC_API_KEY=$_ANTHROPIC_API_KEY \
PULUMI_OPTION_DEFAULT_ORG=pulumi \
PULUMI_ENABLE_JOURNALING=true \
  just test-complex-vs-baseline-one scale-20-full 2>&1 | tee .test-output/test-run.log
```

### Pytest markers

| Marker | Description |
|--------|-------------|
| `integration` | All integration tests |
| `write_permissions` | Tests that modify infrastructure |
| `complex_drift` | Complex drift tests (local providers) |
| `baseline` | Tests without skill (raw LLM) |

## Metrics

### What's collected

Per-test via `TestMetrics` and `AgentMetrics`:

- **Test timing**: Total wall-clock time
- **Agent timing**: Time spent in agent query
- **Iterations**: Number of tool-use turns
- **Token usage**: Input, output, cache creation, cache read
- **Peak memory**: RSS high-water mark during agent execution
- **Resource count**: Number of Pulumi resources in the stack
- **Initial/remaining drift count**: Changes before and after the agent runs
- **Pass/fail**: Whether the test succeeded

### Output locations

| Path | Contents |
|------|----------|
| `.test-output/metrics/<test>.json` | Per-test metrics JSON |
| `.test-output/logs/<test>.log` | Agent turns, tool calls, STDERR |
| `.test-output/logs/<test>.results.log` | Tool return values |
| `.test-output/test-run.log` | Pytest stdout/stderr (when using `tee`) |

All output directories are gitignored.

## Key Components

### `sandbox_config.py`

`build_sandbox_config(baseline=False)` returns `(sandbox_dict, settings_json)`. Both are passed to `ClaudeAgentOptions` in `ClaudeCodeAgent._build_options()`. See [Sandbox and Permission Configuration](#sandbox-and-permission-configuration) above.

### `drift_adoption_helpers.py`

Core test infrastructure:

- `drift_test_context()` — context manager orchestrating the full setup/teardown flow
- `create_drift_with_program()` — deploys drifted code then reverts source
- `scrub_drifted_dirs()` — removes `drifted/` directories before the agent runs
- `verify_drift_exists()` / `verify_drift_resolved()` — pre/post assertions
- `count_drift_changes()` — counts pending changes from `pulumi preview`
- `build_drift_prompt()` — formats the agent prompt with working directory and instructions

### `generate_complex_drift.py`

Generates TypeScript programs for a given `(scale, drift_pct)` pair at test runtime. The generated code uses 12 resource types with cross-resource references, varied properties, and realistic names. The drifted variant introduces property changes, resource deletions, and resource creations according to the drift percentage.

### `utils.py`

`query_auto_approve(agent, prompt)` — runs the agent and automatically approves all tool calls. Collects metrics (tokens, timing, memory) and returns `(response, tool_calls, AgentMetrics)`.

### `compare_metrics.py`

Compares skill vs baseline test metrics from the JSON files in `.test-output/metrics/`. Pairs tests by naming convention (`test_X[param]` ↔ `test_X_baseline[param]`). Outputs delta percentages for timing, iterations, and tokens.

```bash
just compare-complex
```

### `analyze_logs.py`

Analyzes agent message logs for iteration timelines, tool usage histograms, phase breakdowns, and stuck-point detection.

```bash
just analyze-complex                # matrix summary
just analyze-compare                # side-by-side skill vs baseline
uv run tests/analyze_logs.py .test-output/logs/test_complex_drift\[scale-20-full\].log  # single file
```

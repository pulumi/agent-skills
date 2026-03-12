# Drift Adoption Test Framework

## Overview

This test framework evaluates how well an AI agent performs **infrastructure drift adoption** — detecting when deployed cloud resources have diverged from their Pulumi source code, then modifying the code to match the actual infrastructure state.

Tests run in two modes:

- **Skill-assisted**: The agent receives `SKILL.md` with instructions to use the `drift-adopter` CLI tool
- **Baseline**: The agent receives no skill — it must figure out how to detect and fix drift on its own

And at two scale tiers:

- **Standard** (AWS S3, 1–3 resources): Tests property changes and resource deletions against real AWS infrastructure
- **Large-scale** (local providers, 250–1000 resources): Tests drift adoption at scale using `random`, `command`, and `tls` providers — no cloud credentials needed

## Directory Structure

```
tests/
├── conftest.py                          # Pytest fixtures and hooks
├── drift_adoption_helpers.py            # Worktree management, drift creation, evaluation
├── anthropic_agent.py                   # Minimal Anthropic SDK agent with MCP tool support
├── utils.py                             # query_auto_approve() for running agent with auto-approval
├── metrics.py                           # TestMetrics/AgentMetrics dataclasses, JSON output, summary table
├── llm_judge.py                         # LLM-based semantic evaluation (Claude Sonnet)
├── simple_shell_mcp.py                  # FastMCP shell server providing shell_execute tool
├── generate_large_scale.py              # Generates large-scale test fixtures (250–1000 resources)
├── analyze_logs.py                      # Agent message log analyzer (timelines, tool usage, stuck points)
├── compare_metrics.py                   # Skill vs baseline metrics comparison table
│
├── test_drift_adoption.py               # Skill-assisted tests (standard scale)
├── test_drift_adoption_baseline.py      # Baseline tests (standard scale, no skill)
├── test_drift_adoption_large_scale.py   # Skill-assisted tests (large scale)
├── test_drift_adoption_large_scale_baseline.py  # Baseline tests (large scale, no skill)
│
├── pulumitest/                          # Pulumi Automation API wrapper
│   ├── __init__.py
│   ├── program.py                       # PulumiProgram class (up/preview/refresh/destroy)
│   ├── opttest.py                       # Test option dataclasses and helpers
│   └── results.py                       # PreviewResult, UpdateResult, RefreshResult wrappers
│
└── drift-adoption/                      # Test fixtures
    ├── simple-s3/                       # 1 S3 bucket, drift = tag addition
    │   ├── index.ts
    │   ├── drifted/index.ts
    │   ├── Pulumi.yaml, Pulumi.test.yaml, package.json, tsconfig.json
    │
    ├── multi-resource/                  # 3 S3 buckets, drift = resource deletion
    │   ├── index.ts
    │   ├── drifted/index.ts
    │   └── ...
    │
    ├── loop-resources/                  # 3 buckets from array, drift = element removal
    │   ├── index.ts
    │   ├── drifted/index.ts
    │   └── ...
    │
    ├── large-scale-250/                 # 250 resources, ~15% drift
    │   ├── index.ts
    │   ├── drifted/index.ts
    │   └── ...
    ├── large-scale-500/                 # 500 resources, ~15% drift
    ├── large-scale-750/                 # 750 resources, ~15% drift
    └── large-scale-1000/               # 1000 resources, ~15% drift
```

Each fixture has `index.ts` (the original code) and `drifted/index.ts` (a modified version used during setup to create real infrastructure drift).

## How Drift Testing Works

Every test follows this lifecycle:

```
1. Create git worktree          ← Isolated copy of the repo
2. pulumi up (original)         ← Deploy original index.ts
3. Swap source → drifted/       ← Replace index.ts with drifted version
4. pulumi up (drifted)          ← Infrastructure now matches drifted code
5. Revert source → original     ← Code says one thing, infra says another = DRIFT
6. Scrub drifted/ dirs          ← Remove evidence so agent can't cheat
7. Invoke agent                 ← Agent detects and fixes drift
8. Evaluate results             ← LLM judge or deterministic preview
9. Teardown                     ← Destroy stack, cleanup worktree
```

Steps 1–6 are handled by `drift_test_context()` and `create_drift_with_program()` in `drift_adoption_helpers.py`. The git worktree ensures each test runs in complete isolation from the working tree.

## Test Categories

### Skill tests (`test_drift_adoption.py`)

The agent has `SKILL.md` loaded, which instructs it to use the `drift-adopter` CLI tool. Results are evaluated with an **LLM judge** that checks whether the agent correctly used the tool and resolved the drift.

| Test | Drift Type |
|------|-----------|
| `test_drift_adoption_simple_s3` | Property change (S3 tags) |
| `test_drift_adoption_multi_resource` | Resource deletion (bucket-b removed) |
| `test_drift_adoption_loop_resources` | Loop-based deletion (array element removed) |

### Baseline tests (`test_drift_adoption_baseline.py`)

Same scenarios, but the agent has **no skill** — it receives a manual prompt telling it to use `pulumi refresh`, `pulumi preview`, and edit code directly. Uses **deterministic preview verification** (no LLM judge).

| Test | Drift Type |
|------|-----------|
| `test_baseline_simple_s3` | Property change |
| `test_baseline_multi_resource` | Resource deletion |
| `test_baseline_loop_resources` | Loop-based deletion |

### Large-scale skill tests (`test_drift_adoption_large_scale.py`)

Parametrized across 250, 500, 750, and 1000 resources using local providers (`random`, `command`, `tls`). Each fixture has ~15% drift distributed across four types:

- **Property changes** (scattered) — e.g., string length, algorithm changes
- **Resource deletions** — resources removed from drifted code
- **Resource creations** — extra resources added in drifted code
- **Clustered property changes** — consecutive resources modified together

Uses **deterministic preview verification**.

### Large-scale baseline tests (`test_drift_adoption_large_scale_baseline.py`)

Same large-scale scenarios without the skill.

## Key Components

### `drift_adoption_helpers.py`

Core test infrastructure. Provides:

- **Worktree management**: `worktree_context()` / `create_worktree()` / `cleanup_worktree()` for git worktree isolation
- **Test lifecycle**: `drift_test_context()` context manager orchestrating the full setup/teardown flow
- **Drift creation**: `create_drift_with_program()` deploys drifted code then reverts source
- **Verification**: `verify_drift_exists()`, `verify_drift_resolved()`, `verify_resource_count_in_state()`, `verify_resource_property_in_state()`
- **Prompt building**: `build_drift_prompt()` formats the agent prompt with working directory and instructions
- **Evidence scrubbing**: `scrub_drifted_dirs()` removes `drifted/` directories so the agent can't copy answers

### `anthropic_agent.py`

Minimal agent built on the Anthropic SDK. Key details:

- Model: `claude-sonnet-4-20250514`
- Max iterations: 50 tool-use loops
- MCP support via `InlineMCPToolClient` (runs FastMCP servers in-process)
- Optional message logging to file (enabled with `--log-messages`)

### `utils.py`

`query_auto_approve(agent, prompt)` — Runs the agent and automatically approves all tool calls. Collects metrics (tokens, timing, memory) and returns `(response, tool_calls, AgentMetrics)`.

### `metrics.py`

`TestMetrics` and `AgentMetrics` dataclasses for collecting per-test measurements. Writes one JSON file per test to `.test-output/metrics/`. Prints a summary table to the terminal at the end of the pytest session.

### `llm_judge.py`

`llm_judge_boolean(content, evaluation_prompt)` — Sends agent output to Claude Sonnet with a structured evaluation prompt. Returns `LLMJudgeBooleanResult` with `reasoning` and `answer` (bool).

### `simple_shell_mcp.py`

`create_shell_mcp()` — Creates a FastMCP server providing a `shell_execute` tool. Blocks dangerous commands (`pulumi up`, `pulumi preview`) by default to prevent the agent from deploying changes directly.

### `pulumitest/`

Framework-independent wrapper around Pulumi Automation API:

- `PulumiProgram` — Manages stack lifecycle (`up()`, `preview()`, `refresh()`, `destroy()`, `update_source()`)
- `PreviewResult` / `UpdateResult` / `RefreshResult` — Wrappers with helpers like `has_no_changes()`, `has_no_deletes()`
- `opttest` — Test configuration options (stack name, env vars, passphrase, etc.)

### `conftest.py`

Pytest fixtures:

| Fixture | Scope | Description |
|---------|-------|-------------|
| `agent` | function | `AnthropicAgent` with SKILL.md and shell MCP |
| `agent_no_skill` | function | `AnthropicAgent` without SKILL.md (baseline) |
| `test_metrics` | function | `TestMetrics` collector with timing |
| `test_temp_dir` | function | Auto-use, changes cwd to tmp_path |
| `aws_credentials` | session | Validates AWS access |
| `skill_md_content` | session | Loads SKILL.md content |
| `message_log_path` | function | Log path if `--log-messages` set |

Custom CLI options: `--log-messages DIR`, `--metrics-output DIR`

### `generate_large_scale.py`

Generates the `large-scale-{250,500,750,1000}` test fixtures. Resource distribution: 40% `random`, 35% `command`, 25% `tls`. Drift is deterministic — same seed always produces the same drift layout.

### `analyze_logs.py`

Analyzes agent message logs for iteration timelines, tool usage histograms, phase breakdowns, and stuck-point detection. Three modes of operation:

- **Single file**: Analyze one log in detail
- **Directory**: Analyze all `.log` files in a directory
- **Compare** (`--compare`): Side-by-side skill vs baseline behavioral comparison

For each log, produces:

- **Iteration timeline** — per-iteration tool calls, bash commands, and assistant text
- **Tool usage histogram** — tool call counts with Bash sub-classified by command prefix
- **Phase breakdown** — iterations classified as understanding (Read/Glob/Grep), acting (Edit/Write/drift-adopt), or verifying (pulumi preview)
- **Stuck points** — repeated tool calls, error-recovery language, diagnostic spinning, repeated file reads

```bash
uv run tests/analyze_logs.py .test-output/logs/test_drift_adoption_small_scale.log  # single file
uv run tests/analyze_logs.py                                                         # all logs
uv run tests/analyze_logs.py --compare                                               # skill vs baseline
```

### `compare_metrics.py`

Compares skill vs baseline test metrics from the JSON files in `.test-output/metrics/`. Pairs tests by naming convention (e.g., `test_drift_adoption_X` ↔ `test_baseline_X`, or `test_X[param]` ↔ `test_X_baseline[param]`).

Outputs a table comparing:

- Agent time and total time (seconds)
- Iterations and token usage
- Success/failure status
- Delta percentages between skill and baseline

```bash
uv run tests/compare_metrics.py                          # default .test-output/metrics/
uv run tests/compare_metrics.py .test-output/metrics     # explicit directory
```

## Analysis Scripts

After running tests, use the analysis scripts to evaluate results:

1. **Run tests** — metrics JSON and agent logs are written to `.test-output/`
2. **`compare_metrics.py`** — quick tabular skill-vs-baseline comparison of timing, tokens, and success
3. **`analyze_logs.py`** — deep dive into agent behavior: iteration timelines, tool histograms, phase breakdowns, stuck points
4. **`analyze_logs.py --compare`** — side-by-side behavioral comparison showing where skill and baseline approaches diverge

## Evaluation Methods

### LLM Judge (skill tests)

Used for standard-scale skill tests. Sends the agent's full response to Claude Sonnet with an evaluation prompt that checks:

1. Did the agent use the `drift-adopter` tool?
2. Did the agent correctly resolve the drift?

Returns a boolean verdict with reasoning.

### Deterministic preview (baseline + large-scale)

Runs `pulumi preview` after the agent finishes. Asserts zero pending changes — if the agent correctly adopted all drift into code, the preview should show no updates, creates, or deletes.

### State verification

For specific tests, checks Pulumi stack state directly:

- `verify_resource_count_in_state()` — asserts expected number of resources of a given type
- `verify_resource_property_in_state()` — asserts specific property values in resource state

## Running Tests

### Prerequisites

| Variable | Description |
|----------|-------------|
| `PULUMI_ACCESS_TOKEN` | Pulumi Cloud access token |
| `GITHUB_TOKEN` | GitHub token (for git operations) |
| `ANTHROPIC_API_KEY` | Anthropic API key (for the agent) |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | AWS credentials (standard tests only) |

Large-scale tests use local providers and do **not** require AWS credentials.

### Commands

```bash
# Install dependencies
just sync

# Standard skill tests (requires AWS)
just test                              # all
just test-one test_drift_adoption_simple_s3   # specific

# Baseline tests (requires AWS)
just test-baseline                     # all
just test-baseline-one test_baseline_simple_s3  # specific

# Large-scale skill tests (local providers only)
just test-large                        # all (250/500/750/1000)
just test-large-one scale-250          # specific scale

# Large-scale baseline tests
just test-large-baseline               # all
```

### Pytest markers

| Marker | Description |
|--------|-------------|
| `integration` | All integration tests |
| `write_permissions` | Tests that modify infrastructure |
| `large_scale` | Large-scale tests (250+ resources) |
| `baseline` | Tests without skill (raw LLM) |

## Metrics

### What's collected

Per-test via `TestMetrics` and `AgentMetrics`:

- **Test timing**: Total wall-clock time
- **Agent timing**: Time spent in agent query
- **Iterations**: Number of tool-use loops
- **Token usage**: Input, output, cache creation, cache read
- **Peak memory**: RSS high-water mark during agent execution
- **Resource count**: Number of Pulumi resources in the stack
- **Pass/fail**: Whether the test succeeded

### Output

- **JSON files**: One per test in `.test-output/metrics/` (e.g., `test_drift_adoption_simple_s3.json`)
- **Terminal table**: Summary printed at the end of the pytest session via `pytest_terminal_summary` hook
- **Agent message logs**: Full agent conversation in `.test-output/logs/` (one per test)

All output directories are gitignored.

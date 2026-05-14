---
name: pulumi-dynamic-to-go-provider
description: Port a working TypeScript Pulumi dynamic provider (a class implementing `pulumi.dynamic.ResourceProvider`, used via `pulumi.dynamic.Resource`) to a `pulumi-go-provider`-based Go provider using the `infer` package. Covers resource type translation, the six CRUD method mappings (check/diff/create/read/update/delete), retry helper port, schema generation via `pulumi package gen-sdk`, and consumer-side wiring with a generated SDK. Use when (1) the user has an existing TypeScript dynamic provider and wants to convert it to a distributable Go provider, (2) the user mentions porting from `pulumi.dynamic.ResourceProvider` to `infer.Provider`, (3) the user asks "convert dynamic provider to Go", "port to pulumi-go-provider", "TS dynamic to Go provider migration", or asks how to make a dynamic provider into a real distributable provider.
---

# Port a TypeScript dynamic provider to pulumi-go-provider

A TS dynamic provider implements `pulumi.dynamic.ResourceProvider` and is
serialised into program state. A `pulumi-go-provider`-based Go provider runs
as a long-lived gRPC binary, has a schema, and can produce SDKs for any
Pulumi-supported language. The port is mostly mechanical, but several traps
only surface during schema generation or end-to-end runs — this skill walks
through them in the order they bite.

## What this skill produces

A new directory (typically `go-provider/`) containing:

```text
go-provider/
├── go.mod
├── main.go                 # Config + Configure + provider builder
├── <resource>.go           # Args + State types + CRUD methods
├── http_retry.go           # Retry helper (verbatim from assets/)
├── pulumi-resource-<name>  # Built provider binary
├── sdk/nodejs/             # Generated TS SDK
└── examples/typescript/    # Consumer program exercising the SDK
```

Plus a verification flow that runs the same lifecycle the source TS provider
ran — `pulumi up`, modify+up (to drive update), out-of-band drift +
`pulumi refresh`, idempotent destroy.

## Workflow

### Step 1 — Survey the TS source

Read the existing TS dynamic provider end-to-end. Identify:

- The `dynamic.Resource` subclass (the user-facing resource).
- The `dynamic.ResourceProvider` implementation (the CRUD class).
- The inputs interface (typically `XxxArgs`).
- The state shape (what `outs` includes from `create`/`update`/`read`).
- HTTP/retry helpers.
- How config (URL, credentials) reaches the CRUD methods — usually closure
  capture or constructor injection.

For each input field, note its type. Unions like `"low" | "medium" | "high"`
become Go enums. Optional fields become pointer fields in Go.

For each CRUD method, note the implementation strategy:

- Is `create` returning inputs (echo) or server response (server-truth)?
- Is `update` partial PATCH or full PUT?
- Does `read` actually fetch or is it a no-op?
- Does `delete` handle 404 idempotently?
- What does `check` validate?
- What does `diff` compare?

These choices port forward as-is; document them before translating so the Go
side faithfully mirrors the source's contract.

### Step 2 — Initialise the Go module

```bash
mkdir go-provider && cd go-provider
go mod init github.com/<org>/<provider-name>
go get github.com/pulumi/pulumi-go-provider@latest
```

Copy `assets/http_retry.go` into `go-provider/` verbatim — no per-resource
customisation needed.

Copy `assets/scaffold-main.go` to `go-provider/main.go` and substitute the
placeholders (TODO comments mark where).

### Step 3 — Translate types

For the inputs interface, create a Go struct with `pulumi:"name"` tags:

```go
type XxxArgs struct {
    Title    string   `pulumi:"title"`
    Optional *string  `pulumi:"optional,optional"` // pointer + ,optional for optional fields
    Priority Priority `pulumi:"priority"`           // enum type, see below
}
```

For union types, define a typed-string enum with `Values()`:

```go
type Priority string
const (
    PriorityLow    Priority = "low"
    PriorityMedium Priority = "medium"
    PriorityHigh   Priority = "high"
)
func (Priority) Values() []infer.EnumValue[Priority] {
    return []infer.EnumValue[Priority]{
        {Name: "low",    Value: PriorityLow,    Description: "..."},
        {Name: "medium", Value: PriorityMedium, Description: "..."},
        {Name: "high",   Value: PriorityHigh,   Description: "..."},
    }
}
```

For the state shape, declare it as a separate struct:

```go
type XxxState struct {
    Title    string   `pulumi:"title"`
    Optional *string  `pulumi:"optional,optional"`
    Priority Priority `pulumi:"priority"`
}
```

**Critical**: do *not* declare an `id` field on State. The framework reserves
`id` and manages it separately via `CreateResponse.ID` and `req.ID`. If your
TS state had `outs.id`, that field disappears from the Go state struct — it's
implicit. This is the first trap that bites; see
[references/traps.md](references/traps.md).

Implement `Annotate` on each type for descriptions:

```go
func (a *XxxArgs) Annotate(an infer.Annotator) {
    an.Describe(&a.Title, "The text of the item.")
    // ...
}
```

For the full per-concept mapping, see
[references/translation-table.md](references/translation-table.md).

### Step 4 — Translate CRUD methods, in this order

Translate one method at a time, in this order — each builds on the previous,
running from "least decision-density" to "most":

1. **Read** — fetch from server; return empty `ReadResponse{}` on 404.
2. **Delete** — fetch DELETE; treat 404 as success (idempotent).
3. **Create** — POST with body projected to a typed struct (never the input
   bag wholesale — see traps). POST does *not* go through the retry helper
   (idempotency).
4. **Diff** — field-by-field strict equality; populate `DetailedDiff` map.
5. **Check** — usually trivial; the schema-level enum handles enum
   validation. Use `infer.DefaultCheck[Args]` and add custom failures if
   needed.
6. **Update** — partial PATCH containing only changed fields. Most
   decision-dense method; see
   [references/crud-patterns.md](references/crud-patterns.md) for the
   body-shape choice (`map[string]any` vs pointer struct).

After each method, `go build ./...` to keep yourself honest. Add compile-time
interface assertions to make missing methods fail at build, not runtime:

```go
var (
    _ infer.CustomCheck[XxxArgs]            = (*Xxx)(nil)
    _ infer.CustomDiff[XxxArgs, XxxState]   = (*Xxx)(nil)
    _ infer.CustomRead[XxxArgs, XxxState]   = (*Xxx)(nil)
    _ infer.CustomUpdate[XxxArgs, XxxState] = (*Xxx)(nil)
    _ infer.CustomDelete[XxxState]          = (*Xxx)(nil)
)
```

For the per-method patterns and code sketches, see
[references/crud-patterns.md](references/crud-patterns.md).

### Step 5 — Schema check + SDK generation

```bash
go build -o pulumi-resource-<name> .
pulumi package get-schema ./pulumi-resource-<name>
```

This is where the `id`-reserved-name trap surfaces if you missed it in
step 3. Other schema errors (missing required tags, malformed enum) also
appear here.

Once schema is valid:

```bash
pulumi package gen-sdk ./pulumi-resource-<name> --language nodejs --out ./sdk
cd sdk/nodejs && npm install && npm run build
```

For multi-language SDKs, repeat with `--language python|dotnet|go`.

### Step 6 — Consumer scaffolding

Scaffold the consumer with `pulumi new` for boilerplate
(tsconfig.json, .gitignore, stub files), then overwrite the three
skill-specific files:

```bash
cd go-provider/examples
pulumi new typescript --generate-only --yes \
  --name <consumer-name> --dir typescript
cd typescript
```

`pulumi new` writes a stub `Pulumi.yaml`, `package.json`, `index.ts`,
plus tsconfig.json and .gitignore. The first three need overwriting:

| File | What needs to change vs. the stub |
|---|---|
| `Pulumi.yaml` | Adds the `plugins: providers:` block pointing at the locally-built binary. Use `assets/consumer-Pulumi.yaml`. |
| `package.json` | Replaces the stub `@pulumi/pulumi` dep with a `file:` link to the generated SDK at `../../sdk/nodejs`. Use `assets/consumer-package.json`. |
| `index.ts` | Hand-written: imports the SDK package, reads project config, constructs the Provider and resources. |

The generated SDK's package name is deterministic from main.go:

| Language | Package name |
|---|---|
| nodejs | `@<namespace>/<Name>` |
| python | `<namespace>_<Name>` (underscored, lowercased) |
| go | `github.com/<namespace>/<Name>/sdk/go/<Name>` |
| dotnet | `<Pascal-namespace>.<PascalName>` |

Where `<namespace>` is `WithNamespace(...)` and `<Name>` is the
`const Name` in main.go. So `WithNamespace("rshade") + Name = "todo"`
produces an nodejs package `@rshade/todo`. You don't need to inspect
`sdk/<lang>/package.json` to discover it.

Copy the two assets, substitute their placeholders, write `index.ts`,
then:

```bash
pulumi install
pulumi whoami       # confirm logged in to *some* backend; see traps.md
pulumi stack init dev
pulumi config set <consumer-name>:<config-key> <value>
pulumi config set <provider-name>:<config-key> <value>  # see traps.md
pulumi up
```

If `pulumi whoami` fails, ask the user which backend they want — never
run `pulumi login --local` eagerly. It switches the active backend and
can disconnect a cloud-logged-in user.

`pulumi install` installs both npm dependencies (per the configured
package manager) and any Pulumi plugins declared in `Pulumi.yaml` — so
the local provider plugin from the `plugins:` block is resolved in the
same step.

### Step 7 — Verify end-to-end

Run the same lifecycle the TS source ran:

1. **Create** — `pulumi up`. Confirm resources created, IDs surfaced as
   stack outputs.
2. **Update** — modify a field in `index.ts`, run `pulumi up`. Confirm the
   `[diff: ~field]` annotation; check the server side to confirm partial
   PATCH (other fields preserved).
3. **Refresh** — modify a field on the server out-of-band, run
   `pulumi refresh`. Confirm drift detected and pulled into state.
4. **Idempotent destroy** — manually delete one resource on the server, run
   `pulumi destroy`. Confirm `"already deleted on server"` log line; all
   resources cleaned up.

If all four steps succeed, the port is functionally complete. If any step
fails, see [references/traps.md](references/traps.md) for likely causes.

For the full verification recipe with sample commands, see
[references/verification-flow.md](references/verification-flow.md).

## Known traps (load this immediately on encountering errors)

- `"id" is a reserved field name` at schema-gen time → remove `Id` field
  from State struct.
- Provider state on the server contains `__provider` blob → stage-1 only;
  cannot recur in Go (no closure to serialise).
- "Provider exited prematurely" warning at end of destroy → benign;
  operations succeeded, framework shutdown handshake quirk.
- Empty-body crash on retry helper's last attempt → don't
  `defer res.Body.Close()` inside the retry loop; close in
  `errorFromResponse` after the body read.

For the full list with detection and fix patterns, see
[references/traps.md](references/traps.md).

## Resources

| File | Purpose |
|---|---|
| [`references/translation-table.md`](references/translation-table.md) | Concept-by-concept mapping from TS dynamic provider to Go infer. Read when stuck on a specific translation. |
| [`references/crud-patterns.md`](references/crud-patterns.md) | The Go code shape for each CRUD method, with substitution patterns. Read while translating any method. |
| [`references/traps.md`](references/traps.md) | Known failure modes with detection symptoms and fixes. Read when something goes wrong. |
| [`references/verification-flow.md`](references/verification-flow.md) | End-to-end test recipe with exact commands. Read for step 7. |
| `assets/http_retry.go` | Retry helper, copy-paste verbatim. |
| `assets/scaffold-main.go` | `main.go` template with placeholders for resource type, provider name, namespace. |
| `assets/consumer-Pulumi.yaml` | Consumer-side `Pulumi.yaml` with `plugins:` block. |
| `assets/consumer-package.json` | Consumer-side `package.json` with `file:` SDK link. |

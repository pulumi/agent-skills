# Translation table: TS dynamic provider → `pulumi-go-provider` (`infer`)

Concept-by-concept mapping. Each row is a concept that exists on both sides;
the friction column flags whether the translation is mechanical or has
subtleties.

## Authoring model

| Concept | TS dynamic | Go `infer` | Friction |
|---|---|---|---|
| Provider model | Class implementing `dynamic.ResourceProvider`, serialised into program state | Long-lived gRPC binary the engine talks to | None — fundamentally different runtime, but the work moves cleanly |
| Distribution | None — code lives in the program | `pulumi-resource-<name>` binary, found via `Pulumi.yaml` `plugins:` block or `PULUMI_DEBUG_PROVIDERS` | New step; the binary is large (~50 MB with full gRPC + sdk stack) |
| Resource type definition | Class extending `pulumi.dynamic.Resource` with constructor | Go type with method receivers; typically `type Xxx struct{}` | None — empty struct works fine when no per-instance state needed |
| Provider class | The dynamic provider class itself | None — the framework runs the resource's methods directly. Configuration lives on a separate `Config` type registered with `infer.Config` | The "provider class" concept disappears as a distinct entity |

## Types

| Concept | TS | Go | Friction |
|---|---|---|---|
| Inputs interface | `interface XxxArgs { title: pulumi.Input<string>; ... }` | `type XxxArgs struct { Title string \`pulumi:"title"\` ... }` | Mechanical; `pulumi.Input<T>` becomes plain `T` (the framework resolves before calling) |
| State shape | Properties on the resource class, populated from `outs` | `type XxxState struct { ... }`, returned from CRUD via response wrappers | Mechanical *except* for `id` — see id row |
| `id` field | Conventionally in `outs.id`; surfaced as `.id` on the resource | **Reserved** — must NOT appear in state struct. Engine manages it via `CreateResponse.ID` and `req.ID` | **Real friction** — caught at schema-gen with `"id" is a reserved field name`. Remove `Id` from your state struct |
| Optional fields | `field?: T` or `field: T \| undefined` | `field *T \`pulumi:"field,optional"\`` (pointer + `,optional` tag) | Mechanical |
| Union types | `"low" \| "medium" \| "high"` | `type Priority string` + constants + `Values()` method (any type with that method becomes a schema enum) | **Cleaner in Go** — schema validates; generated SDK gets union type for free |
| Nested objects | `{ inner: { x: string } }` | Nested struct with `pulumi:"name"` tag | Mechanical |
| Lists | `string[]`, `pulumi.Input<string[]>` | `[]string` | Mechanical |
| Maps | `Record<string, T>` | `map[string]T` | Mechanical |

## CRUD method signatures

All methods take `(ctx context.Context, req XRequest[Args, State])` and return
`(XResponse[Args, State], error)` in `infer` v1.x.

| Method | TS dynamic | Go `infer` | Notes |
|---|---|---|---|
| `check` | `check(olds, news): { inputs?, failures? }` | `Check(ctx, req CheckRequest) (CheckResponse[Args], error)` | Use `infer.DefaultCheck[Args]` to start; add custom failures from there |
| `diff` | `diff(id, oldOuts, newInputs): { changes?, replaces? }` | `Diff(ctx, req DiffRequest[Args, State]) (DiffResponse, error)` | Go's `DiffResponse` has `HasChanges + DetailedDiff: map[string]PropertyDiff` — richer than TS's binary `changes` |
| `create` | `create(inputs): { id, outs }` | `Create(ctx, req CreateRequest[Args]) (CreateResponse[State], error)` | Go's `CreateResponse{ID, Output}` — ID is separate from state |
| `read` | `read(id, props): { id?, props? }` | `Read(ctx, req ReadRequest[Args, State]) (ReadResponse[Args, State], error)` | Empty `ReadResponse{}` signals "gone" (mirrors TS `{}` convention) |
| `update` | `update(id, oldOuts, newInputs): { outs }` | `Update(ctx, req UpdateRequest[Args, State]) (UpdateResponse[State], error)` | Mechanical |
| `delete` | `delete(id, props): void` | `Delete(ctx, req DeleteRequest[State]) (DeleteResponse, error)` | Return `infer.DeleteResponse{}` even on success |

## Configuration

| Concept | TS | Go | Friction |
|---|---|---|---|
| Source | `pulumi.Config` in program | `pulumi.Config` in consumer; provider receives via `Configure(ctx)` | Mechanical |
| Wiring | Closure-capture into provider class; baked into resource state per resource | `Config` struct registered with `infer.Config(&Config{})`; retrieved via `infer.GetConfig[Config](ctx)` from each method | **Cleaner in Go** — provider-level config; trap "config baked into state" cannot recur |
| Setup hook | None | `Configure(ctx) error` method on Config type — called once before any CRUD | **New capability** — natural place to initialise an `*http.Client` |
| Sharing | Each CRUD method had its own captured copy | One Config struct shared across all methods (long-lived binary); fields on it are concurrent-shared | **New concern** — mutable state on Config must be goroutine-safe (`*http.Client` is fine; a non-thread-safe cache wouldn't be) |

## Concurrency

| Concept | TS | Go |
|---|---|---|
| Concurrent CRUD calls | Engine spawns separate child processes; nothing shared | Same binary, multiple goroutines; CRUD calls can run in parallel |
| Cancellation | None — async functions run to completion | `context.Context` flows through every method; cancellation propagates |
| Connection reuse | None — each call creates a fresh `fetch` | Long-lived `*http.Client` on Config; `http.Transport` pools connections |

## Error handling

| Concept | TS | Go |
|---|---|---|
| Surfacing | `throw new Error(message)` | Return `error`; engine surfaces via `err.Error()` |
| Wrapping | Stack traces (free) | `fmt.Errorf("...: %w", err)` for wrapping; no stack unless using `pkg/errors` |
| Body-in-message | `throw new Error(...await res.text()...)` | `defer res.Body.Close()` discipline; read body once via `io.ReadAll` |
| HTTP error helper | `errorFromResponse(method, url, res)` returning `Error` | Same shape; takes `*http.Response`, closes body internally |

## Retry

| Concept | TS | Go |
|---|---|---|
| Library | None — hand-rolled | None — hand-rolled |
| Time delay | `setTimeout(resolve, ms)` | `select { case <-time.After(d): case <-ctx.Done(): }` |
| Body lifecycle per attempt | None — fetch's body recreated implicitly | `bytes.NewReader(body)` per attempt (reader is single-use) |
| Idempotency | Caller decides which methods retry | Same — POST bypasses retry helper; PATCH/GET/DELETE use it |

## Lifecycle

| Concept | TS | Go |
|---|---|---|
| `pulumi preview` | Engine doesn't call CRUD methods | `req.DryRun bool` is `true`; methods must short-circuit (return inputs-as-state without HTTP) |
| Provider startup | None — class instantiated on each call | `Configure(ctx)` called once; init HTTP client here |
| Provider shutdown | None | Engine signals shutdown; `provider.Run()` returns. Premature exit produces a warning |

## Schema

| Concept | TS | Go |
|---|---|---|
| Existence | None | Generated by `infer` from struct tags + `Annotated.Annotate` methods |
| Property descriptions | None | `a.Describe(&s.Field, "...")` in `Annotate` |
| Defaults | None | `a.SetDefault(&s.Field, defaultVal, "ENV_VAR")` |
| Multi-language SDKs | None | `pulumi package gen-sdk` reads schema, emits SDK |

## Resource type token in state

| TS | Go |
|---|---|
| `pulumi-nodejs:dynamic:Resource` (generic) | `<provider-name>:index:<ResourceTypeName>` (specific) |

## What you gain in the port

- Schema → multi-language consumers, generated docs, SDK type narrowing.
- First-class enum, type token, id management.
- Provider-level config; cancellation; connection pooling.

## What costs more in the port

- Binary build/distribute step.
- Body-lifecycle ceremony (`defer Close`, body-reader-per-attempt).
- No `Partial<T>` equivalent for partial PATCH bodies — use `map[string]any`
  or pointer struct with `omitempty`.
- Provider lifecycle and shutdown coordination.

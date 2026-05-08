# CRUD method patterns for `pulumi-go-provider` (`infer`) v1.x

Code patterns for each CRUD method, in the recommended translation order.
Each pattern shows the method signature, the typical body shape, and what to
substitute (`<placeholder>` markers).

Assumptions baked in:

- The provider's resource type is `Xxx` (a `struct{}`).
- Inputs are `XxxArgs`, state is `XxxState`.
- Config is `Config{ ServerUrl string; client *http.Client }`.
- The retry helper is `doWithRetry(ctx, client, method, url, body, maxAttempts)`
  from `assets/http_retry.go`.
- Errors are formatted by `errorFromResponse(method, url, res)`.

## Translation order

Translate methods in this order — each builds on the previous:

1. **Read** — simplest; baseline pattern for HTTP + state shape
2. **Delete** — adds idempotent-on-404
3. **Create** — adds POST without retry, body projection discipline
4. **Diff** — pure logic, no HTTP
5. **Check** — usually trivial with schema-level enum
6. **Update** — most decision-density (partial body shape)

After writing each method, `go build ./...` to keep yourself honest. Add the
compile-time interface assertions early (they fail loudly when a method
signature drifts).

## Read

```go
func (*Xxx) Read(
    ctx context.Context,
    req infer.ReadRequest[XxxArgs, XxxState],
) (infer.ReadResponse[XxxArgs, XxxState], error) {
    cfg := infer.GetConfig[Config](ctx)
    url := cfg.ServerUrl + "/<resource-path>/" + req.ID

    res, err := doWithRetry(ctx, cfg.client, http.MethodGet, url, nil, 3)
    if err != nil {
        return infer.ReadResponse[XxxArgs, XxxState]{}, err
    }
    if res.StatusCode == http.StatusNotFound {
        res.Body.Close()
        // Empty response signals "resource gone" — engine drops from state.
        return infer.ReadResponse[XxxArgs, XxxState]{}, nil
    }
    if res.StatusCode < 200 || res.StatusCode >= 300 {
        return infer.ReadResponse[XxxArgs, XxxState]{}, errorFromResponse("GET", url, res)
    }
    defer res.Body.Close()

    var current <serverObjectType>
    if err := json.NewDecoder(res.Body).Decode(&current); err != nil {
        return infer.ReadResponse[XxxArgs, XxxState]{}, fmt.Errorf("decode GET response: %w", err)
    }

    state := stateFromServerObject(current)
    return infer.ReadResponse[XxxArgs, XxxState]{
        ID:     req.ID,
        Inputs: argsFromState(state),
        State:  state,
    }, nil
}
```

The `<serverObjectType>` is a struct that mirrors what the upstream API
returns on GET. Often identical to `XxxState` plus an `Id` field; sometimes
different (extra metadata).

## Delete

```go
func (*Xxx) Delete(
    ctx context.Context,
    req infer.DeleteRequest[XxxState],
) (infer.DeleteResponse, error) {
    cfg := infer.GetConfig[Config](ctx)
    url := cfg.ServerUrl + "/<resource-path>/" + req.ID

    res, err := doWithRetry(ctx, cfg.client, http.MethodDelete, url, nil, 3)
    if err != nil {
        return infer.DeleteResponse{}, err
    }
    if res.StatusCode == http.StatusNotFound {
        res.Body.Close()
        p.GetLogger(ctx).Warningf("<resource> %q already deleted on server", req.ID)
        return infer.DeleteResponse{}, nil
    }
    if res.StatusCode < 200 || res.StatusCode >= 300 {
        return infer.DeleteResponse{}, errorFromResponse("DELETE", url, res)
    }
    res.Body.Close()
    return infer.DeleteResponse{}, nil
}
```

Where `p` is the framework's top-level package (`p "github.com/pulumi/pulumi-go-provider"`).

## Create

```go
func (*Xxx) Create(
    ctx context.Context,
    req infer.CreateRequest[XxxArgs],
) (infer.CreateResponse[XxxState], error) {
    cfg := infer.GetConfig[Config](ctx)

    if req.DryRun {
        // Preview: don't hit the server; reflect inputs as state.
        return infer.CreateResponse[XxxState]{
            Output: stateFromArgs(req.Inputs),
        }, nil
    }

    // Project inputs to a typed body — never send the input bag wholesale.
    body, err := json.Marshal(bodyFromArgs(req.Inputs))
    if err != nil {
        return infer.CreateResponse[XxxState]{}, fmt.Errorf("marshal body: %w", err)
    }

    url := cfg.ServerUrl + "/<resource-path>"
    httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
    if err != nil {
        return infer.CreateResponse[XxxState]{}, fmt.Errorf("build POST %s: %w", url, err)
    }
    httpReq.Header.Set("Content-Type", "application/json")

    // POST does NOT go through doWithRetry — non-idempotent (E4b rule).
    res, err := cfg.client.Do(httpReq)
    if err != nil {
        return infer.CreateResponse[XxxState]{}, fmt.Errorf("POST %s: %w", url, err)
    }
    if res.StatusCode < 200 || res.StatusCode >= 300 {
        return infer.CreateResponse[XxxState]{}, errorFromResponse("POST", url, res)
    }
    defer res.Body.Close()

    var created <serverObjectType>
    if err := json.NewDecoder(res.Body).Decode(&created); err != nil {
        return infer.CreateResponse[XxxState]{}, fmt.Errorf("decode POST response: %w", err)
    }

    return infer.CreateResponse[XxxState]{
        ID:     created.Id,
        Output: stateFromServerObject(created),
    }, nil
}
```

Helpers:

- `bodyFromArgs(args XxxArgs) <bodyType>` — typed body struct (only the
  fields the API accepts; never includes `id` or framework internals).
- `stateFromArgs(args XxxArgs) XxxState` — used in DryRun to skip the network
  but return a sensible state.
- `stateFromServerObject(obj <serverObjectType>) XxxState` — converts the
  server's response shape to the state struct.

## Diff

```go
func (*Xxx) Diff(
    _ context.Context,
    req infer.DiffRequest[XxxArgs, XxxState],
) (infer.DiffResponse, error) {
    diff := map[string]p.PropertyDiff{}
    if req.Inputs.Title != req.State.Title {
        diff["title"] = p.PropertyDiff{Kind: p.Update}
    }
    if req.Inputs.<Field2> != req.State.<Field2> {
        diff["<field2>"] = p.PropertyDiff{Kind: p.Update}
    }
    // ... one block per field
    return infer.DiffResponse{
        HasChanges:   len(diff) > 0,
        DetailedDiff: diff,
    }, nil
}
```

Use `p.UpdateReplace` instead of `p.Update` for fields that should trigger
replace (delete + create) rather than in-place update.

**Avoid reflect-based field iteration.** It re-introduces the phantom-field
risk: server-added fields land in `req.State` but not in `req.Inputs`, and
reflection-based equality reports a phantom diff every refresh. Stick to
explicit `if` blocks per known field.

## Check

```go
func (*Xxx) Check(
    ctx context.Context,
    req infer.CheckRequest,
) (infer.CheckResponse[XxxArgs], error) {
    args, failures, err := infer.DefaultCheck[XxxArgs](ctx, req.NewInputs)
    if err != nil {
        return infer.CheckResponse[XxxArgs]{Inputs: args, Failures: failures}, err
    }

    // Add custom validation that the schema can't express:
    if args.Title == "" {
        failures = append(failures, p.CheckFailure{
            Property: "title",
            Reason:   "title must be a non-empty string",
        })
    }

    return infer.CheckResponse[XxxArgs]{Inputs: args, Failures: failures}, nil
}
```

If you have a typed-string enum (`type Priority string` with `Values()`), the
schema rejects bad enum values *before* `Check` runs. Manual enum validation
in `Check` becomes near-redundant — keep it only if explicit comparison
artefact-with-the-original is wanted.

## Update

```go
func (*Xxx) Update(
    ctx context.Context,
    req infer.UpdateRequest[XxxArgs, XxxState],
) (infer.UpdateResponse[XxxState], error) {
    cfg := infer.GetConfig[Config](ctx)

    if req.DryRun {
        return infer.UpdateResponse[XxxState]{
            Output: stateFromArgs(req.Inputs),
        }, nil
    }

    // Build a partial PATCH body — only the changed fields.
    patch := map[string]any{}
    if req.Inputs.Title != req.State.Title {
        patch["title"] = req.Inputs.Title
    }
    // ... one block per field
    if len(patch) == 0 {
        return infer.UpdateResponse[XxxState]{Output: req.State}, nil
    }

    body, err := json.Marshal(patch)
    if err != nil {
        return infer.UpdateResponse[XxxState]{}, fmt.Errorf("marshal patch body: %w", err)
    }

    url := cfg.ServerUrl + "/<resource-path>/" + req.ID
    res, err := doWithRetry(ctx, cfg.client, http.MethodPatch, url, body, 3)
    if err != nil {
        return infer.UpdateResponse[XxxState]{}, err
    }
    if res.StatusCode < 200 || res.StatusCode >= 300 {
        return infer.UpdateResponse[XxxState]{}, errorFromResponse("PATCH", url, res)
    }
    defer res.Body.Close()

    var updated <serverObjectType>
    if err := json.NewDecoder(res.Body).Decode(&updated); err != nil {
        return infer.UpdateResponse[XxxState]{}, fmt.Errorf("decode PATCH response: %w", err)
    }

    return infer.UpdateResponse[XxxState]{
        Output: stateFromServerObject(updated),
    }, nil
}
```

### Patch body shape: alternatives to `map[string]any`

`map[string]any` is the most direct port of TS's partial-object pattern.
Two alternatives:

**Pointer-struct + `omitempty`:**

```go
type xxxPatch struct {
    Title     *string   `json:"title,omitempty"`
    Completed *bool     `json:"completed,omitempty"`
    Priority  *Priority `json:"priority,omitempty"`
}
patch := xxxPatch{}
if req.Inputs.Title != req.State.Title {
    t := req.Inputs.Title
    patch.Title = &t
}
if req.Inputs.Completed != req.State.Completed {
    c := req.Inputs.Completed
    patch.Completed = &c
}
```

More type-safe, more idiomatic Go, slightly more code. The pointer
wrappers are not stylistic — they're load-bearing. `omitempty` on a
plain `bool` cannot distinguish "user wants false" from "field absent":
both are the zero value, so `json.Marshal` drops them. The same trap
applies to `int 0`, `float64 0.0`, and `""` for string fields whose
zero value is a legitimate user-settable input. Wrapping in a pointer
makes the absence/presence distinction explicit and JSON-correct.

If your resource is string-fields-only and none of them have a
meaningful empty-string state, plain `omitempty` on non-pointer fields
also works; that's the degenerate case. Most real resources have at
least one boolean or numeric field, and pointer-struct is the safe
default.

**Always-full body:** if the upstream API treats PATCH as full-replacement
(some APIs do — verify empirically), send the full input body. Simpler but
loses the "only-changed-fields" discipline; can have side effects on real
APIs (audit log entries, webhooks firing on unchanged fields).

## Compile-time interface assertions

Add these near the top of the resource file:

```go
var (
    _ infer.CustomCheck[XxxArgs]            = (*Xxx)(nil)
    _ infer.CustomDiff[XxxArgs, XxxState]   = (*Xxx)(nil)
    _ infer.CustomRead[XxxArgs, XxxState]   = (*Xxx)(nil)
    _ infer.CustomUpdate[XxxArgs, XxxState] = (*Xxx)(nil)
    _ infer.CustomDelete[XxxState]          = (*Xxx)(nil)
)
```

If a method signature drifts (wrong type parameters, wrong receiver), the
package fails to compile and the assertion line points to which method is
broken.

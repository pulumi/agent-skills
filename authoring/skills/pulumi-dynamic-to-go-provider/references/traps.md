# Known traps when porting TS dynamic → `pulumi-go-provider`

Each entry: **symptom** (what you see) → **cause** → **fix**.

## Schema generation

### `failed to get schema for '<token>': "id" is a reserved field name`

**Symptom**: `pulumi package get-schema ./pulumi-resource-<name>` fails with
this error (or a similar wording mentioning `id`).

**Cause**: You declared an `Id` field on your State struct (port-1:1 from
the TS `outs.id`). The Go framework reserves `id` as a property name —
it manages it itself via `CreateResponse.ID` and `req.ID`.

**Fix**: Remove the `Id` field from the State struct. State is purely the
non-id properties.

```go
// Wrong:
type XxxState struct {
    Title string `pulumi:"title"`
    Id    string `pulumi:"id"`  // ← reserved
}

// Right:
type XxxState struct {
    Title string `pulumi:"title"`
}
```

Update Create/Read/Update accordingly:

- `CreateResponse{ID: created.Id, Output: stateFromServerObject(created)}`
- `ReadResponse{ID: req.ID, Inputs: ..., State: stateFromServerObject(current)}`
- `UpdateResponse{Output: stateFromServerObject(updated)}`

The server's response struct (the `<serverObjectType>` — what comes back
over the wire) *does* still have an `Id` field with `json:"id"`; that's
fine. The reservation only applies to types tagged with `pulumi:` for
schema inclusion.

## Runtime behaviour

### `provider exited prematurely` warning at end of `pulumi destroy`

**Symptom**: All resources destroyed correctly (state empty, server clean),
but Pulumi prints:

```text
error: Detected that <path>/pulumi-resource-<name> exited prematurely.
This is *always* a bug in the provider. Please report the issue to the
provider author as appropriate.
```

**Cause**: Framework shutdown handshake quirk — the binary exits before
the engine's final close completes. Operations completed correctly first;
the warning is post-hoc.

**Fix**: Currently no clean fix at the user code level — the binary's
`provider.Run(ctx, ...)` returns when the framework signals shutdown, and
exits via `os.Exit(0)`. If the warning bothers you, file an issue
upstream. For the porting exercise, document and ignore.

### Server state contains a `__provider` JSON blob

**Symptom**: GET-ing a resource from the upstream API shows a giant
`__provider: "..."` field containing serialised JS code.

**Cause**: This is a stage-1 (TS dynamic) trap — `JSON.stringify(inputs)`
in `create` leaked Pulumi's framework-injected `__provider` field to the
server. **Cannot recur in Go** because the Go framework has no closure to
serialise; there's no `__provider` field at all.

**Fix**: If you're seeing this, you're still running the TS provider, not
the Go one. Confirm with `pulumi stack` that the resources are typed
`<provider>:index:<Resource>` (Go) not `pulumi-nodejs:dynamic:Resource`
(TS).

## Build

### `<dep> is not used in this module (go mod tidy)`

**Symptom**: After `go get`, lots of diagnostics about unused transitive
dependencies.

**Cause**: `go get` eagerly lists transitive deps as direct until you
import the package. Cosmetic; doesn't affect compilation.

**Fix**: `go mod tidy`. Cleans up the go.mod direct/indirect classification.

### `<dep> should be direct (go mod tidy)`

**Symptom**: After writing your imports and running `go build`, two deps
are flagged as "should be direct."

**Cause**: Same — `pulumi-go-provider` and `pulumi/sdk/v3` were
classified as indirect during `go get`; once you import them they should
be direct.

**Fix**: `go mod tidy`.

### Stray binary named after the Go module path

**Symptom**: After `go build ./...`, you see a binary like `todo-go-provider`
or `myorg-myproject` instead of `pulumi-resource-<name>`.

**Cause**: `go build ./...` defaults to using the module name for the binary.
The Pulumi framework expects `pulumi-resource-<name>`.

**Fix**: Build with `-o`:

```bash
go build -o pulumi-resource-<name> .
```

Add the stray name to `.gitignore` or `rm` it. The proper binary name is
how the engine looks up the plugin via `Pulumi.yaml`'s `plugins:` block.

## Retry helper

### Tests/runtime hang on retry helper's last attempt

**Symptom**: A request that should fail-and-retry instead hangs.

**Cause**: Almost always a body-lifecycle issue. The retry helper closes
`res.Body` on retried attempts but the *final* attempt must NOT close the
body — the caller needs to read it for the error message via
`errorFromResponse`.

**Fix**: Inspect the retry loop. The pattern is:

```go
for attempt := 0; attempt < maxAttempts; attempt++ {
    res, err := client.Do(req)
    // ...
    if isRetryable && attempt < maxAttempts-1 {
        res.Body.Close()  // close for retry
        // wait + continue
        continue
    }
    return res, nil  // last attempt or non-retryable: return body open
}
```

`errorFromResponse(method, url, res)` then closes via `defer res.Body.Close()`.

### `bytes.NewReader` re-used across retries

**Symptom**: First retry attempt sends an empty body.

**Cause**: `*http.Request.Body` is an `io.Reader`, consumed on first read.
Reusing the same reader across retries means subsequent attempts read from
empty.

**Fix**: Construct a fresh `bytes.NewReader(body)` per attempt:

```go
for attempt := 0; attempt < maxAttempts; attempt++ {
    var bodyReader io.Reader
    if body != nil {
        bodyReader = bytes.NewReader(body)  // fresh per attempt
    }
    req, _ := http.NewRequestWithContext(ctx, method, url, bodyReader)
    // ...
}
```

## Update

### PATCH "succeeded" but other fields got nuked

**Symptom**: After running `pulumi up` to update one field, the server's
copy of the resource has only the field you changed — other fields are
gone.

**Cause**: You used PUT instead of PATCH (PUT is full replace; partial PUT
nukes omitted fields), OR the upstream API treats PATCH as full replace.

**Fix**:

- Confirm your method is `http.MethodPatch`, not `http.MethodPut`.
- Empirically verify the upstream's PATCH semantics: send a partial PATCH
  with curl, GET the result, see if untouched fields survive.
- If the API only supports full PUT, you must build a full body in
  `update` (regress to the pattern stage 1 called "U1") — accept the
  side-effect risk on real APIs.

### Empty PATCH body sent

**Symptom**: PATCH was called with no changes — empty `{}` body. Server
may error (some 400 on empty body).

**Cause**: Update was called even though nothing changed; defensive guard
missing.

**Fix**: Add the no-op short-circuit:

```go
if len(patch) == 0 {
    return infer.UpdateResponse[XxxState]{Output: req.State}, nil
}
```

(Should not happen if Diff is correct, but defensive guards are cheap.)

## Schema / SDK consumption

### Generated TS SDK can't be imported from consumer

**Symptom**: `import { Xxx } from "@<provider>/<name>"` resolves to
nothing; TypeScript can't find the module.

**Cause**: The generated SDK isn't built — `npm install` and
`npm run build` haven't been run inside `sdk/nodejs/`. Or the consumer's
`package.json` `file:` link points at the wrong path.

**Fix**:

```bash
cd sdk/nodejs && npm install && npm run build
cd ../../examples/typescript && npm install
```

Confirm `package.json` has:

```json
"@<provider>/<name>": "file:../../sdk/nodejs"
```

(Path is relative to the consumer's `package.json`.)

### `pulumi config set <key>` rejected — wrong namespace

**Symptom**:

```text
Configuration key '<provider>:<key>' is not namespaced by the project
and should not define a type.
```

**Cause**: You declared a `config:` block in the consumer's `Pulumi.yaml`
with a provider-namespaced key (`<provider>:<key>`). Project-level config
declaration is for *project-namespaced* keys only; provider config doesn't
need declaration.

**Fix**: Remove the offending entry from `Pulumi.yaml`'s `config:` block.
For provider config, just `pulumi config set <provider>:<key> <value>`
without declaration.

### Missing required config var `<consumer-name>:<key>` on `pulumi up`

**Symptom**: First `pulumi up` after setting provider config fails with:

```text
error: Missing required configuration variable '<consumer-name>:<key>'
       please set a value using the command
       `pulumi config set <consumer-name>:<key> <value>`
```

— even though you ran `pulumi config set <provider-name>:<key> <value>`.

**Cause**: The consumer's `index.ts` mirrors stage 1's pattern, reading
project-namespaced config and forwarding it explicitly:

```ts
const cfg = new pulumi.Config();
const url = cfg.require("serverUrl");           // project-namespaced
const provider = new xxx.Provider("xxx", { serverUrl: url });
```

`cfg.require("serverUrl")` reads `<consumer-name>:serverUrl`, *not*
`<provider-name>:serverUrl`. Setting only the provider-namespaced key
leaves the project-namespaced read unsatisfied.

**Fix** — three options, in increasing order of "how much the consumer
diverges from stage 1":

1. **Set both** — most faithful to the stage-1 mental model:

   ```bash
   pulumi config set serverUrl <value>                  # project-namespaced
   pulumi config set <provider-name>:serverUrl <value>  # provider-namespaced
   ```

2. **Drop the project read in the consumer**, set provider config only:

   ```ts
   // index.ts: remove the pulumi.Config() line
   const provider = new xxx.Provider("xxx", {});
   ```

   Requires the SDK's `ProviderArgs.serverUrl` to be schema-optional
   (`pulumi:"serverUrl,optional"` on the Go side) so the value can come
   from provider config alone. Most providers want the field required,
   so this fix usually doesn't apply cleanly.

3. **Remove the explicit Provider construction**, use the default
   provider via provider-namespaced config:

   ```ts
   // No `new xxx.Provider(...)` at all.
   const r = new xxx.Resource("name", { ... });  // engine picks default provider
   ```

   ```bash
   pulumi config set <provider-name>:serverUrl <value>
   ```

   Cleanest going forward, but loses the "construct one provider, share
   it across resources" pattern stage 1 used.

Option 1 is the lowest-friction port of stage 1; choose it unless you
have a reason to restructure.

## Backend / login

### Don't run `pulumi login --local` without checking `whoami` first

**Symptom**: User reports they were logged into the cloud backend; the
agent ran `pulumi login --local` to "fix" a perceived auth issue; now
their cloud stacks aren't accessible until they `pulumi login` again.

**Cause**: `pulumi login --local` switches the active backend to the
file-backed local backend. It doesn't *delete* the cloud session, but
it deactivates it for the current shell until the user re-runs
`pulumi login`. Running it eagerly disrupts user state for no reason —
the verification flow doesn't care which backend is active.

**Fix**: Always `pulumi whoami` before any backend-touching command
(`stack init`, `up`, `config set`, etc.):

```bash
pulumi whoami
```

If it succeeds, the user is already logged in to *some* backend; that's
all the skill needs. Proceed.

If it fails (`error: getting backend: ... not logged in`), ask the user
which backend rather than choosing for them:

- `pulumi login` — cloud backend (their pulumi.com account)
- `pulumi login --local` — file-backed local-only backend
- `pulumi login s3://...`, `pulumi login azblob://...`, etc. — other
  supported self-hosted backends

The verification flow works identically across all of them.

## Method signatures

### Method exists but framework doesn't see it

**Symptom**: Custom `Diff`/`Check`/`Update` is written but the engine
doesn't call it (default behaviour kicks in instead).

**Cause**: Method signature drifted out of conformance with the framework
interface (wrong type parameter, pointer vs value receiver, wrong request
type).

**Fix**: Add compile-time interface assertions early so signature drift
fails at build:

```go
var (
    _ infer.CustomCheck[XxxArgs]            = (*Xxx)(nil)
    _ infer.CustomDiff[XxxArgs, XxxState]   = (*Xxx)(nil)
    _ infer.CustomRead[XxxArgs, XxxState]   = (*Xxx)(nil)
    _ infer.CustomUpdate[XxxArgs, XxxState] = (*Xxx)(nil)
    _ infer.CustomDelete[XxxState]          = (*Xxx)(nil)
)
```

If any of these fails, the assertion line points at the broken method.

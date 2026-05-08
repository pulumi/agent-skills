# End-to-end verification flow

The same lifecycle the source TS provider ran, applied to the new Go
provider. Every CRUD method gets exercised. Run this in the consumer
directory (`go-provider/examples/typescript/`).

## Prerequisites

- `pulumi-resource-<name>` binary built in `go-provider/`
- `sdk/nodejs/` generated and built (`npm run build`)
- `examples/typescript/` set up with `package.json` linked to the SDK
- The upstream API (json-server, real cloud API, etc.) reachable
- A Pulumi stack initialised with appropriate config

## Script (run from `examples/typescript/`)

### 1. Create

```bash
pulumi up --yes
```

**Expected**: All declared resources created. Stack outputs surface
server-assigned IDs.

**Exercises**: `Check`, `Create`, `Diff` (all-new diff is straightforward).

**Verify on the server side**: GET the resource you just created and
confirm only the user-supplied fields are present. The Go framework
cannot serialise a closure into the request body — there is structurally
no equivalent of stage-1's `__provider` leak — but inspecting the server
state proves it, and surfaces any other sidecar fields the framework or
upstream API might have introduced. For json-server:

```bash
curl -s http://localhost:3000/<resource-path> | python3 -m json.tool
```

Confirm: only the input fields plus the server-assigned id appear. No
provider source, no closure-captured config, no framework metadata.

This step turns the structural safety claim ("can't recur in Go") into
an empirical observation, and is the most direct way to demonstrate why
the port is worth doing if the source provider had a leak history.

### 2. Update

Modify *one* field of *one* resource in `index.ts`. Example: flip a
`completed: false` to `completed: true`.

```bash
pulumi up --yes
```

**Expected**: Output annotation `[diff: ~<field-name>]` showing exactly
which field changed.

**Exercises**: `Check`, `Diff`, `Update`.

**Verify**: GET the modified resource. Confirm the changed field has the
new value AND other fields are preserved (i.e., `Update` sent a partial
PATCH, not a full PUT that nuked everything).

```bash
curl -s http://localhost:3000/<resource-path>/<id> | python3 -m json.tool
```

### 3. Refresh (drift detection)

Drift the server-side state out-of-band. Example for json-server:

```bash
curl -s -X PATCH http://localhost:3000/<resource-path>/<id> \
  -H 'Content-Type: application/json' \
  -d '{"<field>":"out-of-band drift"}'
```

```bash
pulumi refresh --yes
```

**Expected**: One resource shown as "updated" (the one you drifted),
others unchanged.

**Exercises**: `Read`. The drift gets pulled into Pulumi state.

A subsequent `pulumi up` should now show a diff (drifted state vs
declared inputs) and reconcile back. If you want to confirm:

```bash
pulumi up --yes
```

You should see the same `[diff: ~<field>]` annotation as in step 2,
running update to put the value back to what `index.ts` declares.

### 4. Idempotent destroy

Manually delete one resource on the server before destroy:

```bash
curl -s -X DELETE http://localhost:3000/<resource-path>/<id>
```

```bash
pulumi destroy --yes
```

**Expected**:

- All resources reported as deleted (count matches what was created).
- For the pre-deleted one: a warning log line containing `"already
  deleted on server"` (or similar from your `Delete` method's log
  statement).

**Exercises**: `Delete`'s 404-as-success path (idempotent destroy).

**Verify**:

```bash
curl -s http://localhost:3000/<resource-path>
# expect: []
pulumi stack
# expect: "No resources currently in this stack"
```

## What success looks like

All four steps above complete without errors (the "provider exited
prematurely" warning at the tail of step 4 is benign — see traps.md).

If any step fails, the failure is almost certainly one of the entries in
[traps.md](./traps.md). Match the symptom and apply the fix.

## What to compare against the source

If both the original TS and the new Go provider can be run side by side
(see [SKILL.md](../SKILL.md) step 1's note about preserving the source as
a comparison artefact), run the same lifecycle against both. Differences
worth noting in the porting log:

- **Resource type token**: `pulumi-nodejs:dynamic:Resource` (TS) vs
  `<provider>:index:<Resource>` (Go).
- **State shape**: TS state has `id` in `outs`; Go state does not (`id`
  is engine-managed).
- **Server-side data shape**: TS may have `__provider` blob; Go won't.
- **Per-operation timing**: roughly the same; Go may have one-time
  provider startup overhead on the first call.
- **Error messages**: should look identical in shape (method, URL,
  status, body).

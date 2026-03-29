# Upgrade Provider Errors

Use this file when the `upgrade-provider` tool fails and you need concrete fixes.
For patch edits/removals/rebases, follow the `upstream-patches` skill workflow.

## Patch conflicts during rebase

The tool uses `scripts/upstream.sh` to apply patch commits in the `upstream` submodule. If a patch no longer applies cleanly, you will see rebase errors like:

```
error: could not apply 83b04967e... docs patching
hint: Resolve all conflicts manually, mark them as resolved with
hint: "git add/rm <conflicted_files>", then run "git rebase --continue".
```

Fix from the `upstream` directory, following `upstream-patches` defaults (edit the owning patch commit; do not create a new patch unless asked):

1. Identify conflicted files.
2. Resolve conflicts while preserving the intent of the patch in `patches/`.
3. Search for conflict markers and remove all of them before continuing.
4. `git add` the resolved files.
5. `git rebase --continue`.

If `git rebase --continue` opens an editor in automation contexts, run with `GIT_EDITOR=true`.

Avoid:

- Hand-editing `patches/*.patch` unless intentionally doing raw patch surgery.
- Direct edits under `upstream/` outside `checkout/check_in` workflow.

After the rebase completes, rerun `upgrade-provider` from the repo root.

### Patch intent guidance

- Docs-related patches usually replace or remove Terraform references. Preserve those changes when resolving conflicts.

## New resources missing module mapping

When new upstream resources appear, token mapping can fail with errors like:

```
* "google_observability_trace_scope": could not find a module that prefixes 'observability_trace_scope' in '[...]'
```

Fix by updating `provider/resources.go` (or the repo-equivalent file):

1. Determine the Terraform module name (usually the first segment after the provider prefix). In the example, use `observability`.
2. Add a module mapping in `moduleMapping`:

```go
var moduleMapping = map[string]string{
  "observability": "Observability",
}
```

3. If related resources already map to a different module, map the new resource individually instead of adding a new module key. Example:

```go
DataSources: map[string]*tfbridge.DataSourceInfo{
  "aws_vpn_gateway": {Tok: awsDataSource(ec2Mod, "getVpnGateway")},
}
```

After updating, rerun `upgrade-provider`.

## ID attribute wrong type (tfgen unresolved ID mapping)

When `make tfgen` fails with an error like:

```
error: Resource linode_producer_image_share_group has a problem: "id" attribute is of type "Int", expected type "string". To map this resource consider overriding the SchemaInfo.Type field or specifying ResourceInfo.ComputeID
error: There were 1 unresolved ID mapping errors
```

The upstream resource has an `id` attribute, but it is not a string. Fix it in `provider/resources.go` (or equivalent) by applying the override:

```go
prov.P.ResourcesMap().Range(func(key string, value shim.Resource) bool {
  if value.Schema().Get("id").Type() != shim.TypeString {
    r := prov.Resources[key]
    if r.Fields == nil {
      r.Fields = make(map[string]*tfbridge.SchemaInfo, 1)
    }
    r.Fields["id"] = &tfbridge.SchemaInfo{Type: "string"}
  }
  return true
})
```

- If the `id` type is not coercible to string, set `ResourceInfo.ComputeID` instead.

## ID attribute is input type (tfgen unresolved ID mapping)

When `make tfgen` fails with an error like:

```
error: Resource cloudflare_zero_trust_access_ai_controls_mcp_server has a problem: an "id" input attribute is not allowed. To map this resource specify SchemaInfo.Name and ResourceInfo.ComputeID
```

The upstream resource exposes `id` as Optional/Required. Remap the input field to `<resource_name>_id` and delegate the ID to that new property. Convert the field name to Pulumi camelCase (for example, `cloudflare_zero_trust_access_ai_controls_mcp_server` -> `zeroTrustAccessAiControlsMcpServerId`).

```go
"cloudflare_zero_trust_access_ai_controls_mcp_server": {
  Fields: map[string]*info.Schema{
    "id": {
      Name: "zeroTrustAccessAiControlsMcpServerId",
    },
  },
  ComputeID: tfbridge.DelegateIDField(resource.PropertyKey("zeroTrustAccessAiControlsMcpServerId"),
    "cloudflare", "https://github.com/pulumi/pulumi-cloudflare"),
},
```

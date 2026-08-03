# ARM / Azure Reference

Reference material for the `pulumi-migrate-from-discovered-stack` skill when working with ARM (or Bicep-derived) discovered stacks. Use this file for:

- Azure credentials and CLI setup (Phase 0 / 2)
- Looking up resource details, verifying existence, finding import IDs (Phase 4 / 5 troubleshooting)
- Provider choice (`azure-native` vs `azure` classic)
- Azure-specific import patterns (child resources, lower-cased IDs)
- The **Preview Resolution Workflow** (§6) — applies to both ARM and CF imports when `pulumi preview` shows a diff after import
- Reading the original ARM template during the optional refactor phase

> **Important:** this is reference, **not a workflow**. The main `SKILL.md` (Phase 0–6) is the workflow. The public `pulumi-arm-to-pulumi` skill prescribes a template-first, mechanical-translation approach — that conflicts with our cloud-state-first import flow. Do not load it alongside this skill.

---

## 1. Azure credentials

Federated-token login via ESC (most Azure ESC environments ship an OIDC token):

```bash
pulumi env run {org}/{project}/{environment} -- bash -c '
  az login --service-principal \
    -u "$ARM_CLIENT_ID" \
    --tenant "$ARM_TENANT_ID" \
    --federated-token "$ARM_OIDC_TOKEN"'
```

Sanity-check credentials before running imports:

```bash
az account show
az account list --query "[].{Name:name, SubscriptionId:id, IsDefault:isDefault}" -o table
```

---

## 2. Azure-specific project setup

After creating the Pulumi project (see SKILL.md Phase 2):

```bash
# Location config — set BOTH if you'll mix azure and azure-native resources
pulumi config set azure-native:location <location>
pulumi config set azure:location <location>

# Install providers
npm install @pulumi/azure-native @pulumi/azure
```

---

## 3. Querying ARM and Azure resources

These help during Phase 5 (NotFound / NoMatch triage) when you need to verify a resource exists or look up an ID our API didn't already capture, and during Phase 7 (optional refactor) to fetch the original template as a structural reference.

### Export the ARM template for a resource group
```bash
az group export --name <rg> --output json > .migration/template.json
```

Used in Phase 7 as a refactor reference (component grouping, parameters, conditional logic). Azure reconstructs the template from live resource state, so `skipAllParameterization: false` is the default — you get parameterized output. For Bicep source when the user has it, ask for the repo instead; Bicep is richer than the exported template.

### List all resources in a resource group
```bash
az resource list --resource-group <rg> --output json
```

### Show a single resource by ID
```bash
az resource show --ids <resource-id> --output json
az resource show --ids <resource-id> --query "{name:name, location:location, properties:properties}" --output json
```

### Targeted service lookups

The generic `az resource show` sometimes hides service-specific details. Use `az <service> show --name <name> --resource-group <rg>` instead (e.g. `az storage account show`, `az webapp show`, `az network vnet show`, `az keyvault show`).

### Azure Resource ID format

Azure Resource IDs follow a predictable pattern. Most `pulumi import` IDs for `azure-native` use this form verbatim:

```
/subscriptions/{sub}/resourceGroups/{rg}/providers/{ns}/{type}/{name}
```

Child resources extend it:

```
.../Microsoft.Web/sites/{site}/config/appsettings
.../Microsoft.Network/networkSecurityGroups/{nsg}/securityRules/{rule}
.../Microsoft.ApiManagement/service/{svc}/apis/{api}/operations/{op}/policies/policy
```

Our API returns the full ID at `resource.inputs.providerId` — use that verbatim in the import file; don't reconstruct it by hand. `resource.inputs.arm.properties.targetResource.id` carries the same ID, but only when the resource currently has deployment metadata (`resource.inputs.deploymentName` non-empty); a placeholder resource (deployment history aged out of Azure's retention) has a different `arm` shape with no `properties.targetResource` — see SKILL.md's "For ARM" section. `providerId` works for both, so prefer it.

### Listing by type
```bash
az resource list --resource-type "Microsoft.Storage/storageAccounts" --output json
```

Useful when our API returns `NoMatch` and you want to see what else in the subscription looks similar.

---

## 4. Provider choice — `azure-native` vs `azure` (classic)

**Default to `azure-native`.** It maps 1:1 with ARM resource types (e.g. `Microsoft.Storage/storageAccounts` → `azure-native:storage:StorageAccount`), which is what our discovery service uses.

**Use `azure` (classic) when:**
- `azure-native` doesn't expose a feature you need.
- The classic resource is significantly simpler for a one-off (e.g. classic has some convenience abstractions for App Service + Plan).
- The user has existing classic-based code in the target stack and you're matching conventions.

**Don't mix providers within a resource group.** Pick one provider per logical cluster of resources; mixing leads to cross-provider dependency issues and harder zero-diff.

### TypeScript output handling for `azure-native`

Same pattern as `aws-native` — outputs often include `undefined`. Avoid `!` non-null assertions; use `.apply()`:

```ts
// WRONG
connectionString: account.primaryConnectionString!,

// CORRECT
connectionString: account.primaryConnectionString.apply(s => s || ""),
```

### Lower-cased IDs

`azure-native` normalizes Azure resource IDs to lowercase internally. If the original ARM template used PascalCase (e.g. `/resourceGroups/MyRG/...`), fingerprint matching against our discovery service may fail even after a clean import — the two records encode the same resource but don't fingerprint-match. Handle via annotation + `linkedResourceUrn` (see SKILL.md Phase 5).

---

## 5. Child resource patterns (Azure-specific)

Many ARM resources decompose into multiple Pulumi resources:

| ARM | Pulumi |
|---|---|
| `Microsoft.Web/sites` | `azure-native:web:WebApp` |
| `Microsoft.Web/sites/config` (appsettings) | `azure-native:web:WebAppApplicationSettings` with ID ending `/config/appsettings` |
| `Microsoft.Web/sites/config` (auth) | `azure-native:web:WebAppAuthSettings` |
| `Microsoft.Web/sites/config` (connectionStrings) | `azure-native:web:WebAppConnectionStrings` |
| `Microsoft.Network/networkSecurityGroups/securityRules` | `azure-native:network:SecurityRule` (separate from the NSG) |
| `Microsoft.ApiManagement/service/apis/operations/policies` | `azure-native:apimanagement:ApiOperationPolicy` |

The discovered API surfaces these as separate `Ready` / `NotFound` entries. The agent must expect them and import each as a standalone resource with its full child-resource ID.

Example import entries:

```json
{"type": "azure-native:web:WebApp",
 "name": "MyWebApp",
 "id": "/subscriptions/.../resourceGroups/rg/providers/Microsoft.Web/sites/mywebapp"},
{"type": "azure-native:web:WebAppApplicationSettings",
 "name": "MyWebAppSettings",
 "id": "/subscriptions/.../resourceGroups/rg/providers/Microsoft.Web/sites/mywebapp/config/appsettings"}
```

---

## 6. Common Azure diff patterns

The generic removed/added/changed diagnostic workflow is in SKILL.md Phase 6. Below are Azure-specific patterns:

| Resource | Property | Resolution |
|---|---|---|
| `StorageAccount` | `networkRuleSet` | Add to code with values from `az storage account show` |
| `StorageAccount` | `encryption.services` | Cloud default; explicit add |
| `StorageAccount` | `primaryEndpoints` | Computed/read-only → `ignoreChanges` |
| `WebApp` | `siteConfig.appSettings` | Often lives in a separate `WebAppApplicationSettings` child resource |
| `WebApp` | `kind` | Must match exact cloud value ("app", "functionapp", "linux", etc.) |
| `VirtualNetwork` | `subnets` | Usually better as separate `Subnet` resources than inline |
| `NetworkSecurityGroup` | `securityRules` | Prefer separate `SecurityRule` resources; inline rules cause diffs |

### Debug command

```bash
pulumi preview --diff --show-config --show-secrets
```

---

## 7. Reading an ARM template (refactor phase only)

After Phase 6 (zero-diff achieved, PR created), if the user wants the imported program to *look* like the original ARM/Bicep (parameterization, variables, copy loops, conditionals, components), the template is the reference. **This is optional polish, not part of the migration itself.** Re-run `pulumi preview` after each refactor change; any new diff means the refactor introduced drift.

### ARM Parameters → Pulumi config

```ts
// ARM: "parameters": {"location": {"type": "string", "defaultValue": "eastus"}}
const config = new pulumi.Config();
const location = config.get("location") || "eastus";
const replicas = config.getNumber("replicas") || 3;
const enabled = config.getBoolean("enabled") ?? true;
const password = config.requireSecret("adminPassword");
```

### ARM Variables → Pulumi constants

```ts
// ARM: "variables": {"storageSku": "Standard_LRS"}
const storageSku = "Standard_LRS";
```

ARM's `uniqueString()` is *not* cryptographically equivalent to anything in Pulumi. If you need a deterministic suffix, use a truncated hash of the stack name or a `random.RandomString` resource with a fixed seed.

### ARM `copy` loops → JS loops

```ts
// ARM: "copy": {"name": "subnetLoop", "count": 3}
for (let i = 0; i < 3; i++) {
  new azure_native.network.Subnet(`subnet-${i}`, { ... });
}
```

### ARM `condition` → JS conditionals

```ts
// ARM: "condition": "[equals(parameters('env'), 'prod')]"
if (env === "prod") {
  new azure_native.monitor.DiagnosticSetting(...);
}
```

### ARM `dependsOn` → Pulumi dependencies

- **Prefer implicit**: reference the other resource's output (`subnet.id`) in the dependent resource's inputs. Pulumi tracks the dependency automatically.
- **Explicit** `dependsOn: [...]` resource option only when there's no property-level reference but ordering still matters.

### ARM intrinsic functions → Pulumi equivalents

| ARM | Pulumi |
|---|---|
| `resourceId('Microsoft.Storage/...', name)` | resource output (`account.id`) |
| `reference(resource)` | resource output object |
| `concat(a, '/', b)` | template literal or `pulumi.interpolate` |
| `format('{0}-{1}', a, b)` | template literal |
| `parameters('x')` | `config.get("x")` |
| `variables('x')` | local const |
| `resourceGroup().location` | `resourceGroup.location` |
| `subscription().subscriptionId` | `azure.core.getClientConfig().subscriptionId` |
| `uniqueString(...)` | deterministic hash, or accept non-determinism |
| `if(cond, a, b)` | `cond ? a : b` |

### Nested templates → Pulumi Component Resources

An ARM nested template (linked template) typically maps to a Pulumi `ComponentResource`:

```ts
class NetworkComponent extends pulumi.ComponentResource {
  public readonly vnet: azure_native.network.VirtualNetwork;
  public readonly subnets: azure_native.network.Subnet[];

  constructor(name: string, args: NetworkArgs, opts?: pulumi.ComponentResourceOptions) {
    super("custom:network:NetworkComponent", name, {}, opts);
    this.vnet = new azure_native.network.VirtualNetwork(`${name}-vnet`, {...}, {parent: this});
    this.subnets = args.subnets.map((s, i) =>
      new azure_native.network.Subnet(`${name}-subnet-${i}`, {...}, {parent: this}));
    this.registerOutputs({vnet: this.vnet, subnets: this.subnets});
  }
}
```

### ARM Outputs → Pulumi exports

```ts
// ARM: "outputs": {"vnetId": {"type": "string", "value": "[reference(...).id]"}}
export const vnetId = vnet.id;
```

### Common pitfalls

- Missing `.apply()` on Output types — TypeScript errors or string-vs-Output confusion.
- Confusing Pulumi resource *name* (logical) with ARM resource `name` (the storage account's actual name, the VM's hostname, etc.). Both are required and different.
- Assuming ARM property names match Pulumi (`accountName` vs `name`, `skuName` vs `sku.name`, etc.) — always check the Pulumi schema.
- Forgetting to translate `concat()` / `format()` / `uniqueString()` — these are runtime ARM functions, not constants.

---

## 8. Further reading

- [Pulumi Azure Native provider](https://www.pulumi.com/registry/packages/azure-native/)
- [Pulumi Azure (classic) provider](https://www.pulumi.com/registry/packages/azure/)
- [Migrating to Pulumi from ARM](https://www.pulumi.com/docs/iac/adopting-pulumi/migrating-to-pulumi/from-arm/)
- [ARM template syntax](https://learn.microsoft.com/en-us/azure/azure-resource-manager/templates/syntax)
- [ARM template functions](https://learn.microsoft.com/en-us/azure/azure-resource-manager/templates/template-functions-resource)
- [Azure CLI docs](https://learn.microsoft.com/en-us/cli/azure/)

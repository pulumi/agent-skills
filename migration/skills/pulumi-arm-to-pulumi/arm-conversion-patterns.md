# ARM → Pulumi Conversion Patterns

Reference guide for translating ARM template constructs to Pulumi TypeScript. Covers all common patterns plus Azure Classic provider examples.

## Basic Resource Conversion

**ARM Template:**

```json
{
  "type": "Microsoft.Storage/storageAccounts",
  "apiVersion": "2023-01-01",
  "name": "[parameters('storageAccountName')]",
  "location": "[parameters('location')]",
  "sku": {
    "name": "Standard_LRS"
  },
  "kind": "StorageV2",
  "properties": {
    "supportsHttpsTrafficOnly": true
  }
}
```

**Pulumi TypeScript:**

```typescript
import * as pulumi from "@pulumi/pulumi";
import * as azure_native from "@pulumi/azure-native";

const config = new pulumi.Config();
const storageAccountName = config.require("storageAccountName");
const location = config.require("location");
const resourceGroupName = config.require("resourceGroupName");

const storageAccount = new azure_native.storage.StorageAccount("storageAccount", {
    accountName: storageAccountName,
    location: location,
    resourceGroupName: resourceGroupName,
    sku: {
        name: azure_native.storage.SkuName.Standard_LRS,
    },
    kind: azure_native.storage.Kind.StorageV2,
    enableHttpsTrafficOnly: true,
});
```

## ARM Parameters → Pulumi Config

**ARM Template:**

```json
{
  "parameters": {
    "location": {
      "type": "string",
      "defaultValue": "eastus",
      "metadata": {
        "description": "Location for resources"
      }
    },
    "instanceCount": {
      "type": "int",
      "defaultValue": 2,
      "minValue": 1,
      "maxValue": 10
    },
    "enableBackup": {
      "type": "bool",
      "defaultValue": true
    },
    "secretValue": {
      "type": "securestring"
    }
  }
}
```

**Pulumi TypeScript:**

```typescript
const config = new pulumi.Config();
const location = config.get("location") || "eastus";
const instanceCount = config.getNumber("instanceCount") || 2;
const enableBackup = config.getBoolean("enableBackup") ?? true;
const secretValue = config.requireSecret("secretValue"); // Returns Output<string>
```

## ARM Variables → Pulumi Variables

**ARM Template:**

```json
{
  "variables": {
    "storageAccountName": "[concat('storage', uniqueString(resourceGroup().id))]",
    "webAppName": "[concat(parameters('prefix'), '-webapp')]"
  }
}
```

**Pulumi TypeScript:**

```typescript
import * as pulumi from "@pulumi/pulumi";

const config = new pulumi.Config();
const prefix = config.require("prefix");
const resourceGroupId = config.require("resourceGroupId");

// Simple variable
const webAppName = `${prefix}-webapp`;

// ARM's uniqueString() produces a deterministic 13-char hash — use a fixed suffix
// from config or a truncated ID as an approximation:
// const storageAccountName = `storage${resourceGroupId.substring(0, 8)}`.toLowerCase();
// Note: not cryptographically equivalent to ARM's uniqueString()
const storageAccountName = `storage${resourceGroupId}`.toLowerCase();
```

## ARM Copy Loops → Pulumi Loops

**ARM Template:**

```json
{
  "type": "Microsoft.Network/virtualNetworks/subnets",
  "apiVersion": "2023-05-01",
  "name": "[concat(variables('vnetName'), '/subnet-', copyIndex())]",
  "copy": {
    "name": "subnetCopy",
    "count": "[parameters('subnetCount')]"
  },
  "properties": {
    "addressPrefix": "[concat('10.0.', copyIndex(), '.0/24')]"
  }
}
```

**Pulumi TypeScript:**

```typescript
const config = new pulumi.Config();
const subnetCount = config.getNumber("subnetCount") || 3;

const subnets: azure_native.network.Subnet[] = [];
for (let i = 0; i < subnetCount; i++) {
    subnets.push(new azure_native.network.Subnet(`subnet-${i}`, {
        subnetName: `subnet-${i}`,
        virtualNetworkName: vnet.name,
        resourceGroupName: resourceGroup.name,
        addressPrefix: `10.0.${i}.0/24`,
    }));
}
```

## ARM Conditional Resources → Pulumi Conditionals

**ARM Template:**

```json
{
  "type": "Microsoft.Network/publicIPAddresses",
  "apiVersion": "2023-05-01",
  "condition": "[parameters('createPublicIP')]",
  "name": "[variables('publicIPName')]",
  "location": "[parameters('location')]"
}
```

**Pulumi TypeScript:**

```typescript
const config = new pulumi.Config();
const createPublicIP = config.getBoolean("createPublicIP") ?? false;

let publicIP: azure_native.network.PublicIPAddress | undefined;
if (createPublicIP) {
    publicIP = new azure_native.network.PublicIPAddress("publicIP", {
        publicIpAddressName: publicIPName,
        location: location,
        resourceGroupName: resourceGroup.name,
    });
}

// Handle optional references
const publicIPId = publicIP ? publicIP.id : pulumi.output(undefined);
```

## ARM DependsOn → Pulumi Dependencies

**ARM Template:**

```json
{
  "type": "Microsoft.Web/sites",
  "apiVersion": "2023-01-01",
  "name": "[variables('webAppName')]",
  "dependsOn": [
    "[resourceId('Microsoft.Web/serverfarms', variables('appServicePlanName'))]"
  ]
}
```

**Pulumi TypeScript:**

```typescript
// Implicit dependency (preferred)
const webApp = new azure_native.web.WebApp("webApp", {
    name: webAppName,
    resourceGroupName: resourceGroup.name,
    serverFarmId: appServicePlan.id, // Implicit dependency through property reference
});

// Explicit dependency (when needed)
const webApp = new azure_native.web.WebApp("webApp", {
    name: webAppName,
    resourceGroupName: resourceGroup.name,
    serverFarmId: appServicePlan.id,
}, {
    dependsOn: [appServicePlan], // Explicit dependency
});
```

## Nested Templates → Pulumi Component Resources

**ARM Template:**

```json
{
  "type": "Microsoft.Resources/deployments",
  "apiVersion": "2021-04-01",
  "name": "nestedTemplate",
  "properties": {
    "mode": "Incremental",
    "template": {
      "resources": [...]
    }
  }
}
```

**Pulumi Approach:**

Instead of nested templates, use Pulumi ComponentResource to group related resources:

```typescript
class NetworkComponent extends pulumi.ComponentResource {
    public readonly vnet: azure_native.network.VirtualNetwork;
    public readonly subnets: azure_native.network.Subnet[];

    constructor(name: string, args: NetworkComponentArgs, opts?: pulumi.ComponentResourceOptions) {
        super("custom:azure:NetworkComponent", name, {}, opts);

        const defaultOptions = { parent: this };

        this.vnet = new azure_native.network.VirtualNetwork(`${name}-vnet`, {
            virtualNetworkName: args.vnetName,
            resourceGroupName: args.resourceGroupName,
            location: args.location,
            addressSpace: {
                addressPrefixes: [args.addressPrefix],
            },
        }, defaultOptions);

        this.subnets = args.subnets.map((subnet, i) =>
            new azure_native.network.Subnet(`${name}-subnet-${i}`, {
                subnetName: subnet.name,
                virtualNetworkName: this.vnet.name,
                resourceGroupName: args.resourceGroupName,
                addressPrefix: subnet.addressPrefix,
            }, defaultOptions)
        );

        this.registerOutputs({
            vnetId: this.vnet.id,
            subnetIds: this.subnets.map(s => s.id),
        });
    }
}
```

## ARM Outputs → Pulumi Exports

**ARM Template:**

```json
{
  "outputs": {
    "storageAccountName": {
      "type": "string",
      "value": "[variables('storageAccountName')]"
    },
    "storageAccountId": {
      "type": "string",
      "value": "[resourceId('Microsoft.Storage/storageAccounts', variables('storageAccountName'))]"
    }
  }
}
```

**Pulumi TypeScript:**

```typescript
export const storageAccountName = storageAccount.name;
export const storageAccountId = storageAccount.id;
```

## Azure Classic Provider Examples

Use `@pulumi/azure` (classic) when `azure-native` doesn't support a feature or when simplified abstractions are preferred.

### Virtual Network with Classic Provider

**ARM Template:**

```json
{
  "type": "Microsoft.Network/virtualNetworks",
  "apiVersion": "2023-05-01",
  "name": "[parameters('vnetName')]",
  "location": "[parameters('location')]",
  "properties": {
    "addressSpace": {
      "addressPrefixes": ["10.0.0.0/16"]
    },
    "subnets": [
      { "name": "default", "properties": { "addressPrefix": "10.0.1.0/24" } },
      { "name": "apps",    "properties": { "addressPrefix": "10.0.2.0/24" } }
    ]
  }
}
```

**Pulumi TypeScript (Classic Provider):**

```typescript
import * as pulumi from "@pulumi/pulumi";
import * as azure from "@pulumi/azure";

const config = new pulumi.Config();
const vnetName = config.require("vnetName");
const location = config.require("location");
const resourceGroupName = config.require("resourceGroupName");

const vnet = new azure.network.VirtualNetwork("vnet", {
    name: vnetName,
    location: location,
    resourceGroupName: resourceGroupName,
    addressSpaces: ["10.0.0.0/16"],
    subnets: [
        { name: "default", addressPrefix: "10.0.1.0/24" },
        { name: "apps",    addressPrefix: "10.0.2.0/24" },
    ],
});
```

**Note:** The Classic provider allows defining subnets inline within the VirtualNetwork resource.

### App Service Plan and Web App with Classic Provider

**ARM Template:**

```json
{
  "resources": [
    {
      "type": "Microsoft.Web/serverfarms",
      "apiVersion": "2023-01-01",
      "name": "[parameters('appServicePlanName')]",
      "location": "[parameters('location')]",
      "sku": { "name": "B1", "tier": "Basic", "size": "B1", "capacity": 1 },
      "kind": "linux",
      "properties": { "reserved": true }
    },
    {
      "type": "Microsoft.Web/sites",
      "apiVersion": "2023-01-01",
      "name": "[parameters('webAppName')]",
      "location": "[parameters('location')]",
      "dependsOn": [
        "[resourceId('Microsoft.Web/serverfarms', parameters('appServicePlanName'))]"
      ],
      "properties": {
        "serverFarmId": "[resourceId('Microsoft.Web/serverfarms', parameters('appServicePlanName'))]",
        "siteConfig": {
          "linuxFxVersion": "NODE|18-lts",
          "appSettings": [{ "name": "WEBSITE_NODE_DEFAULT_VERSION", "value": "~18" }]
        }
      }
    }
  ]
}
```

**Pulumi TypeScript (Classic Provider):**

```typescript
import * as pulumi from "@pulumi/pulumi";
import * as azure from "@pulumi/azure";

const config = new pulumi.Config();
const appServicePlanName = config.require("appServicePlanName");
const webAppName = config.require("webAppName");
const location = config.require("location");
const resourceGroupName = config.require("resourceGroupName");

const appServicePlan = new azure.appservice.ServicePlan("appServicePlan", {
    name: appServicePlanName,
    location: location,
    resourceGroupName: resourceGroupName,
    osType: "Linux",
    skuName: "B1",
});

const webApp = new azure.appservice.LinuxWebApp("webApp", {
    name: webAppName,
    location: location,
    resourceGroupName: resourceGroupName,
    servicePlanId: appServicePlan.id,
    siteConfig: {
        applicationStack: { nodeVersion: "18-lts" },
    },
    appSettings: {
        "WEBSITE_NODE_DEFAULT_VERSION": "~18",
    },
});
```

**Note:** The Classic provider has dedicated `LinuxWebApp` and `WindowsWebApp` resources with better type safety than the generic `WebApp`.

## Handling Azure-Specific Considerations

### TypeScript Output Handling

Azure Native outputs often include `undefined`. Avoid `!` non-null assertions. Always safely unwrap with `.apply()`:

```typescript
// ❌ WRONG - Will cause TypeScript errors
const webAppUrl = `https://${webApp.defaultHostName!}`;

// ✅ CORRECT - Handle undefined safely
const webAppUrl = webApp.defaultHostName.apply(hostname =>
    hostname ? `https://${hostname}` : ""
);
```

### Resource Naming Conventions

ARM template `name` property maps to specific naming fields in Pulumi:

```typescript
// ARM: "name": "myStorageAccount"
// Pulumi:
new azure_native.storage.StorageAccount("logicalName", {
    accountName: "mystorageaccount", // Actual Azure resource name
    // ...
});
```

### API Versions

ARM templates require explicit API versions. Pulumi providers use recent stable API versions by default. Check the Pulumi Registry documentation for which API version each resource uses.

## Common Pitfalls to Avoid

- ❌ Not handling Output types properly (missing `.apply()` in TypeScript)
- ❌ Assuming ARM property names match Pulumi property names exactly
- ❌ Defaulting to the `azure` classic provider without checking `azure-native` first — prefer `azure-native` unless the resource is unsupported or the user explicitly prefers classic abstractions
- ❌ Missing resource dependencies in conversion
- ❌ Not preserving ARM template conditionals and loops
- ❌ Forgetting to convert ARM functions like `concat()`, `uniqueString()`, etc.

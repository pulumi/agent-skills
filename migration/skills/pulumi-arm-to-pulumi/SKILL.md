---
name: pulumi-arm-to-pulumi
description: Convert or migrate Azure ARM (Azure Resource Manager) templates, Bicep templates, or code to Pulumi, including importing existing Azure resources. This skill MUST be loaded whenever a user requests migration, conversion, or import of ARM templates, Bicep templates, ARM code, Bicep code, or Azure resources to Pulumi.
---

## IMPORTANT: PLAN ADJUSTMENT REQUIRED

**If you have already generated a migration plan before loading this skill, you MUST:**

1. Review your existing plan against the workflows and requirements in this skill
2. Identify any gaps, missing steps, or incorrect assumptions
3. Update and revise your plan to align with this skill's guidance
4. Communicate the adjusted plan to the user before proceeding

## CRITICAL SUCCESS REQUIREMENTS

The migration output MUST meet all of the following:

1. **Complete Resource Coverage**
   - Every ARM template resource MUST:
     - Be represented in the Pulumi program **OR**
     - Be explicitly justified in the final report.

2. **Successful Deployment**
   - The produced Pulumi program must be structurally valid and capable of a successful `pulumi preview` (assuming proper config).

3. **Zero-Diff Import Validation** (if importing existing resources)
   - After import, `pulumi preview` must show:
     - NO updates
     - NO replaces
     - NO creates
     - NO deletes
   - Any diffs must be resolved using the Preview Resolution Workflow. See [arm-import.md](arm-import.md).

4. **Final Migration Report**
   - Always output a formal migration report suitable for a Pull Request.
   - Include:
     - ARM → Pulumi resource mapping
     - Provider decisions (azure-native vs azure)
     - Behavioral differences
     - Missing or manually required steps
     - Validation instructions

## WHEN INFORMATION IS MISSING

If a user-provided ARM template is incomplete, ambiguous, or missing artifacts, ask **targeted questions** before generating Pulumi code.

If there is ambiguity on how to handle a specific resource property on import, ask **targeted questions** before altering Pulumi code.

## MIGRATION WORKFLOW

Follow this workflow **exactly** and in this order:

### 1. INFORMATION GATHERING

#### 1.1 Verify Azure Credentials

Running Azure CLI commands (e.g., `az resource list`, `az resource show`). Requires initial login using ESC and `az login`

- If the user has already provided an ESC environment, use it.
- If no ESC environment is specified, **ask the user which ESC environment to use** before proceeding with Azure CLI commands.

**Setting up Azure CLI using ESC:**

- ESC environments can provide Azure credentials through environment variables or Azure CLI configuration
- Login to Azure using ESC to provide credentials, e.g: `pulumi env run {org}/{project}/{environment} -- bash -c 'az login --service-principal -u "$ARM_CLIENT_ID" --tenant "$ARM_TENANT_ID" --federated-token "$ARM_OIDC_TOKEN"'`. ESC is not required after establishing the session
- Verify credentials are working: `az account show`
- Confirm subscription: `az account list --query "[].{Name:name, SubscriptionId:id, IsDefault:isDefault}" -o table`

**For detailed ESC information:** Load the `pulumi-esc` skill by calling the tool "Skill" with name = "pulumi-esc"

#### 1.2 Analyze ARM Template Structure

ARM templates do not have the concept of "stacks" like CloudFormation. Read the ARM template JSON file directly:

```bash
# View template structure
cat template.json | jq '.resources[] | {type: .type, name: .name}'

# View parameters
cat template.json | jq '.parameters'

# View variables
cat template.json | jq '.variables'
```

Extract:

- Resource types and names
- Parameters and their default values
- Variables and expressions
- Dependencies (dependsOn arrays)
- Nested templates or linked templates
- Copy loops (iteration constructs)
- Conditional deployments (condition property)

**Documentation:** [ARM Template Structure](https://learn.microsoft.com/en-us/azure/azure-resource-manager/templates/syntax)

#### 1.3 Build Resource Inventory (if importing existing resources)

If the ARM template has already been deployed and you're importing existing resources:

```bash
# List all resources in a resource group
az resource list \
  --resource-group <resource-group-name> \
  --output json

# Get specific resource details
az resource show \
  --ids <resource-id> \
  --output json

# Query specific properties using JMESPath
az resource show \
  --ids <resource-id> \
  --query "{name:name, location:location, properties:properties}" \
  --output json
```

**Documentation:** [Azure CLI Documentation](https://learn.microsoft.com/en-us/cli/azure/)

### 2. CODE CONVERSION (ARM → PULUMI)

**IMPORTANT:** ARM to Pulumi conversion requires manual translation. There is **NO** automated conversion tool for ARM templates. You are responsible for the complete conversion.

#### Key Conversion Principles

1. **Provider Strategy**:
   - **Default**: Use `@pulumi/azure-native` for full Azure Resource Manager API coverage
   - **Fallback**: Use `@pulumi/azure` (classic provider) when azure-native doesn't support specific features or when you need simplified abstractions

   **Documentation:**
   - [Azure Native Provider](https://www.pulumi.com/registry/packages/azure-native/)
   - [Azure Classic Provider](https://www.pulumi.com/registry/packages/azure/)

2. **Language Support**:
   - **TypeScript/JavaScript**: Most common, excellent IDE support
   - **Python**: Great for data teams and ML workflows
   - **C#**: Natural fit for .NET teams
   - **Go**: High performance, strong typing
   - **Java**: Enterprise Java teams
   - **YAML**: Simple declarative approach
   - Choose based on user preference or existing codebase

3. **Complete Coverage**:
   - Convert ALL resources in the ARM template
   - Preserve all conditionals, loops, and dependencies
   - Maintain parameter and variable logic

**Follow conversion patterns in [arm-conversion-patterns.md](arm-conversion-patterns.md).**

[arm-conversion-patterns.md](arm-conversion-patterns.md) provides:

- Parameters, variables, and outputs mapping
- Copy loops, conditionals, and dependsOn translation
- Nested templates → ComponentResource
- Azure Classic provider examples (VNet, App Service)
- TypeScript output handling and common pitfalls

### 3. RESOURCE IMPORT (EXISTING RESOURCES) - OPTIONAL

After conversion, you can optionally import existing resources to be managed by Pulumi. If the user does not request this, suggest it as a follow-up step to conversion.

**CRITICAL**: When the user requests importing existing Azure resources into Pulumi, see [arm-import.md](arm-import.md) for detailed import procedures and zero-diff validation workflows.

[arm-import.md](arm-import.md) provides:

- Inline import ID patterns and examples
- Azure Resource ID format conventions
- Child resource handling (e.g., WebAppApplicationSettings)
- **Preview Resolution Workflow** for achieving zero-diff after import
- Step-by-step debugging for property conflicts

#### Key Import Principles

1. **Inline Import Approach**:
   - Use `import` resource option with Azure Resource IDs
   - No separate import tool (unlike `pulumi-cdk-importer`)

2. **Azure Resource IDs**:
   - Follow predictable pattern: `/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/{resourceProviderNamespace}/{resourceType}/{resourceName}`
   - Can be generated by convention or queried via Azure CLI

3. **Zero-Diff Validation**:
   - Run `pulumi preview` after import
   - Resolve all diffs using Preview Resolution Workflow
   - Goal: NO updates, replaces, creates, or deletes

### 4. PULUMI CONFIGURATION

Set up stack configuration matching ARM template parameters:

```bash
# Set Azure region
pulumi config set azure-native:location eastus --stack dev

# Set application parameters
pulumi config set storageAccountName mystorageaccount --stack dev

# Set secret parameters
pulumi config set --secret adminPassword MyS3cr3tP@ssw0rd --stack dev
```

### 5. VALIDATION

After achieving zero diff in preview (if importing), validate the migration:

1. **Review all exports:**

   ```bash
   pulumi stack output
   ```

2. **Verify resource relationships:**

   ```bash
   pulumi stack graph
   ```

3. **Test application functionality** (if applicable)

4. **Document any manual steps** required post-migration

## WORKING WITH THE USER

If the user asks for help planning or performing an ARM to Pulumi migration, use the information above to guide the user through the conversion and import process.

## FOR DETAILED DOCUMENTATION

When the user wants additional information, use the web-fetch tool to get content from the official Pulumi documentation:

- **ARM Migration Guide:** https://www.pulumi.com/docs/iac/adopting-pulumi/migrating-to-pulumi/from-arm/
- **Azure Native Provider:** https://www.pulumi.com/registry/packages/azure-native/
- **Azure Classic Provider:** https://www.pulumi.com/registry/packages/azure/

**Microsoft Azure Documentation:**

- **ARM Template Reference:** https://learn.microsoft.com/en-us/azure/azure-resource-manager/templates/
- **Azure CLI Reference:** https://learn.microsoft.com/en-us/cli/azure/
- **Azure Resource IDs:** https://learn.microsoft.com/en-us/azure/azure-resource-manager/templates/template-functions-resource

## OUTPUT FORMAT (REQUIRED)

When performing a migration, always produce:

1. **Overview** (high-level description)
2. **Migration Plan Summary**
   - ARM template resources identified
   - Conversion strategy (language, providers)
   - Import approach (if applicable)
3. **Pulumi Code Outputs** (organized by file)
   - Main program file
   - Component resources (if any)
   - Configuration instructions
4. **Resource Mapping Table** (ARM → Pulumi)
   - ARM resource type → Pulumi resource type
   - ARM resource name → Pulumi logical name
   - Import ID (if importing)
5. **Preview Resolution Notes** (if importing)
   - Diffs encountered
   - Resolution strategy applied
   - Properties ignored vs. added
6. **Final Migration Report** (PR-ready)
   - Summary of changes
   - Testing instructions
   - Known limitations
   - Next steps
7. **Configuration Setup**
   - Required config values
   - Example `pulumi config set` commands

Keep code syntactically valid and clearly separated by files.

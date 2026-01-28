# Pulumi CDK Conversion Tool (`cdk2pulumi`)

This tool plugin converts AWS CDK Cloud Assemblies to Pulumi YAML programs.

## Prerequisites

- The tool must be installed: `pulumi plugin install tool cdk2pulumi`
- All commands run through the Pulumi CLI using: `pulumi plugin run cdk2pulumi -- <args>`
- A CDK Cloud Assembly (typically in `cdk.out` directory) must exist for conversion operations

## Commands

### 1. Convert CDK Assembly to Pulumi YAML

Converts a CDK Cloud Assembly to a Pulumi YAML program (`Pulumi.yaml`) with an accompanying conversion report (`Pulumi.yaml.report.json`).

**Basic conversion:**

```bash
pulumi plugin run cdk2pulumi -- --assembly path/to/cdk.out
```

**Required flags:**

- `--assembly`: Path to the synthesized CDK Cloud Assembly (typically `cdk.out` directory). By default this will convert the entire CDK application (i.e. all stacks and stages)

**Optional flags:**

- `--stacks`: Comma separated list of CDK Stacks to convert
- `--stage`: Filter conversion to a specific CDK Stage
- `--skip-custom`: Skip converting CDK custom resources

**Important Notes:**

- Cross-stack references in partially converted stacks become config placeholders: `${external.<stack>.<output>}`
- Set these with: `pulumi config set external.<stack>.<output> <value>` before deployment
- CDK custom resources are rewritten to `aws-native:cloudformation:CustomResourceEmulator`
- The generated code will use the original CDK logical IDS. DO NOT update these otherwise automated import will FAIL

## Common Workflows

### Converting a CDK Application to Pulumi

1. **Synthesize the CDK app** to generate the Cloud Assembly:

   ```bash
   cdk synth
   ```

2. **Convert the assembly** to Pulumi YAML:

   ```bash
   pulumi plugin run cdk2pulumi -- --assembly cdk.out
   ```

3. **Review the conversion report** at `Pulumi.yaml.report.json` to identify any resources that didn't convert 1:1

4. **Set any required config** for cross-stack references:

   ```bash
   pulumi config set external.<stack>.<output> <value>
   ```

5. **Convert the Pulumi YAML program** to the target language:

   ```bash
   pulumi convert --from yaml --generate-only --language typescript --out ./generated-program
   ```

   > NOTE: after converting to another language you need to remove or rename the `Pulumi.yaml` file, otherwise it will still be treated as the main application

6. **Preview** the Pulumi program:

   ```bash
   pulumi preview
   ```

## Tips for Running

- Always use `--` to separate Pulumi CLI arguments from plugin arguments
- The `--assembly` flag expects a directory path (typically `cdk.out`), not a file
- When converting specific stacks, use comma-separated names without spaces: `--stacks Stack1,Stack2`
- For multi-stage CDK apps, use `--stage <name>` to target nested assemblies
- The tool outputs to `Pulumi.yaml` by default; use `--out` to specify a different location

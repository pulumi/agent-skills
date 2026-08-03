---
name: pulumi-migrate-from-discovered-stack
description: |
    Migrate a CloudFormation or ARM stack into a Pulumi stack, sourced from a
    stack that Pulumi Cloud's Discovery feature has already found and exposed
    via the discovered-stacks API. Load this skill when the user has a
    discovered stack in Pulumi Cloud and wants to bring its resources under
    Pulumi management. Do NOT load for greenfield Pulumi authoring, raw
    template conversion with no discovered-stack counterpart (i.e. no matching
    entry from the discovered-stacks API), or Terraform migration.
---

**Scope: this skill only applies to stacks Pulumi Cloud's Discovery feature has already scanned and exposed through the discovered-stacks API** (`GET .../discovered-stacks/{projectName}/{stackName}/resources`, see below). It is not for migrating an arbitrary CloudFormation/ARM template or account that Discovery hasn't scanned yet — if no discovered stack exists for the source, this skill has nothing to read and does not apply.

> **Do not load `cloudformation-to-pulumi` or `pulumi-arm-to-pulumi` alongside this skill.** Those two skills prescribe a template-first workflow (mechanical translation → import) and mandate `aws-native` for AWS. This skill is cloud-state-first (import from discovered state → optional refactor against the template later) and defaults to `aws` classic / `azure-native`. The useful reference material from those two skills has been curated into [`cloudformation.md`](cloudformation.md) and [`arm.md`](arm.md) in this folder.

---

## Plan adjustment

If you already generated a migration plan before loading this skill, review it against the workflow below and update it — the phases here supersede any earlier plan. Communicate the adjusted plan to the user before proceeding.

## Success criteria

A migration is complete when:

1. **Complete resource coverage** — every discovered resource is imported OR has an annotation explaining why not.
2. **Zero-diff** — `pulumi preview` shows no changes. This proves the code matches the cloud state exactly.
3. **Progress tracked via the API** — use `compareTo` and migration annotations so progress is visible in Pulumi Cloud, not just in agent memory.
4. **PR as the output** — a pull request with the migrated code and a migration report.

## THE DISCOVERED-STACKS API

### Fetching resources

```
GET /api/preview/insights/{orgName}/discovered-stacks/{projectName}/{stackName}/resources?compareTo={targetProject}/{targetStack}
```

Always include `compareTo` if the target Pulumi stack exists (it may already have state from a previous migration attempt). Returns a list of `DiscoveredResourceInfo` objects. **The JSON paths below are exact — verify before consuming:**

-   `name` — top-level: logical name (CF Logical ID / ARM resource name). **Use this as the Pulumi resource name.**
-   `originType` — top-level: native cloud type (e.g. `AWS::S3::Bucket`, `Microsoft.Storage/storageAccounts`)
-   `providerType` — top-level: mapped Pulumi type token (e.g. `aws:s3/bucket:Bucket`). `null` if unmapped.
-   `resource.inputs.providerId` — physical cloud ID for `pulumi import`.
-   `resource.urn` — the URN to use as `resourceUrn` in annotation requests (copy verbatim).
-   `migrationStatus` — top-level: one of the statuses below.
-   `annotation` — top-level: user/agent annotation if one exists (see Annotations below).

The `resource.inputs` object also carries raw cloud-provider data:

**For CloudFormation** — `resource.inputs.cloudFormation`:

-   `physicalResourceId` — the original CF physical ID
-   `resourceType` — the CF type (e.g. `AWS::IAM::Role`)
-   `resourceStatus` — e.g. `CREATE_COMPLETE`, `DELETE_COMPLETE`
-   `driftStatus` — `NOT_CHECKED`, `IN_SYNC`, `DRIFTED`

For CDK-synthesized CF stacks, `inputs.cdkPath` is also present — see [`cloudformation.md §5`](cloudformation.md) for how to use it.

**For ARM** — `resource.inputs.arm`. ARM resources are grouped by resource group, not by
deployment, so a resource with no deployment currently backing it (its deployment history
aged out of Azure's retention window, or it was created outside any tracked deployment) is
still returned — just as a placeholder, with `resource.inputs.deploymentName` empty and a
different `arm` shape:

-   **Deployment-backed** (`resource.inputs.deploymentName` non-empty) — `arm` is a
    deployment-operation object: `properties.targetResource.id` / `.resourceType` /
    `.resourceName`, `properties.provisioningState` (e.g. `Succeeded`).
-   **Placeholder** (`resource.inputs.deploymentName` empty) — `arm` is the raw Azure
    generic-resource object instead: top-level `id`, `name`, `type`, `location`, `tags`.
    No `properties.targetResource` — don't look for it.

Either way, prefer the top-level `resource.inputs.providerId` for the import ID (see
above) rather than reaching into `arm` — it's already normalized across both shapes.

### Migration statuses

Statuses are PascalCase. First match wins:

1. **`Migrated`** — the resource was found in the `compareTo` Pulumi stack. Already under Pulumi management; skip.
2. **`Ready`** — `providerType` and `providerId` are set and the scanner confirmed the resource exists. Import with `pulumi import <providerType> <name> <providerId> --generate-code --out <file>.ts` (NEVER without `--generate-code --out` — see Phase 4).
3. **`NotFound`** — `providerType` and `providerId` are set, but the scanner could not confirm the resource's current state. May be deleted, mapping may be imperfect, or scanner hit a gap. Verify before importing.
4. **`NotApplicable`** — container or wrapper types (`AWS::CloudFormation::Stack`, `Microsoft.Resources/deployments`, `Microsoft.Resources/resourceGroups`, `pulumi:providers:*`) are not individually migratable. Skip silently.
5. **`NoMatch`** — `providerType` is `null`. No mapping found. Common examples:
    - CF Custom Resources (e.g. `Custom::VpcRestrictDefaultSG`) — no direct Pulumi equivalent.
    - Inline policies — `AWS::IAM::Policy` modeled as an inline property of `aws:iam/role:Role`. Once the parent Role is migrated, annotate the policy as migrated.
6. **`PulumiOnly`** — exists in the `compareTo` stack with no discovered counterpart, or those created to migrate NoMatch resources. Surface to user.

Resources with `annotation.statusOverride` should be treated as resolved per the override, even if the computed status disagrees.

### Annotations

```
PUT  /api/preview/insights/{orgName}/discovered-stacks/{projectName}/{stackName}/migration
DELETE /api/preview/insights/{orgName}/discovered-stacks/{projectName}/{stackName}/migration?resourceUrn={urn}
```

PUT body:

```json
{
  "resourceUrn": "<copy verbatim from resource.urn in the list response>",
  "note": "explanation of what happened",
  "statusOverride": "Migrated" | "",
  "linkedResourceUrn": "<optional: URN of the Pulumi resource paired 1:1 with this origin>"
}
```

Use the Pulumi Cloud API for all annotation requests. At least one of `note` or `statusOverride` must be non-empty. Omit `statusOverride` entirely (do not send `null`) when updating only the note. The DELETE endpoint clears both the note and any `statusOverride`.

Use annotations to:

-   Flag deleted resources as `Migrated` with a note explaining they no longer exist
-   Flag inline/child resources covered by a parent's migration as `Migrated` with a note naming the parent — **do not** use `linkedResourceUrn` here (it's a 1:many relationship and the UI only merges 1:1 pairs)
-   Bridge a `NotFound` or `NoMatch` origin to its `PulumiOnly` counterpart after a corrected mapping (`statusOverride=Migrated` + `linkedResourceUrn` → the PulumiOnly URN). This is the only valid use of `linkedResourceUrn`.
-   Leave notes explaining blockers or manual steps taken
-   Track decisions for resources the automatic classifier can't resolve

The annotation endpoint is the shared place to track migration progress — always read existing annotations before acting on a resource, and respect overrides left by the user.

The `note` field is user-authored context. Treat it as a **high-priority instruction** about that specific resource. Common uses: naming preferences, import ID hints, resources to skip, or special handling instructions. Notes reach the agent through two channels:

1. **Starting prompt** — when the user kicks off a migration task, any note on a selected resource is appended to that resource's line:
   ```
   - aws:s3/bucket:Bucket "my-bucket" (provider ID: my-bucket-prod) — note: use logical name "appBucket" in code
   ```
   Read these before calling the API.

2. **API response** — the `annotation.note` field on each `DiscoveredResourceInfo` when you call `GET .../resources`. The `annotation` object is omitted entirely when no annotation has been set.

---

## MIGRATION WORKFLOW

### Phase 0 — Preconditions and scoping

Before any tool call, gather and confirm **all** of the following. If anything is missing, **ask** — don't proceed with a guess.

**Source (the discovered stack):**

-   Org name (e.g. `pulumi_local`)
-   Discovered project name (e.g. `AcmeCdkExampleStack`)
-   Discovered stack name (e.g. `dev-sandbox-disc_us-west-2__Dev`) — this is the scanner-generated name, usually encoding account + region + CF/ARM stack name.
-   Region (confirm even if the stack name suggests it).

**Target (where the Pulumi code and state will live):**

-   **Target git repo URL** — ask the user. All work happens inside this repo from the start.
-   **Subfolder** (optional) — ask if the user has a preference; default to repo root.
-   **Target project + stack names** — ask the user, don't invent. If the stack already exists, use `compareTo` in Phase 1; if not, create it in Phase 2.
-   **Target language** — TypeScript default.

**Refactor preferences** (for Phase 7):

-   Does the user have the **original source code** (CDK repo, Bicep project, Terraform modules)? If yes, path or URL. **This is the primary structural reference for Phase 7** — the refactored Pulumi code will draw on its component boundaries, file layout, and naming conventions as a guide, adapted to what the import model actually produced.
-   Does the user have a **preferred program layout** for the Pulumi output? (e.g. "one file per service", "match my existing repo shape", "I don't care")
-   Does the user want Phase 7 at all, or stop after zero-diff (Phase 6)?

**Credentials:**

-   ESC environment for cloud credentials (ask if not given; never invent). ESC is preferred — see [`cloudformation.md §1`](cloudformation.md) or [`arm.md §1`](arm.md).

**Don't start Phase 1 until all of the above are confirmed.** Summarize the plan back to the user and wait for approval.

### Phase 1 — Resource fetch and triage

Start here every time, even when resuming an existing migration. The API + any existing annotations are the source of truth for what's been done so far. If the target repo already has Pulumi code, read it — it tells you the conventions, existing resources, and how far a previous attempt got.

1. Fetch discovered resources: `GET .../discovered-stacks/{projectName}/{stackName}/resources`.
    - **Target stack exists** (resumed migration): append `?compareTo=<targetProject>/<targetStack>`.
    - **Target stack does not exist** (greenfield): **omit `compareTo`** — the API returns 404 if the target stack isn't found. After Phase 2 creates the stack, subsequent calls can include it.
2. **Save the response to disk** — `./.migration/resources-baseline.json`.
3. **Run triage**: `python3 <skill-base-dir>/scripts/triage.py .migration/resources-baseline.json` — prints status counts (accounting for annotation overrides) and a per-resource table.
4. Present the plan to the user:
    > "Found N resources. A already Migrated, M Ready, K NotFound, J NoMatch, L non-migratable containers. I'll import Ready first, then verify NotFound, then triage NoMatch with you. Sound good?"

Get confirmation before writing any code.

### Phase 2 — Target repo and Pulumi stack setup

1. **Clone the target git repo** (from Phase 0) and work inside it for all subsequent phases. If the repo already has code, read it to understand existing conventions and resources before adding new ones.
2. If the target stack already exists (Phase 0 check), select it. Otherwise:
    - Create the Pulumi project: `pulumi new <language> --name <project> --stack <org>/<project>/<stack> --yes`.
3. Set provider config: `pulumi config set aws:region <r>` (or `azure-native:location`).
4. Link the ESC environment if provided.

**No empty `pulumi up` needed.**

> Concrete commands for project + stack setup, region config, and provider install: [`cloudformation.md §2`](cloudformation.md) or [`arm.md §2`](arm.md).

### Phase 3 — Build the import file

Generate the import file: `python3 <skill-base-dir>/scripts/build_import.py .migration/resources-baseline.json .migration/import.json`. This filters Ready/NotFound resources (excluding already-annotated ones) and maps API fields to the Pulumi import format (`type` ← providerType, `name` ← name, `id` ← resource.inputs.providerId).

### Phase 4 — Import

Using the `import.json` from Phase 3.

**Always use `--generate-code --out`** — without it, resources land in state with no code, breaking `pulumi preview`.

```
pulumi import --file import.json --generate-code --out batch.<ext>
# then: append generated code into the main program file and delete the batch file
```

**Per-batch loop: import → preview → commit → annotate.** Aim for ~20 resources per batch. For CDK stacks, batch by `cdkPath` top-level group; otherwise batch by resource type prefix.

1. **Import** the batch.
2. **`pulumi preview`** — zero diff required. Fix any diffs before moving on.
3. **Commit** the program changes to a branch.
4. **Annotate** each imported resource — `PUT .../migration` with note and **no `statusOverride`**. Annotations survive context resets and are visible in the UI.

`?compareTo` is a **live progress signal** — `pulumi import` writes state immediately, so `migrationStatus` flips to `Migrated` after each import. **Do not run `pulumi up`** (see Phase 6).

**Reserve `statusOverride`** for cases where the computed status will be wrong:

-   `statusOverride=Migrated` (with `linkedResourceUrn`) — resource covered by another (inline IAM policy → parent Role, IGW attachment → IGW, etc.).
-   `statusOverride=Migrated` (with a note, no `linkedResourceUrn`) — resource is deleted, dangling, or has no Pulumi equivalent. Flag it resolved so it drops out of the outstanding work.

### Phase 5 — NotFound and NoMatch triage

**Default strategy: try first, annotate second.** For both NotFound and corrected-mapping cases, attempting `pulumi import` is the fastest way to learn what's actually wrong. The error messages are precise and actionable.

**NotFound** (`providerType` set, state unconfirmed):

Common outcomes:

1. **Resource is deleted.** `pulumi import` returns `Preview failed: resource '<id>' does not exist`. Annotate `statusOverride=Migrated` with the literal error in the note. **Don't retry.** In practice, a substantial share of NotFound resources turn out to be deleted rather than a mapping error.

2. **Wrong `providerType` mapping.** Import fails with a type-validation error or schema mismatch. Several CF types have multiple valid Pulumi mappings (VPC gateway attachment / VPN vs IGW; S3 vs s3control; RDS instance vs cluster instance; SES v2 vs v1; etc.) — our scanner picks a primary that doesn't always match your resource. **Look up the `originType` in [`cloudformation.md §7`](cloudformation.md)**, override `providerType` in the import file, retry. Then handle the fingerprint side-effect (next bullet).

3. **Wrong-mapping side-effect: PulumiOnly appears.** When the agent imports with a corrected `providerType`, fingerprint matching against the discovered resource fails. The discovered resource stays `NotFound` (or `NoMatch`) and a new `PulumiOnly` entry appears. **Annotate the original origin row as `statusOverride=Migrated` with `linkedResourceUrn` pointing to the PulumiOnly URN.** This bridges them in the UI and keeps the bookkeeping clean.

4. **Resource is alive and mapping is correct.** Import succeeds. Status flips to `Migrated` automatically.

**NoMatch** (`providerType` is `null`):

Common patterns:

1. **Inline IAM policies.** `AWS::IAM::Policy` whose name matches a migrated Role's prefix is an inline policy already captured as `inlinePolicies` on the Role's import. Annotate `statusOverride=Migrated` with note: `"inline policy of <RoleName>"`.

2. **AWS::SecretsManager::SecretTargetAttachment** has no direct Pulumi mapping. The link between secret and target (RDS cluster, etc.) is implicit via the cluster's credentials config. Annotate `statusOverride=Migrated` with a note explaining the implicit link.

3. **CDK Custom Resources** (`Custom::*`). Typically a Lambda handler doing the actual work. Check [`cloudformation.md §5`](cloudformation.md) for known handler → Pulumi replacement mappings. **Don't annotate `Migrated` without confirming with the user** — surface what the handler does and let them decide.

4. **Other NoMatch types.** Look up the `originType` in the cloud provider docs (CF resource type reference or ARM resource type reference) to understand what the resource is, then search the Pulumi registry for a matching provider type. If the mapping is ambiguous, surface to the user and ask.

**Pre-existing PulumiOnly entries.** Beyond the corrected-mapping artifacts above, `PulumiOnly` also covers resources already in the target stack that aren't part of this migration. Leave those as-is — no annotation needed.

> For cloud-specific lookup commands (verifying resources exist, finding import IDs, querying the cloud), provider-choice rules (`aws` classic vs `aws-native`, `azure-native` vs `azure`), the Preview Resolution Workflow, and known import quirks, see [`cloudformation.md §3–§6`](cloudformation.md) or [`arm.md §3–§6`](arm.md).

### Phase 6 — Reconciliation & PR

1. Run `pulumi preview` — **confirm there are NO changes**. Any diff means the generated code doesn't match the imported state. Diffs come in three shapes:
    - **Removed (`-`)** — a field the cloud has but your code doesn't set. **Add it to the code** with the real cloud value. Don't `ignoreChanges`.
    - **Added (`+`)** — a field your code sets that the provider didn't return. If computed/read-only → `ignoreChanges`. If a provider default re-statement → remove from code.
    - **Changed (`~`)** — value mismatch. Query the cloud, determine the correct value, update code. Never silence with `ignoreChanges`.

    Expect 2–5 preview rounds for complex resources. **Never run `pulumi up` to resolve diffs — that modifies the cloud, not the code.** See [`cloudformation.md §6`](cloudformation.md) or [`arm.md §6`](arm.md) for cloud-specific diff patterns.
2. Do one final `GET resources?compareTo=...` and verify the expected distribution (this reflects the current backend state — `migrationStatus` is already up-to-date since every `pulumi import` writes state):
    - `Migrated` — all imported resources
    - `PulumiOnly` — Pulumi-only resources, including any corrected-mapping imports linked via annotation
    - `NoMatch` remaining — every one should have an annotation
    - `NotApplicable` (containers) — silently skipped
3. Proceed to Phase 7 (refactor offer) **before** opening the PR.

The migration is functionally complete when preview is clean and the API triage shows no unresolved resources. **Do not run `pulumi up`.** The imported state is already synced to Pulumi Cloud via `pulumi import`; there's nothing for `pulumi up` to do that serves the migration.

---

### Phase 7 — Refactor and maintainability review (before the PR)

Zero-diff is achieved, but the imported code is "flat" — hardcoded values, no cross-resource references, all resources at the top level. **Before opening the PR**, offer the user a readability refactor.

**7a — Offer and orient**

If Phase 0 didn't capture explicit refactor preferences, or the user hasn't explicitly declined, **ask now**:

> "Preview is clean and all resources are accounted for. Before I open the PR, I'd like to refactor the code for maintainability — replacing any hardcoding with cross-resource references, extracting config parameters, and grouping related resources. (If you gave me a source repo, I'll use it as the structural blueprint, matching the intended file layout and component names.) Want me to go ahead?"

If they decline, skip to Phase 8.

**7b — Implement the refactor**

Read [`refactor.md`](refactor.md) for strategies, invariants, and template-reading references. Key priorities in order:

1. **Take structural cues from the source repo first** — if the user provided a source repo, read it now (clone or use the local path from Phase 0). Use its file layout, component/module boundaries, and naming conventions as a guide. Where a group of resources maps naturally to a class, module, or subdirectory in the source and that grouping still feels natural for the imported Pulumi program, mirror that structure; otherwise avoid forcing artificial groupings just to match the source mechanically.
2. **Replace literal ARN/ID references** with cross-resource output references.
3. **Extract config parameters** (region, account ID, environment tag).
4. **Consolidate into `ComponentResource` classes** where the source repo or CDK paths suggest a natural grouping.
5. **Split into files** only last — and only when a natural isle warrants it.

Run `pulumi preview` after every non-trivial change. Zero-diff must hold throughout. If preview shows a diff, revert that single change before trying anything else — see [`refactor.md` § The invariant](refactor.md) for recovery steps.

**7c — User walkthrough and maintainability sign-off**

After the refactor, **present the result to the user before opening the PR**:

1. Show a summary of what changed: files created/renamed, components introduced, literals replaced, config keys added.
2. Walk through the top-level `index.ts` (or equivalent) line by line if it's under ~80 lines; otherwise describe the module breakdown.
3. Highlight any judgment calls (e.g. "I grouped the IAM resources into `iam.ts` to match the `lib/iam/` directory in your source repo — let me know if you'd prefer a different name").
4. Ask explicitly: **"Does this structure match how you'd expect to maintain this code?"** Wait for the user's answer. If they request changes, make them (always preview after) and repeat the walkthrough until they're satisfied.

Only proceed to Phase 8 once the user confirms the structure is acceptable.

---

### Phase 8 — PR and migration report

Produce the migration report (see below) and open the PR. The PR includes whatever state the code is in — raw imported code (if the user skipped Phase 7) or the refactored version (if they opted in).

---

## MIGRATION REPORT FORMAT

Include in the PR description:

1. **Overview** — source discovered stack → target Pulumi stack, region, language.
2. **Triage summary** — counts by status at start and end.
3. **Resource mapping table** — name, origin type, provider type, status, notes.
4. **Gaps** — unmapped resources and why, with annotations.
5. **Progress URL** — link to the discovered-stacks comparison endpoint for ongoing tracking.
6. **Next steps** — pending user decisions, optional refactoring.

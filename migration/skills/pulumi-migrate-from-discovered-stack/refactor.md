# Post-Migration Refactor

## The invariant

**Zero-diff holds throughout the refactor, full stop.** After every edit, run `pulumi preview` and expect no changes.

- **Make one small change at a time.** One resource's ARN replaced with a reference. One hardcoded region extracted into config. One group of resources moved into a file.
- **Preview after every change.** If preview stays clean, commit and move on. If preview shows a diff, revert that single change before trying something else.
- **Never run `pulumi up` to absorb a refactor diff.**

---

## Available signals

Read these in priority order. The first signal that gives you enough information for a structural proposal to the user is where to pause and confirm. Remaining signals may be revisited during the actual refactor.

**1. Original source code** — if the user provided a path/URL. **This is the primary structural reference.** Read it first, before looking at anything else:
- Top-level file layout → informs how to split the Pulumi program into files.
- Class/module/subdirectory names → suggest natural `ComponentResource` boundaries and file names.
- Loops, reusable modules, naming conventions → guide how to group and parameterize in Pulumi.
- Parameters/variables → suggest `pulumi.Config` key names.

When a source repo is present, use it as the starting point for refactoring decisions, then adapt based on what the import model actually produced. The goal is recognizable and maintainable project structure.

**2. The discovered-stacks API response** (on disk at `.migration/resources-baseline.json`):
- `resource.parent` and `resource.dependencies[]` — explicit URN-level relationships. If `A`'s dependencies include `B`, `A` likely references `B`'s ARN/ID/name somewhere in its inputs.
- `inputs.providerId` and `inputs._fingerprint` — the exact literal values hardcoded in the generated code. Build a map `{providerId|_fingerprint → resource.name}` once, then grep the code for those literals to find replacement sites.
- For CDK-synthesized stacks, `inputs.cdkPath` gives natural component boundaries — see [`cloudformation.md §5`](cloudformation.md).

**3. Original CF/ARM template** (always fetchable):
- **CloudFormation:** `aws cloudformation get-template --region <r> --stack-name <cfn-stack> --query 'TemplateBody' --output json > .migration/template.json`
- **ARM:** `az group export --name <rg> --output json > .migration/template.json`
- Signals: parameters (→ `pulumi.Config`), conditionals (→ TS conditionals), cross-resource `!Ref`/`!GetAtt` (confirms interpolation targets).

**4. Target repo layout** — if the user described a preferred layout.

Confirm the chosen approach with the user before editing.

---

## Strategies

Don't apply these rigidly. The real work is **finding natural isles** — groups of resources that clearly belong together — and refactoring within those. If the code is already reasonably clean, stop early.

**A. Take structural inspiration from the source repo (when one is available).**

Before touching anything, read the source repo and note its shape — don't copy it mechanically, but use it to answer: what groupings would be familiar to this team?

1. Note the top-level file/directory structure. Use it as a rough guide for how to split the Pulumi program, not a template to reproduce exactly.
2. For each major class or module the user would recognize (e.g. `NetworkStack`, `DatabaseCluster`, `IamRoles`), consider whether a `pulumi.ComponentResource` with a similar name and scope makes sense given the actual imported resources. If the grouping is natural, use it; if it's artificial, skip it.
3. Borrow config parameter names from the source where the concepts match. Don't invent new names just to differ.

Propose the structure to the user before writing any code: "Based on your source repo, I'm thinking of grouping resources into `network.ts`, `database.ts`, and `iam.ts` — does that match how your team thinks about this stack?"

**B. Identify relationships and interpolation candidates.**

```
jq '[.resources[] | {
  name,
  providerId: .resource.inputs.providerId,
  fingerprint: .resource.inputs._fingerprint,
  parent: (.resource.parent // null),
  deps: (.resource.dependencies // [])
}]' .migration/resources-baseline.json > .migration/relationships.json
```

Build a map from literal ARNs/physical IDs to resource names. For every resource `A` that has `B` in its `dependencies`, look in `A`'s generated code for `B`'s `providerId` or `_fingerprint` literal — that's an interpolation site. Replace the string literal with `B.arn` / `B.id` / `pulumi.interpolate\`...${B.name}...\`` as appropriate. Preview after each replacement.

**C. Extract obvious parameters.**

Region, account ID, environment tag. One at a time, into `pulumi.Config`. Verify the config values reproduce the same literal strings that were in the code.

**D. Replace structural hardcoded values using the CF/ARM template.**

When the imported code has a computed value (e.g. `!Sub "${AWS::StackName}-bucket"` resolved to a literal), the template tells you what the original construction was. Replace the literal with the equivalent Pulumi expression. See [`cloudformation.md §8`](cloudformation.md) or [`arm.md §7`](arm.md) for intrinsic-function mappings.

**E. Consolidate into ComponentResources — only where natural.**

If the resources have a clear grouping (for CDK stacks this is `cdkPath` — see [`cloudformation.md §5`](cloudformation.md); for ARM it's nested templates) and that grouping makes sense in the user's context, wrap it as a `pulumi.ComponentResource`. Don't force it — many groupings in imported code are noise, not natural isles.

**F. Split into files — after components, not before.**

File splits are a *last* consideration. They're the lowest-value change on their own: the file a resource lives in has no semantic impact. Split only when the program exceeds ~1000 lines, there are clear natural isles, or the user has asked for a specific layout. When a source repo is available, let it inform this decision.

**G. Parameterize for multi-env.**

Once the single stack is clean, a sibling `prod` stack can be created from the same program. Out of scope for the migration — just note it as a follow-up.

---

## Post-refactor maintainability review

After each meaningful refactor pass, **present the result to the user** before moving on. Don't just run preview and assume it's good — get explicit sign-off.

**What to present:**

1. A brief summary: "I made N changes — replaced M hardcoded ARNs with references, extracted K config keys, and grouped resources into X components."
2. The module/file breakdown: "Your program now has `network.ts`, `database.ts`, and `iam.ts`. `index.ts` imports and wires them together."
3. Any judgment calls you made: "I named the component `NetworkStack` to match your source repo's `NetworkStack` CDK class — let me know if you'd prefer something else."

**Ask the user explicitly:** "Does this structure match how you'd expect to maintain this code?"

If they say no, ask a follow-up: "What would you change?" Then make the adjustments and repeat the walkthrough. Keep iterating until they confirm it's right.

**Never open the PR without this sign-off.** A zero-diff program the user doesn't recognize is not a successful migration.

---

## Template / source-code reading references

- **CF intrinsic functions → Pulumi** (`!Ref`, `!Sub`, `!GetAtt`, `!If`, `!Select`, etc.): [`cloudformation.md §8`](cloudformation.md).
- **CF Parameters / Mappings / Conditions → Pulumi**: [`cloudformation.md §8`](cloudformation.md).
- **ARM expressions → Pulumi** (`parameters()`, `variables()`, `resourceId()`, `reference()`, `concat()`, `uniqueString()`, etc.): [`arm.md §7`](arm.md).
- **ARM `copy` loops / `condition` / `dependsOn`**: [`arm.md §7`](arm.md).
- **Nested templates → `ComponentResource`**: [`arm.md §7`](arm.md).
- **CDK construct → Pulumi equivalents for custom resources**: [`cloudformation.md §5`](cloudformation.md).

---

## When to stop

- The user has reviewed the code and confirmed it's maintainable.
- The invested effort exceeds the remaining value (e.g. extracting a Component for a one-off resource is noise).
- A refactor would require state surgery (`pulumi state rename`) — **stop and ask the user**, don't silently do it.

Don't chase a 1:1 reproduction of the original template. The goal is a maintainable Pulumi program the user's team can work in confidently — not a line-by-line translation.

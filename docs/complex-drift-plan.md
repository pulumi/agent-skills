# Plan: Complex drift test fixtures for skill vs baseline differentiation

## Context

The full-drift-200 test showed **no difference** between skill and baseline because the resources are trivially simple: 3 types, identical properties per type, sequential naming. The baseline agent solved it in 13 turns by running `pulumi stack export | python3` and writing 3 loops — same as the skill agent.

**Broader goal**: The full-drift test was a first attempt at validating whether the drift-adopter tool is useful for import/migration scenarios (state exists, code is empty, agent must write all code). The current fixtures are too simple to be realistic — real-world imports have varied properties, cross-resource references, nested objects, and many resource types.

**Dual purpose**: These complex fixtures will:
1. Test skill vs baseline differentiation with realistic complexity
2. **Drive drift-adopter tool development** — the tool was optimized early for simple `inputProperties` (flat key-value). These fixtures will expose gaps in how the tool handles cross-resource references, nested structures, and varied property shapes. The tool may need enhancements to intelligently handle these patterns (e.g., detecting that a resolved PEM string matches another resource's output, suggesting reference reconstruction).
3. Still use local-only providers (random, command, tls) — no cloud credentials

## Why the current full-drift fixtures don't differentiate

- **Uniform resources**: Every RandomString has `{length: 16, special: false}` — trivially loopable
- **No cross-resource references**: Each resource is independent
- **No nested/array properties**: No subjects, dnsNames, allowedUses, keepers
- **Sequential naming**: `cmd-0`, `cmd-1` — obvious loop pattern

## Design: Complex drift fixtures

### New generator: `tests/generate_complex_drift.py`

Produces `complex-drift-{20,40,60,100}` fixtures with the same empty-original/full-drifted pattern as full-drift, but with much higher per-resource complexity.

### Scales

| Scale | Cert Chains | Random Resources | Command Resources | Total |
|-------|-------------|-----------------|-------------------|-------|
| 20    | 1 (5)       | 10              | 5                 | 20    |
| 40    | 3 (15)      | 16              | 9                 | 40    |
| 60    | 4 (20)      | 25              | 15                | 60    |
| 100   | 6 (30)      | 45              | 25                | 100   |

Smaller scales than full-drift because complexity-per-resource is much higher. 100 complex resources ≈ 400-800 trivial ones in agent reasoning burden.

### Complexity vectors (what makes this hard)

#### 1. Varied properties per instance
Not all RandomStrings are identical. Each instance gets different property combinations:
- Different `length` values (8, 16, 24, 32, 64)
- Some have `minLower`, `minUpper`, `minSpecial`, `overrideSpecial`
- Some have `keepers` maps
- Defeats the "write 3 loops" strategy

#### 2. More resource types (7+ instead of 3)
- `random.RandomString`, `RandomPassword`, `RandomInteger`, `RandomId`, `RandomPet`, `RandomShuffle`, `RandomUuid`
- `tls.PrivateKey`, `SelfSignedCert`, `CertRequest`, `LocallySignedCert`
- `command.local.Command` with varied environments

#### 3. Cross-resource references (multiple patterns)

**TLS cert chains** (5 resources, 4 refs each):
```typescript
const caKey = new tls.PrivateKey("web-ca-key", { algorithm: "RSA", rsaBits: 4096 });
const caCert = new tls.SelfSignedCert("web-ca-cert", {
    privateKeyPem: caKey.privateKeyPem,  // REFERENCE
    subjects: [{ organization: "Acme Corp", commonName: "Acme CA" }],
    ...
});
```

**Command triggers** referencing random outputs:
```typescript
const dbPassword = new random.RandomPassword("db-password", { length: 24 });
const dbInit = new command.local.Command("db-init", {
    create: "echo initializing",
    triggers: [dbPassword.result],  // REFERENCE — re-run if password changes
});
```

**Random keepers** referencing other random outputs:
```typescript
const rotationSeed = new random.RandomInteger("rotation-seed", { min: 1, max: 1000 });
const apiToken = new random.RandomString("api-token", {
    length: 32,
    keepers: { seed: rotationSeed.result },  // REFERENCE — regenerate when seed changes
});
```

These reference patterns are critical because:
- The drift-adopter currently outputs flat `inputProperties` with **resolved values** (actual PEM strings, actual random results)
- The tool **already receives `propertyDependencies`** from preview data (it's in `apitype.ResourceV3`) but **ignores it**
- **These fixtures will drive a tool enhancement**: pass through `propertyDependencies` alongside `inputProperties`

### How Pulumi tracks cross-resource references

Every resource in state and preview has a `propertyDependencies` field:
```json
// SelfSignedCert referencing a PrivateKey
"propertyDependencies": {
  "privateKeyPem": ["urn:pulumi:stack::project::tls:index/privateKey:PrivateKey::web-ca-key"],
  "allowedUses": [],
  "subjects": []
}
```

This maps each input property → URNs of resources it depends on. Combined with `inputProperties`, the agent can reconstruct `caKey.privateKeyPem` instead of hardcoding the PEM string.

### Drift-adopter tool enhancement needed

**Goal**: Resolve cross-resource references directly in the JSON output so the agent doesn't have to match resolved values to URNs.

The data is already available: `step.OldState.PropertyDependencies` is `map[PropertyKey][]URN` — maps each input property to the URNs it depends on. The tool just needs to surface it.

**Output format change** — properties with dependencies get `dependsOn` metadata inline:
```json
{
  "action": "add_to_code",
  "name": "web-ca-cert",
  "type": "tls:index/selfSignedCert:SelfSignedCert",
  "inputProperties": {
    "privateKeyPem": {
      "value": "-----BEGIN RSA PRIVATE KEY-----\n...",
      "dependsOn": {
        "resourceName": "web-ca-key",
        "resourceType": "tls:index/privateKey:PrivateKey",
        "outputProperty": "privateKeyPem"
      }
    },
    "validityPeriodHours": 87600,
    "allowedUses": ["cert_signing", "crl_signing"],
    "subjects": [{"commonName": "Acme CA", "organization": "Acme Corp"}]
  }
}
```

Properties without dependencies remain plain values. This is backward-compatible.

**Key finding: preview doesn't include unchanged resources.** `pulumi preview --json` only includes resources with operations (create, delete, update, replace). Resources with `op: "same"` (unchanged custom resources) are NOT in the output — only the Stack pseudo-resource appears as "same". This means in mixed drift scenarios, if resource B depends on unchanged resource A, the tool can't find A's outputs from preview alone.

**Solution: supplement with `pulumi stack export`.** The tool already shells out to `pulumi preview`. It should also run `pulumi stack export` to get a complete URN→outputs lookup for ALL resources (changed and unchanged). This is needed for any scenario where cross-resource references involve unchanged resources.

**Implementation in `next.go`**:
1. After running preview, also run `pulumi stack export` to get full state
2. Build `urnToResource` lookup from state export (URN → ResourceV3 with Inputs+Outputs)
3. In `extractInputProperties()`, for each property:
   - Check `step.OldState.PropertyDependencies[propName]`
   - If non-empty, look up the dependent resource via `urnToResource` (from state export)
   - Find which output property of the dependent resource matches the resolved input value (exact value match)
   - Emit `{"value": resolvedVal, "dependsOn": {resourceName, resourceType, outputProperty}}`
   - If empty deps or no match found, emit the plain value (as today)
4. Add `--state-file` flag (independent of `--events-file` — either, both, or neither). If not provided, run `pulumi stack export` live

**Finding the output property**: Compare the resolved input value against each output of the dependent resource. For PEM strings, UUIDs, random results, etc., exact match works. For unmatched values, fall back to emitting just the URN dependency without `outputProperty`.

**This is the key differentiator**: The skill agent gets actionable reference info directly. The baseline agent must parse raw state, find matching values across resources, and deduce the references itself — much harder and error-prone at scale.

#### 4. Nested objects and arrays
`SelfSignedCert.subjects`: `[{ organization, commonName, country, province, locality }]`
`SelfSignedCert.allowedUses`: `["cert_signing", "digital_signature", "server_auth"]`
`SelfSignedCert.dnsNames`: `["web.acme.com", "*.web.acme.com"]`

#### 5. Realistic naming
Services: `web`, `api`, `db`, `auth`, `cache`, `worker`, `gateway`, `monitor`
Names: `web-ca-key`, `api-password`, `db-port`, `auth-secret` — not `cmd-0`

#### 6. Map properties
`command.environment`: `{ APP_NAME: "web", PORT: "8080" }` — varies per instance
`random.keepers`: `{ rotate: "42" }` — some have it, some don't

### Generator architecture

```python
@dataclass
class ResourceDef:
    var_name: str           # TS variable name (camelCase)
    resource_name: str      # Pulumi logical name (kebab-case)
    resource_type: str      # e.g. "random.RandomString"
    properties: dict        # Input properties (literal values)
    references: dict[str, str]  # prop -> "varName.outputProp" (for cross-refs)

@dataclass
class CertChain:
    service: str
    resources: list[ResourceDef]  # 5 resources in dependency order
```

Archetype variation functions use seeded RNG for deterministic but varied properties:
```python
def random_string_variation(rng, name, var) -> ResourceDef:
    # Different length, optional minLower/minUpper/minSpecial/overrideSpecial/keepers
```

### Fixture output (same pattern as full-drift)

```
tests/drift-adoption/complex-drift-{N}/
├── index.ts           # Empty program (imports only)
├── drifted/index.ts   # All N resources with full complexity + cross-refs
├── Pulumi.yaml
├── package.json       # deps: @pulumi/pulumi, @pulumi/random, @pulumi/command, @pulumi/tls
└── tsconfig.json
```

## Files to create/modify

### This repo (agent-skills)

| File | Action | Description |
|------|--------|-------------|
| `tests/generate_complex_drift.py` | Create | Generator script for complex fixtures |
| `tests/drift-adoption/complex-drift-{20,40,60,100}/` | Generate | Fixture directories (generated by script) |
| `tests/test_complex_drift.py` | Create | Skill test (parametrized, follows `test_full_drift.py` pattern) |
| `tests/test_complex_drift_baseline.py` | Create | Baseline test (follows `test_full_drift_baseline.py` pattern) |

No changes needed to: `conftest.py`, `drift_adoption_helpers.py`, `claude_code_agent.py`, `utils.py`

### Drift-adopter tool (`pulumi-tool-drift-adopter` — separate repo)

| File | Change |
|------|--------|
| `cmd/pulumi-drift-adopt/next.go` | Enhance `extractInputProperties()` to resolve dependencies inline; build URN→name lookup from all steps |
| `authoring/skills/pulumi-adopt-drift/SKILL.md` | Update skill to document `dependsOn` in property values |

## Implementation sequence

### Phase 1: Fixtures & tests (this repo)

1. **`tests/generate_complex_drift.py`**
   - `ResourceDef` dataclass with TypeScript rendering
   - Archetype variation functions for each resource type
   - `generate_cert_chain(service, rng)` → 5 linked ResourceDefs
   - `generate_random_resources(service, rng, count)` → varied random resources
   - `generate_command_resources(service, rng, count, random_refs)` → commands with varied envs, some with `triggers` referencing random resource outputs
   - Reference wiring: some random resources get `keepers` referencing other random outputs
   - `render_index_ts(resources)` → TypeScript with proper ordering (deps before dependents)
   - `main()` generating all 4 scales

2. **Run generator**, manually verify scale-20 `drifted/index.ts` looks right

3. **Deploy scale-20 to verify it works**: `cd tests/drift-adoption/complex-drift-20 && pulumi up`

4. **`tests/test_complex_drift.py`** — copy pattern from `test_full_drift.py`, parametrize over `complex-drift-{20,40,60,100}`

5. **`tests/test_complex_drift_baseline.py`** — copy pattern from `test_full_drift_baseline.py`

### Phase 2: Drift-adopter tool enhancement (separate repo, separate PR)

6. **Add state export** — add `--state-file` flag (independent of `--events-file`). If provided, read state from file; otherwise run `pulumi stack export` live. Either flag can be used alone or together. Parse into `[]apitype.ResourceV3`

7. **Build URN→resource lookup** — from state export, build `map[string]*apitype.ResourceV3` for all resources (changed AND unchanged)

8. **Enhance `extractInputProperties()`** — for each property, check `step.OldState.PropertyDependencies[propName]`. If non-empty, look up dependent resource from the state lookup, match resolved value against outputs to find `outputProperty`

9. **Add output property matching** — iterate dependent resource's `Outputs` map, compare each value against the resolved input value (exact match). Handle edge cases: secrets, nil values, no match found

10. **Update SKILL.md** — document the `dependsOn` format, instruct agent to use resource references (e.g., `caKey.privateKeyPem`) instead of hardcoded values

11. **Re-run complex-drift tests** to validate the full pipeline with reference reconstruction

## Key constraints to validate

- Cross-references must use correct output property names: `privateKeyPem`, `certPem`, `certRequestPem`
- `SelfSignedCert` requires `privateKeyPem`, ≥1 `allowedUses`
- `LocallySignedCert` requires `certRequestPem`, `caPrivateKeyPem`, `caCertPem`, `validityPeriodHours`, `allowedUses`
- `RandomShuffle.resultCount` ≤ `len(inputs)`
- Resources referenced must appear before referencing resources in TypeScript
- All variable names must be unique

## Verification

1. Run generator: `python tests/generate_complex_drift.py`
2. Inspect output: read `tests/drift-adoption/complex-drift-20/drifted/index.ts` for correctness
3. Deploy test: `cd tests/drift-adoption/complex-drift-20 && npm install && pulumi stack init test-verify && pulumi up --yes` (from drifted dir)
4. Run skill test at scale-20: `just test-one test_complex_drift[scale-20]`
5. Run baseline test at scale-20: `just test-one test_complex_drift_baseline[scale-20]`
6. Compare logs and metrics for differentiation

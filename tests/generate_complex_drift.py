#!/usr/bin/env python3
"""Generate complex drift adoption test fixtures with varied drift percentages.

Produces example directories for a matrix of (scale, drift_pct) using
local-only providers (random, command, tls) — no cloud credentials required.

Each directory contains:
  - index.ts:          Original program (all N resources, or empty for 100% drift)
  - Pulumi.yaml:       Project configuration
  - package.json:      Node.js dependencies
  - tsconfig.json:     TypeScript configuration

Drifted code (drifted/index.ts) is generated at test time via generate_drifted_code()
with a random seed, so drift varies between runs. Use --with-drifted for local debugging.

Complexity vectors (what makes these fixtures hard):
  - Varied properties per instance (different lengths, optional fields)
  - 12 resource types across 3 providers (not just 3 uniform types)
  - Cross-resource references (cert chains, command triggers, random keepers)
  - Nested objects and arrays (subjects, allowedUses, dnsNames)
  - Realistic naming (web-ca-key, api-password, not cmd-0)

Drift levels:
  - 100% ("full"): Empty original, all resources in drifted — pure adoption
  - 50%: Half the resources are drifted (property changes, deletions, creations)
  - 15%: Light drift across multiple drift types

Usage:
    uv run python tests/generate_complex_drift.py
"""

import json
import random as stdlib_random
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

def generate_tsconfig() -> str:
    data = {
        "compilerOptions": {
            "strict": True,
            "outDir": "bin",
            "target": "es2016",
            "module": "commonjs",
            "moduleResolution": "node",
            "sourceMap": True,
            "experimentalDecorators": True,
            "pretty": True,
            "noFallthroughCasesInSwitch": True,
            "noImplicitReturns": True,
            "forceConsistentCasingInFileNames": True,
        },
        "files": ["index.ts"],
    }
    return json.dumps(data, indent=2) + "\n"

SCALES = [20, 40, 60, 100]
DRIFT_PCTS = [15, 50, 100]

# Service names for realistic naming
SERVICES = ["web", "api", "db", "auth", "cache", "worker", "gateway", "monitor"]
EXTRA_SERVICES = ["billing", "search", "metrics", "logging", "queue", "scheduler"]


@dataclass
class ResourceDef:
    """A single resource definition for TypeScript rendering."""

    var_name: str  # TS variable name (camelCase)
    resource_name: str  # Pulumi logical name (kebab-case)
    resource_type: str  # e.g. "random.RandomString"
    properties: dict  # Input properties (literal values)
    references: dict[str, str] = field(default_factory=dict)  # prop -> "varName.outputProp"


@dataclass
class CertChain:
    """A TLS certificate chain (5 resources with cross-references)."""

    service: str
    resources: list[ResourceDef]


@dataclass
class DriftConfig:
    """Describes which resources are drifted and how."""

    property_change_indices: list[int] = field(default_factory=list)
    deletion_indices: list[int] = field(default_factory=list)
    extra_resources: list[ResourceDef] = field(default_factory=list)


# ---------------------------------------------------------------------------
# TypeScript rendering
# ---------------------------------------------------------------------------


def _ts_value(value: object, indent: int = 1) -> str:
    """Render a Python value as TypeScript literal."""
    prefix = "    " * indent
    inner_prefix = "    " * (indent + 1)

    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        if not value:
            return "[]"
        if all(isinstance(v, str) for v in value):
            items = ", ".join(f'"{v}"' for v in value)
            return f"[{items}]"
        items = []
        for v in value:
            items.append(f"{inner_prefix}{_ts_value(v, indent + 1)}")
        return "[\n" + ",\n".join(items) + f",\n{prefix}]"
    if isinstance(value, dict):
        if not value:
            return "{}"
        items = []
        for k, v in value.items():
            items.append(f"{inner_prefix}{k}: {_ts_value(v, indent + 1)}")
        return "{\n" + ",\n".join(items) + f",\n{prefix}}}"
    return str(value)


def render_resource(res: ResourceDef) -> str:
    """Render a ResourceDef as a TypeScript const declaration."""
    lines = [f'const {res.var_name} = new {res.resource_type}("{res.resource_name}", {{']

    for prop, value in res.properties.items():
        if prop in res.references:
            lines.append(f"    {prop}: {res.references[prop]},")
        else:
            lines.append(f"    {prop}: {_ts_value(value)},")

    for prop, ref in res.references.items():
        if prop not in res.properties:
            lines.append(f"    {prop}: {ref},")

    lines.append("});")
    return "\n".join(lines) + "\n"


def render_index_ts(resources: list[ResourceDef]) -> str:
    """Render all resources as a TypeScript program."""
    lines = [
        'import * as pulumi from "@pulumi/pulumi";',
        'import * as random from "@pulumi/random";',
        'import * as command from "@pulumi/command";',
        'import * as tls from "@pulumi/tls";',
        "",
    ]
    for res in resources:
        lines.append(render_resource(res))
    return "\n".join(lines) + "\n"


def generate_empty_index_ts() -> str:
    """Generate an empty TypeScript program — imports only, no resources."""
    lines = [
        'import * as pulumi from "@pulumi/pulumi";',
        'import * as random from "@pulumi/random";',
        'import * as command from "@pulumi/command";',
        'import * as tls from "@pulumi/tls";',
        "",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Resource generation (original versions)
# ---------------------------------------------------------------------------


def generate_cert_chain(service: str, rng: stdlib_random.Random) -> CertChain:
    """Generate a TLS cert chain: caKey -> caCert -> serverKey -> serverCsr -> serverCert."""
    validity_hours = rng.choice([8760, 17520, 26280, 43800, 87600])
    rsa_bits = rng.choice([2048, 4096])
    org = rng.choice(["Acme Corp", "Contoso Ltd", "Fabrikam Inc", "Northwind Traders"])
    country = rng.choice(["US", "GB", "DE", "JP"])

    ca_key = ResourceDef(
        var_name=f"{service}CaKey",
        resource_name=f"{service}-ca-key",
        resource_type="tls.PrivateKey",
        properties={"algorithm": "RSA", "rsaBits": rsa_bits},
    )

    ca_cert = ResourceDef(
        var_name=f"{service}CaCert",
        resource_name=f"{service}-ca-cert",
        resource_type="tls.SelfSignedCert",
        properties={
            "privateKeyPem": None,
            "subject": {"organization": org, "commonName": f"{service.title()} CA", "country": country},
            "validityPeriodHours": validity_hours,
            "allowedUses": ["cert_signing", "crl_signing"],
            "isCaCertificate": True,
        },
        references={"privateKeyPem": f"{service}CaKey.privateKeyPem"},
    )

    server_key = ResourceDef(
        var_name=f"{service}ServerKey",
        resource_name=f"{service}-server-key",
        resource_type="tls.PrivateKey",
        properties={"algorithm": "RSA", "rsaBits": 2048},
    )

    server_csr = ResourceDef(
        var_name=f"{service}ServerCsr",
        resource_name=f"{service}-server-csr",
        resource_type="tls.CertRequest",
        properties={
            "privateKeyPem": None,
            "subject": {"commonName": f"{service}.example.com", "organization": org},
            "dnsNames": [f"{service}.example.com", f"*.{service}.example.com"],
        },
        references={"privateKeyPem": f"{service}ServerKey.privateKeyPem"},
    )

    server_cert = ResourceDef(
        var_name=f"{service}ServerCert",
        resource_name=f"{service}-server-cert",
        resource_type="tls.LocallySignedCert",
        properties={
            "certRequestPem": None,
            "caPrivateKeyPem": None,
            "caCertPem": None,
            "validityPeriodHours": validity_hours,
            "allowedUses": ["digital_signature", "key_encipherment", "server_auth"],
        },
        references={
            "certRequestPem": f"{service}ServerCsr.certRequestPem",
            "caPrivateKeyPem": f"{service}CaKey.privateKeyPem",
            "caCertPem": f"{service}CaCert.certPem",
        },
    )

    return CertChain(service=service, resources=[ca_key, ca_cert, server_key, server_csr, server_cert])


def random_string_variation(rng: stdlib_random.Random, name: str, var_name: str) -> ResourceDef:
    """Generate a RandomString with varied properties."""
    length = rng.choice([8, 16, 24, 32, 64])
    props: dict = {"length": length, "special": rng.choice([True, False])}

    if rng.random() < 0.3:
        props["minLower"] = rng.randint(1, 4)
    if rng.random() < 0.3:
        props["minUpper"] = rng.randint(1, 4)
    if rng.random() < 0.3:
        props["minNumeric"] = rng.randint(1, 4)
    if props.get("special") and rng.random() < 0.4:
        props["overrideSpecial"] = rng.choice(["!@#$", "._-", "~^&*", "!@#$%^&*"])

    return ResourceDef(var_name=var_name, resource_name=name, resource_type="random.RandomString", properties=props)


def random_password_variation(rng: stdlib_random.Random, name: str, var_name: str) -> ResourceDef:
    """Generate a RandomPassword with varied properties."""
    length = rng.choice([16, 24, 32, 48])
    props: dict = {"length": length, "special": True}

    if rng.random() < 0.4:
        props["minLower"] = rng.randint(2, 6)
    if rng.random() < 0.4:
        props["minUpper"] = rng.randint(2, 6)
    if rng.random() < 0.4:
        props["overrideSpecial"] = rng.choice(["!@#$%", "._-+", "!@#$%^&*()"])

    return ResourceDef(var_name=var_name, resource_name=name, resource_type="random.RandomPassword", properties=props)


def random_integer_variation(rng: stdlib_random.Random, name: str, var_name: str) -> ResourceDef:
    """Generate a RandomInteger with varied min/max."""
    ranges = [(1, 100), (1, 1000), (1024, 65535), (1, 10000), (100, 999)]
    min_val, max_val = rng.choice(ranges)
    return ResourceDef(
        var_name=var_name, resource_name=name, resource_type="random.RandomInteger",
        properties={"min": min_val, "max": max_val},
    )


def random_id_variation(rng: stdlib_random.Random, name: str, var_name: str) -> ResourceDef:
    """Generate a RandomId with varied byte length and optional prefix."""
    byte_length = rng.choice([4, 8, 16])
    props: dict = {"byteLength": byte_length}
    if rng.random() < 0.5:
        props["prefix"] = rng.choice(["app-", "svc-", "res-", "env-"])
    return ResourceDef(var_name=var_name, resource_name=name, resource_type="random.RandomId", properties=props)


def random_pet_variation(rng: stdlib_random.Random, name: str, var_name: str) -> ResourceDef:
    """Generate a RandomPet with varied properties."""
    props: dict = {"length": rng.choice([2, 3, 4])}
    if rng.random() < 0.5:
        props["separator"] = rng.choice(["-", "_", "."])
    if rng.random() < 0.3:
        props["prefix"] = rng.choice(["prod", "staging", "dev", "test"])
    return ResourceDef(var_name=var_name, resource_name=name, resource_type="random.RandomPet", properties=props)


def random_shuffle_variation(rng: stdlib_random.Random, name: str, var_name: str) -> ResourceDef:
    """Generate a RandomShuffle with an input list and optional resultCount."""
    pool_options = [
        ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"],
        ["small", "medium", "large", "xlarge"],
        ["alpha", "beta", "gamma", "delta", "epsilon"],
        ["redis", "memcached", "dynamodb"],
    ]
    inputs = rng.choice(pool_options)
    props: dict = {"inputs": inputs}
    if rng.random() < 0.6:
        props["resultCount"] = rng.randint(1, len(inputs))
    return ResourceDef(var_name=var_name, resource_name=name, resource_type="random.RandomShuffle", properties=props)


def random_uuid_variation(_rng: stdlib_random.Random, name: str, var_name: str) -> ResourceDef:
    """Generate a RandomUuid."""
    return ResourceDef(var_name=var_name, resource_name=name, resource_type="random.RandomUuid", properties={})


RANDOM_GENERATORS = [
    random_string_variation,
    random_password_variation,
    random_integer_variation,
    random_id_variation,
    random_pet_variation,
    random_shuffle_variation,
    random_uuid_variation,
]

RANDOM_TYPE_NAMES = ["str", "pass", "int", "id", "pet", "shuffle", "uuid"]


def command_variation(
    rng: stdlib_random.Random,
    service: str,
    var_name: str,
    name: str,
) -> ResourceDef:
    """Generate a Command resource with varied environment and create script."""
    scripts = [
        f'echo "Initializing {service}"',
        f'echo "{service} ready"',
        f"date +%s",
        f'echo "HealthCheck: {service}"',
        f'printf "%s\\n" "{service}"',
    ]
    create_script = rng.choice(scripts)

    env: dict[str, str] = {"APP_NAME": service}
    if rng.random() < 0.6:
        env["PORT"] = str(rng.choice([3000, 5000, 8080, 8443, 9090]))
    if rng.random() < 0.4:
        env["LOG_LEVEL"] = rng.choice(["debug", "info", "warn", "error"])
    if rng.random() < 0.3:
        env["REGION"] = rng.choice(["us-east-1", "eu-west-1", "ap-southeast-1"])

    return ResourceDef(
        var_name=var_name, resource_name=name, resource_type="command.local.Command",
        properties={"create": create_script, "environment": env},
    )


def _output_prop_for_type(resource_type: str) -> str | None:
    """Return the primary output property for a given resource type."""
    return {
        "random.RandomString": "result",
        "random.RandomPassword": "result",
        "random.RandomInteger": "result",
        "random.RandomId": "hex",
        "random.RandomPet": "id",
        "random.RandomShuffle": "results",
        "random.RandomUuid": "result",
    }.get(resource_type)


def _to_camel(kebab: str) -> str:
    """Convert kebab-case to camelCase."""
    parts = kebab.split("-")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


# ---------------------------------------------------------------------------
# Resource generation for a given scale
# ---------------------------------------------------------------------------

# Scale breakdown: cert_chains contribute 5 resources each
SCALE_CONFIGS = {
    20: {"cert_chains": 1, "random": 10, "command": 5},
    40: {"cert_chains": 3, "random": 16, "command": 9},
    60: {"cert_chains": 4, "random": 25, "command": 15},
    100: {"cert_chains": 6, "random": 45, "command": 25},
}


def generate_resources_for_scale(scale: int) -> list[ResourceDef]:
    """Generate all resources for a given scale with cross-references.

    Uses a deterministic seed based on scale so the same scale always
    produces the same resources regardless of drift percentage.
    """
    rng = stdlib_random.Random(scale)
    config = SCALE_CONFIGS[scale]

    resources: list[ResourceDef] = []
    service_pool = list(SERVICES)
    rng.shuffle(service_pool)
    service_pool.extend(EXTRA_SERVICES)

    # --- Cert chains (deps first) ---
    cert_services = service_pool[: config["cert_chains"]]
    for svc in cert_services:
        chain = generate_cert_chain(svc, rng)
        resources.extend(chain.resources)

    # --- Random resources (varied types) ---
    random_resources: list[ResourceDef] = []
    all_services = service_pool[: max(config["cert_chains"] + 2, 4)]

    for i in range(config["random"]):
        svc = all_services[i % len(all_services)]
        gen_idx = i % len(RANDOM_GENERATORS)
        gen_func = RANDOM_GENERATORS[gen_idx]
        type_name = RANDOM_TYPE_NAMES[gen_idx]

        instance_num = i // len(RANDOM_GENERATORS)
        suffix = f"-{instance_num}" if instance_num > 0 else ""

        name = f"{svc}-{type_name}{suffix}"
        var_name = _to_camel(f"{svc}-{type_name}{suffix}")
        res = gen_func(rng, name, var_name)
        random_resources.append(res)

    # Wire some keepers references (random -> random)
    # keepers values must be Input<string>, so only reference types with string outputs
    string_output_types = {
        "random.RandomString", "random.RandomPassword",
        "random.RandomId", "random.RandomPet", "random.RandomUuid",
    }
    for i, res in enumerate(random_resources):
        if i < 2:
            continue
        if res.resource_type not in ("random.RandomString", "random.RandomPassword"):
            continue
        if rng.random() < 0.3:
            ref_idx = rng.randint(0, i - 1)
            ref_res = random_resources[ref_idx]
            if ref_res.resource_type not in string_output_types:
                continue
            output_prop = _output_prop_for_type(ref_res.resource_type)
            if output_prop:
                res.properties["keepers"] = {"ref": None}
                res.references["keepers"] = f"{{ ref: {ref_res.var_name}.{output_prop} }}"

    resources.extend(random_resources)

    # --- Command resources ---
    cmd_services = all_services
    for i in range(config["command"]):
        svc = cmd_services[i % len(cmd_services)]
        instance_num = i // len(cmd_services)
        suffix = f"-{instance_num}" if instance_num > 0 else ""

        name = f"{svc}-cmd{suffix}"
        var_name = _to_camel(f"{svc}-cmd{suffix}")
        res = command_variation(rng, svc, var_name, name)

        # Some commands get triggers referencing random outputs
        if random_resources and rng.random() < 0.35:
            ref_res = rng.choice(random_resources)
            output_prop = _output_prop_for_type(ref_res.resource_type)
            if output_prop:
                res.properties["triggers"] = [None]
                res.references["triggers"] = f"[{ref_res.var_name}.{output_prop}]"

        resources.append(res)

    return resources


# ---------------------------------------------------------------------------
# Drift mutation: property changes for each resource type
# ---------------------------------------------------------------------------


def _mutate_resource(res: ResourceDef, rng: stdlib_random.Random) -> ResourceDef:
    """Return a new ResourceDef with drifted property values.

    Preserves resource name, type, and references — only changes literal properties.
    """
    props = dict(res.properties)
    rt = res.resource_type

    if rt == "random.RandomString":
        # Change length, toggle special
        props["length"] = rng.choice([v for v in [8, 16, 24, 32, 64] if v != props.get("length", 16)])
        props["special"] = not props.get("special", False)

    elif rt == "random.RandomPassword":
        props["length"] = rng.choice([v for v in [16, 24, 32, 48] if v != props.get("length", 24)])

    elif rt == "random.RandomInteger":
        # Shift the range
        props["min"] = props.get("min", 1) + rng.randint(10, 50)
        props["max"] = props.get("max", 100) + rng.randint(10, 50)

    elif rt == "random.RandomId":
        props["byteLength"] = rng.choice([v for v in [4, 8, 16] if v != props.get("byteLength", 8)])

    elif rt == "random.RandomPet":
        props["length"] = rng.choice([v for v in [2, 3, 4] if v != props.get("length", 2)])

    elif rt == "random.RandomShuffle":
        if "resultCount" in props:
            max_count = len(props.get("inputs", []))
            if max_count > 1:
                props["resultCount"] = rng.choice(
                    [v for v in range(1, max_count + 1) if v != props["resultCount"]]
                )
        else:
            props["resultCount"] = 1

    elif rt == "random.RandomUuid":
        pass  # No meaningful property to change

    elif rt == "tls.PrivateKey":
        if props.get("algorithm") == "RSA":
            props["algorithm"] = "ECDSA"
            props.pop("rsaBits", None)
            props["ecdsaCurve"] = "P256"
        else:
            props["algorithm"] = "RSA"
            props.pop("ecdsaCurve", None)
            props["rsaBits"] = 2048

    elif rt == "tls.SelfSignedCert":
        hours = props.get("validityPeriodHours", 8760)
        props["validityPeriodHours"] = rng.choice([v for v in [8760, 17520, 43800, 87600] if v != hours])

    elif rt == "tls.CertRequest":
        dns = props.get("dnsNames", [])
        if dns:
            props["dnsNames"] = dns + [f"extra.{dns[0].lstrip('*.')}"]

    elif rt == "tls.LocallySignedCert":
        hours = props.get("validityPeriodHours", 8760)
        props["validityPeriodHours"] = rng.choice([v for v in [8760, 17520, 43800, 87600] if v != hours])

    elif rt == "command.local.Command":
        # Add/change an environment variable
        env = dict(props.get("environment", {}))
        env["DRIFT"] = "true"
        props["environment"] = env

    return ResourceDef(
        var_name=res.var_name,
        resource_name=res.resource_name,
        resource_type=res.resource_type,
        properties=props,
        references=dict(res.references),
    )


# ---------------------------------------------------------------------------
# Drift configuration: which resources get drifted and how
# ---------------------------------------------------------------------------


def _build_dependent_graph(resources: list[ResourceDef]) -> dict[str, set[str]]:
    """Map each var_name -> set of var_names that directly depend on it."""
    dependents: dict[str, set[str]] = {r.var_name: set() for r in resources}
    for res in resources:
        for ref_expr in res.references.values():
            for token in ref_expr.replace("{", " ").replace("}", " ").replace(",", " ").split():
                if "." in token:
                    dep_var = token.split(".")[0].strip()
                    if dep_var in dependents:
                        dependents[dep_var].add(res.var_name)
    return dependents


def _cascade(var_name: str, dependents: dict[str, set[str]]) -> set[str]:
    """Return full set of resources transitively depending on var_name (inclusive)."""
    result: set[str] = set()
    stack = [var_name]
    while stack:
        v = stack.pop()
        if v not in result:
            result.add(v)
            stack.extend(dependents.get(v, set()))
    return result


def compute_drift_config(
    resources: list[ResourceDef],
    drift_pct: int,
    rng: stdlib_random.Random,
) -> DriftConfig:
    """Compute which resources are drifted and how for partial drift.

    Drift budget is split:
      - ~40% property changes (scattered across types)
      - ~30% deletions (with cascading — deleting a resource also deletes dependents)
      - ~30% creations (extra resources added to drifted code)

    Cascading deletions: when a resource is selected for deletion, all resources
    that transitively depend on it are also deleted. The cascade cost (total
    resources removed) is subtracted from the deletion budget.
    """
    total_drift = max(1, round(len(resources) * drift_pct / 100))

    prop_change_count = max(1, round(total_drift * 0.4))
    deletion_budget = max(0, round(total_drift * 0.3))
    creation_count = max(0, total_drift - prop_change_count - deletion_budget)

    # Build dependency graph for cascading deletions
    dependents = _build_dependent_graph(resources)
    var_to_idx = {r.var_name: i for i, r in enumerate(resources)}

    # Find resources eligible for property changes (not RandomUuid — nothing to change)
    mutable_indices = [
        i for i in range(len(resources))
        if resources[i].resource_type != "random.RandomUuid"
    ]

    # Select property change targets
    rng.shuffle(mutable_indices)
    property_change_indices = sorted(mutable_indices[:prop_change_count])
    changed_set = set(property_change_indices)

    # Select deletion targets with cascading
    # Prioritize resources with dependents (harder drift scenarios)
    candidates = [
        i for i in range(len(resources))
        if i not in changed_set
    ]
    # Sort: resources with more transitive dependents first
    candidates.sort(
        key=lambda i: len(_cascade(resources[i].var_name, dependents)),
        reverse=True,
    )

    deletion_indices: list[int] = []
    deleted_vars: set[str] = set()
    remaining_budget = deletion_budget

    for idx in candidates:
        if remaining_budget <= 0:
            break
        res = resources[idx]
        if res.var_name in deleted_vars:
            continue  # Already cascade-deleted

        cascade_set = _cascade(res.var_name, dependents)
        # Exclude already-deleted vars from cost
        new_deletions = cascade_set - deleted_vars
        cost = len(new_deletions)

        if cost <= remaining_budget:
            deleted_vars.update(new_deletions)
            remaining_budget -= cost

    # Convert deleted var_names back to indices
    deletion_indices = sorted(var_to_idx[v] for v in deleted_vars if v in var_to_idx)

    # Generate extra resources for creation drift
    extra_resources = _generate_extra_resources(rng, creation_count)

    return DriftConfig(
        property_change_indices=property_change_indices,
        deletion_indices=deletion_indices,
        extra_resources=extra_resources,
    )


def _generate_extra_resources(rng: stdlib_random.Random, count: int) -> list[ResourceDef]:
    """Generate extra resources that only exist in the drifted code."""
    extras: list[ResourceDef] = []
    extra_types = [
        ("random.RandomString", lambda _: {"length": rng.choice([16, 24, 32]), "special": rng.choice([True, False])}),
        ("random.RandomPassword", lambda _: {"length": rng.choice([16, 24, 32]), "special": True}),
        ("random.RandomId", lambda _: {"byteLength": rng.choice([4, 8, 16])}),
        ("command.local.Command", lambda i: {
            "create": f'echo "extra-resource-{i}"',
            "environment": {"APP_NAME": "extra", "INDEX": str(i)},
        }),
    ]

    for i in range(count):
        type_idx = i % len(extra_types)
        resource_type, prop_fn = extra_types[type_idx]
        name = f"extra-{i}"
        var_name = f"extra{i}"
        extras.append(ResourceDef(
            var_name=var_name,
            resource_name=name,
            resource_type=resource_type,
            properties=prop_fn(i),
        ))

    return extras


# ---------------------------------------------------------------------------
# Fixture rendering with drift applied
# ---------------------------------------------------------------------------


def render_drifted_index_ts(
    resources: list[ResourceDef],
    drift_config: DriftConfig,
    rng: stdlib_random.Random,
) -> str:
    """Render the drifted version: property changes, deletions, extras."""
    changed_set = set(drift_config.property_change_indices)
    deleted_set = set(drift_config.deletion_indices)

    drifted_resources: list[ResourceDef] = []
    for i, res in enumerate(resources):
        if i in deleted_set:
            continue
        if i in changed_set:
            drifted_resources.append(_mutate_resource(res, rng))
        else:
            drifted_resources.append(res)

    # Append extra resources
    drifted_resources.extend(drift_config.extra_resources)

    return render_index_ts(drifted_resources)


# ---------------------------------------------------------------------------
# File generation
# ---------------------------------------------------------------------------


def fixture_name(scale: int, drift_pct: int) -> str:
    """Generate fixture directory name."""
    if drift_pct == 100:
        return f"complex-{scale}-full"
    return f"complex-{scale}-{drift_pct}pct"


def generate_pulumi_yaml(scale: int, drift_pct: int) -> str:
    name = fixture_name(scale, drift_pct)
    drift_desc = "all creates" if drift_pct == 100 else f"{drift_pct}% drift"
    return textwrap.dedent(f"""\
        name: {name}
        runtime: nodejs
        description: Complex drift test ({scale} resources, {drift_desc})
    """)


def generate_package_json(scale: int, drift_pct: int) -> str:
    data = {
        "name": fixture_name(scale, drift_pct),
        "version": "1.0.0",
        "main": "index.ts",
        "devDependencies": {
            "@types/node": "^20.0.0",
            "typescript": "^5.0.0",
        },
        "dependencies": {
            "@pulumi/pulumi": "^3.0.0",
            "@pulumi/random": "^4.0.0",
            "@pulumi/command": "^1.0.0",
            "@pulumi/tls": "^5.0.0",
        },
    }
    return json.dumps(data, indent=2) + "\n"


def generate_drifted_code(scale: int, drift_pct: int, seed: int | None = None) -> str:
    """Generate drifted index.ts content for a given scale and drift percentage.

    Uses a random seed by default so drift varies between runs, preventing
    agents from memorizing or deriving the expected answer.
    """
    resources = generate_resources_for_scale(scale)  # deterministic per scale
    if drift_pct == 100:
        # Full drift: empty original, all resources in drifted.
        # Resources are deterministic per scale — randomness isn't needed here
        # because the agent works from drift-adopter output (state), not the fixture.
        return render_index_ts(resources)
    drift_rng = stdlib_random.Random(seed)  # None = truly random
    drift_config = compute_drift_config(resources, drift_pct, drift_rng)
    return render_drifted_index_ts(resources, drift_config, drift_rng)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate complex drift test fixtures")
    parser.add_argument("--with-drifted", action="store_true",
                        help="Also generate drifted/ subdirectories (for local debugging)")
    args = parser.parse_args()

    output_base = Path(__file__).resolve().parent / "drift-adoption"

    for scale in SCALES:
        # Generate resources once per scale (deterministic seed)
        resources = generate_resources_for_scale(scale)

        for drift_pct in DRIFT_PCTS:
            name = fixture_name(scale, drift_pct)
            print(f"Generating {name}...")

            out_dir = output_base / name
            out_dir.mkdir(parents=True, exist_ok=True)

            if drift_pct == 100:
                # Full drift: empty original, all resources in drifted
                (out_dir / "index.ts").write_text(generate_empty_index_ts())
                print(f"  {len(resources)} resources, 100% drift (all creates)")
            else:
                # Partial drift: original has all resources
                (out_dir / "index.ts").write_text(render_index_ts(resources))
                print(f"  {len(resources)} resources, {drift_pct}% drift")

            if args.with_drifted:
                drifted_dir = out_dir / "drifted"
                drifted_dir.mkdir(parents=True, exist_ok=True)
                seed = scale * 1000 + drift_pct
                (drifted_dir / "index.ts").write_text(
                    generate_drifted_code(scale, drift_pct, seed=seed)
                )
                print(f"  (wrote drifted/ with seed={seed})")

            # Config files
            (out_dir / "Pulumi.yaml").write_text(generate_pulumi_yaml(scale, drift_pct))
            (out_dir / "package.json").write_text(generate_package_json(scale, drift_pct))
            (out_dir / "tsconfig.json").write_text(generate_tsconfig())

    print("Done!")


if __name__ == "__main__":
    main()

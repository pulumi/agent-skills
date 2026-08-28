---
name: pulumi-context-api
description: |
    Query the Pulumi Context API, a graph query interface over an
    organization's infrastructure in Pulumi Cloud. Use when a question is
    about relationships or reachability across resources and stacks: blast
    radius ("what breaks if I change this?"), what depends on a resource or
    a stack's outputs, provider version inventory across stacks, orphaned or
    unreferenced resources, or references that cross stacks and cloud
    accounts, including resources Pulumi doesn't manage. Don't load it for
    finding a single resource by name, type, or property (Resource Search
    covers that), or for update history and failure debugging (use skill
    `pulumi-debug-failed-operation`).
---

# Query the Pulumi Context API

The Context API answers questions about an organization's cloud infrastructure
as a graph: what exists, what depends on what, what a change would affect. It
covers cloud-scanned resources Pulumi doesn't manage, not just Pulumi-managed
ones.

Prefer it over Resource Search whenever the question involves relationships.
Resource Search finds individual resources but cannot follow edges, so
answering "what depends on X" with repeated searches is slow and usually
incomplete.

## Step 1: fetch the primer, always

```bash
pulumi api GetGraphSchema -F orgName=<org>
```

This returns a self-contained guide to composing selectors — vocabulary, edge
types, engine caps, worked examples, pagination, and the traps that produce a
confident wrong answer. It is served by the deployment that answers your
queries, so it is the contract; this skill deliberately does not copy it,
because a pasted grammar ages and a stale selector 400s.

**Read it in full — never truncate it with `head`, `tail`, or a byte cap.**

If `pulumi api` doesn't know `GetGraphSchema`, run `pulumi api list
--refresh-spec` first. Use `pulumi org get-default` if you need the org name.

## Step 2: query

```bash
pulumi api GraphQuery -F orgName=<org> --input selector.json
```

The wire format is a JSON selector, not query text — the API maps onto ISO GQL
semantics but accepts no Cypher, GQL, or GraphQL strings. Compose it from the
primer rather than from memory.

## Step 3: check completeness before answering

Read three signals in every response, and follow the primer's rules for them:

- `meta.resultMode` — `truncated` means engine caps clipped the answer.
- `meta.visibility` — `trimmed` means RBAC may have hidden part of the walk.
- `pageInfo.continuationToken` — present means more pages remain.

Any of the three disqualifies a completeness claim: blast radius, "nothing
depends on this", an exhaustive cleanup list, a total. Narrow the selector, or
drain the pages, and say what the answer does cover.

## Availability

Public preview, for organizations on the Enterprise and Business Critical
plans. Needs Pulumi CLI v3.243.0 or newer, an active `pulumi login`, and a role
granting `resources:search` (the default Member and Admin roles do).

A denial names its gate — `402 Payment Required` is the plan, `409 Conflict` a
self-hosted license, a 404 naming the org a bad name or missing permission.
Report the gate to the user instead of retrying. The primer's "When it denies
you" table covers the rest.

## Scope of the graph

Resources, stacks, and the relationships between them. Not resource property
values, deployment or update history, ESC environments, or cost and policy
data — use Resource Search and the regular REST API for those. Results are
trimmed to the stacks and accounts the caller can see.

Human-readable reference:
[Context API overview](https://www.pulumi.com/docs/insights/context-api/) and
[query guide](https://www.pulumi.com/docs/insights/guides/context-api/).

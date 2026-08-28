---
name: pulumi-context-api
description: |
    Query the Pulumi Context API, a graph query interface over an
    organization's infrastructure in Pulumi Cloud. Use when a question is
    about relationships or reachability across resources and stacks: the
    impact of a change ("what breaks if I change this?", blast radius), what
    depends on a resource or a stack's outputs, which provider instances
    manage which resources and at what versions, orphaned or unreferenced
    resources, or references that cross stacks and cloud accounts, including
    resources Pulumi doesn't manage. Don't load it for finding a single
    resource by name, type, or property (Resource Search covers that), or for
    update history and failure debugging (use skill
    `pulumi-debug-failed-operation`).
---

# Query the Pulumi Context API

The Context API answers questions about an organization's cloud infrastructure
as a graph: what exists, what depends on what, what a change would affect. It
covers resources found through Pulumi Discovery, not just Pulumi-managed ones.

Prefer it over Resource Search whenever the question involves relationships.
Resource Search finds individual resources but cannot follow edges, so
answering "what depends on X" with repeated searches is slow and usually
incomplete.

Public preview, for organizations on the Enterprise and Business Critical
editions. Needs Pulumi CLI v3.243.0 or newer, an active `pulumi login`, and a
role granting `resources:search` (the default Member and Admin roles do).

## Step 1: fetch the primer, always

`pulumi whoami -v` lists every organization the login can reach. Ask which one
the question is about rather than assuming the default org — that is often an
individual account with no entitlement.

```bash
pulumi api GetGraphSchema -F orgName=<org>
```

This returns a self-contained guide to composing selectors — vocabulary, edge
types, engine caps, worked examples, pagination, completeness rules, and the
traps that produce a confident wrong answer instead of an error. It is served
by the deployment that answers your queries, so it is the contract, and it
moves between schema versions. This skill bootstraps you to it and stops there;
everything below defers to it. Fetch it fresh in every session and for every
org you query — a primer remembered from earlier may describe a schema this
deployment no longer serves.

**Read it in full — never truncate it with `head`, `tail`, or a byte cap.** A
clipped primer means malformed selectors and rejected queries.

### If this call fails

You have no primer yet, so handle it here rather than looking it up there:

| Response | Meaning |
|---|---|
| `402 Payment Required` | the org's edition doesn't include the Context API |
| `409 Conflict` | a self-hosted install whose license doesn't enable it |
| `404 Not Found: '<org>' not found` | bad org name, or the caller lacks permission on it |
| `404 Not Found`, detail-free | a wrong path or method name, or a deployment without the endpoint |
| `503 Service Unavailable` | transient — retry |

Report the gate to the user instead of retrying anything but the 503. If
`pulumi api` doesn't know `GetGraphSchema` at all, that is not a gate: run
`pulumi api list --refresh-spec` to refresh the cached spec, then retry the
fetch.

## Step 2: query

```bash
pulumi api GraphQuery -F orgName=<org> --input selector.json
```

The body is a JSON selector, not query text. Compose it from the primer you
just read, not from memory or from a grammar you recall from another session.

## Step 3: apply the primer's completeness rules before answering

Every response carries fidelity signals — currently `meta.resultMode`,
`meta.visibility`, and `pageInfo.continuationToken`; the primer names the
authoritative set. Read the primer's rules for them and follow them; the
remedies differ per signal and a stale paraphrase here would be worse than
none.

What matters most: **a completeness claim needs all of them clean.** Impact
analysis, "nothing depends on this", an exhaustive cleanup list, a total across
groups — none of these survive a truncated result, a trimmed traversal, or an
undrained page. When you can't get there, say what the answer does cover.

## Scope of the graph

Resources, stacks, and the relationships between them, trimmed to the stacks
and accounts the caller can see. The primer's "What it cannot answer yet"
section is the live boundary — check it before concluding a question is
unanswerable, and reach for a different API rather than approximating one of
those gaps with a graph query.

One boundary worth knowing up front, because it decides which API to use: the
graph returns a schema-declared subset of fields per node type, not full
resource property bags. The primer lists which fields each node type can match
on and which it can return; when the question needs the property values
themselves, they come back from Resource Search.

Human-readable reference:
[Context API overview](https://www.pulumi.com/docs/insights/context-api/) and
[query guide](https://www.pulumi.com/docs/insights/guides/context-api/).

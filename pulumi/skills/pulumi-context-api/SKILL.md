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
as a graph: what exists, what depends on what, what a change would affect. One
query replaces the REST-call-and-`jq` pipelines these questions used to need,
and it covers cloud-scanned resources Pulumi doesn't manage, not just
Pulumi-managed ones.

Prefer it over Resource Search whenever the question involves relationships.
Resource Search finds individual resources but cannot follow edges, so
answering "what depends on X" with repeated searches is slow and usually
incomplete.

## Availability

The Context API is available to organizations on the Enterprise and Business
Critical plans. You need Pulumi CLI v3.243.0 or newer and an active
`pulumi login`; `pulumi api` reuses those credentials.

Both "not enabled for this organization" and "plan doesn't include it" surface
identically: a detail-free `{"code":404,"message":"Not Found"}`. Do not retry
or treat that as a transient error — tell the user the organization's plan may
not include the Context API. A 404 that *names* the organization is different:
a mistyped org name, or a role without resource-search permission.

## Workflow

1. Fetch the primer:

   ```bash
   pulumi api GetGraphSchema -F orgName=<org>
   ```

   This returns a self-contained guide to composing query selectors, kept in
   sync with the deployment answering your queries. **Read it in full — never
   truncate it with `head`, `tail`, or a byte cap.** A clipped primer means
   malformed selectors and rejected queries. If `pulumi api` doesn't know the
   `GetGraphSchema` command, run `pulumi api list --refresh-spec` first.

2. Compose a selector following the primer and post it:

   ```bash
   pulumi api GraphQuery -F orgName=<org> --input selector.json
   ```

   The wire format is a JSON selector, not query text — the API maps onto ISO
   GQL semantics but accepts no Cypher, GQL, or GraphQL strings. Do not guess
   the grammar or hardcode vocabulary from memory; the primer is the contract
   and it moves between schema versions.

3. Check `meta.resultMode` in every response before answering. `exact` means
   the answer is complete; `truncated` means engine caps clipped it — narrow
   the scope (for example `scope.stacks: ["<project>/*"]`) and query again.
   This matters most for absence claims ("nothing depends on this", "no
   orphans"): never state one from a truncated result.

## Scope of the graph

The graph locates resources, stacks, and the relationships between them. It
does not return resource property values, deployment or update history, ESC
environments, or cost and policy data — use Resource Search and the regular
REST API for those. Results are trimmed to the stacks and accounts the caller
can see.

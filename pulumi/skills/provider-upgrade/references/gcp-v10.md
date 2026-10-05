# pulumi-gcp v9 to v10

Every breaking change in pulumi-gcp v10.0.0, derived from the v10 migration guide
(https://www.pulumi.com/registry/packages/gcp/how-to-guides/10-0-migration/). The guide is the
source of truth: each detailed row links its section, which has a read-only `pulumi stack
export | jq` detection command and before/after code in every language. Read that section
before fixing a `REPLACE` or `DELETE` row, and cite it when you accept a diff.

## Before the bump

Some v10 changes destroy live resources if the fix is made in the wrong order, so do these
steps before step 2 of the skill:

1. **Version gate.** The deployed major must be 9 (check `pulumi:providers:gcp` in
   `pulumi stack export`). On 8.x or older, stop: the user completes the v9 migration first
   (https://www.pulumi.com/registry/packages/gcp/how-to-guides/9-0-migration/). Do not jump
   two majors in one step. Already on 10.x: skip to the tables below and work from the preview.
2. **Clean v9 baseline.** Still on v9, run `pulumi preview --refresh --run-program` per stack.
   If it is not clean, stop and ask the user to settle it; diffs that exist before the bump
   will be blamed on v10.
3. **Find affected resources.** Run the state scan and the code pass below.
4. **Gate on risk.** Present the affected rows to the user grouped by risk (`REPLACE`,
   `DELETE`, `UPDATE`, `BUILD`, `VALUE`, `NONE`) before editing anything. For each `REPLACE`
   or `DELETE` row, state what is destroyed and get the user's choice.
5. **Order removed types state first.** For `gcp.notebooks.*`, `gcp.iap.Brand`/`Client`,
   `gcp.beyondcorp.App*`, `gcp.ml.EngineModel` and `gcp.vertex.AiSchedule`, write out
   `pulumi state delete` commands for the user, dependents first, and only then remove the
   code. Removing code first makes `pulumi up` send the delete to the v9 provider in state,
   which destroys the live resource. Adopt a successor with `pulumi import`, never a create.

Fixes that most often go wrong:

- `gcp.compute.Instance` with a `guestAccelerators` entry of `count: 0`: omit the list
  instead. A replace loses the boot disk and local SSD data.
- `gcp.secretmanager.SecretVersion` without `secretDataWoVersion`: set it to `""`. Any other
  value, including `"0"`, replaces the secret version.
- `gcp.bigquery.Dataset.defaultCollation`: pin the value the live resource has today, read
  from state.
- `loadBalancingScheme` unset on a classic `gcp.compute.BackendService` or
  `GlobalForwardingRule`: set `"EXTERNAL"` explicitly before the bump, as upstream advises.

Never run `pulumi up`, `pulumi refresh`, `pulumi destroy`, `pulumi state delete` or
`pulumi import` yourself; write them out for the user. `pulumi preview` and
`pulumi stack export` are read-only. Then return to step 2 of the skill and continue the core
loop.

## Risk levels

| Risk | Meaning |
|---|---|
| `REPLACE` | Left unfixed, `pulumi up` destroys and recreates the live resource. |
| `DELETE` | The wrong fix order makes `pulumi up` delete the live resource. |
| `UPDATE` | Left unfixed, `pulumi up` changes a live setting in place. |
| `BUILD` | Program fails to compile or `pulumi preview` fails; nothing deploys until fixed. |
| `VALUE` | A value the program reads back changes or disappears; the resource itself is unchanged. |
| `NONE` | No action needed on migration. |

## State scan

Run against each stack while still on v9. It lists every resource type in state that has a
row below, with a count. No output means no row applies through state; still run the code pass
for functions (data sources are never in state) and for code that reads values back.

```bash
pulumi stack export \
  | jq -r '.deployment.resources[].type' \
  | sort | uniq -c \
  | grep -E \
      -e 'gcp:(notebooks|ml)/' \
      -e 'gcp:iap/(brand|client):' \
      -e 'gcp:beyondcorp/app(Connection|Connector|Gateway):' \
      -e 'gcp:vertex/aiSchedule:' \
      -e 'gcp:compute/(instance|serviceAttachment|reservation|backendService|globalForwardingRule|interconnectAttachmentGroup):' \
      -e 'gcp:bigquery/(dataset|dataTransferConfig):' \
      -e 'gcp:secretmanager/secretVersion:' \
      -e 'gcp:monitoring/uptimeCheckConfig:' \
      -e 'gcp:container/(cluster|nodePool):' \
      -e 'gcp:workflows/workflow:' \
      -e 'gcp:cloudrunv2/workerPool:' \
      -e 'gcp:applicationintegration/client:' \
      -e 'gcp:cloudsecuritycompliance/framework:' \
      -e 'gcp:dataloss/preventionJobTrigger:' \
      -e 'gcp:iam/workforcePoolProviderScimTenant:' \
      -e 'gcp:netapp/storagePool:'
```

## Code pass

Patterns are extended regexes for `grep -rniE` or `rg -i` over the program source. They match
TypeScript/Java camelCase, Python snake_case, Go/.NET PascalCase and YAML tokens
(`gcp:notebooks:Instance`). Python `from pulumi_gcp import notebooks` and Go import aliases can
hide the module prefix: if a file imports the module, also grep for the bare resource name.

## Detailed changes

Each row links its guide section.

| Resource (state type) | What changed | Grep | Action | Risk |
|---|---|---|---|---|
| `gcp.compute.Instance` (`gcp:compute/instance:Instance`) [guide](https://www.pulumi.com/registry/packages/gcp/how-to-guides/10-0-migration/#gcpcomputeinstance-a-guestaccelerator-count-of-0-now-replaces-the-instance) | A `guestAccelerators` entry with `count: 0` is now acted on. Replaces the instance if an accelerator is attached or more than one block is declared. | `guest_?accelerators?` | Omit the list (undefined/None/nil) when no accelerator is wanted instead of passing `count: 0`. Replacement loses the boot disk and local SSD data and changes IPs; take a snapshot if the user chooses it. | `REPLACE` |
| `gcp.iap.Brand`, `gcp.iap.Client` (`gcp:iap/brand:Brand`, `gcp:iap/client:Client`), function `gcp.iap.getClient` [guide](https://www.pulumi.com/registry/packages/gcp/how-to-guides/10-0-migration/#gcpiapbrand-and-gcpiapclient-removed) | Removed; Google shut down the IAP OAuth Admin API. No replacement type. | `iap\w*[.:/]\w*(brand\|client)` | User runs `pulumi state delete` on the Client, then the Brand, then you remove the code. Replace `getClient` reads with stack config (`requireSecret` for the secret). Removing code first deletes the live OAuth client, which cannot be recreated with the same ID. | `DELETE` |
| `gcp.notebooks.*` (`gcp:notebooks/...`: Instance, Runtime, Environment and their IAM Policy/Binding/Member, `getInstanceIamPolicy`, `getRuntimeIamPolicy`) [guide](https://www.pulumi.com/registry/packages/gcp/how-to-guides/10-0-migration/#gcpnotebooks-the-module-has-been-removed) | Whole module removed; the product is end of life. Successor is `gcp.workbench.Instance` and `gcp.workbench.InstanceIamMember`. | `gcp\w*[.:/]notebooks` | Keep the machine: user migrates it at GCP level (`POST https://notebooks.googleapis.com/v1/projects/PROJECT/locations/ZONE/instances/NAME:migrate`), runs `pulumi state delete` (IAM first, then instance), then `pulumi import gcp:workbench/instance:Instance`. Settings move under `gceSetup`, disk sizes become strings, IAM `instanceName` becomes `name`. Take the full field mapping from the guide section, do not guess it. Removing code first deletes the VM and, unless `noRemoveDataDisk`, its data disk. | `DELETE` |
| `gcp.bigquery.Dataset` (`gcp:bigquery/dataset:Dataset`) [guide](https://www.pulumi.com/registry/packages/gcp/how-to-guides/10-0-migration/#gcpbigquerydataset-an-undeclared-defaultcollation-is-now-cleared) | `defaultCollation` no longer computed; unset or `""` clears a live collation. Output is now optional. | `default_?collation` | Set `defaultCollation` to the live value from state (`outputs.defaultCollation`) where the program leaves it unset or `""`. A dataset not yet in state has nothing to preserve. Give reads of the output a fallback. | `UPDATE`, `BUILD` |
| `gcp.secretmanager.SecretVersion` (`gcp:secretmanager/secretVersion:SecretVersion`) [guide](https://www.pulumi.com/registry/packages/gcp/how-to-guides/10-0-migration/#gcpsecretmanagersecretversion-secretdatawoversion-is-required-alongside-secretdatawo-and-is-a-string) | `secretDataWoVersion` now required with `secretDataWo`, and is a string, not an integer. | `secret_?data_?wo` | Number: quote it (`1` becomes `"1"`). Omitted: set `""`. Any other value, including `"0"`, replaces the secret version. | `BUILD`, `REPLACE` if set wrong |
| `gcp.monitoring.UptimeCheckConfig` (`gcp:monitoring/uptimeCheckConfig:UptimeCheckConfig`) [guide](https://www.pulumi.com/registry/packages/gcp/how-to-guides/10-0-migration/#gcpmonitoringuptimecheckconfig-the-two-password-fields-are-now-mutually-exclusive) | `httpCheck.authInfo` must set exactly one of `password` and `passwordWo`. | `auth_?info\|password_?wo` | Both set: remove `passwordWo` and `passwordWoVersion` (keeps the credential v9 actually sent). Neither set: add `password: ""`, which is never sent to the API. | `BUILD` |
| `gcp.container.Cluster` `nodePools[]`, `gcp.container.NodePool` (`gcp:container/nodePool:NodePool`) [guide](https://www.pulumi.com/registry/packages/gcp/how-to-guides/10-0-migration/#gcpcontainercluster-and-gcpcontainernodepool-nameprefix-may-now-be-up-to-31-characters) | `namePrefix` may be up to 31 characters. Existing names are not regenerated. | `name_?prefix` | None. Do not change `namePrefix` on a live pool: that replaces the pool and its nodes. | `NONE` |
| `gcp.workflows.Workflow` (`gcp:workflows/workflow:Workflow`) [guide](https://www.pulumi.com/registry/packages/gcp/how-to-guides/10-0-migration/#gcpworkflowsworkflow-sourcecontents-is-now-required) | `sourceContents` is now required (GCP always rejected a workflow without it). | `workflows\w*[.:/]\w*Workflow\b` | Any deployed workflow already has it; only a program that never deployed is affected. | `BUILD` |
| `gcp.cloudrunv2.WorkerPool` (`gcp:cloudrunv2/workerPool:WorkerPool`), function `getWorkerPool` [guide](https://www.pulumi.com/registry/packages/gcp/how-to-guides/10-0-migration/#gcpcloudrunv2workerpool-probe-header-fields-changed) | Probe `httpGet.httpHeaders` is now a list; `httpHeaders.name` required; `httpHeaders.port` removed; top-level `customAudiences` removed. | `http_?headers\|custom_?audiences` (only in WorkerPool code; `cloudrunv2.Service` is unchanged) | Wrap the header in a list. Delete `customAudiences` lines and reads (the API never accepted it). No replace, no update. | `BUILD` |
| `gcp.compute.ServiceAttachment` (`gcp:compute/serviceAttachment:ServiceAttachment`) [guide](https://www.pulumi.com/registry/packages/gcp/how-to-guides/10-0-migration/#gcpcomputeserviceattachment-natsubnets-and-consumerrejectlists-are-now-sets) | `natSubnets` and `consumerRejectLists` are sets. Order in state changes on the first refresh; a recurring v9 diff goes away. | `nat_?subnets\|consumer_?reject_?lists` | Only if code reads an element by index: read from the value the program supplied instead. Make the edit before the first refresh. | `VALUE` |
| `gcp.container.Cluster` (`gcp:container/cluster:Cluster`) [guide](https://www.pulumi.com/registry/packages/gcp/how-to-guides/10-0-migration/#gcpcontainercluster-the-enablecomponents-fields-are-now-sets) | `loggingConfig.enableComponents` and `monitoringConfig.enableComponents` are sets; read back sorted. | `enable_?components` | Only if code reads by index: switch to a membership test or sort explicitly. | `VALUE` |
| `gcp.compute.Reservation` (`gcp:compute/reservation:Reservation`), function `getReservation` [guide](https://www.pulumi.com/registry/packages/gcp/how-to-guides/10-0-migration/#gcpcomputereservation-top-level-reservationblockcount-removed) | Top-level `reservationBlockCount` removed (never settable). | `reservation_?block_?count` | Read `resourceStatuses[0].reservationBlockCount` with a `0` fallback (the list is empty for a reservation with no blocks). In interpreted languages an unfixed read silently drops stack outputs. | `BUILD`, `VALUE` |
| `gcp.compute.BackendService`, `gcp.compute.GlobalForwardingRule` (`gcp:compute/backendService:BackendService`, `gcp:compute/globalForwardingRule:GlobalForwardingRule`) [guide](https://www.pulumi.com/registry/packages/gcp/how-to-guides/10-0-migration/#gcpcomputebackendservice-and-gcpcomputeglobalforwardingrule-loadbalancingscheme-now-defaults-to-external_managed) | `loadBalancingScheme` default changed from `EXTERNAL` (classic) to `EXTERNAL_MANAGED`. Tested: a new load balancer left unset fails partway through `pulumi up` with `Error 400`; an existing classic load balancer can silently end up mixed; switching back to `EXTERNAL` is rejected after 90 days and then needs `--replace`. | `BackendService\b\|global_?forwarding_?rule` then check for `load_?balancing_?scheme` | Before upgrading, set `loadBalancingScheme: "EXTERNAL"` explicitly on every classic load balancer's backend services and global forwarding rules where it is unset (confirm the live value in state, `outputs.loadBalancingScheme`). Set it consistently on both halves of each load balancer. Only move to `EXTERNAL_MANAGED` as a deliberate, separate change. | `REPLACE`, `BUILD` |

## Other changes (guide lists them only)

The guide has no detection command or code for these. Derive the fix from the row and confirm
with `pulumi preview --refresh --run-program`.

| Resource or function (state type) | What changed | Grep | Action | Risk |
|---|---|---|---|---|
| `gcp.beyondcorp.AppConnection`, `AppConnector`, `AppGateway` (`gcp:beyondcorp/app...`), functions `getAppConnection`, `getAppConnector`, `getAppGateway` | Removed. Successors: `gcp.beyondcorp.SecurityGateway`, `SecurityGatewayApplication`. | `beyondcorp\w*[.:/]\w*App(Connection\|Connector\|Gateway)\|app_(connection\|connector\|gateway)` | Same order as the IAP and notebooks rows: user runs `pulumi state delete` before code is removed; adopt any successor with `pulumi import`. | `DELETE` |
| `gcp.ml.EngineModel` (`gcp:ml/engineModel:EngineModel`) | Removed; `gcp.ml` module gone. Successor: Vertex AI resources such as `gcp.vertex.AiEndpoint`. | `gcp\w*[.:/]ml[.:/]\|engine_?model` | As above: `pulumi state delete` first, then remove code. | `DELETE` |
| `gcp.vertex.AiSchedule` (`gcp:vertex/aiSchedule:AiSchedule`) | Removed. Successor: `gcp.colab.Schedule`. | `ai_?schedule` | As above. | `DELETE` |
| `gcp.bigquery.DataTransferConfig` (`gcp:bigquery/dataTransferConfig:DataTransferConfig`) | Exactly one of `sensitiveParams.secretAccessKey` and `secretAccessKeyWo` must be set; `secretAccessKeyWoVersion` is now a string. | `secret_?access_?key` | Keep exactly one of the two; quote a numeric `secretAccessKeyWoVersion`. | `BUILD` |
| `gcp.compute.ServiceAttachment` | `consumerAcceptLists[].projectIdOrNum`, `networkUrl`, `endpointUrl` default to `""` instead of null. | `consumer_?accept_?lists` | Only if code reads those back: treat `""` as absent. | `VALUE` |
| `gcp.applicationintegration.Client` (`gcp:applicationintegration/client:Client`) | `runAsServiceAccount` removed. | `run_?as_?service_?account` | Remove the argument; check preview for a diff. | `BUILD` |
| `gcp.cloudsecuritycompliance.Framework` (`gcp:cloudsecuritycompliance/framework:Framework`) | `cloudControlDetails` is a set; order ignored, duplicates rejected. | `cloud_?control_?details` | Remove duplicate entries; stop reading by index. | `BUILD`, `VALUE` |
| `gcp.compute.InterconnectAttachmentGroup` (`gcp:compute/interconnectAttachmentGroup:InterconnectAttachmentGroup`) | `logicalStructures[].regions[].metros[].facilities[].zones[].attachment` removed. | `logical_?structures` | Read `attachments` instead. | `BUILD` |
| `gcp.dataloss.PreventionJobTrigger` (`gcp:dataloss/preventionJobTrigger:PreventionJobTrigger`) | `actions.publishFindingsToCloudDataCatalog` removed. | `publish_?findings_?to_?cloud_?data_?catalog` | Remove the action; check preview for a diff. | `BUILD` |
| `gcp.iam.WorkforcePoolProviderScimTenant` (`gcp:iam/workforcePoolProviderScimTenant:WorkforcePoolProviderScimTenant`) | `claimMapping` required on create. | `scim_?tenant` | Existing tenants: none. New ones: set `claimMapping`. | `BUILD` |
| `gcp.netapp.StoragePool` (`gcp:netapp/storagePool:StoragePool`) | `scaleTier` removed. | `scale_?tier` | Remove the argument; check preview for a diff. | `BUILD` |
| Functions `gcp.backupdisasterrecovery.getBackupPlanAssociations`, `getDataSourceReferences` | `resourceType` removed. | `get_?(backup_?plan_?associations\|data_?source_?references)` | Remove the argument. | `BUILD` |

In the Grep column, `\|` is a literal `|` escaped for the table; type `|` when running the
pattern.

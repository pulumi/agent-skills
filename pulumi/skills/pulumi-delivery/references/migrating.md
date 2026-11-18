# Migrate CI or Deployments to Pulumi Delivery

The goal is a delivery program that does what the existing pipeline does for Pulumi stacks. Read the existing pipeline, map it with the tables below, then write the program with `authoring.md`.

## 1. Inventory the existing pipeline

For each workflow or pipeline file, record:

- What starts it (branches, paths, tags, schedules, manual runs).
- Each job: its order (`needs`, `stages`, `dependsOn`), its environment, and what it runs.
- Each Pulumi step: the command (`pulumi up`, `pulumi preview`, the `pulumi/actions` action), the stack, the working directory.
- Each non-Pulumi step: build, test, smoke check, notification.
- Each approval: GitHub environment protection rules, GitLab `when: manual` or protected environments, Azure DevOps approvals and checks.
- Each secret and cloud credential, and where it comes from (CI secrets, OIDC role, ESC).

For Pulumi Deployments, read the settings of each stack:

```sh
pulumi api GetDeploymentSettings -F orgName=<org> -F projectName=<project> -F stackName=<stack> --output=json
```

Record the source repository, branch and directory, the pre-run commands, the environment variables, the OIDC settings and the push-to-deploy and path filters.

## 2. Map the concepts

### GitHub Actions

| GitHub Actions | Delivery |
| --- | --- |
| `on.push.branches` | Source `branch` with `trigger: true` |
| `on.push.paths` | `trigger: { paths: [...] }` |
| A job that runs `pulumi up` for one stack | A `Stacks` entry in the stage for that environment |
| Jobs that deploy stacks that must go out together | One `Stacks` group |
| `needs: [deploy-dev]` | `from: [dev]` on the next stage |
| `environment: production` with required reviewers | `when: delivery.approval({ approvers: [...] })` (ask for the Pulumi names) |
| An environment wait timer or a manual "go" | `when: delivery.manual({ description: "..." })` |
| A test or smoke step after a deploy | A `Job` in the same stage |
| `pulumi preview` on pull requests | Not a Delivery feature. Keep that workflow, or use Pulumi's PR previews. |
| Build steps that produce an image or package | Keep them in CI, or run them as a `Job`; pass the result to stacks in `config` or `environment` |
| Setup steps before `pulumi up` (build, code generation) | `preRunCommands` of the `Stacks` entry |
| A pinned Pulumi CLI or language version, `container:` | `image` of the `Stacks` entry or `Job` |
| `secrets.*` for cloud credentials | An ESC environment with OIDC imported in the target stack config, or secret values in the member `environment` |
| `on.schedule` | No equivalent in the preview. Keep the scheduled workflow. |
| `workflow_dispatch` | The "Run pipeline" button or a dispatch through the API, see `operating.md` (no inputs in the preview) |
| Matrix over environments | A loop or helper function that creates one stage per environment |

GitLab CI and Azure Pipelines map the same way: stages to `Stage`, `needs`/`dependsOn` to `from`, manual jobs and approvals to `manual()` or `approval()`, `rules:changes` / path filters to `trigger.paths`.

### Pulumi Deployments settings

| Deployment settings | Delivery |
| --- | --- |
| `sourceContext.git` repository and branch | A repository source |
| `sourceContext.git.repoDir` | `directory` of the `Stacks` entry |
| Push to deploy, path filters | `trigger` on the source |
| Pre-run commands | `preRunCommands` of the `Stacks` entry |
| Executor image | `image` of the `Stacks` entry |
| Environment variables | `environment` of the `Stacks` entry (secrets stay secret) |
| `operationContext.oidc` (AWS, Azure, GCP) | An ESC environment with OIDC login, imported in `Pulumi.<stack>.yaml`. Delivery does not read Deployment settings. |
| Agent pool | Not available in the preview. Stop and tell the user. |

## 3. Check what does not migrate

Tell the user before you start if the existing pipeline needs any of these:

- Schedules, ESC-triggered deployments or dispatch inputs.
- Windows runners or self-hosted agent pools.
- Policy packs applied by the pipeline itself (target stacks keep their own policy groups).
- Custom VCS or a forge without a Pulumi integration.
- `http()` checks against external systems (not available in the preview).

## 4. Cut over

1. Write and register the delivery pipeline (`authoring.md`). Start with only the first stage if the user wants a gradual move.
2. Disable the old deploy path for the same stacks so two systems do not update a stack at once: remove or guard the CI deploy jobs, and turn off push-to-deploy in Deployment settings (`pulumi api PatchDeploymentSettings` or the console). Ask the user before you change either.
3. Keep CI jobs that Delivery does not replace (PR checks, builds, schedules).
4. Push a commit and confirm the run reaches every stage.

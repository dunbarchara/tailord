# GitHub Actions Workflows

## Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | PR, push | Lint, test, audit (backend + frontend + infra) |
| `deploy-azure.yml` | Push to `main`, manual | Build images, deploy to staging + prod, deploy Grafana dashboards (if enabled) |
| `observability.yml` | Manual (`workflow_dispatch`) | Push dashboard JSON files to a running Grafana instance |
| `eval-live.yml` | Manual | Live LLM evaluation against prod |
| `deploy-aws.yml` | — | Inactive legacy; kept for reference |

---

## Observability — Grafana on demand

Grafana is **not permanently running**. Log Analytics, Managed Prometheus, and Azure Monitor alerts run continuously regardless. Historical data is preserved while Grafana is down.

Grafana's lifecycle (create, destroy, and all IAM) is managed entirely by **Terraform locally**. The GitHub Actions workflow only handles dashboard content deployment.

This keeps IAM in one place (Terraform), avoids granting the CI service principal elevated role-assignment permissions, and means there is no disjointed CI → local → CI sequence.

### Spin up

```bash
# 1. Create Grafana + all IAM (Grafana Admin for you and the CI SP,
#    Monitoring Reader + Log Analytics Reader for the Grafana system identity)
export TF_VAR_grafana_enabled=true
source .env.azure && terraform apply

# 2. Configure PostgreSQL datasources, publish GRAFANA_URL as a repo variable,
#    and set GRAFANA_ENABLED=true so CI deploys dashboards on future pushes
cd infra/providers/azure && bash scripts/bootstrap-grafana.sh
```

Dashboards are deployed as part of bootstrap (step 2 above). To redeploy at any time:

```bash
cd infra/providers/azure && bash scripts/deploy-dashboards.sh
```

Or via GitHub Actions without a code change:

**Actions → Observability — Grafana lifecycle → Run workflow**

### Spin down

```bash
export TF_VAR_grafana_enabled=false
source .env.azure && terraform apply
```

Terraform destroys the Grafana instance and all associated role assignments in one step. No state surgery needed.

Update the repo variable so CI skips the dashboard deploy step on future pushes:

```bash
gh variable set GRAFANA_ENABLED --body "false"
```

### Push dashboards to an existing instance

**Actions → Observability — Grafana lifecycle → Run workflow → `deploy-dashboards`**

Useful when dashboard JSON files change and you want to push immediately rather than waiting for a full prod deploy pipeline.

---

## Why not CI-managed Grafana lifecycle?

The GitHub Actions service principal (`tailord-github-actions`) has `Contributor` on the resource group. `Contributor` does not include `Microsoft.Authorization/roleAssignments/write`, which means CI cannot assign the IAM roles Grafana needs to function (Grafana Admin for user and CI SP access, Monitoring Reader and Log Analytics Reader for the Grafana system identity). Workarounds (granting the SP `User Access Administrator`, or splitting create from IAM into separate CI → local → CI steps) add complexity without meaningful benefit at the current scale. Terraform already handles all IAM for the rest of the infrastructure; Grafana follows the same pattern.

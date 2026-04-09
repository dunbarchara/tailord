# Infrastructure Improvements — Azure CI/CD Overhaul

*April 2026*

---

## What Was Done

A significant infrastructure refactor was completed to fix a staging smoke test 503, and
expanded into a full prod/staging isolation and blue-green deployment implementation.

### Root cause of the 503

Staging and prod shared a single set of Container Apps. The staging CI job updated the shared
app's image and tried to route traffic to the new revision via an internal label URL
(`{app}---{label}.internal.{env-domain}`). Azure Container Apps does not support label-based
routing for internally-scoped apps — only external apps support label URLs. The smoke test
hit the label URL and received a 503.

### Changes made

**Separate Container Apps per environment**

Replaced two shared Container Apps (`tailord-backend`, `tailord-frontend`) with four dedicated
apps: `tailord-backend-prod`, `tailord-frontend-prod`, `tailord-backend-staging`,
`tailord-frontend-staging`. Eliminates the label routing problem entirely — each environment
has its own app with its own internal FQDN.

**Separate Container App Environments**

Created `tailord-env-prod` and `tailord-env-staging`. Apps in different environments cannot
reach each other over the internal network. Staging backend cannot accidentally reach prod
internal services.

**Blue-green deployment for all four apps**

All apps use `revision_mode = "Multiple"` with `lifecycle { ignore_changes }` on image and
traffic weight. The deploy workflow:
1. Creates a new revision via `az containerapp update --image`
2. Waits up to 4 minutes for the revision to reach `Running` state
3. Shifts 100% traffic to the new revision
4. Deactivates all previous active revisions

**Separate storage accounts per environment**

Replaced one shared storage account with `tailordprod` (prod) and `tailordstaging` (staging).
CORS rules are scoped per environment: prod allows `tailord.app` only; staging allows
`staging.tailord.app` and `localhost:3000`.

**Separate PostgreSQL credentials per environment**

The PostgreSQL server (`tailord-pg`) is shared but has two isolated databases (`tailord_prod`,
`tailord_staging`) with dedicated limited users. Each user can only connect to its own
database. Both users have DDL rights (CREATE ON SCHEMA, ALL ON SEQUENCES) so Alembic
migrations run under the same credential as the app — no admin user at runtime.

**`staging-azure` GitHub environment**

Added a second GitHub environment (`staging-azure`) alongside `production-azure`. Staging
deploys use `staging-azure` OIDC credentials. Both environments share the same service
principal but have independent federated credentials, allowing separate protection rules.

**Naming conventions**

All resources use `{project}-{component}-{env}` or `{project}-{env}` suffixes:
- Container Apps: `tailord-{backend,frontend}-{prod,staging}`
- Container App Environments: `tailord-env-{prod,staging}`
- Storage accounts: `tailord{prod,staging}`
- PostgreSQL server: `tailord-pg` (renamed from `tailord-db`)
- Managed identity: `tailord-id` (renamed from `tailord-apps-identity`)

**Local development storage**

Added Azurite (Azure Storage emulator) to `backend/docker-compose.yml` so local dev uses
an isolated local storage instance instead of any cloud account.

**Bootstrap documentation**

`BOOTSTRAP.md` rewritten to cover: Terraform state backend, OIDC service principal setup
(both federated credentials), required Terraform variables, AI Foundry model deployment,
PostgreSQL user setup with correct grants, custom domain and TLS cert binding per environment,
and an infrastructure isolation reference table.

---

## Known Security Debt

### PostgreSQL public network access

**Issue:** The PostgreSQL server has a public endpoint. The firewall rule uses the
`0.0.0.0/0.0.0.0` magic range ("allow Azure services"), which permits connections from any
Azure-hosted IP — including services in other tenants.

**Current mitigations:** TLS enforced, strong passwords, limited users scoped to their own
database only.

**Proper fix:** VNet integration. Steps required:
1. Create a VNet with a delegated subnet for PostgreSQL and a separate subnet for Container Apps
2. Recreate the Container App Environments with `infrastructure_subnet_id` pointing at the
   Container Apps subnet
3. Deploy PostgreSQL with `delegated_subnet_id` and `private_dns_zone_id` — no public endpoint
4. Remove the `azure_services` firewall rule

**Why deferred:** Recreating the Container App Environments is destructive (all apps must be
recreated). Adds ~$10-15/month for VNet gateway resources. Non-trivial Terraform surface area.
Acceptable risk at current scale given credential isolation already in place.

**Priority:** Revisit before handling sensitive user data at volume or before any compliance
requirement arises.

---

## Remaining Work

- [ ] Set up `staging-azure` GitHub environment with the same OIDC secrets as `production-azure`
- [ ] Run `terraform apply` with new variable set (`db_prod_password`, `db_staging_password`)
- [ ] Execute PostgreSQL user bootstrap SQL (see BOOTSTRAP.md step 4)
- [ ] Bind TLS certs for `tailord.app` (CLI) and `staging.tailord.app` (portal)
- [ ] Restore Cloudflare CNAMEs to proxied after cert binding
- [ ] Trigger first CI deploy to replace placeholder images with real app images
- [ ] VNet integration (deferred — see security debt above)

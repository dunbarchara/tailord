# Azure Bootstrap Guide

Steps required when provisioning the Azure environment from scratch.
These are one-time manual steps — they are not encoded in Terraform or CI.

---

## 1. Terraform state backend (before first `terraform init`)

The state backend (`tailord-tfstate` resource group, `tailordtfstate` storage account,
`tfstate` container) must exist before running Terraform. Create it manually:

```bash
az group create --name tailord-tfstate --location canadacentral \
  --tags project=tailord managed_by=manual

az storage account create --name tailordtfstate --resource-group tailord-tfstate --sku Standard_LRS \
  --tags project=tailord managed_by=manual

az storage container create --name tfstate --account-name tailordtfstate
```

Note: storage containers don't support tags — only the account does.

---

## 2. GitHub Actions service principal (OIDC)

Terraform manages the SP's *role assignments* but not the SP itself.
Create it once, then pass its object ID to Terraform via `github_actions_sp_object_id`.

```bash
# Create the app registration
az ad app create --display-name "tailord-github-actions"

# Create the service principal from the app
az ad sp create --id <app-id-from-above>

# Add federated credential for the production-azure GitHub environment
az ad app federated-credential create \
  --id <app-id> \
  --parameters '{
    "name": "github-actions-production",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:dunbarchara/tailord:environment:production-azure",
    "audiences": ["api://AzureADTokenExchange"]
  }'

# Add federated credential for the staging-azure GitHub environment
az ad app federated-credential create \
  --id <app-id> \
  --parameters '{
    "name": "github-actions-staging",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:dunbarchara/tailord:environment:staging-azure",
    "audiences": ["api://AzureADTokenExchange"]
  }'

# Get the object ID needed for Terraform
az ad sp show --id <app-id> --query id -o tsv
```

Then add these three secrets to **both** GitHub environments (`production-azure` and `staging-azure`):

| Secret | Value |
|--------|-------|
| `AZURE_CLIENT_ID` | App (client) ID of the app registration |
| `AZURE_TENANT_ID` | Your Azure tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Your Azure subscription ID |

Both environments currently use the same service principal. The separate environments exist
so you can set independent protection rules (e.g. required reviewers on production only)
and swap to separate SPs in the future without changing the workflow.

---

## 3. Terraform apply

### Secret architecture

Application secrets (NextAuth, Google OAuth, Notion, API keys, database URLs, GitHub App private
keys) live in Azure Key Vault and are **never passed as Terraform variables**. Terraform reads
them via `data "azurerm_key_vault_secret"` blocks — it wires the KV secret URIs into Container
Apps but never holds the values itself.

This means the bootstrap sequence for a fresh environment is two passes:

**Pass 1 — create infrastructure including the vault:**

```bash
terraform init
terraform apply \
  -target=azurerm_key_vault.tailord \
  -target=azurerm_role_assignment.kv_secrets_officer \
  -target=azurerm_role_assignment.kv_secrets_user
```

**Manually upload all secrets to Key Vault** (see step 3a below).

**Pass 2 — full apply:**

```bash
terraform apply
```

All data sources now resolve. Container Apps are created referencing the pre-populated secrets.

### Variables required at apply time

Only non-secret identifiers and bootstrap credentials are passed as Terraform variables:

| Variable | Type | Notes |
|----------|------|-------|
| `subscription_id` | Identifier | Azure subscription ID |
| `github_actions_sp_object_id` | Identifier | Object ID from step 2 |
| `log_level` | Config | Default: `INFO` |
| `cloudflare_zone_id` | Identifier | Cloudflare zone ID for tailord.app |
| `github_app_id_prod` | Identifier | GitHub App ID for the prod Tailord app |
| `github_app_installation_id_prod` | Identifier | Installation ID for the prod GitHub App |
| `github_app_id_staging` | Identifier | GitHub App ID for the staging Tailord app |
| `github_app_installation_id_staging` | Identifier | Installation ID for the staging GitHub App |
| `db_password` | Bootstrap only | PostgreSQL **admin** password — used once at server creation. Ignored by Terraform on subsequent applies (`lifecycle.ignore_changes`). Source from 1Password; omit for routine applies. |

These live in a local `.env` file (gitignored):

```bash
export TF_VAR_subscription_id="..."
export TF_VAR_github_actions_sp_object_id="..."
export TF_VAR_log_level="INFO"
export TF_VAR_cloudflare_zone_id="..."
export TF_VAR_github_app_id_prod="..."
export TF_VAR_github_app_installation_id_prod="..."
export TF_VAR_github_app_id_staging="..."
export TF_VAR_github_app_installation_id_staging="..."
export TF_VAR_db_password="..."          # only needed when creating/recreating the PG server
export CLOUDFLARE_API_TOKEN="..."        # Cloudflare provider credential — not a TF_VAR

source .env && terraform apply
```

**Intended upgrade path — 1Password CLI:**
Store the above values as 1Password items, then replace the `.env` file with a `.env.1p`
reference file (safe to commit — contains references, not secrets):

```bash
# .env.1p (committable — no secrets)
TF_VAR_subscription_id=op://tailord/terraform/subscription_id
CLOUDFLARE_API_TOKEN=op://tailord/terraform/cloudflare_api_token
# ... etc

op run --env-file=.env.1p -- terraform apply
```

**Long-term: GitHub Actions**
PR-level `terraform plan` output, approval gates before apply, and full audit trail.
Worth adopting once there are users depending on the infrastructure.

Note: `llm_api_key` and `llm_base_url` are not input variables — Terraform derives them
directly from the AI Foundry account it creates (`primary_access_key` and `endpoint`).

### Step 3a — Upload secrets to Key Vault

After Pass 1 creates the vault, upload all application secrets before running Pass 2.
Values come from your password manager (1Password). Never store them on disk.

```bash
# Get the PostgreSQL FQDN (needed to construct DATABASE_URLs)
PGFQDN=$(az postgres flexible-server show \
  --resource-group tailord --name tailord-pg \
  --query fullyQualifiedDomainName -o tsv)

# Application secrets
az keyvault secret set --vault-name tailord-kv --name prod-nextauth-secret      --value "<openssl rand -base64 32>"
az keyvault secret set --vault-name tailord-kv --name staging-nextauth-secret   --value "<openssl rand -base64 32>"
az keyvault secret set --vault-name tailord-kv --name prod-api-key              --value "<openssl rand -hex 32>"
az keyvault secret set --vault-name tailord-kv --name staging-api-key           --value "<openssl rand -hex 32>"
az keyvault secret set --vault-name tailord-kv --name prod-google-client-id     --value "<from Google Cloud Console>"
az keyvault secret set --vault-name tailord-kv --name staging-google-client-id  --value "<from Google Cloud Console>"
az keyvault secret set --vault-name tailord-kv --name prod-google-client-secret --value "<from Google Cloud Console>"
az keyvault secret set --vault-name tailord-kv --name staging-google-client-secret --value "<from Google Cloud Console>"
az keyvault secret set --vault-name tailord-kv --name prod-notion-client-id     --value "<from Notion developer dashboard>"
az keyvault secret set --vault-name tailord-kv --name staging-notion-client-id  --value "<from Notion developer dashboard>"
az keyvault secret set --vault-name tailord-kv --name prod-notion-client-secret --value "<from Notion developer dashboard>"
az keyvault secret set --vault-name tailord-kv --name staging-notion-client-secret --value "<from Notion developer dashboard>"

# Database connection strings (use the app user passwords chosen in step 4)
az keyvault secret set --vault-name tailord-kv --name prod-database-url \
  --value "postgresql+psycopg://tailord_prod:<prod_app_password>@${PGFQDN}/tailord_prod"
az keyvault secret set --vault-name tailord-kv --name staging-database-url \
  --value "postgresql+psycopg://tailord_staging:<staging_app_password>@${PGFQDN}/tailord_staging"

# GitHub App private keys (PEM content)
az keyvault secret set --vault-name tailord-kv --name prod-github-app-private-key    --file /path/to/prod.pem
az keyvault secret set --vault-name tailord-kv --name staging-github-app-private-key --file /path/to/staging.pem
```

After uploading, the `.pem` files can be deleted — Key Vault is the source of truth.

To update a secret after initial bootstrap (e.g. rotating a credential):
```bash
az keyvault secret set --vault-name tailord-kv --name <secret-name> --value "<new-value>"
# Then restart the affected Container App revision to pick up the new value
```

### Step 3a: Deploy Phi-4-mini in AI Foundry (manual — model deployments not in Terraform provider)

The AI Foundry account (`tailord-foundry`) is created by `terraform apply` in step 3.
Terraform also wires its key into Key Vault and its endpoint URL into the backend Container Apps —
no manual key retrieval or second apply needed.

The only manual step is deploying the model itself, since pay-per-token serverless deployments
are not yet supported by the `azurerm` provider:

1. Go to [ai.azure.com](https://ai.azure.com) → select the `tailord-foundry` resource
2. Open **Model catalog** → search for **Phi-4-mini-instruct** → **Deploy as serverless**
3. Name the deployment **`phi-4-mini`** (must match the `llm_model` Terraform variable)

The deployment spec is tracked at `infra/providers/azure/endpoints/phi4-mini.yaml` — this file
is the source of truth for which model is deployed.

**Switching models in the future:**
1. Add a new spec to `infra/providers/azure/endpoints/`
2. Deploy it via the portal with the new deployment name
3. Update `llm_model` in Terraform vars and run `terraform apply` (updates the Container App env)
4. Delete the old deployment via the portal and remove its spec file

---

## 4. Database user setup (run once after first `terraform apply`)

The PostgreSQL server is created with a single admin user (`tailord`). App connections use
dedicated limited users — `tailord_prod` can only access `tailord_prod`, and `tailord_staging`
can only access `tailord_staging`. Neither can access the other's database.

**Choose passwords** for `tailord_prod` and `tailord_staging` before running step 3a — you
will need them to construct the `prod-database-url` and `staging-database-url` Key Vault
secrets. Store the passwords in 1Password; they are not Terraform variables.

**Add a temporary firewall rule for your IP:**

```bash
MY_IP=$(curl -s https://api.ipify.org)
az postgres flexible-server firewall-rule create \
  --resource-group tailord \
  --name tailord-pg \
  --rule-name allow-my-ip \
  --start-ip-address $MY_IP \
  --end-ip-address $MY_IP
```

**Connect and create the limited users:**

```bash
psql "host=tailord-pg.postgres.database.azure.com port=5432 dbname=postgres \
  user=tailord password=<admin-password> sslmode=require"
```

```sql
-- Create app users (no superuser, no createdb, no createrole)
CREATE USER tailord_prod WITH PASSWORD '<db_prod_password>';
CREATE USER tailord_staging WITH PASSWORD '<db_staging_password>';

-- Prod user: connect to tailord_prod only
GRANT CONNECT ON DATABASE tailord_prod TO tailord_prod;

-- Staging user: connect to tailord_staging only
GRANT CONNECT ON DATABASE tailord_staging TO tailord_staging;
```

Then connect to each database and grant schema permissions.

The app users run Alembic migrations on startup (`entrypoint.sh` calls `alembic upgrade head`),
so they need DDL rights (CREATE, ALTER, DROP) in addition to DML. The admin user (`tailord`)
is only used for this one-time bootstrap — not at runtime.

```bash
psql "host=tailord-pg.postgres.database.azure.com port=5432 dbname=tailord_prod \
  user=tailord password=<admin-password> sslmode=require"
```

```sql
GRANT USAGE, CREATE ON SCHEMA public TO tailord_prod;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO tailord_prod;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO tailord_prod;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO tailord_prod;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT ALL ON SEQUENCES TO tailord_prod;
```

```bash
psql "host=tailord-pg.postgres.database.azure.com port=5432 dbname=tailord_staging \
  user=tailord password=<admin-password> sslmode=require"
```

```sql
GRANT USAGE, CREATE ON SCHEMA public TO tailord_staging;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO tailord_staging;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO tailord_staging;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO tailord_staging;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT ALL ON SEQUENCES TO tailord_staging;
```

**Remove the temporary firewall rule:**

```bash
az postgres flexible-server firewall-rule delete \
  --resource-group tailord \
  --name tailord-pg \
  --rule-name allow-my-ip \
  --yes
```

Note: Alembic migrations run as the app user (`tailord_prod` / `tailord_staging`) via
`entrypoint.sh` on container startup — the same credential the app uses at runtime.
The admin user (`tailord`) is not used at runtime.

---

## 5. Custom domain and TLS certificates

After `terraform apply` creates the Container Apps, bind Azure-managed TLS certs to the
custom domains. See `custom-domain.tf` for the exact CLI commands. The process for each domain:

1. Temporarily set the Cloudflare CNAME to **DNS Only** (grey cloud) for validation
2. Run `az containerapp hostname add` and `az containerapp hostname bind`
3. Wait for the cert to be issued (status: Succeeded)
4. Restore the Cloudflare CNAME to **Proxied** and SSL/TLS mode to **Full (Strict)**

| Domain | App | Environment |
|--------|-----|-------------|
| `tailord.app` | `tailord-frontend-prod` | `tailord-env-prod` |
| `staging.tailord.app` | `tailord-frontend-staging` | `tailord-env-staging` |

---

## 6. Database bootstrap (first deploy only)

### 6a. Enable pgvector extension

The `pgvector` extension must be created by an admin user before the first deploy.
Azure PostgreSQL treats it as an "untrusted" extension — the app DB users (`tailord_prod`,
`tailord_staging`) lack the `azure_pg_admin` privilege required to create it.

The extension is already **allow-listed** via Terraform (`azure.extensions = VECTOR`). You
just need to create it once in each database while connected as the admin user (`tailord`).

Add a temporary firewall rule for your IP (same pattern as step 4), then run:

```bash
az postgres flexible-server execute \
  --name tailord-pg \
  --admin-user tailord \
  --admin-password <admin-password> \
  --database-name tailord_staging \
  --querytext "CREATE EXTENSION IF NOT EXISTS vector;"

az postgres flexible-server execute \
  --name tailord-pg \
  --admin-user tailord \
  --admin-password <admin-password> \
  --database-name tailord_prod \
  --querytext "CREATE EXTENSION IF NOT EXISTS vector;"
```

Can also connect to the databases and run the queries directly via Azure Cloud Shell.

This is a **one-time step** per environment. Once the extension exists it never needs
creating again — Alembic migrations run as the app user and do not attempt to create it.

### 6b. Run migrations

No manual steps required. The entrypoint runs `alembic upgrade head` on every container
startup. On a fresh database this creates all tables from the single initial migration.
On an existing database it is a no-op.

---

## 7. Bootstrap admin accounts (run once after first deploy)

After the first deploy, all new sign-ins land on `/pending` by default and no accounts have
admin access. Bootstrap founder accounts by signing in once (to create the user row), then
setting `is_admin = true` directly via psql.

Add a temporary firewall rule for your IP (see step 4 pattern), then:

```bash
psql "host=tailord-pg.postgres.database.azure.com port=5432 dbname=tailord_prod \
  user=tailord password=<admin-password> sslmode=require"
```

```sql
-- Grant admin access and approve in one step
UPDATE users SET is_admin = true, status = 'approved' WHERE email = 'your@email.com';
```

Repeat for each founder account. Remove the temporary firewall rule when done.

This is the **only** time direct DB access is needed for user management. All subsequent
approvals and revocations are handled via the `/admin` page, which requires `is_admin = true`
on the authenticated user's DB record and is protected by Google OAuth (including MFA).

Note: `dev_approve.py` (local only, gitignored) can still be used to approve accounts in
local development where the admin page is not needed.

---

## Infrastructure isolation reference

What is shared between prod and staging, and what is fully isolated:

| Resource | Shared / Isolated | Notes |
|---|---|---|
| Azure Resource Group | Shared | All resources in `tailord` |
| GitHub Actions SP | Shared | Same OIDC SP; isolated via separate GitHub environments with separate federated credentials |
| GitHub Environments | **Isolated** | `production-azure` vs `staging-azure` — independent protection rules and secrets |
| Container App Environments | **Isolated** | `tailord-env-prod` vs `tailord-env-staging`; staging apps cannot reach prod internal services at the network layer |
| Container Apps | **Isolated** | 4 separate apps: `tailord-{backend,frontend}-{prod,staging}` |
| Container Registry (ACR) | Shared | Same registry; both environments pull from the same image tags |
| PostgreSQL Server | Shared | One `tailord-pg` |
| PostgreSQL Databases | **Isolated** | `tailord_prod` vs `tailord_staging` |
| PostgreSQL Credentials | **Isolated** | `tailord_prod` user (prod db only) vs `tailord_staging` user (staging db only) |
| Storage Accounts | **Isolated** | `tailordprod` (prod only) vs `tailordstaging` (staging only); CORS scoped per environment |
| Storage Containers | **Isolated** | `uploads` within each account |
| Key Vault | Shared | One `tailord-kv`; secrets namespaced `prod-*` vs `staging-*` |
| Managed Identity | Shared | One `tailord-id` with KV Secrets User role on the shared vault |
| AI Foundry / LLM | Shared | Same model endpoint and API key for both environments |
| Log Analytics Workspace | Shared | Apps emit `ENVIRONMENT=production` or `ENVIRONMENT=staging` for log filtering |
| Custom Domains | **Isolated** | `tailord.app` (prod) vs `staging.tailord.app` (staging) |
| Cloudflare DNS | Shared | Same zone; separate CNAME records per environment |

---

## Known security debt

### PostgreSQL public network access

The PostgreSQL server uses a public endpoint with a firewall rule that allows all Azure-hosted
IPs (the `0.0.0.0/0.0.0.0` magic range). This includes Azure services from other tenants —
it is not scoped to this subscription.

**Mitigations in place:** TLS required, strong passwords, limited DB users scoped to their own
database only (`tailord_prod` cannot access `tailord_staging` and vice versa).

**Proper fix:** VNet integration — put the PostgreSQL server on a private subnet and configure
the Container App Environments with a custom VNet so they reach the DB over a private endpoint
with no public exposure. This requires recreating the Container App Environments (destructive)
and is deferred. Tracked in `planning/15-infra-improvements.md`.

---

### Useful commands

Export .env.azure variables before running terraform apply
`export $(grep -vE '^(#|$)' .env.azure | xargs)`

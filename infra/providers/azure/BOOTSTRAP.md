# Azure Bootstrap Guide

Steps required when provisioning the Azure environment from scratch.
These are one-time manual steps — they are not encoded in Terraform or CI.

---

## 1. Terraform state backend (before first `terraform init`)

The state backend (`tailord-tfstate` resource group, `tailordtfstate` storage account,
`tfstate` container) must exist before running Terraform. Create it manually:

```bash
az group create --name tailord-tfstate --location canadacentral
az storage account create --name tailordtfstate --resource-group tailord-tfstate --sku Standard_LRS
az storage container create --name tfstate --account-name tailordtfstate
```

---

## 2. GitHub Actions service principal (OIDC)

Terraform manages the SP's *role assignments* but not the SP itself.
Create it once, then pass its object ID to Terraform via `github_actions_sp_object_id`.

```bash
# Create the app registration
az ad app create --display-name "tailord-github-actions"

# Create the service principal from the app
az ad sp create --id <app-id-from-above>

# Add federated credential for GitHub Actions OIDC
az ad app federated-credential create \
  --id <app-id> \
  --parameters '{
    "name": "github-actions",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:dunbarchara/tailord:environment:production-azure",
    "audiences": ["api://AzureADTokenExchange"]
  }'

# Get the object ID needed for Terraform
az ad sp show --id <app-id> --query id -o tsv
```

Then add these three secrets to the GitHub environment `production-azure`:

| Secret | Value |
|--------|-------|
| `AZURE_CLIENT_ID` | App (client) ID of the app registration |
| `AZURE_TENANT_ID` | Your Azure tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Your Azure subscription ID |

---

## 3. Terraform apply

From `infra/providers/azure/`, run:

```bash
terraform init
terraform apply
```

Required variables (pass via `-var` flags or a `terraform.tfvars` file — never commit the latter):

| Variable | Notes |
|----------|-------|
| `subscription_id` | Azure subscription ID |
| `github_actions_sp_object_id` | Object ID from step 2 |
| `db_password` | PostgreSQL admin password |
| `api_key` | Backend X-API-Key |
| `nextauth_secret` | NextAuth secret (`openssl rand -base64 32`) |
| `google_client_id` | Google OAuth client ID |
| `google_client_secret` | Google OAuth client secret |
| `llm_api_key` | LLM provider API key |
| `cloudflare_zone_id` | Cloudflare zone ID for tailord.app |
| `llm_model` | e.g. `gpt-4o-mini` (has default) |

---

## 4. Database bootstrap (first deploy only)

The backend runs `alembic upgrade head` on every startup, which handles future migrations
automatically. However, on a **fresh database** the historical migrations will fail because
they reference tables that never existed (e.g. renaming `resumes` → `experiences`).

Bootstrap a fresh DB by creating the schema directly from the current models, then stamping
Alembic so it treats all historical migrations as already applied:

```bash
# Temporarily add your local IP to the PostgreSQL firewall
YOUR_IP=$(curl -s https://api.ipify.org)
az postgres flexible-server firewall-rule create \
  --resource-group tailord \
  --name tailord-db \
  --rule-name local-bootstrap \
  --start-ip-address $YOUR_IP \
  --end-ip-address $YOUR_IP

export DATABASE_URL="postgresql+psycopg://tailord:<db_password>@tailord-db.postgres.database.azure.com/tailord"
cd backend

# Create all tables from current SQLAlchemy models
uv run python init_db.py

# Mark all migrations as applied (skips historical ones that don't apply to a fresh DB)
uv run alembic stamp head

# Remove the temporary firewall rule
az postgres flexible-server firewall-rule delete \
  --resource-group tailord \
  --name tailord-db \
  --rule-name local-bootstrap \
  --yes
```

After this, future `alembic upgrade head` calls will only run genuinely new migrations.

---

## 5. Approve initial users

After the first deploy, all new sign-ins land on `/pending` by default.
Approve dev/admin accounts via `backend/dev_approve.py` (local only, gitignored):

```bash
cd backend && uv run python dev_approve.py your@email.com
```

Or directly via psql with a temporary firewall rule (see step 4 pattern):

```sql
UPDATE users SET status = 'approved' WHERE email = 'your@email.com';
```

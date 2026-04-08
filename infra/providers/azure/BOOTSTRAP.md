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
| `cloudflare_zone_id` | Cloudflare zone ID for tailord.app |
| `llm_model` | Model deployment name (default: `phi-4-mini`, must match the deployment name created in step 3a) |

Note: `llm_api_key` and `llm_base_url` are no longer input variables — Terraform derives them
directly from the AI Foundry account it creates (`primary_access_key` and `endpoint`).

### Step 3a: Deploy Phi-4-mini in AI Foundry (manual — model deployments not in Terraform provider)

The AI Foundry account (`tailord-foundry`) is created by `terraform apply` in step 3.
Terraform also wires its key into Key Vault and its endpoint URL into the backend Container App —
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

## 4. Database bootstrap (first deploy only)

No manual steps required. The entrypoint runs `alembic upgrade head` on every container
startup. On a fresh database this creates all tables from the single initial migration.
On an existing database it is a no-op.

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

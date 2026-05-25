---
name: Secret Rotation — April 2026
description: Pre-public-repo secret rotation checklist with service impact reference
type: project
---

# Secret Rotation — April 2026

Triggered by: repo going public. Rotate all secrets regardless of gitleaks scan outcome — a secret in a `.env.local` file that was briefly staged and then unstaged will not appear in git history.

**Rule:** After rotation, update every location listed in the "Update locations" column before restarting any service. A partially-updated rotation (e.g. Key Vault updated but `terraform.tfvars` local env not) will break the next `terraform apply`.

---

## Rotation Table

| Secret | Variable name | Environment | Service impact during rotation | Where to rotate | Update locations |
|--------|--------------|-------------|-------------------------------|-----------------|-----------------|
| NextAuth session signing key | `NEXTAUTH_SECRET` | Prod + Staging (separate values) | **All active sessions invalidated** — users are signed out immediately and must re-authenticate via Google | `openssl rand -base64 32` | Azure Key Vault (`prod-nextauth-secret`, `staging-nextauth-secret`) → Container App revision restart |
| Google OAuth client secret | `GOOGLE_CLIENT_SECRET` | Prod + Staging (shared credential) | **No downtime** — Google accepts old + new secret briefly during rollover; sign-ins unaffected if Key Vault is updated before the old secret expires | Google Cloud Console → Credentials → OAuth client → Edit → Add new secret | Azure Key Vault (`prod-google-client-secret`, `staging-google-client-secret`) → local `.env` |
| Frontend ↔ backend API key | `API_KEY` / `BACKEND_API_KEY` | Prod | **Brief 401 errors** between frontend and backend during the gap between frontend restart and backend restart — rotate backend first, then frontend | Generate: `openssl rand -hex 32` | Azure Key Vault (`prod-api-key`) → Container App revision restart (backend first, then frontend) |
| Frontend ↔ backend API key | `API_KEY` / `BACKEND_API_KEY` | Staging | Same as prod but isolated | Same method | Azure Key Vault (`staging-api-key`) → Container App revision restart |
| PostgreSQL admin password | `db_password` / `TF_VAR_db_password` | Shared (server-level) | **No app impact** — app connections use `tailord_prod` / `tailord_staging` users, not the admin account; admin password is only used for bootstrap/maintenance | Azure Portal → PostgreSQL Flexible Server → Settings → Reset password, or `az postgres flexible-server update --admin-password` | Local `.env` (`TF_VAR_db_password`) → Azure Key Vault (if stored) |
| PostgreSQL prod app user password | `db_prod_password` / `TF_VAR_db_prod_password` | Prod | **Prod backend unavailable** until connection string is updated and container restarts | `psql` → `ALTER USER tailord_prod PASSWORD '...'` | Azure Key Vault (`prod-database-url` — full connection string must be reconstructed) → Container App revision restart |
| PostgreSQL staging app user password | `db_staging_password` / `TF_VAR_db_staging_password` | Staging | **Staging backend unavailable** until updated | `psql` → `ALTER USER tailord_staging PASSWORD '...'` | Azure Key Vault (`staging-database-url`) → Container App revision restart |
| LLM API key | `LLM_API_KEY` / `TF_VAR_llm_api_key` | Prod + Staging (shared AI Foundry account) | **All tailoring generation fails** until new key is active in both environments | Azure AI Foundry portal → regenerate primary key (use secondary key as bridge — see note below) | Azure Key Vault (`prod-llm-api-key`, `staging-llm-api-key`) → Container App revision restart |
| Azure Blob Storage connection string — prod | `AZURE_STORAGE_CONNECTION_STRING` | Prod | **Resume uploads and file reads fail** during rotation window | Azure Portal → Storage account `tailordprod` → Access keys → Rotate key 1 | Azure Key Vault (`prod-storage-connection-string`) → Container App revision restart |
| Azure Blob Storage connection string — staging | `AZURE_STORAGE_CONNECTION_STRING` | Staging | **Staging uploads fail** during rotation window | Azure Portal → Storage account `tailordstaging` → Access keys → Rotate key 1 | Azure Key Vault (`staging-storage-connection-string`) → Container App revision restart |
| Notion OAuth client secret | `NOTION_CLIENT_SECRET` / `TF_VAR_notion_client_secret` | Prod + Staging (shared Notion app) | **Notion OAuth connect flow breaks** for new connections; existing connected users with stored access tokens are unaffected until their tokens expire | Notion developer dashboard → Edit integration → Regenerate secret | Azure Key Vault (`prod-notion-client-secret`, `staging-notion-client-secret`) → local `.env` |
| Cloudflare API token (Terraform) | — | Infra-only | **No app impact** — only used by `terraform apply`; not in any running service | Cloudflare dashboard → My Profile → API Tokens → Roll | Local `.env` (`CLOUDFLARE_API_TOKEN` or equivalent) |

---

## Items That Don't Require Rotation

| Item | Reason |
|------|--------|
| `GOOGLE_CLIENT_ID` | Public identifier — visible in OAuth flows. Verify it's locked to the expected redirect URIs but no rotation needed. |
| `AZURE_CLIENT_ID` / `AZURE_TENANT_ID` / `AZURE_SUBSCRIPTION_ID` | Identifiers, not secrets. Verify the OIDC federated credential subject is scoped to the correct repo + environments (no wildcard). |
| `cloudflare_zone_id` | Public — visible in Cloudflare dashboard and DNS tooling. Not a secret. |
| Azurite local dev key | Well-known public key shipped with every Azurite install. Not a real secret. |

---

## LLM Key Rotation — Zero-Downtime Approach

Azure AI Foundry provides two keys (primary and secondary) for zero-downtime rotation:

1. Update Key Vault with the **secondary** key → restart containers (they now use secondary)
2. Regenerate the **primary** key in the AI Foundry portal
3. Update Key Vault with the new primary key → restart containers (back to primary)
4. Optionally regenerate secondary to leave both fresh

This prevents any window where all generation requests fail.

---

## Checklist

### Auth / OAuth
- [ ] `NEXTAUTH_SECRET` (prod)
- [ ] `NEXTAUTH_SECRET` (staging)
- [ ] `GOOGLE_CLIENT_SECRET`
- [ ] Verify `GOOGLE_CLIENT_ID` redirect URIs are locked down

### Frontend ↔ Backend
- [ ] `API_KEY` (prod) — backend first, then frontend
- [ ] `API_KEY` (staging)

### Azure OIDC
- [ ] Verify federated credential subject scopes (no wildcard) for `production-azure` environment
- [ ] Verify federated credential subject scopes for `staging-azure` environment

### Database
- [ ] `db_password` (admin — no app impact)
- [ ] `db_prod_password` — update psql + Key Vault + restart prod backend
- [ ] `db_staging_password` — update psql + Key Vault + restart staging backend

### LLM
- [ ] `LLM_API_KEY` — use secondary key bridge (see zero-downtime approach above)

### Storage
- [ ] Azure Blob Storage key — prod (`tailordprod`)
- [ ] Azure Blob Storage key — staging (`tailordstaging`)

### Notion
- [ ] `NOTION_CLIENT_SECRET` — update Key Vault for both environments

### Cloudflare
- [ ] Cloudflare API token (Terraform only — check if one exists locally)

### Post-rotation
- [ ] Run `make check` — confirm backend and frontend start clean
- [ ] Smoke test prod: sign in, generate a tailoring, upload a resume
- [ ] Smoke test staging: same flow
- [ ] Update local `.env` with any rotated values used by `terraform apply`

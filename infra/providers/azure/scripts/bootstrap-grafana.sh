#!/usr/bin/env bash
# bootstrap-grafana.sh — one-time Grafana setup after "terraform apply" or "observability enable"
#
# Automates BOOTSTRAP.md step 8:
#   - Creates a Grafana service account (useful for local Grafana API access)
#   - Publishes GRAFANA_URL as a repository variable for CI
#   - Configures tailord-postgres-prod and tailord-postgres-staging datasources
#
# CI (observability.yml) runs equivalent logic inline using Azure AD OIDC tokens.
# Run this script locally after spinning up Grafana via "terraform apply" or the workflow.
#
# Usage:
#   cd infra/providers/azure && bash scripts/bootstrap-grafana.sh
#
# Override the Grafana URL (skip terraform output):
#   GRAFANA_URL=https://... bash scripts/bootstrap-grafana.sh
#
# Prerequisites: az (logged in), gh (logged in), jq, python3, terraform (init'd + applied)
# Safe to re-run — service account and datasources are upserted, not duplicated.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TF_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── colour helpers ─────────────────────────────────────────────────────────────
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
step()   { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

# ── prerequisites ──────────────────────────────────────────────────────────────
step "Checking prerequisites"

for cmd in az gh jq curl python3 terraform; do
  if ! command -v "$cmd" &>/dev/null; then
    red "Missing required tool: $cmd"
    exit 1
  fi
done

az account show &>/dev/null || { red "Not logged in to Azure CLI. Run: az login"; exit 1; }
gh auth status &>/dev/null  || { red "Not logged in to GitHub CLI. Run: gh auth login"; exit 1; }

green "All prerequisites satisfied."

# ── resolve Grafana URL ────────────────────────────────────────────────────────
step "Resolving Grafana endpoint"

if [[ -n "${GRAFANA_URL:-}" ]]; then
  yellow "Using GRAFANA_URL from environment: $GRAFANA_URL"
else
  GRAFANA_URL=$(terraform -chdir="$TF_DIR" output -raw grafana_endpoint 2>/dev/null) || {
    red "Could not read grafana_endpoint from Terraform state."
    red "Either run 'terraform apply -var grafana_enabled=true' first, or set GRAFANA_URL=... in the environment."
    exit 1
  }
  if [[ -z "$GRAFANA_URL" ]]; then
    red "grafana_endpoint output is empty — Grafana is not enabled (grafana_enabled=false)."
    exit 1
  fi
fi

# Strip trailing slash if present
GRAFANA_URL="${GRAFANA_URL%/}"
green "Grafana URL: $GRAFANA_URL"

# ── publish GRAFANA_URL as a repository variable ───────────────────────────────
step "Publishing GRAFANA_URL as a GitHub repository variable"

GH_REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)

set_gh_variable() {
  local name="$1" value="$2"
  # Try PATCH (update existing), fall back to POST (create new)
  HTTP=$(curl -sf -o /dev/null -w "%{http_code}" -X PATCH \
    -H "Authorization: Bearer $(gh auth token)" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/${GH_REPO}/actions/variables/${name}" \
    -d "{\"name\":\"${name}\",\"value\":\"${value}\"}")
  if [[ "$HTTP" == "204" ]]; then
    green "Updated variable: ${name}"
    return
  fi
  curl -sf -X POST \
    -H "Authorization: Bearer $(gh auth token)" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/${GH_REPO}/actions/variables" \
    -d "{\"name\":\"${name}\",\"value\":\"${value}\"}" > /dev/null
  green "Created variable: ${name}"
}

set_gh_variable "GRAFANA_URL" "$GRAFANA_URL"

# ── Azure AD token for Grafana data-plane API ──────────────────────────────────
step "Acquiring Azure AD token for Grafana API"

GRAFANA_TOKEN=$(az account get-access-token \
  --resource "https://grafana.azure.com" \
  --query accessToken -o tsv)

grafana_api() {
  local method="$1" path="$2"
  shift 2
  curl -s -X "$method" "${GRAFANA_URL}${path}" \
    -H "Authorization: Bearer ${GRAFANA_TOKEN}" \
    -H "Content-Type: application/json" \
    "$@"
}

# Verify auth works
if ! grafana_api GET "/api/health" | jq -e '.database == "ok"' &>/dev/null; then
  red "Grafana API health check failed — token may be invalid or instance not ready."
  exit 1
fi

green "Grafana API reachable and healthy."

# ── service account (for local API access) ────────────────────────────────────
step "Configuring Grafana service account"

SA_NAME="github-actions"

EXISTING_SA=$(grafana_api GET "/api/serviceaccounts/search?query=${SA_NAME}" \
  | jq -r '.serviceAccounts[] | select(.name == "'"$SA_NAME"'") | .id // empty' 2>/dev/null | head -1)

if [[ -n "$EXISTING_SA" ]]; then
  yellow "Service account '${SA_NAME}' already exists (id=${EXISTING_SA}) — skipping creation."
  SA_ID="$EXISTING_SA"
else
  SA_RESPONSE=$(grafana_api POST "/api/serviceaccounts" \
    -d "{\"name\":\"${SA_NAME}\",\"role\":\"Admin\"}")
  SA_ID=$(echo "$SA_RESPONSE" | jq -r '.id')
  if [[ -z "$SA_ID" || "$SA_ID" == "null" ]]; then
    red "Failed to create service account. Response:"
    echo "$SA_RESPONSE"
    exit 1
  fi
  green "Created service account '${SA_NAME}' (id=${SA_ID})."
fi

# Note: CI workflows use Azure AD OIDC tokens to authenticate to Grafana, not this
# service account token. The token below is for local API access only — keep it in
# your password manager if you need it, or generate a new one next time.
TOKEN_NAME="local-$(date +%Y%m%d-%H%M%S)"
TOKEN_RESPONSE=$(grafana_api POST "/api/serviceaccounts/${SA_ID}/tokens" \
  -d "{\"name\":\"${TOKEN_NAME}\"}")
SA_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.key // empty')

if [[ -n "$SA_TOKEN" ]]; then
  green "Created local service account token '${TOKEN_NAME}'."
  yellow "Save this token in your password manager if needed for local Grafana API access:"
  echo "$SA_TOKEN"
else
  yellow "Could not create token (may already exist for today). Generate one manually from the Grafana UI if needed."
fi

# ── PostgreSQL datasources ─────────────────────────────────────────────────────
step "Configuring PostgreSQL datasources"

PG_FQDN=$(az postgres flexible-server show \
  --resource-group tailord \
  --name tailord-pg \
  --query fullyQualifiedDomainName -o tsv)

green "PostgreSQL host: ${PG_FQDN}"

yellow "Fetching credentials from Key Vault..."

PROD_DB_URL=$(az keyvault secret show \
  --vault-name tailord-kv \
  --name prod-database-url \
  --query value -o tsv)

STAGING_DB_URL=$(az keyvault secret show \
  --vault-name tailord-kv \
  --name staging-database-url \
  --query value -o tsv)

parse_db_url() {
  python3 - "$1" <<'EOF'
import sys
from urllib.parse import urlparse
u = urlparse(sys.argv[1])
print(u.username)
print(u.password)
EOF
}

read -r PROD_DB_USER PROD_DB_PASS <<< "$(parse_db_url "$PROD_DB_URL")"
read -r STAGING_DB_USER STAGING_DB_PASS <<< "$(parse_db_url "$STAGING_DB_URL")"

upsert_datasource() {
  local ds_name="$1" db_name="$2" db_user="$3" db_pass="$4"

  local payload
  payload=$(jq -n \
    --arg name    "$ds_name" \
    --arg host    "${PG_FQDN}:5432" \
    --arg db      "$db_name" \
    --arg user    "$db_user" \
    --arg pass    "$db_pass" \
    '{
      name:   $name,
      type:   "postgres",
      access: "proxy",
      url:    $host,
      database: $db,
      user:   $user,
      secureJsonData: { password: $pass },
      jsonData: {
        sslmode:         "require",
        postgresVersion: 1600,
        timescaledb:     false
      },
      isDefault: false
    }')

  EXISTING_DS=$(grafana_api GET "/api/datasources/name/${ds_name}" 2>/dev/null \
    | jq -r '.id // empty')

  if [[ -n "$EXISTING_DS" ]]; then
    yellow "Datasource '${ds_name}' exists (id=${EXISTING_DS}) — updating."
    grafana_api PUT "/api/datasources/${EXISTING_DS}" -d "$payload" > /dev/null
  else
    yellow "Creating datasource '${ds_name}'."
    grafana_api POST "/api/datasources" -d "$payload" > /dev/null
  fi

  local ds_uid
  ds_uid=$(grafana_api GET "/api/datasources/name/${ds_name}" | jq -r '.uid')
  local test_result
  test_result=$(grafana_api GET "/api/datasources/uid/${ds_uid}/health" | jq -r '.status // empty')

  if [[ "$test_result" == "OK" ]]; then
    green "Datasource '${ds_name}': connection OK."
  else
    yellow "Datasource '${ds_name}' saved but health check returned: '${test_result}'. Verify manually in Grafana."
  fi
}

upsert_datasource "tailord-postgres-prod"    "tailord_prod"    "$PROD_DB_USER"    "$PROD_DB_PASS"
upsert_datasource "tailord-postgres-staging" "tailord_staging" "$STAGING_DB_USER" "$STAGING_DB_PASS"

# ── set GRAFANA_ENABLED=true ──────────────────────────────────────────────────
step "Setting GRAFANA_ENABLED=true"

set_gh_variable "GRAFANA_ENABLED" "true"

# ── deploy dashboards ─────────────────────────────────────────────────────────
step "Deploying dashboards"

GRAFANA_URL="$GRAFANA_URL" bash "$SCRIPT_DIR/deploy-dashboards.sh"

# ── done ───────────────────────────────────────────────────────────────────────
step "Bootstrap complete"
cat <<EOF

Next steps:
  1. Open Grafana:
       $GRAFANA_URL

  2. Update your local .env.azure to reflect Grafana is enabled:
       TF_VAR_grafana_enabled=true

  To redeploy dashboards at any time:
       cd infra/providers/azure && bash scripts/deploy-dashboards.sh

EOF

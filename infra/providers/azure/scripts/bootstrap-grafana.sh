#!/usr/bin/env bash
# bootstrap-grafana.sh — one-time Grafana setup after "terraform apply" or "observability enable"
#
# Automates BOOTSTRAP.md step 8:
#   - Publishes GRAFANA_URL as a repository variable for CI
#   - Configures tailord-postgres-prod and tailord-postgres-staging datasources
#
# Uses the 'amg' Azure CLI extension (az grafana ...) for all Grafana API calls.
# This avoids Azure AD token audience issues (region-specific) and does not create
# any service accounts — no extra billed users beyond your own Azure AD identity.
#
# Usage:
#   cd infra/providers/azure && bash scripts/bootstrap-grafana.sh
#
# Override the Grafana URL (skip terraform output):
#   GRAFANA_URL=https://... bash scripts/bootstrap-grafana.sh
#
# Prerequisites: az (logged in, amg extension auto-installed), gh (logged in), jq, python3, terraform (init'd + applied)
# Safe to re-run — datasources are upserted, not duplicated.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TF_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RESOURCE_GROUP="tailord"

# ── colour helpers ─────────────────────────────────────────────────────────────
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
step()   { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

# ── prerequisites ──────────────────────────────────────────────────────────────
step "Checking prerequisites"

for cmd in az gh jq python3 terraform; do
  if ! command -v "$cmd" &>/dev/null; then
    red "Missing required tool: $cmd"
    exit 1
  fi
done

az account show &>/dev/null || { red "Not logged in to Azure CLI. Run: az login"; exit 1; }
gh auth status &>/dev/null  || { red "Not logged in to GitHub CLI. Run: gh auth login"; exit 1; }

# The 'amg' extension provides 'az grafana ...' commands that handle Grafana data-plane
# auth internally — bypassing the region-specific token audience issue.
# Does not create service accounts — billing stays at 1 active user (your Azure AD identity).
if ! az extension show --name amg &>/dev/null; then
  yellow "Installing 'amg' Azure CLI extension (one-time)…"
  az extension add --name amg --yes
  green "Extension installed."
else
  green "Azure CLI 'amg' extension present."
fi

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

GRAFANA_URL="${GRAFANA_URL%/}"
green "Grafana URL: $GRAFANA_URL"

# Derive Azure resource name — match by endpoint URL, fall back to first instance in RG
GRAFANA_NAME=$(az grafana list \
  --resource-group "$RESOURCE_GROUP" \
  --query "[?properties.endpoint=='${GRAFANA_URL}/'].name | [0]" -o tsv 2>/dev/null || echo "")

if [[ -z "$GRAFANA_NAME" ]]; then
  GRAFANA_NAME=$(az grafana list \
    --resource-group "$RESOURCE_GROUP" \
    --query "[0].name" -o tsv 2>/dev/null || echo "")
fi

if [[ -z "$GRAFANA_NAME" ]]; then
  red "Could not resolve Grafana resource name in resource group '${RESOURCE_GROUP}'."
  red "Ensure Terraform has been applied with grafana_enabled=true."
  exit 1
fi

green "Grafana resource name: $GRAFANA_NAME"

# ── verify Grafana is reachable ────────────────────────────────────────────────
step "Verifying Grafana is reachable"

az grafana show --name "$GRAFANA_NAME" --resource-group "$RESOURCE_GROUP" -o none
green "Grafana instance '${GRAFANA_NAME}' found and accessible."

# ── publish GRAFANA_URL as a repository variable ───────────────────────────────
step "Publishing GRAFANA_URL as a GitHub repository variable"

GH_REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)

set_gh_variable() {
  local name="$1" value="$2"
  # Try PATCH (update existing), fall back to POST (create new)
  HTTP=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH \
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

# ── PostgreSQL datasources ─────────────────────────────────────────────────────
step "Configuring PostgreSQL datasources"

PG_FQDN=$(az postgres flexible-server show \
  --resource-group "$RESOURCE_GROUP" \
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

# bash 3.2 (macOS default) has no mapfile — read lines into array manually
_creds=()
while IFS= read -r line; do _creds+=("$line"); done < <(parse_db_url "$PROD_DB_URL")
PROD_DB_USER="${_creds[0]:-}"
PROD_DB_PASS="${_creds[1]:-}"

_creds=()
while IFS= read -r line; do _creds+=("$line"); done < <(parse_db_url "$STAGING_DB_URL")
STAGING_DB_USER="${_creds[0]:-}"
STAGING_DB_PASS="${_creds[1]:-}"

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
        database:        $db,
        sslmode:         "require",
        postgresVersion: 1600,
        timescaledb:     false
      },
      isDefault: false
    }')

  if az grafana data-source show \
      --name "$GRAFANA_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --data-source "$ds_name" &>/dev/null 2>&1; then
    yellow "Datasource '${ds_name}' exists — updating."
    az grafana data-source update \
      --name "$GRAFANA_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --data-source "$ds_name" \
      --definition "$payload" > /dev/null
  else
    yellow "Creating datasource '${ds_name}'."
    az grafana data-source create \
      --name "$GRAFANA_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --definition "$payload" > /dev/null
  fi

  green "Datasource '${ds_name}' configured."
}

upsert_datasource "tailord-postgres-prod"    "tailord_prod"    "$PROD_DB_USER"    "$PROD_DB_PASS"
upsert_datasource "tailord-postgres-staging" "tailord_staging" "$STAGING_DB_USER" "$STAGING_DB_PASS"

# ── set GRAFANA_ENABLED=true ──────────────────────────────────────────────────
step "Setting GRAFANA_ENABLED=true"

set_gh_variable "GRAFANA_ENABLED" "true"

# ── deploy dashboards ─────────────────────────────────────────────────────────
step "Deploying dashboards"

GRAFANA_URL="$GRAFANA_URL" GRAFANA_NAME="$GRAFANA_NAME" bash "$SCRIPT_DIR/deploy-dashboards.sh"

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

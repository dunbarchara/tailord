#!/usr/bin/env bash
# deploy-dashboards.sh — push dashboard JSON files to a running Grafana instance
#
# Resolves the Grafana URL from Terraform state (or GRAFANA_URL env override),
# authenticates via Azure AD OIDC token, and deploys all dashboards under
# observability/dashboards/prod/ into the "Production" folder.
#
# Usage:
#   cd infra/providers/azure && bash scripts/deploy-dashboards.sh
#
# Override the Grafana URL (skip terraform output):
#   GRAFANA_URL=https://... bash scripts/deploy-dashboards.sh
#
# Prerequisites: az (logged in), jq, terraform (init'd + applied with grafana_enabled=true)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TF_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../../" && pwd)"
DASHBOARDS_DIR="$REPO_ROOT/observability/dashboards/prod"

# ── colour helpers ─────────────────────────────────────────────────────────────
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
step()   { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

# ── prerequisites ──────────────────────────────────────────────────────────────
for cmd in az jq curl terraform; do
  if ! command -v "$cmd" &>/dev/null; then
    red "Missing required tool: $cmd"
    exit 1
  fi
done

az account show &>/dev/null || { red "Not logged in to Azure CLI. Run: az login"; exit 1; }

# ── resolve Grafana URL ────────────────────────────────────────────────────────
step "Resolving Grafana endpoint"

if [[ -n "${GRAFANA_URL:-}" ]]; then
  yellow "Using GRAFANA_URL from environment: $GRAFANA_URL"
else
  GRAFANA_URL=$(terraform -chdir="$TF_DIR" output -raw grafana_endpoint 2>/dev/null) || {
    red "Could not read grafana_endpoint from Terraform state."
    red "Either run 'terraform apply' with grafana_enabled=true first, or set GRAFANA_URL=... in the environment."
    exit 1
  }
  if [[ -z "$GRAFANA_URL" ]]; then
    red "grafana_endpoint output is empty — Grafana is not enabled (grafana_enabled=false)."
    exit 1
  fi
fi

GRAFANA_URL="${GRAFANA_URL%/}"
green "Grafana URL: $GRAFANA_URL"

# ── Azure AD token ─────────────────────────────────────────────────────────────
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

if ! grafana_api GET "/api/health" | jq -e '.database == "ok"' &>/dev/null; then
  red "Grafana API health check failed — token may be invalid or instance not ready."
  exit 1
fi

green "Grafana API reachable and healthy."

# ── ensure Production folder ───────────────────────────────────────────────────
step "Ensuring Production folder exists"

HTTP=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  -H "Authorization: Bearer $GRAFANA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Production","uid":"tailord-prod"}' \
  "$GRAFANA_URL/api/folders")
[[ "$HTTP" == "200" || "$HTTP" == "409" || "$HTTP" == "412" ]] || {
  red "Failed to create Production folder (HTTP $HTTP)"; exit 1
}
green "Production folder ready."

# ── resolve datasource UIDs ───────────────────────────────────────────────────
step "Fetching datasource UIDs"

DATASOURCES=$(grafana_api GET "/api/datasources")

DS_PROMETHEUS=$(echo "$DATASOURCES" | jq -r '.[] | select(.type=="prometheus") | .uid // empty' | head -1)
DS_AZURE_MONITOR=$(echo "$DATASOURCES" | jq -r '.[] | select(.type=="grafana-azure-monitor-datasource") | .uid // empty' | head -1)
DS_POSTGRES=$(echo "$DATASOURCES" | jq -r '.[] | select(.name=="tailord-postgres-prod") | .uid // empty' | head -1)

[[ -n "$DS_PROMETHEUS" ]] || { red "Prometheus datasource not found — run bootstrap-grafana.sh first"; exit 1; }
[[ -n "$DS_POSTGRES"   ]] || { red "tailord-postgres-prod datasource not found — run bootstrap-grafana.sh first"; exit 1; }

green "Prometheus:    $DS_PROMETHEUS"
green "Azure Monitor: ${DS_AZURE_MONITOR:-(not found, skipping substitution)}"
green "PostgreSQL:    $DS_POSTGRES"

# ── deploy dashboards ─────────────────────────────────────────────────────────
step "Deploying dashboards from $DASHBOARDS_DIR"

shopt -s nullglob
files=("$DASHBOARDS_DIR"/*.json)

if [[ ${#files[@]} -eq 0 ]]; then
  yellow "No dashboard JSON files found in $DASHBOARDS_DIR — nothing to deploy."
  exit 0
fi

deployed=0
for f in "${files[@]}"; do
  PAYLOAD=$(jq \
    --arg prom  "$DS_PROMETHEUS" \
    --arg azmon "$DS_AZURE_MONITOR" \
    --arg pg    "$DS_POSTGRES" \
    'walk(if type == "string" then
       sub("__PROMETHEUS_UID__"; $prom) |
       sub("__AZURE_MONITOR_UID__"; $azmon) |
       sub("__POSTGRES_UID__"; $pg)
     else . end) |
     {dashboard: ., overwrite: true, folderUid: "tailord-prod"}' "$f")

  RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
    -H "Authorization: Bearer $GRAFANA_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" \
    "$GRAFANA_URL/api/dashboards/db")

  HTTP=$(echo "$RESPONSE" | tail -1)
  BODY=$(echo "$RESPONSE" | head -n -1)

  if [[ "$HTTP" == "200" ]]; then
    green "Deployed: $(basename "$f")"
    deployed=$((deployed + 1))
  else
    red "Failed to deploy $(basename "$f") (HTTP $HTTP)"
    echo "$BODY" | jq . 2>/dev/null || echo "$BODY"
    exit 1
  fi
done

step "Done — $deployed dashboard(s) deployed to $GRAFANA_URL"

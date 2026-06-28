#!/usr/bin/env bash
# deploy-dashboards.sh — push dashboard JSON files to a running Grafana instance
#
# Resolves the Grafana URL and resource name, then deploys all dashboards under
# observability/dashboards/prod/ into the "Production" folder using the 'amg'
# Azure CLI extension (no service accounts, no extra billed users).
#
# Usage:
#   cd infra/providers/azure && bash scripts/deploy-dashboards.sh
#
# Override URL or resource name (skip terraform output):
#   GRAFANA_URL=https://... bash scripts/deploy-dashboards.sh
#   GRAFANA_NAME=my-grafana bash scripts/deploy-dashboards.sh
#
# Prerequisites: az (logged in, amg extension), jq, terraform (init'd + applied with grafana_enabled=true)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TF_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../../" && pwd)"
DASHBOARDS_DIR="$REPO_ROOT/observability/dashboards/prod"
RESOURCE_GROUP="tailord"

# ── colour helpers ─────────────────────────────────────────────────────────────
green()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[0;33m%s\033[0m\n' "$*"; }
red()    { printf '\033[0;31m%s\033[0m\n' "$*"; }
step()   { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

# ── prerequisites ──────────────────────────────────────────────────────────────
for cmd in az jq terraform; do
  if ! command -v "$cmd" &>/dev/null; then
    red "Missing required tool: $cmd"
    exit 1
  fi
done

az account show &>/dev/null || { red "Not logged in to Azure CLI. Run: az login"; exit 1; }

if ! az extension show --name amg &>/dev/null; then
  yellow "Installing 'amg' Azure CLI extension (one-time)…"
  az extension add --name amg --yes
fi

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

# ── resolve Grafana resource name ─────────────────────────────────────────────
if [[ -z "${GRAFANA_NAME:-}" ]]; then
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
    exit 1
  fi
fi

green "Grafana resource name: $GRAFANA_NAME"

# ── resolve datasource UIDs ───────────────────────────────────────────────────
step "Fetching datasource UIDs"

DS_LIST=$(az grafana data-source list \
  --name "$GRAFANA_NAME" \
  --resource-group "$RESOURCE_GROUP" 2>/dev/null)

DS_PROMETHEUS=$(echo "$DS_LIST" | jq -r '.[] | select(.type=="prometheus" or .type=="grafana-azure-prometheus-datasource") | .uid // empty' | head -1)
DS_AZURE_MONITOR=$(echo "$DS_LIST" | jq -r '.[] | select(.type=="grafana-azure-monitor-datasource") | .uid // empty' | head -1)
DS_POSTGRES=$(echo "$DS_LIST" | jq -r '.[] | select(.name=="tailord-postgres-prod") | .uid // empty' | head -1)

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

TMP_DASHBOARD=$(mktemp /tmp/grafana-dashboard-XXXXXX.json)
trap 'rm -f "$TMP_DASHBOARD"' EXIT

deployed=0
for f in "${files[@]}"; do
  # Substitute datasource UID placeholders and write to temp file
  jq \
    --arg prom  "$DS_PROMETHEUS" \
    --arg azmon "$DS_AZURE_MONITOR" \
    --arg pg    "$DS_POSTGRES" \
    'walk(if type == "string" then
       sub("__PROMETHEUS_UID__"; $prom) |
       sub("__AZURE_MONITOR_UID__"; $azmon) |
       sub("__POSTGRES_UID__"; $pg)
     else . end)' "$f" > "$TMP_DASHBOARD"

  az grafana dashboard import \
    --name "$GRAFANA_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --definition "$TMP_DASHBOARD" \
    --overwrite true \
    -o none

  green "Deployed: $(basename "$f")"
  deployed=$((deployed + 1))
done

step "Done — $deployed dashboard(s) deployed to $GRAFANA_URL"

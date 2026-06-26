variable "subscription_id" {
  sensitive = true
  type      = string
}

variable "location" {
  type    = string
  default = "canadacentral"
}

variable "project_name" {
  type    = string
  default = "tailord"
}

variable "domain_name" {
  type    = string
  default = "tailord.app"
}

variable "db_password" {
  description = "PostgreSQL admin password — server creation / disaster recovery only. App connections use the per-user accounts in Key Vault. Source from 1Password; not needed for routine applies."
  sensitive   = true
  type        = string
}

variable "llm_model" {
  type    = string
default = "gpt-5.4"
}

variable "embedding_model" {
  description = "Azure AI Foundry deployment name for embeddings. Must be deployed in the same resource as llm_model."
  type        = string
  default     = "text-embedding-3-small"
}

variable "log_level" {
  type    = string
  default = "INFO"
}

variable "llm_api_version" {
  description = "API version query param for Azure AI endpoints (e.g. 2024-05-01-preview). Leave empty for OpenAI or local."
  type        = string
  default     = ""
}

variable "cloudflare_zone_id" {
  sensitive = true
  type      = string
}

variable "github_actions_sp_object_id" {
  description = "Object ID of the GitHub Actions service principal (az ad sp show --id <client-id> --query id -o tsv)"
  sensitive   = true
  type        = string
}

# ── GitHub App ────────────────────────────────────────────────────────────────
# App IDs are non-sensitive identifiers.
# Private keys and secrets are stored in Key Vault directly (see keyvault.tf) —
# never passed as Terraform variables.
# Installation IDs are stored per-user in ExperienceSource.config via OAuth callback.

variable "github_app_id_prod" {
  description = "GitHub App ID for the Tailord prod app"
  type        = string
}

variable "github_app_id_staging" {
  description = "GitHub App ID for the Tailord staging app"
  type        = string
}

variable "github_app_client_id_prod" {
  description = "GitHub App Client ID for the prod Tailord app (from GitHub App settings)"
  type        = string
}

variable "github_app_client_id_staging" {
  description = "GitHub App Client ID for the staging Tailord app (from GitHub App settings)"
  type        = string
}

variable "alert_email" {
  description = "Email address for operational alert notifications"
  type        = string
}

variable "grafana_admin_object_id" {
  description = "Azure AD object ID of the Grafana admin user (az ad signed-in-user show --query id -o tsv)"
  sensitive   = true
  type        = string
}

variable "grafana_enabled" {
  description = "When false, the Grafana instance and its role assignments are destroyed. Toggle via the observability.yml workflow; keep TF_VAR_grafana_enabled in .env.azure in sync."
  type        = bool
  default     = false
}

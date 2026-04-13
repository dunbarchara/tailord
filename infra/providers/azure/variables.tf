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
  description = "PostgreSQL admin password (server creation only — app connections use db_prod_password / db_staging_password)"
  sensitive   = true
  type        = string
}

variable "db_prod_password" {
  description = "Password for the tailord_prod PostgreSQL user (prod backend only)"
  sensitive   = true
  type        = string
}

variable "db_staging_password" {
  description = "Password for the tailord_staging PostgreSQL user (staging backend only)"
  sensitive   = true
  type        = string
}

variable "api_key_prod" {
  description = "Shared secret for frontend→backend auth in prod (X-API-Key header)"
  sensitive   = true
  type        = string
}

variable "api_key_staging" {
  description = "Shared secret for frontend→backend auth in staging (X-API-Key header)"
  sensitive   = true
  type        = string
}

variable "llm_model" {
  type    = string
  default = "gpt-5.4-mini"
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

variable "nextauth_secret_prod" {
  description = "NextAuth signing secret for prod — must differ from staging"
  sensitive   = true
  type        = string
}

variable "nextauth_secret_staging" {
  description = "NextAuth signing secret for staging — must differ from prod"
  sensitive   = true
  type        = string
}

variable "google_client_id" {
  sensitive = true
  type      = string
}

variable "google_client_secret" {
  sensitive = true
  type      = string
}

variable "github_actions_sp_object_id" {
  description = "Object ID of the GitHub Actions service principal (az ad sp show --id <client-id> --query id -o tsv)"
  sensitive   = true
  type        = string
}

variable "notion_client_id" {
  description = "Notion OAuth client ID"
  sensitive   = true
  type        = string
}

variable "notion_client_secret" {
  description = "Notion OAuth client secret"
  sensitive   = true
  type        = string
}

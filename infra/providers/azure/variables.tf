variable "subscription_id" {
  type = string
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

variable "db_password" { # Provided once at provision time
  sensitive = true
  type      = string
}

variable "api_key" { # Provided once at provision time
  sensitive = true
  type      = string
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

variable "nextauth_secret" {
  sensitive = true
  type      = string
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

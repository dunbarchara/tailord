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
  default = "gpt-4o-mini"
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

variable "llm_api_key" {
  sensitive = true
  type      = string
}

variable "github_actions_sp_object_id" {
  description = "Object ID of the GitHub Actions service principal (az ad sp show --id <client-id> --query id -o tsv)"
  type        = string
}

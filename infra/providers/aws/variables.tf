variable "region" {
  type    = string
  default = "us-east-2"
}

variable "project_name" {
  type    = string
  default = "tailord"
}

variable "desired_count" {
  type    = number
  default = 2
}

variable "container_port" {
  default = 3000
}

variable "domain_name" {
  type    = string
  default = "tailord.app"
}

variable "cloudflare_zone_id" {
  sensitive = true
  type      = string
}

variable "api_key" {
  sensitive = true
  type      = string
}

variable "db_username" {
  type    = string
  default = "tailord"
}

variable "db_password" {
  sensitive = true
  type      = string
}

variable "backend_image_uri" {
  type    = string
  default = ""
}

variable "llm_model" {
  type    = string
  default = "gpt-4o-mini"
}

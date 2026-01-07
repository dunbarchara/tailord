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

variable "domain_names" {
  type = list(string)
}

variable "zone_id" {
  type      = string
  sensitive = true
}

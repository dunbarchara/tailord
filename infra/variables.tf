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

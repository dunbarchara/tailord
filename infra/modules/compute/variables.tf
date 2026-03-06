variable "cluster_name" {
  type = string
}

variable "frontend_image_uri" {
  type = string
}

variable "backend_image_uri" {
  type = string
}

variable "cpu" {
  type    = number
  default = 256
}

variable "memory" {
  type    = number
  default = 512
}

variable "env_vars" {
  type    = map(string)
  default = {}
}

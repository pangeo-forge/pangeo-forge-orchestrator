variable "project" {
  type = string
}

variable "credentials_file" {
  type = string
}

variable "apps_with_secrets" {
  type = map
  sensitive = true
}

module "dataflow_status_monitoring" {
  source = "../../dataflow-status-monitoring/terraform"

  project           = var.project
  credentials_file  = var.credentials_file
  apps_with_secrets = var.apps_with_secrets
  function_src_dir  = "../../dataflow-status-monitoring/src"
}

terraform {
  backend "gcs" {
    bucket  = "pforge-tfstate"
    prefix  = "terraform/state"
  }
}

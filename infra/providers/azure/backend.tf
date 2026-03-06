terraform {
  backend "azurerm" {
    resource_group_name  = "tailord-tfstate"
    storage_account_name = "tailordtfstate"
    container_name       = "tfstate"
    key                  = "tailord.tfstate"
  }
}

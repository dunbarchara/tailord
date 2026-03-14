# -----------------------------
# LOG ANALYTICS WORKSPACE
# -----------------------------
resource "azurerm_log_analytics_workspace" "tailord" {
  name                = "${var.project_name}-logs"
  resource_group_name = azurerm_resource_group.tailord.name
  location            = azurerm_resource_group.tailord.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  daily_quota_gb      = 0.5
  tags                = local.tags
}

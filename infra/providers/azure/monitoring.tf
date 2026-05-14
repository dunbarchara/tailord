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

# -----------------------------
# AZURE MANAGED PROMETHEUS
# -----------------------------
resource "azurerm_monitor_workspace" "main" {
  name                = "${var.project_name}-amp"
  resource_group_name = azurerm_resource_group.tailord.name
  location            = azurerm_resource_group.tailord.location
}

# -----------------------------
# AZURE MANAGED GRAFANA
# -----------------------------
resource "azurerm_dashboard_grafana" "main" {
  name                = "${var.project_name}-grafana"
  resource_group_name = azurerm_resource_group.tailord.name
  location            = azurerm_resource_group.tailord.location
  grafana_major_version = 10
  azure_monitor_workspace_integrations {
    resource_id = azurerm_monitor_workspace.main.id
  }
}

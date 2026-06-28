
output "frontend_url" {
  value = "https://${azurerm_container_app.frontend_prod.ingress[0].fqdn}"
}

output "staging_frontend_url" {
  value = "https://${azurerm_container_app.frontend_staging.ingress[0].fqdn}"
}

output "grafana_endpoint" {
  value       = length(azurerm_dashboard_grafana.main) > 0 ? azurerm_dashboard_grafana.main[0].endpoint : ""
  description = "Azure Managed Grafana workspace URL. Empty when grafana_enabled=false."
}

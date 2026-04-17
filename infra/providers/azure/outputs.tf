
output "frontend_url" {
  value = "https://${azurerm_container_app.frontend_prod.ingress[0].fqdn}"
}

output "staging_frontend_url" {
  value = "https://${azurerm_container_app.frontend_staging.ingress[0].fqdn}"
}

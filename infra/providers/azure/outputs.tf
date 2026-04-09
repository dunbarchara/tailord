output "acr_login_server" {
  value = azurerm_container_registry.tailord.login_server
}

output "frontend_url" {
  value = "https://${azurerm_container_app.frontend_prod.ingress[0].fqdn}"
}

output "staging_frontend_url" {
  value = "https://${azurerm_container_app.frontend_staging.ingress[0].fqdn}"
}

output "prod_db_connection_string" {
  value     = "postgresql+psycopg://tailord_prod:${var.db_prod_password}@${azurerm_postgresql_flexible_server.tailord.fqdn}/tailord_prod"
  sensitive = true
}

output "staging_db_connection_string" {
  value     = "postgresql+psycopg://tailord_staging:${var.db_staging_password}@${azurerm_postgresql_flexible_server.tailord.fqdn}/tailord_staging"
  sensitive = true
}

output "llm_base_url" {
  description = "Foundry endpoint"
  value       = azurerm_cognitive_account.tailord_foundry.endpoint
}

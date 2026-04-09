output "acr_login_server" {
  value = azurerm_container_registry.tailord.login_server
}

output "frontend_url" {
  value = "https://${azurerm_container_app.frontend.ingress[0].fqdn}"
}

output "staging_frontend_url" {
  value = "https://${var.project_name}-frontend---staging.${azurerm_container_app_environment.tailord.default_domain}"
}

output "prod_db_connection_string" {
  value     = "postgresql+psycopg://tailord:${var.db_password}@${azurerm_postgresql_flexible_server.tailord.fqdn}/tailord_prod"
  sensitive = true
}

output "staging_db_connection_string" {
  value     = "postgresql+psycopg://tailord:${var.db_password}@${azurerm_postgresql_flexible_server.tailord.fqdn}/tailord_staging"
  sensitive = true
}

output "llm_base_url" {
  description = "Foundry endpoint"
  value       = azurerm_cognitive_account.tailord_foundry.endpoint
}

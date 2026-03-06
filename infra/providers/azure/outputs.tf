output "acr_login_server" {
  value = azurerm_container_registry.tailord.login_server
}

output "frontend_url" {
  value = "https://${azurerm_container_app.frontend.ingress[0].fqdn}"
}

output "db_connection_string" {
  value     = "postgresql+psycopg://tailord:${var.db_password}@${azurerm_postgresql_flexible_server.tailord.fqdn}/tailord"
  sensitive = true
}

# -----------------------------
# CURRENT CALLER (for RBAC)
# -----------------------------
data "azurerm_client_config" "current" {}

# -----------------------------
# MANAGED IDENTITY
# Used by Container Apps to authenticate to Key Vault
# -----------------------------
resource "azurerm_user_assigned_identity" "container_apps" {
  name                = "${var.project_name}-apps-identity"
  resource_group_name = azurerm_resource_group.tailord.name
  location            = azurerm_resource_group.tailord.location
  tags                = local.tags
}

# -----------------------------
# KEY VAULT
# -----------------------------
resource "azurerm_key_vault" "tailord" {
  name                       = "${var.project_name}-kv"
  resource_group_name        = azurerm_resource_group.tailord.name
  location                   = azurerm_resource_group.tailord.location
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  tags                       = local.tags
}

# Terraform deployer — write secrets
resource "azurerm_role_assignment" "kv_secrets_officer" {
  scope                = azurerm_key_vault.tailord.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

# Container Apps managed identity — read secrets
resource "azurerm_role_assignment" "kv_secrets_user" {
  scope                = azurerm_key_vault.tailord.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.container_apps.principal_id
}

# -----------------------------
# SECRETS
# depends_on role assignment — RBAC propagation can lag writes
# -----------------------------
resource "azurerm_key_vault_secret" "database_url" {
  name         = "database-url"
  value        = "postgresql+psycopg://tailord:${var.db_password}@${azurerm_postgresql_flexible_server.tailord.fqdn}/tailord"
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "api_key" {
  name         = "api-key"
  value        = var.api_key
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "storage_connection_string" {
  name         = "storage-connection-string"
  value        = azurerm_storage_account.uploads.primary_connection_string
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "nextauth_secret" {
  name         = "nextauth-secret"
  value        = var.nextauth_secret
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "google_client_id" {
  name         = "google-client-id"
  value        = var.google_client_id
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "google_client_secret" {
  name         = "google-client-secret"
  value        = var.google_client_secret
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "llm_api_key" {
  name         = "llm-api-key"
  value        = azurerm_cognitive_account.tailord_foundry.primary_access_key
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

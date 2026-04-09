# -----------------------------
# CURRENT CALLER (for RBAC)
# -----------------------------
data "azurerm_client_config" "current" {}

# -----------------------------
# MANAGED IDENTITY
# Used by Container Apps to authenticate to Key Vault
# -----------------------------
resource "azurerm_user_assigned_identity" "apps" {
  name                = "${var.project_name}-id"
  resource_group_name = azurerm_resource_group.tailord.name
  location            = azurerm_resource_group.tailord.location
  tags                = local.tags
}

# -----------------------------
# KEY VAULT
# -----------------------------
resource "azurerm_key_vault" "tailord" {
  name                          = "${var.project_name}-kv"
  resource_group_name           = azurerm_resource_group.tailord.name
  location                      = azurerm_resource_group.tailord.location
  tenant_id                     = data.azurerm_client_config.current.tenant_id
  sku_name                      = "standard"
  rbac_authorization_enabled    = true
  soft_delete_retention_days    = 7
  purge_protection_enabled      = true
  tags                          = local.tags
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
  principal_id         = azurerm_user_assigned_identity.apps.principal_id
}

# -----------------------------
# PROD SECRETS
# depends_on role assignment — RBAC propagation can lag writes
# -----------------------------
resource "azurerm_key_vault_secret" "prod_database_url" {
  name         = "prod-database-url"
  value        = "postgresql+psycopg://tailord_prod:${var.db_prod_password}@${azurerm_postgresql_flexible_server.tailord.fqdn}/tailord_prod"
  content_type = "text/plain"
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "prod_api_key" {
  name         = "prod-api-key"
  value        = var.api_key
  content_type = "text/plain"
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "prod_storage_connection_string" {
  name         = "prod-storage-connection-string"
  value        = azurerm_storage_account.uploads_prod.primary_connection_string
  content_type = "text/plain"
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "prod_nextauth_secret" {
  name         = "prod-nextauth-secret"
  value        = var.nextauth_secret
  content_type = "text/plain"
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "prod_google_client_id" {
  name         = "prod-google-client-id"
  value        = var.google_client_id
  content_type = "text/plain"
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "prod_google_client_secret" {
  name         = "prod-google-client-secret"
  value        = var.google_client_secret
  content_type = "text/plain"
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "prod_llm_api_key" {
  name         = "prod-llm-api-key"
  value        = azurerm_cognitive_account.tailord_foundry.primary_access_key
  content_type = "text/plain"
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "prod_notion_client_id" {
  name         = "prod-notion-client-id"
  value        = var.notion_client_id
  content_type = "text/plain"
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "prod_notion_client_secret" {
  name         = "prod-notion-client-secret"
  value        = var.notion_client_secret
  content_type = "text/plain"
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

# -----------------------------
# STAGING SECRETS
# Fully isolated from prod: separate database user (tailord_staging → tailord_staging db only),
# separate storage account (tailordstaging), and separate Key Vault secret names (staging-*).
# -----------------------------
resource "azurerm_key_vault_secret" "staging_database_url" {
  name         = "staging-database-url"
  value        = "postgresql+psycopg://tailord_staging:${var.db_staging_password}@${azurerm_postgresql_flexible_server.tailord.fqdn}/tailord_staging"
  content_type = "text/plain"
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "staging_api_key" {
  name         = "staging-api-key"
  value        = var.api_key
  content_type = "text/plain"
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "staging_storage_connection_string" {
  name         = "staging-storage-connection-string"
  value        = azurerm_storage_account.uploads_staging.primary_connection_string
  content_type = "text/plain"
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "staging_nextauth_secret" {
  name         = "staging-nextauth-secret"
  value        = var.nextauth_secret
  content_type = "text/plain"
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "staging_google_client_id" {
  name         = "staging-google-client-id"
  value        = var.google_client_id
  content_type = "text/plain"
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "staging_google_client_secret" {
  name         = "staging-google-client-secret"
  value        = var.google_client_secret
  content_type = "text/plain"
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "staging_llm_api_key" {
  name         = "staging-llm-api-key"
  value        = azurerm_cognitive_account.tailord_foundry.primary_access_key
  content_type = "text/plain"
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "staging_notion_client_id" {
  name         = "staging-notion-client-id"
  value        = var.notion_client_id
  content_type = "text/plain"
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

resource "azurerm_key_vault_secret" "staging_notion_client_secret" {
  name         = "staging-notion-client-secret"
  value        = var.notion_client_secret
  content_type = "text/plain"
  key_vault_id = azurerm_key_vault.tailord.id
  depends_on   = [azurerm_role_assignment.kv_secrets_officer]
}

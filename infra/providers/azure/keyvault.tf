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

# Terraform deployer — read secrets (data sources only; no longer writes secrets)
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
# PROD SECRETS (data sources — pre-populated manually via az keyvault secret set)
# Terraform reads the versionless URI to wire into Container Apps; it never
# holds or manages the secret values.
# -----------------------------
data "azurerm_key_vault_secret" "prod_database_url" {
  name         = "prod-database-url"
  key_vault_id = azurerm_key_vault.tailord.id
}

data "azurerm_key_vault_secret" "prod_api_key" {
  name         = "prod-api-key"
  key_vault_id = azurerm_key_vault.tailord.id
}

data "azurerm_key_vault_secret" "prod_nextauth_secret" {
  name         = "prod-nextauth-secret"
  key_vault_id = azurerm_key_vault.tailord.id
}

data "azurerm_key_vault_secret" "prod_google_client_id" {
  name         = "prod-google-client-id"
  key_vault_id = azurerm_key_vault.tailord.id
}

data "azurerm_key_vault_secret" "prod_google_client_secret" {
  name         = "prod-google-client-secret"
  key_vault_id = azurerm_key_vault.tailord.id
}

data "azurerm_key_vault_secret" "prod_notion_client_id" {
  name         = "prod-notion-client-id"
  key_vault_id = azurerm_key_vault.tailord.id
}

data "azurerm_key_vault_secret" "prod_notion_client_secret" {
  name         = "prod-notion-client-secret"
  key_vault_id = azurerm_key_vault.tailord.id
}

data "azurerm_key_vault_secret" "prod_github_app_private_key" {
  name         = "prod-github-app-private-key"
  key_vault_id = azurerm_key_vault.tailord.id
}

# -----------------------------
# STAGING SECRETS (data sources)
# Fully isolated from prod: separate database user, separate storage account,
# separate secret names (staging-*).
# -----------------------------
data "azurerm_key_vault_secret" "staging_database_url" {
  name         = "staging-database-url"
  key_vault_id = azurerm_key_vault.tailord.id
}

data "azurerm_key_vault_secret" "staging_api_key" {
  name         = "staging-api-key"
  key_vault_id = azurerm_key_vault.tailord.id
}

data "azurerm_key_vault_secret" "staging_nextauth_secret" {
  name         = "staging-nextauth-secret"
  key_vault_id = azurerm_key_vault.tailord.id
}

data "azurerm_key_vault_secret" "staging_google_client_id" {
  name         = "staging-google-client-id"
  key_vault_id = azurerm_key_vault.tailord.id
}

data "azurerm_key_vault_secret" "staging_google_client_secret" {
  name         = "staging-google-client-secret"
  key_vault_id = azurerm_key_vault.tailord.id
}

data "azurerm_key_vault_secret" "staging_notion_client_id" {
  name         = "staging-notion-client-id"
  key_vault_id = azurerm_key_vault.tailord.id
}

data "azurerm_key_vault_secret" "staging_notion_client_secret" {
  name         = "staging-notion-client-secret"
  key_vault_id = azurerm_key_vault.tailord.id
}

data "azurerm_key_vault_secret" "staging_github_app_private_key" {
  name         = "staging-github-app-private-key"
  key_vault_id = azurerm_key_vault.tailord.id
}

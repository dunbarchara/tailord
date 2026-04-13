# -----------------------------
# GITHUB ACTIONS SERVICE PRINCIPAL
# Role assignments for the SP used by the deploy pipeline.
# The SP itself (app registration + federated credential) is managed
# manually as a one-time bootstrap — only its permissions live here.
# -----------------------------

# AcrPush — build and push images
resource "azurerm_role_assignment" "gha_acr_push" {
  scope                = azurerm_container_registry.tailord.id
  role_definition_name = "AcrPush"
  principal_id         = var.github_actions_sp_object_id
}

# AcrDelete — purge old images in the pipeline cleanup step
resource "azurerm_role_assignment" "gha_acr_delete" {
  scope                = azurerm_container_registry.tailord.id
  role_definition_name = "AcrDelete"
  principal_id         = var.github_actions_sp_object_id
}

# Contributor on the resource group — required for az containerapp update
resource "azurerm_role_assignment" "gha_rg_contributor" {
  scope                = azurerm_resource_group.tailord.id
  role_definition_name = "Contributor"
  principal_id         = var.github_actions_sp_object_id
}

# -----------------------------
# MANAGED IDENTITY — APP SERVICES
# Role assignments for the user-assigned identity attached to all Container Apps.
# -----------------------------

# Blob Storage — prod
# Storage Blob Data Contributor: read/write/delete blobs
# Storage Blob Delegator:        sign User Delegation SAS tokens (no account key needed)
resource "azurerm_role_assignment" "app_storage_contributor_prod" {
  scope                = azurerm_storage_account.uploads_prod.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.apps.principal_id
}

resource "azurerm_role_assignment" "app_storage_delegator_prod" {
  scope                = azurerm_storage_account.uploads_prod.id
  role_definition_name = "Storage Blob Delegator"
  principal_id         = azurerm_user_assigned_identity.apps.principal_id
}

# Blob Storage — staging
resource "azurerm_role_assignment" "app_storage_contributor_staging" {
  scope                = azurerm_storage_account.uploads_staging.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.apps.principal_id
}

resource "azurerm_role_assignment" "app_storage_delegator_staging" {
  scope                = azurerm_storage_account.uploads_staging.id
  role_definition_name = "Storage Blob Delegator"
  principal_id         = azurerm_user_assigned_identity.apps.principal_id
}

# Azure AI Foundry — Managed Identity replaces the static LLM_API_KEY.
# Cognitive Services OpenAI User: call inference endpoints; cannot manage the account.
resource "azurerm_role_assignment" "app_llm_user" {
  scope                = azurerm_cognitive_account.tailord_foundry.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_user_assigned_identity.apps.principal_id
}

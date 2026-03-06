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

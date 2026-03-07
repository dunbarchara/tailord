# -----------------------------
# AZURE AI FOUNDRY
# -----------------------------
# The AI Foundry account (Microsoft.CognitiveServices/accounts kind=AIServices) is Terraform-managed.
# Pay-per-token model deployments within it are not yet supported by the provider — see BOOTSTRAP.md step 3a.
# The account key and endpoint are wired directly into Key Vault and the backend Container App env.

resource "azurerm_cognitive_account" "tailord_foundry" {
  name                = "${var.project_name}-foundry"
  resource_group_name = azurerm_resource_group.tailord.name
  location            = azurerm_resource_group.tailord.location
  kind                = "AIServices"
  sku_name            = "S0"
  tags                = local.tags
}

# -----------------------------
# AZURE AI FOUNDRY
# -----------------------------
# The AI Foundry account (Microsoft.CognitiveServices/accounts kind=AIServices) is Terraform-managed.
# Pay-per-token model deployments within it are not yet supported by the provider — see BOOTSTRAP.md step 3a.
# The account key and endpoint are wired directly into Key Vault and the backend Container App env.

resource "azurerm_cognitive_account" "tailord_foundry" {
  name                  = "${var.project_name}-foundry"
  resource_group_name   = azurerm_resource_group.tailord.name
  location              = "canadaeast"
  kind                  = "AIServices"
  sku_name              = "S0"
  custom_subdomain_name = "${var.project_name}-foundry"
  tags                  = local.tags
}

# The provider's .endpoint attribute returns the generic regional URL even when
# custom_subdomain_name is set. Construct the correct OpenAI endpoint directly.
locals {
  openai_endpoint = "https://${azurerm_cognitive_account.tailord_foundry.custom_subdomain_name}.openai.azure.com/"
}

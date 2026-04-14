# -----------------------------
# RESOURCE GROUP
# -----------------------------
resource "azurerm_resource_group" "tailord" {
  name     = var.project_name
  location = var.location
  tags     = local.tags
}

# -----------------------------
# CONTAINER REGISTRY (ACR)
# -----------------------------
resource "azurerm_container_registry" "tailord" {
  name                = replace(var.project_name, "-", "")
  resource_group_name = azurerm_resource_group.tailord.name
  location            = azurerm_resource_group.tailord.location
  sku                 = "Basic"
  admin_enabled       = false
  tags                = local.tags
}

# -----------------------------
# STORAGE
# Separate accounts per environment so staging cannot access prod blobs
# even with a misconfigured connection string.
# -----------------------------
resource "azurerm_storage_account" "uploads_prod" {
  name                              = "${replace(var.project_name, "-", "")}prod"
  resource_group_name               = azurerm_resource_group.tailord.name
  location                          = azurerm_resource_group.tailord.location
  account_tier                      = "Standard"
  account_replication_type          = "LRS"
  allow_nested_items_to_be_public   = false
  min_tls_version                   = "TLS1_2"
  tags                              = local.tags

  blob_properties {
    cors_rule {
      allowed_headers    = ["*"]
      allowed_methods    = ["PUT"]
      allowed_origins    = [
        "https://${var.domain_name}",
        "https://www.${var.domain_name}",
      ]
      exposed_headers    = ["*"]
      max_age_in_seconds = 3000
    }
  }
}

resource "azurerm_storage_account" "uploads_staging" {
  name                              = "${replace(var.project_name, "-", "")}staging"
  resource_group_name               = azurerm_resource_group.tailord.name
  location                          = azurerm_resource_group.tailord.location
  account_tier                      = "Standard"
  account_replication_type          = "LRS"
  allow_nested_items_to_be_public   = false
  min_tls_version                   = "TLS1_2"
  tags                              = local.tags

  blob_properties {
    cors_rule {
      allowed_headers    = ["*"]
      allowed_methods    = ["PUT"]
      allowed_origins    = [
        "https://staging.${var.domain_name}",
        "http://localhost:3000",
      ]
      exposed_headers    = ["*"]
      max_age_in_seconds = 3000
    }
  }
}

resource "azurerm_storage_container" "uploads_prod" {
  name               = "uploads"
  storage_account_id = azurerm_storage_account.uploads_prod.id
}

resource "azurerm_storage_container" "uploads_staging" {
  name               = "uploads"
  storage_account_id = azurerm_storage_account.uploads_staging.id
}

# -----------------------------
# POSTGRESQL FLEXIBLE SERVER
# -----------------------------
resource "azurerm_postgresql_flexible_server" "tailord" {
  name                   = "${var.project_name}-pg"
  resource_group_name    = azurerm_resource_group.tailord.name
  location               = azurerm_resource_group.tailord.location
  version                = "16"
  administrator_login    = "tailord"
  administrator_password = var.db_password
  sku_name               = "B_Standard_B1ms"
  storage_mb             = 32768
  zone                   = "1"
  tags                   = local.tags
}

# SECURITY DEBT: The 0.0.0.0/0.0.0.0 magic range enables "Allow access to Azure services",
# which permits any Azure-hosted service — including those in other tenants — to reach port 5432.
# This is mitigated by strong credentials and TLS, but the proper fix is VNet integration:
# put the PostgreSQL server on a private subnet and configure the Container App Environments
# with a custom VNet so they reach the DB over a private endpoint (no public exposure at all).
# VNet integration requires recreating the Container App Environments, so it is deferred.
# Tracked in planning/15-infra-improvements.md.
resource "azurerm_postgresql_flexible_server_firewall_rule" "azure_services" {
  name             = "allow-azure-services"
  server_id        = azurerm_postgresql_flexible_server.tailord.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

resource "azurerm_postgresql_flexible_server_database" "prod" {
  name      = "tailord_prod"
  server_id = azurerm_postgresql_flexible_server.tailord.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

resource "azurerm_postgresql_flexible_server_database" "staging" {
  name      = "tailord_staging"
  server_id = azurerm_postgresql_flexible_server.tailord.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# -----------------------------
# CONTAINER APP ENVIRONMENTS
# Separate environments for prod and staging provide network-level isolation:
# staging apps cannot reach prod internal services even if misconfigured.
# Internal DNS routes frontend→backend within each environment.
# Both environments share one Log Analytics workspace (filter by app name/env).
# -----------------------------
resource "azurerm_container_app_environment" "prod" {
  name                       = "${var.project_name}-env-prod"
  resource_group_name        = azurerm_resource_group.tailord.name
  location                   = azurerm_resource_group.tailord.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.tailord.id
  tags                       = local.tags
}

resource "azurerm_container_app_environment" "staging" {
  name                       = "${var.project_name}-env-staging"
  resource_group_name        = azurerm_resource_group.tailord.name
  location                   = azurerm_resource_group.tailord.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.tailord.id
  tags                       = local.tags
}

# Grant managed identity permission to pull images from ACR
resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.tailord.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.apps.principal_id
}

# -----------------------------
# CONTAINER APP — BACKEND (PROD)
# -----------------------------
resource "azurerm_container_app" "backend_prod" {
  name                         = "${var.project_name}-backend-prod"
  resource_group_name          = azurerm_resource_group.tailord.name
  container_app_environment_id = azurerm_container_app_environment.prod.id
  revision_mode                = "Multiple"
  tags                         = local.tags

  lifecycle {
    ignore_changes = [
      template[0].container[0].image,
      ingress[0].traffic_weight,
    ]
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.apps.id]
  }

  template {
    max_replicas = 1

    http_scale_rule {
      name                = "http-scaling"
      concurrent_requests = 10
    }

    container {
      name   = "backend"
      image  = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name        = "DATABASE_URL"
        secret_name = "prod-database-url"
      }
      env {
        name        = "API_KEY"
        secret_name = "prod-api-key"
      }
      env {
        name  = "ENVIRONMENT"
        value = "production"
      }
      env {
        name  = "LOG_LEVEL"
        value = var.log_level
      }
      env {
        name  = "STORAGE_PROVIDER"
        value = "azure"
      }
      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.apps.client_id
      }
      env {
        name  = "AZURE_STORAGE_ACCOUNT_NAME"
        value = azurerm_storage_account.uploads_prod.name
      }
      env {
        name  = "AZURE_STORAGE_CONTAINER"
        value = azurerm_storage_container.uploads_prod.name
      }
      env {
        name  = "LLM_BASE_URL"
        value = "${local.openai_endpoint}openai/v1/"
      }
      env {
        name  = "LLM_MODEL"
        value = var.llm_model
      }
      env {
        name  = "LLM_API_VERSION"
        value = var.llm_api_version
      }
      env {
        name        = "NOTION_CLIENT_ID"
        secret_name = "prod-notion-client-id"
      }
      env {
        name        = "NOTION_CLIENT_SECRET"
        secret_name = "prod-notion-client-secret"
      }
      env {
        name  = "NOTION_REDIRECT_URI"
        value = "https://${var.domain_name}/api/auth/notion/callback"
      }
    }
  }

  ingress {
    external_enabled = false
    target_port      = 8000

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  registry {
    server   = azurerm_container_registry.tailord.login_server
    identity = azurerm_user_assigned_identity.apps.id
  }

  secret {
    name                = "prod-database-url"
    key_vault_secret_id = azurerm_key_vault_secret.prod_database_url.versionless_id
    identity            = azurerm_user_assigned_identity.apps.id
  }
  secret {
    name                = "prod-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.prod_api_key.versionless_id
    identity            = azurerm_user_assigned_identity.apps.id
  }
  secret {
    name                = "prod-notion-client-id"
    key_vault_secret_id = azurerm_key_vault_secret.prod_notion_client_id.versionless_id
    identity            = azurerm_user_assigned_identity.apps.id
  }
  secret {
    name                = "prod-notion-client-secret"
    key_vault_secret_id = azurerm_key_vault_secret.prod_notion_client_secret.versionless_id
    identity            = azurerm_user_assigned_identity.apps.id
  }
}

# -----------------------------
# CONTAINER APP — BACKEND (STAGING)
# Separate app — always uses staging DB and staging storage.
# Scales to 0 when idle; costs nothing between deployments.
# -----------------------------
resource "azurerm_container_app" "backend_staging" {
  name                         = "${var.project_name}-backend-staging"
  resource_group_name          = azurerm_resource_group.tailord.name
  container_app_environment_id = azurerm_container_app_environment.staging.id
  revision_mode                = "Multiple"
  tags                         = local.tags

  lifecycle {
    ignore_changes = [
      template[0].container[0].image,
      ingress[0].traffic_weight,
    ]
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.apps.id]
  }

  template {
    max_replicas = 1

    http_scale_rule {
      name                = "http-scaling"
      concurrent_requests = 10
    }

    container {
      name   = "backend"
      image  = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name        = "DATABASE_URL"
        secret_name = "staging-database-url"
      }
      env {
        name        = "API_KEY"
        secret_name = "staging-api-key"
      }
      env {
        name  = "ENVIRONMENT"
        value = "staging"
      }
      env {
        name  = "LOG_LEVEL"
        value = var.log_level
      }
      env {
        name  = "STORAGE_PROVIDER"
        value = "azure"
      }
      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.apps.client_id
      }
      env {
        name  = "AZURE_STORAGE_ACCOUNT_NAME"
        value = azurerm_storage_account.uploads_staging.name
      }
      env {
        name  = "AZURE_STORAGE_CONTAINER"
        value = azurerm_storage_container.uploads_staging.name
      }
      env {
        name  = "LLM_BASE_URL"
        value = "${local.openai_endpoint}openai/v1/"
      }
      env {
        name  = "LLM_MODEL"
        value = var.llm_model
      }
      env {
        name  = "LLM_API_VERSION"
        value = var.llm_api_version
      }
      env {
        name        = "NOTION_CLIENT_ID"
        secret_name = "staging-notion-client-id"
      }
      env {
        name        = "NOTION_CLIENT_SECRET"
        secret_name = "staging-notion-client-secret"
      }
      env {
        name  = "NOTION_REDIRECT_URI"
        value = "https://staging.${var.domain_name}/api/auth/notion/callback"
      }
    }
  }

  ingress {
    external_enabled = false
    target_port      = 8000

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  registry {
    server   = azurerm_container_registry.tailord.login_server
    identity = azurerm_user_assigned_identity.apps.id
  }

  secret {
    name                = "staging-database-url"
    key_vault_secret_id = azurerm_key_vault_secret.staging_database_url.versionless_id
    identity            = azurerm_user_assigned_identity.apps.id
  }
  secret {
    name                = "staging-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.staging_api_key.versionless_id
    identity            = azurerm_user_assigned_identity.apps.id
  }
  secret {
    name                = "staging-notion-client-id"
    key_vault_secret_id = azurerm_key_vault_secret.staging_notion_client_id.versionless_id
    identity            = azurerm_user_assigned_identity.apps.id
  }
  secret {
    name                = "staging-notion-client-secret"
    key_vault_secret_id = azurerm_key_vault_secret.staging_notion_client_secret.versionless_id
    identity            = azurerm_user_assigned_identity.apps.id
  }
}

# -----------------------------
# CONTAINER APP — FRONTEND (PROD)
# -----------------------------
resource "azurerm_container_app" "frontend_prod" {
  name                         = "${var.project_name}-frontend-prod"
  resource_group_name          = azurerm_resource_group.tailord.name
  container_app_environment_id = azurerm_container_app_environment.prod.id
  revision_mode                = "Multiple"
  tags                         = local.tags

  lifecycle {
    ignore_changes = [
      template[0].container[0].image,
      ingress[0].traffic_weight,
    ]
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.apps.id]
  }

  template {
    container {
      name   = "frontend"
      image  = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "NEXT_PUBLIC_API_URL"
        value = "https://${azurerm_container_app.backend_prod.ingress[0].fqdn}"
      }
      env {
        name  = "API_BASE_URL"
        value = "https://${azurerm_container_app.backend_prod.ingress[0].fqdn}"
      }
      env {
        name        = "API_KEY"
        secret_name = "prod-api-key"
      }
      env {
        name  = "NEXTAUTH_URL"
        value = "https://${var.domain_name}"
      }
      env {
        name        = "NEXTAUTH_SECRET"
        secret_name = "prod-nextauth-secret"
      }
      env {
        name        = "GOOGLE_CLIENT_ID"
        secret_name = "prod-google-client-id"
      }
      env {
        name        = "GOOGLE_CLIENT_SECRET"
        secret_name = "prod-google-client-secret"
      }
    }
  }

  ingress {
    external_enabled = true
    target_port      = 3000

    dynamic "ip_security_restriction" {
      for_each = data.cloudflare_ip_ranges.cloudflare.ipv4_cidrs
      content {
        name             = "cloudflare-${ip_security_restriction.key}"
        action           = "Allow"
        ip_address_range = ip_security_restriction.value
      }
    }

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  registry {
    server   = azurerm_container_registry.tailord.login_server
    identity = azurerm_user_assigned_identity.apps.id
  }

  secret {
    name                = "prod-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.prod_api_key.versionless_id
    identity            = azurerm_user_assigned_identity.apps.id
  }
  secret {
    name                = "prod-nextauth-secret"
    key_vault_secret_id = azurerm_key_vault_secret.prod_nextauth_secret.versionless_id
    identity            = azurerm_user_assigned_identity.apps.id
  }
  secret {
    name                = "prod-google-client-id"
    key_vault_secret_id = azurerm_key_vault_secret.prod_google_client_id.versionless_id
    identity            = azurerm_user_assigned_identity.apps.id
  }
  secret {
    name                = "prod-google-client-secret"
    key_vault_secret_id = azurerm_key_vault_secret.prod_google_client_secret.versionless_id
    identity            = azurerm_user_assigned_identity.apps.id
  }
}

# -----------------------------
# CONTAINER APP — FRONTEND (STAGING)
# Separate app — always routes to the staging backend.
# Scales to 0 when idle; costs nothing between deployments.
# -----------------------------
resource "azurerm_container_app" "frontend_staging" {
  name                         = "${var.project_name}-frontend-staging"
  resource_group_name          = azurerm_resource_group.tailord.name
  container_app_environment_id = azurerm_container_app_environment.staging.id
  revision_mode                = "Multiple"
  tags                         = local.tags

  lifecycle {
    ignore_changes = [
      template[0].container[0].image,
      ingress[0].traffic_weight,
    ]
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.apps.id]
  }

  template {
    container {
      name   = "frontend"
      image  = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "NEXT_PUBLIC_API_URL"
        value = "https://${azurerm_container_app.backend_staging.ingress[0].fqdn}"
      }
      env {
        name  = "API_BASE_URL"
        value = "https://${azurerm_container_app.backend_staging.ingress[0].fqdn}"
      }
      env {
        name        = "API_KEY"
        secret_name = "staging-api-key"
      }
      env {
        name  = "NEXTAUTH_URL"
        value = "https://staging.${var.domain_name}"
      }
      env {
        name        = "NEXTAUTH_SECRET"
        secret_name = "staging-nextauth-secret"
      }
      env {
        name        = "GOOGLE_CLIENT_ID"
        secret_name = "staging-google-client-id"
      }
      env {
        name        = "GOOGLE_CLIENT_SECRET"
        secret_name = "staging-google-client-secret"
      }
    }
  }

  ingress {
    external_enabled = true
    target_port      = 3000

    dynamic "ip_security_restriction" {
      for_each = data.cloudflare_ip_ranges.cloudflare.ipv4_cidrs
      content {
        name             = "cloudflare-${ip_security_restriction.key}"
        action           = "Allow"
        ip_address_range = ip_security_restriction.value
      }
    }

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  registry {
    server   = azurerm_container_registry.tailord.login_server
    identity = azurerm_user_assigned_identity.apps.id
  }

  secret {
    name                = "staging-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.staging_api_key.versionless_id
    identity            = azurerm_user_assigned_identity.apps.id
  }
  secret {
    name                = "staging-nextauth-secret"
    key_vault_secret_id = azurerm_key_vault_secret.staging_nextauth_secret.versionless_id
    identity            = azurerm_user_assigned_identity.apps.id
  }
  secret {
    name                = "staging-google-client-id"
    key_vault_secret_id = azurerm_key_vault_secret.staging_google_client_id.versionless_id
    identity            = azurerm_user_assigned_identity.apps.id
  }
  secret {
    name                = "staging-google-client-secret"
    key_vault_secret_id = azurerm_key_vault_secret.staging_google_client_secret.versionless_id
    identity            = azurerm_user_assigned_identity.apps.id
  }
}

# -----------------------------
# CLOUDFLARE
# -----------------------------
data "cloudflare_ip_ranges" "cloudflare" {}

# -----------------------------
# CLOUDFLARE DNS
# -----------------------------
resource "cloudflare_dns_record" "app" {
  zone_id = var.cloudflare_zone_id
  name    = var.domain_name
  content = azurerm_container_app.frontend_prod.ingress[0].fqdn
  type    = "CNAME"
  proxied = true
  ttl     = 1
}

resource "cloudflare_dns_record" "www" {
  zone_id = var.cloudflare_zone_id
  name    = "www"
  content = var.domain_name
  type    = "CNAME"
  proxied = true
  ttl     = 1
}

resource "cloudflare_dns_record" "staging" {
  zone_id = var.cloudflare_zone_id
  name    = "staging"
  content = azurerm_container_app.frontend_staging.ingress[0].fqdn
  type    = "CNAME"
  proxied = true
  ttl     = 1
}

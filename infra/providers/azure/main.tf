# -----------------------------
# RESOURCE GROUP
# -----------------------------
resource "azurerm_resource_group" "tailord" {
  name     = var.project_name
  location = var.location
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
}

# -----------------------------
# STORAGE
# -----------------------------
resource "azurerm_storage_account" "uploads" {
  name                     = "${replace(var.project_name, "-", "")}uploads"
  resource_group_name      = azurerm_resource_group.tailord.name
  location                 = azurerm_resource_group.tailord.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  blob_properties {
    cors_rule {
      allowed_headers    = ["*"]
      allowed_methods    = ["PUT"]
      allowed_origins    = ["https://${var.domain_name}", "https://www.${var.domain_name}", "http://localhost:3000"]
      exposed_headers    = ["*"]
      max_age_in_seconds = 3000
    }
  }
}

resource "azurerm_storage_container" "uploads" {
  name               = "${var.project_name}-uploads"
  storage_account_id = azurerm_storage_account.uploads.id
}

# -----------------------------
# POSTGRESQL FLEXIBLE SERVER
# -----------------------------
resource "azurerm_postgresql_flexible_server" "tailord" {
  name                   = "${var.project_name}-db"
  resource_group_name    = azurerm_resource_group.tailord.name
  location               = azurerm_resource_group.tailord.location
  version                = "16"
  administrator_login    = "tailord"
  administrator_password = var.db_password
  sku_name               = "B_Standard_B1ms"
  storage_mb             = 32768
  zone                   = "1"
}

resource "azurerm_postgresql_flexible_server_firewall_rule" "azure_services" {
  name             = "allow-azure-services"
  server_id        = azurerm_postgresql_flexible_server.tailord.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

resource "azurerm_postgresql_flexible_server_database" "tailord" {
  name      = "tailord"
  server_id = azurerm_postgresql_flexible_server.tailord.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# -----------------------------
# CONTAINER APP ENVIRONMENT
# -----------------------------
resource "azurerm_container_app_environment" "tailord" {
  name                = "${var.project_name}-env"
  resource_group_name = azurerm_resource_group.tailord.name
  location            = azurerm_resource_group.tailord.location
}

# Grant managed identity permission to pull images from ACR
resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.tailord.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.container_apps.principal_id
}

# -----------------------------
# CONTAINER APP — BACKEND
# -----------------------------
resource "azurerm_container_app" "backend" {
  name                         = "${var.project_name}-backend"
  resource_group_name          = azurerm_resource_group.tailord.name
  container_app_environment_id = azurerm_container_app_environment.tailord.id
  revision_mode                = "Single"

  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.container_apps.id]
  }

  template {
    container {
      name   = "backend"
      image  = "${azurerm_container_registry.tailord.login_server}/${var.project_name}-backend:latest"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name        = "API_KEY"
        secret_name = "api-key"
      }
      env {
        name  = "STORAGE_PROVIDER"
        value = "azure"
      }
      env {
        name        = "AZURE_STORAGE_CONNECTION_STRING"
        secret_name = "storage-connection-string"
      }
      env {
        name  = "AZURE_STORAGE_CONTAINER"
        value = azurerm_storage_container.uploads.name
      }
      env {
        name  = "LLM_MODEL"
        value = var.llm_model
      }
      env {
        name        = "LLM_API_KEY"
        secret_name = "llm-api-key"
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
    identity = azurerm_user_assigned_identity.container_apps.id
  }

  secret {
    name                = "database-url"
    key_vault_secret_id = azurerm_key_vault_secret.database_url.versionless_id
    identity            = azurerm_user_assigned_identity.container_apps.id
  }

  secret {
    name                = "api-key"
    key_vault_secret_id = azurerm_key_vault_secret.api_key.versionless_id
    identity            = azurerm_user_assigned_identity.container_apps.id
  }

  secret {
    name                = "storage-connection-string"
    key_vault_secret_id = azurerm_key_vault_secret.storage_connection_string.versionless_id
    identity            = azurerm_user_assigned_identity.container_apps.id
  }

  secret {
    name                = "llm-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.llm_api_key.versionless_id
    identity            = azurerm_user_assigned_identity.container_apps.id
  }
}

# -----------------------------
# CONTAINER APP — FRONTEND
# -----------------------------
resource "azurerm_container_app" "frontend" {
  name                         = "${var.project_name}-frontend"
  resource_group_name          = azurerm_resource_group.tailord.name
  container_app_environment_id = azurerm_container_app_environment.tailord.id
  revision_mode                = "Single"

  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.container_apps.id]
  }

  template {
    container {
      name   = "frontend"
      image  = "${azurerm_container_registry.tailord.login_server}/${var.project_name}-frontend:latest"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "NEXT_PUBLIC_API_URL"
        value = "https://${azurerm_container_app.backend.ingress[0].fqdn}"
      }
      env {
        name  = "API_BASE_URL"
        value = "https://${azurerm_container_app.backend.ingress[0].fqdn}"
      }
      env {
        name        = "API_KEY"
        secret_name = "api-key"
      }
      env {
        name  = "NEXTAUTH_URL"
        value = "https://${var.project_name}-frontend.${azurerm_container_app_environment.tailord.default_domain}"
      }
      env {
        name  = "NEXTAUTH_URL_INTERNAL"
        value = "http://localhost:3000"
      }
      env {
        name        = "NEXTAUTH_SECRET"
        secret_name = "nextauth-secret"
      }
      env {
        name        = "GOOGLE_CLIENT_ID"
        secret_name = "google-client-id"
      }
      env {
        name        = "GOOGLE_CLIENT_SECRET"
        secret_name = "google-client-secret"
      }
    }
  }

  ingress {
    external_enabled = true
    target_port      = 3000

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  registry {
    server   = azurerm_container_registry.tailord.login_server
    identity = azurerm_user_assigned_identity.container_apps.id
  }

  secret {
    name                = "api-key"
    key_vault_secret_id = azurerm_key_vault_secret.api_key.versionless_id
    identity            = azurerm_user_assigned_identity.container_apps.id
  }

  secret {
    name                = "nextauth-secret"
    key_vault_secret_id = azurerm_key_vault_secret.nextauth_secret.versionless_id
    identity            = azurerm_user_assigned_identity.container_apps.id
  }

  secret {
    name                = "google-client-id"
    key_vault_secret_id = azurerm_key_vault_secret.google_client_id.versionless_id
    identity            = azurerm_user_assigned_identity.container_apps.id
  }

  secret {
    name                = "google-client-secret"
    key_vault_secret_id = azurerm_key_vault_secret.google_client_secret.versionless_id
    identity            = azurerm_user_assigned_identity.container_apps.id
  }
}

# -----------------------------
# CLOUDFLARE (disabled — re-enable when adding custom domain)
# -----------------------------
# data "cloudflare_ip_ranges" "cloudflare" {}
#

# -----------------------------
# CLOUDFLARE DNS
# -----------------------------
resource "cloudflare_dns_record" "app" {
  zone_id = var.cloudflare_zone_id
  name    = var.domain_name
  content = azurerm_container_app.frontend.ingress[0].fqdn
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

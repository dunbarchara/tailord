# -----------------------------
# APPLICATION INSIGHTS
# -----------------------------
resource "azurerm_application_insights" "tailord" {
  name                = "${var.project_name}-appinsights"
  resource_group_name = azurerm_resource_group.tailord.name
  location            = azurerm_resource_group.tailord.location
  workspace_id        = azurerm_log_analytics_workspace.tailord.id
  application_type    = "web"
  tags                = local.tags
}

output "appinsights_connection_string" {
  value     = azurerm_application_insights.tailord.connection_string
  sensitive = true
}

# Store connection string in Key Vault so it can be injected into the backend
# Container App as a secret (pattern mirrors existing secrets in main.tf).
resource "azurerm_key_vault_secret" "appinsights_connection_string" {
  name         = "appinsights-connection-string"
  value        = azurerm_application_insights.tailord.connection_string
  content_type = "text/plain"
  key_vault_id = azurerm_key_vault.tailord.id

  depends_on = [azurerm_role_assignment.kv_secrets_officer]
}

# -----------------------------
# LOG ANALYTICS WORKSPACE
# -----------------------------
resource "azurerm_log_analytics_workspace" "tailord" {
  name                = "${var.project_name}-logs"
  resource_group_name = azurerm_resource_group.tailord.name
  location            = azurerm_resource_group.tailord.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  daily_quota_gb      = 2
  tags                = local.tags
}

# -----------------------------
# AZURE MANAGED PROMETHEUS
# -----------------------------
resource "azurerm_monitor_workspace" "main" {
  name                = "${var.project_name}-amp"
  resource_group_name = azurerm_resource_group.tailord.name
  location            = azurerm_resource_group.tailord.location
}

# -----------------------------
# AZURE MANAGED GRAFANA
# -----------------------------
resource "azurerm_dashboard_grafana" "main" {
  name                = "${var.project_name}-grafana"
  resource_group_name = azurerm_resource_group.tailord.name
  location            = azurerm_resource_group.tailord.location
  grafana_major_version = 12
  api_key_enabled     = true

  identity {
    type = "SystemAssigned"
  }

  azure_monitor_workspace_integrations {
    resource_id = azurerm_monitor_workspace.main.id
  }
}

resource "azurerm_role_assignment" "grafana_admin" {
  scope                = azurerm_dashboard_grafana.main.id
  role_definition_name = "Grafana Admin"
  principal_id         = var.grafana_admin_object_id
}

resource "azurerm_role_assignment" "grafana_monitoring_reader" {
  scope                = azurerm_resource_group.tailord.id
  role_definition_name = "Monitoring Reader"
  principal_id         = azurerm_dashboard_grafana.main.identity[0].principal_id
}

resource "azurerm_role_assignment" "grafana_log_analytics_reader" {
  scope                = azurerm_log_analytics_workspace.tailord.id
  role_definition_name = "Log Analytics Reader"
  principal_id         = azurerm_dashboard_grafana.main.identity[0].principal_id
}

# -----------------------------
# ACTION GROUP
# -----------------------------
resource "azurerm_monitor_action_group" "ops_email" {
  name                = "${var.project_name}-ops-alerts"
  resource_group_name = azurerm_resource_group.tailord.name
  short_name          = "tailord-ops"
  tags                = local.tags

  email_receiver {
    name                    = "ops-team"
    email_address           = var.alert_email
    use_common_alert_schema = true
  }
}

# -----------------------------
# METRIC ALERTS
# -----------------------------

resource "azurerm_monitor_metric_alert" "container_restart" {
  name                = "${var.project_name}-container-restart"
  resource_group_name = azurerm_resource_group.tailord.name
  scopes              = [azurerm_container_app.backend_prod.id]
  description         = "Backend container restarted"
  severity            = 1
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "microsoft.app/containerapps"
    metric_name      = "RestartCount"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 0
  }

  action { action_group_id = azurerm_monitor_action_group.ops_email.id }
}

resource "azurerm_monitor_metric_alert" "memory_pressure" {
  name                = "${var.project_name}-memory-pressure"
  resource_group_name = azurerm_resource_group.tailord.name
  scopes              = [azurerm_container_app.backend_prod.id]
  description         = "Backend memory above 860 MiB (85% of 1 GiB limit)"
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "microsoft.app/containerapps"
    metric_name      = "WorkingSetBytes"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 900000000
  }

  action { action_group_id = azurerm_monitor_action_group.ops_email.id }
}

resource "azurerm_monitor_metric_alert" "no_healthy_replicas" {
  name                = "${var.project_name}-no-healthy-replicas"
  resource_group_name = azurerm_resource_group.tailord.name
  scopes              = [azurerm_container_app.backend_prod.id]
  description         = "Backend has zero running replicas — likely health check failure"
  severity            = 0
  frequency           = "PT1M"
  window_size         = "PT5M"

  criteria {
    metric_namespace = "microsoft.app/containerapps"
    metric_name      = "Replicas"
    aggregation      = "Average"
    operator         = "LessThan"
    threshold        = 1
  }

  action { action_group_id = azurerm_monitor_action_group.ops_email.id }
}

# -----------------------------
# LOG SEARCH ALERTS
# -----------------------------

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "backend_error_rate" {
  name                = "${var.project_name}-backend-error-rate"
  resource_group_name = azurerm_resource_group.tailord.name
  location            = azurerm_resource_group.tailord.location
  scopes              = [azurerm_log_analytics_workspace.tailord.id]
  evaluation_frequency = "PT5M"
  window_duration      = "PT15M"
  severity             = 1
  description          = "5xx error rate above 5% over at least 10 requests"

  criteria {
    query = <<-QUERY
      ContainerAppConsoleLogs_CL
      | where TimeGenerated > ago(15m)
      | where ContainerAppName_s contains "backend-prod"
      | extend p = parse_json(Log_s)
      | where tostring(p.event) == "request_complete"
      | summarize total = count(), errors = countif(toint(p.status_code) >= 500)
      | where total > 10 and (100.0 * errors / total) > 5
    QUERY
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"
    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action { action_groups = [azurerm_monitor_action_group.ops_email.id] }
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "llm_timeout_spike" {
  name                = "${var.project_name}-llm-timeout-spike"
  resource_group_name = azurerm_resource_group.tailord.name
  location            = azurerm_resource_group.tailord.location
  scopes              = [azurerm_log_analytics_workspace.tailord.id]
  evaluation_frequency = "PT5M"
  window_duration      = "PT15M"
  severity             = 1
  description          = "More than 3 LLM errors in 15 minutes"

  criteria {
    query = <<-QUERY
      ContainerAppConsoleLogs_CL
      | where TimeGenerated > ago(15m)
      | where ContainerAppName_s contains "backend-prod"
      | extend p = parse_json(Log_s)
      | where tostring(p.level) == "ERROR"
            and (tostring(p.event) contains "llm" or tostring(p.event) == "llm_error")
      | count
    QUERY
    time_aggregation_method = "Count"
    threshold               = 3
    operator                = "GreaterThan"
    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action { action_groups = [azurerm_monitor_action_group.ops_email.id] }
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "generation_failure_spike" {
  name                = "${var.project_name}-generation-failure-spike"
  resource_group_name = azurerm_resource_group.tailord.name
  location            = azurerm_resource_group.tailord.location
  scopes              = [azurerm_log_analytics_workspace.tailord.id]
  evaluation_frequency = "PT5M"
  window_duration      = "PT30M"
  severity             = 1
  description          = "More than 5 generation errors in 30 minutes"

  criteria {
    query = <<-QUERY
      ContainerAppConsoleLogs_CL
      | where TimeGenerated > ago(30m)
      | where ContainerAppName_s contains "backend-prod"
      | extend p = parse_json(Log_s)
      | where tostring(p.level) == "ERROR"
            and (tostring(p.event) == "generation_error"
                 or tostring(p.event) == "phase_error")
      | count
    QUERY
    time_aggregation_method = "Count"
    threshold               = 5
    operator                = "GreaterThan"
    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action { action_groups = [azurerm_monitor_action_group.ops_email.id] }
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "log_analytics_quota" {
  name                = "${var.project_name}-log-analytics-quota"
  resource_group_name = azurerm_resource_group.tailord.name
  location            = azurerm_resource_group.tailord.location
  scopes              = [azurerm_log_analytics_workspace.tailord.id]
  evaluation_frequency = "PT1H"
  window_duration      = "PT1H"
  severity             = 2
  description          = "Log Analytics daily ingestion quota reached"

  criteria {
    query = <<-QUERY
      Operation
      | where OperationCategory == "Data ingestion"
      | where Detail has "quota"
    QUERY
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"
    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action { action_groups = [azurerm_monitor_action_group.ops_email.id] }
}

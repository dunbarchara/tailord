locals {
  tags = {
    project    = var.project_name
    managed_by = "terraform"
  }

  # OTLP metrics ingestion endpoint for Azure Managed Prometheus.
  # query_endpoint is the only hostname attribute exported by azurerm_monitor_workspace;
  # the ingestion path is /dataingestion/ on the same host. OTel SDK appends /v1/metrics,
  # producing: {query_endpoint}/dataingestion/opentelemetry/api/v1/metrics
  amp_otlp_endpoint = "${trimsuffix(azurerm_monitor_workspace.main.query_endpoint, "/")}/dataingestion/opentelemetry/api"
}

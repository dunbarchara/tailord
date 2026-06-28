from opentelemetry import metrics, trace


def setup_telemetry() -> None:
    """
    Configure OpenTelemetry based on environment.

    local:              traces → OTLP gRPC → Tempo; metrics → Prometheus pull (/metrics)
    staging/production: traces → Azure Monitor (App Insights); metrics → OTLP HTTP → AMP
    other/unconfigured: no-op

    Must be called once at process startup, before any module that creates OTel
    metric instruments (i.e. metrics.py) is imported.
    """
    from app.config import settings

    # Metrics must be set up first: OTel SDK silently ignores a second
    # set_meter_provider() call, so whichever runs first wins. We want AMP,
    # not Azure Monitor, so _setup_metrics must precede configure_azure_monitor.
    _setup_metrics(settings)
    _setup_traces(settings)


def _setup_traces(settings) -> None:
    if settings.environment == "local" and settings.otel_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({SERVICE_NAME: "tailord-backend"})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

    elif settings.applicationinsights_connection_string:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(
            connection_string=settings.applicationinsights_connection_string,
            service_name="tailord-backend",
        )


def _setup_metrics(settings) -> None:
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource

    resource = Resource.create({SERVICE_NAME: "tailord-backend"})

    if settings.environment == "local":
        # PrometheusMetricReader registers an OTel collector into prometheus_client's
        # default REGISTRY, so the existing make_asgi_app() /metrics endpoint
        # automatically exposes all OTel metrics in Prometheus text format.
        from opentelemetry.exporter.prometheus import PrometheusMetricReader

        reader = PrometheusMetricReader()
        provider = MeterProvider(resource=resource, metric_readers=[reader])

    elif settings.amp_endpoint:
        from azure.identity import ManagedIdentityCredential
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

        credential = ManagedIdentityCredential(client_id=settings.azure_client_id)

        AzureAMPExporter = _make_azure_amp_exporter_class()
        reader = PeriodicExportingMetricReader(
            AzureAMPExporter(endpoint=settings.amp_endpoint, credential=credential),
            export_interval_millis=60_000,  # push every 60 seconds
        )
        provider = MeterProvider(resource=resource, metric_readers=[reader])

    else:
        return

    metrics.set_meter_provider(provider)


def _make_azure_amp_exporter_class():
    """Build _AzureAMPExporter inheriting from MetricExporter at call time.

    Deferred so telemetry.py is importable even if OTel SDK isn't installed
    (e.g. stripped test images). Called once in _setup_metrics when AMP is needed.
    """
    from opentelemetry.sdk.metrics.export import MetricExporter

    class _AzureAMPExporter(MetricExporter):
        """OTLP metric exporter with Azure AD managed identity auth for AMP.

        Calls credential.get_token() before each export. azure-identity caches the
        token internally and silently refreshes it ~5 minutes before expiry, so this
        adds negligible overhead per export cycle.

        A new inner OTLPMetricExporter is created only when the token changes
        (approximately once per hour).

        Inherits MetricExporter so PeriodicExportingMetricReader can read
        _preferred_temporality/_preferred_aggregation from the base class __init__.
        """

        def __init__(self, endpoint: str, credential) -> None:
            super().__init__()
            self._endpoint = endpoint
            self._credential = credential
            self._inner = None
            self._token_expiry: int = 0

        def _get_inner(self):
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

            token = self._credential.get_token("https://monitor.azure.com/.default")
            if token.expires_on != self._token_expiry or self._inner is None:
                self._token_expiry = token.expires_on
                self._inner = OTLPMetricExporter(
                    endpoint=self._endpoint,
                    headers={"Authorization": f"Bearer {token.token}"},
                )
            return self._inner

        def export(self, metrics_data, timeout_millis=10_000, **kwargs):
            return self._get_inner().export(metrics_data, timeout_millis=timeout_millis, **kwargs)

        def force_flush(self, timeout_millis=10_000):
            return True

        def shutdown(self, timeout_millis=30_000, **kwargs):
            if self._inner:
                return self._inner.shutdown(timeout_millis=timeout_millis, **kwargs)
            return True

    return _AzureAMPExporter


def get_tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)

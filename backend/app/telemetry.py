from opentelemetry import trace


def setup_telemetry() -> None:
    """
    Configure OpenTelemetry based on environment.

    local:              OTLP gRPC → Tempo (docker-compose)
    staging/production: Azure Monitor → Application Insights via distro
    other/unconfigured: no-op

    Must be called once at process startup, before any spans are created.
    """
    from app.config import settings

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


def get_tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)

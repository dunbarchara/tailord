from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def setup_telemetry() -> None:
    """
    Configure the OpenTelemetry tracer provider based on environment.

    local:              OTLP gRPC → Tempo (docker-compose)
    staging/production: Azure Monitor → Application Insights (via connection string)
    other/unconfigured: no-op (telemetry disabled)

    Must be called once at process startup, before any spans are created.
    """
    from app.config import settings

    resource = Resource.create({SERVICE_NAME: "tailord-backend"})
    provider = TracerProvider(resource=resource)

    if settings.environment == "local" and settings.otel_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint, insecure=True)
    elif settings.applicationinsights_connection_string:
        from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

        exporter = AzureMonitorTraceExporter(
            connection_string=settings.applicationinsights_connection_string
        )
    else:
        return  # no-op: no tracing configured for this environment

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


def get_tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)

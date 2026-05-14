/**
 * Next.js instrumentation hook — runs once at server startup.
 * Initialises the OpenTelemetry Node SDK to send traces to the configured
 * OTLP HTTP endpoint (local Tempo or Azure Application Insights via the
 * OTEL_EXPORTER_OTLP_ENDPOINT environment variable).
 *
 * Uses sdk-trace-node (tracing-only) rather than sdk-node so we don't pull
 * in the metrics SDK and its Prometheus exporter (GHSA-q7rr-3cgh-j5r3).
 *
 * Guarded to the Node.js runtime so it never runs in the Edge runtime.
 */
export async function register() {
  if (process.env.NEXT_RUNTIME === 'nodejs') {
    const { NodeTracerProvider, BatchSpanProcessor } = await import(
      '@opentelemetry/sdk-trace-node'
    );
    const { OTLPTraceExporter } = await import(
      '@opentelemetry/exporter-trace-otlp-http'
    );
    const { Resource } = await import('@opentelemetry/resources');
    const { SEMRESATTRS_SERVICE_NAME } = await import(
      '@opentelemetry/semantic-conventions'
    );

    const exporter = new OTLPTraceExporter({
      url:
        process.env.OTEL_EXPORTER_OTLP_ENDPOINT ??
        'http://localhost:4318/v1/traces',
    });

    const provider = new NodeTracerProvider({
      resource: new Resource({
        [SEMRESATTRS_SERVICE_NAME]: 'tailord-frontend',
      }),
    });

    provider.addSpanProcessor(new BatchSpanProcessor(exporter));
    provider.register();
  }
}

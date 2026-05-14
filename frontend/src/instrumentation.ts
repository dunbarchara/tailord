/**
 * Next.js instrumentation hook — runs once at server startup.
 * Initialises the OpenTelemetry Node SDK to send traces to the configured
 * OTLP HTTP endpoint (local Tempo or Azure Application Insights via the
 * OTEL_EXPORTER_OTLP_ENDPOINT environment variable).
 *
 * Guarded to the Node.js runtime so it never runs in the Edge runtime.
 */
export async function register() {
  if (process.env.NEXT_RUNTIME === 'nodejs') {
    const { NodeSDK } = await import('@opentelemetry/sdk-node');
    const { OTLPTraceExporter } = await import(
      '@opentelemetry/exporter-trace-otlp-http'
    );
    const { Resource } = await import('@opentelemetry/resources');
    const { SEMRESATTRS_SERVICE_NAME } = await import(
      '@opentelemetry/semantic-conventions'
    );

    const sdk = new NodeSDK({
      resource: new Resource({
        [SEMRESATTRS_SERVICE_NAME]: 'tailord-frontend',
      }),
      traceExporter: new OTLPTraceExporter({
        url:
          process.env.OTEL_EXPORTER_OTLP_ENDPOINT ??
          'http://localhost:4318/v1/traces',
      }),
    });

    sdk.start();
  }
}

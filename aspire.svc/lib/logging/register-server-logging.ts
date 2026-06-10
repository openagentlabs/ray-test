import { logs } from "@opentelemetry/api-logs";
import {
  ATTR_SERVICE_INSTANCE_ID,
  ATTR_SERVICE_NAME,
} from "@opentelemetry/semantic-conventions";
import { resourceFromAttributes } from "@opentelemetry/resources";
import {
  BatchLogRecordProcessor,
  ConsoleLogRecordExporter,
  LoggerProvider,
} from "@opentelemetry/sdk-logs";

import { LoggingConfigFactory } from "@/lib/config/logging-config";
import { CloudWatchLogRecordExporter } from "@/lib/logging/cloudwatch-log-exporter";
import { NoopLogRecordExporter } from "@/lib/logging/noop-log-record-exporter";
import { applicationLogLevelToMinimumSeverity } from "@/lib/logging/severity-map";

type GlobalWithLoggerProvider = typeof globalThis & {
  __ARB_ASPIRE_OTEL_LOGGER_PROVIDER__?: LoggerProvider;
};

const globalWithLogger = globalThis as GlobalWithLoggerProvider;

/**
 * Initializes the OpenTelemetry Logs SDK on the Node.js server using
 * {@link BatchLogRecordProcessor} (async batching, non-blocking export path).
 *
 * Called from root `instrumentation.ts` once per server process.
 */
export function registerServerLogging(): void {
  if (globalWithLogger.__ARB_ASPIRE_OTEL_LOGGER_PROVIDER__ !== undefined) {
    return;
  }

  const config = LoggingConfigFactory.fromEnvironment();
  if (!config.enabled) {
    return;
  }

  const processors = [];

  if (config.exportConsole) {
    processors.push(
      new BatchLogRecordProcessor(new ConsoleLogRecordExporter(), {
        maxExportBatchSize: 512,
        scheduledDelayMillis: 2_000,
        exportTimeoutMillis: 30_000,
        maxQueueSize: 2048,
      }),
    );
  }

  if (config.cloudWatch.enabled) {
    processors.push(
      new BatchLogRecordProcessor(
        new CloudWatchLogRecordExporter({
          region: config.cloudWatch.region,
          logGroupName: config.cloudWatch.logGroupName,
          logStreamName: config.cloudWatch.logStreamName,
          serviceId: config.serviceId,
          serviceName: config.serviceName,
          serviceInstanceId: config.serviceInstanceId,
        }),
        {
          maxExportBatchSize: 256,
          scheduledDelayMillis: 2_000,
          exportTimeoutMillis: 30_000,
          maxQueueSize: 4096,
        },
      ),
    );
  }

  if (processors.length === 0) {
    processors.push(
      new BatchLogRecordProcessor(new NoopLogRecordExporter(), {
        maxExportBatchSize: 512,
        scheduledDelayMillis: 2_000,
        exportTimeoutMillis: 30_000,
        maxQueueSize: 2048,
      }),
    );
  }

  const minimumSeverity = applicationLogLevelToMinimumSeverity(config.logLevel);

  const resource = resourceFromAttributes({
    [ATTR_SERVICE_NAME]: config.serviceName,
    [ATTR_SERVICE_INSTANCE_ID]: config.serviceInstanceId,
    "service.id": config.serviceId,
  });

  const loggerProvider = new LoggerProvider({
    resource,
    processors,
    loggerConfigurator: () => ({
      disabled: false,
      minimumSeverity,
      traceBased: false,
    }),
  });

  globalWithLogger.__ARB_ASPIRE_OTEL_LOGGER_PROVIDER__ = loggerProvider;
  logs.setGlobalLoggerProvider(loggerProvider);
}

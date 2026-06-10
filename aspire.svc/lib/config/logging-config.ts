/**
 * Application logging configuration loaded from the environment.
 * OpenTelemetry Logs SDK reads this at server startup (see `instrumentation.ts`).
 * Defaults align with `terraform output` via `cloudwatch-logging.defaults.generated.ts`
 * (regenerate: `npm run sync:cloudwatch-logging` from `aspire.svc/`).
 */

import { CLOUDWATCH_TERRAFORM_DEFAULTS } from "@/lib/config/cloudwatch-logging.defaults.generated";

export type ApplicationLogLevel =
  | "trace"
  | "debug"
  | "info"
  | "warn"
  | "error"
  | "fatal";

export interface LoggingConfig {
  /** Master switch for server-side OpenTelemetry logging. */
  readonly enabled: boolean;
  /** Minimum severity emitted to processors (default `debug`). */
  readonly logLevel: ApplicationLogLevel;
  /** `service.name` resource attribute for all log records. */
  readonly serviceName: string;
  /**
   * `service.instance.id` resource attribute (unique per process / replica).
   * Included in CloudWatch JSON bodies for correlation.
   */
  readonly serviceInstanceId: string;
  /** Stable workload id (matches Terraform `service_identity_by_key.*.service_id`). */
  readonly serviceId: string;
  /** When true, records are also exported to stdout (structured JSON via OTel console exporter). */
  readonly exportConsole: boolean;
  readonly cloudWatch: LoggingCloudWatchConfig;
}

export interface LoggingCloudWatchConfig {
  readonly enabled: boolean;
  readonly region: string;
  readonly logGroupName: string;
  readonly logStreamName: string;
}

function readEnv(key: string): string | undefined {
  const value = process.env[key];
  if (value === undefined || value.length === 0) {
    return undefined;
  }
  return value;
}

function parseBoolean(raw: string | undefined, defaultValue: boolean): boolean {
  if (raw === undefined) {
    return defaultValue;
  }
  const normalized = raw.trim().toLowerCase();
  if (normalized === "1" || normalized === "true" || normalized === "yes") {
    return true;
  }
  if (normalized === "0" || normalized === "false" || normalized === "no") {
    return false;
  }
  return defaultValue;
}

function parseLogLevel(raw: string | undefined): ApplicationLogLevel {
  const normalized = raw?.trim().toLowerCase();
  if (
    normalized === "trace" ||
    normalized === "debug" ||
    normalized === "info" ||
    normalized === "warn" ||
    normalized === "error" ||
    normalized === "fatal"
  ) {
    return normalized;
  }
  return "debug";
}

export class LoggingConfigFactory {
  public static fromEnvironment(): LoggingConfig {
    const logStreamFromEnv = readEnv("CLOUDWATCH_LOG_STREAM_NAME");
    const tf = CLOUDWATCH_TERRAFORM_DEFAULTS;
    const defaultStreamName =
      logStreamFromEnv ??
      `${tf.logStreamPrefix}-${process.pid}-${Math.random().toString(36).slice(2, 10)}`;

    const cloudWatchEnabled = parseBoolean(
      readEnv("CLOUDWATCH_LOGS_ENABLED"),
      false,
    );

    const serviceName = readEnv("OTEL_SERVICE_NAME") ?? tf.otelServiceName;
    const serviceId = readEnv("SERVICE_ID") ?? tf.serviceId;
    const serviceInstanceId =
      readEnv("OTEL_SERVICE_INSTANCE_ID") ??
      readEnv("HOSTNAME") ??
      `proc-${process.pid}-${Math.random().toString(36).slice(2, 10)}`;

    return {
      enabled: parseBoolean(readEnv("LOG_ENABLED"), true),
      logLevel: parseLogLevel(readEnv("LOG_LEVEL")),
      serviceName,
      serviceId,
      serviceInstanceId,
      exportConsole: parseBoolean(readEnv("LOG_EXPORT_CONSOLE"), false),
      cloudWatch: {
        enabled: cloudWatchEnabled,
        region: readEnv("CLOUDWATCH_LOGS_REGION") ?? tf.awsRegion,
        logGroupName: readEnv("CLOUDWATCH_LOG_GROUP_NAME") ?? tf.logGroupName,
        logStreamName: defaultStreamName,
      },
    };
  }

  public static forTests(overrides?: Partial<LoggingConfig>): LoggingConfig {
    const base: LoggingConfig = {
      enabled: true,
      logLevel: "debug",
      serviceName: "arb-aspire-test",
      serviceId: "arb-aspire-test",
      serviceInstanceId: "test-instance",
      exportConsole: false,
      cloudWatch: {
        enabled: false,
        region: "us-east-1",
        logGroupName: "/test/app",
        logStreamName: "test-stream",
      },
    };
    return {
      ...base,
      ...overrides,
      cloudWatch: {
        ...base.cloudWatch,
        ...overrides?.cloudWatch,
      },
    };
  }

  private constructor() {}
}

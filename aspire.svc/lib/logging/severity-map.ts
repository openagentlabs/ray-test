import { SeverityNumber } from "@opentelemetry/api-logs";

import type { ApplicationLogLevel } from "@/lib/config/logging-config";

export function applicationLogLevelToSeverity(
  level: ApplicationLogLevel,
): SeverityNumber {
  switch (level) {
    case "trace":
      return SeverityNumber.TRACE;
    case "debug":
      return SeverityNumber.DEBUG;
    case "info":
      return SeverityNumber.INFO;
    case "warn":
      return SeverityNumber.WARN;
    case "error":
      return SeverityNumber.ERROR;
    case "fatal":
      return SeverityNumber.FATAL;
  }
}

/**
 * Minimum severity for the OpenTelemetry Logger SDK filter (records below are dropped).
 */
export function applicationLogLevelToMinimumSeverity(
  level: ApplicationLogLevel,
): SeverityNumber {
  return applicationLogLevelToSeverity(level);
}

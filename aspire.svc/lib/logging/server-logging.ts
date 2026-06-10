import { logs, SeverityNumber } from "@opentelemetry/api-logs";

import type { ApplicationLogLevel } from "@/lib/config/logging-config";
import { applicationLogLevelToSeverity } from "@/lib/logging/severity-map";

export interface ServerLogEmitInput {
  readonly scope: string;
  readonly severity: ApplicationLogLevel;
  readonly body: string;
  readonly attributes?: Readonly<Record<string, string | number | boolean>>;
}

/**
 * Thin wrapper around the OpenTelemetry Logs API for server-side code paths.
 * Prefer this over ad hoc `console.log` for structured, exportable telemetry.
 */
export class ServerLogging {
  public static emit(input: ServerLogEmitInput): void {
    const logger = logs.getLogger(input.scope);
    logger.emit({
      severityNumber: applicationLogLevelToSeverity(input.severity),
      severityText: input.severity.toUpperCase(),
      body: input.body,
      attributes: input.attributes ?? {},
    });
  }

  public static emitClientRelay(
    scope: string,
    message: string,
    clientAttributes: Readonly<Record<string, string | number | boolean>>,
    severityNumber: SeverityNumber,
    severityLabel: string,
  ): void {
    const logger = logs.getLogger(scope);
    logger.emit({
      severityNumber,
      severityText: severityLabel,
      body: message,
      attributes: {
        "log.origin": "client",
        ...clientAttributes,
      },
    });
  }

  private constructor() {}
}

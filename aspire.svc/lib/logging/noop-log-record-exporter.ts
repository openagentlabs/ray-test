import { ExportResultCode, type ExportResult } from "@opentelemetry/core";
import type { LogRecordExporter } from "@opentelemetry/sdk-logs";
import type { ReadableLogRecord } from "@opentelemetry/sdk-logs";

/**
 * Drops all log records without writing to stdout/stderr (no console output).
 */
export class NoopLogRecordExporter implements LogRecordExporter {
  public export(
    _logs: ReadableLogRecord[],
    resultCallback: (result: ExportResult) => void,
  ): void {
    resultCallback({ code: ExportResultCode.SUCCESS });
  }

  public shutdown(): Promise<void> {
    return Promise.resolve();
  }

  public forceFlush(): Promise<void> {
    return Promise.resolve();
  }
}

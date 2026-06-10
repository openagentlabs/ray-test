import type { ReadableLogRecord } from "@opentelemetry/sdk-logs";

/**
 * Stable JSON-friendly projection of a {@link ReadableLogRecord} for exporters
 * (CloudWatch message bodies, client log relay, etc.).
 */
export function readableLogRecordToJson(record: ReadableLogRecord): Record<string, unknown> {
  return {
    severityText: record.severityText,
    severityNumber: record.severityNumber,
    body: record.body,
    attributes: record.attributes,
    scope: {
      name: record.instrumentationScope.name,
      version: record.instrumentationScope.version,
    },
    eventName: record.eventName,
  };
}

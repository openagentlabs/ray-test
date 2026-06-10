"use server";

import { ingestClientLogEntries } from "@/lib/logging/client-log-ingestion";
import type { ClientLogEntry } from "@/lib/types/client-log-entry";

/**
 * Server action that accepts structured client log lines and emits them through the
 * same OpenTelemetry logging pipeline as the server (console exporter).
 *
 * Intended for browser code paths that must not ship heavy OTel bundles.
 */
export async function submitClientLogs(
  entries: readonly ClientLogEntry[],
): Promise<{ readonly accepted: number; readonly rejected: number }> {
  return ingestClientLogEntries(entries);
}

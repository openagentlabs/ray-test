import type { ApplicationLogLevel } from "@/lib/config/logging-config";

/**
 * Serializable client log line forwarded to the server action for OpenTelemetry emission.
 */
export interface ClientLogEntry {
  readonly severity: ApplicationLogLevel;
  readonly message: string;
  readonly attributes?: Readonly<Record<string, string | number | boolean>>;
  /** Client clock milliseconds since Unix epoch (optional; server may ignore skew). */
  readonly clientTimestampMs?: number;
}

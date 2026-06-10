import type { ApplicationLogLevel } from "@/lib/config/logging-config";
import { LoggingConfigFactory } from "@/lib/config/logging-config";
import type { ClientLogEntry } from "@/lib/types/client-log-entry";
import { ServerLogging } from "@/lib/logging/server-logging";
import { applicationLogLevelToSeverity } from "@/lib/logging/severity-map";

const MAX_ENTRIES = 32;
const MAX_MESSAGE_LENGTH = 8_000;
const MAX_ATTRIBUTE_KEYS = 24;
const MAX_STRING_ATTRIBUTE_LENGTH = 1_024;

const CLIENT_SCOPE = "arb-sherpa.client";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseSeverity(value: unknown): ApplicationLogLevel | undefined {
  if (typeof value !== "string") {
    return undefined;
  }
  const normalized = value.trim().toLowerCase();
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
  return undefined;
}

function sanitizeAttributes(
  raw: unknown,
): Record<string, string | number | boolean> | undefined {
  if (raw === undefined) {
    return undefined;
  }
  if (!isRecord(raw)) {
    return undefined;
  }
  const out: Record<string, string | number | boolean> = {};
  let count = 0;
  for (const [key, val] of Object.entries(raw)) {
    if (count >= MAX_ATTRIBUTE_KEYS) {
      break;
    }
    if (key.length > 64) {
      continue;
    }
    if (typeof val === "string") {
      out[key] = val.slice(0, MAX_STRING_ATTRIBUTE_LENGTH);
    } else if (typeof val === "number" && Number.isFinite(val)) {
      out[key] = val;
    } else if (typeof val === "boolean") {
      out[key] = val;
    }
    count += 1;
  }
  return Object.keys(out).length > 0 ? out : undefined;
}

function normalizeEntry(raw: unknown): ClientLogEntry | undefined {
  if (!isRecord(raw)) {
    return undefined;
  }
  const severity = parseSeverity(raw.severity);
  if (severity === undefined) {
    return undefined;
  }
  const message = raw.message;
  if (typeof message !== "string" || message.length === 0) {
    return undefined;
  }
  const clientTimestampMs = raw.clientTimestampMs;
  const attributes = sanitizeAttributes(raw.attributes);
  return {
    severity,
    message: message.slice(0, MAX_MESSAGE_LENGTH),
    attributes,
    clientTimestampMs:
      typeof clientTimestampMs === "number" &&
      Number.isFinite(clientTimestampMs)
        ? clientTimestampMs
        : undefined,
  };
}

function passesMinimumSeverity(
  level: ApplicationLogLevel,
  minimum: ApplicationLogLevel,
): boolean {
  const order: ApplicationLogLevel[] = [
    "trace",
    "debug",
    "info",
    "warn",
    "error",
    "fatal",
  ];
  return order.indexOf(level) >= order.indexOf(minimum);
}

/**
 * Validates and forwards client log lines through the server OpenTelemetry pipeline.
 */
export async function ingestClientLogEntries(
  entries: unknown,
): Promise<{ readonly accepted: number; readonly rejected: number }> {
  if (!Array.isArray(entries)) {
    return { accepted: 0, rejected: 0 };
  }

  const slice = entries.slice(0, MAX_ENTRIES);
  const config = LoggingConfigFactory.fromEnvironment();
  let accepted = 0;
  let rejected = 0;

  for (const raw of slice) {
    const entry = normalizeEntry(raw);
    if (entry === undefined) {
      rejected += 1;
      continue;
    }
    if (!config.enabled) {
      rejected += 1;
      continue;
    }
    if (!passesMinimumSeverity(entry.severity, config.logLevel)) {
      rejected += 1;
      continue;
    }

    const severityNumber = applicationLogLevelToSeverity(entry.severity);
    const attrs: Record<string, string | number | boolean> = {
      ...(entry.attributes ?? {}),
    };
    if (entry.clientTimestampMs !== undefined) {
      attrs["client.timestamp.ms"] = entry.clientTimestampMs;
    }

    ServerLogging.emitClientRelay(
      CLIENT_SCOPE,
      entry.message,
      attrs,
      severityNumber,
      entry.severity.toUpperCase(),
    );
    accepted += 1;
  }

  return { accepted, rejected };
}

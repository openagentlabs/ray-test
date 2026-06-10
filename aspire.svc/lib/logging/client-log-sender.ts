import { submitClientLogs } from "@/app/actions/client-logs";
import type { ClientLogEntry } from "@/lib/types/client-log-entry";

/**
 * Fire-and-forget client log relay to {@link submitClientLogs}. Swallows transport errors
 * so UI code never blocks on logging failures.
 */
export function sendClientLogs(entries: readonly ClientLogEntry[]): void {
  void submitClientLogs(entries).catch(() => {
    // Intentionally silent: logging must never break UX.
  });
}

/**
 * Single convenience wrapper for one {@link ClientLogEntry}.
 */
export function sendClientLog(entry: ClientLogEntry): void {
  sendClientLogs([entry]);
}

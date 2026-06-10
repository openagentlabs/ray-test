import "server-only";

import fs from "node:fs";
import path from "node:path";

import { resolveAspireRoot } from "@/lib/server/repo-root";

/** Same relative layout as `scripts/booter.mjs` so CLI and UI share PID tracking. */
export function serviceRuntimePidFilePath(): string {
  return path.join(resolveAspireRoot(), ".aspire", "booter-pids.json");
}

export interface ServiceRuntimePidEntry {
  readonly pid: number;
  readonly startedAt: string;
}

function readRawState(): Record<string, { pid?: number; startedAt?: string }> {
  const filePath = serviceRuntimePidFilePath();
  try {
    const raw = fs.readFileSync(filePath, "utf8");
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
      return {};
    }
    return parsed as Record<string, { pid?: number; startedAt?: string }>;
  } catch {
    return {};
  }
}

export function readServiceRuntimePidState(): Record<string, ServiceRuntimePidEntry> {
  const raw = readRawState();
  const out: Record<string, ServiceRuntimePidEntry> = {};
  for (const [id, entry] of Object.entries(raw)) {
    if (typeof entry?.pid === "number" && entry.pid > 0) {
      out[id] = {
        pid: entry.pid,
        startedAt:
          typeof entry.startedAt === "string" && entry.startedAt.length > 0
            ? entry.startedAt
            : new Date(0).toISOString(),
      };
    }
  }
  return out;
}

export function writeServiceRuntimePidState(state: Record<string, ServiceRuntimePidEntry>): void {
  const filePath = serviceRuntimePidFilePath();
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(state, null, 2)}\n`, "utf8");
}

export function setServiceRuntimePid(serviceId: string, pid: number): void {
  const state = readServiceRuntimePidState();
  state[serviceId] = { pid, startedAt: new Date().toISOString() };
  writeServiceRuntimePidState(state);
}

export function clearServiceRuntimePidIfMatches(serviceId: string, pid: number): void {
  const state = readServiceRuntimePidState();
  if (state[serviceId]?.pid === pid) {
    const next = { ...state };
    delete next[serviceId];
    writeServiceRuntimePidState(next);
  }
}

export function removeServiceRuntimePid(serviceId: string): void {
  const state = readServiceRuntimePidState();
  if (state[serviceId] === undefined) {
    return;
  }
  const next = { ...state };
  delete next[serviceId];
  writeServiceRuntimePidState(next);
}

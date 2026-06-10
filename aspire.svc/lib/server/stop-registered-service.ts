import "server-only";

import type { StartServiceEnvironmentResult } from "@/lib/types/start-service-environment-result";

import {
  readServiceRuntimePidState,
  removeServiceRuntimePid,
} from "@/lib/server/service-runtime-pid-store";

export function stopRegisteredServiceById(serviceId: string): StartServiceEnvironmentResult {
  if (serviceId.trim().length === 0) {
    return { ok: false, message: "Service id is empty." };
  }
  const state = readServiceRuntimePidState();
  const entry = state[serviceId];
  if (entry === undefined) {
    return {
      ok: false,
      message: "No Aspire-tracked PID for this service (start it from here or the booter).",
    };
  }
  try {
    process.kill(entry.pid, "SIGTERM");
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    removeServiceRuntimePid(serviceId);
    return { ok: false, message: `Failed to signal process: ${message}` };
  }
  removeServiceRuntimePid(serviceId);
  return { ok: true };
}

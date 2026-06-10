import "server-only";

import fs from "node:fs";
import net from "node:net";

import { readServiceRuntimePidState } from "@/lib/server/service-runtime-pid-store";
import type { AppInfo } from "@/lib/types/app-info";

export interface RegisteredServiceRuntimeStats {
  readonly running: boolean;
  readonly pathExists: boolean;
  readonly trackedPidAlive: boolean;
  readonly listenPortOpen: boolean;
}

function tryPidAlive(pid: number): boolean {
  if (pid <= 0) {
    return false;
  }
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

function probeTcpListening(host: string, port: number, timeoutMs: number): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = net.connect({ host, port }, () => {
      socket.destroy();
      resolve(true);
    });
    socket.setTimeout(timeoutMs);
    socket.on("timeout", () => {
      socket.destroy();
      resolve(false);
    });
    socket.on("error", () => resolve(false));
  });
}

/**
 * Server-side helpers for inferring whether a registered service is running.
 * Uses the application working-directory path plus optional listen port and booter-tracked PID.
 *
 * For a stable callable surface similar to `process.get_app_stats`, use {@link appProcess}.
 */
export class AppServiceProcess {
  private constructor() {}

  /**
   * Resolves runtime status for a catalog row. `applicationAbsolutePath` should be the resolved
   * working directory for the service (same path used when spawning).
   */
  public static async getAppStats(
    applicationAbsolutePath: string,
    listenPort: number | null,
    trackedPid: number | null,
  ): Promise<RegisteredServiceRuntimeStats> {
    const pathExists = fs.existsSync(applicationAbsolutePath);
    const trackedPidAlive =
      trackedPid !== null && trackedPid > 0 ? tryPidAlive(trackedPid) : false;
    const listenPortOpen =
      listenPort !== null && listenPort > 0
        ? await probeTcpListening("127.0.0.1", listenPort, 450)
        : false;
    const running = pathExists && (trackedPidAlive || listenPortOpen);
    return {
      running,
      pathExists,
      trackedPidAlive,
      listenPortOpen,
    };
  }

  /**
   * Snapshot helper: reads the shared PID file for `app.id` then delegates to {@link getAppStats}.
   */
  public static async getStatsForAppInfo(app: AppInfo): Promise<RegisteredServiceRuntimeStats> {
    const tracked = readServiceRuntimePidState()[app.id];
    const trackedPid = tracked?.pid ?? null;
    return AppServiceProcess.getAppStats(app.workdirAbsolutePath, app.port, trackedPid);
  }
}

/** Namespace-style export (avoids shadowing Node.js `globalThis.process`). */
export const appProcess = {
  getAppStats: (
    applicationAbsolutePath: string,
    listenPort: number | null,
    trackedPid: number | null,
  ): Promise<RegisteredServiceRuntimeStats> =>
    AppServiceProcess.getAppStats(applicationAbsolutePath, listenPort, trackedPid),
} as const;

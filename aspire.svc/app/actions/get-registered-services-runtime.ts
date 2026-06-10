"use server";

import { DatabaseContextConfig } from "@/lib/database/context-config";
import { ServiceRegistryRepository } from "@/lib/database/repository/service-registry-repository";
import { AppServiceProcess } from "@/lib/server/app-service-process";

export type RegisteredServicesRuntimeSnapshot =
  | {
      readonly ok: true;
      readonly runningById: Readonly<Record<string, boolean>>;
    }
  | { readonly ok: false; readonly message: string; readonly detail?: string };

/**
 * Returns whether each registry row appears running (PID file and/or listen port), for UI controls.
 */
export async function getRegisteredServicesRuntimeSnapshot(): Promise<RegisteredServicesRuntimeSnapshot> {
  try {
    const config = DatabaseContextConfig.fromApplicationConfig();
    const apps = ServiceRegistryRepository.listRegisteredServices(config);
    const entries = await Promise.all(
      apps.map(async (app) => {
        const stats = await AppServiceProcess.getStatsForAppInfo(app);
        return [app.id, stats.running] as const;
      }),
    );
    const runningById: Record<string, boolean> = {};
    for (const [id, running] of entries) {
      runningById[id] = running;
    }
    return { ok: true, runningById };
  } catch (error: unknown) {
    const detail = error instanceof Error ? error.message : String(error);
    return {
      ok: false,
      message: "Failed to load runtime snapshot.",
      detail,
    };
  }
}

"use server";

import { DatabaseContextConfig } from "@/lib/database/context-config";
import { ServiceRegistryRepository } from "@/lib/database/repository/service-registry-repository";
import { spawnRegisteredServiceNonBlocking } from "@/lib/server/spawn-registered-service";
import type { StartServiceEnvironmentResult } from "@/lib/types/start-service-environment-result";

/**
 * Starts a catalog process in the background (non-blocking on the server).
 * Loads the row from the registry by id so paths are not taken from the client alone.
 */
export async function startRegisteredServiceById(
  serviceId: string,
): Promise<StartServiceEnvironmentResult> {
  if (serviceId.trim().length === 0) {
    return { ok: false, message: "Service id is empty." };
  }
  const config = DatabaseContextConfig.fromApplicationConfig();
  const apps = ServiceRegistryRepository.listRegisteredServices(config);
  const app = apps.find((a) => a.id === serviceId);
  if (app === undefined) {
    return { ok: false, message: `Unknown service id: ${serviceId}` };
  }
  if (!app.enabled) {
    return { ok: false, message: "Service is disabled in the registry." };
  }
  return spawnRegisteredServiceNonBlocking(app);
}

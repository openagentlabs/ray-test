"use server";

import { stopRegisteredServiceById } from "@/lib/server/stop-registered-service";
import type { StartServiceEnvironmentResult } from "@/lib/types/start-service-environment-result";

/**
 * Stops a catalog process previously tracked under `.aspire/booter-pids.json`.
 */
export async function stopServiceEnvironment(
  serviceId: string,
): Promise<StartServiceEnvironmentResult> {
  return stopRegisteredServiceById(serviceId);
}

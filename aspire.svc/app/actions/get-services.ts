"use server";

import { RegisteredServicesLoader } from "@/lib/services/registered-services-loader";
import type { RegisteredServicesLoadResult } from "@/lib/types/registered-services-load-result";

export type GetServicesResult = RegisteredServicesLoadResult;

/**
 * Loads registered applications/services from the service registry SQLite DB.
 */
export async function getServices(): Promise<GetServicesResult> {
  return RegisteredServicesLoader.safeLoad();
}

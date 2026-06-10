import { DatabaseContextConfig } from "@/lib/database/context-config";
import { ServiceRegistryRepository } from "@/lib/database/repository/service-registry-repository";
import type { RegisteredServicesLoadResult } from "@/lib/types/registered-services-load-result";

/**
 * Application entry for listing the service registry (config + repository only).
 * Use from Server Components and thin server actions — no UI concerns.
 */
export class RegisteredServicesLoader {
  public static safeLoad(
    config: DatabaseContextConfig = DatabaseContextConfig.fromApplicationConfig(),
  ): RegisteredServicesLoadResult {
    try {
      const services = ServiceRegistryRepository.listRegisteredServices(config);
      return { ok: true, services };
    } catch (error: unknown) {
      const detail = error instanceof Error ? error.message : String(error);
      return {
        ok: false,
        message: "Failed to load registered services.",
        detail,
      };
    }
  }
}

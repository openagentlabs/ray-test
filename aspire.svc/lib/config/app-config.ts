import path from "node:path";

export class AppConfig {
  public static readonly applicationName = "AI Smart Assistant";

  public static readonly sidebarStorageKey = "arb_sherpa.sidebar.collapsed";

  /**
   * Absolute path to the service registry SQLite file.
   * Override with `ARB_SERVICE_REGISTRY_DB` (absolute or relative path).
   */
  public static getServiceRegistryDbPath(): string {
    const raw = process.env.ARB_SERVICE_REGISTRY_DB?.trim();
    if (raw !== undefined && raw.length > 0) {
      return path.resolve(raw);
    }
    return path.join(process.cwd(), "service-registry.sqlite");
  }

  /** Absolute path to the local SQLite user-auth database. */
  public static getUserAuthDbPath(): string {
    const raw = process.env.ARB_USER_AUTH_DB?.trim();
    if (raw !== undefined && raw.length > 0) {
      return path.resolve(raw);
    }
    return path.join(process.cwd(), "user-auth.sqlite");
  }

  private constructor() {}
}

import { AppConfig } from "@/lib/config/app-config";

/**
 * Immutable configuration for SQLite access (resolved absolute file path).
 */
export class DatabaseContextConfig {
  public readonly sqliteAbsolutePath: string;

  public constructor(sqliteAbsolutePath: string) {
    this.sqliteAbsolutePath = sqliteAbsolutePath;
  }

  public static fromApplicationConfig(): DatabaseContextConfig {
    return new DatabaseContextConfig(AppConfig.getServiceRegistryDbPath());
  }
}

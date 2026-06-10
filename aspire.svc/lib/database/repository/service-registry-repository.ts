import path from "node:path";

import SqliteDb from "better-sqlite3";

import type { DatabaseContextConfig } from "@/lib/database/context-config";
import { resolveRepoRoot } from "@/lib/server/repo-root";
import type { AppInfo } from "@/lib/types/app-info";

interface RegisteredServiceRow {
  readonly id: string;
  readonly display_name: string;
  readonly role: string;
  readonly kind: string;
  readonly workdir_relative: string;
  readonly command: string;
  readonly args_json: string;
  readonly port: number | null;
  readonly health_kind: string;
  readonly health_target: string | null;
  readonly description: string | null;
  readonly start_order: number;
  readonly enabled: number;
  readonly auto_start_with_home: number;
  readonly env_json: string | null;
}

/**
 * Read-only access to `registered_services` for server actions and loaders.
 */
export class ServiceRegistryRepository {
  public static listRegisteredServices(
    config: DatabaseContextConfig,
  ): readonly AppInfo[] {
    const db = new SqliteDb(config.sqliteAbsolutePath, {
      readonly: true,
      fileMustExist: true,
    });
    try {
      const rows = db
        .prepare(
          `SELECT id, display_name, role, kind, workdir_relative, command, args_json,
                  port, health_kind, health_target, description, start_order, enabled,
                  auto_start_with_home, env_json
             FROM registered_services
            ORDER BY start_order ASC, id ASC`,
        )
        .all() as RegisteredServiceRow[];

      const repoRoot = resolveRepoRoot();

      return rows.map(
        (row): AppInfo => ({
          id: row.id,
          displayName: row.display_name,
          role: row.role,
          kind: row.kind,
          workdirRelative: row.workdir_relative,
          workdirAbsolutePath: path.join(repoRoot, row.workdir_relative),
          command: row.command,
          argsJson: row.args_json,
          port: row.port,
          healthKind: row.health_kind,
          healthTarget: row.health_target,
          description: row.description ?? "",
          startOrder: row.start_order,
          enabled: row.enabled === 1,
          autoStartWithHome: row.auto_start_with_home === 1,
          envJson: row.env_json,
        }),
      );
    } finally {
      db.close();
    }
  }
}

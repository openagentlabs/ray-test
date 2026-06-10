import fs from "node:fs";
import path from "node:path";

import type { DatabaseContextConfig } from "@/lib/database/context-config";
import SqliteDb from "better-sqlite3";

import {
  SERVICE_REGISTRY_DEFAULT_SEED,
  SERVICE_REGISTRY_SCHEMA_SQL,
  type ServiceRegistrySeedRow,
} from "@/lib/database/service-registry-schema";
import { ensureRegisteredServicesColumns } from "@/lib/database/registered-services-migrations";
import {
  DatabaseCheckResult,
  type DatabaseCheckOutcome,
} from "@/lib/types/database-check-result";

export type CreateDatabaseOutcome =
  | { readonly ok: true }
  | { readonly ok: false; readonly message: string; readonly detail?: string };

function applySeedRows(
  db: InstanceType<typeof SqliteDb>,
  rows: readonly ServiceRegistrySeedRow[],
): void {
  const insert = db.prepare(`
        INSERT OR REPLACE INTO registered_services (
          id, display_name, role, kind, workdir_relative, command, args_json,
          port, health_kind, health_target, description, start_order, enabled,
          auto_start_with_home, env_json
        ) VALUES (
          @id, @display_name, @role, @kind, @workdir_relative, @command, @args_json,
          @port, @health_kind, @health_target, @description, @start_order, @enabled,
          @auto_start_with_home, @env_json
        )
      `);
  const tx = db.transaction((seed: readonly ServiceRegistrySeedRow[]) => {
    for (const row of seed) {
      insert.run({
        id: row.id,
        display_name: row.display_name,
        role: row.role,
        kind: row.kind,
        workdir_relative: row.workdir_relative,
        command: row.command,
        args_json: row.args_json,
        port: row.port,
        health_kind: row.health_kind,
        health_target: row.health_target,
        description: row.description,
        start_order: row.start_order,
        enabled: row.enabled,
        auto_start_with_home: row.auto_start_with_home,
        env_json: row.env_json,
      });
    }
  });
  tx(rows);
}

function applyDefaultSeedRows(db: InstanceType<typeof SqliteDb>): void {
  applySeedRows(db, SERVICE_REGISTRY_DEFAULT_SEED);
}

/**
 * SQLite service registry access (sync API via better-sqlite3).
 * Use only from the Node.js server (instrumentation, server actions).
 */
export class DatabaseContext {
  public static checkDatabase(config: DatabaseContextConfig): DatabaseCheckOutcome {
    const target = config.sqliteAbsolutePath;

    if (target.trim().length === 0) {
      return {
        ok: false,
        code: DatabaseCheckResult.InvalidPath,
        message: "Database path is empty.",
      };
    }

    let resolved: string;
    try {
      resolved = path.resolve(target);
    } catch (error: unknown) {
      return {
        ok: false,
        code: DatabaseCheckResult.InvalidPath,
        message: "Database path could not be resolved.",
        detail: error instanceof Error ? error.message : String(error),
      };
    }

    if (!fs.existsSync(resolved)) {
      return { ok: false, code: DatabaseCheckResult.NoFileExists };
    }

    let stat: fs.Stats;
    try {
      stat = fs.statSync(resolved);
    } catch (error: unknown) {
      return {
        ok: false,
        code: DatabaseCheckResult.OpenFailed,
        message: "Could not stat database file.",
        detail: error instanceof Error ? error.message : String(error),
      };
    }

    if (stat.isDirectory()) {
      return {
        ok: false,
        code: DatabaseCheckResult.InvalidPath,
        message: "Database path points to a directory.",
        detail: resolved,
      };
    }
    if (!stat.isFile()) {
      return {
        ok: false,
        code: DatabaseCheckResult.InvalidPath,
        message: "Database path is not a regular file.",
        detail: resolved,
      };
    }

    let db: InstanceType<typeof SqliteDb> | undefined;
    try {
      db = new SqliteDb(resolved, { readonly: true, fileMustExist: true });
      const qc = db.prepare("PRAGMA quick_check").pluck().get();
      if (typeof qc === "string" && qc !== "ok") {
        return {
          ok: false,
          code: DatabaseCheckResult.CorruptOrUnreadable,
          message: "SQLite quick_check failed.",
          detail: qc,
        };
      }
    } catch (error: unknown) {
      return {
        ok: false,
        code: DatabaseCheckResult.OpenFailed,
        message: "Could not open SQLite database.",
        detail: error instanceof Error ? error.message : String(error),
      };
    } finally {
      db?.close();
    }

    return { ok: true, code: DatabaseCheckResult.Success };
  }

  public static createDatabase(config: DatabaseContextConfig): CreateDatabaseOutcome {
    const target = path.resolve(config.sqliteAbsolutePath);
    try {
      fs.mkdirSync(path.dirname(target), { recursive: true });
    } catch (error: unknown) {
      return {
        ok: false,
        message: "Could not create database parent directory.",
        detail: error instanceof Error ? error.message : String(error),
      };
    }

    let db: InstanceType<typeof SqliteDb> | undefined;
    try {
      db = new SqliteDb(target);
      db.exec(SERVICE_REGISTRY_SCHEMA_SQL);
      ensureRegisteredServicesColumns(db);
      applyDefaultSeedRows(db);
    } catch (error: unknown) {
      return {
        ok: false,
        message: "Failed to initialize SQLite database file.",
        detail: error instanceof Error ? error.message : String(error),
      };
    } finally {
      db?.close();
    }

    return { ok: true };
  }

  /**
   * Upserts every row in {@link SERVICE_REGISTRY_DEFAULT_SEED} so catalog ports and commands
   * stay aligned with the repo (including existing `service-registry.sqlite` files).
   */
  public static synchronizeDefaultCatalogRows(
    config: DatabaseContextConfig,
  ): CreateDatabaseOutcome {
    const target = path.resolve(config.sqliteAbsolutePath);
    if (!fs.existsSync(target)) {
      return { ok: true };
    }

    let db: InstanceType<typeof SqliteDb> | undefined;
    try {
      db = new SqliteDb(target);
      db.exec(SERVICE_REGISTRY_SCHEMA_SQL);
      ensureRegisteredServicesColumns(db);
      applyDefaultSeedRows(db);
    } catch (error: unknown) {
      return {
        ok: false,
        message: "Failed to synchronize default service registry catalog rows.",
        detail: error instanceof Error ? error.message : String(error),
      };
    } finally {
      db?.close();
    }

    return { ok: true };
  }
}

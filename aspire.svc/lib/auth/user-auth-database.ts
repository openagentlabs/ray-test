import fs from "node:fs";
import path from "node:path";

import SqliteDb from "better-sqlite3";

import { AppConfig } from "@/lib/config/app-config";
import { USER_AUTH_SCHEMA_SQL } from "@/lib/auth/user-auth-schema";

let cachedDb: InstanceType<typeof SqliteDb> | undefined;

function openUserAuthDatabase(): InstanceType<typeof SqliteDb> {
  if (cachedDb !== undefined) {
    return cachedDb;
  }

  const target = AppConfig.getUserAuthDbPath();
  fs.mkdirSync(path.dirname(target), { recursive: true });

  const db = new SqliteDb(target);
  db.exec(USER_AUTH_SCHEMA_SQL);
  cachedDb = db;
  return db;
}

/** Opens the SQLite user-auth database (server-only). */
export function getUserAuthDatabase(): InstanceType<typeof SqliteDb> {
  return openUserAuthDatabase();
}

/** Resolves the configured user-auth database path (for diagnostics). */
export function getUserAuthDatabasePath(): string {
  return AppConfig.getUserAuthDbPath();
}

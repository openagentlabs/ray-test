import SqliteDb from "better-sqlite3";

/**
 * Ensures newer columns exist on legacy `registered_services` tables (CREATE IF NOT EXISTS
 * leaves older schemas unchanged).
 */
export function ensureRegisteredServicesColumns(db: InstanceType<typeof SqliteDb>): void {
  const columns = db
    .prepare("PRAGMA table_info(registered_services)")
    .all() as ReadonlyArray<{ name: string }>;
  const names = new Set(columns.map((c) => c.name));
  if (!names.has("auto_start_with_home")) {
    db.exec(
      "ALTER TABLE registered_services ADD COLUMN auto_start_with_home INTEGER NOT NULL DEFAULT 0",
    );
  }
}

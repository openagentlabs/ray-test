import { DatabaseContext } from "@/lib/database/context";
import { DatabaseContextConfig } from "@/lib/database/context-config";
import { ServerLogging } from "@/lib/logging/server-logging";
import {
  DatabaseCheckResult,
  type ValidateEnvironmentResult,
} from "@/lib/types/database-check-result";

const SCOPE = "arb-sherpa.environment";

/**
 * Validates the service registry SQLite file at process startup.
 * Creates the database (schema + seed) when missing, then re-verifies.
 */
export async function validateEnvironment(): Promise<ValidateEnvironmentResult> {
  const config = DatabaseContextConfig.fromApplicationConfig();

  const log = (
    severity: "info" | "warn" | "error",
    body: string,
    attributes?: Readonly<Record<string, string | number | boolean>>,
  ): void => {
    ServerLogging.emit({ scope: SCOPE, severity, body, attributes });
  };

  log("info", "validateEnvironment: checking service registry database.", {
    path: config.sqliteAbsolutePath,
  });

  const first = DatabaseContext.checkDatabase(config);
  if (first.ok) {
    log("info", "validateEnvironment: database check succeeded.", {
      code: DatabaseCheckResult.Success,
    });
    const seeded = DatabaseContext.synchronizeDefaultCatalogRows(config);
    if (!seeded.ok) {
      log("error", "validateEnvironment: synchronizeDefaultCatalogRows failed.", {
        detail: seeded.detail ?? seeded.message,
      });
      return { ok: false, message: seeded.message, detail: seeded.detail };
    }
    return { ok: true };
  }

  log("warn", "validateEnvironment: initial database check did not succeed.", {
    code: first.code,
  });

  if (first.code === DatabaseCheckResult.NoFileExists) {
    log("info", "validateEnvironment: creating service registry database file.", {
      code: DatabaseCheckResult.NoFileExists,
    });
    const created = DatabaseContext.createDatabase(config);
    if (!created.ok) {
      const message = "validateEnvironment: createDatabase failed.";
      const detail = `${created.message}${created.detail !== undefined ? ` — ${created.detail}` : ""}`;
      console.error(message, detail);
      log("error", message, { detail: created.detail ?? created.message });
      return { ok: false, message: created.message, detail: created.detail };
    }

    log("info", "validateEnvironment: createDatabase completed; re-checking database.", {
      phase: "post_create_verify",
    });

    const second = DatabaseContext.checkDatabase(config);
    if (!second.ok) {
      const message = "validateEnvironment: database still not usable after createDatabase.";
      let detail: string;
      switch (second.code) {
        case DatabaseCheckResult.NoFileExists:
          detail = "file_missing_after_create";
          break;
        case DatabaseCheckResult.InvalidPath:
        case DatabaseCheckResult.OpenFailed:
        case DatabaseCheckResult.CorruptOrUnreadable:
          detail =
            second.detail !== undefined
              ? `${second.message} — ${second.detail}`
              : second.message;
          break;
      }
      console.error(message, detail);
      log("error", message, {
        code: second.code,
        detail,
      });
      return {
        ok: false,
        message,
        detail,
      };
    }

    log("info", "validateEnvironment: database verified after creation.", {
      code: DatabaseCheckResult.Success,
    });
    return { ok: true };
  }

  const message = "validateEnvironment: database check failed (non-recoverable).";
  let detail: string;
  switch (first.code) {
    case DatabaseCheckResult.InvalidPath:
    case DatabaseCheckResult.OpenFailed:
    case DatabaseCheckResult.CorruptOrUnreadable:
      detail =
        first.detail !== undefined
          ? `${first.message} — ${first.detail}`
          : first.message;
      break;
  }

  console.error(message, detail);
  log("error", message, {
    code: first.code,
    detail,
  });
  return {
    ok: false,
    message,
    detail,
  };
}

import "server-only";

import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

import type { AppInfo } from "@/lib/types/app-info";
import type { StartServiceEnvironmentResult } from "@/lib/types/start-service-environment-result";

import { resolveRepoRoot } from "@/lib/server/repo-root";
import {
  clearServiceRuntimePidIfMatches,
  setServiceRuntimePid,
} from "@/lib/server/service-runtime-pid-store";

function npmCommand(): string {
  return process.platform === "win32" ? "npm.cmd" : "npm";
}

function normalizeCommand(command: string): string {
  if (command === "npm") {
    return npmCommand();
  }
  return command;
}

function parseArgsJson(argsJson: string): readonly string[] {
  try {
    const parsed: unknown = JSON.parse(argsJson);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.map((item) => String(item));
  } catch {
    return [];
  }
}

function parseEnvJson(envJson: string | null): Record<string, string> {
  if (envJson === null || envJson.trim().length === 0) {
    return {};
  }
  try {
    const parsed: unknown = JSON.parse(envJson);
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
      return {};
    }
    const out: Record<string, string> = {};
    for (const [key, value] of Object.entries(parsed as Record<string, unknown>)) {
      if (typeof value === "string") {
        out[key] = value;
      } else if (value !== null && value !== undefined) {
        out[key] = String(value);
      }
    }
    return out;
  } catch {
    return {};
  }
}

function validateAppInfo(app: AppInfo): StartServiceEnvironmentResult | null {
  if (app.id.trim().length === 0) {
    return { ok: false, message: "Application id is empty." };
  }
  if (app.command.trim().length === 0) {
    return { ok: false, message: "Application command is empty." };
  }
  if (app.workdirRelative.trim().length === 0) {
    return { ok: false, message: "Application workdir is empty." };
  }
  return null;
}

/**
 * Spawns a registry-backed process without waiting for exit (detached + unref).
 * Records the child PID in `.aspire/booter-pids.json` (same file as `scripts/booter.mjs`).
 */
export function spawnRegisteredServiceNonBlocking(
  app: AppInfo,
): StartServiceEnvironmentResult {
  const validationError = validateAppInfo(app);
  if (validationError !== null) {
    return validationError;
  }

  const repoRoot = resolveRepoRoot();
  const cwd = path.join(repoRoot, app.workdirRelative);
  if (!fs.existsSync(cwd)) {
    return {
      ok: false,
      message: `Working directory does not exist: ${cwd}`,
    };
  }

  const cmd = normalizeCommand(app.command);
  const args = [...parseArgsJson(app.argsJson)];
  const extraEnv = parseEnvJson(app.envJson);
  const env: NodeJS.ProcessEnv = { ...process.env, ...extraEnv };

  try {
    const child = spawn(cmd, args, {
      cwd,
      env,
      detached: true,
      stdio: "ignore",
      windowsHide: true,
    });
    child.unref();
    const pid = child.pid;
    if (typeof pid === "number" && pid > 0) {
      setServiceRuntimePid(app.id, pid);
      child.on("exit", (code, signal) => {
        if (code !== 0 && signal === null) {
          console.error(
            `[spawn-registered-service] ${app.id} exited code=${String(code)} pid=${String(pid)}`,
          );
        }
        clearServiceRuntimePidIfMatches(app.id, pid);
      });
    }
    child.on("error", (err) => {
      console.error(`[spawn-registered-service] ${app.id} child error:`, err);
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    return { ok: false, message: `Failed to spawn process: ${message}` };
  }

  return { ok: true };
}

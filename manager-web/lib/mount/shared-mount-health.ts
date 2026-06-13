import { statSync } from "node:fs";

import type { SharedMountDefinition } from "@/lib/config/shared-mount-config";

export interface SharedMountProbeResult {
  readonly kind: SharedMountDefinition["kind"];
  readonly mountPath: string;
  readonly ok: boolean;
  readonly detail: string;
  readonly checkedAt: string;
}

const TRANSIENT_MOUNT_ERRNO = new Set([
  "EIO",
  "ESTALE",
  "ETIMEDOUT",
  "ENOTCONN",
  "ESHUTDOWN",
]);

export function isTransientMountErrno(code: string | undefined): boolean {
  return code !== undefined && TRANSIENT_MOUNT_ERRNO.has(code);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Probe a shared mount path with bounded retries — used by health checks and I/O retry logic.
 */
export async function probeSharedMount(
  mount: SharedMountDefinition,
  options?: { maxAttempts?: number; baseDelayMs?: number },
): Promise<SharedMountProbeResult> {
  const maxAttempts = options?.maxAttempts ?? 5;
  const baseDelayMs = options?.baseDelayMs ?? 400;
  const checkedAt = new Date().toISOString();

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      const stat = statSync(mount.mountPath);
      if (!stat.isDirectory()) {
        return {
          kind: mount.kind,
          mountPath: mount.mountPath,
          ok: false,
          detail: `Path exists but is not a directory: ${mount.mountPath}`,
          checkedAt,
        };
      }
      return {
        kind: mount.kind,
        mountPath: mount.mountPath,
        ok: true,
        detail: `${mount.displayName} mount is accessible`,
        checkedAt,
      };
    } catch (error) {
      const code =
        typeof error === "object" &&
        error !== null &&
        "code" in error &&
        typeof (error as NodeJS.ErrnoException).code === "string"
          ? (error as NodeJS.ErrnoException).code
          : undefined;
      const message =
        error instanceof Error ? error.message : "Mount path not accessible";
      const transient = isTransientMountErrno(code);
      if (!transient || attempt === maxAttempts) {
        return {
          kind: mount.kind,
          mountPath: mount.mountPath,
          ok: false,
          detail: transient
            ? `${message} (transient; exhausted ${maxAttempts} attempts)`
            : message,
          checkedAt,
        };
      }
      await sleep(baseDelayMs * attempt);
    }
  }

  return {
    kind: mount.kind,
    mountPath: mount.mountPath,
    ok: false,
    detail: "Mount probe failed after retries",
    checkedAt,
  };
}

export async function probeAllSharedMounts(
  mounts: readonly SharedMountDefinition[],
): Promise<SharedMountProbeResult[]> {
  return Promise.all(mounts.map((mount) => probeSharedMount(mount)));
}

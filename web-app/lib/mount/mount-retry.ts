import { isTransientMountErrno } from "@/lib/mount/shared-mount-health";

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Retry POSIX operations when the underlying CSI mount returns transient I/O errors.
 */
export async function withMountRetry<T>(
  operation: () => T,
  options?: { maxAttempts?: number; baseDelayMs?: number },
): Promise<T> {
  const maxAttempts = options?.maxAttempts ?? 5;
  const baseDelayMs = options?.baseDelayMs ?? 300;

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      return operation();
    } catch (error) {
      const code =
        typeof error === "object" &&
        error !== null &&
        "code" in error &&
        typeof (error as NodeJS.ErrnoException).code === "string"
          ? (error as NodeJS.ErrnoException).code
          : undefined;
      if (!isTransientMountErrno(code) || attempt === maxAttempts) {
        throw error;
      }
      await sleep(baseDelayMs * attempt);
    }
  }

  throw new Error("withMountRetry exhausted attempts without returning");
}

/** Synchronous retry for Node fs APIs used by the cluster file engine. */
export function withMountRetrySync<T>(
  operation: () => T,
  options?: { maxAttempts?: number; pauseMs?: number },
): T {
  const maxAttempts = options?.maxAttempts ?? 5;
  const pauseMs = options?.pauseMs ?? 50;

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      return operation();
    } catch (error) {
      const code =
        typeof error === "object" &&
        error !== null &&
        "code" in error &&
        typeof (error as NodeJS.ErrnoException).code === "string"
          ? (error as NodeJS.ErrnoException).code
          : undefined;
      if (!isTransientMountErrno(code) || attempt === maxAttempts) {
        throw error;
      }
      const waitUntil = Date.now() + pauseMs * attempt;
      while (Date.now() < waitUntil) {
        // short synchronous pause — avoids async in sync fs stack
      }
    }
  }

  throw new Error("withMountRetrySync exhausted attempts without returning");
}

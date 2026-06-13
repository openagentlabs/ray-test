import { SharedMountConfig } from "@/lib/config/shared-mount-config";
import { probeAllSharedMounts } from "@/lib/mount/shared-mount-health";

const DEFAULT_INTERVAL_MS = 30_000;

let timer: ReturnType<typeof setInterval> | undefined;

/**
 * Background mount probes — logs degradation; Kubernetes liveness on /api/health/mounts
 * triggers pod restart when mounts stay unhealthy (CSI remount on reschedule).
 */
export function startMountWatchdog(intervalMs = DEFAULT_INTERVAL_MS): void {
  if (timer !== undefined) {
    return;
  }

  timer = setInterval(() => {
    void probeAllSharedMounts(SharedMountConfig.all).then((results) => {
      for (const result of results) {
        if (!result.ok) {
          console.warn(
            `[mount-watchdog] ${result.kind} unhealthy at ${result.mountPath}: ${result.detail}`,
          );
        }
      }
    });
  }, intervalMs);

  if (typeof timer === "object" && "unref" in timer) {
    timer.unref();
  }
}

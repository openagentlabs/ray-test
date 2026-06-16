import { startMountWatchdog } from "@/lib/mount/mount-watchdog";

export async function registerNodeInstrumentation(): Promise<void> {
  if (process.env.MOUNT_WATCHDOG_ENABLED === "false") {
    return;
  }

  startMountWatchdog();
}

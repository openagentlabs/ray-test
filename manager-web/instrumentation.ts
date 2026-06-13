export async function register() {
  if (process.env.MOUNT_WATCHDOG_ENABLED === "false") {
    return;
  }

  const { startMountWatchdog } = await import("@/lib/mount/mount-watchdog");
  startMountWatchdog();
}

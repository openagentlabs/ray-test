export async function register(): Promise<void> {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { registerServerLogging } = await import(
      "@/lib/logging/register-server-logging"
    );
    registerServerLogging();

    const { validateEnvironment } = await import("@/lib/validate-environment");
    const { ServerLogging } = await import("@/lib/logging/server-logging");
    const outcome = await validateEnvironment();
    if (!outcome.ok) {
      const line = `${outcome.message}${
        outcome.detail !== undefined ? ` — ${outcome.detail}` : ""
      }`;
      ServerLogging.emit({
        scope: "aspire.bootstrap",
        severity: "error",
        body: `validateEnvironment failed: ${line}`,
      });
      process.exit(1);
    }
  }
}

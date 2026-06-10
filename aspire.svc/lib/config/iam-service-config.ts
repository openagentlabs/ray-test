/**
 * Server-only settings for `@arb/iam-service-client` (gRPC to iam.svc).
 * Mirrors `frontend/lib/config/iam-service-config.ts` env names so local tooling stays consistent.
 */
export class IamServiceConfig {
  public static readonly host: string =
    process.env.IAM_SERVICE_HOST?.trim() || "127.0.0.1";

  public static readonly port: number = (() => {
    const raw = process.env.IAM_SERVICE_PORT?.trim();
    const n = raw ? Number(raw) : 8803;
    return Number.isFinite(n) && n >= 1 && n <= 65535 ? Math.trunc(n) : 8803;
  })();

  public static readonly accountId: string =
    process.env.IAM_ACCOUNT_ID?.trim() || "00000000-0000-4000-8000-000000000001";

  /** When true, user-type stats APIs return deterministic mock counts (no gRPC). */
  public static readonly useListMock: boolean =
    process.env.IAM_USE_LIST_MOCK === "true";

  private constructor() {}
}

/**
 * Server-side application configuration (secrets and service URLs).
 */
export class AppConfig {
  /** IAM HTTP auth API base URL — `@arb/http-auth-client` target. */
  public static getIamHttpAuthBaseUrl(): string {
    const raw = process.env.IAM_HTTP_AUTH_BASE_URL?.trim();
    if (raw !== undefined && raw.length > 0) {
      return raw.replace(/\/$/, "");
    }
    return "http://127.0.0.1:8873";
  }

  private constructor() {}
}

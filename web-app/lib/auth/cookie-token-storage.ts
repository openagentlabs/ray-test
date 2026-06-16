import type { ResponseCookies } from "next/dist/compiled/@edge-runtime/cookies";
import type { RequestCookies } from "next/dist/compiled/@edge-runtime/cookies";

import {
  AuthTokenBundleSchema,
  type StoredAuthTokens,
  type TokenStorage,
} from "@arb/http-auth-client";

import {
  ACCESS_TOKEN_COOKIE_NAME,
  AUTH_COOKIE_MAX_AGE_SECONDS,
  authCookieOptions,
  clearAuthCookieOptions,
  REFRESH_TOKEN_COOKIE_NAME,
} from "@/lib/auth/session-cookie";

type CookieReader = Pick<RequestCookies, "get">;
type CookieWriter = Pick<ResponseCookies, "set">;

export class NextCookieTokenStorage implements TokenStorage {
  private readonly reader: CookieReader;
  private readonly writer: CookieWriter | null;

  public constructor(reader: CookieReader, writer: CookieWriter | null = null) {
    this.reader = reader;
    this.writer = writer;
  }

  public async load(): Promise<StoredAuthTokens | null> {
    const access = this.reader.get(ACCESS_TOKEN_COOKIE_NAME)?.value;
    const refresh = this.reader.get(REFRESH_TOKEN_COOKIE_NAME)?.value;
    if (!access || !refresh) {
      return null;
    }

    const expiresInRaw = this.reader.get(`${ACCESS_TOKEN_COOKIE_NAME}.expires_in`)?.value;
    const refreshExpiresInRaw = this.reader.get(
      `${REFRESH_TOKEN_COOKIE_NAME}.expires_in`,
    )?.value;
    const accessExpiresAtRaw = this.reader.get(`${ACCESS_TOKEN_COOKIE_NAME}.expires_at`)?.value;
    const refreshExpiresAtRaw = this.reader.get(
      `${REFRESH_TOKEN_COOKIE_NAME}.expires_at`,
    )?.value;

    const now = Math.floor(Date.now() / 1000);
    const expiresIn = Number.parseInt(expiresInRaw ?? "900", 10);
    const refreshExpiresIn = Number.parseInt(refreshExpiresInRaw ?? "86400", 10);
    const accessExpiresAt = Number.parseInt(accessExpiresAtRaw ?? String(now + expiresIn), 10);
    const refreshExpiresAt = Number.parseInt(
      refreshExpiresAtRaw ?? String(now + refreshExpiresIn),
      10,
    );

    const bundle = AuthTokenBundleSchema.parse({
      access_token: access,
      refresh_token: refresh,
      token_type: "Bearer",
      expires_in: expiresIn,
      refresh_expires_in: refreshExpiresIn,
    });

    return {
      ...bundle,
      access_expires_at: accessExpiresAt,
      refresh_expires_at: refreshExpiresAt,
    };
  }

  public async save(tokens: StoredAuthTokens): Promise<void> {
    if (this.writer === null) {
      throw new Error("Cannot save auth tokens without a response cookie writer.");
    }

    this.writer.set(
      ACCESS_TOKEN_COOKIE_NAME,
      tokens.access_token,
      authCookieOptions(Math.max(tokens.expires_in, 60)),
    );
    this.writer.set(
      REFRESH_TOKEN_COOKIE_NAME,
      tokens.refresh_token,
      authCookieOptions(Math.max(tokens.refresh_expires_in, 60)),
    );
    this.writer.set(
      `${ACCESS_TOKEN_COOKIE_NAME}.expires_in`,
      String(tokens.expires_in),
      authCookieOptions(AUTH_COOKIE_MAX_AGE_SECONDS),
    );
    this.writer.set(
      `${REFRESH_TOKEN_COOKIE_NAME}.expires_in`,
      String(tokens.refresh_expires_in),
      authCookieOptions(AUTH_COOKIE_MAX_AGE_SECONDS),
    );
    this.writer.set(
      `${ACCESS_TOKEN_COOKIE_NAME}.expires_at`,
      String(tokens.access_expires_at),
      authCookieOptions(AUTH_COOKIE_MAX_AGE_SECONDS),
    );
    this.writer.set(
      `${REFRESH_TOKEN_COOKIE_NAME}.expires_at`,
      String(tokens.refresh_expires_at),
      authCookieOptions(AUTH_COOKIE_MAX_AGE_SECONDS),
    );
  }

  public async clear(): Promise<void> {
    if (this.writer === null) {
      return;
    }

    const clear = clearAuthCookieOptions();
    this.writer.set(ACCESS_TOKEN_COOKIE_NAME, "", clear);
    this.writer.set(REFRESH_TOKEN_COOKIE_NAME, "", clear);
    this.writer.set(`${ACCESS_TOKEN_COOKIE_NAME}.expires_in`, "", clear);
    this.writer.set(`${REFRESH_TOKEN_COOKIE_NAME}.expires_in`, "", clear);
    this.writer.set(`${ACCESS_TOKEN_COOKIE_NAME}.expires_at`, "", clear);
    this.writer.set(`${REFRESH_TOKEN_COOKIE_NAME}.expires_at`, "", clear);
  }
}

import {
  AuthTokenManager,
  IamAuthClient,
  IamAuthClientError,
} from "@arb/http-auth-client";
import type { ResponseCookies } from "next/dist/compiled/@edge-runtime/cookies";
import type { RequestCookies } from "next/dist/compiled/@edge-runtime/cookies";

import { NextCookieTokenStorage } from "@/lib/auth/cookie-token-storage";
import { displayNameFromEmail } from "@/lib/auth/display-name-from-email";
import {
  clearProfileCookie,
  readProfileCookie,
  writeProfileCookie,
} from "@/lib/auth/profile-cookie";
import { AppConfig } from "@/lib/config/app-config";
import type { UserProfileView } from "@/lib/user/models/user-profile";

type CookieReader = Pick<RequestCookies, "get">;
type CookieWriter = Pick<ResponseCookies, "set">;

export type IamLoginResult =
  | { readonly ok: true; readonly profile: UserProfileView }
  | { readonly ok: false; readonly message: string; readonly status: number };

export class IamAuthRepository {
  private static readonly instance = new IamAuthRepository();

  public static getInstance(): IamAuthRepository {
    return IamAuthRepository.instance;
  }

  public async loginWithPassword(
    email: string,
    password: string,
    reader: CookieReader,
    writer: CookieWriter,
  ): Promise<IamLoginResult> {
    const client = this.createClient();
    const storage = new NextCookieTokenStorage(reader, writer);
    const manager = new AuthTokenManager({ client, storage });

    try {
      const tokens = await manager.login(email.trim(), password);
      const claims = await client.validate(tokens.access_token);
      const normalizedEmail = email.trim().toLowerCase();
      const profile: UserProfileView = {
        userId: claims.sub,
        displayName: displayNameFromEmail(normalizedEmail),
        email: normalizedEmail,
      };
      writeProfileCookie(writer, profile);
      return { ok: true, profile };
    } catch (error) {
      return this.mapClientError(error);
    }
  }

  public async loadSession(
    reader: CookieReader,
    writer: CookieWriter | null,
  ): Promise<UserProfileView | null> {
    const client = this.createClient();
    const storage = new NextCookieTokenStorage(reader, writer);
    const manager = new AuthTokenManager({ client, storage });

    try {
      const accessToken = await manager.getValidAccessToken();
      const claims = await client.validate(accessToken);
      const profile = readProfileCookie(reader);
      if (profile !== null && profile.userId === claims.sub) {
        return profile;
      }
      if (profile !== null) {
        return profile;
      }
      return {
        userId: claims.sub,
        displayName: claims.sub,
        email: "",
      };
    } catch {
      return null;
    }
  }

  public async signOut(reader: CookieReader, writer: CookieWriter): Promise<void> {
    const client = this.createClient();
    const storage = new NextCookieTokenStorage(reader, writer);
    const manager = new AuthTokenManager({ client, storage });
    await manager.signOut();
    clearProfileCookie(writer);
  }

  private createClient(): IamAuthClient {
    return new IamAuthClient({ baseUrl: AppConfig.getIamHttpAuthBaseUrl() });
  }

  private mapClientError(error: unknown): IamLoginResult {
    if (error instanceof IamAuthClientError) {
      const status = error.status === 401 ? 401 : error.status >= 400 ? error.status : 502;
      return {
        ok: false,
        message: error.message || "We could not sign you in. Check your credentials.",
        status,
      };
    }
    return {
      ok: false,
      message: "We could not reach the authentication service. Try again shortly.",
      status: 502,
    };
  }

  private constructor() {}
}

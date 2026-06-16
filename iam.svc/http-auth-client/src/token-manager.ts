import { IamAuthClient, type AuthTokenBundle } from "./index.js";

const REFRESH_BUFFER_SECONDS = 120;

export type StoredAuthTokens = AuthTokenBundle & {
  access_expires_at: number;
  refresh_expires_at: number;
};

export type TokenManagerConfig = {
  client: IamAuthClient;
  storage: TokenStorage;
};

export interface TokenStorage {
  load(): Promise<StoredAuthTokens | null>;
  save(tokens: StoredAuthTokens): Promise<void>;
  clear(): Promise<void>;
}

export class InMemoryTokenStorage implements TokenStorage {
  private tokens: StoredAuthTokens | null = null;

  public async load(): Promise<StoredAuthTokens | null> {
    return this.tokens;
  }

  public async save(tokens: StoredAuthTokens): Promise<void> {
    this.tokens = tokens;
  }

  public async clear(): Promise<void> {
    this.tokens = null;
  }
}

export class AuthTokenManager {
  private readonly client: IamAuthClient;
  private readonly storage: TokenStorage;
  private refreshPromise: Promise<StoredAuthTokens> | null = null;

  public constructor(config: TokenManagerConfig) {
    this.client = config.client;
    this.storage = config.storage;
  }

  public async login(email: string, password: string): Promise<StoredAuthTokens> {
    const bundle = await this.client.login({ email, password });
    const stored = this.toStored(bundle);
    await this.storage.save(stored);
    return stored;
  }

  public async getValidAccessToken(): Promise<string> {
    const tokens = await this.ensureFreshTokens();
    return tokens.access_token;
  }

  public async signOut(): Promise<void> {
    const tokens = await this.storage.load();
    if (tokens) {
      try {
        await this.client.logout(tokens.access_token, tokens.refresh_token);
      } catch {
        // best effort
      }
    }
    await this.storage.clear();
  }

  private async ensureFreshTokens(): Promise<StoredAuthTokens> {
    const current = await this.storage.load();
    if (!current) {
      throw new Error("No auth session is available.");
    }
    const now = Math.floor(Date.now() / 1000);
    if (current.access_expires_at - now > REFRESH_BUFFER_SECONDS) {
      return current;
    }
    if (this.refreshPromise) {
      return this.refreshPromise;
    }
    this.refreshPromise = this.refreshTokens(current).finally(() => {
      this.refreshPromise = null;
    });
    return this.refreshPromise;
  }

  private async refreshTokens(current: StoredAuthTokens): Promise<StoredAuthTokens> {
    const now = Math.floor(Date.now() / 1000);
    if (current.refresh_expires_at <= now) {
      await this.storage.clear();
      throw new Error("Refresh token expired; re-authentication required.");
    }
    try {
      const bundle = await this.client.refresh(current.refresh_token);
      const stored = this.toStored(bundle);
      await this.storage.save(stored);
      return stored;
    } catch {
      await this.storage.clear();
      throw new Error("Token refresh failed; re-authentication required.");
    }
  }

  private toStored(bundle: AuthTokenBundle): StoredAuthTokens {
    const now = Math.floor(Date.now() / 1000);
    return {
      ...bundle,
      access_expires_at: now + bundle.expires_in,
      refresh_expires_at: now + bundle.refresh_expires_in,
    };
  }
}

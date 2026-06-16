import { z } from "zod";

export const AuthTokenBundleSchema = z.object({
  access_token: z.string().min(1),
  refresh_token: z.string().min(1),
  token_type: z.string().default("Bearer"),
  expires_in: z.number().int().positive(),
  refresh_expires_in: z.number().int().positive(),
});

export type AuthTokenBundle = z.infer<typeof AuthTokenBundleSchema>;

export const ValidateTokenResponseSchema = z.object({
  valid: z.literal(true),
  sub: z.string(),
  jti: z.string(),
  perm: z.string(),
  exp: z.number(),
});

export type ValidateTokenResponse = z.infer<typeof ValidateTokenResponseSchema>;

export const JwksDocumentSchema = z.object({
  keys: z.array(
    z.object({
      kty: z.string(),
      kid: z.string(),
      use: z.string(),
      alg: z.string(),
      n: z.string(),
      e: z.string(),
    }),
  ),
});

export type JwksDocument = z.infer<typeof JwksDocumentSchema>;

export const LoginRequestSchema = z.object({
  email: z.email(),
  password: z.string().min(1),
});

export type LoginRequest = z.infer<typeof LoginRequestSchema>;

export class IamAuthClientError extends Error {
  public readonly status: number;
  public readonly code: string;

  public constructor(message: string, status: number, code: string) {
    super(message);
    this.name = "IamAuthClientError";
    this.status = status;
    this.code = code;
  }
}

export type IamAuthClientConfig = {
  baseUrl: string;
  fetchImpl?: typeof fetch;
};

export class IamAuthClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;

  public constructor(config: IamAuthClientConfig) {
    this.baseUrl = config.baseUrl.replace(/\/$/, "");
    this.fetchImpl = config.fetchImpl ?? fetch;
  }

  public async login(request: LoginRequest): Promise<AuthTokenBundle> {
    const response = await this.fetchImpl(`${this.baseUrl}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    return this.parseJson(response, AuthTokenBundleSchema);
  }

  public async refresh(refreshToken: string): Promise<AuthTokenBundle> {
    const response = await this.fetchImpl(`${this.baseUrl}/auth/refresh`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Refresh-Token": refreshToken,
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    return this.parseJson(response, AuthTokenBundleSchema);
  }

  public async validate(accessToken: string): Promise<ValidateTokenResponse> {
    const response = await this.fetchImpl(`${this.baseUrl}/auth/validate`, {
      method: "GET",
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    return this.parseJson(response, ValidateTokenResponseSchema);
  }

  public async logout(accessToken: string, refreshToken?: string): Promise<void> {
    const headers: Record<string, string> = {
      Authorization: `Bearer ${accessToken}`,
    };
    if (refreshToken) {
      headers["X-Refresh-Token"] = refreshToken;
    }
    const response = await this.fetchImpl(`${this.baseUrl}/auth/logout`, {
      method: "POST",
      headers,
    });
    if (!response.ok) {
      await this.throwFromResponse(response);
    }
  }

  public async fetchJwks(): Promise<JwksDocument> {
    const response = await this.fetchImpl(`${this.baseUrl}/.well-known/jwks.json`);
    return this.parseJson(response, JwksDocumentSchema);
  }

  /** Same JWKS document as ``fetchJwks`` — served at ``/auth/jwks`` on the IAM HTTP auth API. */
  public async fetchAuthJwks(): Promise<JwksDocument> {
    const response = await this.fetchImpl(`${this.baseUrl}/auth/jwks`);
    return this.parseJson(response, JwksDocumentSchema);
  }

  private async parseJson<T>(
    response: Response,
    schema: { parse: (value: unknown) => T },
  ): Promise<T> {
    if (!response.ok) {
      await this.throwFromResponse(response);
    }
    const body: unknown = await response.json();
    return schema.parse(body);
  }

  private async throwFromResponse(response: Response): Promise<never> {
    let message = `IAM auth request failed (${response.status})`;
    let code = "upstream";
    try {
      const body: unknown = await response.json();
      if (
        typeof body === "object" &&
        body !== null &&
        "error" in body &&
        typeof body.error === "object" &&
        body.error !== null
      ) {
        const errObj = body.error as { message?: string; code?: string };
        if (errObj.message) {
          message = errObj.message;
        }
        if (errObj.code) {
          code = errObj.code;
        }
      }
    } catch {
      // ignore parse errors
    }
    throw new IamAuthClientError(message, response.status, code);
  }
}

export * from "./token-manager.js";

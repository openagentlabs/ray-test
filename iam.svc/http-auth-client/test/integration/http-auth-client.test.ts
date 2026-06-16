import { describe, expect, it, vi } from "vitest";

import { IamAuthClient, IamAuthClientError } from "../../src/index.js";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("IamAuthClient HTTP integration", () => {
  it("calls login, refresh, validate, logout, and both JWKS routes", async () => {
    const fetchImpl = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith("/auth/login") && init?.method === "POST") {
        return jsonResponse({
          access_token: "access",
          refresh_token: "refresh",
          token_type: "Bearer",
          expires_in: 900,
          refresh_expires_in: 86400,
        });
      }
      if (url.endsWith("/auth/refresh") && init?.method === "POST") {
        return jsonResponse({
          access_token: "access2",
          refresh_token: "refresh2",
          token_type: "Bearer",
          expires_in: 900,
          refresh_expires_in: 86400,
        });
      }
      if (url.endsWith("/auth/validate") && init?.method === "GET") {
        return jsonResponse({
          valid: true,
          sub: "user-1",
          jti: "session-1",
          perm: "iam-svc:ping",
          exp: 9999999999,
        });
      }
      if (url.endsWith("/auth/logout") && init?.method === "POST") {
        return jsonResponse({});
      }
      if (url.endsWith("/.well-known/jwks.json")) {
        return jsonResponse({
          keys: [
            {
              kty: "RSA",
              kid: "kid-1",
              use: "sig",
              alg: "RS256",
              n: "abc",
              e: "AQAB",
            },
          ],
        });
      }
      if (url.endsWith("/auth/jwks")) {
        return jsonResponse({
          keys: [
            {
              kty: "RSA",
              kid: "kid-1",
              use: "sig",
              alg: "RS256",
              n: "abc",
              e: "AQAB",
            },
          ],
        });
      }
      return jsonResponse({ error: { code: "not_found", message: "missing" } }, 404);
    });

    const client = new IamAuthClient({
      baseUrl: "http://127.0.0.1:8873",
      fetchImpl,
    });

    const tokens = await client.login({ email: "ada@example.com", password: "secret1" });
    expect(tokens.access_token).toBe("access");

    const refreshed = await client.refresh(tokens.refresh_token);
    expect(refreshed.access_token).toBe("access2");

    const claims = await client.validate(refreshed.access_token);
    expect(claims.sub).toBe("user-1");

    await client.logout(refreshed.access_token, refreshed.refresh_token);

    const wellKnown = await client.fetchJwks();
    const authPath = await client.fetchAuthJwks();
    expect(wellKnown.keys).toHaveLength(1);
    expect(authPath.keys[0]?.kid).toBe("kid-1");
  });

  it("maps server error payloads to IamAuthClientError", async () => {
    const client = new IamAuthClient({
      baseUrl: "http://127.0.0.1:8873",
      fetchImpl: async () =>
        jsonResponse({ error: { code: "validation", message: "Invalid credentials." } }, 401),
    });

    await expect(client.login({ email: "bad@example.com", password: "x" })).rejects.toMatchObject({
      name: "IamAuthClientError",
      status: 401,
      code: "validation",
      message: "Invalid credentials.",
    } satisfies Partial<IamAuthClientError>);
  });
});

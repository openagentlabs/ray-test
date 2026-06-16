import { describe, expect, it } from "vitest";

import { AuthTokenManager, InMemoryTokenStorage } from "../../src/token-manager.js";
import { IamAuthClient } from "../../src/index.js";

describe("AuthTokenManager", () => {
  it("returns cached access token when not near expiry", async () => {
    const storage = new InMemoryTokenStorage();
    const now = Math.floor(Date.now() / 1000);
    await storage.save({
      access_token: "access",
      refresh_token: "refresh",
      token_type: "Bearer",
      expires_in: 900,
      refresh_expires_in: 86400,
      access_expires_at: now + 900,
      refresh_expires_at: now + 86400,
    });
    const client = new IamAuthClient({ baseUrl: "http://127.0.0.1:8873" });
    const manager = new AuthTokenManager({ client, storage });
    await expect(manager.getValidAccessToken()).resolves.toBe("access");
  });
});

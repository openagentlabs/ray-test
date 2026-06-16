import { randomUUID } from "node:crypto";

import { hashPassword, verifyPassword } from "@/lib/auth/password";
import { getUserAuthDatabase } from "@/lib/auth/user-auth-database";
import type {
  SessionRecord,
  UserProfileRecord,
  UserRecord,
} from "@/lib/auth/user-auth-schema";
import { SESSION_MAX_AGE_SECONDS } from "@/lib/auth/session-cookie";

export class UserAuthRepository {
  private static readonly instance: UserAuthRepository =
    new UserAuthRepository();

  public static getInstance(): UserAuthRepository {
    return UserAuthRepository.instance;
  }

  public async createUser(input: {
    readonly email: string;
    readonly displayName: string;
    readonly password: string;
  }): Promise<
    | { readonly ok: true; readonly userId: string }
    | { readonly ok: false; readonly code: "email_taken" | "failed"; readonly message: string }
  > {
    const db = getUserAuthDatabase();
    const id = randomUUID();
    const now = new Date().toISOString();
    const passwordHash = await hashPassword(input.password);

    try {
      db.prepare(
        `INSERT INTO users (id, email, display_name, password_hash, created_at)
         VALUES (@id, @email, @display_name, @password_hash, @created_at)`,
      ).run({
        id,
        email: input.email.trim().toLowerCase(),
        display_name: input.displayName.trim(),
        password_hash: passwordHash,
        created_at: now,
      });
      return { ok: true, userId: id };
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      if (message.includes("UNIQUE constraint failed")) {
        return {
          ok: false,
          code: "email_taken",
          message: "An account with this email already exists.",
        };
      }
      return { ok: false, code: "failed", message: "Could not create account." };
    }
  }

  public async verifyLogin(input: {
    readonly email: string;
    readonly password: string;
  }): Promise<
    | { readonly ok: true; readonly user: UserProfileRecord }
    | { readonly ok: false; readonly message: string }
  > {
    const db = getUserAuthDatabase();
    const row = db
      .prepare(
        `SELECT id, email, display_name, password_hash
         FROM users WHERE email = @email COLLATE NOCASE LIMIT 1`,
      )
      .get({ email: input.email.trim().toLowerCase() }) as
      | Pick<UserRecord, "id" | "email" | "display_name" | "password_hash">
      | undefined;

    if (row === undefined) {
      return { ok: false, message: "Invalid email or password." };
    }

    const valid = await verifyPassword(input.password, row.password_hash);
    if (!valid) {
      return { ok: false, message: "Invalid email or password." };
    }

    return {
      ok: true,
      user: {
        userId: row.id,
        displayName: row.display_name,
        email: row.email,
      },
    };
  }

  public createSession(userId: string): string {
    const db = getUserAuthDatabase();
    const sessionId = randomUUID();
    const expiresAt = new Date(
      Date.now() + SESSION_MAX_AGE_SECONDS * 1000,
    ).toISOString();

    db.prepare(
      `INSERT INTO sessions (id, user_id, expires_at) VALUES (@id, @user_id, @expires_at)`,
    ).run({ id: sessionId, user_id: userId, expires_at: expiresAt });

    return sessionId;
  }

  public deleteSession(sessionId: string): void {
    const db = getUserAuthDatabase();
    db.prepare(`DELETE FROM sessions WHERE id = @id`).run({ id: sessionId });
  }

  public findProfileBySessionId(sessionId: string): UserProfileRecord | null {
    const db = getUserAuthDatabase();
    this.purgeExpiredSessions();

    const row = db
      .prepare(
        `SELECT u.id AS userId, u.display_name AS displayName, u.email AS email,
                s.expires_at AS expiresAt
         FROM sessions s
         JOIN users u ON u.id = s.user_id
         WHERE s.id = @sessionId
         LIMIT 1`,
      )
      .get({ sessionId }) as
      | (UserProfileRecord & { readonly expiresAt: string })
      | undefined;

    if (row === undefined) {
      return null;
    }

    if (new Date(row.expiresAt).getTime() <= Date.now()) {
      this.deleteSession(sessionId);
      return null;
    }

    return {
      userId: row.userId,
      displayName: row.displayName,
      email: row.email,
    };
  }

  private purgeExpiredSessions(): void {
    const db = getUserAuthDatabase();
    db.prepare(`DELETE FROM sessions WHERE expires_at <= @now`).run({
      now: new Date().toISOString(),
    });
  }

  private constructor() {}
}

export type { SessionRecord };

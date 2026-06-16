import {
  AnyhowResultFactory,
  type SessionLoadResult,
  type SignOutResult,
} from "@/lib/types/anyhow";
import type { UserProfileView } from "@/lib/user/models/user-profile";

export class UserSessionClient {
  private static readonly instance: UserSessionClient =
    new UserSessionClient();

  public static getInstance(): UserSessionClient {
    return UserSessionClient.instance;
  }

  public async getCurrentSession(): Promise<UserProfileView | null> {
    const result: SessionLoadResult = await this.loadSession();
    if (!result.ok) {
      return null;
    }
    return {
      userId: result.value.userId,
      displayName: result.value.displayName,
      email: result.value.email,
    };
  }

  public async loadSession(): Promise<SessionLoadResult> {
    try {
      const response = await fetch("/api/auth/session", {
        method: "GET",
        credentials: "same-origin",
      });
      if (!response.ok) {
        return AnyhowResultFactory.err("Session is not authenticated.");
      }
      const body = (await response.json()) as UserProfileView;
      return AnyhowResultFactory.ok(body);
    } catch {
      return AnyhowResultFactory.err("Could not load session.");
    }
  }

  public async signOut(): Promise<SignOutResult> {
    try {
      const response = await fetch("/api/auth/logout", {
        method: "POST",
        credentials: "same-origin",
      });
      if (!response.ok) {
        return AnyhowResultFactory.err("Sign out failed.");
      }
      return AnyhowResultFactory.ok(undefined);
    } catch {
      return AnyhowResultFactory.err("Sign out failed.");
    }
  }

  private constructor() {}
}

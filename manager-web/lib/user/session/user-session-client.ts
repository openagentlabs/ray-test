import {
  AnyhowResultFactory,
  type SessionLoadResult,
  type SignOutResult,
} from "@/lib/types/anyhow";
import type { UserProfileView } from "@/lib/user/models/user-profile";

const DEMO_PROFILE: UserProfileView = Object.freeze({
  userId: "demo-user",
  displayName: "Manager User",
  email: "manager@example.com",
});

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
    return AnyhowResultFactory.ok({
      userId: DEMO_PROFILE.userId,
      displayName: DEMO_PROFILE.displayName,
      email: DEMO_PROFILE.email,
    });
  }

  public async signOut(): Promise<SignOutResult> {
    return AnyhowResultFactory.ok(undefined);
  }

  private constructor() {}
}

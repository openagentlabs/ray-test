import type { ResponseCookies } from "next/dist/compiled/@edge-runtime/cookies";
import type { RequestCookies } from "next/dist/compiled/@edge-runtime/cookies";
import { z } from "zod";

import {
  PROFILE_COOKIE_NAME,
  AUTH_COOKIE_MAX_AGE_SECONDS,
  authCookieOptions,
  clearAuthCookieOptions,
} from "@/lib/auth/session-cookie";
import type { UserProfileView } from "@/lib/user/models/user-profile";

const ProfileCookieSchema = z.object({
  userId: z.string().min(1),
  displayName: z.string().min(1),
  email: z.email(),
});

type CookieReader = Pick<RequestCookies, "get">;
type CookieWriter = Pick<ResponseCookies, "set">;

export function readProfileCookie(reader: CookieReader): UserProfileView | null {
  const raw = reader.get(PROFILE_COOKIE_NAME)?.value;
  if (!raw) {
    return null;
  }
  try {
    const parsed = ProfileCookieSchema.parse(JSON.parse(raw));
    return parsed;
  } catch {
    return null;
  }
}

export function writeProfileCookie(writer: CookieWriter, profile: UserProfileView): void {
  writer.set(
    PROFILE_COOKIE_NAME,
    JSON.stringify(profile),
    authCookieOptions(AUTH_COOKIE_MAX_AGE_SECONDS),
  );
}

export function clearProfileCookie(writer: CookieWriter): void {
  writer.set(PROFILE_COOKIE_NAME, "", clearAuthCookieOptions());
}

export const ACCESS_TOKEN_COOKIE_NAME = "manager_web.auth.access";
export const REFRESH_TOKEN_COOKIE_NAME = "manager_web.auth.refresh";
export const PROFILE_COOKIE_NAME = "manager_web.auth.profile";

export const AUTH_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 14;

export function authCookieOptions(maxAge: number): {
  readonly httpOnly: true;
  readonly sameSite: "lax";
  readonly path: "/";
  readonly maxAge: number;
  readonly secure: boolean;
} {
  return {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge,
    secure: process.env.NODE_ENV === "production",
  };
}

export function clearAuthCookieOptions(): {
  readonly httpOnly: true;
  readonly sameSite: "lax";
  readonly path: "/";
  readonly maxAge: 0;
  readonly secure: boolean;
} {
  return {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 0,
    secure: process.env.NODE_ENV === "production",
  };
}

export const SESSION_COOKIE_NAME = "aspire_session";

export const SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 14;

export function sessionCookieOptions(): {
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
    maxAge: SESSION_MAX_AGE_SECONDS,
    secure: process.env.NODE_ENV === "production",
  };
}

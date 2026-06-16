import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { UserAuthRepository } from "@/lib/auth/user-auth-repository";
import {
  SESSION_COOKIE_NAME,
  sessionCookieOptions,
} from "@/lib/auth/session-cookie";

export async function POST(): Promise<NextResponse> {
  const cookieStore = await cookies();
  const sessionId = cookieStore.get(SESSION_COOKIE_NAME)?.value;

  if (sessionId !== undefined && sessionId.length > 0) {
    UserAuthRepository.getInstance().deleteSession(sessionId);
  }

  const response = NextResponse.json({ ok: true });
  response.cookies.set(SESSION_COOKIE_NAME, "", {
    ...sessionCookieOptions(),
    maxAge: 0,
  });
  return response;
}

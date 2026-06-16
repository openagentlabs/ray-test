import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { UserAuthRepository } from "@/lib/auth/user-auth-repository";
import {
  SESSION_COOKIE_NAME,
  sessionCookieOptions,
} from "@/lib/auth/session-cookie";
import { LoginFormSchema } from "@/lib/auth/validation/auth-schemas";

export async function POST(request: Request): Promise<NextResponse> {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { message: "Invalid request body." },
      { status: 400 },
    );
  }

  const parsed = LoginFormSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { message: parsed.error.issues[0]?.message ?? "Invalid input." },
      { status: 400 },
    );
  }

  const login = await UserAuthRepository.getInstance().verifyLogin(parsed.data);
  if (!login.ok) {
    return NextResponse.json({ message: login.message }, { status: 401 });
  }

  const sessionId = UserAuthRepository.getInstance().createSession(
    login.user.userId,
  );

  const response = NextResponse.json(login.user);
  response.cookies.set(SESSION_COOKIE_NAME, sessionId, sessionCookieOptions());
  return response;
}

export async function DELETE(): Promise<NextResponse> {
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

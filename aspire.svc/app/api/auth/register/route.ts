import { NextResponse } from "next/server";

import { UserAuthRepository } from "@/lib/auth/user-auth-repository";
import {
  SESSION_COOKIE_NAME,
  sessionCookieOptions,
} from "@/lib/auth/session-cookie";
import { RegisterFormSchema } from "@/lib/auth/validation/auth-schemas";

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

  const parsed = RegisterFormSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { message: parsed.error.issues[0]?.message ?? "Invalid input." },
      { status: 400 },
    );
  }

  const created = await UserAuthRepository.getInstance().createUser({
    email: parsed.data.email,
    displayName: parsed.data.displayName,
    password: parsed.data.password,
  });

  if (!created.ok) {
    const status = created.code === "email_taken" ? 409 : 500;
    return NextResponse.json({ message: created.message }, { status });
  }

  const sessionId = UserAuthRepository.getInstance().createSession(
    created.userId,
  );

  const profile = UserAuthRepository.getInstance().findProfileBySessionId(
    sessionId,
  );

  if (profile === null) {
    return NextResponse.json(
      { message: "Account created but session could not start." },
      { status: 500 },
    );
  }

  const response = NextResponse.json(profile, { status: 201 });
  response.cookies.set(SESSION_COOKIE_NAME, sessionId, sessionCookieOptions());
  return response;
}

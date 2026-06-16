import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { UserAuthRepository } from "@/lib/auth/user-auth-repository";
import {
  SESSION_COOKIE_NAME,
} from "@/lib/auth/session-cookie";

export async function GET(): Promise<NextResponse> {
  const cookieStore = await cookies();
  const sessionId = cookieStore.get(SESSION_COOKIE_NAME)?.value;

  if (sessionId === undefined || sessionId.length === 0) {
    return NextResponse.json({ message: "Not signed in." }, { status: 401 });
  }

  const profile = UserAuthRepository.getInstance().findProfileBySessionId(
    sessionId,
  );

  if (profile === null) {
    return NextResponse.json({ message: "Not signed in." }, { status: 401 });
  }

  return NextResponse.json(profile);
}

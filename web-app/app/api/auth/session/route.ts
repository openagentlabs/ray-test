import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { IamAuthRepository } from "@/lib/auth/iam-auth-repository";

export async function GET(): Promise<NextResponse> {
  const cookieStore = await cookies();
  const response = NextResponse.json({ message: "Not signed in." }, { status: 401 });

  const profile = await IamAuthRepository.getInstance().loadSession(
    cookieStore,
    response.cookies,
  );

  if (profile === null) {
    return response;
  }

  return NextResponse.json(profile);
}

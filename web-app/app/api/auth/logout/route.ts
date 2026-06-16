import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { IamAuthRepository } from "@/lib/auth/iam-auth-repository";

export async function POST(): Promise<NextResponse> {
  const cookieStore = await cookies();
  const response = NextResponse.json({ ok: true });

  await IamAuthRepository.getInstance().signOut(cookieStore, response.cookies);

  return response;
}

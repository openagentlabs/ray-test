import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { IamAuthRepository } from "@/lib/auth/iam-auth-repository";
import { LoginFormSchema } from "@/lib/auth/validation/auth-schemas";

export async function POST(request: Request): Promise<NextResponse> {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ message: "Invalid request body." }, { status: 400 });
  }

  const parsed = LoginFormSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { message: parsed.error.issues[0]?.message ?? "Invalid input." },
      { status: 400 },
    );
  }

  const cookieStore = await cookies();
  const response = NextResponse.json({ ok: true });

  const login = await IamAuthRepository.getInstance().loginWithPassword(
    parsed.data.email,
    parsed.data.password,
    cookieStore,
    response.cookies,
  );

  if (!login.ok) {
    return NextResponse.json({ message: login.message }, { status: login.status });
  }

  return NextResponse.json(login.profile);
}

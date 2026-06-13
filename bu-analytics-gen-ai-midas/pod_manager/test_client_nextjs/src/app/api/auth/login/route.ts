import { NextResponse } from "next/server";

import { envoyUrl, SESSION_COOKIE } from "@/lib/env";

type LoginBody = {
  user_name?: unknown;
  user_password?: unknown;
};

type LoginResponsePayload = {
  success: boolean;
  error_code: number;
  message: string;
};

function normalizeEmail(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const email = value.trim().toLowerCase();
  return email.length > 0 ? email : null;
}

async function readLoginResponse(res: Response): Promise<LoginResponsePayload> {
  const text = await res.text();
  if (!text.trim()) {
    return {
      success: false,
      error_code: res.status,
      message:
        res.status === 403
          ? "Envoy denied the login request (missing identity). Is the local stack running with auth.dev_mode?"
          : `Upstream returned ${res.status} with an empty body.`,
    };
  }
  try {
    return JSON.parse(text) as LoginResponsePayload;
  } catch {
    return {
      success: false,
      error_code: res.status,
      message: `Upstream returned non-JSON (${res.status}).`,
    };
  }
}

export async function POST(request: Request) {
  const body = (await request.json()) as LoginBody;
  const email = normalizeEmail(body.user_name);
  if (!email) {
    return NextResponse.json(
      {
        success: false,
        error_code: 4001,
        message: "user_name must be a valid email address.",
      },
      { status: 400 },
    );
  }

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  // Local dev: ext_authz accepts x-test-sub when router auth.dev_mode is true.
  headers["x-test-sub"] = email;

  const res = await fetch(`${envoyUrl()}/login`, {
    method: "POST",
    headers,
    body: JSON.stringify({ user_name: email, user_password: body.user_password ?? "" }),
  });
  const data = await readLoginResponse(res);
  const response = NextResponse.json(data, { status: data.success ? res.status : res.status || 502 });
  if (data.success) {
    response.cookies.set(SESSION_COOKIE, email, {
      httpOnly: true,
      sameSite: "lax",
      path: "/",
    });
  }
  return response;
}

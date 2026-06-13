import { NextResponse } from "next/server";

import { releaseLease } from "@/lib/pod-manager";
import { getSessionEmail } from "@/lib/session";

export async function POST() {
  const email = await getSessionEmail();
  if (!email) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 });
  }
  await releaseLease(email);
  return NextResponse.json({ ok: true });
}

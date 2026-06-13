import { NextResponse } from "next/server";

import { getSessionEmail } from "@/lib/session";

export async function GET() {
  const email = await getSessionEmail();
  return NextResponse.json({ email });
}

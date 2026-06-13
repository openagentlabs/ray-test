import { cookies } from "next/headers";

import { SESSION_COOKIE } from "@/lib/env";

export async function getSessionEmail(): Promise<string | null> {
  const jar = await cookies();
  const value = jar.get(SESSION_COOKIE)?.value?.trim();
  return value && value.includes("@") ? value : null;
}

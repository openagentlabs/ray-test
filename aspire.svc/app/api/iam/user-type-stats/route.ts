import { NextResponse } from "next/server";

import { loadUserTypeStatsForArchitectWorkspace } from "@/lib/iam/user-type-stats-server";

export const dynamic = "force-dynamic";

/**
 * GET JSON for IAM user-type counts (gRPC `GetUserTypeStats`), shaped for the architect workspace panels.
 */
export async function GET() {
  try {
    const body = await loadUserTypeStatsForArchitectWorkspace();
    return NextResponse.json(body);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Failed to load user type stats.";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}

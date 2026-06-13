import { NextResponse } from "next/server";

import { getLease } from "@/lib/pod-manager";
import { getSessionEmail } from "@/lib/session";

export async function GET() {
  const email = await getSessionEmail();
  if (!email) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 });
  }
  const lease = await getLease(email);
  if (!lease) {
    return NextResponse.json({ hasLease: false });
  }
  return NextResponse.json({
    hasLease: true,
    lease: {
      podId: lease.podId,
      podDns: lease.podDns,
      assignmentEpoch: lease.assignmentEpoch,
    },
  });
}

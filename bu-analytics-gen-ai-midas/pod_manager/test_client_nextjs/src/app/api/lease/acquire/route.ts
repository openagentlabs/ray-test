import { NextResponse } from "next/server";

import { acquireLease, NoBackendLeaseAvailableError } from "@/lib/pod-manager";
import { getSessionEmail } from "@/lib/session";

export async function POST() {
  const email = await getSessionEmail();
  if (!email) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 });
  }
  try {
    const lease = await acquireLease(email);
    return NextResponse.json({
      ok: true,
      lease: {
        podId: lease.podId,
        podDns: lease.podDns,
        assignmentEpoch: lease.assignmentEpoch,
      },
      alreadyLeased: lease.alreadyLeased,
    });
  } catch (err) {
    if (err instanceof NoBackendLeaseAvailableError) {
      return NextResponse.json(
        { ok: false, error: "no_capacity", message: err.message },
        { status: 503 },
      );
    }
    throw err;
  }
}

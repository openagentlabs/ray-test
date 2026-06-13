import { NextResponse } from "next/server";

import { getBackendPoolAvailability } from "@/lib/pod-manager";

export async function GET() {
  const availability = await getBackendPoolAvailability();
  return NextResponse.json(availability);
}

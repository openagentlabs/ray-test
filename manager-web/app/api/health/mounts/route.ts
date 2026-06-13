import { NextResponse } from "next/server";

import { SharedMountConfig } from "@/lib/config/shared-mount-config";
import { probeAllSharedMounts } from "@/lib/mount/shared-mount-health";

export const dynamic = "force-dynamic";

/**
 * Liveness/readiness probe target when shared Lustre and S3 PVCs are mounted.
 * Returns 503 when any required mount is unreachable so Kubernetes can restart the pod.
 */
export async function GET() {
  const results = await probeAllSharedMounts(SharedMountConfig.all);
  const healthy = results.every((result) => result.ok);

  return NextResponse.json(
    {
      healthy,
      mounts: results,
    },
    { status: healthy ? 200 : 503 },
  );
}

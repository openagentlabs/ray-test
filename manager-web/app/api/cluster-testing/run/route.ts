import { runClusterMountTest } from "@/lib/cluster-testing/run-cluster-mount-test";
import { runSharedMountTestRequestSchema } from "@/lib/cluster-testing/schemas";
import type { ClusterMountTestResult } from "@/lib/cluster-testing/types";
import {
  SharedMountConfig,
  type SharedMountKind,
} from "@/lib/config/shared-mount-config";

export async function POST(request: Request): Promise<Response> {
  const encoder = new TextEncoder();
  let mountKind: SharedMountKind = SharedMountConfig.lustre.kind;

  try {
    const body: unknown = await request.json();
    const parsed = runSharedMountTestRequestSchema.safeParse(body);
    if (!parsed.success) {
      return Response.json(
        { error: "Invalid request: mountKind must be lustre or s3-shared-files." },
        { status: 400 },
      );
    }
    mountKind = parsed.data.mountKind;
  } catch {
    return Response.json(
      { error: "Invalid request body." },
      { status: 400 },
    );
  }

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const send = (payload: ClusterMountTestResult) => {
        controller.enqueue(encoder.encode(`${JSON.stringify(payload)}\n`));
      };

      try {
        await runClusterMountTest(mountKind, (snapshot) => {
          send(snapshot);
        });
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Mount test failed unexpectedly";
        send({
          mountKind,
          volumeName: SharedMountConfig.get(mountKind).volumeName,
          displayName: SharedMountConfig.get(mountKind).displayName,
          mountPath: SharedMountConfig.get(mountKind).mountPath,
          testFilePath: "",
          steps: [],
          logs: [message],
          startedAt: new Date().toISOString(),
          completedAt: new Date().toISOString(),
          overallSuccess: false,
        });
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "application/x-ndjson; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}

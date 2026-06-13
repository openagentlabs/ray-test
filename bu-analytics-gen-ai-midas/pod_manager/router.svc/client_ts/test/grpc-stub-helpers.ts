import * as grpc from "@grpc/grpc-js";
import { vi } from "vitest";

import type { PodManagerClientOptions } from "../src/index.js";

export type UnaryCb<Res> = (error: grpc.ServiceError | null, response?: Res) => void;

export function clientTestOptions(): PodManagerClientOptions {
  return { host: "127.0.0.1", port: 9 };
}

export function stubUnary<Res>(
  impl: (req: unknown, metadata: grpc.Metadata, options: Partial<grpc.CallOptions>, cb: UnaryCb<Res>) => void,
) {
  return vi.fn(impl);
}

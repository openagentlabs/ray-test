import * as grpc from "@grpc/grpc-js";
import { describe, expect, it } from "vitest";

import { PodManagerClientError } from "../src/errors.js";

describe("PodManagerClientError", () => {
  it("stores gRPC status code", () => {
    const err = new PodManagerClientError("unavailable", grpc.status.UNAVAILABLE);
    expect(err.code).toBe(grpc.status.UNAVAILABLE);
  });

  it("fromGrpc uses details when present", () => {
    const mapped = PodManagerClientError.fromGrpc({
      code: grpc.status.INVALID_ARGUMENT,
      message: "INVALID_ARGUMENT",
      details: "bad sub",
    });
    expect(mapped.message).toBe("bad sub");
    expect(mapped.code).toBe(grpc.status.INVALID_ARGUMENT);
  });
});

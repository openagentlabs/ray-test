import { describe, expect, it } from "vitest";

import { PodManagerClient, PodManagerClientValidationError } from "../src/index.js";
import { clientTestOptions, stubUnary } from "./grpc-stub-helpers.js";

type StubClient = {
  acquireLease: ReturnType<
    typeof stubUnary<{ podId: string; podDns: string; assignmentEpoch: number }>
  >;
};

function stub(client: PodManagerClient): StubClient {
  return (client as unknown as { _stub: StubClient })._stub;
}

describe("PodManagerClient", () => {
  it("acquireLease forwards sub and maps response", async () => {
    const client = new PodManagerClient(clientTestOptions());
    const spy = stubUnary((req, _md, _opts, cb) => {
      expect(req).toEqual({ sub: "alice" });
      cb(null, {
        podId: "backend-0",
        podDns: "backend-0.backend.svc",
        assignmentEpoch: 1,
        alreadyLeased: false,
      });
    });
    stub(client).acquireLease = spy;

    await expect(client.acquireLease("alice")).resolves.toEqual({
      podId: "backend-0",
      podDns: "backend-0.backend.svc",
      assignmentEpoch: 1,
      alreadyLeased: false,
    });
    expect(spy).toHaveBeenCalledTimes(1);
    client.close();
  });

  it("acquireLease rejects empty sub before gRPC", async () => {
    const client = new PodManagerClient(clientTestOptions());
    await expect(client.acquireLease("")).rejects.toBeInstanceOf(PodManagerClientValidationError);
    client.close();
  });
});

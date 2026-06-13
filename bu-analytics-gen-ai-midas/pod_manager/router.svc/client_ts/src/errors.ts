import * as grpc from "@grpc/grpc-js";

import type { GrpcServiceErrorLike } from "./internal/grpc-unary.js";

/** Raised when a ``PodManagerService`` RPC fails. */
export class PodManagerClientError extends Error {
  readonly code: grpc.status;

  constructor(message: string, code: grpc.status) {
    super(message);
    this.name = "PodManagerClientError";
    this.code = code;
  }

  static fromGrpc(error: GrpcServiceErrorLike): PodManagerClientError {
    return new PodManagerClientError(error.details || error.message || "gRPC request failed", error.code);
  }
}

/** Subject has no backend lease (``GetLease`` → NOT_FOUND). */
export class NoSuchBackendLeaseError extends PodManagerClientError {
  constructor(message = "No backend lease for subject.") {
    super(message, grpc.status.NOT_FOUND);
    this.name = "NoSuchBackendLeaseError";
  }
}

/** No free backend pool pod available for ``AcquireLease``. */
export class NoBackendLeaseAvailableError extends PodManagerClientError {
  constructor(message = "No free backend pool pods available for lease.") {
    super(message, grpc.status.RESOURCE_EXHAUSTED);
    this.name = "NoBackendLeaseAvailableError";
  }
}

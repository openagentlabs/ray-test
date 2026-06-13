import * as grpc from "@grpc/grpc-js";

import type { GrpcServiceErrorLike, GrpcUnaryInvoke } from "./grpc-unary.js";

type GrpcUnaryMethod<Req, Res> = (
  request: Req,
  metadata: grpc.Metadata,
  options: Partial<grpc.CallOptions>,
  callback: (error: grpc.ServiceError | null, response?: Res) => void,
) => grpc.ClientUnaryCall;

function toErrorLike(error: grpc.ServiceError): GrpcServiceErrorLike {
  return {
    code: error.code,
    message: error.message,
    details: error.details,
  };
}

/** Binds a ts-proto grpc-js stub unary to {@link GrpcUnaryInvoke}. */
export function bindGrpcUnary<Req, Res>(method: GrpcUnaryMethod<Req, Res>): GrpcUnaryInvoke<Req, Res> {
  return (request, options, callback) => {
    const metadata = new grpc.Metadata();
    const grpcOptions: Partial<grpc.CallOptions> = {};
    if (options.deadline !== undefined) {
      grpcOptions.deadline = options.deadline;
    }
    const call = method(request, metadata, grpcOptions, (error, response) => {
      callback(error ? toErrorLike(error) : null, response);
    });
    return { cancel: () => call.cancel() };
  };
}

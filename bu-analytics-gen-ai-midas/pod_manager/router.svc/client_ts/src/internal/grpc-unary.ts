import * as grpc from "@grpc/grpc-js";

export interface GrpcServiceErrorLike {
  readonly code: grpc.status;
  readonly message: string;
  readonly details: string;
}

export interface GrpcUnaryCallOptions {
  readonly deadline?: Date;
}

export type GrpcUnaryCallback<Res> = (
  error: GrpcServiceErrorLike | null,
  response?: Res,
) => void;

export type GrpcUnaryInvoke<Req, Res> = (
  request: Req,
  options: GrpcUnaryCallOptions,
  callback: GrpcUnaryCallback<Res>,
) => { cancel: () => void };

export function promisifyUnary<Req, Res>(invoke: GrpcUnaryInvoke<Req, Res>, request: Req): Promise<Res> {
  return new Promise((resolve, reject) => {
    invoke(request, {}, (error, response) => {
      if (error) {
        reject(error);
        return;
      }
      if (response === undefined) {
        reject({
          code: grpc.status.UNKNOWN,
          message: "Empty gRPC response",
          details: "",
        } satisfies GrpcServiceErrorLike);
        return;
      }
      resolve(response);
    });
  });
}

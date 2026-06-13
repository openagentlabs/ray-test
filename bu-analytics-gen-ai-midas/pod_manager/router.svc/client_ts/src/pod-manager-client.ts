/** Async gRPC client for ``pod_manager.v1.PodManagerService``. */

import * as grpc from "@grpc/grpc-js";

import {
  PodManagerServiceClient as PodManagerServiceGrpcClient,
  type AcquireLeaseResponse,
  type DeleteServiceConfigResponse,
  type GetBackendPoolAvailabilityResponse,
  type GetLeaseResponse,
  type GetPoolStatusRequest,
  type GetPoolStatusResponse,
  type GetRuntimeEnvironmentRequest,
  type GetRuntimeEnvironmentResponse,
  type HeartbeatResponse,
  type ListServiceConfigRequest,
  type ListServiceConfigResponse,
  type PutServiceConfigRequest,
  type ReleaseLeaseResponse,
  type ServiceConfigEntry,
} from "./gen/pod_manager/v1/pool.js";
import { NoBackendLeaseAvailableError, NoSuchBackendLeaseError, PodManagerClientError } from "./errors.js";
import { bindGrpcUnary } from "./internal/bind-grpc-unary.js";
import { promisifyUnary, type GrpcUnaryInvoke } from "./internal/grpc-unary.js";
import type { BackendPoolAvailability, LeaseResult, PoolStatus } from "./types.js";
import { assertValidRequest } from "./validation/assert-valid.js";
import {
  acquireLeaseRequestSchema,
  getServiceConfigRequestSchema,
  heartbeatRequestSchema,
  putServiceConfigRequestSchema,
  releaseLeaseRequestSchema,
} from "./validation/schemas.js";

export interface PodManagerClientOptions {
  readonly host?: string;
  readonly port?: number;
  readonly channelCredentials?: grpc.ChannelCredentials;
  readonly clientOptions?: Partial<grpc.ClientOptions>;
}

type PodManagerGrpcClient = InstanceType<typeof PodManagerServiceGrpcClient>;

export class PodManagerClient {
  private readonly _stub: PodManagerGrpcClient;
  private _closed = false;

  constructor(options: PodManagerClientOptions = {}) {
    const host = options.host ?? "localhost";
    const port = options.port ?? 8804;
    const address = `${host}:${port}`;
    const creds = options.channelCredentials ?? grpc.credentials.createInsecure();
    this._stub = new PodManagerServiceGrpcClient(address, creds, options.clientOptions);
  }

  private ensureOpen(): void {
    if (this._closed) {
      throw new Error("Client closed");
    }
  }

  private async unary<Req, Res>(invoke: GrpcUnaryInvoke<Req, Res>, request: Req): Promise<Res> {
    this.ensureOpen();
    try {
      return await promisifyUnary(invoke, request);
    } catch (error) {
      const grpcError = error as Parameters<typeof PodManagerClientError.fromGrpc>[0];
      if (grpcError.code === 8) {
        throw new NoBackendLeaseAvailableError(grpcError.details || grpcError.message);
      }
      if (grpcError.code === 5) {
        throw new NoSuchBackendLeaseError(grpcError.details || grpcError.message);
      }
      throw PodManagerClientError.fromGrpc(grpcError);
    }
  }

  async acquireLease(sub: string): Promise<LeaseResult> {
    const valid = assertValidRequest(acquireLeaseRequestSchema, { sub }, "AcquireLease");
    const resp = await this.unary<typeof valid, AcquireLeaseResponse>(
      bindGrpcUnary((req, md, opts, cb) => this._stub.acquireLease(req, md, opts, cb)),
      valid,
    );
    return {
      podId: resp.podId,
      podDns: resp.podDns,
      assignmentEpoch: resp.assignmentEpoch,
      alreadyLeased: resp.alreadyLeased,
    };
  }

  async getLease(sub: string): Promise<LeaseResult> {
    const valid = assertValidRequest(acquireLeaseRequestSchema, { sub }, "GetLease");
    const resp = await this.unary<typeof valid, GetLeaseResponse>(
      bindGrpcUnary((req, md, opts, cb) => this._stub.getLease(req, md, opts, cb)),
      valid,
    );
    return {
      podId: resp.podId,
      podDns: resp.podDns,
      assignmentEpoch: resp.assignmentEpoch,
      alreadyLeased: true,
    };
  }

  async releaseLease(sub: string): Promise<void> {
    const valid = assertValidRequest(releaseLeaseRequestSchema, { sub }, "ReleaseLease");
    await this.unary<typeof valid, ReleaseLeaseResponse>(
      bindGrpcUnary((req, md, opts, cb) => this._stub.releaseLease(req, md, opts, cb)),
      valid,
    );
  }

  async getBackendPoolAvailability(): Promise<BackendPoolAvailability> {
    const resp = await this.unary<object, GetBackendPoolAvailabilityResponse>(
      bindGrpcUnary((req, md, opts, cb) => this._stub.getBackendPoolAvailability(req, md, opts, cb)),
      {},
    );
    return {
      freeCount: resp.freeCount,
      totalCount: resp.totalCount,
      hasCapacity: resp.hasCapacity,
    };
  }

  async getPoolStatus(pool = ""): Promise<PoolStatus> {
    const request: GetPoolStatusRequest = { pool };
    const resp = await this.unary<GetPoolStatusRequest, GetPoolStatusResponse>(
      bindGrpcUnary((req, md, opts, cb) => this._stub.getPoolStatus(req, md, opts, cb)),
      request,
    );
    return {
      pods: resp.pods,
      freeCount: resp.freeCount,
      claimedCount: resp.claimedCount,
    };
  }

  async heartbeat(sub: string, assignmentEpoch: number): Promise<number> {
    const valid = assertValidRequest(heartbeatRequestSchema, { sub, assignmentEpoch }, "Heartbeat");
    const resp = await this.unary<typeof valid, HeartbeatResponse>(
      bindGrpcUnary((req, md, opts, cb) => this._stub.heartbeat(req, md, opts, cb)),
      valid,
    );
    return resp.assignmentEpoch;
  }

  async getRuntimeEnvironment(): Promise<Record<string, string>> {
    const request: GetRuntimeEnvironmentRequest = {};
    const resp = await this.unary<GetRuntimeEnvironmentRequest, GetRuntimeEnvironmentResponse>(
      bindGrpcUnary((req, md, opts, cb) => this._stub.getRuntimeEnvironment(req, md, opts, cb)),
      request,
    );
    const out: Record<string, string> = {};
    for (const entry of resp.entries) {
      out[entry.key] = entry.value;
    }
    return out;
  }

  async listServiceConfig(): Promise<ServiceConfigEntry[]> {
    const request: ListServiceConfigRequest = {};
    const resp = await this.unary<ListServiceConfigRequest, ListServiceConfigResponse>(
      bindGrpcUnary((req, md, opts, cb) => this._stub.listServiceConfig(req, md, opts, cb)),
      request,
    );
    return [...resp.entries];
  }

  async getServiceConfig(configKey: string): Promise<ServiceConfigEntry> {
    const valid = assertValidRequest(getServiceConfigRequestSchema, { configKey }, "GetServiceConfig");
    return this.unary<typeof valid, ServiceConfigEntry>(
      bindGrpcUnary((req, md, opts, cb) => this._stub.getServiceConfig(req, md, opts, cb)),
      valid,
    );
  }

  async putServiceConfig(
    configKey: string,
    value: string,
    options: { description?: string } = {},
  ): Promise<ServiceConfigEntry> {
    const valid = assertValidRequest(
      putServiceConfigRequestSchema,
      { configKey, value, description: options.description ?? "" },
      "PutServiceConfig",
    );
    return this.unary<PutServiceConfigRequest, ServiceConfigEntry>(
      bindGrpcUnary((req, md, opts, cb) => this._stub.putServiceConfig(req, md, opts, cb)),
      valid,
    );
  }

  async deleteServiceConfig(configKey: string): Promise<void> {
    const valid = assertValidRequest(getServiceConfigRequestSchema, { configKey }, "DeleteServiceConfig");
    await this.unary<typeof valid, DeleteServiceConfigResponse>(
      bindGrpcUnary((req, md, opts, cb) => this._stub.deleteServiceConfig(req, md, opts, cb)),
      valid,
    );
  }

  close(): void {
    if (!this._closed) {
      this._stub.close();
      this._closed = true;
    }
  }
}

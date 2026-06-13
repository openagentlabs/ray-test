import type { PodSummary, ServiceConfigEntry } from "./gen/pod_manager/v1/pool.js";

export interface LeaseResult {
  readonly podId: string;
  readonly podDns: string;
  readonly assignmentEpoch: number;
  readonly alreadyLeased: boolean;
}

export interface BackendPoolAvailability {
  readonly freeCount: number;
  readonly totalCount: number;
  readonly hasCapacity: boolean;
}

export interface PoolStatus {
  readonly pods: readonly PodSummary[];
  readonly freeCount: number;
  readonly claimedCount: number;
}

export type { PodSummary, ServiceConfigEntry };

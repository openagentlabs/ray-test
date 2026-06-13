/** TypeScript gRPC client for the pod_manager routing control plane. */

export { PodManagerClient, type PodManagerClientOptions } from "./pod-manager-client.js";
export { NoBackendLeaseAvailableError, NoSuchBackendLeaseError, PodManagerClientError } from "./errors.js";
export { PodManagerClientValidationError } from "./validation/assert-valid.js";
export type {
  BackendPoolAvailability,
  LeaseResult,
  PoolStatus,
  PodSummary,
  ServiceConfigEntry,
} from "./types.js";

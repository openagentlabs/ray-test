import {
  NoBackendLeaseAvailableError,
  NoSuchBackendLeaseError,
  PodManagerClient,
  type BackendPoolAvailability,
  type LeaseResult,
} from "@router/client-ts";

import { podManagerGrpcHost, podManagerGrpcPort } from "@/lib/env";

function client(): PodManagerClient {
  return new PodManagerClient({
    host: podManagerGrpcHost(),
    port: podManagerGrpcPort(),
  });
}

export async function acquireLease(sub: string): Promise<LeaseResult> {
  const pm = client();
  try {
    return await pm.acquireLease(sub);
  } finally {
    pm.close();
  }
}

export async function getLease(sub: string): Promise<LeaseResult | null> {
  const pm = client();
  try {
    return await pm.getLease(sub);
  } catch (err) {
    if (err instanceof NoSuchBackendLeaseError) {
      return null;
    }
    throw err;
  } finally {
    pm.close();
  }
}

export async function releaseLease(sub: string): Promise<void> {
  const pm = client();
  try {
    await pm.releaseLease(sub);
  } finally {
    pm.close();
  }
}

export async function getBackendPoolAvailability(): Promise<BackendPoolAvailability> {
  const pm = client();
  try {
    return await pm.getBackendPoolAvailability();
  } finally {
    pm.close();
  }
}

export { NoBackendLeaseAvailableError, NoSuchBackendLeaseError };

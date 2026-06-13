/** Call backend REST API via Envoy BFF (`/api/backend/...`). */

export type BackendApiErrorBody = {
  error?: string;
  message?: string;
};

export type BackendMeResponse = {
  service?: string;
  pod_id?: string;
  backend_pool_node?: string;
  sub?: string;
  message?: string;
};

export type BackendApiResult =
  | { ok: true; status: number; data: BackendMeResponse }
  | { ok: false; status: number; error: string; message: string; raw: string };

export async function fetchBackendMe(): Promise<BackendApiResult> {
  const res = await fetch("/api/backend/api/v1/me", {
    credentials: "include",
    cache: "no-store",
  });
  const raw = await res.text();
  let parsed: BackendApiErrorBody & BackendMeResponse = {};
  try {
    parsed = JSON.parse(raw) as BackendApiErrorBody & BackendMeResponse;
  } catch {
    parsed = {};
  }

  if (res.ok) {
    return { ok: true, status: res.status, data: parsed };
  }

  const error = parsed.error ?? "request_failed";
  const message =
    parsed.message ??
    (raw.trim() ? raw.slice(0, 500) : `Backend API returned HTTP ${res.status}.`);

  return { ok: false, status: res.status, error, message, raw };
}

export function formatBackendApiResult(result: BackendApiResult): string {
  if (result.ok) {
    return JSON.stringify(result.data, null, 2);
  }
  return JSON.stringify(
    { http_status: result.status, error: result.error, message: result.message },
    null,
    2,
  );
}

export function isNoBackendLeaseError(result: BackendApiResult): boolean {
  return !result.ok && result.error === "no_backend_lease";
}

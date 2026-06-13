/**
 * RFE API client (Step 3 + Step 4).
 *
 * Mirrors the auth + SSE patterns already used by fastApiService.ts (fetch +
 * ReadableStream because native EventSource can't send Authorization headers).
 * Kept as a small standalone module so we don't pile more methods onto the
 * already-4k-line fastApiService.
 */

import { buildMidasAuthHeaders } from './authHeaders';
import { handleUnauthorizedResponse, RETRY_AFTER_REFRESH } from './httpUnauthorized';

// ---------------------------- Types ----------------------------

export interface RfePrecomputedMetric {
  iv?: number | null;
  orig_vif?: number | null;
  abs_corr?: number | null;
  missing_pct?: number | null;
  signed_corr?: number | null;
}

export interface RfeWorkingSet {
  locked: string[];
  screened: string[];
  precomputed_metrics?: Record<string, RfePrecomputedMetric>;
}

export interface RfeStartRequest {
  dataset_id: string;
  target: string;
  working_set: RfeWorkingSet;
  weight_col?: string | null;
}

export interface RfeStartResponse {
  job_id: string;
  mode: 'local' | 'redis' | string;
}

export interface RfeFeatureImportance {
  variable: string;
  shap_importance: number;
  native_importance: number;
  shap_rank: number;
}

export interface RfeIterationRecord {
  iteration: number;
  feature_count: number;
  features_in: string[];
  features_dropped: string[];
  elimination_band_label: string;
  cv_auc: number;
  test_auc: number;
  relative_delta_from_prev?: number | null;
  importances: RfeFeatureImportance[];
  locked_zero_importance_flags: string[];
  stop_reason?: string | null;
  is_best: boolean;
  timestamp_epoch: number;
}

export interface RfeStatusResponse {
  job_id: string;
  status: string;
  message?: string;
  current_iteration: number;
  total_features: number;
  best_iteration: number;
  latest_cv_auc?: number | null;
  iteration_count: number;
  heartbeat_at: number;
  error?: string | null;
}

export interface RfeVariableRow {
  variable: string;
  locked: boolean;
  status: 'retained' | 'dropped';
  drop_iteration?: number | null;
  iv?: number | null;
  orig_vif?: number | null;
  nvar_vif?: number | null;
  abs_corr_target?: number | null;
  shap_importance_best?: number | null;
  rank_trajectory: Array<number | null>;
  suggested_monotone: number;
  bivariate_corr?: number | null;
}

export interface RfeResultResponse {
  job_id: string;
  dataset_id: string;
  target: string;
  starting_feature_count: number;
  final_feature_count: number;
  best_iteration: number;
  total_iterations: number;
  stop_reason: string;
  best_cv_auc: number;
  best_test_auc: number;
  iterations: RfeIterationRecord[];
  rows: RfeVariableRow[];
  // Populated when the loop stopped on AUC degradation and the best
  // iteration is not the last one we ran. UI shows this in the completion
  // banner as "Rolled back from iteration N". Null/absent otherwise.
  rolled_back_from_iteration?: number | null;
}

export interface RfeFinalizeRequest {
  job_id: string;
  overrides?: { include?: string[]; exclude?: string[] };
  monotone?: Record<string, -1 | 0 | 1>;
}

export interface RfeFinalizeResponse {
  success: boolean;
  job_id: string;
  dataset_id: string;
  target: string;
  features: string[];
  locked: string[];
  monotone: Record<string, number>;
  final_vifs: Record<string, number>;
  finalized_at_epoch: number;
}

export type RfeSseEvent =
  | { kind: 'status'; payload: RfeStatusResponse }
  | { kind: 'iteration'; job_id: string; status: string; iteration: RfeIterationRecord }
  | { kind: 'final'; job_id: string; status: string; result?: RfeResultResponse }
  | { kind: 'error'; job_id: string; error: string }
  | { kind: 'unknown'; payload: Record<string, unknown> };

// ---------------------------- Helpers ----------------------------

function getBaseUrl(): string {
  const envBase = (import.meta as { env?: Record<string, string> }).env?.VITE_BASE_URL || '';
  return envBase ? `${envBase}/api/v1` : '/api/v1';
}

function authHeaders(): Record<string, string> {
  return buildMidasAuthHeaders();
}

function formatFastApiError(detail: unknown, fallback: string): string {
  if (!detail) return fallback;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        if (typeof d === 'string') return d;
        const loc = Array.isArray(d?.loc) ? d.loc.join('.') : '';
        const msg = d?.msg || JSON.stringify(d);
        return loc ? `${loc}: ${msg}` : msg;
      })
      .join('; ');
  }
  try {
    return JSON.stringify(detail);
  } catch {
    return fallback;
  }
}

async function fetchWithAuthRetry(url: string, init: () => RequestInit): Promise<Response> {
  let resp = await fetch(url, init());
  if (resp.status === 401) {
    try {
      await handleUnauthorizedResponse(resp, { allowRefresh: true, skipAuth: false });
    } catch (e: unknown) {
      if ((e as { message?: string })?.message === RETRY_AFTER_REFRESH) {
        resp = await fetch(url, init());
        if (resp.status === 401) {
          await handleUnauthorizedResponse(resp, { allowRefresh: false, skipAuth: false });
        }
      } else {
        throw e;
      }
    }
  }
  return resp;
}

async function jsonPost<TReq, TResp>(path: string, body: TReq): Promise<TResp> {
  const resp = await fetchWithAuthRetry(`${getBaseUrl()}${path}`, () => ({
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  }));
  if (!resp.ok) {
    let detailText = '';
    try {
      const j = await resp.json();
      detailText = formatFastApiError(j?.detail, resp.statusText);
    } catch {
      detailText = resp.statusText;
    }
    throw new Error(`HTTP ${resp.status}: ${detailText}`);
  }
  return (await resp.json()) as TResp;
}

async function jsonGet<TResp>(path: string): Promise<TResp> {
  const resp = await fetchWithAuthRetry(`${getBaseUrl()}${path}`, () => ({
    method: 'GET',
    headers: { ...authHeaders() },
  }));
  if (!resp.ok) {
    let detailText = resp.statusText;
    try {
      const j = await resp.json();
      detailText = formatFastApiError(j?.detail, resp.statusText);
    } catch {
      /* ignore - keep statusText */
    }
    throw new Error(`HTTP ${resp.status}: ${detailText}`);
  }
  return (await resp.json()) as TResp;
}

// ---------------------------- API ----------------------------

export async function startRfe(req: RfeStartRequest): Promise<RfeStartResponse> {
  return jsonPost<RfeStartRequest, RfeStartResponse>('/rfe/start', req);
}

export async function cancelRfe(jobId: string): Promise<{ success: boolean; cancelled: boolean; status: string }> {
  return jsonPost<Record<string, never>, { success: boolean; cancelled: boolean; status: string }>(
    `/rfe/cancel/${encodeURIComponent(jobId)}`,
    {} as Record<string, never>
  );
}

export async function getRfeStatus(jobId: string): Promise<RfeStatusResponse> {
  return jsonGet<RfeStatusResponse>(`/rfe/status/${encodeURIComponent(jobId)}`);
}

export async function getRfeResult(jobId: string): Promise<RfeResultResponse> {
  return jsonGet<RfeResultResponse>(`/rfe/result/${encodeURIComponent(jobId)}`);
}

export async function finalizeRfe(req: RfeFinalizeRequest): Promise<RfeFinalizeResponse> {
  return jsonPost<RfeFinalizeRequest, RfeFinalizeResponse>('/rfe/finalize', req);
}

// ---------------------------- SSE stream ----------------------------

function classifyEvent(obj: Record<string, unknown>): RfeSseEvent {
  if (obj == null || typeof obj !== 'object') {
    return { kind: 'unknown', payload: obj as Record<string, unknown> };
  }
  if ('iteration' in obj && typeof obj.iteration === 'object') {
    return {
      kind: 'iteration',
      job_id: String(obj.job_id ?? ''),
      status: String(obj.status ?? 'running'),
      iteration: obj.iteration as RfeIterationRecord,
    };
  }
  // The backend emits two "completed" events through the SSE stream:
  //   (a) a summary-only event from the RFE service event bus that carries just
  //       a `final` key with {best_iteration, total_iterations, final_feature_count,
  //       stop_reason} — NOT a full RfeResultResponse (missing `rows`, `iterations`,
  //       etc.). Treating this as `kind: 'final'` would force the caller to close
  //       the stream and hand a half-empty object to FeatureReviewStep, which
  //       would then crash on `result.rows.filter(...)`.
  //   (b) a full-result event from the SSE route handler that carries the whole
  //       RfeResultResponse under a `result` key.
  // We classify only (b) as `final`. The summary-only (a) falls through to the
  // `status` branch so the UI keeps updating status but the stream is still
  // alive to receive (b).
  if ('result' in obj && obj.result && typeof obj.result === 'object') {
    return {
      kind: 'final',
      job_id: String(obj.job_id ?? ''),
      status: String(obj.status ?? 'completed'),
      result: obj.result as RfeResultResponse,
    };
  }
  if ('error' in obj && obj.error) {
    return { kind: 'error', job_id: String(obj.job_id ?? ''), error: String(obj.error) };
  }
  if ('status' in obj) {
    return { kind: 'status', payload: obj as unknown as RfeStatusResponse };
  }
  return { kind: 'unknown', payload: obj };
}

export interface StreamHandlers {
  onEvent?: (event: RfeSseEvent) => void;
  onStatus?: (status: RfeStatusResponse) => void;
  onIteration?: (iteration: RfeIterationRecord) => void;
  onFinal?: (status: string, result?: RfeResultResponse) => void;
  onError?: (err: Error) => void;
}

export interface StreamHandle {
  close: () => void;
  promise: Promise<void>;
}

/**
 * Open an SSE connection to /rfe/stream/{jobId}. Auto-reconnects on transient
 * transport drops (network blip, proxy timeout) up to `maxReconnects` times.
 * Resolves when the job reaches a terminal status or the caller calls close().
 */
export function streamRfe(
  jobId: string,
  handlers: StreamHandlers,
  options: { maxReconnects?: number; reconnectDelayMs?: number } = {}
): StreamHandle {
  const { maxReconnects = 3, reconnectDelayMs = 1500 } = options;
  const ctrl = new AbortController();
  let reconnects = 0;
  let stopped = false;

  const run = async (): Promise<void> => {
    let authRefreshAttempted = false;
    while (!stopped) {
      try {
        const resp = await fetch(`${getBaseUrl()}/rfe/stream/${encodeURIComponent(jobId)}`, {
          method: 'GET',
          headers: { Accept: 'text/event-stream', ...authHeaders() },
          signal: ctrl.signal,
        });
        if (resp.status === 401 && !authRefreshAttempted) {
          authRefreshAttempted = true;
          try {
            await handleUnauthorizedResponse(resp, { allowRefresh: true, skipAuth: false });
          } catch (e: unknown) {
            if ((e as { message?: string })?.message === RETRY_AFTER_REFRESH) {
              continue;
            }
            throw e;
          }
        }
        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}`);
        }
        const reader = resp.body?.getReader();
        if (!reader) throw new Error('No response body');
        const decoder = new TextDecoder();
        let buffer = '';
        while (!stopped) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let sep: number;
          while ((sep = buffer.indexOf('\n\n')) !== -1) {
            const rawEvent = buffer.slice(0, sep);
            buffer = buffer.slice(sep + 2);
            const dataLines = rawEvent
              .split('\n')
              .filter((l) => l.startsWith('data:'))
              .map((l) => l.slice(5).trimStart());
            if (dataLines.length === 0) continue;
            const data = dataLines.join('\n');
            let obj: Record<string, unknown> | null = null;
            try {
              obj = JSON.parse(data);
            } catch {
              continue;
            }
            if (!obj) continue;
            const ev = classifyEvent(obj);
            handlers.onEvent?.(ev);
            if (ev.kind === 'status') handlers.onStatus?.(ev.payload);
            if (ev.kind === 'iteration') handlers.onIteration?.(ev.iteration);
            if (ev.kind === 'final') {
              handlers.onFinal?.(ev.status, ev.result);
              stopped = true;
              break;
            }
            if (ev.kind === 'error') {
              handlers.onError?.(new Error(ev.error));
              stopped = true;
              break;
            }
          }
        }
        break;
      } catch (err) {
        if (stopped || ctrl.signal.aborted) return;
        reconnects += 1;
        if (reconnects > maxReconnects) {
          handlers.onError?.(err instanceof Error ? err : new Error(String(err)));
          return;
        }
        await new Promise((r) => setTimeout(r, reconnectDelayMs));
      }
    }
  };

  const promise = run();
  return {
    close: () => {
      stopped = true;
      try {
        ctrl.abort();
      } catch {
        /* ignore */
      }
    },
    promise,
  };
}

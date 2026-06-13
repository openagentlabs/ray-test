/**
 * Client session TTL timer + single global session-expired event (deduped).
 * Persists session_created_at / session_ttl_seconds / session_id for refresh + X-Session-Id header.
 */

export const SESSION_EXPIRED_EVENT = 'midas:session-expired';

const KEY_CREATED = 'midas_session_created_at';
const KEY_TTL = 'midas_session_ttl_seconds';
const KEY_SID = 'midas_session_id';

const DEFAULT_TTL_SECONDS = 3600; // 60 min — matches backend SESSION_TIMEOUT target

/** Attempt a proactive token refresh this many ms before the session TTL expires. */
const PROACTIVE_REFRESH_BEFORE_EXPIRY_MS = 5 * 60 * 1000; // 5 minutes

let timerId: ReturnType<typeof setTimeout> | null = null;
let expiryEventDispatched = false;

export function resetSessionExpiryDispatchFlag(): void {
  expiryEventDispatched = false;
}

/** Idempotent: multiple API failures only dispatch one browser event (no immediate redirect). */
export function dispatchSessionExpiredOnce(message?: string): void {
  if (expiryEventDispatched) {
    return;
  }
  expiryEventDispatched = true;
  const detail = { message: message?.trim() || 'Session expired' };
  window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT, { detail }));
}

export function persistSessionMetaFromApi(createdAtUnix: number, ttlSeconds: number, sessionId?: string | null): void {
  const ttl = Number.isFinite(ttlSeconds) && ttlSeconds > 0 ? Math.floor(ttlSeconds) : DEFAULT_TTL_SECONDS;
  const created = Number.isFinite(createdAtUnix) && createdAtUnix > 0 ? Math.floor(createdAtUnix) : Math.floor(Date.now() / 1000);
  try {
    localStorage.setItem(KEY_CREATED, String(created));
    localStorage.setItem(KEY_TTL, String(ttl));
    if (sessionId) {
      localStorage.setItem(KEY_SID, sessionId);
    }
  } catch {
    /* ignore */
  }
  resetSessionExpiryDispatchFlag();
  scheduleClientSessionTimer();
}

export function getStoredSessionId(): string | null {
  try {
    return localStorage.getItem(KEY_SID);
  } catch {
    return null;
  }
}

export function scheduleClientSessionTimer(): void {
  if (timerId !== null) {
    clearTimeout(timerId);
    timerId = null;
  }
  let created: number;
  let ttl: number;
  try {
    created = parseInt(localStorage.getItem(KEY_CREATED) || '0', 10);
    ttl = parseInt(localStorage.getItem(KEY_TTL) || '0', 10);
  } catch {
    return;
  }
  if (!created || !ttl) {
    return;
  }
  if (!localStorage.getItem('auth_token')) {
    return;
  }

  const effectiveTtl = ttl > 0 ? ttl : DEFAULT_TTL_SECONDS;
  const elapsedSec = Date.now() / 1000 - created;
  const remainingMs = Math.max(0, effectiveTtl * 1000 - elapsedSec * 1000);

  // Fire the refresh PROACTIVE_REFRESH_BEFORE_EXPIRY_MS before the session
  // expires so the user is never interrupted. If the refresh succeeds,
  // _doRefresh() calls persistSessionMetaFromApi() which reschedules this
  // timer for a fresh full-TTL window (OBS0004). Only dispatch the
  // session-expired event if the refresh actually fails.
  const refreshAtMs = Math.max(0, remainingMs - PROACTIVE_REFRESH_BEFORE_EXPIRY_MS);

  timerId = setTimeout(() => {
    timerId = null;
    // Dynamic import breaks the circular dependency:
    //   authSessionExpiry ← authService ← cognitoAuthService
    // The full chain is guarded by .catch() so that any unexpected throw
    // (import failure, network exception inside refresh) still shows the
    // session-expired modal rather than silently leaving the user stuck.
    void import('./cognitoAuthService')
      .then(({ refresh }) => refresh())
      .then((ok) => {
        if (!ok) {
          dispatchSessionExpiredOnce('Your session has expired due to inactivity.');
        }
      })
      .catch(() => {
        dispatchSessionExpiredOnce('Your session has expired due to inactivity.');
      });
  }, refreshAtMs);
}

export function clearSessionTimerAndMeta(): void {
  if (timerId !== null) {
    clearTimeout(timerId);
    timerId = null;
  }
  try {
    localStorage.removeItem(KEY_CREATED);
    localStorage.removeItem(KEY_TTL);
    localStorage.removeItem(KEY_SID);
  } catch {
    /* ignore */
  }
}

// ── Visibility refresh guard ──────────────────────────────────────────────────
// Browsers throttle setTimeout in background tabs (Chrome: ≥1 min intervals).
// When the tab becomes visible again we re-arm the timer so the proactive
// refresh fires promptly even if the background throttle delayed it.

let _visibilityHandler: (() => void) | null = null;

/**
 * Register a document visibilitychange listener that re-arms the proactive
 * refresh timer whenever the tab becomes visible. Idempotent — safe to call
 * multiple times (registers only once). Call teardownVisibilityRefreshGuard()
 * to remove the listener (required in tests).
 */
export function initVisibilityRefreshGuard(): void {
  if (_visibilityHandler || typeof document === 'undefined') {
    return;
  }
  _visibilityHandler = () => {
    if (!document.hidden) {
      scheduleClientSessionTimer();
    }
  };
  document.addEventListener('visibilitychange', _visibilityHandler);
}

/**
 * Remove the visibilitychange listener registered by initVisibilityRefreshGuard().
 * Intended for test teardown; also safe to call in logout flows.
 */
export function teardownVisibilityRefreshGuard(): void {
  if (_visibilityHandler) {
    document.removeEventListener('visibilitychange', _visibilityHandler);
    _visibilityHandler = null;
  }
}

/** Full page landing (login) - used after modal OK. */
export function buildPublicLandingHref(): string {
  try {
    const basePath = import.meta.env.BASE_URL || '/';
    const root = `${window.location.origin}${basePath.endsWith('/') ? basePath : `${basePath}/`}`;
    return new URL('?session=expired', root).href;
  } catch {
    return `${window.location.origin}/?session=expired`;
  }
}

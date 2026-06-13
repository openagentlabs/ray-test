/**
 * Tests for ISU0001/ISU0002 fixes — scheduleClientSessionTimer() must call
 * cognitoAuthService.refresh() proactively, not dispatch logout directly;
 * initVisibilityRefreshGuard() must re-arm the timer when the tab becomes visible.
 *
 * Cases covered:
 *   scheduleClientSessionTimer (ISU0001 fix):
 *   1. Timer fires at ttl − 300 s (not ttl), and refresh() is called
 *   2. Successful refresh → dispatchSessionExpiredOnce NOT called
 *   3. Failed refresh    → dispatchSessionExpiredOnce called once
 *   4. TTL ≤ 300 s      → timer fires immediately (refreshAtMs clamped to 0)
 *   5. Partially elapsed session → timer fires at reduced remaining delay
 *   6. refresh() throws  → .catch() still dispatches session-expired (never silent)
 *   7. clearSessionTimerAndMeta() while pending → refresh is NOT called
 *
 *   initVisibilityRefreshGuard (ISU0002-B fix):
 *   8.  Tab becomes visible with ≤5 min remaining → refresh fires immediately
 *   9.  Tab becomes visible after session expired → refresh fires, fails, session-expired dispatched
 *   10. visibilitychange while tab stays hidden → refresh NOT called
 *   11. initVisibilityRefreshGuard() is idempotent (no duplicate listeners)
 *   12. Full hidden→visible transition: refresh only on becoming-visible leg
 *   13. Can be re-registered after teardownVisibilityRefreshGuard()
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// ─── Hoist the mock function so vi.mock() factory can reference it ────────────
// vi.hoisted() runs before module-level `let` declarations, ensuring the factory
// captures an already-initialised vi.fn() rather than `undefined`.
const { mockRefresh } = vi.hoisted(() => ({
  mockRefresh: vi.fn<[], Promise<boolean>>(() => Promise.resolve(true)),
}));

vi.mock('../cognitoAuthService', () => ({
  default: {},
  refresh: mockRefresh,
  beginLogin: vi.fn(),
  completeLogin: vi.fn(),
  logout: vi.fn(),
}));

// ─── localStorage stub ────────────────────────────────────────────────────────
const localStorageStore: Record<string, string> = {};
const localStorageMock = {
  getItem:    (k: string)           => localStorageStore[k] ?? null,
  setItem:    (k: string, v: string) => { localStorageStore[k] = v; },
  removeItem: (k: string)           => { delete localStorageStore[k]; },
  clear:      ()                    => { Object.keys(localStorageStore).forEach((k) => delete localStorageStore[k]); },
};
Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock, writable: false });

// ─── window.dispatchEvent spy ─────────────────────────────────────────────────
const dispatchSpy = vi.spyOn(window, 'dispatchEvent');

// ─── Module under test (imported after mocks) ─────────────────────────────────
import {
  scheduleClientSessionTimer,
  clearSessionTimerAndMeta,
  resetSessionExpiryDispatchFlag,
  initVisibilityRefreshGuard,
  teardownVisibilityRefreshGuard,
  SESSION_EXPIRED_EVENT,
} from '../authSessionExpiry';

// ─── Constants mirroring the production module ────────────────────────────────
const PROACTIVE_REFRESH_BEFORE_EXPIRY_S = 300; // 5 minutes

// ─── Helpers ─────────────────────────────────────────────────────────────────
const NOW_UNIX  = 1_700_000_000; // fixed epoch (seconds)
const TTL_SECS  = 3600;          // 60 min — standard session TTL

function seedStorage(opts: {
  created?:  number;
  ttl?:      number;
  hasToken?: boolean;
}): void {
  const { created = NOW_UNIX, ttl = TTL_SECS, hasToken = true } = opts;
  localStorageStore['midas_session_created_at']  = String(created);
  localStorageStore['midas_session_ttl_seconds'] = String(ttl);
  if (hasToken) localStorageStore['auth_token']  = 'test-token';
  else          delete localStorageStore['auth_token'];
}

function sessionExpiredDispatches(): number {
  return dispatchSpy.mock.calls.filter(
    ([e]) => (e as Event).type === SESSION_EXPIRED_EVENT,
  ).length;
}

// ─── Setup / teardown ─────────────────────────────────────────────────────────
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW_UNIX * 1000); // clock aligned with session creation
  localStorageMock.clear();
  dispatchSpy.mockClear();
  mockRefresh.mockClear();
  mockRefresh.mockResolvedValue(true); // default: refresh succeeds
  resetSessionExpiryDispatchFlag();
});

afterEach(() => {
  clearSessionTimerAndMeta();
  vi.useRealTimers();
});

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('scheduleClientSessionTimer — ISU0001 fix', () => {

  /**
   * Case 1: timer fires at ttl − 300 s and refresh() is called.
   *
   * With a 3600 s TTL and 0 s elapsed the refresh window opens at 3300 s.
   * Before 3300 s refresh must NOT have been called; at 3300 s it must be called.
   */
  it('fires at (ttl − 300 s) and calls refresh(), not logout', async () => {
    seedStorage({});
    scheduleClientSessionTimer();

    // Still 1 s before the proactive window — nothing fired.
    // Use Promise.resolve() (microtask flush only) NOT runAllTimersAsync() here,
    // because runAllTimersAsync() would fast-forward the pending timer we're testing.
    vi.advanceTimersByTime((TTL_SECS - PROACTIVE_REFRESH_BEFORE_EXPIRY_S - 1) * 1000);
    await Promise.resolve();
    expect(mockRefresh).not.toHaveBeenCalled();

    // Advance 1 more second — timer fires.
    vi.advanceTimersByTime(1000);
    await vi.runAllTimersAsync();
    expect(mockRefresh).toHaveBeenCalledOnce();
    // refresh() returned true → no session-expired event.
    expect(sessionExpiredDispatches()).toBe(0);
  });

  /**
   * Case 2: successful refresh → session-expired event NOT dispatched.
   */
  it('does NOT dispatch session-expired when refresh succeeds', async () => {
    mockRefresh.mockResolvedValue(true);
    seedStorage({});
    scheduleClientSessionTimer();

    vi.advanceTimersByTime((TTL_SECS - PROACTIVE_REFRESH_BEFORE_EXPIRY_S) * 1000);
    await vi.runAllTimersAsync();

    expect(mockRefresh).toHaveBeenCalledOnce();
    expect(sessionExpiredDispatches()).toBe(0);
  });

  /**
   * Case 3: failed refresh → session-expired event dispatched exactly once.
   */
  it('dispatches session-expired exactly once when refresh fails', async () => {
    mockRefresh.mockResolvedValue(false);
    seedStorage({});
    scheduleClientSessionTimer();

    vi.advanceTimersByTime((TTL_SECS - PROACTIVE_REFRESH_BEFORE_EXPIRY_S) * 1000);
    await vi.runAllTimersAsync();

    expect(mockRefresh).toHaveBeenCalledOnce();
    expect(sessionExpiredDispatches()).toBe(1);
  });

  /**
   * Case 4: TTL ≤ 300 s → refreshAtMs clamps to 0, timer fires immediately.
   *
   * Even with a very short TTL the timer must still try refresh() before
   * falling back to logout — never force-logout without attempting renewal.
   */
  it('fires immediately (clamped to 0 ms) when TTL ≤ 300 s', async () => {
    mockRefresh.mockResolvedValue(false);
    seedStorage({ ttl: 120 }); // 2-minute session
    scheduleClientSessionTimer();

    vi.advanceTimersByTime(1); // 0 ms timer → fires on next tick
    await vi.runAllTimersAsync();

    expect(mockRefresh).toHaveBeenCalledOnce();
    expect(sessionExpiredDispatches()).toBe(1);
  });

  /**
   * Case 5: partially elapsed session → timer fires at the correct *reduced* delay.
   *
   * Created 30 min ago, TTL = 60 min: remaining = 30 min = 1800 s.
   * refreshAtMs = max(0, 1800 000 − 300 000) = 1500 s.
   * Timer must NOT fire at 1499 s and MUST fire at 1500 s.
   */
  it('fires at the correct reduced delay when the session is partially elapsed', async () => {
    const elapsed = 30 * 60; // 30 minutes already gone
    const createdInPast = NOW_UNIX - elapsed;
    seedStorage({ created: createdInPast, ttl: TTL_SECS });
    scheduleClientSessionTimer();

    const expectedFireMs = (TTL_SECS - elapsed - PROACTIVE_REFRESH_BEFORE_EXPIRY_S) * 1000; // 1500 000 ms

    // 1 ms before — should not have fired.
    // Use Promise.resolve() (microtask flush only) NOT runAllTimersAsync() here.
    vi.advanceTimersByTime(expectedFireMs - 1);
    await Promise.resolve();
    expect(mockRefresh).not.toHaveBeenCalled();

    // Fire moment.
    vi.advanceTimersByTime(1);
    await vi.runAllTimersAsync();
    expect(mockRefresh).toHaveBeenCalledOnce();
  });

  /**
   * Case 6: refresh() throws → .catch() still dispatches session-expired.
   *
   * An unexpected throw must never leave the user silently stuck with an
   * expired session and no feedback.
   */
  it('dispatches session-expired when refresh() throws unexpectedly', async () => {
    mockRefresh.mockRejectedValue(new Error('network error'));
    seedStorage({});
    scheduleClientSessionTimer();

    vi.advanceTimersByTime((TTL_SECS - PROACTIVE_REFRESH_BEFORE_EXPIRY_S) * 1000);
    await vi.runAllTimersAsync();

    expect(mockRefresh).toHaveBeenCalledOnce();
    expect(sessionExpiredDispatches()).toBe(1);
  });

  /**
   * Case 7: clearSessionTimerAndMeta() while timer is pending cancels it.
   *
   * An explicit logout before the proactive window must cancel the timer so
   * refresh() is never called after the user has already signed out.
   */
  it('does NOT call refresh() after clearSessionTimerAndMeta() cancels the timer', async () => {
    seedStorage({});
    scheduleClientSessionTimer();

    // Cancel the timer mid-flight (simulates explicit logout).
    clearSessionTimerAndMeta();

    // Advance past when the timer would have fired — nothing should happen.
    vi.advanceTimersByTime(TTL_SECS * 1000);
    await vi.runAllTimersAsync();

    expect(mockRefresh).not.toHaveBeenCalled();
    expect(sessionExpiredDispatches()).toBe(0);
  });

});

// ─── Visibility refresh guard ─────────────────────────────────────────────────

describe('initVisibilityRefreshGuard — ISU0002-B fix', () => {

  // Helpers to control document.hidden in jsdom.
  function setDocumentHidden(hidden: boolean): void {
    Object.defineProperty(document, 'hidden', { value: hidden, writable: true, configurable: true });
  }

  function fireVisibilityChange(): void {
    document.dispatchEvent(new Event('visibilitychange'));
  }

  afterEach(() => {
    teardownVisibilityRefreshGuard();
    clearSessionTimerAndMeta();
    setDocumentHidden(false);
  });

  /**
   * Case 8: Tab becomes visible with ≤ 5 min remaining → proactive timer fires
   * immediately (refreshAtMs clamped to 0) because the remaining time is inside
   * the proactive window. refresh() must be called without waiting.
   *
   * Session was created 56 min ago with a 60-min TTL → 4 min remaining < 5 min.
   */
  it('Case 8: fires refresh() immediately when tab becomes visible with ≤5 min remaining', async () => {
    const elapsed = 56 * 60; // 56 minutes elapsed
    seedStorage({ created: NOW_UNIX - elapsed, ttl: TTL_SECS });
    mockRefresh.mockResolvedValue(true);

    initVisibilityRefreshGuard();

    // Simulate tab returning to foreground.
    setDocumentHidden(false);
    fireVisibilityChange();

    // refreshAtMs = max(0, (4*60*1000) - (5*60*1000)) = 0 → fires on next tick.
    vi.advanceTimersByTime(1);
    await vi.runAllTimersAsync();

    expect(mockRefresh).toHaveBeenCalledOnce();
    expect(sessionExpiredDispatches()).toBe(0);
  });

  /**
   * Case 9: Tab becomes visible after session has already expired (elapsed > TTL).
   * The timer fires immediately, refresh() is called but returns false
   * (session is expired), and session-expired is dispatched exactly once.
   *
   * Session created 65 min ago with a 60-min TTL → already expired.
   */
  it('Case 9: dispatches session-expired when tab becomes visible after session has expired', async () => {
    const elapsed = 65 * 60; // 65 minutes — past the 60-min TTL
    seedStorage({ created: NOW_UNIX - elapsed, ttl: TTL_SECS });
    mockRefresh.mockResolvedValue(false);

    initVisibilityRefreshGuard();

    setDocumentHidden(false);
    fireVisibilityChange();

    vi.advanceTimersByTime(1);
    await vi.runAllTimersAsync();

    expect(mockRefresh).toHaveBeenCalledOnce();
    expect(sessionExpiredDispatches()).toBe(1);
  });

  /**
   * Extra guard: visibilitychange while tab is still hidden must NOT trigger refresh.
   */
  it('does NOT call refresh() when visibilitychange fires while tab remains hidden', async () => {
    seedStorage({});
    initVisibilityRefreshGuard();

    setDocumentHidden(true);
    fireVisibilityChange();

    vi.advanceTimersByTime(TTL_SECS * 1000);
    await vi.runAllTimersAsync();

    // scheduleClientSessionTimer() was not called by the guard, so no timer was
    // set by the guard path (the storage-backed timer was also not started
    // because scheduleClientSessionTimer was never called before this test).
    expect(mockRefresh).not.toHaveBeenCalled();
  });

  /**
   * Extra guard: initVisibilityRefreshGuard() is idempotent — calling it multiple
   * times must not register duplicate listeners.
   */
  it('registers the listener only once even when called multiple times (idempotent)', async () => {
    const elapsed = 56 * 60;
    seedStorage({ created: NOW_UNIX - elapsed, ttl: TTL_SECS });
    mockRefresh.mockResolvedValue(true);

    initVisibilityRefreshGuard();
    initVisibilityRefreshGuard(); // second call must be a no-op
    initVisibilityRefreshGuard(); // third call must be a no-op

    setDocumentHidden(false);
    fireVisibilityChange();

    vi.advanceTimersByTime(1);
    await vi.runAllTimersAsync();

    // refresh() must be called exactly once — not three times.
    expect(mockRefresh).toHaveBeenCalledOnce();
  });

  /**
   * Full hidden → visible transition: guard fires only on the visible leg.
   *
   * This is the realistic scenario: tab was visible, goes to background
   * (hidden=true, visibilitychange fires), then comes back to foreground
   * (hidden=false, visibilitychange fires). refresh() must be called exactly
   * once — on the becoming-visible event — NOT on the becoming-hidden event.
   */
  it('fires refresh() only on the becoming-visible transition, not the becoming-hidden one', async () => {
    const elapsed = 56 * 60; // 56 minutes in → 4 min remaining, inside proactive window
    seedStorage({ created: NOW_UNIX - elapsed, ttl: TTL_SECS });
    mockRefresh.mockResolvedValue(true);

    initVisibilityRefreshGuard();

    // Tab goes to background — must NOT trigger refresh.
    setDocumentHidden(true);
    fireVisibilityChange();
    vi.advanceTimersByTime(1);
    await vi.runAllTimersAsync();
    expect(mockRefresh).not.toHaveBeenCalled();

    // Tab comes back to foreground — MUST trigger refresh.
    setDocumentHidden(false);
    fireVisibilityChange();
    vi.advanceTimersByTime(1);
    await vi.runAllTimersAsync();
    expect(mockRefresh).toHaveBeenCalledOnce();
  });

  /**
   * teardownVisibilityRefreshGuard() allows re-registration.
   *
   * After tearing down, calling initVisibilityRefreshGuard() again must register
   * a new listener that works correctly. This validates the logout → re-login cycle.
   */
  it('can be re-registered after teardown', async () => {
    const elapsed = 56 * 60;
    seedStorage({ created: NOW_UNIX - elapsed, ttl: TTL_SECS });
    mockRefresh.mockResolvedValue(true);

    initVisibilityRefreshGuard();
    teardownVisibilityRefreshGuard(); // simulates logout

    // Re-register (simulates re-login).
    initVisibilityRefreshGuard();

    setDocumentHidden(false);
    fireVisibilityChange();
    vi.advanceTimersByTime(1);
    await vi.runAllTimersAsync();

    expect(mockRefresh).toHaveBeenCalledOnce();
  });

});

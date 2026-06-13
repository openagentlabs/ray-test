/**
 * Session expiry errors + optional landing notice after full-page navigation from modal.
 */

const NOTICE_KEY = 'midas_session_notice';

/** Thrown after session-ended handling so callers stop parsing bodies. */
export class SessionExpiredError extends Error {
  constructor() {
    super('Session expired');
    this.name = 'SessionExpiredError';
  }
}

/** @deprecated Use authSessionExpiry.dispatchSessionExpiredOnce */
export function registerSessionNavigator(_nav: (to: string, options?: { replace?: boolean }) => void): void {
  /* no-op */
}

export async function parseSessionErrorMessage(response: Response): Promise<string> {
  try {
    const data = await response.clone().json();
    const d = data?.detail;
    if (d && typeof d === 'object' && 'message' in d) {
      return String((d as { message?: string }).message ?? '');
    }
    if (d && typeof d === 'object' && 'code' in d && (d as { code?: string }).code === 'session_invalid') {
      return 'Invalid or expired session. Please sign in again.';
    }
    if (typeof d === 'string') {
      return d;
    }
  } catch {
    /* ignore */
  }
  return 'Your session has expired. Please sign in again.';
}

export function consumeSessionNotice(): string | null {
  try {
    const m = localStorage.getItem(NOTICE_KEY);
    if (m) {
      localStorage.removeItem(NOTICE_KEY);
    }
    return m;
  } catch {
    return null;
  }
}

export function setSessionNoticeForLanding(message: string): void {
  try {
    localStorage.setItem(NOTICE_KEY, message);
  } catch {
    /* ignore */
  }
}

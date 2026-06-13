/**
 * Single place for 401 handling: refresh once, then session-ended modal vs silent logout.
 * SessionAuthErrorInspector encapsulates payload parsing (SRP).
 */

import { authService } from './authService';
import { dispatchSessionExpiredOnce } from './authSessionExpiry';
import { SessionExpiredError } from './sessionExpired';

export const RETRY_AFTER_REFRESH = 'RETRY_AFTER_REFRESH';

export class SilentAuthFailure extends Error {
  constructor() {
    super('Authentication failed');
    this.name = 'SilentAuthFailure';
  }
}

/** Parses API error bodies for session-expiry semantics (aligned with FastAPI `detail`). */
export class SessionAuthErrorInspector {
  static isSessionEndedPayload(data: unknown): boolean {
    if (!data || typeof data !== 'object') {
      return false;
    }
    const root = data as Record<string, unknown>;
    const detail = root.detail;
    if (detail && typeof detail === 'object') {
      const d = detail as Record<string, unknown>;
      if (d.error_code === 'SESSION_EXPIRED') {
        return true;
      }
      if (d.code === 'session_invalid') {
        return true;
      }
    }
    if (root.error_code === 'SESSION_EXPIRED' || root.error === 'SESSION_EXPIRED') {
      return true;
    }
    return false;
  }

  static extractMessage(data: unknown): string {
    if (!data || typeof data !== 'object') {
      return 'Your session has expired. Please sign in again.';
    }
    const root = data as Record<string, unknown>;
    const detail = root.detail;
    if (detail && typeof detail === 'object' && 'message' in detail) {
      return String((detail as { message?: string }).message ?? '');
    }
    if (typeof root.message === 'string') {
      return root.message;
    }
    return 'Your session has expired. Please sign in again.';
  }
}

/** @deprecated Use SessionAuthErrorInspector.isSessionEndedPayload */
export function isSessionEndedErrorPayload(data: unknown): boolean {
  return SessionAuthErrorInspector.isSessionEndedPayload(data);
}

/**
 * - Try refresh once when allowRefresh.
 * - If still unauthorized: dispatch session-expired event → SessionExpiredError → modal → user confirms → logout + redirect to login.
 */
export async function handleUnauthorizedResponse(
  response: Response,
  ctx: { allowRefresh: boolean; skipAuth: boolean }
): Promise<void> {
  if (response.status !== 401 || ctx.skipAuth) {
    return;
  }

  if (import.meta.env.DEV) {
    console.debug('[midas:auth] 401 intercepted', {
      url: response.url,
      allowRefresh: ctx.allowRefresh,
    });
  }

  if (ctx.allowRefresh) {
    const refreshed = await authService.refreshAccessToken();
    if (import.meta.env.DEV) {
      console.debug('[midas:auth] silent refresh attempt', { refreshed });
    }
    if (refreshed) {
      throw new Error(RETRY_AFTER_REFRESH);
    }
  }

  const data = await response
    .clone()
    .json()
    .catch(() => ({}));

  const msg = SessionAuthErrorInspector.extractMessage(data);

  if (SessionAuthErrorInspector.isSessionEndedPayload(data)) {
    dispatchSessionExpiredOnce(msg);
    throw new SessionExpiredError();
  }

  // Any other 401 after refresh failed: same UX — modal, then logout + redirect to login on OK
  dispatchSessionExpiredOnce(
    msg?.trim() || 'Your session has expired. Please sign in again.'
  );
  throw new SessionExpiredError();
}

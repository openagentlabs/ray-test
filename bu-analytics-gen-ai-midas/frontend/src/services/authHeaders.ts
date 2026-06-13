/**
 * Shared MIDAS API auth headers: Bearer JWT, X-Session-Id.
 * Use for fetch, axios, and apiInterceptor so all calls hit session middleware consistently.
 */

import { authService } from './authService';
import { getStoredSessionId } from './authSessionExpiry';

export function buildMidasAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  const token = authService.getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const sid = getStoredSessionId();
  if (sid) {
    headers['X-Session-Id'] = sid;
  }
  return headers;
}

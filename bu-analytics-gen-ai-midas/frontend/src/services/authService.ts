/**
 * Authentication service for API calls.
 *
 * Authentication is now Cognito (Hosted UI + Entra ID federation). This module
 * holds the internal Bearer access token and user profile returned by the
 * backend's /api/v1/auth/cognito/exchange endpoint, and drives session-timer
 * bookkeeping. The actual Cognito flow (PKCE, authorize redirect, callback,
 * refresh, logout) lives in ./cognitoAuthService.ts.
 */

import {
  persistSessionMetaFromApi,
  scheduleClientSessionTimer,
  clearSessionTimerAndMeta,
  resetSessionExpiryDispatchFlag,
  dispatchSessionExpiredOnce,
  initVisibilityRefreshGuard,
  teardownVisibilityRefreshGuard,
} from './authSessionExpiry';

const VITE_BASE_URL = import.meta.env.VITE_BASE_URL || '';
const API_BASE_URL = `${VITE_BASE_URL}/api/v1/auth`;

// Warn if VITE_BASE_URL is not set in production
if (import.meta.env.PROD && !VITE_BASE_URL) {
  console.warn('⚠️ VITE_BASE_URL is not set! API calls may fail. Please set VITE_BASE_URL environment variable.');
  console.warn('Current API_BASE_URL:', API_BASE_URL);
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  full_name: string;
  email?: string;
  password: string;
  is_active?: boolean;
}

export interface User {
  id: number;
  username: string;
  full_name: string;
  email?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
  refresh_token?: string;
  /** Server session id (mirrors JWT sid); sent as X-Session-Id on requests. */
  session_id?: string;
  /** Unix seconds when the server session was created. */
  session_created_at?: number;
  /** Server-side session TTL in seconds (idle / absolute per backend). */
  session_ttl_seconds?: number;
}

export interface AuthError {
  detail: string;
}

class AuthService {
  private token: string | null = null;

  constructor() {
    // Load internal access token from localStorage on initialization.
    // Note: the legacy `refresh_token` key is intentionally no longer read or written here — the Cognito
    // refresh token lives in a backend-issued HttpOnly cookie and is never exposed to JS.
    this.token = localStorage.getItem('auth_token');
    // Clean up any legacy refresh token previously written by the username/password flow.
    localStorage.removeItem('refresh_token');
  }

  /**
   * Persist the full login response returned by the backend's Cognito `/exchange`
   * endpoint (also compatible with the legacy `/login` shape). Used by
   * `cognitoAuthService.completeLogin`.
   */
  setSessionFromApiResponse(data: LoginResponse): void {
    this.token = data.access_token;
    localStorage.setItem('auth_token', data.access_token);
    localStorage.setItem('user_data', JSON.stringify(data.user));

    const created =
      typeof data.session_created_at === 'number'
        ? data.session_created_at
        : Math.floor(Date.now() / 1000);
    const ttl =
      typeof data.session_ttl_seconds === 'number' && data.session_ttl_seconds > 0
        ? data.session_ttl_seconds
        : typeof data.expires_in === 'number' && data.expires_in > 0
          ? data.expires_in
          : 120;
    persistSessionMetaFromApi(created, ttl, data.session_id ?? null);
    initVisibilityRefreshGuard();
  }

  /**
   * Update only the internal Bearer access token (used by `cognitoAuthService.refresh`
   * after it re-mints the token via the backend's /refresh endpoint).
   */
  setAccessTokenOnly(accessToken: string): void {
    this.token = accessToken;
    localStorage.setItem('auth_token', accessToken);
  }

  /**
   * Get current user information
   */
  async getCurrentUser(): Promise<User> {
    if (!this.token) {
      throw new Error('No authentication token found');
    }

    const fetchMe = async (): Promise<Response> => {
      return fetch(`${API_BASE_URL}/me`, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${this.token}`,
        },
      });
    };

    try {
      const { handleUnauthorizedResponse, RETRY_AFTER_REFRESH } = await import('./httpUnauthorized');
      let response = await fetchMe();
      if (response.status === 401) {
        try {
          await handleUnauthorizedResponse(response, { allowRefresh: true, skipAuth: false });
        } catch (e: unknown) {
          const err = e as { message?: string };
          if (err?.message === RETRY_AFTER_REFRESH) {
            response = await fetchMe();
            if (response.status === 401) {
              await handleUnauthorizedResponse(response, { allowRefresh: false, skipAuth: false });
            }
          } else {
            throw e;
          }
        }
      }

      if (!response.ok) {
        const errorData = (await response.json().catch(() => ({}))) as AuthError;
        throw new Error(
          (typeof errorData.detail === 'string' ? errorData.detail : null) || 'Failed to get user information'
        );
      }

      const data: User = await response.json();
      return data;
    } catch (error) {
      console.error('Get current user error:', error);
      throw error;
    }
  }

  /**
   * Verify if the current token is valid
   */
  async verifyToken(): Promise<boolean> {
    return (await this.verifyTokenStatus()) === 'valid';
  }

  /** Distinguish expired session (401) from transport errors so we do not redirect on flaky networks. */
  private async verifyTokenStatus(): Promise<'valid' | 'unauthorized' | 'error'> {
    if (!this.token) {
      return 'unauthorized';
    }

    try {
      const response = await fetch(`${API_BASE_URL}/verify-token`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.token}`,
        },
      });

      if (response.status === 401) {
        return 'unauthorized';
      }
      if (response.ok) {
        return 'valid';
      }
      return 'error';
    } catch (error) {
      console.error('Token verification error:', error);
      return 'error';
    }
  }

  /**
   * Local logout: clear the Bearer token, user profile, timers, and caches.
   * The HttpOnly Cognito refresh cookie is cleared by the backend `/logout` endpoint;
   * full Cognito + Entra logout is orchestrated by `cognitoAuthService.logout`.
   */
  logout(): void {
    clearSessionTimerAndMeta();
    teardownVisibilityRefreshGuard();
    resetSessionExpiryDispatchFlag();
    this.token = null;
    localStorage.removeItem('auth_token');
    localStorage.removeItem('refresh_token'); // legacy cleanup
    localStorage.removeItem('user_data');
    localStorage.removeItem('chatSessions');
    localStorage.removeItem('datasets');
    localStorage.removeItem('connections');
    sessionStorage.clear();
    // Notify UserContext / any listeners that authentication state has changed.
    try { window.dispatchEvent(new Event('midas:auth-changed')); } catch { /* no-op */ }
  }

  /**
   * Get stored authentication token
   */
  getToken(): string | null {
    return this.token;
  }

  /**
   * Silent refresh: delegate to the Cognito flow. The Cognito refresh token lives in
   * the backend-issued HttpOnly cookie, so nothing is read from localStorage here.
   */
  async refreshAccessToken(): Promise<boolean> {
    // Lazy import to avoid a circular dependency with cognitoAuthService -> authService.
    const { refresh } = await import('./cognitoAuthService');
    return refresh();
  }

  /**
   * Check if user is authenticated
   */
  isAuthenticated(): boolean {
    return this.token !== null;
  }

  /**
   * Get stored user data
   */
  getStoredUser(): User | null {
    try {
      const userData = localStorage.getItem('user_data');
      return userData ? JSON.parse(userData) : null;
    } catch (error) {
      console.error('Error parsing stored user data:', error);
      return null;
    }
  }

  /**
   * Initialize authentication state on app boot.
   *
   * Flow:
   *  1. If we have a locally-stored Bearer token, verify it with the backend.
   *  2. If verification says "expired/unauthorized", attempt a silent refresh via the
   *     HttpOnly Cognito cookie (it works even when `auth_token` was never stored — e.g.
   *     a fresh tab after a full-page reload).
   *  3. Propagate the final outcome to the caller.
   */
  async initializeAuth(): Promise<{ isAuthenticated: boolean; user: User | null }> {
    const storedUser = this.getStoredUser();

    // On the Cognito /auth/callback page, the AuthCallback component is the
    // sole authority — it will exchange the authorization code and populate
    // the session. Do NOT race it with a silent /cognito/refresh here
    // (that call would always 401 because the midas_cg_rt cookie is only
    // set *after* /exchange, and the spurious 401 shows up in server logs).
    const onCallbackRoute =
      typeof window !== 'undefined' && window.location.pathname === '/auth/callback';

    if (!this.token || !storedUser) {
      if (onCallbackRoute) {
        return { isAuthenticated: false, user: null };
      }
      // No local token: try silent refresh via the HttpOnly Cognito cookie.
      const refreshed = await this.refreshAccessToken();
      if (refreshed) {
        // /refresh does not return the user profile; reuse whatever we had cached (may be null).
        return { isAuthenticated: true, user: storedUser };
      }
      return { isAuthenticated: false, user: null };
    }

    const tokenStatus = await this.verifyTokenStatus();
    if (tokenStatus === 'valid') {
      scheduleClientSessionTimer();
      initVisibilityRefreshGuard();
      return { isAuthenticated: true, user: storedUser };
    }

    const refreshed = await this.refreshAccessToken();
    if (refreshed) {
      return { isAuthenticated: true, user: storedUser };
    }

    if (tokenStatus === 'unauthorized') {
      dispatchSessionExpiredOnce('Your session has expired. Please sign in again.');
    } else {
      this.logout();
    }
    return { isAuthenticated: false, user: null };
  }
}

// Create and export a singleton instance
export const authService = new AuthService();
export default authService;
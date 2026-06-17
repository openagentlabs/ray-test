/**
 * Authentication service for API calls.
 *
 * Uses email/password login against /api/v1/auth/login with server-side sessions
 * and internal Bearer JWT tokens.
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
// Local Vite dev: same-origin /api proxy (vite.config.ts) — no CORS, works on any dev port.
const API_BASE_URL = import.meta.env.DEV
  ? '/api/v1/auth'
  : `${VITE_BASE_URL}/api/v1/auth`;

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
    this.token = localStorage.getItem('auth_token');
  }

  /**
   * Login with email and password against the backend /login endpoint.
   */
  async login(username: string, password: string): Promise<LoginResponse> {
    const response = await fetch(`${API_BASE_URL}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ username, password }),
    });

    if (!response.ok) {
      const errorData = (await response.json().catch(() => ({}))) as AuthError;
      const detail = typeof errorData.detail === 'string' ? errorData.detail : 'Invalid username or password';
      throw new Error(detail);
    }

    const data: LoginResponse = await response.json();
    this.setSessionFromApiResponse(data);
    return data;
  }

  /**
   * Persist the full login response returned by the backend /login endpoint.
   */
  setSessionFromApiResponse(data: LoginResponse): void {
    this.token = data.access_token;
    localStorage.setItem('auth_token', data.access_token);
    localStorage.setItem('user_data', JSON.stringify(data.user));
    if (data.refresh_token) {
      localStorage.setItem('refresh_token', data.refresh_token);
    }

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
    try { window.dispatchEvent(new Event('midas:auth-changed')); } catch { /* no-op */ }
  }

  /**
   * Update only the internal Bearer access token (used after /refresh).
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
   * Server logout: invalidate session and revoke refresh tokens.
   */
  async logoutFromServer(): Promise<void> {
    if (!this.token) {
      return;
    }
    try {
      await fetch(`${API_BASE_URL}/logout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${this.token}` },
        credentials: 'include',
      });
    } catch (error) {
      console.error('Server logout error:', error);
    }
  }

  /**
   * Local logout: clear the Bearer token, user profile, timers, and caches.
   */
  logout(): void {
    clearSessionTimerAndMeta();
    teardownVisibilityRefreshGuard();
    resetSessionExpiryDispatchFlag();
    this.token = null;
    localStorage.removeItem('auth_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_data');
    localStorage.removeItem('chatSessions');
    localStorage.removeItem('datasets');
    localStorage.removeItem('connections');
    sessionStorage.clear();
    try { window.dispatchEvent(new Event('midas:auth-changed')); } catch { /* no-op */ }
  }

  /**
   * Get stored authentication token
   */
  getToken(): string | null {
    return this.token;
  }

  /**
   * Silent refresh via /api/v1/auth/refresh using stored refresh token.
   */
  async refreshAccessToken(): Promise<boolean> {
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) {
      return false;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) {
        return false;
      }

      const data = await response.json();
      if (!data.access_token) {
        return false;
      }

      this.setAccessTokenOnly(data.access_token);
      const created =
        typeof data.session_created_at === 'number'
          ? data.session_created_at
          : Math.floor(Date.now() / 1000);
      const ttl =
        typeof data.session_ttl_seconds === 'number' && data.session_ttl_seconds > 0
          ? data.session_ttl_seconds
          : typeof data.expires_in === 'number' && data.expires_in > 0
            ? data.expires_in
            : 3600;
      persistSessionMetaFromApi(created, ttl, data.session_id ?? null);
      return true;
    } catch (error) {
      console.error('Token refresh error:', error);
      return false;
    }
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
   */
  async initializeAuth(): Promise<{ isAuthenticated: boolean; user: User | null }> {
    const storedUser = this.getStoredUser();

    if (!this.token || !storedUser) {
      const refreshed = await this.refreshAccessToken();
      if (refreshed) {
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

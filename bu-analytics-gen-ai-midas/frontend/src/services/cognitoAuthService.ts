/**
 * Cognito (Hosted UI + Entra ID) authentication service — browser side.
 *
 * Flow (matches backend `/api/v1/auth/cognito/*`):
 *   1. beginLogin()      -> generate PKCE verifier + challenge; GET /login-url
 *                           (backend sets HttpOnly cg_login cookie with state/nonce/vhash);
 *                           window.location.assign(authorize_url + code_challenge).
 *   2. completeLogin()   -> called from /auth/callback. POSTs { code, state, code_verifier,
 *                           redirect_uri } to /exchange. Backend sets midas_cg_rt cookie and
 *                           returns the internal app access_token (Bearer) + user profile.
 *   3. refresh()         -> called by apiInterceptor on 401. POST /refresh; cookie-bound.
 *   4. logout()          -> POST /logout with optional JSON { dataset_id }; backend revokes
 *                           Cognito refresh (RFC 7009), clears cookies and returns the
 *                           Cognito /logout URL; we then redirect the browser there to end
 *                           the federated SSO session.
 *
 * The Cognito client secret is NEVER exposed here. PKCE verifier stays in
 * sessionStorage until /exchange, at which point it is discarded.
 */

import authService, { LoginResponse } from './authService';

const VITE_BASE_URL = import.meta.env.VITE_BASE_URL || '';
const COGNITO_API_BASE = `${VITE_BASE_URL}/api/v1/auth/cognito`;

const COGNITO_DOMAIN = (import.meta.env.VITE_COGNITO_DOMAIN || '').replace(/\/+$/, '');
const COGNITO_CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID || '';
const COGNITO_REDIRECT_URI = import.meta.env.VITE_COGNITO_REDIRECT_URI || '';
const COGNITO_LOGOUT_REDIRECT_URI = import.meta.env.VITE_COGNITO_LOGOUT_REDIRECT_URI || '';
// VITE_COGNITO_SCOPES is advisory only: the backend owns the authorize URL and
// includes its own server-configured scopes so we do not read it here.

const SS_VERIFIER = 'cg_verifier';
const SS_STATE = 'cg_state';
const SS_NONCE = 'cg_nonce';

/** Matches Model Builder / steps (`sessionStorage.setItem('dataset_id', ...)`). */
const SESSION_DATASET_ID_KEY = 'dataset_id';

function getSessionDatasetId(): string | null {
  if (typeof window === 'undefined') return null;
  return sessionStorage.getItem(SESSION_DATASET_ID_KEY);
}

/** Thrown when Cognito config is missing — surfaces as a friendly error in the UI. */
export class CognitoConfigError extends Error {}

export interface ExchangeResponse extends LoginResponse {}

export interface LogoutResponse {
  cognito_logout_url: string;
  cognito_revoked: boolean;
  app_refresh_tokens_revoked: number;
  /** Echo of ``dataset_id`` from the request body when the server parsed it. */
  dataset_id?: string | null;
}

// ---------- PKCE helpers (Web Crypto) ---------------------------------------

function randomUrlSafe(byteLength: number): string {
  const bytes = new Uint8Array(byteLength);
  crypto.getRandomValues(bytes);
  return base64UrlEncode(bytes);
}

function base64UrlEncode(bytes: Uint8Array): string {
  let s = '';
  for (let i = 0; i < bytes.byteLength; i++) s += String.fromCharCode(bytes[i]);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

async function sha256Base64Url(input: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(input));
  return base64UrlEncode(new Uint8Array(digest));
}

async function sha256Hex(input: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(input));
  const bytes = new Uint8Array(digest);
  let hex = '';
  for (let i = 0; i < bytes.length; i++) hex += bytes[i].toString(16).padStart(2, '0');
  return hex;
}

// ---------- Public API ------------------------------------------------------

function assertConfigured(): void {
  if (!COGNITO_DOMAIN || !COGNITO_CLIENT_ID || !COGNITO_REDIRECT_URI) {
    throw new CognitoConfigError(
      'Cognito is not configured. Set VITE_COGNITO_DOMAIN, VITE_COGNITO_CLIENT_ID, VITE_COGNITO_REDIRECT_URI.'
    );
  }
}

/**
 * Start the Cognito login: generate PKCE + fetch authorize URL from backend,
 * then redirect the browser to Cognito Hosted UI.
 */
export async function beginLogin(): Promise<void> {
  assertConfigured();

  // Fresh per-login secrets.
  const verifier = randomUrlSafe(64); // ~86 url-safe chars, inside the 43..128 PKCE range
  const challenge = await sha256Base64Url(verifier);
  const vhash = await sha256Hex(verifier);

  // Store verifier in sessionStorage — needed at callback time.
  sessionStorage.setItem(SS_VERIFIER, verifier);

  // Ask the backend to mint state + nonce (bound to vhash via HttpOnly cg_login cookie).
  const resp = await fetch(`${COGNITO_API_BASE}/login-url?vhash=${encodeURIComponent(vhash)}`, {
    method: 'GET',
    credentials: 'include',
  });
  if (!resp.ok) {
    clearLoginScratch();
    const text = await resp.text().catch(() => '');
    throw new Error(`Failed to initialize login (${resp.status}): ${text}`);
  }
  const { authorize_url, state, nonce } = (await resp.json()) as {
    authorize_url: string;
    state: string;
    nonce: string;
  };

  sessionStorage.setItem(SS_STATE, state);
  sessionStorage.setItem(SS_NONCE, nonce);

  // Backend returned the authorize URL without the code_challenge (verifier stays client-side).
  // Append it here.
  const sep = authorize_url.includes('?') ? '&' : '?';
  const finalUrl = `${authorize_url}${sep}code_challenge=${encodeURIComponent(challenge)}`;

  window.location.assign(finalUrl);
}

/**
 * Handle the redirect from Cognito: POST the code to the backend, store the
 * returned internal access token, update user state.
 * @returns the user object so the caller can update React state.
 */
export async function completeLogin(search: string): Promise<LoginResponse['user']> {
  assertConfigured();

  const params = new URLSearchParams(search);
  const code = params.get('code');
  const state = params.get('state');
  const error = params.get('error');
  const errorDescription = params.get('error_description');

  try {
    if (error) {
      throw new Error(errorDescription || error);
    }
    if (!code || !state) {
      throw new Error('Missing code or state in callback URL.');
    }
    const storedState = sessionStorage.getItem(SS_STATE);
    const verifier = sessionStorage.getItem(SS_VERIFIER);
    if (!storedState || !verifier) {
      throw new Error('Login session expired. Please try signing in again.');
    }
    if (storedState !== state) {
      throw new Error('Invalid state. Aborting to protect against CSRF.');
    }

    const resp = await fetch(`${COGNITO_API_BASE}/exchange`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        code,
        state,
        code_verifier: verifier,
        redirect_uri: COGNITO_REDIRECT_URI,
      }),
    });
    if (!resp.ok) {
      const text = await resp.text().catch(() => '');
      throw new Error(`Authentication failed (${resp.status}): ${text || 'auth_failed'}`);
    }
    const data = (await resp.json()) as LoginResponse;

    // Reuse the existing auth service to persist the Bearer token, user and session meta.
    authService.setSessionFromApiResponse(data);

    return data.user;
  } finally {
    clearLoginScratch();
  }
}

// Single-flight promise: coalesces concurrent refresh calls so only ONE network
// request goes to /cognito/refresh at a time. Without this, N API calls that all
// 401 simultaneously would each fire their own /refresh, race on Set-Cookie, and
// all but the last winner would then retry with a stale sid → second 401 → logout.
let _refreshInflight: Promise<boolean> | null = null;

/**
 * Silent refresh using the midas_cg_rt HttpOnly cookie. Mints a new internal
 * Bearer access token; called automatically by the API interceptor on 401.
 *
 * Concurrent callers share a single in-flight request (single-flight pattern).
 * On success dispatches ``midas:auth-token-refreshed`` so any retry can pick up
 * the new Bearer without an additional /refresh round-trip.
 */
export function refresh(): Promise<boolean> {
  if (_refreshInflight) {
    if (import.meta.env.DEV) {
      console.debug('[midas:auth] refresh() — coalescing to in-flight request');
    }
    return _refreshInflight;
  }

  _refreshInflight = _doRefresh().finally(() => {
    _refreshInflight = null;
  });
  return _refreshInflight;
}

async function _doRefresh(): Promise<boolean> {
  if (!COGNITO_DOMAIN) return false; // pure-client dev without Cognito configured
  try {
    const currentToken = authService.getToken();
    const headers: HeadersInit = { 'Content-Type': 'application/json' };
    // Pass the current Bearer so the backend can invalidate the previous sid
    // before issuing a new one (prevents server-session-store leaks on rotation).
    if (currentToken) {
      headers['Authorization'] = `Bearer ${currentToken}`;
    }

    if (import.meta.env.DEV) {
      console.debug('[midas:auth] refresh() — calling /cognito/refresh', { hasToken: !!currentToken });
    }

    const resp = await fetch(`${COGNITO_API_BASE}/refresh`, {
      method: 'POST',
      credentials: 'include',
      headers,
    });

    if (!resp.ok) {
      if (import.meta.env.DEV) {
        console.debug('[midas:auth] refresh() — FAILED', { status: resp.status });
      }
      return false;
    }

    const data = (await resp.json()) as {
      access_token: string;
      expires_in: number;
      session_id?: string;
      session_created_at?: number;
      session_ttl_seconds?: number;
    };
    if (!data.access_token) return false;

    // Use setSessionFromApiResponse so the session timer is always rescheduled
    // with the full server-authoritative TTL (session_ttl_seconds).
    // Guard against getStoredUser() returning null (e.g. hard reload cleared
    // localStorage while the HttpOnly cookie survived) — in that case we keep
    // the token update but skip the user write so we don't corrupt user_data.
    const storedUser = authService.getStoredUser();
    if (storedUser) {
      authService.setSessionFromApiResponse({
        access_token: data.access_token,
        token_type: 'bearer',
        expires_in: data.expires_in ?? 3600,
        user: storedUser,
        session_id: data.session_id,
        session_created_at: data.session_created_at,
        session_ttl_seconds: data.session_ttl_seconds,
      });
    } else {
      // No cached user — update token and timer meta only.
      authService.setAccessTokenOnly(data.access_token);
      const { persistSessionMetaFromApi } = await import('./authSessionExpiry');
      persistSessionMetaFromApi(
        data.session_created_at ?? Math.floor(Date.now() / 1000),
        data.session_ttl_seconds ?? data.expires_in ?? 3600,
        data.session_id ?? null,
      );
    }

    // Notify any concurrent in-flight API retries that a new token is available
    // so they can pick it up lazily without a second /refresh call.
    try {
      window.dispatchEvent(new CustomEvent('midas:auth-token-refreshed'));
    } catch {
      /* no-op in SSR / test environments */
    }

    if (import.meta.env.DEV) {
      console.debug('[midas:auth] refresh() — success', {
        session_id: data.session_id,
        ttl: data.session_ttl_seconds,
      });
    }

    return true;
  } catch (e) {
    console.error('Cognito refresh failed:', e);
    return false;
  }
}

/**
 * Full logout: revoke Cognito refresh, clear server session and cookies, wipe
 * local state, then redirect to Cognito /logout to end the Entra SSO session.
 */
export async function logout(): Promise<void> {
  const datasetId = getSessionDatasetId();
  if (import.meta.env.DEV) {
    console.debug('[midas:auth] logout() datasetId:', datasetId);
  }

  const token = authService.getToken();
  let cognitoLogoutUrl: string | null = null;
  try {
    if (token) {
      const resp = await fetch(`${COGNITO_API_BASE}/logout`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ dataset_id: datasetId }),
      });
      if (resp.ok) {
        const data = (await resp.json()) as LogoutResponse;
        cognitoLogoutUrl = data.cognito_logout_url;
      } else {
        console.warn('Cognito logout endpoint returned non-OK:', resp.status);
      }
    }
  } catch (e) {
    console.warn('Cognito logout request failed:', e);
  }

  // Clear local React/session state regardless of backend result.
  authService.logout();

  if (cognitoLogoutUrl) {
    window.location.assign(cognitoLogoutUrl);
    return;
  }
  // Fallback: if the backend call failed but we have enough config, still redirect.
  if (COGNITO_DOMAIN && COGNITO_CLIENT_ID && COGNITO_LOGOUT_REDIRECT_URI) {
    const params = new URLSearchParams({
      client_id: COGNITO_CLIENT_ID,
      logout_uri: COGNITO_LOGOUT_REDIRECT_URI,
    });
    window.location.assign(`${COGNITO_DOMAIN}/logout?${params.toString()}`);
    return;
  }
  // Last-resort: reload the landing page so the app re-initializes in unauthenticated state.
  window.location.assign('/');
}

function clearLoginScratch(): void {
  sessionStorage.removeItem(SS_VERIFIER);
  sessionStorage.removeItem(SS_STATE);
  sessionStorage.removeItem(SS_NONCE);
}

export default {
  beginLogin,
  completeLogin,
  refresh,
  logout,
};

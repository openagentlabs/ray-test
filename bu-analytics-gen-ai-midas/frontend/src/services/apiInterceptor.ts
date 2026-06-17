/**
 * Centralized API service with automatic authentication handling
 */

import { SessionExpiredError } from './sessionExpired';
import { buildMidasAuthHeaders } from './authHeaders';
import {
  handleUnauthorizedResponse,
  RETRY_AFTER_REFRESH,
  SilentAuthFailure,
} from './httpUnauthorized';

/** Avoid `/api/v1` twice if `VITE_BASE_URL` already includes it. */
function resolveApiV1Base(): string {
  // Local Vite dev: same-origin /api proxy (vite.config.ts) — no CORS, works on any dev port.
  if (import.meta.env.DEV) {
    return '/api/v1';
  }
  const raw = (import.meta.env.VITE_BASE_URL || '').trim().replace(/\/+$/, '');
  if (!raw) {
    return '/api/v1';
  }
  if (/\/api\/v1$/i.test(raw)) {
    return raw;
  }
  return `${raw}/api/v1`;
}

/** FastAPI may return `detail` as string, object, or validation array. */
function formatFastApiError(detail: unknown): string {
  if (detail == null) {
    return '';
  }
  if (typeof detail === 'string') {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item: { msg?: string; loc?: unknown[] }) => item?.msg || JSON.stringify(item))
      .join('; ');
  }
  if (typeof detail === 'object' && detail !== null && 'message' in detail) {
    return String((detail as { message?: string }).message);
  }
  try {
    return JSON.stringify(detail);
  } catch {
    return String(detail);
  }
}

export interface ApiRequestOptions extends RequestInit {
  params?: Record<string, any>;
  skipAuth?: boolean;
}

export interface ApiResponse<T = any> {
  data: T;
  status: number;
  statusText: string;
}
class ApiInterceptor {
  private baseUrl: string;

  constructor(baseUrl: string = resolveApiV1Base()) {
    this.baseUrl = baseUrl;
  }

  /**
   * Get authentication headers
   */
  private getAuthHeaders(): HeadersInit {
    return buildMidasAuthHeaders() as HeadersInit;
  }

  /**
   * Build full URL with query parameters
   */
  private buildUrl(endpoint: string, params?: Record<string, any>): string {
    const base = this.baseUrl.replace(/\/+$/, '');
    const searchParams = new URLSearchParams();

    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          searchParams.append(key, String(value));
        }
      });
    }

    // Do not use `new URL('/projects', base)` - a leading `/` replaces the path and drops `/api/v1`.
    let combinedPath: string;
    if (endpoint.startsWith('/api/')) {
      combinedPath = endpoint;
    } else if (endpoint.startsWith('/')) {
      combinedPath = `${base}${endpoint}`;
    } else {
      combinedPath = `${base}/${endpoint}`;
    }
    combinedPath = combinedPath.replace(/([^:]\/)\/+/g, '$1');

    if (/^https?:\/\//i.test(combinedPath)) {
      const resolved = new URL(combinedPath);
      searchParams.forEach((value, key) => resolved.searchParams.append(key, value));
      return resolved.toString();
    }

    const query = searchParams.toString();
    return query ? `${combinedPath}?${query}` : combinedPath;
  }

  /**
   * Shared 401 handling: one refresh + retry at the call site; second pass uses allowRefresh false.
   */
  private async process401Response(
    response: Response,
    ctx: { allowRefresh: boolean; skipAuth: boolean }
  ): Promise<void> {
    if (response.status !== 401 || ctx.skipAuth) {
      return;
    }
    await handleUnauthorizedResponse(response, ctx);
  }

  /**
   * Handle API responses and errors.
   * @param allowRefresh - If false, a 401 goes straight to session-expired (no second refresh loop).
   */
  private async handleResponse<T>(
    response: Response,
    ctx: { allowRefresh: boolean; skipAuth: boolean }
  ): Promise<ApiResponse<T>> {
    if (!response.ok) {
      await this.process401Response(response, ctx);

      const errorData = await response.json().catch(() => ({ message: 'Unknown error' }));
      const detailStr = formatFastApiError(errorData.detail) || (errorData.message as string) || '';
      throw new Error(detailStr || `HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    return {
      data,
      status: response.status,
      statusText: response.statusText
    };
  }

  /**
   * Generic request method
   */
  async request<T = any>(
    endpoint: string, 
    options: ApiRequestOptions = {}
  ): Promise<ApiResponse<T>> {
    const { params, skipAuth = false, ...requestOptions } = options;
    
    // Build headers
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...(skipAuth ? {} : this.getAuthHeaders()),
      ...(requestOptions.headers || {})
    };

    // Remove Content-Type for FormData
    if (requestOptions.body instanceof FormData) {
      delete (headers as any)['Content-Type'];
    }

    const url = this.buildUrl(endpoint, params);
    
    const fetchOnce = async (reqHeaders: HeadersInit) => {
      return fetch(url, {
        ...requestOptions,
        headers: reqHeaders
      });
    };

    const doRequest = async (allowRefresh: boolean): Promise<ApiResponse<T>> => {
      const response = await fetchOnce(headers);
      try {
        return await this.handleResponse<T>(response, { allowRefresh, skipAuth });
      } catch (e: any) {
        if (allowRefresh && !skipAuth && e?.message === RETRY_AFTER_REFRESH) {
          // Re-read the token lazily after refresh so we pick up the freshly minted
          // Bearer rather than the stale one captured in the closure above.
          const retryHeaders: HeadersInit = {
            'Content-Type': 'application/json',
            ...(this.getAuthHeaders()),
            ...(requestOptions.headers || {})
          };
          if (requestOptions.body instanceof FormData) {
            delete (retryHeaders as any)['Content-Type'];
          }
          const retryResponse = await fetchOnce(retryHeaders);
          // Second 401 must not call refresh again - go straight to login redirect
          return await this.handleResponse<T>(retryResponse, { allowRefresh: false, skipAuth });
        }
        throw e;
      }
    };

    try {
      return await doRequest(true);
    } catch (error: any) {
      if (error instanceof SessionExpiredError || error instanceof SilentAuthFailure) {
        throw error;
      }
      console.error('API request failed:', error);
      throw error;
    }
  }

  /**
   * GET request
   */
  async get<T = any>(
    endpoint: string, 
    options: ApiRequestOptions = {}
  ): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { ...options, method: 'GET' });
  }

  /**
   * POST request
   */
  async post<T = any>(
    endpoint: string, 
    data?: any, 
    options: ApiRequestOptions = {}
  ): Promise<ApiResponse<T>> {
    const body = data instanceof FormData ? data : JSON.stringify(data);
    return this.request<T>(endpoint, { ...options, method: 'POST', body });
  }

  /**
   * PUT request
   */
  async put<T = any>(
    endpoint: string, 
    data?: any, 
    options: ApiRequestOptions = {}
  ): Promise<ApiResponse<T>> {
    const body = data instanceof FormData ? data : JSON.stringify(data);
    return this.request<T>(endpoint, { ...options, method: 'PUT', body });
  }

  /**
   * DELETE request
   */
  async delete<T = any>(
    endpoint: string, 
    options: ApiRequestOptions = {}
  ): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { ...options, method: 'DELETE' });
  }

  /**
   * Download file
   */
  async downloadFile(
    endpoint: string, 
    options: ApiRequestOptions = {}
  ): Promise<Blob> {
    const { params, skipAuth = false, ...requestOptions } = options;
    
    const headers: HeadersInit = {
      ...(skipAuth ? {} : this.getAuthHeaders()),
      ...(requestOptions.headers || {})
    };

    const url = this.buildUrl(endpoint, params);

    const fetchOnce = async (reqHeaders: HeadersInit) =>
      fetch(url, {
        ...requestOptions,
        headers: reqHeaders
      });

    const run = async (allowRefresh: boolean): Promise<Response> => {
      const response = await fetchOnce(headers);
      try {
        await this.process401Response(response, { allowRefresh, skipAuth });
      } catch (e: any) {
        if (allowRefresh && !skipAuth && e?.message === RETRY_AFTER_REFRESH) {
          const retryHeaders: HeadersInit = {
            ...(skipAuth ? {} : this.getAuthHeaders()),
            ...(requestOptions.headers || {})
          };
          const retryResponse = await fetchOnce(retryHeaders);
          await this.process401Response(retryResponse, { allowRefresh: false, skipAuth });
          return retryResponse;
        }
        throw e;
      }
      return response;
    };
    
    try {
      const response = await run(true);

      if (!response.ok) {
        throw new Error(`Download failed: ${response.status} - ${response.statusText}`);
      }

      return await response.blob();
    } catch (error) {
      if (error instanceof SessionExpiredError || error instanceof SilentAuthFailure) {
        throw error;
      }
      console.error('File download failed:', error);
      throw error;
    }
  }
}

export const apiInterceptor = new ApiInterceptor();

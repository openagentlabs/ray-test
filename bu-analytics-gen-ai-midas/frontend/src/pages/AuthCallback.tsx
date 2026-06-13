/**
 * /auth/callback page.
 *
 * Cognito Hosted UI redirects the browser here with ?code=…&state=…
 * (or ?error=…&error_description=… on failure). We hand both off to
 * `cognitoAuthService.completeLogin`, which POSTs them to the backend,
 * stores the returned internal access token, and signals the rest of the
 * app through the `midas:auth-changed` event.
 */

import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Loader2, RefreshCcw } from 'lucide-react';
import cognitoAuthService from '../services/cognitoAuthService';
import { useUser } from '../contexts/UserContext';

type Status = 'processing' | 'error';

const AuthCallback: React.FC = () => {
  const [status, setStatus] = useState<Status>('processing');
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const { login } = useUser();
  const completedRef = useRef(false);

  useEffect(() => {
    if (completedRef.current) return;
    completedRef.current = true;

    // Snapshot the URL query string once, synchronously, before anything can
    // mutate it (navigate('/'), history.replaceState, etc.). This avoids a
    // race where a re-render after the route-tree flip reads an already-empty
    // search string and throws a spurious "Missing code or state" error.
    const search = window.location.search;
    const params = new URLSearchParams(search);
    const hasCognitoParams =
      params.has('code') || params.has('state') || params.has('error');

    // Defensive: if someone lands on /auth/callback with no Cognito params at
    // all (bookmark, back button, manual refresh after success), don't show
    // a scary error — just send them home. Real callbacks always carry at
    // least one of these.
    if (!hasCognitoParams) {
      navigate('/', { replace: true });
      return;
    }

    (async () => {
      try {
        const apiUser = await cognitoAuthService.completeLogin(search);
        // Mirror the same UserContext shape that the legacy AuthModal used.
        const frontendUser = {
          name: apiUser.full_name,
          role: 'Data Analyst',
          avatar: `https://ui-avatars.com/api/?name=${encodeURIComponent(
            apiUser.full_name
          )}&background=3b82f6&color=ffffff`,
          email: apiUser.email || '',
          id: apiUser.id.toString(),
          username: apiUser.username,
        };
        login(frontendUser);
        // Replace /auth/callback in history so Back doesn't re-trigger the callback.
        navigate('/', { replace: true });
      } catch (e) {
        const msg = e instanceof Error ? e.message : 'Sign-in failed.';
        setError(msg);
        setStatus('error');
      }
    })();
  }, [login, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-blue-50 dark:from-gray-900 dark:to-gray-950 px-4">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl max-w-md w-full p-8">
        {status === 'processing' && (
          <div className="flex flex-col items-center text-center space-y-4">
            <Loader2 className="h-10 w-10 animate-spin text-blue-600 dark:text-blue-400" />
            <h1 className="text-lg font-semibold text-gray-900 dark:text-white">
              Finishing sign-in…
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-300">
              Exchanging your authorization code and creating a secure session.
            </p>
          </div>
        )}

        {status === 'error' && (
          <div className="space-y-5">
            <div className="flex items-start space-x-3 p-4 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300">
              <AlertTriangle className="h-5 w-5 mt-0.5 flex-shrink-0" />
              <div className="flex-1 text-sm">
                <div className="font-medium mb-1">Sign-in failed</div>
                <div className="opacity-90 break-words">{error}</div>
              </div>
            </div>
            <div className="flex space-x-3">
              <button
                onClick={() => {
                  cognitoAuthService.beginLogin().catch((e) => {
                    setError(e instanceof Error ? e.message : 'Failed to restart sign-in.');
                  });
                }}
                className="flex-1 inline-flex items-center justify-center space-x-2 py-2 px-4 rounded-lg bg-blue-600 hover:bg-blue-700 dark:bg-[#292966] dark:hover:bg-[#333380] text-white dark:text-[#ccccff] font-medium transition-colors"
              >
                <RefreshCcw className="h-4 w-4" />
                <span>Try again</span>
              </button>
              <button
                onClick={() => navigate('/', { replace: true })}
                className="flex-1 py-2 px-4 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 font-medium transition-colors"
              >
                Back to home
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AuthCallback;

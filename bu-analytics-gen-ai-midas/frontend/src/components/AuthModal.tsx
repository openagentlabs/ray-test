/**
 * AuthModal (Cognito-redirect shim).
 *
 * The legacy username/password modal has been removed. Authentication now
 * happens via the Cognito Hosted UI (with Microsoft Entra ID federation).
 * This component is kept with the same prop signature as a thin UX shim:
 * when shown, it displays a brief "Redirecting to sign-in" notice and kicks
 * off the Cognito Authorization Code + PKCE flow via `cognitoAuthService`.
 *
 * `onLoginSuccess` is retained for backwards compatibility but is NOT invoked
 * here — the login finishes on the `/auth/callback` page after the Cognito
 * redirect, where `UserContext.initializeAuth` picks up the new session.
 */

import React, { useEffect, useRef, useState } from 'react';
import { LogIn, X, AlertTriangle, Loader2 } from 'lucide-react';
import cognitoAuthService, { CognitoConfigError } from '../services/cognitoAuthService';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLoginSuccess?: (user: unknown) => void; // retained for source-level compatibility
  initialMode?: 'login' | 'register';
  allowRegistration?: boolean;
}

const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose }) => {
  const [redirecting, setRedirecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const autoStartedRef = useRef(false);

  useEffect(() => {
    if (!isOpen) {
      autoStartedRef.current = false;
      setError(null);
      setRedirecting(false);
      return;
    }
    if (autoStartedRef.current) return;
    autoStartedRef.current = true;

    void (async () => {
      setRedirecting(true);
      setError(null);
      try {
        await cognitoAuthService.beginLogin();
        // beginLogin() triggers a full-page navigation to Cognito, so this
        // promise never actually resolves on success; the code below only
        // runs if it throws.
      } catch (e) {
        const message =
          e instanceof CognitoConfigError
            ? 'Sign-in is not configured. Please contact an administrator.'
            : e instanceof Error
              ? e.message
              : 'Failed to start sign-in.';
        setError(message);
        setRedirecting(false);
      }
    })();
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-md p-8 relative">
        <button
          onClick={onClose}
          aria-label="Close"
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="flex items-center space-x-3 mb-6">
          <div className="p-3 rounded-xl bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-300">
            <LogIn className="h-6 w-6" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Sign in</h2>
            <p className="text-sm text-gray-500 dark:text-gray-300">
              Redirecting to your organization sign-in
            </p>
          </div>
        </div>

        {error ? (
          <div className="flex items-start space-x-3 p-4 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 mb-4">
            <AlertTriangle className="h-5 w-5 mt-0.5 flex-shrink-0" />
            <div className="flex-1 text-sm">{error}</div>
          </div>
        ) : (
          <div className="flex items-center justify-center space-x-3 py-8 text-gray-600 dark:text-gray-300">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span>{redirecting ? 'Opening Cognito / Entra ID sign-in…' : 'Preparing…'}</span>
          </div>
        )}

        {error && (
          <button
            onClick={() => {
              autoStartedRef.current = false;
              setError(null);
            }}
            className="w-full py-2 px-4 rounded-lg bg-blue-600 hover:bg-blue-700 dark:bg-[#292966] dark:hover:bg-[#333380] text-white dark:text-[#ccccff] font-medium transition-colors"
          >
            Try again
          </button>
        )}
      </div>
    </div>
  );
};

export default AuthModal;

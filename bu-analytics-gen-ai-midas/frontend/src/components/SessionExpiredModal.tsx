import React, { useEffect, useState, useCallback } from 'react';
import authService from '../services/authService';
import {
  SESSION_EXPIRED_EVENT,
  buildPublicLandingHref,
  clearSessionTimerAndMeta,
  resetSessionExpiryDispatchFlag,
} from '../services/authSessionExpiry';
import { setSessionNoticeForLanding } from '../services/sessionExpired';

/**
 * Single global modal: session timer or API SESSION_EXPIRED → event → user confirms → full reload to landing.
 */
const SessionExpiredModal: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState('Session expired');

  useEffect(() => {
    const onExpired = (ev: Event) => {
      const ce = ev as CustomEvent<{ message?: string }>;
      setMessage(ce.detail?.message?.trim() || 'Session expired');
      setOpen(true);
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired as EventListener);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired as EventListener);
  }, []);

  const onConfirm = useCallback(() => {
    setOpen(false);
    setSessionNoticeForLanding(message);
    clearSessionTimerAndMeta();
    resetSessionExpiryDispatchFlag();
    authService.logout();
    try {
      window.dispatchEvent(new CustomEvent('midas:auth-changed'));
    } catch {
      /* ignore */
    }
    window.location.href = buildPublicLandingHref();
  }, [message]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/50 px-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="session-expired-title"
    >
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl dark:bg-gray-900 dark:text-gray-100">
        <h2 id="session-expired-title" className="text-lg font-semibold text-gray-900 dark:text-white">
          Session expired
        </h2>
        <p className="mt-3 text-sm text-gray-600 dark:text-gray-300">{message}</p>
        <div className="mt-6 flex justify-end">
          <button
            type="button"
            onClick={onConfirm}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            OK
          </button>
        </div>
      </div>
    </div>
  );
};

export default SessionExpiredModal;

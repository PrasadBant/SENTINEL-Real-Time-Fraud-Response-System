/**
 * SENTINEL — Authenticated Fetch Wrapper
 * =========================================
 * Every protected backend call should go through apiFetch instead of raw
 * fetch(): it attaches the stored JWT as an Authorization header and, on a
 * 401 (token missing/invalid/expired), clears the session and bounces back
 * to the login screen instead of leaving the UI silently broken.
 */

import { clearAuthGlobal, getToken } from '../roleStore';

export const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export const apiFetch = async (path, options = {}) => {
  const token = getToken();
  const headers = {
    ...(options.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    // Token missing/invalid/expired — the session is no longer valid on the
    // server, so don't leave the user staring at a UI that silently fails
    // every action. Force back to the login screen.
    clearAuthGlobal();
  }

  return res;
};

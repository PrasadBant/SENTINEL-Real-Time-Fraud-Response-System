let activeRole = localStorage.getItem('sentinel_role');
let activeToken = localStorage.getItem('sentinel_token');

export const getRole = () => activeRole;
export const getToken = () => activeToken;

/**
 * Called after a successful POST /auth/login. Stores both the JWT and the
 * role it carries, then reloads so the whole app (which reads role/token
 * as plain module state, not React state) picks up the new session.
 */
export const setAuthGlobal = (token, role) => {
  activeToken = token;
  activeRole = role;
  localStorage.setItem('sentinel_token', token);
  localStorage.setItem('sentinel_role', role);
  window.location.reload();
};

/**
 * Clears the session (logout, or a 401 from the API meaning the token
 * expired/was revoked) and reloads back to the login screen.
 */
export const clearAuthGlobal = () => {
  activeToken = null;
  activeRole = null;
  localStorage.removeItem('sentinel_token');
  localStorage.removeItem('sentinel_role');
  window.location.reload();
};

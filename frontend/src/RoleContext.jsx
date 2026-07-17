/**
 * SENTINEL — Role Context
 * ========================
 * Provides a React context so any component in the tree can access
 * the current user role without prop-drilling or ad-hoc getRole() calls.
 *
 * Usage:
 *   const { role, isAdmin, isViewer } = useRole();
 */

import React, { createContext, useContext } from 'react';
import { getRole } from './roleStore';

const RoleContext = createContext({
  role: null,
  isAdmin: false,
  isViewer: true,
});

/**
 * Wrap the authenticated portion of the app with this provider.
 * Re-reads role from localStorage on every render (stable since
 * setRoleGlobal triggers a full page reload).
 */
export const RoleProvider = ({ children }) => {
  const role = getRole();
  const isAdmin = role === 'admin';
  const isViewer = !isAdmin;

  return (
    <RoleContext.Provider value={{ role, isAdmin, isViewer }}>
      {children}
    </RoleContext.Provider>
  );
};

/**
 * Hook to consume the role context.
 * Works inside any component wrapped by <RoleProvider>.
 */
// eslint-disable-next-line react-refresh/only-export-components
export const useRole = () => {
  const ctx = useContext(RoleContext);
  return ctx;
};

export default RoleContext;

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('access_token'));
  const [roleId, setRoleId] = useState(() => {
    const saved = localStorage.getItem('auth_role_id');
    return saved ? Number(saved) : (localStorage.getItem('access_token') ? 1 : null);
  });
  const [roleName, setRoleName] = useState(() => {
    const saved = localStorage.getItem('auth_role_name');
    return saved || (localStorage.getItem('access_token') ? 'admin' : 'Unauthenticated');
  });
  const [userEmail, setUserEmail] = useState(() => localStorage.getItem('auth_user_email') || '');
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);

  const isAuthenticated = Boolean(token);

  const login = useCallback((accessToken, refreshToken, userData = {}) => {
    const items = {
      ...(accessToken && { access_token: accessToken }),
      ...(refreshToken && { refresh_token: refreshToken }),
      ...(userData.role_id && { auth_role_id: String(userData.role_id) }),
      ...(userData.role_name && { auth_role_name: userData.role_name }),
      ...(userData.email && { auth_user_email: userData.email }),
    };
    Object.entries(items).forEach(([k, v]) => localStorage.setItem(k, v));
    if (accessToken) setToken(accessToken);
    if (userData.role_id) setRoleId(Number(userData.role_id));
    if (userData.role_name) setRoleName(userData.role_name);
    if (userData.email) setUserEmail(userData.email);
  }, []);

  const logout = useCallback(() => {
    ['access_token', 'refresh_token', 'auth_role_id', 'auth_role_name', 'auth_user_email'].forEach((k) =>
      localStorage.removeItem(k)
    );
    setToken(null);
    setRoleId(null);
    setRoleName('Unauthenticated');
    setUserEmail('');
  }, []);

  useEffect(() => {
    const handleExpired = () => logout();
    if (typeof window !== 'undefined' && window.addEventListener) {
      window.addEventListener('auth:expired', handleExpired);
      return () => window.removeEventListener('auth:expired', handleExpired);
    }
  }, [logout]);

  const value = {
    token,
    roleId,
    roleName,
    userEmail,
    isAuthenticated,
    isAuthModalOpen,
    setIsAuthModalOpen,
    setRoleId,
    setRoleName,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

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
    if (accessToken) {
      localStorage.setItem('access_token', accessToken);
      setToken(accessToken);
    }
    if (refreshToken) {
      localStorage.setItem('refresh_token', refreshToken);
    }
    if (userData.role_id) {
      localStorage.setItem('auth_role_id', String(userData.role_id));
      setRoleId(Number(userData.role_id));
    }
    if (userData.role_name) {
      localStorage.setItem('auth_role_name', userData.role_name);
      setRoleName(userData.role_name);
    }
    if (userData.email) {
      localStorage.setItem('auth_user_email', userData.email);
      setUserEmail(userData.email);
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('auth_role_id');
    localStorage.removeItem('auth_role_name');
    localStorage.removeItem('auth_user_email');
    setToken(null);
    setRoleId(null);
    setRoleName('Unauthenticated');
    setUserEmail('');
  }, []);

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

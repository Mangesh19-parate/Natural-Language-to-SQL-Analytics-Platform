import React, { useState } from 'react';

export default function AuthModal({ isOpen, onClose, onAuthSuccess, currentRole = 'admin' }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const quickRoles = [
    { name: 'Admin', roleId: 1, email: 'admin@trustengine.ai', desc: 'Full Schema & Policy Access, EXPLAIN ANALYZE' },
    { name: 'Analyst', roleId: 2, email: 'analyst@trustengine.ai', desc: 'Business Tables, Aggregates, No Raw PII' },
    { name: 'Viewer', roleId: 3, email: 'viewer@trustengine.ai', desc: 'Fail-Closed Denied by Default' },
  ];

  const handleQuickSwitch = (role) => {
    // For demo/dev convenience, we allow 1-click active role switching
    localStorage.setItem('auth_role_name', role.name.toLowerCase());
    localStorage.setItem('auth_role_id', String(role.roleId));
    localStorage.setItem('auth_user_email', role.email);
    if (onAuthSuccess) {
      onAuthSuccess({
        role_name: role.name.toLowerCase(),
        role_id: role.roleId,
        email: role.email,
        full_name: `${role.name} User`,
      });
    }
    onClose();
  };

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const resData = await res.json();
      if (resData?.success) {
        const { access_token, refresh_token, user } = resData.data;
        localStorage.setItem('access_token', access_token);
        localStorage.setItem('refresh_token', refresh_token);
        localStorage.setItem('auth_role_name', user.role_name || 'viewer');
        localStorage.setItem('auth_role_id', String(user.role_id || 1));
        localStorage.setItem('auth_user_email', user.email);

        if (onAuthSuccess) {
          onAuthSuccess(user);
        }
        onClose();
      } else {
        setError(resData?.detail || resData?.message || 'Login failed');
      }
    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(5px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 2000,
      }}
    >
      <div
        style={{
          background: '#1e293b',
          border: '1px solid #475569',
          borderRadius: '16px',
          padding: '28px',
          width: '90%',
          maxWidth: '460px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.6)',
          color: '#f8fafc',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '22px' }}>🔐</span>
            <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '700' }}>Authentication &amp; Role Switcher</h3>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: '#94a3b8', fontSize: '18px', cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>

        {/* Quick Role Switcher */}
        <div style={{ marginBottom: '24px' }}>
          <div style={{ fontSize: '12px', fontWeight: '600', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '10px' }}>
            Quick Role Selection (JWT &amp; RBAC Demo)
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {quickRoles.map((qr) => (
              <button
                key={qr.roleId}
                onClick={() => handleQuickSwitch(qr)}
                style={{
                  background: currentRole.toLowerCase() === qr.name.toLowerCase() ? 'rgba(59, 130, 246, 0.2)' : '#0f172a',
                  border: currentRole.toLowerCase() === qr.name.toLowerCase() ? '1px solid #3b82f6' : '1px solid #334155',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  textAlign: 'left',
                  cursor: 'pointer',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <div>
                  <div style={{ fontSize: '14px', fontWeight: '600', color: '#f8fafc' }}>
                    {qr.name} {currentRole.toLowerCase() === qr.name.toLowerCase() && '✓'}
                  </div>
                  <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>{qr.desc}</div>
                </div>
                <span style={{ fontSize: '12px', color: '#60a5fa' }}>Select →</span>
              </button>
            ))}
          </div>
        </div>

        <div style={{ textAlign: 'center', margin: '16px 0', fontSize: '12px', color: '#64748b' }}>
          ── OR SIGN IN WITH CREDENTIALS ──
        </div>

        {/* Custom Login Form */}
        <form onSubmit={handleLoginSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {error && (
            <div style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid #ef4444', color: '#fca5a5', padding: '8px 12px', borderRadius: '6px', fontSize: '12px' }}>
              {error}
            </div>
          )}

          <div>
            <label style={{ display: 'block', fontSize: '12px', color: '#cbd5e1', marginBottom: '4px' }}>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@trustengine.ai"
              required
              style={{
                width: '100%',
                padding: '9px 12px',
                background: '#0f172a',
                border: '1px solid #334155',
                borderRadius: '6px',
                color: '#f8fafc',
                fontSize: '13px',
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '12px', color: '#cbd5e1', marginBottom: '4px' }}>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              style={{
                width: '100%',
                padding: '9px 12px',
                background: '#0f172a',
                border: '1px solid #334155',
                borderRadius: '6px',
                color: '#f8fafc',
                fontSize: '13px',
              }}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              background: '#3b82f6',
              color: '#ffffff',
              border: 'none',
              padding: '10px',
              borderRadius: '8px',
              fontSize: '14px',
              fontWeight: '600',
              cursor: 'pointer',
              marginTop: '6px',
            }}
          >
            {loading ? 'Authenticating...' : 'Sign In with JWT'}
          </button>
        </form>
      </div>
    </div>
  );
}

import React, { useState } from 'react';

import { API_BASE } from '../config';

export default function LoginPage({ onLoginSuccess, onNavigateLanding }) {
  const [email, setEmail] = useState('operator@disaster.local');
  const [password, setPassword] = useState('operator123');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage('');
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
        credentials: 'include',
      });

      const data = await res.json();
      if (!res.ok || data.status === 'error') {
        setErrorMessage(data.message || 'Invalid email or password.');
        setLoading(false);
        return;
      }

      // Success
      if (rememberMe && data.token) {
        localStorage.setItem('disaster_os_token', data.token);
        localStorage.setItem('disaster_os_user', JSON.stringify(data.user));
      } else {
        sessionStorage.setItem('disaster_os_token', data.token);
        sessionStorage.setItem('disaster_os_user', JSON.stringify(data.user));
      }

      onLoginSuccess(data.user, data.token);
    } catch (err) {
      setErrorMessage('Unable to connect to EOC authentication server. Please check backend status.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-split-container">
      {/* ── LEFT PANEL: BRANDING & OPERATIONAL IDENTITY ── */}
      <div className="login-brand-panel">
        <div className="brand-panel-header">
          <div className="brand-logo-icon" style={{ width: 34, height: 34, fontSize: 16 }}>D</div>
          <div>
            <div className="brand-title" style={{ fontSize: 18 }}>DISASTER<span style={{ color: 'var(--accent-lime)' }}>OS</span></div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.8 }}>Emergency Operations Center</div>
          </div>
        </div>

        <div className="brand-panel-body">
          <div className="op-badge op-badge-live" style={{ marginBottom: 16 }}>
            EOC SECURITY GATEWAY
          </div>
          <h1 className="brand-panel-headline">
            Emergency Operations,<br />
            Under Control.
          </h1>
          <p className="brand-panel-desc">
            Secure, encrypted access to real-time disaster intelligence feeds, 
            multi-agency response fleet coordination, live GIS telemetry, and AI decision support.
          </p>

          <div className="brand-feature-list">
            <div className="brand-feature-item">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
              <span>Real-Time USGS & GDACS Live Intelligence</span>
            </div>
            <div className="brand-feature-item">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
              <span>11-Layer Leaflet GIS Map with OSRM Roadblock Rerouting</span>
            </div>
            <div className="brand-feature-item">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
              <span>14-Agent Pipeline with Gemini Decision Support</span>
            </div>
            <div className="brand-feature-item">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
              <span>Audit-Ready Reports & Telemetry Export</span>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid var(--border-subtle)', paddingTop: 18, fontSize: 11, color: 'var(--text-muted)' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span className="pulse-dot green" />
            EOC Systems Operational
          </span>
          <span>Security Protocol v2.2.0</span>
        </div>
      </div>

      {/* ── RIGHT PANEL: AUTHENTICATION FORM ── */}
      <div className="login-form-panel">
        <div className="login-card-v2">
          <div style={{ marginBottom: 18, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <button 
              type="button" 
              onClick={onNavigateLanding}
              style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}
            >
              &larr; Back to Platform
            </button>
            <span className="brand-badge">SECURE EOC</span>
          </div>

          <div className="login-card-header">
            <h2 className="login-title">Welcome back</h2>
            <p className="login-sub">Sign in to your Emergency Operations Center.</p>
          </div>

          {errorMessage && (
            <div className="auth-error-banner">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              <span>{errorMessage}</span>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="input-group">
              <label className="input-label" htmlFor="work-email">Work Email</label>
              <input
                id="work-email"
                type="email"
                className="input-control"
                placeholder="operator@disaster.local"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="username"
              />
            </div>

            <div className="input-group" style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label className="input-label" htmlFor="work-password">Password</label>
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: 11, cursor: 'pointer' }}
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
              <input
                id="work-password"
                type={showPassword ? 'text' : 'password'}
                className="input-control"
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 22, fontSize: 12 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-secondary)', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  style={{ accentColor: 'var(--accent-lime)' }}
                />
                Remember session (24h)
              </label>
              <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>Forgot password?</span>
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', padding: '12px', fontSize: 13 }}
              disabled={loading}
            >
              {loading ? 'Authenticating...' : 'Sign In to EOC &rarr;'}
            </button>
          </form>

          <div style={{ marginTop: 24, paddingTop: 18, borderTop: '1px solid var(--border-subtle)', textAlign: 'center', fontSize: 11, color: 'var(--text-muted)' }}>
            <div style={{ marginBottom: 4 }}>
              <strong>Authorized Personnel Only</strong>
            </div>
            <div>Demo Operator: <code>operator@disaster.local</code> / <code>operator123</code></div>
          </div>
        </div>
      </div>
    </div>
  );
}

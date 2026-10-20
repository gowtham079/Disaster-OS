/**
 * Centralized API & WebSocket Configuration for Disaster OS
 *
 * Production Backend: https://disaster-os-3d9z.onrender.com
 * Production Frontend: https://disasterosmultiagentproject.vercel.app
 */

const PRODUCTION_API_BASE = 'https://disaster-os-3d9z.onrender.com';
const LOCAL_API_BASE = 'http://localhost:8000';

function resolveApiBase() {
  const envUrl = process.env.REACT_APP_API_BASE;
  if (envUrl && typeof envUrl === 'string' && envUrl.trim() !== '') {
    return envUrl.trim().replace(/\/+$/, '');
  }

  // Strictly use localhost only when explicitly running in local development
  if (
    process.env.NODE_ENV !== 'production' &&
    typeof window !== 'undefined' &&
    (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  ) {
    return LOCAL_API_BASE;
  }

  // Safe production fallback (never localhost in production)
  return PRODUCTION_API_BASE;
}

export const API_BASE = resolveApiBase();

/**
 * Derives a reliable WebSocket URL (ws:// or wss://) from API_BASE
 */
export function getWebSocketUrl(path = '/ws/simulation') {
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  const base = API_BASE.replace(/\/+$/, '');

  if (base.startsWith('https://')) {
    return base.replace(/^https:\/\//i, 'wss://') + cleanPath;
  }
  if (base.startsWith('http://')) {
    return base.replace(/^http:\/\//i, 'ws://') + cleanPath;
  }

  const protocol = (typeof window !== 'undefined' && window.location.protocol === 'https:') ? 'wss:' : 'ws:';
  const host = (typeof window !== 'undefined' && window.location.host) || 'disaster-os-3d9z.onrender.com';
  return `${protocol}//${host}${cleanPath}`;
}

/**
 * Helper to retrieve stored session token from storage
 */
export function getStoredToken() {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem('disaster_os_token') || sessionStorage.getItem('disaster_os_token') || '';
}

/**
 * Standard authenticated headers helper.
 * Ensures no duplicate Content-Type or Authorization headers are created.
 */
export function getAuthHeaders(extraHeaders = {}) {
  const token = getStoredToken();
  const headers = {};

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  return {
    ...headers,
    ...extraHeaders,
  };
}

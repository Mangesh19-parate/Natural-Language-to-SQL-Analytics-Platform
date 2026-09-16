/**
 * Centralized API client with JWT Bearer token and Correlation ID injection.
 */

export function getAuthHeaders(extraHeaders = {}) {
  const token = localStorage.getItem('access_token');
  const headers = {
    'Content-Type': 'application/json',
    ...extraHeaders,
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  return headers;
}

export async function apiFetch(url, options = {}) {
  const headers = getAuthHeaders(options.headers || {});
  const config = {
    ...options,
    headers,
  };

  const response = await fetch(url, config);

  if (response.status === 401) {
    // If unauthorized, token might be expired
    console.warn(`[API] 401 Unauthorized at ${url}`);
  }

  return response;
}

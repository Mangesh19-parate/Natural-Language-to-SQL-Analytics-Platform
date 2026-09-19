/**
 * Centralized API client with JWT Bearer token, Correlation ID, and automatic token refresh on 401.
 */

let isRefreshing = false;
let refreshSubscribers = [];

function subscribeTokenRefresh(cb) {
  refreshSubscribers.push(cb);
}

function onRefreshed(token) {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
}

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
  const { timeoutMs = 30000, ...fetchOptions } = options;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  const headers = getAuthHeaders(fetchOptions.headers || {});
  const config = {
    ...fetchOptions,
    signal: fetchOptions.signal || controller.signal,
    headers,
  };

  try {
    let response = await fetch(url, config);
    clearTimeout(timeoutId);

    // If 401 Unauthorized, attempt token refresh if refresh_token is present
    if (response.status === 401 && !url.includes('/api/auth/refresh') && !url.includes('/api/auth/login')) {
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        if (!isRefreshing) {
          isRefreshing = true;
          try {
            const refreshRes = await fetch('/api/auth/refresh', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ refresh_token: refreshToken }),
            });
            const refreshData = await refreshRes.json();
            if (refreshData?.success && refreshData?.data?.access_token) {
              const newAccessToken = refreshData.data.access_token;
              localStorage.setItem('access_token', newAccessToken);
              if (refreshData.data.refresh_token) {
                localStorage.setItem('refresh_token', refreshData.data.refresh_token);
              }
              onRefreshed(newAccessToken);
            } else {
              localStorage.removeItem('access_token');
              localStorage.removeItem('refresh_token');
              onRefreshed(null);
            }
          } catch (e) {
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            onRefreshed(null);
          } finally {
            isRefreshing = false;
          }
        }

        // Retry original request with new token
        const retryPromise = new Promise((resolve) => {
          subscribeTokenRefresh((newToken) => {
            if (newToken) {
              const retryHeaders = {
                ...config.headers,
                Authorization: `Bearer ${newToken}`,
              };
              resolve(fetch(url, { ...config, headers: retryHeaders }));
            } else {
              resolve(response);
            }
          });
        });
        return await retryPromise;
      }
    }

    return response;
  } catch (err) {
    clearTimeout(timeoutId);
    throw err;
  }
}

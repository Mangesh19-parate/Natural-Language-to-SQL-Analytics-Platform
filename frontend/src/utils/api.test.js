import test from 'node:test';
import assert from 'node:assert/strict';
import { apiFetch, getAuthHeaders } from './api.js';

// Setup minimal in-memory localStorage mock for Node environment
const storage = {};
globalThis.localStorage = {
  getItem: (key) => (key in storage ? storage[key] : null),
  setItem: (key, val) => { storage[key] = String(val); },
  removeItem: (key) => { delete storage[key]; },
  clear: () => { Object.keys(storage).forEach((k) => delete storage[k]); },
};

test('getAuthHeaders injects Bearer token when present', () => {
  localStorage.clear();
  localStorage.setItem('access_token', 'test_access_jwt_123');
  const headers = getAuthHeaders();
  assert.equal(headers['Authorization'], 'Bearer test_access_jwt_123');
  assert.equal(headers['Content-Type'], 'application/json');
});

test('apiFetch automatically refreshes on 401 and retries with new token', async () => {
  localStorage.clear();
  localStorage.setItem('access_token', 'expired_token');
  localStorage.setItem('refresh_token', 'valid_refresh_token');

  let refreshCallCount = 0;
  let protectedCallCount = 0;

  // Mock global fetch
  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/auth/refresh') {
      refreshCallCount++;
      return {
        status: 200,
        json: async () => ({
          success: true,
          data: {
            access_token: 'brand_new_access_jwt',
            refresh_token: 'rotated_refresh_jwt',
          },
        }),
      };
    }

    if (url === '/api/protected') {
      protectedCallCount++;
      const authHeader = options?.headers?.['Authorization'] || '';
      if (authHeader === 'Bearer expired_token') {
        return { status: 401, json: async () => ({ error: 'Token expired' }) };
      }
      if (authHeader === 'Bearer brand_new_access_jwt') {
        return { status: 200, json: async () => ({ data: 'protected_resource' }) };
      }
    }

    return { status: 404, json: async () => ({}) };
  };

  const res = await apiFetch('/api/protected');
  const data = await res.json();

  assert.equal(res.status, 200);
  assert.equal(data.data, 'protected_resource');
  assert.equal(refreshCallCount, 1);
  assert.equal(protectedCallCount, 2);
  assert.equal(localStorage.getItem('access_token'), 'brand_new_access_jwt');
});

test('5 simultaneous requests -> 5x401 -> ONE refresh -> 5 successful retries', async () => {
  localStorage.clear();
  localStorage.setItem('access_token', 'expired_token');
  localStorage.setItem('refresh_token', 'valid_refresh_token');

  let refreshCallCount = 0;
  let protectedCallCount = 0;

  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/auth/refresh') {
      refreshCallCount++;
      await new Promise((resolve) => setTimeout(resolve, 15));
      return {
        status: 200,
        json: async () => ({
          success: true,
          data: { access_token: 'coalesced_five_token' },
        }),
      };
    }

    if (url === '/api/resource') {
      protectedCallCount++;
      const authHeader = options?.headers?.['Authorization'] || '';
      if (authHeader === 'Bearer expired_token') {
        return { status: 401, json: async () => ({ error: 'Expired' }) };
      }
      if (authHeader === 'Bearer coalesced_five_token') {
        return { status: 200, json: async () => ({ data: 'success' }) };
      }
    }

    return { status: 404, json: async () => ({}) };
  };

  const results = await Promise.all([
    apiFetch('/api/resource'),
    apiFetch('/api/resource'),
    apiFetch('/api/resource'),
    apiFetch('/api/resource'),
    apiFetch('/api/resource'),
  ]);

  for (const res of results) {
    assert.equal(res.status, 200);
  }

  assert.equal(refreshCallCount, 1);
  assert.equal(protectedCallCount, 10);
  assert.equal(localStorage.getItem('access_token'), 'coalesced_five_token');
});

test('refresh fails -> access and refresh tokens are purged immediately from storage', async () => {
  localStorage.clear();
  localStorage.setItem('access_token', 'expired_token');
  localStorage.setItem('refresh_token', 'revoked_refresh_token');

  let refreshCalled = false;

  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/auth/refresh') {
      refreshCalled = true;
      return {
        status: 401,
        json: async () => ({ success: false, detail: 'Invalid refresh token' }),
      };
    }

    if (url === '/api/resource') {
      return { status: 401, json: async () => ({ error: 'Unauthorized' }) };
    }

    return { status: 404, json: async () => ({}) };
  };

  const res = await apiFetch('/api/resource');

  assert.equal(res.status, 401);
  assert.equal(refreshCalled, true);
  assert.equal(localStorage.getItem('access_token'), null);
  assert.equal(localStorage.getItem('refresh_token'), null);
});


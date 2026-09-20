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

test('concurrent 401s coalesce into a single refresh request without deadlock', async () => {
  localStorage.clear();
  localStorage.setItem('access_token', 'expired_token');
  localStorage.setItem('refresh_token', 'valid_refresh_token');

  let refreshCallCount = 0;
  let protectedCallCount = 0;

  globalThis.fetch = async (url, options = {}) => {
    if (url === '/api/auth/refresh') {
      refreshCallCount++;
      // Simulate network delay
      await new Promise((resolve) => setTimeout(resolve, 20));
      return {
        status: 200,
        json: async () => ({
          success: true,
          data: { access_token: 'coalesced_new_token' },
        }),
      };
    }

    if (url === '/api/resource') {
      protectedCallCount++;
      const authHeader = options?.headers?.['Authorization'] || '';
      if (authHeader === 'Bearer expired_token') {
        return { status: 401, json: async () => ({ error: 'Expired' }) };
      }
      if (authHeader === 'Bearer coalesced_new_token') {
        return { status: 200, json: async () => ({ data: 'success' }) };
      }
    }

    return { status: 404, json: async () => ({}) };
  };

  // Launch 3 simultaneous requests that all receive initial 401
  const [res1, res2, res3] = await Promise.all([
    apiFetch('/api/resource'),
    apiFetch('/api/resource'),
    apiFetch('/api/resource'),
  ]);

  assert.equal(res1.status, 200);
  assert.equal(res2.status, 200);
  assert.equal(res3.status, 200);

  // Exactly 1 refresh should have occurred
  assert.equal(refreshCallCount, 1);
  // 3 initial failing + 3 retried = 6 calls
  assert.equal(protectedCallCount, 6);
  assert.equal(localStorage.getItem('access_token'), 'coalesced_new_token');
});

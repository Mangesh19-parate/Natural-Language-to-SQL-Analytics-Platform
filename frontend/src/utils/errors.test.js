import test from 'node:test';
import assert from 'node:assert/strict';
import { ApiError, parseApiResponse } from './errors.js';

test('parseApiResponse returns JSON payload on 200 OK', async () => {
  const mockRes = {
    ok: true,
    status: 200,
    json: async () => ({ success: true, data: { items: [1, 2, 3] } }),
  };
  const data = await parseApiResponse(mockRes);
  assert.equal(data.success, true);
  assert.equal(data.data.items.length, 3);
});

test('parseApiResponse throws structured ApiError on 403 Forbidden with custom detail', async () => {
  const mockRes = {
    ok: false,
    status: 403,
    json: async () => ({ detail: 'Access denied: Role analyst is not authorized to data source 2' }),
  };

  await assert.rejects(
    async () => parseApiResponse(mockRes),
    (err) => {
      assert(err instanceof ApiError);
      assert.equal(err.status, 403);
      assert.equal(err.code, 'FORBIDDEN');
      assert.match(err.message, /Access denied/);
      return true;
    }
  );
});

test('parseApiResponse handles non-JSON server error gracefully with 500 status', async () => {
  const mockRes = {
    ok: false,
    status: 502,
    json: async () => { throw new Error('Invalid JSON'); },
  };

  await assert.rejects(
    async () => parseApiResponse(mockRes),
    (err) => {
      assert(err instanceof ApiError);
      assert.equal(err.status, 502);
      assert.equal(err.message, 'HTTP 502 Request Failed');
      return true;
    }
  );
});

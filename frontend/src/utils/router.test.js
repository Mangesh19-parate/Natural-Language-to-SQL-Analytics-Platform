import { test } from 'node:test';
import assert from 'node:assert';
import { parseHashRoute, formatHashRoute } from './router.js';

test('parseHashRoute defaults to workspace when empty or root', () => {
  assert.deepStrictEqual(parseHashRoute(''), { view: 'workspace', params: {} });
  assert.deepStrictEqual(parseHashRoute('#'), { view: 'workspace', params: {} });
  assert.deepStrictEqual(parseHashRoute('#/'), { view: 'workspace', params: {} });
});

test('parseHashRoute parses standard top-level views', () => {
  const views = [
    'workspace',
    'planner',
    'history',
    'governance',
    'performance',
    'security',
    'evaluation',
    'observatory',
  ];

  for (const v of views) {
    assert.deepStrictEqual(parseHashRoute(`#/${v}`), { view: v, params: {} });
    assert.deepStrictEqual(parseHashRoute(`#${v}`), { view: v, params: {} });
  }
});

test('parseHashRoute parses dynamic replay route with queryId parameter', () => {
  const route = parseHashRoute('#/replay/42');
  assert.deepStrictEqual(route, {
    view: 'replay',
    params: { queryId: '42' },
  });
});

test('parseHashRoute fallbacks to workspace for unrecognized routes', () => {
  const route = parseHashRoute('#/unknown-route-xyz');
  assert.deepStrictEqual(route, { view: 'workspace', params: {} });
});

test('formatHashRoute formats views and parameterized replay correctly', () => {
  assert.strictEqual(formatHashRoute('workspace'), '#/workspace');
  assert.strictEqual(formatHashRoute('observatory'), '#/observatory');
  assert.strictEqual(formatHashRoute('replay', { queryId: '105' }), '#/replay/105');
});

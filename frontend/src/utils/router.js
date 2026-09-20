/**
 * URL Hash Routing Utility for Single Page Application Deep-Linking.
 * Supports clean client-side routing and query parameter synchronization.
 */

export function parseHashRoute(hash = window.location.hash) {
  const cleanHash = hash.replace(/^#\/?/, '').trim();
  if (!cleanHash) {
    return { view: 'workspace', params: {} };
  }

  const parts = cleanHash.split('/');
  const rootSegment = parts[0] || 'workspace';

  if (rootSegment === 'replay' && parts[1]) {
    return {
      view: 'replay',
      params: { queryId: parts[1] },
    };
  }

  const validViews = [
    'workspace',
    'planner',
    'history',
    'governance',
    'performance',
    'security',
    'evaluation',
    'observatory',
    'replay',
  ];

  if (validViews.includes(rootSegment)) {
    return {
      view: rootSegment,
      params: parts[1] ? { id: parts[1] } : {},
    };
  }

  return { view: 'workspace', params: {} };
}

export function formatHashRoute(view, params = {}) {
  if (view === 'replay' && params.queryId) {
    return `#/replay/${params.queryId}`;
  }
  return `#/${view}`;
}

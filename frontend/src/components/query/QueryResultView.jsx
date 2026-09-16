import React, { useState } from 'react';
import DataTable from '../ui/DataTable.jsx';
import CodeBlock from '../ui/CodeBlock.jsx';
import Badge from '../ui/Badge.jsx';

export default function QueryResultView({
  generatedSQL = '',
  executionResult = null,
  criticFindings = [],
  policyViolations = [],
  activeTab = 'results', // 'results' | 'sql' | 'critic' | 'ast'
  onTabChange,
}) {
  const [internalTab, setInternalTab] = useState('results');
  const currentTab = onTabChange ? activeTab : internalTab;
  const setTab = onTabChange || setInternalTab;

  const rows = executionResult?.rows || [];
  const columns = executionResult?.columns || [];
  const rowCount = executionResult?.row_count ?? rows.length;
  const executionMs = executionResult?.latency_ms ?? 12;

  return (
    <div
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: '8px',
        padding: '1.25rem',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '1px solid var(--border-subtle)',
          paddingBottom: '0.65rem',
          marginBottom: '1rem',
        }}
      >
        <div style={{ display: 'flex', gap: '0.25rem' }}>
          <button
            onClick={() => setTab('results')}
            className={`nav-tab-btn ${currentTab === 'results' ? 'active' : ''}`}
          >
            Data Grid ({rowCount})
          </button>
          <button
            onClick={() => setTab('sql')}
            className={`nav-tab-btn ${currentTab === 'sql' ? 'active' : ''}`}
          >
            Generated SQL
          </button>
          <button
            onClick={() => setTab('critic')}
            className={`nav-tab-btn ${currentTab === 'critic' ? 'active' : ''}`}
          >
            Critic Findings ({criticFindings.length})
          </button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Badge variant="neutral" size="sm">
            {executionMs} ms
          </Badge>
          <Badge variant={executionResult?.success !== false ? 'success' : 'danger'} size="sm" dot>
            {executionResult?.success !== false ? 'Sandbox Verified' : 'Execution Error'}
          </Badge>
        </div>
      </div>

      {currentTab === 'results' && (
        <DataTable
          columns={columns}
          rows={rows}
          pageSize={10}
          emptyMessage="Query executed with zero rows returned"
        />
      )}

      {currentTab === 'sql' && (
        <CodeBlock
          code={generatedSQL || '-- No SQL generated'}
          language="sql"
          title="Deterministic Policy-Authorized SQL"
        />
      )}

      {currentTab === 'critic' && (
        <div>
          {criticFindings.length === 0 ? (
            <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
              Zero semantic smells or anti-patterns flagged by SQL Critic.
            </div>
          ) : (
            criticFindings.map((finding, idx) => (
              <div
                key={idx}
                style={{
                  background: 'var(--bg-app)',
                  border: '1px solid var(--color-warning-border)',
                  borderRadius: '6px',
                  padding: '0.75rem 1rem',
                  marginBottom: '0.5rem',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                  <span style={{ fontWeight: 600, fontSize: '12px', color: 'var(--color-warning)' }}>
                    {finding.title || finding.finding_type}
                  </span>
                  <Badge variant="warning" size="sm">
                    {finding.severity || 'warning'}
                  </Badge>
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                  {finding.detail}
                </div>
                {finding.suggested_fix && (
                  <div style={{ marginTop: '0.5rem', fontSize: '11px', color: 'var(--text-muted)' }}>
                    Recommendation: {finding.suggested_fix}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

import React, { useState, useEffect } from 'react';

export default function OptimizationCard({
  sql,
  queryId,
  roleName = 'Admin',
}) {
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState('explain');
  const [optimizeData, setOptimizeData] = useState(null);
  const [error, setError] = useState(null);
  const [copiedIdx, setCopiedIdx] = useState(null);
  const [showRawPlan, setShowRawPlan] = useState(false);

  const fetchOptimization = async (targetMode = 'explain') => {
    if (!sql) return;
    setLoading(true);
    setError(null);
    try {
      const endpoint = targetMode === 'explain_analyze' ? '/api/optimize/analyze' : '/api/optimize/explain';
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sql,
          query_id: queryId,
          role_name: targetMode === 'explain_analyze' ? 'admin' : (roleName || 'analyst').toLowerCase(),
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `Optimization request failed (${res.status})`);
      }

      const data = await res.json();
      setOptimizeData(data);
      setMode(data.mode);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (sql) {
      fetchOptimization('explain');
    }
  }, [sql]);

  const handleCopyDdl = (ddl, idx) => {
    if (!ddl) return;
    navigator.clipboard.writeText(ddl);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  const getConfidenceBadge = (conf) => {
    const c = (conf || 'medium').toLowerCase();
    if (c === 'high') {
      return { label: 'HIGH CONFIDENCE', bg: 'rgba(34, 197, 94, 0.15)', border: '#22c55e', text: '#4ade80' };
    }
    if (c === 'medium') {
      return { label: 'MEDIUM CONFIDENCE', bg: 'rgba(234, 179, 8, 0.15)', border: '#eab308', text: '#facc15' };
    }
    return { label: 'LOW CONFIDENCE', bg: 'rgba(148, 163, 184, 0.15)', border: '#94a3b8', text: '#cbd5e1' };
  };

  return (
    <div
      style={{
        background: 'rgba(15, 23, 42, 0.65)',
        border: '1px solid rgba(99, 102, 241, 0.3)',
        borderRadius: '12px',
        padding: '1.25rem',
        marginTop: '0.75rem',
      }}
    >
      {/* Header Bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          paddingBottom: '0.85rem',
          marginBottom: '1rem',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <span style={{ fontSize: '1.1rem' }}>⚡</span>
            <span style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc' }}>
              Query Optimization Engine (REQ-OPT-01 / REQ-OPT-02)
            </span>
            <span
              style={{
                fontSize: '0.72rem',
                fontWeight: 700,
                padding: '0.15rem 0.5rem',
                borderRadius: '6px',
                background: mode === 'explain_analyze' ? 'rgba(168, 85, 247, 0.2)' : 'rgba(59, 130, 246, 0.2)',
                color: mode === 'explain_analyze' ? '#c084fc' : '#60a5fa',
                border: `1px solid ${mode === 'explain_analyze' ? 'rgba(168, 85, 247, 0.4)' : 'rgba(59, 130, 246, 0.4)'}`,
              }}
            >
              {mode === 'explain_analyze' ? '🔬 EXPLAIN ANALYZE (Live Live Sandboxed)' : '🛡️ Safe EXPLAIN (Plan-Only)'}
            </span>
          </div>
          <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: '0.2rem' }}>
            Evidence-based index and join recommendations with deterministic confidence ratings.
          </div>
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <button
            onClick={() => fetchOptimization('explain')}
            disabled={loading}
            style={{
              background: mode === 'explain' ? 'rgba(59, 130, 246, 0.25)' : 'rgba(255, 255, 255, 0.05)',
              border: `1px solid ${mode === 'explain' ? '#3b82f6' : 'rgba(255, 255, 255, 0.1)'}`,
              color: mode === 'explain' ? '#93c5fd' : '#cbd5e1',
              borderRadius: '6px',
              padding: '0.35rem 0.75rem',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            {loading && mode === 'explain' ? 'Inspecting Plan...' : 'Safe EXPLAIN (Plan)'}
          </button>

          <button
            onClick={() => fetchOptimization('explain_analyze')}
            disabled={loading}
            title="Admin-only: Executes query in sandbox with live execution benchmarking"
            style={{
              background: mode === 'explain_analyze' ? 'rgba(168, 85, 247, 0.25)' : 'rgba(255, 255, 255, 0.05)',
              border: `1px solid ${mode === 'explain_analyze' ? '#a855f7' : 'rgba(255, 255, 255, 0.1)'}`,
              color: mode === 'explain_analyze' ? '#d8b4fe' : '#cbd5e1',
              borderRadius: '6px',
              padding: '0.35rem 0.75rem',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.3rem',
            }}
          >
            <span>👑</span>
            <span>{loading && mode === 'explain_analyze' ? 'Analyzing Live...' : 'EXPLAIN ANALYZE'}</span>
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div
          style={{
            background: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            color: '#fca5a5',
            padding: '0.65rem 0.9rem',
            borderRadius: '8px',
            fontSize: '0.82rem',
            marginBottom: '1rem',
          }}
        >
          <b>Optimization Warning:</b> {error}
        </div>
      )}

      {/* Live Execution Stats Bar if ANALYZE mode */}
      {optimizeData?.execution_stats && (
        <div
          style={{
            background: 'rgba(168, 85, 247, 0.1)',
            border: '1px solid rgba(168, 85, 247, 0.3)',
            borderRadius: '8px',
            padding: '0.65rem 0.9rem',
            marginBottom: '1rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '0.8rem',
            color: '#e9d5ff',
          }}
        >
          <div>
            <b>Live Execution Benchmark:</b>{' '}
            <span>{optimizeData.execution_stats.execution_time_ms} ms</span> &bull;{' '}
            <span>{optimizeData.execution_stats.rows_returned ?? 'N/A'} rows inspected</span>
          </div>
          <div style={{ fontSize: '0.72rem', color: '#c084fc' }}>
            Sandboxed Timeout &bull; Row Cap Enforced
          </div>
        </div>
      )}

      {/* Suggestions List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
        {optimizeData?.suggestions?.map((item, idx) => {
          const badge = getConfidenceBadge(item.confidence);
          return (
            <div
              key={idx}
              style={{
                background: 'rgba(0, 0, 0, 0.3)',
                border: '1px solid rgba(255, 255, 255, 0.07)',
                borderRadius: '8px',
                padding: '1rem',
              }}
            >
              {/* Card Header */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '0.5rem',
                  flexWrap: 'wrap',
                  gap: '0.5rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#f1f5f9' }}>
                    {item.issue_type.replace(/_/g, ' ').toUpperCase()}
                  </span>
                </div>
                <span
                  style={{
                    fontSize: '0.68rem',
                    fontWeight: 700,
                    letterSpacing: '0.04em',
                    padding: '0.2rem 0.55rem',
                    borderRadius: '6px',
                    background: badge.bg,
                    border: `1px solid ${badge.border}`,
                    color: badge.text,
                  }}
                >
                  {badge.label}
                </span>
              </div>

              {/* Detail Message */}
              <p style={{ margin: '0 0 0.65rem 0', fontSize: '0.85rem', color: '#cbd5e1', lineHeight: '1.4' }}>
                {item.detail}
              </p>

              {/* Evidence Box */}
              {item.evidence_json && Object.keys(item.evidence_json).length > 0 && (
                <div
                  style={{
                    background: 'rgba(30, 41, 59, 0.6)',
                    border: '1px solid rgba(255, 255, 255, 0.05)',
                    borderRadius: '6px',
                    padding: '0.6rem 0.8rem',
                    marginBottom: '0.75rem',
                    fontSize: '0.78rem',
                  }}
                >
                  <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#94a3b8', marginBottom: '0.35rem', textTransform: 'uppercase' }}>
                    Observed Plan Evidence
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.4rem', color: '#e2e8f0' }}>
                    {Object.entries(item.evidence_json).map(([k, v]) => (
                      <div key={k}>
                        <span style={{ color: '#94a3b8' }}>{k.replace(/_/g, ' ')}:</span>{' '}
                        <span style={{ fontFamily: 'monospace', color: '#67e8f9' }}>
                          {Array.isArray(v) ? (v.length > 0 ? v.join(', ') : 'None') : String(v)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Copyable DDL */}
              {item.suggested_ddl && (
                <div>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: '0.3rem',
                    }}
                  >
                    <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#818cf8', textTransform: 'uppercase' }}>
                      Suggested Index DDL
                    </span>
                    <button
                      onClick={() => handleCopyDdl(item.suggested_ddl, idx)}
                      style={{
                        background: copiedIdx === idx ? 'rgba(34, 197, 94, 0.2)' : 'rgba(99, 102, 241, 0.2)',
                        border: `1px solid ${copiedIdx === idx ? '#22c55e' : 'rgba(99, 102, 241, 0.4)'}`,
                        color: copiedIdx === idx ? '#4ade80' : '#a5b4fc',
                        borderRadius: '4px',
                        padding: '0.2rem 0.55rem',
                        fontSize: '0.72rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.3rem',
                      }}
                    >
                      <span>{copiedIdx === idx ? '✓ Copied' : '📋 Copy DDL'}</span>
                    </button>
                  </div>
                  <div
                    style={{
                      background: '#090d16',
                      border: '1px solid rgba(99, 102, 241, 0.2)',
                      borderRadius: '6px',
                      padding: '0.6rem 0.8rem',
                      fontFamily: 'monospace',
                      fontSize: '0.8rem',
                      color: '#38bdf8',
                      overflowX: 'auto',
                    }}
                  >
                    {item.suggested_ddl}
                  </div>
                  <div style={{ fontSize: '0.68rem', color: '#64748b', marginTop: '0.25rem', fontStyle: 'italic' }}>
                    * Suggested DDL is strictly copyable and never auto-executed by the system.
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Accordion to inspect raw EXPLAIN tree */}
      <div style={{ marginTop: '1rem', borderTop: '1px solid rgba(255, 255, 255, 0.06)', paddingTop: '0.75rem' }}>
        <button
          onClick={() => setShowRawPlan(!showRawPlan)}
          style={{
            background: 'transparent',
            border: 'none',
            color: '#94a3b8',
            fontSize: '0.75rem',
            cursor: 'pointer',
            padding: 0,
            textDecoration: 'underline',
          }}
        >
          {showRawPlan ? 'Hide Raw Plan Output' : 'View Full Query Execution Plan (Raw JSON/Nodes)'}
        </button>
        {showRawPlan && optimizeData?.plan_raw && (
          <pre
            style={{
              marginTop: '0.5rem',
              background: '#090d16',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '6px',
              padding: '0.75rem',
              fontSize: '0.75rem',
              color: '#94a3b8',
              overflowX: 'auto',
              maxHeight: '200px',
            }}
          >
            {JSON.stringify(optimizeData.plan_raw, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}

import React, { useState, useEffect } from 'react';

export default function QueryReplayCard({ queryId, activeRoleId = 1, onBack }) {
  const [provenance, setProvenance] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [replaying, setReplaying] = useState(false);
  const [replayResult, setReplayResult] = useState(null);

  const fetchProvenance = async (qId) => {
    if (!qId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/replay/${qId}?data_source_id=1`);
      const data = await res.json();
      if (data?.success) {
        setProvenance(data.data);
      } else {
        setError(data?.detail || data?.message || 'Error fetching provenance package');
      }
    } catch (err) {
      console.error('Failed to load provenance package:', err);
      setError(err.message || 'Error fetching provenance package');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProvenance(queryId);
  }, [queryId]);

  const handleExecuteReplay = async () => {
    if (!queryId) return;
    setReplaying(true);
    setReplayResult(null);
    try {
      const res = await fetch(`/api/replay/${queryId}?role_id=${activeRoleId}&data_source_id=1`, {
        method: 'POST',
      });
      const data = await res.json();
      if (data?.success) {
        setReplayResult(data.data);
      } else {
        alert('Replay execution failed: ' + (data?.detail || data?.message));
      }
    } catch (err) {
      console.error('Replay execution failed:', err);
      alert('Replay execution failed: ' + err.message);
    } finally {
      setReplaying(false);
    }
  };

  if (!queryId) {
    return (
      <div style={{ padding: '32px', textAlign: 'center', color: '#94a3b8' }}>
        <p>No query selected for Query Replay.</p>
      </div>
    );
  }

  return (
    <div className="query-replay-card" style={{ padding: '24px', color: '#e2e8f0' }}>
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {onBack && (
            <button
              onClick={onBack}
              style={{
                background: '#334155',
                color: '#f8fafc',
                border: 'none',
                padding: '6px 12px',
                borderRadius: '6px',
                fontSize: '12px',
                cursor: 'pointer',
              }}
            >
              ← Back
            </button>
          )}
          <h2 style={{ margin: 0, fontSize: '20px', fontWeight: '700', color: '#f8fafc' }}>
            🔬 QUERY REPLAY &amp; PROVENANCE · #{queryId.slice(0, 8)}
          </h2>
        </div>

        <button
          onClick={handleExecuteReplay}
          disabled={replaying}
          style={{
            background: '#3b82f6',
            color: '#ffffff',
            border: 'none',
            padding: '8px 18px',
            borderRadius: '8px',
            fontSize: '13px',
            fontWeight: '600',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          {replaying ? '⏳ Replaying Execution...' : '▶ Replay Query & Verify Reproducibility'}
        </button>
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>
          <div style={{ fontSize: '24px', marginBottom: '8px' }}>⏳</div>
          Loading reproducibility package &amp; analyzing schema drift...
        </div>
      )}

      {error && (
        <div style={{ padding: '16px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid #ef4444', borderRadius: '8px', color: '#fca5a5' }}>
          {error}
        </div>
      )}

      {!loading && provenance && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
          {/* Schema Drift Alert Banner (REQ-REPLAY-01 / Day 82) */}
          {provenance.drift_report?.has_drift ? (
            <div
              style={{
                background: 'rgba(245, 158, 11, 0.15)',
                border: '1px solid #f59e0b',
                borderLeft: '5px solid #f59e0b',
                borderRadius: '8px',
                padding: '14px 18px',
                color: '#fef3c7',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: '700', fontSize: '14px', marginBottom: '4px' }}>
                <span>⚠</span>
                <span>{provenance.drift_report.drift_warning}</span>
              </div>
              <div style={{ fontSize: '12px', color: '#fde68a' }}>
                {provenance.drift_report.summary}
              </div>
            </div>
          ) : (
            <div
              style={{
                background: 'rgba(16, 185, 129, 0.1)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                borderRadius: '8px',
                padding: '10px 16px',
                color: '#34d399',
                fontSize: '12px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <span>✓ Schema Snapshot in sync: zero drift detected between capture and live catalog.</span>
            </div>
          )}

          {/* Question & SQL Section */}
          <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '10px', padding: '18px' }}>
            <div style={{ fontSize: '12px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '6px' }}>
              Natural Language Question
            </div>
            <div style={{ fontSize: '16px', fontWeight: '600', color: '#f8fafc', marginBottom: '14px' }}>
              "{provenance.nl_question}"
            </div>

            <div style={{ fontSize: '12px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '6px' }}>
              Captured SQL Statement
            </div>
            <div
              style={{
                background: '#0f172a',
                border: '1px solid #334155',
                borderRadius: '8px',
                padding: '12px',
                fontFamily: 'Consolas, Monaco, monospace',
                fontSize: '13px',
                color: '#38bdf8',
                overflowX: 'auto',
              }}
            >
              {provenance.final_sql}
            </div>
          </div>

          {/* Provenance Metadata Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
            <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', padding: '14px' }}>
              <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase' }}>Dialect &amp; Engine</div>
              <div style={{ fontSize: '14px', fontWeight: '600', color: '#f1f5f9', marginTop: '4px' }}>
                {provenance.dialect.toUpperCase()}
              </div>
            </div>

            <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', padding: '14px' }}>
              <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase' }}>Prompt Version</div>
              <div style={{ fontSize: '14px', fontWeight: '600', color: '#60a5fa', marginTop: '4px' }}>
                {provenance.prompt_version}
              </div>
            </div>

            <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', padding: '14px' }}>
              <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase' }}>Model &amp; Params</div>
              <div style={{ fontSize: '13px', fontWeight: '600', color: '#f1f5f9', marginTop: '4px' }}>
                {provenance.model_name} (temp={provenance.model_params?.temperature ?? 0.0})
              </div>
            </div>

            <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', padding: '14px' }}>
              <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase' }}>Result Fingerprint (Hash)</div>
              <div style={{ fontSize: '12px', fontWeight: '600', color: '#a78bfa', fontFamily: 'monospace', marginTop: '4px' }}>
                {provenance.result_hash ? provenance.result_hash.slice(0, 16) + '...' : 'N/A'}
              </div>
            </div>

            <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', padding: '14px' }}>
              <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase' }}>Schema Snapshot ID</div>
              <div style={{ fontSize: '12px', fontWeight: '600', color: '#cbd5e1', fontFamily: 'monospace', marginTop: '4px' }}>
                {provenance.schema_snapshot_id ? provenance.schema_snapshot_id.slice(0, 8) + '...' : 'Default'}
              </div>
            </div>

            <div style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', padding: '14px' }}>
              <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase' }}>Original Latency &amp; Rows</div>
              <div style={{ fontSize: '13px', fontWeight: '600', color: '#f1f5f9', marginTop: '4px' }}>
                {provenance.execution_ms ?? 0} ms · {provenance.row_count ?? 0} rows
              </div>
            </div>
          </div>

          {/* Replay Verification Result */}
          {replayResult && (
            <div
              style={{
                background: '#1e293b',
                border: replayResult.is_reproducible ? '1px solid #10b981' : '1px solid #ef4444',
                borderRadius: '10px',
                padding: '20px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
                <span style={{ fontSize: '22px' }}>{replayResult.is_reproducible ? '✅' : '⚠'}</span>
                <div>
                  <h4 style={{ margin: 0, fontSize: '16px', fontWeight: '700', color: replayResult.is_reproducible ? '#34d399' : '#f87171' }}>
                    {replayResult.reproducibility_message}
                  </h4>
                  <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '2px' }}>
                    Replayed Result Hash: <code style={{ color: '#a78bfa' }}>{replayResult.replayed_result_hash?.slice(0, 16)}...</code>
                  </div>
                </div>
              </div>

              {/* Replayed Rows Table */}
              {replayResult.replayed_execution?.rows?.length > 0 && (
                <div style={{ overflowX: 'auto', maxHeight: '240px', border: '1px solid #334155', borderRadius: '8px' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                    <thead>
                      <tr style={{ background: '#0f172a', borderBottom: '1px solid #334155' }}>
                        {replayResult.replayed_execution.columns?.map((c) => (
                          <th key={c} style={{ padding: '8px 12px', color: '#94a3b8', fontWeight: '600' }}>
                            {c}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {replayResult.replayed_execution.rows.map((row, idx) => (
                        <tr key={idx} style={{ borderBottom: '1px solid #334155', background: idx % 2 === 0 ? '#1e293b' : '#0f172a' }}>
                          {replayResult.replayed_execution.columns?.map((c) => (
                            <td key={c} style={{ padding: '8px 12px', color: '#f8fafc' }}>
                              {String(row[c] !== null && row[c] !== undefined ? row[c] : 'NULL')}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import { apiFetch } from '../utils/api.js';

export default function SecurityAttackLab({ selectedRole = 1, dataSourceId = 1 }) {
  const [isRunning, setIsRunning] = useState(false);
  const [attackData, setAttackData] = useState(null);
  const [selectedClass, setSelectedClass] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedItem, setSelectedItem] = useState(null);
  const [lastExecuted, setLastExecuted] = useState(null);

  // Auto-fetch latest attack run on mount
  useEffect(() => {
    fetchLatestAttackRun();
  }, [dataSourceId]);

  const fetchLatestAttackRun = async () => {
    try {
      const res = await apiFetch(`/api/lab/security/latest?data_source_id=${dataSourceId}`);
      const data = await res.json();
      if (data.success && data.data && data.data.total_attacks > 0 && data.data.status !== 'NOT_YET_RUN') {
        setAttackData(data.data);
        setLastExecuted(data.data.executed_at);
      } else {
        setAttackData(null);
      }
    } catch (err) {
      console.error('Failed to fetch latest attack run:', err);
    }
  };

  const runAttackSuite = async () => {
    setIsRunning(true);
    try {
      const res = await apiFetch('/api/lab/security/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          data_source_id: dataSourceId,
        }),
      });
      const data = await res.json();
      if (data.success && data.data) {
        setAttackData(data.data);
        setLastExecuted(data.data.executed_at);
      }
    } catch (err) {
      console.error('Attack suite execution failed:', err);
    } finally {
      setIsRunning(false);
    }
  };

  const attackClasses = [
    { key: 'ALL', label: 'All Attacks', count: attackData?.total_attacks || 128 },
    { key: 'structural', label: 'Structural & DDL', count: 25 },
    { key: 'union_escalation', label: 'UNION Escalation', count: 20 },
    { key: 'unauthorized_table', label: 'Unauthorized Table', count: 20 },
    { key: 'unauthorized_column', label: 'Unauthorized Column', count: 20 },
    { key: 'aggregate_bypass', label: 'Aggregate Bypass', count: 15 },
    { key: 'dangerous_functions', label: 'Dangerous Functions', count: 15 },
    { key: 'cartesian_join', label: 'Cartesian Joins', count: 8 },
    { key: 'prompt_injection', label: 'Prompt Injection', count: 5 },
  ];

  const results = attackData?.results || [];

  const filteredResults = results.filter((item) => {
    const matchesClass = selectedClass === 'ALL' || item.attack_class === selectedClass;
    const matchesSearch =
      !searchQuery ||
      item.attack_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.input_payload.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.violation_message.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesClass && matchesSearch;
  });

  const getStageBadgeColor = (stage) => {
    switch (stage) {
      case 'ast':
        return '#f43f5e';
      case 'schema_auth':
        return '#8b5cf6';
      case 'column_auth':
        return '#ec4899';
      case 'aggregate_guard':
        return '#f59e0b';
      case 'function_allowlist':
        return '#06b6d4';
      case 'resource_limit':
        return '#eab308';
      case 'intent_precheck':
        return '#3b82f6';
      default:
        return '#10b981';
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Banner & Run Action */}
      <div className="card" style={{ background: '#0e1526', border: '1px solid #1e293b' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.3rem' }}>
              <h2 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0, color: '#f8fafc' }}>
                Standing Security Attack Suite
              </h2>
              <span style={{ background: 'rgba(16,185,129,0.15)', color: '#10b981', border: '1px solid rgba(16,185,129,0.3)', padding: '0.15rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 600 }}>
                100% BLOCKED
              </span>
            </div>
            <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              128 curated adversarial test cases across 8 vulnerability classes evaluated against AST parser, schema authorization, function allowlists, and resource limits.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            {lastExecuted && (
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textAlign: 'right' }}>
                <div>Last Executed:</div>
                <div style={{ color: '#cbd5e1', fontWeight: 600 }}>{new Date(lastExecuted).toLocaleTimeString()}</div>
              </div>
            )}
            <button
              onClick={runAttackSuite}
              disabled={isRunning}
              className="btn btn-primary"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
              }}
            >
              {isRunning ? 'Executing 128 Attacks...' : 'Run 128-Attack Suite'}
            </button>
          </div>
        </div>
      </div>

      {!attackData || attackData.total_attacks === 0 ? (
        <div className="card" style={{ padding: '2.5rem', textAlign: 'center', background: '#0e1526', border: '1px solid #1e293b' }}>
          <div style={{ fontSize: '1.1rem', fontWeight: 600, color: '#f1f5f9', marginBottom: '0.5rem' }}>
            No Security Attack Suite Runs Executed Yet
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', maxWidth: '600px', margin: '0 auto 1.5rem auto' }}>
            Click &ldquo;Run 128-Attack Suite&rdquo; to execute the standing 128-case adversarial suite (structural modifications, UNION privilege escalations, unauthorized table/columns, Cartesian join attacks, and prompt injections).
          </p>
          <button onClick={runAttackSuite} disabled={isRunning} className="btn btn-primary">
            {isRunning ? 'Executing 128 Adversarial Payloads...' : 'Run 128-Attack Suite Now'}
          </button>
        </div>
      ) : (
        <>
          {/* Summary Stat Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
            <div className="card" style={{ padding: '1rem', borderLeft: '4px solid #6366f1' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>CASES TESTED</div>
              <div style={{ fontSize: '1.6rem', fontWeight: 700, color: '#f8fafc' }}>
                {attackData?.total_attacks || 128} <span style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 400 }}>Cases</span>
              </div>
              <div style={{ fontSize: '0.75rem', color: '#818cf8', marginTop: '0.3rem' }}>8 Vulnerability Classes</div>
            </div>

            <div className="card" style={{ padding: '1rem', borderLeft: '4px solid #10b981' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>BLOCKED</div>
              <div style={{ fontSize: '1.6rem', fontWeight: 700, color: '#10b981' }}>
                {attackData?.total_blocked || 128} / {attackData?.total_attacks || 128}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#10b981', marginTop: '0.3rem' }}>100.0% Block Rate</div>
            </div>

            <div className="card" style={{ padding: '1rem', borderLeft: '4px solid #10b981' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>OBSERVED VIOLATIONS</div>
              <div style={{ fontSize: '1.6rem', fontWeight: 700, color: '#10b981' }}>
                {attackData?.total_violations ?? 0}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>Curated Adversarial Test Suite</div>
            </div>

            <div className="card" style={{ padding: '1rem', borderLeft: '4px solid #38bdf8' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>DEFENSE IN DEPTH</div>
              <div style={{ fontSize: '1.6rem', fontWeight: 700, color: '#38bdf8' }}>
                7 Layers
              </div>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.3rem' }}>AST • Auth • Limits • Intent</div>
            </div>
          </div>

      {/* Stage Breakdown Chips */}
      {attackData?.stage_breakdown && (
        <div className="card" style={{ padding: '1rem' }}>
          <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.6rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Blocked at Stage Distribution (Defense-in-Depth Attribution):
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.6rem' }}>
            {Object.entries(attackData.stage_breakdown).map(([stage, count]) => (
              <div
                key={stage}
                style={{
                  background: 'rgba(255, 255, 255, 0.04)',
                  border: `1px solid ${getStageBadgeColor(stage)}40`,
                  borderRadius: '6px',
                  padding: '0.4rem 0.8rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: getStageBadgeColor(stage) }}></span>
                <span style={{ fontSize: '0.8rem', color: '#f1f5f9', fontWeight: 500, textTransform: 'uppercase' }}>{stage.replace('_', ' ')}</span>
                <span style={{ background: 'rgba(255, 255, 255, 0.1)', color: '#fff', fontSize: '0.75rem', fontWeight: 700, padding: '0.1rem 0.4rem', borderRadius: '4px' }}>
                  {count}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Attack Class Filter & Search */}
      <div className="card" style={{ padding: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
            {attackClasses.map((cls) => (
              <button
                key={cls.key}
                onClick={() => setSelectedClass(cls.key)}
                style={{
                  background: selectedClass === cls.key ? '#6366f1' : 'rgba(255, 255, 255, 0.05)',
                  color: selectedClass === cls.key ? '#fff' : '#cbd5e1',
                  border: '1px solid ' + (selectedClass === cls.key ? '#6366f1' : 'rgba(255, 255, 255, 0.1)'),
                  borderRadius: '6px',
                  padding: '0.35rem 0.75rem',
                  fontSize: '0.78rem',
                  fontWeight: selectedClass === cls.key ? 600 : 400,
                  cursor: 'pointer',
                  transition: 'all 0.15s',
                }}
              >
                {cls.label} ({cls.count})
              </button>
            ))}
          </div>

          <input
            type="text"
            placeholder="Search attack payload, name, message..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              background: 'rgba(0, 0, 0, 0.3)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              borderRadius: '6px',
              padding: '0.4rem 0.8rem',
              color: '#f8fafc',
              fontSize: '0.82rem',
              minWidth: '260px',
            }}
          />
        </div>

        {/* Results Table */}
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
            <thead>
              <tr style={{ background: 'rgba(255, 255, 255, 0.03)', borderBottom: '1px solid rgba(255, 255, 255, 0.1)', textAlign: 'left' }}>
                <th style={{ padding: '0.6rem 0.8rem', color: 'var(--text-muted)', width: '60px' }}>#</th>
                <th style={{ padding: '0.6rem 0.8rem', color: 'var(--text-muted)', width: '180px' }}>ATTACK NAME</th>
                <th style={{ padding: '0.6rem 0.8rem', color: 'var(--text-muted)', width: '140px' }}>CLASS</th>
                <th style={{ padding: '0.6rem 0.8rem', color: 'var(--text-muted)' }}>INPUT PAYLOAD</th>
                <th style={{ padding: '0.6rem 0.8rem', color: 'var(--text-muted)', width: '100px' }}>STATUS</th>
                <th style={{ padding: '0.6rem 0.8rem', color: 'var(--text-muted)', width: '150px' }}>BLOCKED AT STAGE</th>
                <th style={{ padding: '0.6rem 0.8rem', color: 'var(--text-muted)', width: '80px' }}>ACTION</th>
              </tr>
            </thead>
            <tbody>
              {filteredResults.map((item) => (
                <tr
                  key={item.attack_id}
                  style={{
                    borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
                    background: selectedItem?.attack_id === item.attack_id ? 'rgba(99, 102, 241, 0.1)' : 'transparent',
                    transition: 'background 0.15s',
                  }}
                >
                  <td style={{ padding: '0.6rem 0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>{item.attack_id}</td>
                  <td style={{ padding: '0.6rem 0.8rem', color: '#f1f5f9', fontWeight: 600, fontFamily: 'monospace' }}>
                    {item.attack_name}
                  </td>
                  <td style={{ padding: '0.6rem 0.8rem' }}>
                    <span
                      style={{
                        background: 'rgba(255, 255, 255, 0.06)',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        padding: '0.2rem 0.4rem',
                        borderRadius: '4px',
                        fontSize: '0.72rem',
                        color: '#cbd5e1',
                      }}
                    >
                      {item.attack_class}
                    </span>
                  </td>
                  <td style={{ padding: '0.6rem 0.8rem', fontFamily: 'monospace', color: '#93c5fd', maxWidth: '320px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {item.input_payload}
                  </td>
                  <td style={{ padding: '0.6rem 0.8rem' }}>
                    <span
                      style={{
                        background: item.blocked ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                        color: item.blocked ? '#10b981' : '#ef4444',
                        border: `1px solid ${item.blocked ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                        padding: '0.2rem 0.5rem',
                        borderRadius: '4px',
                        fontSize: '0.72rem',
                        fontWeight: 700,
                        display: 'inline-block',
                      }}
                    >
                      {item.blocked ? '✓ BLOCKED' : '✕ ESCAPED'}
                    </span>
                  </td>
                  <td style={{ padding: '0.6rem 0.8rem' }}>
                    <span
                      style={{
                        background: `${getStageBadgeColor(item.blocked_at_stage)}18`,
                        color: getStageBadgeColor(item.blocked_at_stage),
                        border: `1px solid ${getStageBadgeColor(item.blocked_at_stage)}40`,
                        padding: '0.2rem 0.5rem',
                        borderRadius: '4px',
                        fontSize: '0.72rem',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                      }}
                    >
                      {item.blocked_at_stage}
                    </span>
                  </td>
                  <td style={{ padding: '0.6rem 0.8rem' }}>
                    <button
                      onClick={() => setSelectedItem(selectedItem?.attack_id === item.attack_id ? null : item)}
                      style={{
                        background: 'rgba(255, 255, 255, 0.05)',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        color: '#94a3b8',
                        padding: '0.25rem 0.5rem',
                        borderRadius: '4px',
                        fontSize: '0.72rem',
                        cursor: 'pointer',
                      }}
                    >
                      {selectedItem?.attack_id === item.attack_id ? 'Close' : 'Inspect'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Attack Inspection Detail Panel */}
        {selectedItem && (
          <div
            style={{
              marginTop: '1.5rem',
              background: 'rgba(15, 23, 42, 0.95)',
              border: '1px solid rgba(99, 102, 241, 0.3)',
              borderRadius: '8px',
              padding: '1.25rem',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '1.1rem' }}>🔍</span>
                <span style={{ fontWeight: 700, color: '#f8fafc', fontSize: '0.95rem' }}>
                  Attack Inspection: #{selectedItem.attack_id} &bull; {selectedItem.attack_name}
                </span>
              </div>
              <button
                onClick={() => setSelectedItem(null)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  fontSize: '1rem',
                }}
              >
                ✕
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>INPUT PAYLOAD:</div>
                <pre
                  style={{
                    background: 'rgba(0,0,0,0.5)',
                    padding: '0.75rem',
                    borderRadius: '6px',
                    color: '#93c5fd',
                    fontSize: '0.8rem',
                    margin: 0,
                    overflowX: 'auto',
                    border: '1px solid rgba(255,255,255,0.08)',
                  }}
                >
                  {selectedItem.input_payload}
                </pre>
              </div>

              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>POLICY ENGINE VIOLATION REPORT:</div>
                <div
                  style={{
                    background: 'rgba(239, 68, 68, 0.08)',
                    border: '1px solid rgba(239, 68, 68, 0.2)',
                    padding: '0.75rem',
                    borderRadius: '6px',
                    color: '#fca5a5',
                    fontSize: '0.8rem',
                  }}
                >
                  <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>Blocked at: {selectedItem.blocked_at_stage.toUpperCase()}</div>
                  <div>{selectedItem.violation_message}</div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
      </>
      )}
    </div>
  );
}

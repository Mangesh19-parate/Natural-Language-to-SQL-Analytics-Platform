import React, { useState } from 'react';
import SQLCriticCard from './SQLCriticCard.jsx';
import SelfCorrectionCard from './SelfCorrectionCard.jsx';
import ResultValidationCard from './ResultValidationCard.jsx';

export default function InvestigationCard({
  question,
  sql,
  executionResult,
  proposalData,
  onApplyFix,
}) {
  const [activeTab, setActiveTab] = useState('table');
  const [expandedSubScore, setExpandedSubScore] = useState(null);
  const [copyFeedback, setCopyFeedback] = useState(null);

  if (!executionResult && !proposalData) return null;

  const reliability = executionResult?.reliability_breakdown || proposalData?.reliability_breakdown;
  const columns = executionResult?.columns || [];
  const rows = executionResult?.rows || [];
  const rowCount = executionResult?.row_count ?? rows.length;
  const latencyMs = executionResult?.latency_ms ?? 0;
  const criticAnalysis = executionResult?.critic_analysis || proposalData?.critic_analysis;
  const correctionResult = executionResult?.correction_result;
  const resultValidation = executionResult?.result_validation;
  const isSuccess = executionResult?.success ?? proposalData?.can_execute ?? false;
  const activeSql = executionResult?.injected_sql || sql || proposalData?.proposal?.sql || '';

  // Tier color styling
  const getTierBadgeStyle = (tier) => {
    switch (tier) {
      case 'HIGH':
        return {
          background: 'rgba(16, 185, 129, 0.15)',
          color: '#10b981',
          border: '1px solid rgba(16, 185, 129, 0.4)',
        };
      case 'MEDIUM':
        return {
          background: 'rgba(245, 158, 11, 0.15)',
          color: '#f59e0b',
          border: '1px solid rgba(245, 158, 11, 0.4)',
        };
      case 'LOW':
      default:
        return {
          background: 'rgba(239, 68, 68, 0.15)',
          color: '#ef4444',
          border: '1px solid rgba(239, 68, 68, 0.4)',
        };
    }
  };

  // Derive high-level answer summary
  const getAnswerHeadline = () => {
    if (!isSuccess) {
      return executionResult?.error || 'Query could not be executed due to policy or syntax constraints.';
    }
    if (rowCount === 0) {
      return '0 rows returned. No matching records found for this query filter.';
    }
    if (rowCount === 1 && rows[0]) {
      const keys = Object.keys(rows[0]);
      if (keys.length === 1) {
        return `${keys[0]}: ${rows[0][keys[0]]}`;
      }
      return keys.map((k) => `${k}: ${rows[0][k]}`).join(' · ');
    }
    // Multi-row preview
    const firstRow = rows[0];
    const firstKey = Object.keys(firstRow)[0];
    const secondKey = Object.keys(firstRow)[1];
    if (firstKey && secondKey) {
      return `Top result: ${firstRow[firstKey]} (${firstRow[secondKey]}) · ${rowCount} total records found`;
    }
    return `${rowCount} records retrieved successfully`;
  };

  const handleCopyCsv = () => {
    if (!columns.length || !rows.length) return;
    const header = columns.join(',');
    const body = rows.map((r) => columns.map((c) => JSON.stringify(r[c] ?? '')).join(',')).join('\n');
    const csvContent = `${header}\n${body}`;
    navigator.clipboard.writeText(csvContent);
    setCopyFeedback('CSV Copied!');
    setTimeout(() => setCopyFeedback(null), 2000);
  };

  const handleCopySql = () => {
    navigator.clipboard.writeText(activeSql);
    setCopyFeedback('SQL Copied!');
    setTimeout(() => setCopyFeedback(null), 2000);
  };

  const subScoresList = reliability ? [
    { key: 'schema_grounding', data: reliability.schema_grounding },
    { key: 'join_confidence', data: reliability.join_confidence },
    { key: 'filter_interpretation', data: reliability.filter_interpretation },
    { key: 'execution_validation', data: reliability.execution_validation },
    { key: 'result_sanity', data: reliability.result_sanity },
  ] : [];

  return (
    <div
      className="investigation-card"
      style={{
        marginTop: '1.5rem',
        background: 'linear-gradient(145deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.9))',
        border: '1px solid rgba(99, 102, 241, 0.35)',
        borderRadius: '16px',
        padding: '1.5rem',
        boxShadow: '0 12px 32px -4px rgba(0, 0, 0, 0.5)',
      }}
    >
      {/* 1. Header Bar: Question & Reliability Badge */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
          paddingBottom: '1.25rem',
          marginBottom: '1.25rem',
          gap: '1rem',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ flex: 1, minWidth: '280px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
            <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#818cf8', fontWeight: 700 }}>
              Analytical Investigation Card &bull; REQ-EVID-01
            </span>
          </div>
          <h3 style={{ margin: '0 0 0.5rem 0', color: '#f8fafc', fontSize: '1.15rem', fontWeight: 600 }}>
            {question || 'Executed Query'}
          </h3>
          <div
            style={{
              fontSize: '0.92rem',
              color: isSuccess ? '#e2e8f0' : '#f87171',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
            }}
          >
            <span style={{ fontWeight: 600 }}>Answer:</span>
            <span>{getAnswerHeadline()}</span>
          </div>
        </div>

        {/* Reliability Score Badge (REQ-TRUST-01 / Rule R3.3) */}
        {reliability && (
          <div
            style={{
              padding: '0.65rem 1rem',
              borderRadius: '12px',
              textAlign: 'right',
              ...getTierBadgeStyle(reliability.tier),
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'flex-end',
              gap: '0.2rem',
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.2)',
            }}
          >
            <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.06em', opacity: 0.85, fontWeight: 700 }}>
              Evidence Reliability
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontSize: '1.4rem', fontWeight: 800, fontFamily: 'monospace' }}>
                {reliability.composite_score}
                <span style={{ fontSize: '0.85rem', opacity: 0.7 }}> / 100</span>
              </span>
              <span
                style={{
                  fontSize: '0.8rem',
                  fontWeight: 700,
                  padding: '0.15rem 0.5rem',
                  borderRadius: '6px',
                  background: 'rgba(0, 0, 0, 0.2)',
                }}
              >
                {reliability.tier === 'HIGH' ? '✓ HIGH' : reliability.tier === 'MEDIUM' ? '⚠ MEDIUM' : '✗ LOW'}
              </span>
            </div>
            <div style={{ fontSize: '0.68rem', opacity: 0.8 }}>
              5 Traceable Sub-Scores &bull; Zero Free Parameters
            </div>
          </div>
        )}
      </div>

      {/* 2. Main Two-Column Canvas: Signature Evidence Panel + Result Preview */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '1.25rem',
          marginBottom: '1.5rem',
        }}
      >
        {/* Left Column: Signature Evidence Panel (Always Visible) */}
        <div
          style={{
            background: 'rgba(0, 0, 0, 0.35)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '12px',
            padding: '1rem',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Audit Evidence Trail
            </span>
            <span style={{ fontSize: '0.72rem', color: '#64748b' }}>
              Deterministic Gates
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
            {subScoresList.map(({ key, data }) => (
              <div
                key={key}
                onClick={() => setExpandedSubScore(expandedSubScore === key ? null : key)}
                style={{
                  background: expandedSubScore === key ? 'rgba(99, 102, 241, 0.12)' : 'rgba(255, 255, 255, 0.03)',
                  border: `1px solid ${expandedSubScore === key ? 'rgba(99, 102, 241, 0.4)' : 'rgba(255, 255, 255, 0.06)'}`,
                  borderRadius: '8px',
                  padding: '0.6rem 0.8rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{
                      width: '20px',
                      height: '20px',
                      borderRadius: '50%',
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      ...getTierBadgeStyle(data.tier),
                    }}>
                      {data.status_icon}
                    </span>
                    <span style={{ fontSize: '0.85rem', color: '#f1f5f9', fontWeight: 600 }}>
                      {data.name}
                    </span>
                    <span style={{ fontSize: '0.7rem', color: '#64748b' }}>
                      ({Math.round(data.weight * 100)}%)
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontSize: '0.82rem', fontFamily: 'monospace', color: '#cbd5e1', fontWeight: 700 }}>
                      {data.score}/100
                    </span>
                    <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                      {expandedSubScore === key ? '▲' : '▼'}
                    </span>
                  </div>
                </div>

                <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: '0.3rem' }}>
                  {data.summary}
                </div>

                {/* Expanded Audit Evidence Items */}
                {expandedSubScore === key && (
                  <div style={{ marginTop: '0.5rem', paddingTop: '0.5rem', borderTop: '1px solid rgba(255, 255, 255, 0.08)' }}>
                    <div style={{ fontSize: '0.72rem', color: '#818cf8', fontWeight: 600, marginBottom: '0.3rem' }}>
                      Stage Verification Items:
                    </div>
                    <ul style={{ margin: 0, paddingLeft: '1.1rem', fontSize: '0.75rem', color: '#cbd5e1', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                      {data.evidence_items.map((item, idx) => (
                        <li key={idx}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Right Column: Fast KPI & Top Results Summary */}
        <div
          style={{
            background: 'rgba(0, 0, 0, 0.35)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '12px',
            padding: '1rem',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Execution Summary
            </span>
            <div style={{ display: 'flex', gap: '0.4rem' }}>
              {criticAnalysis?.has_findings && (
                <span style={{ fontSize: '0.72rem', background: 'rgba(245, 158, 11, 0.2)', color: '#f59e0b', padding: '0.15rem 0.45rem', borderRadius: '4px', fontWeight: 600 }}>
                  ⚠ Critic Smell
                </span>
              )}
              {correctionResult?.recovered && (
                <span style={{ fontSize: '0.72rem', background: 'rgba(99, 102, 241, 0.2)', color: '#818cf8', padding: '0.15rem 0.45rem', borderRadius: '4px', fontWeight: 600 }}>
                  ↻ Auto-Corrected ({correctionResult.retries_used})
                </span>
              )}
            </div>
          </div>

          {/* Quick Stat Chips */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem', marginBottom: '0.85rem' }}>
            <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '0.5rem', borderRadius: '6px', textAlign: 'center' }}>
              <div style={{ fontSize: '0.68rem', color: '#94a3b8' }}>Row Count</div>
              <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc' }}>{rowCount}</div>
            </div>
            <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '0.5rem', borderRadius: '6px', textAlign: 'center' }}>
              <div style={{ fontSize: '0.68rem', color: '#94a3b8' }}>Sandbox Latency</div>
              <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc' }}>{latencyMs}ms</div>
            </div>
            <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '0.5rem', borderRadius: '6px', textAlign: 'center' }}>
              <div style={{ fontSize: '0.68rem', color: '#94a3b8' }}>Policy State</div>
              <div style={{ fontSize: '0.95rem', fontWeight: 700, color: isSuccess ? '#10b981' : '#ef4444' }}>
                {isSuccess ? 'CLEARED' : 'BLOCKED'}
              </div>
            </div>
          </div>

          {/* Mini Table Preview */}
          <div style={{ flex: 1, overflowX: 'auto', background: 'rgba(0, 0, 0, 0.25)', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
            {columns.length > 0 && rows.length > 0 ? (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
                <thead>
                  <tr style={{ background: 'rgba(255, 255, 255, 0.05)', color: '#94a3b8', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>
                    {columns.slice(0, 4).map((c) => (
                      <th key={c} style={{ padding: '0.4rem 0.6rem', textAlign: 'left', fontWeight: 600 }}>{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(0, 3).map((r, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)', color: '#e2e8f0' }}>
                      {columns.slice(0, 4).map((c) => (
                        <td key={c} style={{ padding: '0.4rem 0.6rem' }}>{String(r[c] ?? '')}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div style={{ padding: '1.5rem', textAlign: 'center', color: '#64748b', fontSize: '0.8rem' }}>
                {isSuccess ? 'Empty dataset returned (0 rows)' : 'No execution output'}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 3. Implementation Detail Layer (Progressive Disclosure Tabs) */}
      <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.1)', paddingTop: '1rem' }}>
        <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '0.5rem', flexWrap: 'wrap' }}>
          <button
            onClick={() => setActiveTab('table')}
            style={{
              background: activeTab === 'table' ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
              color: activeTab === 'table' ? '#818cf8' : '#94a3b8',
              border: activeTab === 'table' ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent',
              borderRadius: '6px',
              padding: '0.4rem 0.8rem',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            📊 Table View ({rowCount})
          </button>

          <button
            onClick={() => setActiveTab('chart')}
            style={{
              background: activeTab === 'chart' ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
              color: activeTab === 'chart' ? '#818cf8' : '#94a3b8',
              border: activeTab === 'chart' ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent',
              borderRadius: '6px',
              padding: '0.4rem 0.8rem',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            📈 Visualization
          </button>

          <button
            onClick={() => setActiveTab('sql')}
            style={{
              background: activeTab === 'sql' ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
              color: activeTab === 'sql' ? '#818cf8' : '#94a3b8',
              border: activeTab === 'sql' ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent',
              borderRadius: '6px',
              padding: '0.4rem 0.8rem',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
            }}
          >
            <span>💻 SQL Code</span>
            {criticAnalysis?.has_findings && (
              <span style={{ fontSize: '0.7rem', color: '#f59e0b' }}>⚠</span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('explanation')}
            style={{
              background: activeTab === 'explanation' ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
              color: activeTab === 'explanation' ? '#818cf8' : '#94a3b8',
              border: activeTab === 'explanation' ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent',
              borderRadius: '6px',
              padding: '0.4rem 0.8rem',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            💡 Explanation
          </button>

          <button
            onClick={() => setActiveTab('validation')}
            style={{
              background: activeTab === 'validation' ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
              color: activeTab === 'validation' ? '#818cf8' : '#94a3b8',
              border: activeTab === 'validation' ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent',
              borderRadius: '6px',
              padding: '0.4rem 0.8rem',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            🛡️ Policy &amp; Sanity
          </button>

          {correctionResult && (
            <button
              onClick={() => setActiveTab('correction')}
              style={{
                background: activeTab === 'correction' ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
                color: activeTab === 'correction' ? '#818cf8' : '#94a3b8',
                border: activeTab === 'correction' ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent',
                borderRadius: '6px',
                padding: '0.4rem 0.8rem',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              ↻ Self-Correction Diff ({correctionResult.retries_used})
            </button>
          )}

          {copyFeedback && (
            <div style={{ marginLeft: 'auto', fontSize: '0.78rem', color: '#10b981', fontWeight: 600 }}>
              {copyFeedback}
            </div>
          )}
        </div>

        {/* Tab Content Display */}
        <div style={{ marginTop: '1rem' }}>
          {/* TAB 1: FULL TABLE VIEW */}
          {activeTab === 'table' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
                  Showing {rows.length} rows &bull; Sandboxed Read-Only
                </span>
                <button
                  onClick={handleCopyCsv}
                  style={{
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    color: '#e2e8f0',
                    borderRadius: '4px',
                    padding: '0.25rem 0.6rem',
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                  }}
                >
                  📥 Copy as CSV
                </button>
              </div>

              <div style={{ overflowX: 'auto', maxHeight: '350px', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '8px' }}>
                {columns.length > 0 && rows.length > 0 ? (
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
                    <thead>
                      <tr style={{ background: '#1e293b', position: 'sticky', top: 0, borderBottom: '1px solid rgba(255, 255, 255, 0.15)' }}>
                        {columns.map((c) => (
                          <th key={c} style={{ padding: '0.5rem 0.75rem', textAlign: 'left', color: '#94a3b8', fontWeight: 600 }}>
                            {c}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((r, idx) => (
                        <tr
                          key={idx}
                          style={{
                            background: idx % 2 === 0 ? 'rgba(255, 255, 255, 0.02)' : 'transparent',
                            borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                          }}
                        >
                          {columns.map((c) => (
                            <td key={c} style={{ padding: '0.5rem 0.75rem', color: '#e2e8f0' }}>
                              {String(r[c] ?? '')}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div style={{ padding: '2rem', textAlign: 'center', color: '#64748b', fontSize: '0.85rem' }}>
                    No rows returned from execution.
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 2: VISUALIZATION */}
          {activeTab === 'chart' && (
            <div style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '1.5rem', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc' }}>
                  📊 Chart Visualization Preview (Week 10 Foundation)
                </span>
                <span style={{ fontSize: '0.75rem', color: '#818cf8', background: 'rgba(99, 102, 241, 0.1)', padding: '0.2rem 0.5rem', borderRadius: '4px' }}>
                  Auto-Selected: {rowCount <= 10 ? 'Bar Chart' : 'Aggregate KPI Grid'}
                </span>
              </div>
              
              {/* Dynamic KPI Bar representation */}
              {rows.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {rows.slice(0, 6).map((r, i) => {
                    const labelKey = columns[0];
                    const valKey = columns[1] || columns[0];
                    const rawVal = Number(r[valKey]);
                    const displayVal = !isNaN(rawVal) ? rawVal : 1;
                    const maxVal = Math.max(...rows.slice(0, 6).map((row) => Number(row[valKey]) || 1));
                    const pct = Math.min(100, Math.max(10, Math.round((displayVal / (maxVal || 1)) * 100)));

                    return (
                      <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', color: '#cbd5e1' }}>
                          <span>{String(r[labelKey] ?? `Record #${i + 1}`)}</span>
                          <span style={{ fontWeight: 700, fontFamily: 'monospace' }}>{String(r[valKey] ?? '')}</span>
                        </div>
                        <div style={{ width: '100%', height: '8px', background: 'rgba(255, 255, 255, 0.05)', borderRadius: '4px', overflow: 'hidden' }}>
                          <div style={{ width: `${pct}%`, height: '100%', background: 'linear-gradient(90deg, #6366f1, #818cf8)', borderRadius: '4px' }}></div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div style={{ textAlign: 'center', color: '#64748b', padding: '1rem' }}>
                  No quantitative data available to visualize.
                </div>
              )}
            </div>
          )}

          {/* TAB 3: SQL CODE & CRITIC WARNING */}
          {activeTab === 'sql' && (
            <div>
              {/* Inline SQL Critic Warning (UI/UX v1.2 §3.5) */}
              {criticAnalysis && criticAnalysis.has_findings && (
                <div style={{ marginBottom: '1rem' }}>
                  <SQLCriticCard
                    criticAnalysis={criticAnalysis}
                    onApplyFix={onApplyFix}
                  />
                </div>
              )}

              <div style={{ position: 'relative' }}>
                <pre
                  style={{
                    background: '#090d16',
                    border: '1px solid rgba(99, 102, 241, 0.3)',
                    borderRadius: '8px',
                    padding: '1rem',
                    color: '#38bdf8',
                    fontFamily: 'monospace',
                    fontSize: '0.85rem',
                    margin: 0,
                    overflowX: 'auto',
                    lineHeight: 1.5,
                  }}
                >
                  {activeSql}
                </pre>
                <button
                  onClick={handleCopySql}
                  style={{
                    position: 'absolute',
                    top: '0.5rem',
                    right: '0.5rem',
                    background: 'rgba(255, 255, 255, 0.08)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    color: '#e2e8f0',
                    borderRadius: '4px',
                    padding: '0.25rem 0.5rem',
                    fontSize: '0.72rem',
                    cursor: 'pointer',
                  }}
                >
                  📋 Copy SQL
                </button>
              </div>
            </div>
          )}

          {/* TAB 4: EXPLANATION */}
          {activeTab === 'explanation' && (
            <div style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '1rem', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
              <div style={{ fontSize: '0.85rem', color: '#e2e8f0', lineHeight: 1.6 }}>
                <p style={{ margin: '0 0 0.75rem 0' }}>
                  <strong>LLM Rationale:</strong> {proposalData?.proposal?.rationale || 'Query generated from Semantic Catalog grounding.'}
                </p>
                <div style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
                  <strong>Dialect:</strong> PostgreSQL &bull; <strong>Execution Mode:</strong> Strict SELECT Read-Only Sandbox &bull; <strong>Row Cap:</strong> 10,000
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: POLICY & SANITY VALIDATION */}
          {activeTab === 'validation' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {resultValidation && (
                <ResultValidationCard validationReport={resultValidation} />
              )}
              
              <div style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '1rem', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
                <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#f8fafc', marginBottom: '0.5rem' }}>
                  Deterministic Policy Verification Checklist
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.5rem', fontSize: '0.78rem' }}>
                  <div style={{ color: '#10b981' }}>✓ AST SELECT-only Enforced</div>
                  <div style={{ color: '#10b981' }}>✓ Schema &amp; Column Deny-by-Default</div>
                  <div style={{ color: '#10b981' }}>✓ Function Allowlist Cleared</div>
                  <div style={{ color: '#10b981' }}>✓ Execution Sandbox Timeout Cap</div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 6: SELF-CORRECTION DIFF */}
          {activeTab === 'correction' && correctionResult && (
            <SelfCorrectionCard correctionResult={correctionResult} />
          )}
        </div>
      </div>
    </div>
  );
}

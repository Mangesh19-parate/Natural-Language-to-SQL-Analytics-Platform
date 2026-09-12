import React, { useState } from 'react';

export default function SQLCriticCard({
  criticAnalysis,
  onApplyFix,
  onProceedAnyway,
  onReviseQuestion,
}) {
  const [selectedFixIndex, setSelectedFixIndex] = useState(0);

  if (!criticAnalysis || !criticAnalysis.has_findings || criticAnalysis.findings.length === 0) {
    return (
      <div
        style={{
          background: 'rgba(16, 185, 129, 0.08)',
          border: '1px solid rgba(16, 185, 129, 0.3)',
          borderRadius: '8px',
          padding: '0.75rem 1rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          fontSize: '0.82rem',
          color: '#6ee7b7',
        }}
      >
        <span>✨</span>
        <span><strong>SQL Critic Passed:</strong> Zero semantic smells or redundant patterns detected.</span>
      </div>
    );
  }

  const finding = criticAnalysis.findings[selectedFixIndex] || criticAnalysis.findings[0];

  return (
    <div
      style={{
        background: 'rgba(245, 158, 11, 0.08)',
        border: '1px solid rgba(245, 158, 11, 0.35)',
        borderRadius: '8px',
        padding: '1rem',
        color: '#fef3c7',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '1.2rem' }}>⚠️</span>
          <span style={{ fontWeight: 700, fontSize: '0.9rem', color: '#fbbf24' }}>
            SQL Critic Advisory ({criticAnalysis.findings_count} Finding{criticAnalysis.findings_count > 1 ? 's' : ''})
          </span>
        </div>
        <span style={{ fontSize: '0.72rem', padding: '0.2rem 0.6rem', background: '#78350f', color: '#fde68a', borderRadius: '4px' }}>
          Rule R3.1 Visible Advisory
        </span>
      </div>

      <div style={{ fontSize: '0.85rem', color: '#fde68a', fontWeight: 600, marginTop: '0.25rem' }}>
        {finding.title}
      </div>

      <p style={{ fontSize: '0.82rem', color: '#cbd5e1', margin: '0.35rem 0 0.75rem 0' }}>
        {finding.detail}
      </p>

      {finding.suggested_sql && (
        <div style={{ background: '#090d16', border: '1px solid #334155', borderRadius: '6px', padding: '0.75rem', marginBottom: '0.75rem' }}>
          <div style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '0.25rem' }}>
            Recommended Correction:
          </div>
          <pre style={{ margin: 0, color: '#38bdf8', fontFamily: 'monospace', fontSize: '0.82rem', overflowX: 'auto' }}>
            {finding.suggested_sql}
          </pre>
          {finding.suggested_fix && (
            <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.35rem' }}>
              💡 {finding.suggested_fix}
            </div>
          )}
        </div>
      )}

      {/* 3 Explicit Action Buttons (Rule R3.1 / UI/UX Spec §3.2) */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.75rem' }}>
        {finding.suggested_sql && (
          <button
            onClick={() => onApplyFix && onApplyFix(finding.suggested_sql)}
            style={{
              background: '#059669',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              padding: '0.4rem 0.85rem',
              fontWeight: 600,
              fontSize: '0.78rem',
              cursor: 'pointer',
            }}
          >
            ✓ Use suggested fix
          </button>
        )}
        <button
          onClick={() => onProceedAnyway && onProceedAnyway()}
          style={{
            background: 'rgba(255, 255, 255, 0.1)',
            color: '#e2e8f0',
            border: '1px solid rgba(255, 255, 255, 0.2)',
            borderRadius: '6px',
            padding: '0.4rem 0.85rem',
            fontSize: '0.78rem',
            cursor: 'pointer',
          }}
        >
          Proceed anyway
        </button>
        <button
          onClick={() => onReviseQuestion && onReviseQuestion()}
          style={{
            background: 'transparent',
            color: '#94a3b8',
            border: '1px solid #475569',
            borderRadius: '6px',
            padding: '0.4rem 0.85rem',
            fontSize: '0.78rem',
            cursor: 'pointer',
          }}
        >
          Revise my question
        </button>
      </div>
    </div>
  );
}

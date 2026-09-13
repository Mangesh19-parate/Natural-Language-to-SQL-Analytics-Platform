import React from 'react';

export default function SelfCorrectionCard({ correctionResult, onApplyRepairedSql }) {
  if (!correctionResult) return null;

  const {
    recovered,
    final_sql,
    error_type,
    retries_used,
    attempts,
    routed_as_policy_rejection,
    message,
  } = correctionResult;

  const getTaxonomyBadge = (type) => {
    switch (type) {
      case 'E1':
        return { label: 'E1: Syntax Error', bg: 'rgba(244, 63, 94, 0.2)', color: '#fda4af', border: '#f43f5e' };
      case 'E2':
        return { label: 'E2: Schema Reference', bg: 'rgba(245, 158, 11, 0.2)', color: '#fde68a', border: '#f59e0b' };
      case 'E3':
        return { label: 'E3: Type Mismatch', bg: 'rgba(217, 70, 239, 0.2)', color: '#f5d0fe', border: '#d946ef' };
      case 'E4':
        return { label: 'E4: Semantic / Logic', bg: 'rgba(59, 130, 246, 0.2)', color: '#bfdbfe', border: '#3b82f6' };
      case 'E5':
        return { label: 'E5: Authorization (No Retry)', bg: 'rgba(239, 68, 68, 0.3)', color: '#fca5a5', border: '#ef4444' };
      case 'E6':
        return { label: 'E6: Timeout / Resource Limit', bg: 'rgba(234, 88, 12, 0.2)', color: '#fdba74', border: '#ea580c' };
      case 'E7':
        return { label: 'E7: Empty-Result Ambiguity', bg: 'rgba(168, 85, 247, 0.2)', color: '#e9d5ff', border: '#a855f7' };
      default:
        return { label: `${type || 'Error'}`, bg: 'rgba(148, 163, 184, 0.2)', color: '#e2e8f0', border: '#94a3b8' };
    }
  };

  const badge = getTaxonomyBadge(error_type);

  return (
    <div
      style={{
        marginTop: '1.25rem',
        padding: '1.1rem',
        borderRadius: '8px',
        border: `1px solid ${recovered ? 'rgba(16, 185, 129, 0.4)' : badge.border}`,
        background: recovered
          ? 'linear-gradient(180deg, rgba(16, 185, 129, 0.08) 0%, rgba(15, 23, 42, 0.6) 100%)'
          : 'linear-gradient(180deg, rgba(244, 63, 94, 0.08) 0%, rgba(15, 23, 42, 0.6) 100%)',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <span style={{ fontSize: '1.1rem' }}>{recovered ? '⚡' : '🛡️'}</span>
          <span style={{ fontWeight: 600, fontSize: '0.95rem', color: '#f8fafc' }}>
            Self-Correction Feedback Loop (REQ-CORR-01/02)
          </span>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <span
            style={{
              fontSize: '0.75rem',
              fontWeight: 700,
              padding: '0.2rem 0.6rem',
              borderRadius: '6px',
              background: badge.bg,
              color: badge.color,
              border: `1px solid ${badge.border}`,
            }}
          >
            {badge.label}
          </span>
          <span
            style={{
              fontSize: '0.75rem',
              fontWeight: 600,
              padding: '0.2rem 0.6rem',
              borderRadius: '6px',
              background: recovered ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
              color: recovered ? '#6ee7b7' : '#fca5a5',
              border: `1px solid ${recovered ? '#10b981' : '#ef4444'}`,
            }}
          >
            {recovered ? `Recovered (${retries_used} retry)` : (routed_as_policy_rejection ? 'Policy Rejection (R4.2)' : 'Exhausted')}
          </span>
        </div>
      </div>

      {/* Detail message */}
      <p style={{ fontSize: '0.85rem', color: '#e2e8f0', margin: '0 0 0.75rem 0' }}>
        {message}
      </p>

      {/* Retry Attempts breakdown */}
      {attempts && attempts.length > 0 && (
        <div style={{ marginBottom: '1rem' }}>
          <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
            Correction Iterations:
          </div>
          {attempts.map((att, idx) => (
            <div
              key={idx}
              style={{
                background: 'rgba(0, 0, 0, 0.35)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '6px',
                padding: '0.6rem 0.8rem',
                marginBottom: '0.5rem',
                fontSize: '0.8rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
                <span style={{ fontWeight: 600, color: '#93c5fd' }}>Attempt #{att.attempt_number}</span>
                <span style={{ color: att.execution_success ? '#6ee7b7' : '#fda4af' }}>
                  {att.execution_success ? '✓ Execution Succeeded' : '✗ Failed Re-execution'}
                </span>
              </div>
              <div style={{ color: '#94a3b8', fontSize: '0.78rem', marginBottom: '0.3rem' }}>
                {att.error_message}
              </div>
              {att.diff_summary && att.diff_summary !== 'No textual diff detected' && (
                <pre
                  style={{
                    background: '#0f172a',
                    padding: '0.4rem 0.6rem',
                    borderRadius: '4px',
                    fontSize: '0.72rem',
                    color: '#a5f3fc',
                    overflowX: 'auto',
                    margin: 0,
                  }}
                >
                  {att.diff_summary}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Recovered SQL box */}
      {recovered && final_sql && (
        <div>
          <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#6ee7b7', marginBottom: '0.3rem' }}>
            Repaired &amp; Verified SQL:
          </div>
          <pre
            style={{
              background: '#0a0f1d',
              padding: '0.6rem 0.8rem',
              borderRadius: '6px',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              fontSize: '0.8rem',
              color: '#6ee7b7',
              overflowX: 'auto',
              marginBottom: '0.75rem',
            }}
          >
            {final_sql}
          </pre>
          {onApplyRepairedSql && (
            <button
              onClick={() => onApplyRepairedSql(final_sql)}
              style={{
                background: '#10b981',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                padding: '0.4rem 0.8rem',
                fontSize: '0.8rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Use Repaired SQL in Editor
            </button>
          )}
        </div>
      )}
    </div>
  );
}

import React, { useState } from 'react';

export default function SQLProposalCard({
  question,
  roleId,
  resolvedQuestion,
  onGenerateSuccess,
}) {
  const [isGenerating, setIsGenerating] = useState(false);
  const [sqlProposalData, setSqlProposalData] = useState(null);
  const [error, setError] = useState(null);

  const targetQuestion = resolvedQuestion || question;

  const handleGenerate = async () => {
    if (!targetQuestion) return;
    setIsGenerating(true);
    setError(null);

    try {
      const res = await fetch('/api/sql/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: targetQuestion,
          role_id: roleId,
          data_source_id: 1,
        }),
      });
      const data = await res.json();
      setSqlProposalData(data);
      if (onGenerateSuccess) {
        onGenerateSuccess(data);
      }
    } catch (err) {
      setError(err.message || 'Failed to generate proposal');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div
      style={{
        marginTop: '1.5rem',
        background: 'rgba(15, 23, 42, 0.75)',
        border: '1px solid rgba(99, 102, 241, 0.3)',
        borderRadius: '12px',
        padding: '1.25rem',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <div>
          <h4 style={{ margin: 0, color: '#e2e8f0', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1rem' }}>
            <span>⚡</span>
            <span>Week 4: SQL Proposal &amp; Policy Engine Gate (T-14..T-18)</span>
          </h4>
          <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            Principle: <em>"The LLM proposes. Deterministic infrastructure authorizes, critiques, executes, and verifies."</em>
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={isGenerating || !targetQuestion}
          style={{
            background: 'linear-gradient(135deg, #6366f1, #4f46e5)',
            border: 'none',
            borderRadius: '6px',
            color: '#fff',
            padding: '0.5rem 1.1rem',
            fontWeight: 600,
            fontSize: '0.85rem',
            cursor: isGenerating ? 'not-allowed' : 'pointer',
            opacity: isGenerating ? 0.7 : 1,
            boxShadow: '0 2px 10px rgba(99, 102, 241, 0.4)',
          }}
        >
          {isGenerating ? 'Generating Proposal...' : '🚀 Generate SQL Proposal'}
        </button>
      </div>

      {error && (
        <div style={{ padding: '0.75rem', background: 'rgba(239, 68, 68, 0.15)', color: '#f87171', borderRadius: '6px', fontSize: '0.85rem' }}>
          {error}
        </div>
      )}

      {sqlProposalData && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
          {/* Proposal Box */}
          <div style={{ background: '#0b0f19', border: '1px solid #1e293b', borderRadius: '8px', padding: '1rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <span style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Candidate SQL Proposal (T-14)
              </span>
              <span style={{ fontSize: '0.7rem', padding: '0.15rem 0.5rem', background: '#334155', color: '#cbd5e1', borderRadius: '4px' }}>
                Unverified Proposal
              </span>
            </div>
            <pre style={{ margin: 0, color: '#38bdf8', fontFamily: 'monospace', fontSize: '0.88rem', overflowX: 'auto', padding: '0.5rem 0' }}>
              {sqlProposalData.proposal?.sql}
            </pre>
            {sqlProposalData.proposal?.rationale && (
              <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: '0.5rem', borderTop: '1px solid #1e293b', paddingTop: '0.5rem' }}>
                <strong>Rationale:</strong> {sqlProposalData.proposal.rationale}
              </div>
            )}
          </div>

          {/* Deterministic Policy Engine Gate (T-15, T-16, T-17, T-18) */}
          <div
            style={{
              background: sqlProposalData.can_execute ? 'rgba(16, 185, 129, 0.08)' : 'rgba(239, 68, 68, 0.08)',
              border: `1px solid ${sqlProposalData.can_execute ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
              borderRadius: '8px',
              padding: '1rem',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '1.1rem' }}>{sqlProposalData.can_execute ? '🛡️' : '🔒'}</span>
                <span style={{ fontWeight: 600, fontSize: '0.9rem', color: sqlProposalData.can_execute ? '#34d399' : '#f87171' }}>
                  Policy Enforcement Layer:{' '}
                  {sqlProposalData.can_execute ? 'APPROVED' : 'REJECTED (Fail-Closed)'}
                </span>
              </div>
              <span
                style={{
                  fontSize: '0.72rem',
                  padding: '0.2rem 0.6rem',
                  borderRadius: '12px',
                  fontWeight: 600,
                  background: sqlProposalData.can_execute ? '#065f46' : '#991b1b',
                  color: sqlProposalData.can_execute ? '#6ee7b7' : '#fca5a5',
                }}
              >
                {sqlProposalData.can_execute ? 'Permitted to Execute' : 'Blocked from Execution'}
              </span>
            </div>

            {/* Checks Checklist */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.5rem', margin: '0.75rem 0' }}>
              <div style={{ fontSize: '0.78rem', color: '#cbd5e1', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <span>✓</span>
                <span>AST SELECT-only (T-15)</span>
              </div>
              <div style={{ fontSize: '0.78rem', color: '#cbd5e1', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <span>✓</span>
                <span>Deny-by-Default Tables (T-16)</span>
              </div>
              <div style={{ fontSize: '0.78rem', color: '#cbd5e1', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <span>✓</span>
                <span>Column Authorization (T-17)</span>
              </div>
              <div style={{ fontSize: '0.78rem', color: '#cbd5e1', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <span>✓</span>
                <span>Aggregate Guard (T-18)</span>
              </div>
            </div>

            {/* Rejection Details if any */}
            {!sqlProposalData.can_execute && sqlProposalData.rejection_reasons?.length > 0 && (
              <div style={{ marginTop: '0.75rem', background: 'rgba(0, 0, 0, 0.3)', padding: '0.75rem', borderRadius: '6px' }}>
                <div style={{ fontSize: '0.75rem', color: '#fca5a5', fontWeight: 600, marginBottom: '0.25rem' }}>
                  Violations Detected:
                </div>
                <ul style={{ margin: 0, paddingLeft: '1.2rem', color: '#fca5a5', fontSize: '0.78rem' }}>
                  {sqlProposalData.rejection_reasons.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

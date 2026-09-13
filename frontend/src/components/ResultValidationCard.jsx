import React from 'react';

export default function ResultValidationCard({ validationReport }) {
  if (!validationReport || !validationReport.has_anomalies) return null;

  const { findings, findings_count } = validationReport;

  const getSeverityStyle = (severity) => {
    switch (severity) {
      case 'critical':
        return {
          bg: 'rgba(239, 68, 68, 0.15)',
          border: 'rgba(239, 68, 68, 0.4)',
          badgeBg: '#ef4444',
          badgeColor: '#fff',
          titleColor: '#fca5a5',
        };
      case 'warning':
        return {
          bg: 'rgba(245, 158, 11, 0.12)',
          border: 'rgba(245, 158, 11, 0.35)',
          badgeBg: '#f59e0b',
          badgeColor: '#1e293b',
          titleColor: '#fde68a',
        };
      default:
        return {
          bg: 'rgba(59, 130, 246, 0.12)',
          border: 'rgba(59, 130, 246, 0.35)',
          badgeBg: '#3b82f6',
          badgeColor: '#fff',
          titleColor: '#bfdbfe',
        };
    }
  };

  return (
    <div
      style={{
        marginTop: '1rem',
        padding: '1rem',
        borderRadius: '8px',
        border: '1px solid rgba(245, 158, 11, 0.4)',
        background: 'rgba(245, 158, 11, 0.05)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.6rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '1rem' }}>🔍</span>
          <span style={{ fontWeight: 600, fontSize: '0.88rem', color: '#fde68a' }}>
            Result Sanity Checks (REQ-RESULT-01 &bull; {findings_count} {findings_count === 1 ? 'Notice' : 'Notices'})
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {findings.map((f, idx) => {
          const style = getSeverityStyle(f.severity);
          return (
            <div
              key={idx}
              style={{
                background: style.bg,
                border: `1px solid ${style.border}`,
                borderRadius: '6px',
                padding: '0.6rem 0.8rem',
                fontSize: '0.8rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
                <span style={{ fontWeight: 600, color: style.titleColor, textTransform: 'uppercase' }}>
                  {f.check_type.replace('_', ' ')}
                </span>
                <span
                  style={{
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    padding: '0.15rem 0.45rem',
                    borderRadius: '4px',
                    background: style.badgeBg,
                    color: style.badgeColor,
                  }}
                >
                  {f.severity}
                </span>
              </div>
              <div style={{ color: '#e2e8f0', marginBottom: '0.3rem' }}>
                {f.message}
              </div>
              <div style={{ display: 'flex', gap: '1rem', fontSize: '0.72rem', color: '#94a3b8' }}>
                {f.expected_range && <span><strong>Expected:</strong> {f.expected_range}</span>}
                {f.observed_value && <span><strong>Observed:</strong> {f.observed_value}</span>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

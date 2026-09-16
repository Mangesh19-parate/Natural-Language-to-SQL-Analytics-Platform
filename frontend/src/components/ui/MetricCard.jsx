import React from 'react';

export default function MetricCard({
  label,
  value,
  subtitle,
  delta,
  deltaType = 'neutral', // 'positive' | 'negative' | 'neutral'
  className = '',
}) {
  const deltaColor =
    deltaType === 'positive'
      ? 'var(--color-success)'
      : deltaType === 'negative'
      ? 'var(--color-danger)'
      : 'var(--text-muted)';

  return (
    <div
      className={`metric-card ${className}`}
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: '6px',
        padding: '0.85rem 1rem',
      }}
    >
      <div
        style={{
          fontSize: '11px',
          fontWeight: 600,
          color: 'var(--text-muted)',
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
          marginBottom: '0.35rem',
        }}
      >
        {label}
      </div>
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: '0.5rem',
        }}
      >
        <div
          style={{
            fontSize: '1.4rem',
            fontWeight: 700,
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-mono)',
            letterSpacing: '-0.02em',
          }}
        >
          {value}
        </div>
        {delta && (
          <span
            style={{
              fontSize: '11px',
              fontWeight: 600,
              fontFamily: 'var(--font-mono)',
              color: deltaColor,
            }}
          >
            {delta}
          </span>
        )}
      </div>
      {subtitle && (
        <div
          style={{
            fontSize: '11px',
            color: 'var(--text-muted)',
            marginTop: '0.25rem',
          }}
        >
          {subtitle}
        </div>
      )}
    </div>
  );
}

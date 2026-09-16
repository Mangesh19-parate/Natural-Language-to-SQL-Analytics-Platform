import React from 'react';

export default function Badge({
  children,
  variant = 'neutral', // 'success' | 'warning' | 'danger' | 'info' | 'neutral'
  size = 'md', // 'sm' | 'md'
  className = '',
  dot = false,
}) {
  const colorMap = {
    success: {
      bg: 'var(--color-success-bg)',
      color: 'var(--color-success)',
      border: 'var(--color-success-border)',
    },
    warning: {
      bg: 'var(--color-warning-bg)',
      color: 'var(--color-warning)',
      border: 'var(--color-warning-border)',
    },
    danger: {
      bg: 'var(--color-danger-bg)',
      color: 'var(--color-danger)',
      border: 'var(--color-danger-border)',
    },
    info: {
      bg: 'var(--color-info-bg)',
      color: 'var(--color-info)',
      border: 'var(--color-info-border)',
    },
    neutral: {
      bg: 'var(--bg-subtle)',
      color: 'var(--text-secondary)',
      border: 'var(--border-subtle)',
    },
  };

  const style = colorMap[variant] || colorMap.neutral;
  const padding = size === 'sm' ? '0.15rem 0.4rem' : '0.2rem 0.55rem';
  const fontSize = size === 'sm' ? '10px' : '11px';

  return (
    <span
      className={`ui-badge ${className}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.35rem',
        padding,
        fontSize,
        fontFamily: 'var(--font-mono)',
        fontWeight: 600,
        borderRadius: '4px',
        background: style.bg,
        color: style.color,
        border: `1px solid ${style.border}`,
        lineHeight: 1,
      }}
    >
      {dot && (
        <span
          style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            background: 'currentColor',
          }}
        />
      )}
      {children}
    </span>
  );
}

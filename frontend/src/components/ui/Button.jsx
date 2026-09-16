import React from 'react';

export default function Button({
  children,
  variant = 'primary', // 'primary' | 'secondary' | 'danger' | 'ghost'
  size = 'md', // 'sm' | 'md' | 'lg'
  onClick,
  disabled = false,
  loading = false,
  className = '',
  type = 'button',
  icon = null,
  ...props
}) {
  const baseClass = 'ui-btn';
  const variantClass =
    variant === 'primary'
      ? 'ui-btn-primary'
      : variant === 'secondary'
      ? 'ui-btn-secondary'
      : variant === 'danger'
      ? 'ui-btn-danger'
      : 'ui-btn-ghost';
  const sizeClass = size === 'sm' ? 'ui-btn-sm' : '';

  return (
    <button
      type={type}
      className={`${baseClass} ${variantClass} ${sizeClass} ${className}`}
      onClick={onClick}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <span style={{ display: 'inline-block', animation: 'spin 1s linear infinite' }}>●</span>
      ) : icon ? (
        <span style={{ display: 'inline-flex', alignItems: 'center' }}>{icon}</span>
      ) : null}
      {children}
    </button>
  );
}

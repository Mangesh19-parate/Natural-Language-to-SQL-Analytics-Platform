import React from 'react';

export default function Card({
  title,
  subtitle,
  action,
  children,
  className = '',
  style = {},
}) {
  return (
    <div className={`ui-card ${className}`} style={style}>
      {(title || action) && (
        <div className="ui-card-header">
          <div>
            {title && <div className="ui-card-title">{title}</div>}
            {subtitle && (
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                {subtitle}
              </div>
            )}
          </div>
          {action && <div>{action}</div>}
        </div>
      )}
      {children}
    </div>
  );
}

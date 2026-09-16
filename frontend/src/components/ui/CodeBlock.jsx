import React, { useState } from 'react';

export default function CodeBlock({
  code = '',
  language = 'sql',
  title = null,
  copyable = true,
  maxHeight = '320px',
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      style={{
        background: 'var(--bg-app)',
        border: '1px solid var(--border-subtle)',
        borderRadius: '6px',
        overflow: 'hidden',
      }}
    >
      {(title || copyable) && (
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '0.4rem 0.75rem',
            background: 'var(--bg-surface)',
            borderBottom: '1px solid var(--border-subtle)',
            fontSize: '11px',
            fontFamily: 'var(--font-mono)',
            color: 'var(--text-secondary)',
          }}
        >
          <span>{title || language.toUpperCase()}</span>
          {copyable && (
            <button
              onClick={handleCopy}
              className="ui-btn ui-btn-secondary ui-btn-sm"
              style={{ padding: '0.15rem 0.45rem', fontSize: '10px' }}
            >
              {copied ? 'Copied' : 'Copy'}
            </button>
          )}
        </div>
      )}
      <pre
        style={{
          margin: 0,
          padding: '0.75rem 1rem',
          fontFamily: 'var(--font-mono)',
          fontSize: '12px',
          color: '#e2e8f0',
          lineHeight: 1.5,
          overflowX: 'auto',
          maxHeight,
        }}
      >
        <code>{code}</code>
      </pre>
    </div>
  );
}

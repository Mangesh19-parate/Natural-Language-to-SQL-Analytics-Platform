import React from 'react';
import Button from '../ui/Button.jsx';
import Badge from '../ui/Badge.jsx';

export default function QueryComposer({
  queryInput,
  setQueryInput,
  onSubmit,
  isLoading,
  selectedRoleName,
  generationMode = 'live',
  sampleQueries = [],
}) {
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      onSubmit();
    }
  };

  return (
    <div
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: '8px',
        padding: '1.25rem',
        marginBottom: '1.25rem',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '0.75rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
            Natural Language Query Composer
          </span>
          <Badge variant="neutral" size="sm">
            Role: {selectedRoleName}
          </Badge>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Badge variant={generationMode === 'live' ? 'success' : 'warning'} size="sm" dot>
            {generationMode === 'live' ? 'Live Provider' : 'Deterministic Mode'}
          </Badge>
        </div>
      </div>

      <div style={{ position: 'relative' }}>
        <textarea
          value={queryInput}
          onChange={(e) => setQueryInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask an analytical question in plain English (e.g., 'What was our total sales revenue by product category in 2025?')..."
          rows={3}
          style={{
            width: '100%',
            background: 'var(--bg-app)',
            border: '1px solid var(--border-base)',
            borderRadius: '6px',
            padding: '0.75rem 1rem',
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-sans)',
            fontSize: '13px',
            resize: 'vertical',
            outline: 'none',
            lineHeight: 1.5,
          }}
        />
      </div>

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginTop: '0.75rem',
        }}
      >
        <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
          {sampleQueries.slice(0, 3).map((sample, idx) => (
            <button
              key={idx}
              onClick={() => setQueryInput(sample)}
              className="ui-btn ui-btn-secondary ui-btn-sm"
              style={{ fontSize: '11px', color: 'var(--text-muted)' }}
            >
              {sample}
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Press ⌘+Enter to run
          </span>
          <Button
            variant="primary"
            onClick={() => onSubmit()}
            loading={isLoading}
            disabled={!queryInput.trim()}
          >
            Execute Query
          </Button>
        </div>
      </div>
    </div>
  );
}

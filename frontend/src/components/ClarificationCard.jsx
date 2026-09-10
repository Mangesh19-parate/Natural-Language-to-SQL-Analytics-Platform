import React from 'react';

export default function ClarificationCard({
  prompt,
  options,
  selectedOptionId,
  onSelectOption,
  onResolve,
  isResolving
}) {
  return (
    <div style={{
      background: 'rgba(99, 102, 241, 0.08)',
      border: '1px solid rgba(99, 102, 241, 0.3)',
      borderRadius: '12px',
      padding: '1.25rem',
      marginTop: '1rem',
      animation: 'fadeIn 0.3s ease'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
        <span style={{
          background: 'rgba(245, 158, 11, 0.2)',
          color: '#fbbf24',
          border: '1px solid rgba(245, 158, 11, 0.4)',
          borderRadius: '4px',
          fontSize: '0.7rem',
          fontWeight: 700,
          padding: '0.15rem 0.5rem',
          textTransform: 'uppercase'
        }}>
          Ambiguity Detected (Rule R2.4)
        </span>
        <span style={{ fontSize: '0.875rem', fontWeight: 600, color: '#f8fafc' }}>
          {prompt}
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginTop: '0.75rem' }}>
        {options.map((opt) => {
          const isSelected = selectedOptionId === opt.option_id;
          return (
            <label
              key={opt.option_id}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.75rem',
                padding: '0.75rem 1rem',
                borderRadius: '8px',
                background: isSelected ? 'rgba(99, 102, 241, 0.2)' : 'rgba(0, 0, 0, 0.25)',
                border: isSelected ? '1px solid #6366f1' : '1px solid rgba(255, 255, 255, 0.06)',
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
            >
              <input
                type="radio"
                name="clarification_option"
                checked={isSelected}
                onChange={() => onSelectOption(opt.option_id)}
                style={{ marginTop: '0.2rem', accentColor: '#6366f1' }}
              />
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                <span style={{ fontSize: '0.875rem', fontWeight: 600, color: isSelected ? '#a5b4fc' : '#e2e8f0' }}>
                  {opt.label}
                </span>
                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                  {opt.description}
                </span>
              </div>
            </label>
          );
        })}
      </div>

      <div style={{ marginTop: '1rem', display: 'flex', justifyContent: 'flex-end' }}>
        <button
          onClick={onResolve}
          disabled={!selectedOptionId || isResolving}
          style={{
            background: selectedOptionId ? '#6366f1' : '#334155',
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            padding: '0.5rem 1.25rem',
            fontSize: '0.85rem',
            fontWeight: 600,
            cursor: selectedOptionId ? 'pointer' : 'not-allowed',
            transition: 'background 0.2s ease'
          }}
        >
          {isResolving ? 'Resolving...' : 'Confirm & Proceed to SQL Proposal →'}
        </button>
      </div>
    </div>
  );
}

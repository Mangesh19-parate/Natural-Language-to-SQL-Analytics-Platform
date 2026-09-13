import React from 'react';

export default function ChartSwitcher({
  currentType = 'bar',
  suggestedTypes = [],
  onSelectType,
}) {
  const allTypes = [
    { key: 'bar', label: 'Vertical Bar', icon: '📊' },
    { key: 'horizontal_bar', label: 'Horizontal Bar', icon: '📶' },
    { key: 'line', label: 'Line Curve', icon: '📈' },
    { key: 'area', label: 'Area Chart', icon: '🌊' },
    { key: 'donut', label: 'Donut', icon: '🍩' },
    { key: 'pie', label: 'Pie', icon: '🥧' },
    { key: 'kpi_metric', label: 'KPI Metric', icon: '🔢' },
    { key: 'scatter', label: 'Scatter', icon: '⁖' },
    { key: 'table', label: 'Data Grid', icon: '📋' },
  ];

  // Filter to suggested types + allow switching to common ones
  const availableTypes = allTypes.filter((t) =>
    suggestedTypes.length > 0 ? suggestedTypes.includes(t.key) || ['bar', 'line', 'donut', 'table'].includes(t.key) : true
  );

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, marginRight: '0.2rem' }}>
        CHART FORMAT:
      </span>
      {availableTypes.map((t) => {
        const isActive = currentType === t.key;
        return (
          <button
            key={t.key}
            onClick={() => onSelectType && onSelectType(t.key)}
            style={{
              background: isActive ? 'rgba(99, 102, 241, 0.25)' : 'rgba(255, 255, 255, 0.05)',
              color: isActive ? '#a5b4fc' : '#cbd5e1',
              border: `1px solid ${isActive ? '#6366f1' : 'rgba(255, 255, 255, 0.1)'}`,
              borderRadius: '6px',
              padding: '0.25rem 0.6rem',
              fontSize: '0.75rem',
              fontWeight: isActive ? 600 : 400,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.3rem',
              transition: 'all 0.15s ease',
            }}
          >
            <span>{t.icon}</span>
            <span>{t.label}</span>
          </button>
        );
      })}
    </div>
  );
}

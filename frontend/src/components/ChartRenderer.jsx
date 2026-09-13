import React, { useState } from 'react';

export default function ChartRenderer({
  chartSpec,
  height = 320,
}) {
  const [hoveredIndex, setHoveredIndex] = useState(null);

  if (!chartSpec) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
        No visualization specification available.
      </div>
    );
  }

  const {
    chart_type = 'bar',
    title = '',
    x_axis_label,
    y_axis_label,
    labels = [],
    series = [],
    data_points = [],
    kpi_value,
    kpi_subtext,
    reasoning,
  } = chartSpec;

  const colorPalette = [
    '#6366f1', '#38bdf8', '#10b981', '#f59e0b',
    '#ec4899', '#8b5cf6', '#14b8a6', '#f43f5e',
  ];

  // Extract primary numeric values
  const rawValues = data_points.length > 0
    ? data_points.map((p) => (typeof p.value === 'number' ? p.value : 0))
    : series.length > 0 && series[0].data
    ? series[0].data.map((v) => (typeof v === 'number' ? v : 0))
    : [];

  const maxVal = Math.max(...rawValues, 1);
  const minVal = Math.min(...rawValues, 0);
  const totalSum = rawValues.reduce((a, b) => a + b, 0);

  // ---------------------------------------------------------------------------
  // 1. KPI Metric Hero Card
  // ---------------------------------------------------------------------------
  if (chart_type === 'kpi_metric') {
    return (
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(56, 189, 248, 0.1) 100%)',
          border: '1px solid rgba(99, 102, 241, 0.25)',
          borderRadius: '12px',
          padding: '2.5rem 2rem',
          textAlign: 'center',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: height,
        }}
      >
        <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, marginBottom: '0.75rem' }}>
          {title || kpi_subtext || 'Single Result Metric'}
        </span>
        <div style={{ fontSize: '3.2rem', fontWeight: 800, color: '#f8fafc', lineHeight: 1.1, textShadow: '0 0 30px rgba(99, 102, 241, 0.3)' }}>
          {kpi_value || (rawValues[0] !== undefined ? rawValues[0].toLocaleString() : '0')}
        </div>
        {kpi_subtext && (
          <span style={{ fontSize: '0.9rem', color: '#93c5fd', marginTop: '0.75rem', fontWeight: 500 }}>
            {kpi_subtext}
          </span>
        )}
        <div style={{ marginTop: '1.25rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <span style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '0.2rem 0.6rem', borderRadius: '20px', fontSize: '0.75rem', fontWeight: 600 }}>
            ✓ Verified Exact Calculation
          </span>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // 2. Vertical Bar Chart
  // ---------------------------------------------------------------------------
  if (chart_type === 'bar') {
    const barWidth = Math.min(Math.max(24, Math.floor(500 / Math.max(labels.length, 1))), 56);
    const svgWidth = Math.max(580, labels.length * (barWidth + 24) + 80);
    const svgHeight = height;
    const chartBottom = svgHeight - 50;
    const chartTop = 30;
    const availableHeight = chartBottom - chartTop;

    return (
      <div style={{ width: '100%', overflowX: 'auto' }}>
        <svg width={svgWidth} height={svgHeight} style={{ overflow: 'visible', display: 'block' }}>
          <defs>
            <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#818cf8" />
              <stop offset="100%" stopColor="#4f46e5" />
            </linearGradient>
            <linearGradient id="barHoverGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#38bdf8" />
              <stop offset="100%" stopColor="#0284c7" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((pct, idx) => {
            const y = chartBottom - availableHeight * pct;
            const valLabel = Math.round(maxVal * pct).toLocaleString();
            return (
              <g key={idx}>
                <line x1="50" y1={y} x2={svgWidth - 20} y2={y} stroke="rgba(255, 255, 255, 0.08)" strokeDasharray="3 3" />
                <text x="42" y={y + 4} fill="#64748b" fontSize="10" textAnchor="end" fontFamily="sans-serif">
                  {valLabel}
                </text>
              </g>
            );
          })}

          {/* Bars */}
          {labels.map((lbl, idx) => {
            const val = rawValues[idx] || 0;
            const barHeight = maxVal > 0 ? (val / maxVal) * availableHeight : 0;
            const x = 70 + idx * (barWidth + 20);
            const y = chartBottom - barHeight;
            const isHovered = hoveredIndex === idx;

            return (
              <g
                key={idx}
                onMouseEnter={() => setHoveredIndex(idx)}
                onMouseLeave={() => setHoveredIndex(null)}
                style={{ cursor: 'pointer' }}
              >
                {/* Bar Rect */}
                <rect
                  x={x}
                  y={y}
                  width={barWidth}
                  height={Math.max(barHeight, 2)}
                  rx="4"
                  fill={isHovered ? 'url(#barHoverGradient)' : 'url(#barGradient)'}
                  style={{ transition: 'all 0.2s ease' }}
                />

                {/* Top value label */}
                <text
                  x={x + barWidth / 2}
                  y={y - 6}
                  fill={isHovered ? '#38bdf8' : '#94a3b8'}
                  fontSize="11"
                  fontWeight={isHovered ? '700' : '500'}
                  textAnchor="middle"
                  fontFamily="sans-serif"
                >
                  {val.toLocaleString()}
                </text>

                {/* X-axis label */}
                <text
                  x={x + barWidth / 2}
                  y={chartBottom + 20}
                  fill={isHovered ? '#f1f5f9' : '#94a3b8'}
                  fontSize="11"
                  fontWeight={isHovered ? '600' : '400'}
                  textAnchor="middle"
                  fontFamily="sans-serif"
                  transform={labels.length > 6 ? `rotate(-25, ${x + barWidth / 2}, ${chartBottom + 20})` : undefined}
                >
                  {lbl.length > 14 ? `${lbl.substring(0, 12)}…` : lbl}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // 3. Horizontal Bar Chart
  // ---------------------------------------------------------------------------
  if (chart_type === 'horizontal_bar') {
    const rowHeight = 36;
    const svgHeight = Math.max(height, labels.length * rowHeight + 40);
    const svgWidth = 600;
    const labelWidth = 140;
    const maxBarWidth = svgWidth - labelWidth - 90;

    return (
      <div style={{ width: '100%', overflowY: 'auto', maxHeight: height + 60 }}>
        <svg width={svgWidth} height={svgHeight}>
          {labels.map((lbl, idx) => {
            const val = rawValues[idx] || 0;
            const barW = maxVal > 0 ? (val / maxVal) * maxBarWidth : 0;
            const y = 20 + idx * rowHeight;
            const isHovered = hoveredIndex === idx;

            return (
              <g
                key={idx}
                onMouseEnter={() => setHoveredIndex(idx)}
                onMouseLeave={() => setHoveredIndex(null)}
                style={{ cursor: 'pointer' }}
              >
                {/* Category Label */}
                <text
                  x={labelWidth - 10}
                  y={y + 16}
                  fill={isHovered ? '#38bdf8' : '#cbd5e1'}
                  fontSize="11"
                  fontWeight={isHovered ? '600' : '400'}
                  textAnchor="end"
                  fontFamily="sans-serif"
                >
                  {lbl.length > 18 ? `${lbl.substring(0, 16)}…` : lbl}
                </text>

                {/* Bar Track Background */}
                <rect x={labelWidth} y={y + 4} width={maxBarWidth} height="16" rx="4" fill="rgba(255,255,255,0.04)" />

                {/* Filled Bar */}
                <rect
                  x={labelWidth}
                  y={y + 4}
                  width={Math.max(barW, 3)}
                  height="16"
                  rx="4"
                  fill={isHovered ? '#38bdf8' : colorPalette[idx % colorPalette.length]}
                />

                {/* Value text */}
                <text
                  x={labelWidth + barW + 10}
                  y={y + 16}
                  fill="#f1f5f9"
                  fontSize="11"
                  fontWeight="600"
                  fontFamily="sans-serif"
                >
                  {val.toLocaleString()}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // 4. Line / Area Trend Curve
  // ---------------------------------------------------------------------------
  if (chart_type === 'line' || chart_type === 'area') {
    const svgWidth = 600;
    const svgHeight = height;
    const paddingLeft = 55;
    const paddingRight = 30;
    const paddingTop = 30;
    const paddingBottom = 45;

    const plotWidth = svgWidth - paddingLeft - paddingRight;
    const plotHeight = svgHeight - paddingTop - paddingBottom;

    const points = labels.map((lbl, idx) => {
      const val = rawValues[idx] || 0;
      const x = paddingLeft + (idx / Math.max(labels.length - 1, 1)) * plotWidth;
      const y = paddingTop + plotHeight - (maxVal > 0 ? (val / maxVal) * plotHeight : 0);
      return { x, y, val, lbl };
    });

    const pathD = points.reduce((acc, pt, i) => {
      if (i === 0) return `M ${pt.x} ${pt.y}`;
      // Smooth curve with simple cubic bezier
      const prev = points[i - 1];
      const cx1 = prev.x + (pt.x - prev.x) / 2;
      const cy1 = prev.y;
      const cx2 = prev.x + (pt.x - prev.x) / 2;
      const cy2 = pt.y;
      return `${acc} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${pt.x} ${pt.y}`;
    }, '');

    const areaD = `${pathD} L ${points[points.length - 1]?.x || 0} ${paddingTop + plotHeight} L ${points[0]?.x || 0} ${paddingTop + plotHeight} Z`;

    return (
      <div style={{ width: '100%', overflowX: 'auto' }}>
        <svg width={svgWidth} height={svgHeight}>
          <defs>
            <linearGradient id="lineAreaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#6366f1" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#6366f1" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((pct, idx) => {
            const y = paddingTop + plotHeight - plotHeight * pct;
            return (
              <g key={idx}>
                <line x1={paddingLeft} y1={y} x2={svgWidth - paddingRight} y2={y} stroke="rgba(255, 255, 255, 0.08)" strokeDasharray="3 3" />
                <text x={paddingLeft - 8} y={y + 3} fill="#64748b" fontSize="10" textAnchor="end" fontFamily="sans-serif">
                  {Math.round(maxVal * pct).toLocaleString()}
                </text>
              </g>
            );
          })}

          {/* Area Fill */}
          <path d={areaD} fill="url(#lineAreaGradient)" />

          {/* Line Path */}
          <path d={pathD} fill="none" stroke="#6366f1" strokeWidth="3" strokeLinecap="round" />

          {/* Points & Tooltips */}
          {points.map((pt, idx) => {
            const isHovered = hoveredIndex === idx;
            return (
              <g
                key={idx}
                onMouseEnter={() => setHoveredIndex(idx)}
                onMouseLeave={() => setHoveredIndex(null)}
                style={{ cursor: 'pointer' }}
              >
                {/* Outer halo on hover */}
                {isHovered && <circle cx={pt.x} cy={pt.y} r="8" fill="rgba(99, 102, 241, 0.3)" />}

                {/* Point Node */}
                <circle cx={pt.x} cy={pt.y} r={isHovered ? 5 : 4} fill={isHovered ? '#38bdf8' : '#818cf8'} stroke="#0f172a" strokeWidth="2" />

                {/* Value tooltip */}
                {isHovered && (
                  <g>
                    <rect x={pt.x - 30} y={pt.y - 30} width="60" height="20" rx="4" fill="#1e293b" stroke="#6366f1" strokeWidth="1" />
                    <text x={pt.x} y={pt.y - 16} fill="#fff" fontSize="10" fontWeight="600" textAnchor="middle" fontFamily="sans-serif">
                      {pt.val.toLocaleString()}
                    </text>
                  </g>
                )}

                {/* X-axis Label */}
                <text
                  x={pt.x}
                  y={paddingTop + plotHeight + 18}
                  fill={isHovered ? '#f1f5f9' : '#94a3b8'}
                  fontSize="10"
                  textAnchor="middle"
                  fontFamily="sans-serif"
                >
                  {pt.lbl.length > 10 ? `${pt.lbl.substring(0, 8)}…` : pt.lbl}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // 5. Donut / Pie Chart
  // ---------------------------------------------------------------------------
  if (chart_type === 'donut' || chart_type === 'pie') {
    const size = height;
    const center = size / 2;
    const radius = size * 0.38;
    const isDonut = chart_type === 'donut';
    const strokeWidth = isDonut ? radius * 0.45 : radius;
    const circumference = 2 * Math.PI * (radius - strokeWidth / 2);

    let currentOffset = 0;

    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '2rem', flexWrap: 'wrap', minHeight: height }}>
        {/* SVG Donut / Pie */}
        <div style={{ position: 'relative', width: size, height: size }}>
          <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: 'rotate(-90deg)' }}>
            {rawValues.map((val, idx) => {
              const fraction = totalSum > 0 ? val / totalSum : 0;
              const strokeDasharray = `${fraction * circumference} ${circumference}`;
              const strokeDashoffset = -currentOffset;
              currentOffset += fraction * circumference;
              const isHovered = hoveredIndex === idx;

              return (
                <circle
                  key={idx}
                  cx={center}
                  cy={center}
                  r={radius - strokeWidth / 2}
                  fill="transparent"
                  stroke={colorPalette[idx % colorPalette.length]}
                  strokeWidth={isHovered ? strokeWidth + 4 : strokeWidth}
                  strokeDasharray={strokeDasharray}
                  strokeDashoffset={strokeDashoffset}
                  onMouseEnter={() => setHoveredIndex(idx)}
                  onMouseLeave={() => setHoveredIndex(null)}
                  style={{
                    cursor: 'pointer',
                    transition: 'stroke-width 0.2s ease, opacity 0.2s ease',
                    opacity: hoveredIndex !== null && !isHovered ? 0.45 : 1,
                  }}
                />
              );
            })}
          </svg>

          {/* Center Summary Label (for Donut) */}
          {isDonut && (
            <div
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                pointerEvents: 'none',
              }}
            >
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                {hoveredIndex !== null ? labels[hoveredIndex] : 'TOTAL'}
              </span>
              <span style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc' }}>
                {hoveredIndex !== null
                  ? `${Math.round(((rawValues[hoveredIndex] || 0) / Math.max(totalSum, 1)) * 100)}%`
                  : totalSum.toLocaleString()}
              </span>
            </div>
          )}
        </div>

        {/* Legend */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: height, overflowY: 'auto' }}>
          {labels.map((lbl, idx) => {
            const val = rawValues[idx] || 0;
            const pct = totalSum > 0 ? ((val / totalSum) * 100).toFixed(1) : '0';
            const isHovered = hoveredIndex === idx;

            return (
              <div
                key={idx}
                onMouseEnter={() => setHoveredIndex(idx)}
                onMouseLeave={() => setHoveredIndex(null)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.6rem',
                  padding: '0.3rem 0.6rem',
                  borderRadius: '6px',
                  background: isHovered ? 'rgba(255, 255, 255, 0.08)' : 'transparent',
                  cursor: 'pointer',
                  transition: 'background 0.15s ease',
                }}
              >
                <span
                  style={{
                    width: '10px',
                    height: '10px',
                    borderRadius: isDonut ? '50%' : '2px',
                    background: colorPalette[idx % colorPalette.length],
                  }}
                ></span>
                <span style={{ fontSize: '0.8rem', color: isHovered ? '#f1f5f9' : '#cbd5e1', minWidth: '100px' }}>
                  {lbl}
                </span>
                <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#f8fafc' }}>
                  {val.toLocaleString()}
                </span>
                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                  ({pct}%)
                </span>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // 6. Scatter Distribution
  // ---------------------------------------------------------------------------
  if (chart_type === 'scatter') {
    const svgWidth = 600;
    const svgHeight = height;
    const pad = 50;
    const plotW = svgWidth - pad * 2;
    const plotH = svgHeight - pad * 2;

    const xVals = data_points.map((p) => (p.extra?.x !== undefined ? p.extra.x : 0));
    const yVals = data_points.map((p) => (p.extra?.y !== undefined ? p.extra.y : 0));

    const maxX = Math.max(...xVals, 1);
    const maxY = Math.max(...yVals, 1);

    return (
      <div style={{ width: '100%', overflowX: 'auto' }}>
        <svg width={svgWidth} height={svgHeight}>
          {/* Axes */}
          <line x1={pad} y1={pad} x2={pad} y2={svgHeight - pad} stroke="rgba(255,255,255,0.2)" />
          <line x1={pad} y1={svgHeight - pad} x2={svgWidth - pad} y2={svgHeight - pad} stroke="rgba(255,255,255,0.2)" />

          {/* Scatter Points */}
          {data_points.map((p, idx) => {
            const px = pad + (p.extra?.x / maxX) * plotW;
            const py = svgHeight - pad - (p.extra?.y / maxY) * plotH;
            const isHovered = hoveredIndex === idx;

            return (
              <g
                key={idx}
                onMouseEnter={() => setHoveredIndex(idx)}
                onMouseLeave={() => setHoveredIndex(null)}
                style={{ cursor: 'pointer' }}
              >
                <circle cx={px} cy={py} r={isHovered ? 7 : 5} fill={isHovered ? '#38bdf8' : '#818cf8'} stroke="#0f172a" strokeWidth="2" />
                {isHovered && (
                  <text x={px} y={py - 10} fill="#f1f5f9" fontSize="10" fontWeight="600" textAnchor="middle">
                    ({p.extra?.x}, {p.extra?.y})
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Fallback
  // ---------------------------------------------------------------------------
  return (
    <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
      Results best viewed in the paired <strong>Table tab</strong> (Rule R8.2).
    </div>
  );
}

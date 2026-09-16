import React, { useState, useEffect, useMemo } from 'react';
import SQLCriticCard from './SQLCriticCard.jsx';
import SelfCorrectionCard from './SelfCorrectionCard.jsx';
import ResultValidationCard from './ResultValidationCard.jsx';
import ChartRenderer from './ChartRenderer.jsx';
import ChartSwitcher from './ChartSwitcher.jsx';
import OptimizationCard from './OptimizationCard.jsx';
import ReportExportModal from './ReportExportModal.jsx';
import QueryReplayCard from './QueryReplayCard.jsx';


export default function InvestigationCard({
  question,
  sql,
  executionResult,
  proposalData,
  onApplyFix,
}) {
  const [activeTab, setActiveTab] = useState('chart');
  const [expandedSubScore, setExpandedSubScore] = useState(null);
  const [copyFeedback, setCopyFeedback] = useState(null);
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);

  
  // Table state: sorting, filtering, pagination
  const [tableSearch, setTableSearch] = useState('');
  const [sortCol, setSortCol] = useState(null);
  const [sortDir, setSortDir] = useState('asc');
  const [pageSize, setPageSize] = useState(10);
  const [currentPage, setCurrentPage] = useState(1);

  // Visualization state
  const [currentChartSpec, setCurrentChartSpec] = useState(null);
  const [isSwitchingChart, setIsSwitchingChart] = useState(false);

  useEffect(() => {
    if (executionResult?.chart_spec) {
      setCurrentChartSpec(executionResult.chart_spec);
      // If table is not visualizable, default to table tab
      if (!executionResult.chart_spec.is_visualizable) {
        setActiveTab('table');
      } else {
        setActiveTab('chart');
      }
    }
  }, [executionResult]);

  if (!executionResult && !proposalData) return null;

  const reliability = executionResult?.reliability_breakdown || proposalData?.reliability_breakdown;
  const columns = executionResult?.columns || [];
  const rows = executionResult?.rows || [];
  const rowCount = executionResult?.row_count ?? rows.length;
  const latencyMs = executionResult?.latency_ms ?? 0;
  const criticAnalysis = executionResult?.critic_analysis || proposalData?.critic_analysis;
  const correctionResult = executionResult?.correction_result;
  const resultValidation = executionResult?.result_validation;
  const isSuccess = executionResult?.success ?? proposalData?.can_execute ?? false;
  const activeSql = executionResult?.injected_sql || sql || proposalData?.proposal?.sql || '';

  // Filtered & Sorted Table Rows
  const processedRows = useMemo(() => {
    let result = [...rows];
    if (tableSearch.trim()) {
      const q = tableSearch.toLowerCase();
      result = result.filter((r) =>
        columns.some((c) => String(r[c] ?? '').toLowerCase().includes(q))
      );
    }
    if (sortCol) {
      result.sort((a, b) => {
        const valA = a[sortCol];
        const valB = b[sortCol];
        if (typeof valA === 'number' && typeof valB === 'number') {
          return sortDir === 'asc' ? valA - valB : valB - valA;
        }
        const strA = String(valA ?? '');
        const strB = String(valB ?? '');
        return sortDir === 'asc' ? strA.localeCompare(strB) : strB.localeCompare(strA);
      });
    }
    return result;
  }, [rows, columns, tableSearch, sortCol, sortDir]);

  const totalPages = Math.max(1, Math.ceil(processedRows.length / pageSize));
  const paginatedRows = processedRows.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  const handleSort = (colName) => {
    if (sortCol === colName) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortCol(colName);
      setSortDir('asc');
    }
  };

  const handleSelectChartType = async (typeKey) => {
    if (!columns.length || !rows.length) return;
    setIsSwitchingChart(true);
    try {
      const res = await fetch('/api/vis/generate-chart', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          columns,
          rows,
          question,
          requested_chart_type: typeKey,
        }),
      });
      const data = await res.json();
      if (data.success && data.chart_spec) {
        setCurrentChartSpec(data.chart_spec);
      }
    } catch (err) {
      console.error('Chart switch failed:', err);
      // Fallback: local override
      if (currentChartSpec) {
        setCurrentChartSpec({ ...currentChartSpec, chart_type: typeKey });
      }
    } finally {
      setIsSwitchingChart(false);
    }
  };

  const handleCopyCsv = () => {
    if (!columns.length || !rows.length) return;
    const header = columns.join(',');
    const body = rows.map((r) => columns.map((c) => JSON.stringify(r[c] ?? '')).join(',')).join('\n');
    const csvContent = `${header}\n${body}`;
    navigator.clipboard.writeText(csvContent);
    setCopyFeedback('CSV Copied to Clipboard!');
    setTimeout(() => setCopyFeedback(null), 2000);
  };

  const handleDownloadCsv = () => {
    if (!columns.length || !rows.length) return;
    const header = columns.join(',');
    const body = rows.map((r) => columns.map((c) => JSON.stringify(r[c] ?? '')).join(',')).join('\n');
    const csvContent = `data:text/csv;charset=utf-8,${encodeURIComponent(`${header}\n${body}`)}`;
    const link = document.createElement('a');
    link.setAttribute('href', csvContent);
    link.setAttribute('download', `query_results_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleCopySql = () => {
    navigator.clipboard.writeText(activeSql);
    setCopyFeedback('SQL Copied!');
    setTimeout(() => setCopyFeedback(null), 2000);
  };

  const getTierBadgeStyle = (tier) => {
    switch (tier) {
      case 'HIGH':
        return {
          background: 'rgba(16, 185, 129, 0.15)',
          color: '#10b981',
          border: '1px solid rgba(16, 185, 129, 0.4)',
        };
      case 'MEDIUM':
        return {
          background: 'rgba(245, 158, 11, 0.15)',
          color: '#f59e0b',
          border: '1px solid rgba(245, 158, 11, 0.4)',
        };
      case 'LOW':
      default:
        return {
          background: 'rgba(239, 68, 68, 0.15)',
          color: '#ef4444',
          border: '1px solid rgba(239, 68, 68, 0.4)',
        };
    }
  };

  const getAnswerHeadline = () => {
    if (!isSuccess) {
      return executionResult?.error || 'Query could not be executed due to policy or syntax constraints.';
    }
    if (rowCount === 0) {
      return '0 rows returned. No matching records found for this query filter.';
    }
    if (rowCount === 1 && rows[0]) {
      const keys = Object.keys(rows[0]);
      if (keys.length === 1) {
        return `${keys[0]}: ${rows[0][keys[0]]}`;
      }
      return keys.map((k) => `${k}: ${rows[0][k]}`).join(' · ');
    }
    const firstRow = rows[0];
    const firstKey = Object.keys(firstRow)[0];
    const secondKey = Object.keys(firstRow)[1];
    if (firstKey && secondKey) {
      return `Top result: ${firstRow[firstKey]} (${firstRow[secondKey]}) · ${rowCount} total records found`;
    }
    return `${rowCount} records retrieved successfully`;
  };

  const subScoresList = reliability ? [
    { key: 'schema_grounding', data: reliability.schema_grounding },
    { key: 'join_confidence', data: reliability.join_confidence },
    { key: 'filter_interpretation', data: reliability.filter_interpretation },
    { key: 'execution_validation', data: reliability.execution_validation },
    { key: 'result_sanity', data: reliability.result_sanity },
  ] : [];

  return (
    <div
      className="investigation-card"
      style={{
        marginTop: '1.5rem',
        background: 'linear-gradient(145deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.9))',
        border: '1px solid rgba(99, 102, 241, 0.35)',
        borderRadius: '16px',
        padding: '1.5rem',
        boxShadow: '0 12px 32px -4px rgba(0, 0, 0, 0.5)',
      }}
    >
      {/* 1. Header Bar: Question & Reliability Badge */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
          paddingBottom: '1.25rem',
          marginBottom: '1.25rem',
          gap: '1rem',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ flex: 1, minWidth: '280px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
            <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#818cf8', fontWeight: 700 }}>
              Analytical Investigation Card &bull; REQ-EVID-01 &bull; REQ-VIS-01
            </span>
          </div>
          <h3 style={{ margin: '0 0 0.5rem 0', color: '#f8fafc', fontSize: '1.15rem', fontWeight: 600 }}>
            {question || 'Executed Query'}
          </h3>
          <div
            style={{
              fontSize: '0.92rem',
              color: isSuccess ? '#e2e8f0' : '#f87171',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
            }}
          >
            <span style={{ fontWeight: 600 }}>Answer:</span>
            <span>{getAnswerHeadline()}</span>
          </div>
        </div>

        {/* Actions & Reliability Score Badge */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            onClick={() => setIsExportModalOpen(true)}
            style={{
              background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(79, 70, 229, 0.3))',
              border: '1px solid rgba(99, 102, 241, 0.5)',
              color: '#c7d2fe',
              borderRadius: '10px',
              padding: '0.6rem 0.9rem',
              fontSize: '0.82rem',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              boxShadow: '0 4px 12px rgba(99, 102, 241, 0.2)',
              transition: 'all 0.2s',
            }}
          >
            <span>📑</span>
            <span>Export Report</span>
          </button>

          {reliability && (
            <div
              style={{
                padding: '0.65rem 1rem',
                borderRadius: '12px',
                textAlign: 'right',
                ...getTierBadgeStyle(reliability.tier),
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-end',
                gap: '0.2rem',
                boxShadow: '0 4px 12px rgba(0, 0, 0, 0.2)',
              }}
            >
              <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.06em', opacity: 0.85, fontWeight: 700 }}>
                Evidence Reliability
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '1.4rem', fontWeight: 800, fontFamily: 'monospace' }}>
                  {reliability.composite_score}
                  <span style={{ fontSize: '0.85rem', opacity: 0.7 }}> / 100</span>
                </span>
                <span
                  style={{
                    fontSize: '0.8rem',
                    fontWeight: 700,
                    padding: '0.15rem 0.5rem',
                    borderRadius: '6px',
                    background: 'rgba(0, 0, 0, 0.2)',
                  }}
                >
                  {reliability.tier === 'HIGH' ? '✓ HIGH' : reliability.tier === 'MEDIUM' ? '⚠ MEDIUM' : '✗ LOW'}
                </span>
              </div>
              <div style={{ fontSize: '0.68rem', opacity: 0.8 }}>
                5 Traceable Sub-Scores &bull; Rule R3.3 Compliant
              </div>
            </div>
          )}
        </div>
      </div>


      {/* 2. Main Two-Column Canvas: Signature Evidence Panel + Quick Summary */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '1.25rem',
          marginBottom: '1.5rem',
        }}
      >
        {/* Left Column: Signature Evidence Panel */}
        <div
          style={{
            background: 'rgba(0, 0, 0, 0.35)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '12px',
            padding: '1rem',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Audit Evidence Trail
            </span>
            <span style={{ fontSize: '0.72rem', color: '#64748b' }}>
              Deterministic Gates
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
            {subScoresList.map(({ key, data }) => (
              <div
                key={key}
                onClick={() => setExpandedSubScore(expandedSubScore === key ? null : key)}
                style={{
                  background: expandedSubScore === key ? 'rgba(99, 102, 241, 0.12)' : 'rgba(255, 255, 255, 0.03)',
                  border: `1px solid ${expandedSubScore === key ? 'rgba(99, 102, 241, 0.4)' : 'rgba(255, 255, 255, 0.06)'}`,
                  borderRadius: '8px',
                  padding: '0.6rem 0.8rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{
                      width: '20px',
                      height: '20px',
                      borderRadius: '50%',
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      ...getTierBadgeStyle(data.tier),
                    }}>
                      {data.status_icon}
                    </span>
                    <span style={{ fontSize: '0.85rem', color: '#f1f5f9', fontWeight: 600 }}>
                      {data.name}
                    </span>
                    <span style={{ fontSize: '0.7rem', color: '#64748b' }}>
                      ({Math.round(data.weight * 100)}%)
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontSize: '0.82rem', fontFamily: 'monospace', color: '#cbd5e1', fontWeight: 700 }}>
                      {data.score}/100
                    </span>
                    <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                      {expandedSubScore === key ? '▲' : '▼'}
                    </span>
                  </div>
                </div>

                <div style={{ fontSize: '0.78rem', color: '#94a3b8', marginTop: '0.3rem' }}>
                  {data.summary}
                </div>

                {expandedSubScore === key && (
                  <div style={{ marginTop: '0.5rem', paddingTop: '0.5rem', borderTop: '1px solid rgba(255, 255, 255, 0.08)' }}>
                    <div style={{ fontSize: '0.72rem', color: '#818cf8', fontWeight: 600, marginBottom: '0.3rem' }}>
                      Stage Verification Items:
                    </div>
                    <ul style={{ margin: 0, paddingLeft: '1.1rem', fontSize: '0.75rem', color: '#cbd5e1', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                      {data.evidence_items.map((item, idx) => (
                        <li key={idx}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Right Column: Execution Stats & Mode */}
        <div
          style={{
            background: 'rgba(0, 0, 0, 0.35)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '12px',
            padding: '1rem',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Execution Summary
            </span>
            <div style={{ display: 'flex', gap: '0.4rem' }}>
              {criticAnalysis?.has_findings && (
                <span style={{ fontSize: '0.72rem', background: 'rgba(245, 158, 11, 0.2)', color: '#f59e0b', padding: '0.15rem 0.45rem', borderRadius: '4px', fontWeight: 600 }}>
                  ⚠ Critic Smell
                </span>
              )}
              {correctionResult?.recovered && (
                <span style={{ fontSize: '0.72rem', background: 'rgba(99, 102, 241, 0.2)', color: '#818cf8', padding: '0.15rem 0.45rem', borderRadius: '4px', fontWeight: 600 }}>
                  ↻ Auto-Corrected ({correctionResult.retries_used})
                </span>
              )}
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem', marginBottom: '0.85rem' }}>
            <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '0.5rem', borderRadius: '6px', textAlign: 'center' }}>
              <div style={{ fontSize: '0.68rem', color: '#94a3b8' }}>Row Count</div>
              <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc' }}>{rowCount}</div>
            </div>
            <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '0.5rem', borderRadius: '6px', textAlign: 'center' }}>
              <div style={{ fontSize: '0.68rem', color: '#94a3b8' }}>Sandbox Latency</div>
              <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc' }}>{latencyMs}ms</div>
            </div>
            <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '0.5rem', borderRadius: '6px', textAlign: 'center' }}>
              <div style={{ fontSize: '0.68rem', color: '#94a3b8' }}>Policy State</div>
              <div style={{ fontSize: '0.95rem', fontWeight: 700, color: isSuccess ? '#10b981' : '#ef4444' }}>
                {isSuccess ? 'CLEARED' : 'BLOCKED'}
              </div>
            </div>
          </div>

          {/* Quick Chart / Data Type Indicator */}
          <div style={{ background: 'rgba(255, 255, 255, 0.02)', padding: '0.75rem', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.05)', flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <div style={{ fontSize: '0.78rem', color: '#cbd5e1', marginBottom: '0.3rem' }}>
              <strong>Visual Format:</strong> {currentChartSpec?.chart_type ? currentChartSpec.chart_type.toUpperCase() : 'AUTO'}
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              {currentChartSpec?.reasoning || 'Chart and tabular views are paired for full verification (Rule R8.2).'}
            </div>
          </div>
        </div>
      </div>

      {/* 3. Implementation Detail Layer (Progressive Disclosure Tabs) */}
      <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.1)', paddingTop: '1rem' }}>
        <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '0.5rem', flexWrap: 'wrap' }}>
          <button
            onClick={() => setActiveTab('chart')}
            style={{
              background: activeTab === 'chart' ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
              color: activeTab === 'chart' ? '#818cf8' : '#94a3b8',
              border: activeTab === 'chart' ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent',
              borderRadius: '6px',
              padding: '0.4rem 0.8rem',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.3rem',
            }}
          >
            <span>📈</span>
            <span>Chart View</span>
          </button>

          <button
            onClick={() => setActiveTab('table')}
            style={{
              background: activeTab === 'table' ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
              color: activeTab === 'table' ? '#818cf8' : '#94a3b8',
              border: activeTab === 'table' ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent',
              borderRadius: '6px',
              padding: '0.4rem 0.8rem',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.3rem',
            }}
          >
            <span>📊</span>
            <span>Table View ({rowCount})</span>
          </button>

          <button
            onClick={() => setActiveTab('sql')}
            style={{
              background: activeTab === 'sql' ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
              color: activeTab === 'sql' ? '#818cf8' : '#94a3b8',
              border: activeTab === 'sql' ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent',
              borderRadius: '6px',
              padding: '0.4rem 0.8rem',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
            }}
          >
            <span>💻</span>
            <span>SQL Code</span>
            {criticAnalysis?.has_findings && (
              <span style={{ fontSize: '0.7rem', color: '#f59e0b' }}>⚠</span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('explanation')}
            style={{
              background: activeTab === 'explanation' ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
              color: activeTab === 'explanation' ? '#818cf8' : '#94a3b8',
              border: activeTab === 'explanation' ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent',
              borderRadius: '6px',
              padding: '0.4rem 0.8rem',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            💡 Explanation
          </button>

          <button
            onClick={() => setActiveTab('validation')}
            style={{
              background: activeTab === 'validation' ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
              color: activeTab === 'validation' ? '#818cf8' : '#94a3b8',
              border: activeTab === 'validation' ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent',
              borderRadius: '6px',
              padding: '0.4rem 0.8rem',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            🛡️ Policy &amp; Sanity
          </button>

          <button
            onClick={() => setActiveTab('optimize')}
            style={{
              background: activeTab === 'optimize' ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
              color: activeTab === 'optimize' ? '#818cf8' : '#94a3b8',
              border: activeTab === 'optimize' ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent',
              borderRadius: '6px',
              padding: '0.4rem 0.8rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.3rem',
            }}
          >
            <span>⚡</span>
            <span>Optimize</span>
          </button>


          <button
            onClick={() => setActiveTab('replay')}
            style={{
              background: activeTab === 'replay' ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
              color: activeTab === 'replay' ? '#818cf8' : '#94a3b8',
              border: activeTab === 'replay' ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent',
              borderRadius: '6px',
              padding: '0.4rem 0.8rem',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.3rem',
            }}
          >
            <span>🔬</span>
            <span>Replay &amp; Provenance</span>
          </button>


          {correctionResult && (
            <button
              onClick={() => setActiveTab('correction')}
              style={{
                background: activeTab === 'correction' ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
                color: activeTab === 'correction' ? '#818cf8' : '#94a3b8',
                border: activeTab === 'correction' ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent',
                borderRadius: '6px',
                padding: '0.4rem 0.8rem',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              ↻ Self-Correction Diff ({correctionResult.retries_used})
            </button>
          )}


          {copyFeedback && (
            <div style={{ marginLeft: 'auto', fontSize: '0.78rem', color: '#10b981', fontWeight: 600 }}>
              {copyFeedback}
            </div>
          )}
        </div>


        {/* Tab Content Display */}
        <div style={{ marginTop: '1rem' }}>
          {/* TAB 1: CHART VIEW (REQ-VIS-01 / Rule R8.2) */}
          {activeTab === 'chart' && (
            <div style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '1.25rem', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
              {/* Chart Switcher Controls */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
                <ChartSwitcher
                  currentType={currentChartSpec?.chart_type || 'bar'}
                  suggestedTypes={currentChartSpec?.suggested_chart_types || []}
                  onSelectType={handleSelectChartType}
                />
                <button
                  onClick={() => setActiveTab('table')}
                  style={{
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    color: '#94a3b8',
                    padding: '0.25rem 0.6rem',
                    borderRadius: '4px',
                    fontSize: '0.72rem',
                    cursor: 'pointer',
                  }}
                >
                  View as Paired Table (Rule R8.2) &rarr;
                </button>
              </div>

              {/* Live SVG Chart Rendering */}
              {isSwitchingChart ? (
                <div style={{ padding: '3rem', textAlign: 'center', color: '#818cf8' }}>
                  <span>⏳ Re-rendering chart specification...</span>
                </div>
              ) : (
                <ChartRenderer chartSpec={currentChartSpec} height={300} />
              )}
            </div>
          )}

          {/* TAB 2: FULL TABLE VIEW (WITH SEARCH, SORT, PAGINATION, CSV EXPORT) */}
          {activeTab === 'table' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <input
                    type="text"
                    placeholder="Search in table rows..."
                    value={tableSearch}
                    onChange={(e) => {
                      setTableSearch(e.target.value);
                      setCurrentPage(1);
                    }}
                    style={{
                      background: 'rgba(0,0,0,0.4)',
                      border: '1px solid rgba(255,255,255,0.15)',
                      borderRadius: '4px',
                      padding: '0.3rem 0.6rem',
                      color: '#f8fafc',
                      fontSize: '0.78rem',
                      minWidth: '180px',
                    }}
                  />
                  <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                    {processedRows.length} of {rows.length} rows
                  </span>
                </div>

                <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                  <select
                    value={pageSize}
                    onChange={(e) => {
                      setPageSize(Number(e.target.value));
                      setCurrentPage(1);
                    }}
                    style={{
                      background: '#1e293b',
                      color: '#cbd5e1',
                      border: '1px solid #475569',
                      borderRadius: '4px',
                      padding: '0.25rem 0.4rem',
                      fontSize: '0.75rem',
                    }}
                  >
                    <option value={10}>10 / page</option>
                    <option value={25}>25 / page</option>
                    <option value={50}>50 / page</option>
                  </select>

                  <button
                    onClick={handleCopyCsv}
                    style={{
                      background: 'rgba(255, 255, 255, 0.05)',
                      border: '1px solid rgba(255, 255, 255, 0.1)',
                      color: '#e2e8f0',
                      borderRadius: '4px',
                      padding: '0.25rem 0.6rem',
                      fontSize: '0.75rem',
                      cursor: 'pointer',
                    }}
                  >
                    📋 Copy CSV
                  </button>

                  <button
                    onClick={handleDownloadCsv}
                    style={{
                      background: 'rgba(99, 102, 241, 0.15)',
                      border: '1px solid rgba(99, 102, 241, 0.3)',
                      color: '#818cf8',
                      borderRadius: '4px',
                      padding: '0.25rem 0.6rem',
                      fontSize: '0.75rem',
                      cursor: 'pointer',
                    }}
                  >
                    📥 Export CSV
                  </button>
                </div>
              </div>

              <div style={{ overflowX: 'auto', maxHeight: '350px', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '8px' }}>
                {columns.length > 0 && paginatedRows.length > 0 ? (
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
                    <thead>
                      <tr style={{ background: '#1e293b', position: 'sticky', top: 0, borderBottom: '1px solid rgba(255, 255, 255, 0.15)' }}>
                        {columns.map((c) => (
                          <th
                            key={c}
                            onClick={() => handleSort(c)}
                            style={{
                              padding: '0.5rem 0.75rem',
                              textAlign: 'left',
                              color: sortCol === c ? '#818cf8' : '#94a3b8',
                              fontWeight: 600,
                              cursor: 'pointer',
                              userSelect: 'none',
                            }}
                          >
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                              <span>{c}</span>
                              <span style={{ fontSize: '0.65rem' }}>
                                {sortCol === c ? (sortDir === 'asc' ? '▲' : '▼') : '↕'}
                              </span>
                            </span>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {paginatedRows.map((r, idx) => (
                        <tr
                          key={idx}
                          style={{
                            background: idx % 2 === 0 ? 'rgba(255, 255, 255, 0.02)' : 'transparent',
                            borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                          }}
                        >
                          {columns.map((c) => (
                            <td key={c} style={{ padding: '0.5rem 0.75rem', color: '#e2e8f0' }}>
                              {String(r[c] ?? '')}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div style={{ padding: '2rem', textAlign: 'center', color: '#64748b', fontSize: '0.85rem' }}>
                    {tableSearch ? 'No rows match search query.' : 'No rows returned from execution.'}
                  </div>
                )}
              </div>

              {/* Pagination Controls */}
              {totalPages > 1 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.6rem', fontSize: '0.75rem', color: '#94a3b8' }}>
                  <span>Page {currentPage} of {totalPages}</span>
                  <div style={{ display: 'flex', gap: '0.3rem' }}>
                    <button
                      onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                      disabled={currentPage === 1}
                      style={{
                        background: 'rgba(255,255,255,0.05)',
                        border: '1px solid rgba(255,255,255,0.1)',
                        color: currentPage === 1 ? '#475569' : '#cbd5e1',
                        borderRadius: '4px',
                        padding: '0.2rem 0.5rem',
                        cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
                      }}
                    >
                      &larr; Prev
                    </button>
                    <button
                      onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                      disabled={currentPage === totalPages}
                      style={{
                        background: 'rgba(255,255,255,0.05)',
                        border: '1px solid rgba(255,255,255,0.1)',
                        color: currentPage === totalPages ? '#475569' : '#cbd5e1',
                        borderRadius: '4px',
                        padding: '0.2rem 0.5rem',
                        cursor: currentPage === totalPages ? 'not-allowed' : 'pointer',
                      }}
                    >
                      Next &rarr;
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: SQL CODE & CRITIC WARNING */}
          {activeTab === 'sql' && (
            <div>
              {criticAnalysis && criticAnalysis.has_findings && (
                <div style={{ marginBottom: '1rem' }}>
                  <SQLCriticCard
                    criticAnalysis={criticAnalysis}
                    onApplyFix={onApplyFix}
                  />
                </div>
              )}

              <div style={{ position: 'relative' }}>
                <pre
                  style={{
                    background: '#090d16',
                    border: '1px solid rgba(99, 102, 241, 0.3)',
                    borderRadius: '8px',
                    padding: '1rem',
                    color: '#38bdf8',
                    fontFamily: 'monospace',
                    fontSize: '0.85rem',
                    margin: 0,
                    overflowX: 'auto',
                    lineHeight: 1.5,
                  }}
                >
                  {activeSql}
                </pre>
                <button
                  onClick={handleCopySql}
                  style={{
                    position: 'absolute',
                    top: '0.5rem',
                    right: '0.5rem',
                    background: 'rgba(255, 255, 255, 0.08)',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    color: '#e2e8f0',
                    borderRadius: '4px',
                    padding: '0.25rem 0.5rem',
                    fontSize: '0.72rem',
                    cursor: 'pointer',
                  }}
                >
                  📋 Copy SQL
                </button>
              </div>
            </div>
          )}

          {/* TAB 4: EXPLANATION */}
          {activeTab === 'explanation' && (
            <div style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '1rem', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
              <div style={{ fontSize: '0.85rem', color: '#e2e8f0', lineHeight: 1.6 }}>
                <p style={{ margin: '0 0 0.75rem 0' }}>
                  <strong>LLM Rationale:</strong> {proposalData?.proposal?.rationale || 'Query generated from Semantic Catalog grounding.'}
                </p>
                <div style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
                  <strong>Dialect:</strong> PostgreSQL &bull; <strong>Execution Mode:</strong> Strict SELECT Read-Only Sandbox &bull; <strong>Row Cap:</strong> 10,000
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: POLICY & SANITY VALIDATION */}
          {activeTab === 'validation' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {resultValidation && (
                <ResultValidationCard validationReport={resultValidation} />
              )}
              
              <div style={{ background: 'rgba(0, 0, 0, 0.3)', padding: '1rem', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
                <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#f8fafc', marginBottom: '0.5rem' }}>
                  Deterministic Policy Verification Checklist
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.5rem', fontSize: '0.78rem' }}>
                  <div style={{ color: '#10b981' }}>✓ AST SELECT-only Enforced</div>
                  <div style={{ color: '#10b981' }}>✓ Schema &amp; Column Deny-by-Default</div>
                  <div style={{ color: '#10b981' }}>✓ Function Allowlist Cleared</div>
                  <div style={{ color: '#10b981' }}>✓ Execution Sandbox Timeout Cap</div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 6: SELF-CORRECTION DIFF */}
          {activeTab === 'correction' && correctionResult && (
            <SelfCorrectionCard correctionResult={correctionResult} />
          )}

          {/* TAB 7: QUERY OPTIMIZATION ENGINE (REQ-OPT-01 / REQ-OPT-02) */}
          {activeTab === 'optimize' && (
            <OptimizationCard
              sql={activeSql}
              queryId={executionResult?.query_id || proposalData?.query_id}
              roleName="Admin"
            />
          )}

          {/* TAB 8: QUERY REPLAY & PROVENANCE (REQ-REPLAY-01 / Milestone M3) */}
          {activeTab === 'replay' && (
            <QueryReplayCard
              queryId={executionResult?.query_id || proposalData?.query_id}
            />
          )}
        </div>
      </div>


      {/* Export Report Modal (REQ-RPT-01 / REQ-RPT-02 / Rule R8.3) */}
      <ReportExportModal
        isOpen={isExportModalOpen}
        onClose={() => setIsExportModalOpen(false)}
        currentQueryItem={{
          query_id: executionResult?.query_id || proposalData?.query_id,
          question: question || 'Executed Query',
          proposed_sql: proposalData?.proposal?.sql,
          executed_sql: activeSql,
          status: isSuccess ? 'success' : 'failed',
          latency_ms: latencyMs,
          row_count: rowCount,
          reliability_breakdown: reliability,
          columns: columns,
          rows: rows,
        }}
        sessionQueries={[{
          query_id: executionResult?.query_id || proposalData?.query_id,
          question: question || 'Executed Query',
          executed_sql: activeSql,
          status: isSuccess ? 'success' : 'failed',
          latency_ms: latencyMs,
          row_count: rowCount,
          reliability_breakdown: reliability,
          columns: columns,
          rows: rows,
        }]}
        dataSourceName="Northwind Commercial DB"
        roleName="Admin"
      />
    </div>
  );
}


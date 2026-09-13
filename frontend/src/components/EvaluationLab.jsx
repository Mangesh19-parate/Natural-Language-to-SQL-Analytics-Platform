import React, { useState, useEffect } from 'react';

export default function EvaluationLab() {
  const [isRunning, setIsRunning] = useState(false);
  const [evalData, setEvalData] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState('ALL');
  const [selectedVariant, setSelectedVariant] = useState('baseline_d_proposed');
  const [lastExecuted, setLastExecuted] = useState(null);

  useEffect(() => {
    fetchLatestEvaluationRun();
  }, []);

  const fetchLatestEvaluationRun = async () => {
    try {
      const res = await fetch('/api/lab/evaluation/latest');
      const data = await res.json();
      if (data.success && data.data) {
        setEvalData(data.data);
        setLastExecuted(data.data.executed_at);
      } else {
        runBenchmark();
      }
    } catch (err) {
      console.error('Failed to fetch latest evaluation run:', err);
      runBenchmark();
    }
  };

  const runBenchmark = async () => {
    setIsRunning(true);
    try {
      const res = await fetch('/api/lab/evaluation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          data_source_id: 1,
        }),
      });
      const data = await res.json();
      if (data.success && data.data) {
        setEvalData(data.data);
        setLastExecuted(data.data.executed_at);
      }
    } catch (err) {
      console.error('Evaluation benchmark run failed:', err);
    } finally {
      setIsRunning(false);
    }
  };

  const categories = evalData?.category_breakdown || [];
  const detailedResults = evalData?.detailed_results || [];
  const overallMetrics = evalData?.overall_metrics || {};

  const filteredDetailedResults = detailedResults.filter((r) => {
    const matchesCategory = selectedCategory === 'ALL' || r.category === selectedCategory;
    const matchesVariant = selectedVariant === 'ALL' || r.baseline_variant === selectedVariant;
    return matchesCategory && matchesVariant;
  });

  const getVariantLabel = (v) => {
    switch (v) {
      case 'baseline_a_plain_llm':
        return 'Baseline A (Plain LLM)';
      case 'baseline_b_schema_aware':
        return 'Baseline B (Schema-Aware)';
      case 'baseline_c_schema_and_correction':
        return 'Baseline C (+Correction)';
      case 'baseline_d_proposed':
        return 'Baseline D (Trust Engine)';
      default:
        return v;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Banner & Run Action */}
      <div className="card" style={{ background: 'linear-gradient(135deg, rgba(99,102,241,0.08) 0%, rgba(16,185,129,0.08) 100%)', border: '1px solid rgba(99,102,241,0.2)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.3rem' }}>
              <span style={{ fontSize: '1.25rem' }}>📊</span>
              <h2 style={{ fontSize: '1.2rem', fontWeight: 700, margin: 0, color: '#f8fafc' }}>
                Evaluation Lab Harness (REQ-EVALLAB-01 &bull; Task T-32)
              </h2>
              <span style={{ background: 'rgba(99,102,241,0.15)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.3)', padding: '0.15rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 600 }}>
                4-BASELINE COMPARISON
              </span>
            </div>
            <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Standing comparative benchmark measuring execution success, safety violations, and repair efficacy across Baselines A (Plain LLM), B (Schema-Aware), C (+Correction), and D (Trust Engine).
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            {lastExecuted && (
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textAlign: 'right' }}>
                <div>Last Benchmark:</div>
                <div style={{ color: '#cbd5e1', fontWeight: 600 }}>{new Date(lastExecuted).toLocaleTimeString()}</div>
              </div>
            )}
            <button
              onClick={runBenchmark}
              disabled={isRunning}
              style={{
                background: isRunning ? '#475569' : 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
                color: '#fff',
                border: 'none',
                borderRadius: '8px',
                padding: '0.65rem 1.25rem',
                fontSize: '0.9rem',
                fontWeight: 600,
                cursor: isRunning ? 'not-allowed' : 'pointer',
                boxShadow: '0 4px 14px rgba(99, 102, 241, 0.3)',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                transition: 'all 0.2s',
              }}
            >
              {isRunning ? (
                <>
                  <span style={{ display: 'inline-block', animation: 'spin 1s linear infinite' }}>⏳</span>
                  <span>Running Benchmark...</span>
                </>
              ) : (
                <>
                  <span>⚡ Run Comparative Benchmark</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* 4-Baseline Overall Comparison Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
        <div className="card" style={{ padding: '1rem', borderTop: '4px solid #64748b' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>BASELINE A: PLAIN LLM</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#94a3b8' }}>
            {overallMetrics.baseline_a_overall_success || 0}% <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Success</span>
          </div>
          <div style={{ fontSize: '0.75rem', color: '#ef4444', marginTop: '0.3rem' }}>No Catalog &bull; High Hallucination</div>
        </div>

        <div className="card" style={{ padding: '1rem', borderTop: '4px solid #38bdf8' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>BASELINE B: SCHEMA-AWARE</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#38bdf8' }}>
            {overallMetrics.baseline_b_overall_success || 0}% <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Success</span>
          </div>
          <div style={{ fontSize: '0.75rem', color: '#38bdf8', marginTop: '0.3rem' }}>Catalog Grounded Prompt</div>
        </div>

        <div className="card" style={{ padding: '1rem', borderTop: '4px solid #818cf8' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>BASELINE C: +SELF-CORRECTION</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#818cf8' }}>
            {overallMetrics.baseline_c_overall_success || 0}% <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Success</span>
          </div>
          <div style={{ fontSize: '0.75rem', color: '#818cf8', marginTop: '0.3rem' }}>E1–E7 Sandbox Retry Loop</div>
        </div>

        <div className="card" style={{ padding: '1rem', borderTop: '4px solid #10b981', background: 'rgba(16,185,129,0.04)' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>BASELINE D: TRUST ENGINE</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#10b981' }}>
            {overallMetrics.baseline_d_overall_success || 0}% <span style={{ fontSize: '0.8rem', color: '#10b981' }}>Success</span>
          </div>
          <div style={{ fontSize: '0.75rem', color: '#10b981', marginTop: '0.3rem' }}>0.00% Safety Violations (Hard Gate)</div>
        </div>
      </div>

      {/* Category Performance Matrix */}
      <div className="card" style={{ padding: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <div>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#f8fafc', margin: '0 0 0.2rem 0' }}>
              Category Performance Matrix (9 Benchmark Domains)
            </h3>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Comparison across standard business queries, complex nested joins, adversarial injections, and unauthorized attempts.
            </span>
          </div>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
            <thead>
              <tr style={{ background: 'rgba(255, 255, 255, 0.03)', borderBottom: '1px solid rgba(255, 255, 255, 0.1)', textAlign: 'left' }}>
                <th style={{ padding: '0.65rem 0.8rem', color: 'var(--text-muted)' }}>CATEGORY</th>
                <th style={{ padding: '0.65rem 0.8rem', color: 'var(--text-muted)', textAlign: 'center' }}>QUESTIONS</th>
                <th style={{ padding: '0.65rem 0.8rem', color: '#94a3b8', textAlign: 'center' }}>BASE A (PLAIN)</th>
                <th style={{ padding: '0.65rem 0.8rem', color: '#38bdf8', textAlign: 'center' }}>BASE B (SCHEMA)</th>
                <th style={{ padding: '0.65rem 0.8rem', color: '#818cf8', textAlign: 'center' }}>BASE C (+CORRECT)</th>
                <th style={{ padding: '0.65rem 0.8rem', color: '#10b981', textAlign: 'center' }}>BASE D (TRUST ENGINE)</th>
                <th style={{ padding: '0.65rem 0.8rem', color: 'var(--text-muted)', textAlign: 'center' }}>D SAFETY VIOLATION</th>
                <th style={{ padding: '0.65rem 0.8rem', color: 'var(--text-muted)', textAlign: 'center' }}>D AVG LATENCY</th>
              </tr>
            </thead>
            <tbody>
              {categories.map((row) => (
                <tr
                  key={row.category}
                  style={{
                    borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
                  }}
                >
                  <td style={{ padding: '0.65rem 0.8rem', fontWeight: 600, color: '#f1f5f9', textTransform: 'capitalize' }}>
                    {row.category}
                  </td>
                  <td style={{ padding: '0.65rem 0.8rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                    {row.question_count}
                  </td>
                  <td style={{ padding: '0.65rem 0.8rem', textAlign: 'center', color: '#94a3b8' }}>
                    {row.baseline_a_success}%
                  </td>
                  <td style={{ padding: '0.65rem 0.8rem', textAlign: 'center', color: '#38bdf8' }}>
                    {row.baseline_b_success}%
                  </td>
                  <td style={{ padding: '0.65rem 0.8rem', textAlign: 'center', color: '#818cf8' }}>
                    {row.baseline_c_success}%
                  </td>
                  <td style={{ padding: '0.65rem 0.8rem', textAlign: 'center' }}>
                    <span
                      style={{
                        background: 'rgba(16, 185, 129, 0.15)',
                        color: '#10b981',
                        border: '1px solid rgba(16, 185, 129, 0.3)',
                        padding: '0.2rem 0.5rem',
                        borderRadius: '4px',
                        fontWeight: 700,
                      }}
                    >
                      {row.baseline_d_success}%
                    </span>
                  </td>
                  <td style={{ padding: '0.65rem 0.8rem', textAlign: 'center', color: '#10b981', fontWeight: 600 }}>
                    {row.baseline_d_safety_violation.toFixed(1)}%
                  </td>
                  <td style={{ padding: '0.65rem 0.8rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                    {row.baseline_d_avg_latency_ms} ms
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detailed Benchmark Questions Drawer */}
      <div className="card" style={{ padding: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc', margin: '0 0 0.2rem 0' }}>
              Detailed Question Evaluation Results
            </h3>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Inspect individual questions, execution correctness, and reliability scores.
            </span>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <select
              value={selectedVariant}
              onChange={(e) => setSelectedVariant(e.target.value)}
              style={{
                background: '#1e293b',
                color: '#fff',
                border: '1px solid #475569',
                borderRadius: '6px',
                padding: '0.35rem 0.6rem',
                fontSize: '0.8rem',
              }}
            >
              <option value="ALL">All Baselines</option>
              <option value="baseline_a_plain_llm">Baseline A (Plain LLM)</option>
              <option value="baseline_b_schema_aware">Baseline B (Schema-Aware)</option>
              <option value="baseline_c_schema_and_correction">Baseline C (+Correction)</option>
              <option value="baseline_d_proposed">Baseline D (Trust Engine)</option>
            </select>

            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              style={{
                background: '#1e293b',
                color: '#fff',
                border: '1px solid #475569',
                borderRadius: '6px',
                padding: '0.35rem 0.6rem',
                fontSize: '0.8rem',
              }}
            >
              <option value="ALL">All Categories</option>
              {categories.map((c) => (
                <option key={c.category} value={c.category}>
                  {c.category}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
            <thead>
              <tr style={{ background: 'rgba(255, 255, 255, 0.03)', borderBottom: '1px solid rgba(255, 255, 255, 0.1)', textAlign: 'left' }}>
                <th style={{ padding: '0.5rem 0.75rem', color: 'var(--text-muted)', width: '60px' }}>ID</th>
                <th style={{ padding: '0.5rem 0.75rem', color: 'var(--text-muted)' }}>QUESTION</th>
                <th style={{ padding: '0.5rem 0.75rem', color: 'var(--text-muted)', width: '100px' }}>CATEGORY</th>
                <th style={{ padding: '0.5rem 0.75rem', color: 'var(--text-muted)', width: '150px' }}>VARIANT</th>
                <th style={{ padding: '0.5rem 0.75rem', color: 'var(--text-muted)', width: '90px' }}>EXEC</th>
                <th style={{ padding: '0.5rem 0.75rem', color: 'var(--text-muted)', width: '90px' }}>CORRECT</th>
                <th style={{ padding: '0.5rem 0.75rem', color: 'var(--text-muted)', width: '80px' }}>SAFETY</th>
                <th style={{ padding: '0.5rem 0.75rem', color: 'var(--text-muted)', width: '90px' }}>RELIABILITY</th>
              </tr>
            </thead>
            <tbody>
              {filteredDetailedResults.map((item, idx) => (
                <tr key={idx} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                  <td style={{ padding: '0.5rem 0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>{item.question_id}</td>
                  <td style={{ padding: '0.5rem 0.75rem', color: '#f1f5f9', fontWeight: 500 }}>{item.question}</td>
                  <td style={{ padding: '0.5rem 0.75rem', color: '#cbd5e1', textTransform: 'capitalize' }}>{item.category}</td>
                  <td style={{ padding: '0.5rem 0.75rem', color: '#93c5fd', fontSize: '0.75rem' }}>
                    {getVariantLabel(item.baseline_variant)}
                  </td>
                  <td style={{ padding: '0.5rem 0.75rem' }}>
                    <span
                      style={{
                        color: item.execution_success ? '#10b981' : '#ef4444',
                        fontWeight: 600,
                      }}
                    >
                      {item.execution_success ? '✓ Yes' : '✕ No'}
                    </span>
                  </td>
                  <td style={{ padding: '0.5rem 0.75rem' }}>
                    <span
                      style={{
                        color: item.result_correct ? '#10b981' : '#ef4444',
                        fontWeight: 600,
                      }}
                    >
                      {item.result_correct ? '✓ Yes' : '✕ No'}
                    </span>
                  </td>
                  <td style={{ padding: '0.5rem 0.75rem' }}>
                    <span
                      style={{
                        color: item.safety_violation ? '#ef4444' : '#10b981',
                        fontWeight: 600,
                      }}
                    >
                      {item.safety_violation ? '✕ VIOLATION' : '✓ Clean'}
                    </span>
                  </td>
                  <td style={{ padding: '0.5rem 0.75rem', color: '#f59e0b', fontWeight: 700 }}>
                    {item.reliability_score !== null && item.reliability_score !== undefined
                      ? `${item.reliability_score}`
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

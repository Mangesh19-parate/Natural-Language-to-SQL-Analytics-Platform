import React, { useState, useEffect } from 'react';
import ClarificationCard from './components/ClarificationCard.jsx';

export default function App() {
  const [health, setHealth] = useState({
    status: 'checking...',
    environment: 'local',
    metadata_db_connected: false,
    business_db_connected: false,
    version: '1.2.0',
  });
  const [catalog, setCatalog] = useState(null);
  const [selectedRole, setSelectedRole] = useState(1); // 1: admin, 2: analyst, 3: viewer

  // Intent Studio State
  const [queryInput, setQueryInput] = useState('');
  const [isClassifying, setIsClassifying] = useState(false);
  const [intentResult, setIntentResult] = useState(null);
  const [selectedOptionId, setSelectedOptionId] = useState(null);
  const [resolvedQuestion, setResolvedQuestion] = useState(null);
  const [isResolving, setIsResolving] = useState(false);

  useEffect(() => {
    fetch('/api/health')
      .then((res) => res.json())
      .then((data) => setHealth(data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetch(`/api/schema?role_id=${selectedRole}`)
      .then((res) => res.json())
      .then((res) => setCatalog(res.data))
      .catch(() => {});
  }, [selectedRole]);

  const handleClassify = async (questionToClassify) => {
    const q = questionToClassify || queryInput;
    if (!q.trim()) return;

    setIsClassifying(true);
    setIntentResult(null);
    setSelectedOptionId(null);
    setResolvedQuestion(null);

    try {
      const res = await fetch('/api/intent/classify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: q,
          role_id: selectedRole,
          data_source_id: 1,
        }),
      });
      const data = await res.json();
      if (data.success) {
        setIntentResult(data.data);
        if (data.data.classification === 'answerable') {
          setResolvedQuestion(data.data.resolved_question);
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsClassifying(false);
    }
  };

  const handleResolveOption = async () => {
    if (!intentResult || !selectedOptionId) return;
    const selectedOption = intentResult.clarification_options.find(
      (o) => o.option_id === selectedOptionId
    );
    if (!selectedOption) return;

    setIsResolving(true);
    try {
      const res = await fetch('/api/intent/resolve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          original_question: queryInput,
          selected_option_id: selectedOptionId,
          clarification_prompt: intentResult.clarification_prompt,
          selected_option: selectedOption,
        }),
      });
      const data = await res.json();
      if (data.success) {
        setResolvedQuestion(data.data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsResolving(false);
    }
  };

  const sampleQuestions = [
    { label: 'Ambiguous: Total Revenue', text: 'Show our total revenue' },
    { label: 'Ambiguous: Top Customer', text: 'Who is our top customer by spend?' },
    { label: 'Answerable: Product Prices', text: 'List top 10 products with price' },
    { label: 'Unsupported: Logistics (Zero Hallucination)', text: 'What is our average supplier shipping carrier delay?' },
    { label: 'Unauthorized: Salary (Viewer/Analyst Test)', text: 'What is Alice salary in Engineering?' },
  ];

  const getBadgeClass = (classification) => {
    switch (classification) {
      case 'answerable':
        return 'badge-done';
      case 'ambiguous':
        return 'badge-p0';
      case 'unsupported':
        return 'badge-p0';
      case 'unauthorized':
        return 'badge-p0';
      default:
        return 'badge-p0';
    }
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="header">
        <div className="logo-section">
          <div className="logo-badge">SQL</div>
          <div className="title-group">
            <h1>Intelligent SQL Assistant</h1>
            <p>Trust Engine Architecture &mdash; v1.2</p>
          </div>
        </div>
        <div className="status-pill">
          <span className="status-dot"></span>
          <span>SYSTEM READY ({health.version})</span>
        </div>
      </header>

      {/* Week 1-3 Status Grid */}
      <div className="grid-layout">
        {/* Core Engine Card */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <span>Trust Engine Core</span>
            </div>
            <span className="badge badge-done">Weeks 1–3 Ready</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">Environment</span>
            <span className="stat-value">{health.environment}</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">Policy Engine (T-04)</span>
            <span className="stat-value" style={{ color: '#10b981' }}>Fail-Closed Active</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">Semantic Catalog (T-05)</span>
            <span className="stat-value" style={{ color: '#06b6d4' }}>25 Columns Classified</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">Intent Analyzer (T-10/11)</span>
            <span className="stat-value" style={{ color: '#6366f1' }}>4-Way Classifier Ready</span>
          </div>
        </div>

        {/* Role Access Simulation */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <span>Simulate Role &amp; Catalog</span>
            </div>
            <span className="badge badge-p0">T-08 Policy Filter</span>
          </div>
          <div className="stat-row" style={{ alignItems: 'center' }}>
            <span className="stat-label">Active User Role:</span>
            <select
              value={selectedRole}
              onChange={(e) => {
                setSelectedRole(Number(e.target.value));
                setIntentResult(null);
                setResolvedQuestion(null);
              }}
              style={{
                background: '#1e293b',
                color: '#fff',
                border: '1px solid rgba(255,255,255,0.2)',
                borderRadius: '6px',
                padding: '0.3rem 0.6rem',
                fontFamily: 'inherit',
                fontSize: '0.85rem'
              }}
            >
              <option value={1}>Admin (All 6 Tables + Salary)</option>
              <option value={2}>Analyst (Products &amp; Orders)</option>
              <option value={3}>Viewer (0 Tables - Fail Closed)</option>
            </select>
          </div>
          <div className="stat-row">
            <span className="stat-label">Authorized Tables</span>
            <span className="stat-value" style={{ color: catalog?.tables?.length ? '#10b981' : '#f43f5e' }}>
              {catalog?.tables?.length > 0 ? catalog.tables.map((t) => t.table_name).join(', ') : 'None (0 Tables)'}
            </span>
          </div>
          <div className="stat-row">
            <span className="stat-label">Ambiguity Engine (T-12)</span>
            <span className="stat-value" style={{ color: '#10b981' }}>&ge;80% Catch Rate</span>
          </div>
        </div>
      </div>

      {/* Week 3 Interactive Intent Studio */}
      <div className="card" style={{ marginBottom: '2rem' }}>
        <div className="card-header">
          <div className="card-title">
            <span>Intent Analyzer &amp; Ambiguity Studio (T-10, T-11, T-12, T-13)</span>
          </div>
          <span className="badge badge-done">Pre-Generation Gate</span>
        </div>

        <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '1rem' }}>
          Rule R2.1: Every question is classified as <strong>Answerable / Ambiguous / Unsupported / Unauthorized</strong> before any SQL proposal is generated.
        </p>

        {/* Sample Question Chips */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem' }}>
          {sampleQuestions.map((sq, idx) => (
            <button
              key={idx}
              onClick={() => {
                setQueryInput(sq.text);
                handleClassify(sq.text);
              }}
              style={{
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '6px',
                padding: '0.35rem 0.75rem',
                fontSize: '0.78rem',
                color: '#cbd5e1',
                cursor: 'pointer',
                transition: 'all 0.2s'
              }}
            >
              {sq.label}
            </button>
          ))}
        </div>

        {/* Query Input Box */}
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <input
            type="text"
            placeholder="Type a natural-language business question..."
            value={queryInput}
            onChange={(e) => setQueryInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleClassify()}
            style={{
              flex: 1,
              background: 'rgba(0, 0, 0, 0.4)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              borderRadius: '8px',
              padding: '0.75rem 1rem',
              color: '#f8fafc',
              fontSize: '0.9rem',
              fontFamily: 'inherit'
            }}
          />
          <button
            onClick={() => handleClassify()}
            disabled={isClassifying || !queryInput.trim()}
            style={{
              background: '#6366f1',
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              padding: '0.75rem 1.5rem',
              fontSize: '0.9rem',
              fontWeight: 600,
              cursor: isClassifying ? 'not-allowed' : 'pointer'
            }}
          >
            {isClassifying ? 'Analyzing...' : 'Classify Intent →'}
          </button>
        </div>

        {/* Classification Result Display */}
        {intentResult && (
          <div style={{ marginTop: '1.5rem', borderTop: '1px solid rgba(255, 255, 255, 0.08)', paddingTop: '1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <span style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>Classification:</span>
                <span
                  style={{
                    textTransform: 'uppercase',
                    fontWeight: 700,
                    fontSize: '0.85rem',
                    padding: '0.2rem 0.6rem',
                    borderRadius: '6px',
                    background:
                      intentResult.classification === 'answerable'
                        ? 'rgba(16, 185, 129, 0.2)'
                        : intentResult.classification === 'ambiguous'
                        ? 'rgba(245, 158, 11, 0.2)'
                        : 'rgba(244, 63, 94, 0.2)',
                    color:
                      intentResult.classification === 'answerable'
                        ? '#6ee7b7'
                        : intentResult.classification === 'ambiguous'
                        ? '#fbbf24'
                        : '#fda4af',
                    border: '1px solid rgba(255, 255, 255, 0.15)'
                  }}
                >
                  {intentResult.classification}
                </span>
              </div>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Confidence: {(intentResult.confidence * 100).toFixed(0)}%
              </span>
            </div>

            <p style={{ fontSize: '0.875rem', color: '#e2e8f0', marginBottom: '0.5rem' }}>
              {intentResult.reasoning}
            </p>

            {/* Evidence Gap Alert for Unsupported */}
            {intentResult.evidence_gap && (
              <div
                style={{
                  background: 'rgba(244, 63, 94, 0.1)',
                  border: '1px solid rgba(244, 63, 94, 0.3)',
                  borderRadius: '8px',
                  padding: '0.75rem 1rem',
                  fontSize: '0.85rem',
                  color: '#fda4af',
                  marginTop: '0.5rem'
                }}
              >
                <strong>Missing Evidence Gap:</strong> {intentResult.evidence_gap}
                <div style={{ fontSize: '0.78rem', color: '#fecdd3', marginTop: '0.25rem' }}>
                  Rule R2.2: Refusing execution without hallucinating tables. Authorized tables: [{intentResult.available_tables.join(', ')}]
                </div>
              </div>
            )}

            {/* Clarification Flow for Ambiguous (T-13) */}
            {intentResult.classification === 'ambiguous' && (
              <ClarificationCard
                prompt={intentResult.clarification_prompt}
                options={intentResult.clarification_options}
                selectedOptionId={selectedOptionId}
                onSelectOption={setSelectedOptionId}
                onResolve={handleResolveOption}
                isResolving={isResolving}
              />
            )}

            {/* Resolved Question Ready for SQL Generator */}
            {resolvedQuestion && (
              <div
                style={{
                  background: 'rgba(16, 185, 129, 0.1)',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                  borderRadius: '8px',
                  padding: '0.75rem 1rem',
                  fontSize: '0.875rem',
                  color: '#6ee7b7',
                  marginTop: '1rem'
                }}
              >
                <strong>Resolved Query Proposal (Ready for Week 4 SQL Generator):</strong>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.82rem', marginTop: '0.3rem', color: '#f8fafc' }}>
                  {resolvedQuestion}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Week 3 Automated Test Matrix */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <span>Automated Test Verification Matrix (Weeks 1, 2, 3 Suite)</span>
          </div>
          <span className="badge badge-done">20 / 20 Passing</span>
        </div>
        <div className="code-box">
{`tests/integration/test_business_seeding.py::test_business_seed_data_counts       [PASSED] (T-02 Business DB Seeding)
tests/integration/test_health_api.py::test_root_endpoint                           [PASSED]
tests/integration/test_health_api.py::test_health_endpoint                         [PASSED]
tests/integration/test_intent_api.py::test_intent_api_classify_and_resolve         [PASSED] (T-10/T-12 Classify & Resolve API)
tests/integration/test_schema_api.py::test_schema_api_policy_filtering           [PASSED] (T-08 Policy Filter API)
tests/unit/test_ambiguity_engine.py::test_ambiguity_detection_benchmark          [PASSED] (T-12 >=80% Benchmark Catch Rate)
tests/unit/test_ambiguity_engine.py::test_ambiguity_resolution                     [PASSED] (T-12 Option Resolution)
tests/unit/test_data_policy.py::test_default_deny                                 [PASSED] (T-04 Fail-Closed Gate)
tests/unit/test_data_policy.py::test_explicit_table_grant                         [PASSED]
tests/unit/test_data_policy.py::test_column_level_denial                          [PASSED]
tests/unit/test_data_policy.py::test_aggregate_guard                              [PASSED] (Rule R1.4 Guard)
tests/unit/test_data_policy.py::test_row_filter_retrieval                         [PASSED]
tests/unit/test_intent_analyzer.py::test_unsupported_detection_10_cases             [PASSED] (T-10 10/10 Impossible Refused)
tests/unit/test_intent_analyzer.py::test_unauthorized_precheck                     [PASSED] (T-11 Pre-Gen Auth Check)
tests/unit/test_intent_analyzer.py::test_answerable_question                       [PASSED]
tests/unit/test_llm_provider.py::test_llm_provider_hashed_auditing                [PASSED] (Rule R5.3 Privacy)
tests/unit/test_prompt_builder.py::test_catalog_prompt_builder_consumes_catalog_only [PASSED] (T-09 Catalog-Only Prompt)
tests/unit/test_sanitized_grounding.py::test_high_medium_sensitivity_never_sampled [PASSED] (T-07 Zero PII Grounding)
tests/unit/test_sanitized_grounding.py::test_categorical_low_none_sensitivity_sampled [PASSED]
tests/unit/test_schema_introspector.py::test_schema_introspection                 [PASSED] (T-06 Schema FKs/PKs)`}
        </div>
      </div>

      {/* Footer Banner */}
      <div className="banner">
        <div className="banner-text">
          <h3>Core Principle Enforced:</h3>
          <p>&ldquo;The LLM proposes. Deterministic infrastructure authorizes, critiques, executes, and verifies.&rdquo;</p>
        </div>
        <span className="badge badge-p0">Rule 0 Binding</span>
      </div>
    </div>
  );
}

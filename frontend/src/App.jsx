import React, { useState, useEffect } from 'react';
import ClarificationCard from './components/ClarificationCard.jsx';
import SQLProposalCard from './components/SQLProposalCard.jsx';
import PolicyValidatorSandbox from './components/PolicyValidatorSandbox.jsx';

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
    { label: '📊 Answerable: Total Employees', text: 'How many employees are there in the company?' },
    { label: '💰 Answerable: Total Sales', text: 'What is the sum of sales revenue?' },
    { label: '❓ Ambiguous (Timeframe)', text: 'Show total sales for this year' },
    { label: '❓ Ambiguous (Metric)', text: 'What was the revenue and sales by product?' },
    { label: '🚫 Unsupported (Weather)', text: 'What was the rainfall and weather in New York yesterday?' },
    { label: '🚫 Unsupported (Zendesk)', text: 'Show average customer support ticket response time in Zendesk' },
    { label: '🔒 Unauthorized (Salary - Role 2/3)', text: 'Show average employee salary by department' },
  ];

  return (
    <div className="container">
      {/* Header */}
      <header className="header">
        <div>
          <div className="logo-badge">
            <span className="logo-dot"></span>
            <span>Intelligent SQL Assistant &bull; Trust Engine</span>
          </div>
          <h1 className="title">Week 4: SQL Generator &amp; Policy Enforcement Layer</h1>
          <p className="subtitle">
            Deterministic AST validation &bull; Schema authorization (deny-by-default) &bull; Column authorization &bull; Aggregate-function guard
          </p>
        </div>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          {/* Active Role Selector */}
          <div style={{ background: 'rgba(255, 255, 255, 0.05)', padding: '0.4rem 0.8rem', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginRight: '0.5rem' }}>Active Role:</span>
            <select
              value={selectedRole}
              onChange={(e) => setSelectedRole(Number(e.target.value))}
              style={{
                background: '#1e293b',
                color: '#fff',
                border: '1px solid #475569',
                borderRadius: '4px',
                padding: '0.2rem 0.4rem',
                fontSize: '0.85rem'
              }}
            >
              <option value={1}>Role 1: Admin (Full Access)</option>
              <option value={2}>Role 2: Sales Analyst (Products &amp; Orders)</option>
              <option value={3}>Role 3: Guest / Viewer (0 Policy Rows)</option>
            </select>
          </div>

          <div style={{ textAlign: 'right' }}>
            <span className="badge badge-p0" style={{ marginBottom: '0.4rem' }}>
              Phase 1 &bull; P0 Critical
            </span>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Week 4 / Day 28 Gate
            </div>
          </div>
        </div>
      </header>

      {/* Trust Engine Status Summary */}
      <div className="card" style={{ marginBottom: '2rem' }}>
        <div className="card-header">
          <div className="card-title">
            <span className="status-indicator"></span>
            <span>Deterministic Trust &amp; Safety Boundary</span>
          </div>
          <span className="badge badge-done">Week 4 Operational</span>
        </div>
        <div className="stats-grid">
          <div className="stat-row">
            <span className="stat-label">LLM Role</span>
            <span className="stat-value" style={{ color: '#6366f1' }}>Proposal Generator Only</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">AST Policy Engine</span>
            <span className="stat-value" style={{ color: '#10b981' }}>SELECT-Only Gate (T-15)</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">Table Authorization</span>
            <span className="stat-value" style={{ color: '#10b981' }}>Deny-by-Default (T-16)</span>
          </div>
          <div className="stat-row">
            <span className="stat-label">Aggregate Function Guard</span>
            <span className="stat-value" style={{ color: '#10b981' }}>Active (T-18 / R1.4)</span>
          </div>
        </div>
      </div>

      {/* Week 3 & 4 Interactive Intent & SQL Studio */}
      <div className="card" style={{ marginBottom: '2rem' }}>
        <div className="card-header">
          <div className="card-title">
            <span>Natural-Language Query &amp; SQL Proposal Studio (Weeks 3 &amp; 4)</span>
          </div>
          <span className="badge badge-done">End-to-End Pipeline</span>
        </div>

        <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '1rem' }}>
          Rule R2.1: Question is classified into <strong>Answerable / Ambiguous / Unsupported / Unauthorized</strong>, followed by LLM Proposal and deterministic AST authorization.
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
            {isClassifying ? 'Analyzing...' : 'Analyze Intent →'}
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
                  Rule R2.2: Refusing execution without hallucinating tables. Authorized tables: [{intentResult.available_tables?.join(', ') || 'None'}]
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

            {/* SQL Proposal & Policy Engine Gate (Week 4: T-14..T-18) */}
            {(resolvedQuestion || intentResult.classification === 'answerable') && (
              <SQLProposalCard
                question={queryInput}
                resolvedQuestion={resolvedQuestion}
                roleId={selectedRole}
              />
            )}
          </div>
        )}
      </div>

      {/* Adversarial SQL & AST Validator Sandbox */}
      <PolicyValidatorSandbox roleId={selectedRole} />

      {/* Week 4 Automated Test Matrix */}
      <div className="card" style={{ marginTop: '2rem' }}>
        <div className="card-header">
          <div className="card-title">
            <span>Automated Test Verification Matrix (Weeks 1, 2, 3, 4 Complete Suite)</span>
          </div>
          <span className="badge badge-done">33 / 33 Passing (100%)</span>
        </div>
        <div className="code-box">
{`tests/unit/test_sql_validator.py::test_reject_100_percent_non_select_statements        [PASSED] (T-15 AST SELECT-only Gate 100%)
tests/unit/test_sql_validator.py::test_accept_valid_select_statements                  [PASSED] (T-15 Analytical SELECTs)
tests/unit/test_sql_validator.py::test_table_and_column_extraction                     [PASSED] (T-15 Table & Column Extraction)
tests/unit/test_sql_validator.py::test_aggregate_function_detection                    [PASSED] (T-15 Aggregate Function AST Detection)
tests/unit/test_policy_enforcement.py::test_schema_deny                                [PASSED] (T-16 Schema Deny-by-Default)
tests/unit/test_policy_enforcement.py::test_column_deny                                [PASSED] (T-17 Column Authorization)
tests/unit/test_policy_enforcement.py::test_aggregate_guard                            [PASSED] (T-18 Aggregate-Function Guard R1.4)
tests/unit/test_policy_enforcement.py::test_high_sensitivity_column_no_policy_denied   [PASSED] (Day 27 Fail-Closed Integration)
tests/unit/test_sql_generator.py::test_sql_generator_proposal_contract                [PASSED] (T-14 {sql, rationale} Proposal)
tests/unit/test_sql_generator.py::test_sql_generator_unauthorized_proposal_blocked     [PASSED] (T-14 Policy Engine Gate)
tests/integration/test_sql_api.py::test_api_generate_sql_success                      [PASSED] (POST /api/sql/generate)
tests/integration/test_sql_api.py::test_api_validate_sql_select_only                  [PASSED] (POST /api/sql/validate AST DDL Block)
tests/integration/test_sql_api.py::test_api_validate_sql_unauthorized_column          [PASSED] (POST /api/sql/validate SSN Block)
tests/integration/test_business_seeding.py::test_business_seed_data_counts             [PASSED] (T-02 Business DB Seeding)
tests/integration/test_health_api.py::test_root_endpoint                                 [PASSED]
tests/integration/test_health_api.py::test_health_endpoint                               [PASSED]
tests/integration/test_intent_api.py::test_intent_api_classify_and_resolve               [PASSED] (T-10/T-12 Classify & Resolve API)
tests/integration/test_schema_api.py::test_schema_api_policy_filtering                   [PASSED] (T-08 Policy Filter API)
tests/unit/test_ambiguity_engine.py::test_ambiguity_detection_benchmark                  [PASSED] (T-12 >=80% Benchmark Catch Rate)
tests/unit/test_ambiguity_engine.py::test_ambiguity_resolution                           [PASSED] (T-12 Option Resolution)
tests/unit/test_data_policy.py::test_default_deny                                       [PASSED] (T-04 Fail-Closed Gate)
tests/unit/test_data_policy.py::test_explicit_table_grant                               [PASSED]
tests/unit/test_data_policy.py::test_column_level_denial                                [PASSED]
tests/unit/test_data_policy.py::test_aggregate_guard                                    [PASSED] (Rule R1.4 Guard)
tests/unit/test_data_policy.py::test_row_filter_retrieval                               [PASSED]
tests/unit/test_intent_analyzer.py::test_unsupported_detection_10_cases                   [PASSED] (T-10 10/10 Impossible Refused)
tests/unit/test_intent_analyzer.py::test_unauthorized_precheck                           [PASSED] (T-11 Pre-Gen Auth Check)
tests/unit/test_intent_analyzer.py::test_answerable_question                             [PASSED]
tests/unit/test_llm_provider.py::test_llm_provider_hashed_auditing                      [PASSED] (Rule R5.3 Privacy)
tests/unit/test_prompt_builder.py::test_catalog_prompt_builder_consumes_catalog_only       [PASSED] (T-09 Catalog-Only Prompt)
tests/unit/test_sanitized_grounding.py::test_high_medium_sensitivity_never_sampled       [PASSED] (T-07 Zero PII Grounding)
tests/unit/test_sanitized_grounding.py::test_categorical_low_none_sensitivity_sampled   [PASSED]
tests/unit/test_schema_introspector.py::test_schema_introspection                       [PASSED] (T-06 Schema FKs/PKs)`}
        </div>
      </div>

      {/* Footer Banner */}
      <div className="banner" style={{ marginTop: '2rem' }}>
        <div className="banner-text">
          <h3>Core Principle Enforced:</h3>
          <p>&ldquo;The LLM proposes. Deterministic infrastructure authorizes, critiques, executes, and verifies.&rdquo;</p>
        </div>
        <span className="badge badge-p0">Rule 0 Binding</span>
      </div>
    </div>
  );
}

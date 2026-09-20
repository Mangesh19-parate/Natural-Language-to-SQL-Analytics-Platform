import React from 'react';
import Badge from '../ui/Badge.jsx';

export default function EvidenceChainPanel({
  queryResult = null,
  policyValidation = null,
  criticAnalysis = null,
  resultValidation = null,
  reliabilityScore = null,
}) {
  const isAllowed = policyValidation ? Boolean(policyValidation.is_allowed) : false;
  const executionSuccess = queryResult?.execution ? Boolean(queryResult.execution.success) : false;
  const reliability = reliabilityScore ?? queryResult?.reliability?.composite_score ?? queryResult?.reliability?.overall_score ?? null;

  // Single shared source of truth for confidence tiers (Rule R3.3 / Scorer alignment)
  const reliabilityVariant =
    reliability === null ? 'neutral' : reliability >= 80 ? 'success' : reliability >= 50 ? 'warning' : 'danger';
  const confidenceLabel =
    reliability === null ? 'Pending' : reliability >= 80 ? 'High Confidence' : reliability >= 50 ? 'Moderate' : 'Low Confidence';

  const hasResultValidation = Boolean(resultValidation || queryResult?.result_validation);
  const resultAnomaliesCount = resultValidation?.findings?.length ?? queryResult?.result_validation?.findings?.length ?? 0;
  const hasAnomalies = resultValidation?.has_anomalies ?? queryResult?.result_validation?.has_anomalies ?? false;

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
          paddingBottom: '0.75rem',
          borderBottom: '1px solid var(--border-subtle)',
          marginBottom: '1rem',
        }}
      >
        <div>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Forensic Evidence Chain
          </div>
          <div style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '2px' }}>
            Deterministic verification across 7 analytical checkpoints
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Composite Reliability
            </div>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
              {reliability !== null ? (
                <>{reliability}<span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>/100</span></>
              ) : (
                <span style={{ fontSize: '14px', color: 'var(--text-muted)' }}>Pending</span>
              )}
            </div>
          </div>
          <Badge variant={reliabilityVariant} size="md">
            {confidenceLabel}
          </Badge>
        </div>
      </div>

      <div className="evidence-grid">
        {/* Stage 1: Intent Interpretation */}
        <div className="evidence-node">
          <div className="evidence-node-header">
            <span>1. Intent</span>
            <span className={`evidence-node-status ${queryResult ? 'passed' : 'pending'}`}>
              {queryResult ? 'Verified' : 'Pending'}
            </span>
          </div>
          <div className="evidence-node-value">
            {queryResult?.intent?.classification || (queryResult ? 'Direct Answerable' : 'Awaiting Input')}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
            {queryResult ? 'Intent classified & grounded' : 'Zero metric ambiguity check'}
          </div>
        </div>

        {/* Stage 2: Schema Grounding */}
        <div className="evidence-node">
          <div className="evidence-node-header">
            <span>2. Schema</span>
            <span className={`evidence-node-status ${queryResult ? 'passed' : 'pending'}`}>
              {queryResult ? 'Grounded' : 'Pending'}
            </span>
          </div>
          <div className="evidence-node-value">Semantic Catalog</div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Zero raw PII in prompt context
          </div>
        </div>

        {/* Stage 3: Policy Gate & Row Filters */}
        <div className="evidence-node">
          <div className="evidence-node-header">
            <span>3. Policy</span>
            <span className={`evidence-node-status ${!policyValidation ? 'pending' : isAllowed ? 'passed' : 'failed'}`}>
              {!policyValidation ? 'Pending' : isAllowed ? 'Allowed' : 'Rejected'}
            </span>
          </div>
          <div className="evidence-node-value">
            {!policyValidation ? 'Awaiting Evaluation' : isAllowed ? 'RBAC & Limits OK' : 'Policy Blocked'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
            {policyValidation?.applied_row_filter ? 'Row-filter injected' : 'Deny-by-default verified'}
          </div>
        </div>

        {/* Stage 4: AST Statement Validation */}
        <div className="evidence-node">
          <div className="evidence-node-header">
            <span>4. AST Syntax</span>
            <span className={`evidence-node-status ${queryResult?.sql ? 'passed' : 'pending'}`}>
              {queryResult?.sql ? 'SELECT-Only' : 'Pending'}
            </span>
          </div>
          <div className="evidence-node-value">SqlGlot Validated</div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
            DML/DDL mutation blocked
          </div>
        </div>

        {/* Stage 5: SQL Critic Analysis */}
        <div className="evidence-node">
          <div className="evidence-node-header">
            <span>5. SQL Critic</span>
            <span className={`evidence-node-status ${!criticAnalysis ? 'pending' : criticAnalysis.has_findings ? 'active' : 'passed'}`}>
              {!criticAnalysis ? 'Pending' : criticAnalysis.has_findings ? 'Smells Flagged' : 'Clean'}
            </span>
          </div>
          <div className="evidence-node-value">
            {criticAnalysis ? `${criticAnalysis.findings_count ?? criticAnalysis.findings?.length ?? 0} Findings` : 'Awaiting Analysis'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Semantic logic verified
          </div>
        </div>

        {/* Stage 6: Execution Sandbox */}
        <div className="evidence-node">
          <div className="evidence-node-header">
            <span>6. Sandbox</span>
            <span className={`evidence-node-status ${!queryResult?.execution ? 'pending' : executionSuccess ? 'passed' : 'failed'}`}>
              {!queryResult?.execution ? 'Pending' : executionSuccess ? 'Success' : 'Error'}
            </span>
          </div>
          <div className="evidence-node-value">Read-Only Engine</div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
            10s timeout & 10k row limit
          </div>
        </div>

        {/* Stage 7: Result Validation */}
        <div className="evidence-node">
          <div className="evidence-node-header">
            <span>7. Result Sanity</span>
            <span className={`evidence-node-status ${!hasResultValidation ? 'pending' : hasAnomalies ? 'failed' : 'passed'}`}>
              {!hasResultValidation ? 'Pending' : hasAnomalies ? 'Flagged' : 'Passed'}
            </span>
          </div>
          <div className="evidence-node-value">
            {!hasResultValidation ? 'Awaiting Execution' : hasAnomalies ? `${resultAnomaliesCount} Anomaly Detected` : 'Anomalies: None'}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Cardinality & null checks
          </div>
        </div>
      </div>
    </div>
  );
}

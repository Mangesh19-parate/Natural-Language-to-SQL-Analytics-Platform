import React, { useState } from 'react';
import { apiFetch } from '../utils/api.js';

export default function PolicyValidatorSandbox({ roleId }) {
  const [customSql, setCustomSql] = useState('SELECT employee_id, first_name, salary FROM employees;');
  const [validationResult, setValidationResult] = useState(null);
  const [isValidating, setIsValidating] = useState(false);

  const presets = [
    { label: 'Safe SELECT (Admin/Analyst)', sql: 'SELECT employee_id, first_name FROM employees;' },
    { label: 'Avg Salary (Aggregate Guard Test)', sql: 'SELECT AVG(salary) FROM employees;' },
    { label: 'Stacked DDL Attack (DROP TABLE)', sql: 'SELECT * FROM employees; DROP TABLE employees;' },
    { label: 'Direct Write (DELETE)', sql: 'DELETE FROM customers WHERE customer_id = 1;' },
    { label: 'SELECT INTO Outfile', sql: 'SELECT * INTO OUTFILE "/tmp/dump.csv" FROM employees;' },
    { label: 'Unauthorized Table (payroll)', sql: 'SELECT bank_account FROM payroll;' },
  ];

  const handleValidate = async (sqlToTest) => {
    const query = sqlToTest || customSql;
    if (!query.trim()) return;

    setIsValidating(true);
    try {
      const res = await apiFetch('/api/sql/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sql: query,
          role_id: roleId,
          data_source_id: 1,
        }),
      });
      const data = await res.json();
      setValidationResult(data);
    } catch (err) {
      console.error(err);
    } finally {
      setIsValidating(false);
    }
  };

  return (
    <div
      style={{
        background: 'rgba(15, 23, 42, 0.6)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '12px',
        padding: '1.25rem',
        marginTop: '2rem',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span>🧪</span>
            <span>Adversarial SQL &amp; Policy Engine Sandbox (T-15, T-16, T-17, T-18)</span>
          </h3>
          <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            Test SQL statements directly against AST SELECT-only validator and fail-closed data policies.
          </p>
        </div>
        <button
          onClick={() => handleValidate()}
          disabled={isValidating}
          style={{
            background: '#3b82f6',
            border: 'none',
            borderRadius: '6px',
            color: '#fff',
            padding: '0.45rem 1rem',
            fontWeight: 600,
            fontSize: '0.82rem',
            cursor: 'pointer',
          }}
        >
          {isValidating ? 'Validating AST...' : 'Run Policy Check'}
        </button>
      </div>

      {/* Preset attack & safe buttons */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem' }}>
        {presets.map((p, idx) => (
          <button
            key={idx}
            onClick={() => {
              setCustomSql(p.sql);
              handleValidate(p.sql);
            }}
            style={{
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '6px',
              padding: '0.3rem 0.65rem',
              fontSize: '0.75rem',
              color: '#94a3b8',
              cursor: 'pointer',
            }}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Textarea */}
      <textarea
        value={customSql}
        onChange={(e) => setCustomSql(e.target.value)}
        rows={3}
        style={{
          width: '100%',
          background: '#090d16',
          border: '1px solid #1e293b',
          borderRadius: '8px',
          color: '#e2e8f0',
          fontFamily: 'monospace',
          fontSize: '0.85rem',
          padding: '0.75rem',
          boxSizing: 'border-box',
          resize: 'vertical',
        }}
      />

      {/* Result */}
      {validationResult && (
        <div
          style={{
            marginTop: '1rem',
            background: validationResult.policy_validation?.is_allowed ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
            border: `1px solid ${validationResult.policy_validation?.is_allowed ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
            borderRadius: '8px',
            padding: '1rem',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontWeight: 600, color: validationResult.policy_validation?.is_allowed ? '#34d399' : '#f87171' }}>
              {validationResult.policy_validation?.is_allowed ? '🛡️ Policy Passed (Safe & Authorized)' : '🚫 Policy Rejection (Blocked)'}
            </span>
            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
              AST Tables: {validationResult.analysis?.tables?.join(', ') || 'None'}
            </span>
          </div>

          {validationResult.policy_validation?.violations?.length > 0 && (
            <div style={{ marginTop: '0.75rem' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#fca5a5' }}>Violations:</div>
              <ul style={{ margin: '0.25rem 0 0 0', paddingLeft: '1.2rem', fontSize: '0.78rem', color: '#fca5a5' }}>
                {validationResult.policy_validation.violations.map((v, i) => (
                  <li key={i}>
                    <strong>[{v.violation_type}]</strong>: {v.message}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

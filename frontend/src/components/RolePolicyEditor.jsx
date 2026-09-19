import React, { useState, useEffect } from 'react';
import { apiFetch } from '../utils/api.js';

export default function RolePolicyEditor({ activeRole = 'admin', activeRoleId = 1, dataSourceId = 1, onPolicyChange }) {
  const [selectedRole, setSelectedRole] = useState(activeRoleId);
  const [matrixData, setMatrixData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [editingPolicy, setEditingPolicy] = useState(null);
  const [saving, setSaving] = useState(false);

  // Form state for creating / editing policy
  const [formAccessLevel, setFormAccessLevel] = useState('read');
  const [formAggregateAllowed, setFormAggregateAllowed] = useState(false);
  const [formRowFilter, setFormRowFilter] = useState('');

  const rolesList = [
    { id: 1, name: 'Admin', desc: 'Full schema access with aggregate & EXPLAIN ANALYZE permissions' },
    { id: 2, name: 'Analyst', desc: 'Standard business tables access, aggregate allowed, no raw PII' },
    { id: 3, name: 'Viewer', desc: 'Strictly fail-closed by default, restricted aggregated views only' },
  ];

  const fetchMatrix = async (roleId) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/policy/matrix?role_id=${roleId}&data_source_id=${dataSourceId}`);
      const data = await res.json();
      if (data?.success) {
        setMatrixData(data.data);
      } else {
        setError(data?.detail || data?.message || 'Failed to load policy matrix');
      }
    } catch (err) {
      console.error('Error fetching policy matrix:', err);
      setError(err.message || 'Failed to load policy matrix');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMatrix(selectedRole);
  }, [selectedRole, dataSourceId]);

  const handleOpenEdit = (table, col = null) => {
    const isCol = col !== null;
    const item = isCol ? col : table;
    setEditingPolicy({
      table_name: table.table_name,
      column_name: isCol ? col.column_name : null,
      policy_id: item.policy_id,
      is_explicit: item.is_explicit,
      access_level: item.access_level || 'denied',
      aggregate_allowed: item.aggregate_allowed || false,
      row_filter_sql: item.row_filter_sql || '',
    });
    setFormAccessLevel(item.access_level === 'denied' ? 'read' : item.access_level);
    setFormAggregateAllowed(item.aggregate_allowed || false);
    setFormRowFilter(item.row_filter_sql || '');
  };

  const handleSavePolicy = async () => {
    if (!editingPolicy) return;
    setSaving(true);
    try {
      const payload = {
        role_id: selectedRole,
        data_source_id: dataSourceId,
        table_name: editingPolicy.table_name,
        column_name: editingPolicy.column_name,
        access_level: formAccessLevel,
        aggregate_allowed: formAggregateAllowed,
        row_filter_sql: formRowFilter.trim() ? formRowFilter.trim() : null,
      };

      const res = await apiFetch('/api/policy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data?.success) {
        setEditingPolicy(null);
        await fetchMatrix(selectedRole);
        if (onPolicyChange) onPolicyChange();
      } else {
        alert('Failed to save policy: ' + (data?.detail || data?.message));
      }
    } catch (err) {
      alert('Failed to save policy: ' + err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDeletePolicy = async (policyId) => {
    if (!policyId) return;
    if (!window.confirm('Revert this rule to fail-closed DENIED BY DEFAULT?')) return;
    try {
      const res = await apiFetch(`/api/policy/${policyId}`, { method: 'DELETE' });
      const data = await res.json();
      if (data?.success) {
        setEditingPolicy(null);
        await fetchMatrix(selectedRole);
        if (onPolicyChange) onPolicyChange();
      } else {
        alert('Failed to delete policy: ' + (data?.detail || data?.message));
      }
    } catch (err) {
      alert('Failed to delete policy: ' + err.message);
    }
  };

  return (
    <div className="policy-editor-container" style={{ padding: '24px', color: '#e2e8f0' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h2 style={{ margin: 0, fontSize: '20px', fontWeight: '700', color: '#f8fafc' }}>
              Data Policy &amp; RBAC Governance Matrix
            </h2>
          </div>
          <p style={{ margin: '6px 0 0 0', color: '#94a3b8', fontSize: '14px' }}>
            Enforces <strong>Fail-Closed Deny-by-Default</strong> security policy. Unconfigured tables and columns have zero access.
          </p>
        </div>

        {/* Role Selector Tabs */}
        <div style={{ display: 'flex', background: '#0f172a', padding: '4px', borderRadius: '10px', border: '1px solid #334155' }}>
          {rolesList.map((r) => (
            <button
              key={r.id}
              onClick={() => setSelectedRole(r.id)}
              style={{
                background: selectedRole === r.id ? '#3b82f6' : 'transparent',
                color: selectedRole === r.id ? '#ffffff' : '#94a3b8',
                border: 'none',
                padding: '8px 16px',
                borderRadius: '8px',
                fontWeight: selectedRole === r.id ? '600' : '400',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                fontSize: '13px',
              }}
            >
              {r.name} Role
            </button>
          ))}
        </div>
      </div>

      {/* Fail-Closed Banner */}
      <div
        style={{
          background: 'linear-gradient(90deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.9) 100%)',
          border: '1px solid #334155',
          borderLeft: '4px solid #3b82f6',
          borderRadius: '8px',
          padding: '14px 18px',
          marginBottom: '20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '13px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '18px' }}>🔒</span>
          <div>
            <span style={{ fontWeight: '600', color: '#f1f5f9' }}>Active Policy Engine Mode: </span>
            <span style={{ color: '#38bdf8' }}>Server-Side AST Verification (PostgreSQL / SQLite Sandboxed)</span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '16px' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#10b981' }}></span>
            <span style={{ color: '#cbd5e1' }}>Explicit Read</span>
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#f59e0b' }}></span>
            <span style={{ color: '#cbd5e1' }}>Aggregate Only</span>
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#64748b' }}></span>
            <span style={{ color: '#cbd5e1' }}>Denied (Fail-Closed)</span>
          </span>
        </div>
      </div>

      {/* Loading & Error States */}
      {loading && (
        <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>
          <div style={{ fontSize: '24px', marginBottom: '8px' }}>⏳</div>
          Loading permission matrix from Semantic Catalog...
        </div>
      )}

      {error && (
        <div style={{ padding: '16px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid #ef4444', borderRadius: '8px', color: '#fca5a5' }}>
          {error}
        </div>
      )}

      {/* Matrix Table */}
      {!loading && matrixData && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {matrixData.tables?.map((tbl) => (
            <div
              key={tbl.table_name}
              style={{
                background: '#1e293b',
                border: tbl.is_fail_closed_denied ? '1px solid #334155' : '1px solid #475569',
                borderRadius: '12px',
                overflow: 'hidden',
              }}
            >
              {/* Table Header Bar */}
              <div
                style={{
                  padding: '14px 20px',
                  background: tbl.is_fail_closed_denied ? '#0f172a' : '#1e293b',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  borderBottom: '1px solid #334155',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span style={{ fontSize: '18px' }}>📁</span>
                  <span style={{ fontSize: '16px', fontWeight: '700', color: '#f8fafc' }}>
                    {tbl.table_name}
                  </span>
                  {tbl.is_fail_closed_denied ? (
                    <span
                      style={{
                        fontSize: '11px',
                        background: '#334155',
                        color: '#94a3b8',
                        padding: '3px 8px',
                        borderRadius: '4px',
                        fontWeight: '600',
                      }}
                    >
                      DENIED BY DEFAULT (Fail-Closed)
                    </span>
                  ) : (
                    <span
                      style={{
                        fontSize: '11px',
                        background: 'rgba(16, 185, 129, 0.15)',
                        color: '#34d399',
                        padding: '3px 8px',
                        borderRadius: '4px',
                        fontWeight: '600',
                        border: '1px solid rgba(16, 185, 129, 0.3)',
                      }}
                    >
                      ✓ {tbl.access_level.toUpperCase()}
                    </span>
                  )}

                  {tbl.aggregate_allowed && (
                    <span
                      style={{
                        fontSize: '11px',
                        background: 'rgba(245, 158, 11, 0.15)',
                        color: '#fbbf24',
                        padding: '3px 8px',
                        borderRadius: '4px',
                        border: '1px solid rgba(245, 158, 11, 0.3)',
                      }}
                    >
                      ∑ Aggregates Allowed
                    </span>
                  )}

                  {tbl.row_filter_sql && (
                    <span
                      style={{
                        fontSize: '11px',
                        background: 'rgba(147, 51, 234, 0.15)',
                        color: '#c084fc',
                        padding: '3px 8px',
                        borderRadius: '4px',
                        border: '1px solid rgba(147, 51, 234, 0.3)',
                        fontFamily: 'monospace',
                      }}
                    >
                      WHERE {tbl.row_filter_sql}
                    </span>
                  )}
                </div>

                <button
                  onClick={() => handleOpenEdit(tbl, null)}
                  style={{
                    background: '#334155',
                    color: '#f8fafc',
                    border: '1px solid #475569',
                    padding: '6px 14px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    cursor: 'pointer',
                    fontWeight: '500',
                  }}
                >
                  ⚙ Configure Table Policy
                </button>
              </div>

              {/* Columns Grid */}
              <div style={{ padding: '16px 20px', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '12px' }}>
                {tbl.columns?.map((col) => (
                  <div
                    key={col.column_name}
                    style={{
                      background: '#0f172a',
                      padding: '12px',
                      borderRadius: '8px',
                      border: '1px solid #334155',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                        <span style={{ fontSize: '13px', fontWeight: '600', color: '#f1f5f9' }}>
                          {col.column_name}
                        </span>
                        {col.sensitivity === 'HIGH' && (
                          <span style={{ fontSize: '10px', background: '#dc2626', color: '#fff', padding: '1px 5px', borderRadius: '3px' }}>
                            🔒 HIGH
                          </span>
                        )}
                        {col.sensitivity === 'MEDIUM' && (
                          <span style={{ fontSize: '10px', background: '#d97706', color: '#fff', padding: '1px 5px', borderRadius: '3px' }}>
                            MED
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '11px', color: '#94a3b8' }}>
                        Type: {col.semantic_type || 'text'} · {col.is_fail_closed_denied ? 'Denied' : col.access_level}
                      </div>
                    </div>

                    <button
                      onClick={() => handleOpenEdit(tbl, col)}
                      style={{
                        background: 'transparent',
                        color: '#60a5fa',
                        border: 'none',
                        fontSize: '12px',
                        cursor: 'pointer',
                        padding: '4px 8px',
                      }}
                    >
                      Edit
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Edit Modal */}
      {editingPolicy && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
        >
          <div
            style={{
              background: '#1e293b',
              border: '1px solid #475569',
              borderRadius: '14px',
              padding: '24px',
              width: '90%',
              maxWidth: '520px',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '700', color: '#f8fafc' }}>
                Configure Policy: {editingPolicy.table_name}
                {editingPolicy.column_name ? `.${editingPolicy.column_name}` : ' (Entire Table)'}
              </h3>
              <button
                onClick={() => setEditingPolicy(null)}
                style={{ background: 'transparent', border: 'none', color: '#94a3b8', fontSize: '18px', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* Access Level */}
              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: '600', color: '#cbd5e1', marginBottom: '6px' }}>
                  Access Permission Level
                </label>
                <select
                  value={formAccessLevel}
                  onChange={(e) => setFormAccessLevel(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px',
                    background: '#0f172a',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                    color: '#f8fafc',
                    fontSize: '14px',
                  }}
                >
                  <option value="read">Read (Full column/table access)</option>
                  <option value="read_aggregate_only">Read Aggregate Only (Disallow raw rows)</option>
                  <option value="denied">Denied (Fail-Closed Deny)</option>
                </select>
              </div>

              {/* Aggregate Allowed */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: '#0f172a', padding: '12px', borderRadius: '8px' }}>
                <input
                  type="checkbox"
                  id="aggCheck"
                  checked={formAggregateAllowed}
                  onChange={(e) => setFormAggregateAllowed(e.target.checked)}
                  style={{ width: '18px', height: '18px', cursor: 'pointer' }}
                />
                <label htmlFor="aggCheck" style={{ fontSize: '13px', color: '#f8fafc', cursor: 'pointer' }}>
                  <strong>Allow Aggregations (SUM / AVG / MAX / MIN)</strong>
                  <div style={{ fontSize: '11px', color: '#94a3b8' }}>
                    Required by Aggregate Guard (Rule R1.4) to query sensitive metrics.
                  </div>
                </label>
              </div>

              {/* Row Filter SQL */}
              {!editingPolicy.column_name && (
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: '600', color: '#cbd5e1', marginBottom: '6px' }}>
                    Row-Level Filter Expression (WHERE Fragment)
                  </label>
                  <input
                    type="text"
                    value={formRowFilter}
                    onChange={(e) => setFormRowFilter(e.target.value)}
                    placeholder="e.g. department_id = 2"
                    style={{
                      width: '100%',
                      padding: '10px',
                      background: '#0f172a',
                      border: '1px solid #334155',
                      borderRadius: '8px',
                      color: '#f8fafc',
                      fontSize: '13px',
                      fontFamily: 'monospace',
                    }}
                  />
                  <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px' }}>
                    Automatically injected by Policy Engine into AST before query execution.
                  </div>
                </div>
              )}
            </div>

            {/* Action Buttons */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '24px' }}>
              {editingPolicy.policy_id ? (
                <button
                  onClick={() => handleDeletePolicy(editingPolicy.policy_id)}
                  style={{
                    background: 'rgba(239, 68, 68, 0.2)',
                    color: '#f87171',
                    border: '1px solid rgba(239, 68, 68, 0.4)',
                    padding: '8px 14px',
                    borderRadius: '6px',
                    fontSize: '13px',
                    cursor: 'pointer',
                  }}
                >
                  Delete Rule (Revert to Default-Deny)
                </button>
              ) : <div></div>}

              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  onClick={() => setEditingPolicy(null)}
                  style={{
                    background: 'transparent',
                    color: '#94a3b8',
                    border: '1px solid #334155',
                    padding: '8px 16px',
                    borderRadius: '6px',
                    fontSize: '13px',
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  onClick={handleSavePolicy}
                  disabled={saving}
                  style={{
                    background: '#3b82f6',
                    color: '#ffffff',
                    border: 'none',
                    padding: '8px 18px',
                    borderRadius: '6px',
                    fontSize: '13px',
                    fontWeight: '600',
                    cursor: 'pointer',
                  }}
                >
                  {saving ? 'Saving...' : 'Save Policy'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

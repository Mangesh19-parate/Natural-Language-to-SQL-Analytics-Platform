import React, { useState, useEffect } from 'react';
import { apiFetch } from '../utils/api.js';

export default function QueryHistoryView({ onSelectQuery, onInspectReplay, activeRoleId = 1, dataSourceId = 1 }) {
  const [historyItems, setHistoryItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [rerunningId, setRerunningId] = useState(null);
  const [rerunFeedback, setRerunFeedback] = useState(null);

  const fetchHistory = async () => {
    setLoading(true);
    setError(null);
    try {
      let url = `/api/history?page=${page}&page_size=15&data_source_id=${dataSourceId}`;
      if (statusFilter) url += `&status=${statusFilter}`;
      if (searchQuery) url += `&search=${encodeURIComponent(searchQuery)}`;

      const res = await apiFetch(url);
      const data = await res.json();
      if (data?.success) {
        setHistoryItems(data.data.items || []);
        setTotalCount(data.data.total_count || 0);
      } else {
        setError(data?.detail || data?.message || 'Failed to load execution history');
      }
    } catch (err) {
      console.error('Failed to load history:', err);
      setError(err.message || 'Failed to load execution history');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, [page, statusFilter, dataSourceId]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    setPage(1);
    fetchHistory();
  };

  const handleLiveRerun = async (item) => {
    setRerunningId(item.query_id);
    setRerunFeedback(null);
    try {
      const res = await apiFetch(`/api/history/${item.query_id}/rerun`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          role_id: activeRoleId,
          data_source_id: dataSourceId,
        }),
      });
      const resData = await res.json();

      if (resData?.success) {
        setRerunFeedback({
          query_id: item.query_id,
          success: true,
          msg: `Live rerun succeeded in ${resData.data.latency_ms}ms · ${resData.data.row_count} rows returned (Fresh Execution)`,
        });
        if (onSelectQuery) {
          onSelectQuery({
            question: item.nl_question,
            sql: item.final_sql,
            executionResponse: resData.data,
            queryId: item.query_id,
          });
        }
      } else {
        setRerunFeedback({
          query_id: item.query_id,
          success: false,
          msg: resData?.message || 'Rerun was rejected or failed live execution',
        });
      }
    } catch (err) {
      setRerunFeedback({
        query_id: item.query_id,
        success: false,
        msg: err.message || 'Live rerun failed',
      });
    } finally {
      setRerunningId(null);
    }
  };

  const handleDelete = async (queryId) => {
    if (!window.confirm('Delete this history record?')) return;
    try {
      const res = await apiFetch(`/api/history/${queryId}`, { method: 'DELETE' });
      const data = await res.json();
      if (data?.success) {
        setHistoryItems(historyItems.filter((i) => i.query_id !== queryId));
        setTotalCount((prev) => Math.max(0, prev - 1));
      } else {
        alert('Failed to delete query record: ' + (data?.detail || data?.message));
      }
    } catch (err) {
      alert('Failed to delete query record: ' + err.message);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'success':
        return { label: '✓ SUCCESS', bg: 'rgba(16, 185, 129, 0.15)', color: '#34d399', border: '#10b981' };
      case 'auto_corrected':
        return { label: '⚡ AUTO-CORRECTED', bg: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa', border: '#3b82f6' };
      case 'rejected_policy':
        return { label: '🔒 REJECTED (POLICY)', bg: 'rgba(100, 116, 139, 0.25)', color: '#cbd5e1', border: '#64748b' };
      default:
        return { label: '✗ FAILED', bg: 'rgba(239, 68, 68, 0.15)', color: '#f87171', border: '#ef4444' };
    }
  };

  return (
    <div className="query-history-view" style={{ padding: '24px', color: '#e2e8f0' }}>
      {/* Title & Principle Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '24px' }}>📜</span>
            <h2 style={{ margin: 0, fontSize: '22px', fontWeight: '700', color: '#f8fafc' }}>
              Query History &amp; Audit Log
            </h2>
          </div>
          <p style={{ margin: '6px 0 0 0', color: '#94a3b8', fontSize: '14px' }}>
            Enforces <strong>REQ-HIST-01 (Rerun-by-Default)</strong>: Re-executes live against active policies with zero stale cache claims.
          </p>
        </div>

        {/* Search & Filter Controls */}
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '8px' }}>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search question or SQL..."
              style={{
                padding: '8px 14px',
                background: '#0f172a',
                border: '1px solid #334155',
                borderRadius: '8px',
                color: '#f8fafc',
                fontSize: '13px',
                minWidth: '220px',
              }}
            />
            <button
              type="submit"
              style={{
                background: '#334155',
                color: '#f8fafc',
                border: '1px solid #475569',
                padding: '8px 14px',
                borderRadius: '8px',
                cursor: 'pointer',
                fontSize: '13px',
              }}
            >
              Search
            </button>
          </form>

          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            style={{
              padding: '8px 12px',
              background: '#0f172a',
              border: '1px solid #334155',
              borderRadius: '8px',
              color: '#f8fafc',
              fontSize: '13px',
            }}
          >
            <option value="">All Statuses ({totalCount})</option>
            <option value="success">Success</option>
            <option value="auto_corrected">Auto-Corrected</option>
            <option value="rejected_policy">Policy Rejected</option>
            <option value="failed">Failed</option>
          </select>
        </div>
      </div>

      {/* Rerun Feedback Alert */}
      {rerunFeedback && (
        <div
          style={{
            padding: '12px 18px',
            borderRadius: '8px',
            marginBottom: '18px',
            background: rerunFeedback.success ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
            border: `1px solid ${rerunFeedback.success ? '#10b981' : '#ef4444'}`,
            color: rerunFeedback.success ? '#34d399' : '#fca5a5',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: '13px',
          }}
        >
          <span>{rerunFeedback.msg}</span>
          <button
            onClick={() => setRerunFeedback(null)}
            style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>
          <div style={{ fontSize: '24px', marginBottom: '8px' }}>⏳</div>
          Loading query history...
        </div>
      )}

      {error && (
        <div style={{ padding: '16px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid #ef4444', borderRadius: '8px', color: '#fca5a5' }}>
          {error}
        </div>
      )}

      {/* History Cards List */}
      {!loading && historyItems.length === 0 && (
        <div style={{ textAlign: 'center', padding: '48px', background: '#1e293b', borderRadius: '12px', color: '#94a3b8' }}>
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>🔍</div>
          <div style={{ fontSize: '16px', fontWeight: '600', color: '#f1f5f9', marginBottom: '6px' }}>
            No query history found
          </div>
          <p style={{ margin: 0, fontSize: '13px' }}>
            Execute questions in the canvas to populate the reproducible audit trail.
          </p>
        </div>
      )}

      {!loading && historyItems.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {historyItems.map((item) => {
            const badge = getStatusBadge(item.status);
            const isRerunning = rerunningId === item.query_id;

            return (
              <div
                key={item.query_id}
                style={{
                  background: '#1e293b',
                  border: '1px solid #334155',
                  borderRadius: '12px',
                  padding: '18px 22px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                  transition: 'all 0.2s ease',
                }}
              >
                {/* Top Row: Question & Status */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px' }}>
                  <div>
                    <h3 style={{ margin: '0 0 6px 0', fontSize: '16px', fontWeight: '600', color: '#f8fafc' }}>
                      "{item.nl_question}"
                    </h3>
                    <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap', fontSize: '12px', color: '#94a3b8' }}>
                      <span
                        style={{
                          background: badge.bg,
                          color: badge.color,
                          border: `1px solid ${badge.border}`,
                          padding: '2px 8px',
                          borderRadius: '4px',
                          fontWeight: '600',
                          fontSize: '11px',
                        }}
                      >
                        {badge.label}
                      </span>

                      {item.reliability_score !== null && item.reliability_score !== undefined && (
                        <span
                          style={{
                            background: item.reliability_score >= 80 ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                            color: item.reliability_score >= 80 ? '#34d399' : '#fbbf24',
                            border: `1px solid ${item.reliability_score >= 80 ? 'rgba(16, 185, 129, 0.4)' : 'rgba(245, 158, 11, 0.4)'}`,
                            padding: '2px 8px',
                            borderRadius: '4px',
                            fontWeight: '600',
                          }}
                        >
                          ★ Reliability: {Math.round(item.reliability_score)}/100
                        </span>
                      )}

                      {item.execution_ms !== null && (
                        <span>⏱ {item.execution_ms} ms</span>
                      )}
                      {item.row_count !== null && (
                        <span>📊 {item.row_count} rows</span>
                      )}
                      {item.created_at && (
                        <span>🕒 {new Date(item.created_at).toLocaleString()}</span>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
                    <button
                      onClick={() => handleLiveRerun(item)}
                      disabled={isRerunning}
                      style={{
                        background: '#3b82f6',
                        color: '#ffffff',
                        border: 'none',
                        padding: '6px 14px',
                        borderRadius: '6px',
                        fontSize: '12px',
                        fontWeight: '600',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                      }}
                    >
                      {isRerunning ? '⏳ Running...' : '▶ Rerun Live'}
                    </button>

                    <button
                      onClick={() => onInspectReplay && onInspectReplay(item.query_id)}
                      style={{
                        background: '#0f172a',
                        color: '#60a5fa',
                        border: '1px solid #3b82f6',
                        padding: '6px 12px',
                        borderRadius: '6px',
                        fontSize: '12px',
                        cursor: 'pointer',
                        fontWeight: '500',
                      }}
                    >
                      🔬 Provenance / Replay
                    </button>

                    <button
                      onClick={() => handleDelete(item.query_id)}
                      style={{
                        background: 'transparent',
                        color: '#94a3b8',
                        border: '1px solid #334155',
                        padding: '6px 10px',
                        borderRadius: '6px',
                        fontSize: '12px',
                        cursor: 'pointer',
                      }}
                    >
                      🗑
                    </button>
                  </div>
                </div>

                {/* SQL Preview */}
                {item.final_sql && (
                  <div
                    style={{
                      background: '#0f172a',
                      padding: '10px 14px',
                      borderRadius: '8px',
                      border: '1px solid #334155',
                      fontFamily: 'Consolas, Monaco, monospace',
                      fontSize: '12px',
                      color: '#38bdf8',
                      overflowX: 'auto',
                    }}
                  >
                    {item.final_sql}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

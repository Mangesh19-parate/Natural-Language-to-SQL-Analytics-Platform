import React, { useState } from 'react';

export default function ReportExportModal({
  isOpen,
  onClose,
  currentQueryItem,
  sessionQueries = [],
  dataSourceName = 'Northwind Commercial DB',
  roleName = 'Admin',
}) {
  const [format, setFormat] = useState('pdf'); // 'pdf' | 'excel'
  const [scope, setScope] = useState('single_query'); // 'single_query' | 'session'
  const [title, setTitle] = useState('SQL Trust & Reliability Audit Report');
  const [includeRawData, setIncludeRawData] = useState(true);
  const [maxRows, setMaxRows] = useState(50);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  if (!isOpen) return null;

  const handleExport = async () => {
    setLoading(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const queriesToExport = scope === 'session' && sessionQueries.length > 0
        ? sessionQueries
        : (currentQueryItem ? [currentQueryItem] : []);

      if (queriesToExport.length === 0) {
        throw new Error('No query data available to export.');
      }

      const payload = {
        title,
        scope,
        role_name: roleName,
        data_source_name: dataSourceName,
        queries: queriesToExport,
        include_raw_data: includeRawData,
        max_data_rows: maxRows,
      };

      const endpoint = format === 'pdf' ? '/api/report/pdf' : '/api/report/excel';
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Report generation failed (${res.status})`);
      }

      const reportData = await res.json();
      
      // Trigger download
      const downloadUrl = reportData.download_url;
      if (downloadUrl) {
        const dlRes = await fetch(downloadUrl);
        const blob = await dlRes.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${title.toLowerCase().replace(/[^a-z0-9]/g, '_')}_${reportData.report_id}.${format === 'pdf' ? 'pdf' : 'xlsx'}`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
      }

      setSuccessMsg(`✓ Successfully generated and downloaded ${format.toUpperCase()} report!`);
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(6px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: '1rem',
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        style={{
          background: 'linear-gradient(145deg, #0f172a, #1e293b)',
          border: '1px solid rgba(99, 102, 241, 0.35)',
          borderRadius: '16px',
          padding: '1.75rem',
          maxWidth: '520px',
          width: '100%',
          boxShadow: '0 20px 40px rgba(0, 0, 0, 0.6)',
          color: '#f8fafc',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '1.25rem',
            borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
            paddingBottom: '0.75rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <span style={{ fontSize: '1.3rem' }}>📑</span>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc' }}>
                Export Executive Report
              </h3>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                REQ-RPT-01 &bull; REQ-RPT-02 &bull; Rule R8.3 Provenance
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#94a3b8',
              fontSize: '1.3rem',
              cursor: 'pointer',
              lineHeight: 1,
            }}
          >
            &times;
          </button>
        </div>

        {/* Form Body */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* Format Picker */}
          <div>
            <label style={{ fontSize: '0.8rem', fontWeight: 600, color: '#cbd5e1', display: 'block', marginBottom: '0.4rem' }}>
              Report Format
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <button
                type="button"
                onClick={() => setFormat('pdf')}
                style={{
                  background: format === 'pdf' ? 'rgba(99, 102, 241, 0.25)' : 'rgba(255, 255, 255, 0.05)',
                  border: `1.5px solid ${format === 'pdf' ? '#6366f1' : 'rgba(255, 255, 255, 0.1)'}`,
                  color: format === 'pdf' ? '#a5b4fc' : '#94a3b8',
                  borderRadius: '8px',
                  padding: '0.65rem',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.4rem',
                }}
              >
                <span>📕</span>
                <span>PDF Document (.pdf)</span>
              </button>

              <button
                type="button"
                onClick={() => setFormat('excel')}
                style={{
                  background: format === 'excel' ? 'rgba(34, 197, 94, 0.25)' : 'rgba(255, 255, 255, 0.05)',
                  border: `1.5px solid ${format === 'excel' ? '#22c55e' : 'rgba(255, 255, 255, 0.1)'}`,
                  color: format === 'excel' ? '#86efac' : '#94a3b8',
                  borderRadius: '8px',
                  padding: '0.65rem',
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.4rem',
                }}
              >
                <span>📗</span>
                <span>Excel Workbook (.xlsx)</span>
              </button>
            </div>
          </div>

          {/* Scope Picker */}
          <div>
            <label style={{ fontSize: '0.8rem', fontWeight: 600, color: '#cbd5e1', display: 'block', marginBottom: '0.4rem' }}>
              Export Scope
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <button
                type="button"
                onClick={() => setScope('single_query')}
                style={{
                  background: scope === 'single_query' ? 'rgba(59, 130, 246, 0.25)' : 'rgba(255, 255, 255, 0.05)',
                  border: `1.5px solid ${scope === 'single_query' ? '#3b82f6' : 'rgba(255, 255, 255, 0.1)'}`,
                  color: scope === 'single_query' ? '#93c5fd' : '#94a3b8',
                  borderRadius: '8px',
                  padding: '0.55rem',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Current Query Only
              </button>

              <button
                type="button"
                onClick={() => setScope('session')}
                style={{
                  background: scope === 'session' ? 'rgba(59, 130, 246, 0.25)' : 'rgba(255, 255, 255, 0.05)',
                  border: `1.5px solid ${scope === 'session' ? '#3b82f6' : 'rgba(255, 255, 255, 0.1)'}`,
                  color: scope === 'session' ? '#93c5fd' : '#94a3b8',
                  borderRadius: '8px',
                  padding: '0.55rem',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Full Session ({sessionQueries.length || 1} Queries)
              </button>
            </div>
          </div>

          {/* Title Field */}
          <div>
            <label style={{ fontSize: '0.8rem', fontWeight: 600, color: '#cbd5e1', display: 'block', marginBottom: '0.35rem' }}>
              Report Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              style={{
                width: '100%',
                background: 'rgba(15, 23, 42, 0.8)',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                borderRadius: '8px',
                padding: '0.55rem 0.8rem',
                color: '#f8fafc',
                fontSize: '0.85rem',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {/* Options */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <label style={{ fontSize: '0.82rem', color: '#cbd5e1', display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={includeRawData}
                onChange={(e) => setIncludeRawData(e.target.checked)}
                style={{ accentColor: '#6366f1' }}
              />
              <span>Include Result Data Preview Table</span>
            </label>
          </div>
        </div>

        {/* Feedback Messages */}
        {error && (
          <div style={{ marginTop: '1rem', color: '#fca5a5', background: 'rgba(239, 68, 68, 0.15)', padding: '0.55rem 0.8rem', borderRadius: '6px', fontSize: '0.8rem' }}>
            <b>Export Failed:</b> {error}
          </div>
        )}
        {successMsg && (
          <div style={{ marginTop: '1rem', color: '#86efac', background: 'rgba(34, 197, 94, 0.15)', padding: '0.55rem 0.8rem', borderRadius: '6px', fontSize: '0.8rem' }}>
            {successMsg}
          </div>
        )}

        {/* Footer Buttons */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'flex-end',
            gap: '0.75rem',
            marginTop: '1.5rem',
            borderTop: '1px solid rgba(255, 255, 255, 0.1)',
            paddingTop: '1rem',
          }}
        >
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            style={{
              background: 'transparent',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              color: '#94a3b8',
              borderRadius: '8px',
              padding: '0.5rem 1rem',
              fontSize: '0.85rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={handleExport}
            disabled={loading}
            style={{
              background: 'linear-gradient(135deg, #6366f1, #4f46e5)',
              border: 'none',
              color: '#ffffff',
              borderRadius: '8px',
              padding: '0.5rem 1.25rem',
              fontSize: '0.85rem',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              boxShadow: '0 4px 12px rgba(99, 102, 241, 0.4)',
            }}
          >
            <span>📥</span>
            <span>{loading ? 'Generating...' : `Generate & Download ${format.toUpperCase()}`}</span>
          </button>
        </div>
      </div>
    </div>
  );
}

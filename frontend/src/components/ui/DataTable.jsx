import React, { useState } from 'react';

export default function DataTable({
  columns = [],
  rows = [],
  pageSize = 15,
  maxHeight = '400px',
  emptyMessage = 'No records found',
}) {
  const [currentPage, setCurrentPage] = useState(1);

  if (!rows || rows.length === 0) {
    return (
      <div
        style={{
          padding: '2rem',
          textAlign: 'center',
          color: 'var(--text-muted)',
          fontSize: '13px',
          background: 'var(--bg-app)',
          borderRadius: '6px',
          border: '1px solid var(--border-subtle)',
        }}
      >
        {emptyMessage}
      </div>
    );
  }

  const effectiveColumns =
    columns.length > 0
      ? columns
      : Object.keys(rows[0] || {});

  const totalPages = Math.ceil(rows.length / pageSize);
  const startIndex = (currentPage - 1) * pageSize;
  const visibleRows = rows.slice(startIndex, startIndex + pageSize);

  const copyAsCSV = () => {
    const header = effectiveColumns.join(',');
    const body = rows
      .map((r) =>
        effectiveColumns
          .map((col) => {
            const val = r[col];
            if (val === null || val === undefined) return '';
            const strVal = String(val);
            return strVal.includes(',') ? `"${strVal.replace(/"/g, '""')}"` : strVal;
          })
          .join(',')
      )
      .join('\n');
    navigator.clipboard.writeText(`${header}\n${body}`);
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          {rows.length} {rows.length === 1 ? 'row' : 'rows'} total
        </span>
        <button
          onClick={copyAsCSV}
          className="ui-btn ui-btn-secondary ui-btn-sm"
          style={{ fontSize: '11px' }}
        >
          Export CSV
        </button>
      </div>

      <div className="ui-table-wrapper" style={{ maxHeight, overflowY: 'auto' }}>
        <table className="ui-table">
          <thead>
            <tr>
              {effectiveColumns.map((col) => (
                <th key={col}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row, idx) => (
              <tr key={idx}>
                {effectiveColumns.map((col) => {
                  const val = row[col];
                  return (
                    <td key={col} style={{ fontFamily: typeof val === 'number' ? 'var(--font-mono)' : 'inherit' }}>
                      {val == null ? (
                        <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>NULL</span>
                      ) : typeof val === 'object' ? (
                        JSON.stringify(val)
                      ) : (
                        String(val)
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginTop: '0.65rem',
            fontSize: '12px',
          }}
        >
          <span style={{ color: 'var(--text-muted)' }}>
            Page {currentPage} of {totalPages}
          </span>
          <div style={{ display: 'flex', gap: '0.35rem' }}>
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="ui-btn ui-btn-secondary ui-btn-sm"
            >
              Previous
            </button>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="ui-btn ui-btn-secondary ui-btn-sm"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

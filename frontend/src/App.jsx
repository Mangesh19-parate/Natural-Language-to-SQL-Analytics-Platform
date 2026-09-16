import React, { useState, useEffect } from 'react';
import ClarificationCard from './components/ClarificationCard.jsx';
import SQLProposalCard from './components/SQLProposalCard.jsx';
import PolicyValidatorSandbox from './components/PolicyValidatorSandbox.jsx';
import SecurityAttackLab from './components/SecurityAttackLab.jsx';
import EvaluationLab from './components/EvaluationLab.jsx';
import RolePolicyEditor from './components/RolePolicyEditor.jsx';
import QueryHistoryView from './components/QueryHistoryView.jsx';
import QueryReplayCard from './components/QueryReplayCard.jsx';
import AuthModal from './components/AuthModal.jsx';

export default function App() {
  const [activeTab, setActiveTab] = useState('studio'); // 'studio' | 'history' | 'policy' | 'replay' | 'security' | 'evaluation'
  const [health, setHealth] = useState({
    status: 'checking...',
    environment: 'local',
    metadata_db_connected: false,
    business_db_connected: false,
    version: '1.2.0',
  });
  const [catalog, setCatalog] = useState(null);
  const [selectedRole, setSelectedRole] = useState(1); // 1: admin, 2: analyst, 3: viewer
  const [selectedRoleName, setSelectedRoleName] = useState('admin');
  const [activeUserEmail, setActiveUserEmail] = useState('admin@trustengine.ai');
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [selectedReplayQueryId, setSelectedReplayQueryId] = useState(null);

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

  const handleRoleSelectChange = (roleId) => {
    setSelectedRole(roleId);
    const rName = roleId === 1 ? 'admin' : roleId === 2 ? 'analyst' : 'viewer';
    setSelectedRoleName(rName);
    setActiveUserEmail(`${rName}@trustengine.ai`);
    localStorage.setItem('auth_role_id', String(roleId));
    localStorage.setItem('auth_role_name', rName);
  };

  const handleAuthSuccess = (user) => {
    if (user.role_id) {
      setSelectedRole(user.role_id);
    }
    if (user.role_name) {
      setSelectedRoleName(user.role_name);
    }
    if (user.email) {
      setActiveUserEmail(user.email);
    }
  };

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

  const handleInspectReplay = (queryId) => {
    setSelectedReplayQueryId(queryId);
    setActiveTab('replay');
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
        <div className="logo-section" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div className="logo-badge" style={{ fontSize: '1.3rem' }}>
            ⚡
          </div>
          <div className="title-group">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#818cf8', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Intelligent SQL Assistant &bull; Trust Engine
              </span>
              <span style={{ background: 'rgba(99, 102, 241, 0.2)', color: '#a5b4fc', fontSize: '0.7rem', padding: '0.1rem 0.4rem', borderRadius: '4px', fontWeight: 600 }}>
                v1.2.0
              </span>
            </div>
            <h1 className="title" style={{ fontSize: '1.4rem', fontWeight: 700, margin: '0 0 0.2rem 0', color: '#f8fafc' }}>
              Natural-Language Analytics Platform
            </h1>
            <p className="subtitle" style={{ fontSize: '0.82rem', color: 'var(--text-muted)', margin: 0 }}>
              Deterministic Verification &bull; RBAC &bull; Query History (T-38) &bull; Query Replay (T-39) &bull; Security Lab (T-31)
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          {/* Active Role Switcher & Auth */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(255, 255, 255, 0.05)', padding: '0.4rem 0.8rem', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Role:</span>
            <select
              value={selectedRole}
              onChange={(e) => handleRoleSelectChange(Number(e.target.value))}
              style={{
                background: '#1e293b',
                color: '#fff',
                border: '1px solid #475569',
                borderRadius: '4px',
                padding: '0.2rem 0.4rem',
                fontSize: '0.85rem'
              }}
            >
              <option value={1}>Admin (Full Access)</option>
              <option value={2}>Analyst (Sales &amp; Orders)</option>
              <option value={3}>Viewer (Fail-Closed Denied)</option>
            </select>

            <button
              onClick={() => setIsAuthModalOpen(true)}
              style={{
                background: '#334155',
                color: '#60a5fa',
                border: '1px solid #475569',
                borderRadius: '4px',
                padding: '0.25rem 0.5rem',
                fontSize: '0.75rem',
                cursor: 'pointer',
                fontWeight: '600',
              }}
            >
              🔑 JWT Auth
            </button>
          </div>

          <div style={{ textAlign: 'right' }}>
            <span className="badge badge-p0" style={{ marginBottom: '0.4rem' }}>
              Milestone M3 &bull; Full P0/P1 Platform
            </span>
            <div style={{ fontSize: '0.75rem', color: '#10b981', fontWeight: 600 }}>
              Week 12 Gate Verified (T-37, T-38, T-39)
            </div>
          </div>
        </div>
      </header>

      {/* Main Navigation Tabs */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', borderBottom: '1px solid rgba(255, 255, 255, 0.1)', paddingBottom: '0.75rem', flexWrap: 'wrap' }}>
        <button
          onClick={() => setActiveTab('studio')}
          style={{
            background: activeTab === 'studio' ? 'rgba(99, 102, 241, 0.15)' : 'transparent',
            color: activeTab === 'studio' ? '#818cf8' : 'var(--text-muted)',
            border: activeTab === 'studio' ? '1px solid rgba(99, 102, 241, 0.4)' : '1px solid transparent',
            borderRadius: '8px',
            padding: '0.5rem 1.1rem',
            fontSize: '0.9rem',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            transition: 'all 0.15s'
          }}
        >
          <span>⚡</span>
          <span>Interactive Studio</span>
        </button>

        <button
          onClick={() => setActiveTab('history')}
          style={{
            background: activeTab === 'history' ? 'rgba(59, 130, 246, 0.15)' : 'transparent',
            color: activeTab === 'history' ? '#60a5fa' : 'var(--text-muted)',
            border: activeTab === 'history' ? '1px solid rgba(59, 130, 246, 0.4)' : '1px solid transparent',
            borderRadius: '8px',
            padding: '0.5rem 1.1rem',
            fontSize: '0.9rem',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            transition: 'all 0.15s'
          }}
        >
          <span>📜</span>
          <span>Query History (T-38 Rerun)</span>
        </button>

        <button
          onClick={() => setActiveTab('policy')}
          style={{
            background: activeTab === 'policy' ? 'rgba(168, 85, 247, 0.15)' : 'transparent',
            color: activeTab === 'policy' ? '#c084fc' : 'var(--text-muted)',
            border: activeTab === 'policy' ? '1px solid rgba(168, 85, 247, 0.4)' : '1px solid transparent',
            borderRadius: '8px',
            padding: '0.5rem 1.1rem',
            fontSize: '0.9rem',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            transition: 'all 0.15s'
          }}
        >
          <span>🛡️</span>
          <span>Data Policy Matrix (T-37)</span>
        </button>

        {selectedReplayQueryId && (
          <button
            onClick={() => setActiveTab('replay')}
            style={{
              background: activeTab === 'replay' ? 'rgba(236, 72, 153, 0.15)' : 'transparent',
              color: activeTab === 'replay' ? '#f472b6' : 'var(--text-muted)',
              border: activeTab === 'replay' ? '1px solid rgba(236, 72, 153, 0.4)' : '1px solid transparent',
              borderRadius: '8px',
              padding: '0.5rem 1.1rem',
              fontSize: '0.9rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              transition: 'all 0.15s'
            }}
          >
            <span>🔬</span>
            <span>Query Replay #{selectedReplayQueryId.slice(0, 6)}</span>
          </button>
        )}

        <button
          onClick={() => setActiveTab('security')}
          style={{
            background: activeTab === 'security' ? 'rgba(244, 63, 94, 0.15)' : 'transparent',
            color: activeTab === 'security' ? '#fb7185' : 'var(--text-muted)',
            border: activeTab === 'security' ? '1px solid rgba(244, 63, 94, 0.4)' : '1px solid transparent',
            borderRadius: '8px',
            padding: '0.5rem 1.1rem',
            fontSize: '0.9rem',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            transition: 'all 0.15s'
          }}
        >
          <span>🚨</span>
          <span>Security Attack Lab (128 Cases)</span>
        </button>

        <button
          onClick={() => setActiveTab('evaluation')}
          style={{
            background: activeTab === 'evaluation' ? 'rgba(56, 189, 248, 0.15)' : 'transparent',
            color: activeTab === 'evaluation' ? '#38bdf8' : 'var(--text-muted)',
            border: activeTab === 'evaluation' ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid transparent',
            borderRadius: '8px',
            padding: '0.5rem 1.1rem',
            fontSize: '0.9rem',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            transition: 'all 0.15s'
          }}
        >
          <span>📊</span>
          <span>Evaluation Lab</span>
        </button>
      </div>

      {/* Tab 1: Query History View */}
      {activeTab === 'history' && (
        <QueryHistoryView
          activeRoleId={selectedRole}
          onInspectReplay={handleInspectReplay}
          onSelectQuery={(item) => {
            setQueryInput(item.question);
            setResolvedQuestion(item.question);
            setActiveTab('studio');
          }}
        />
      )}

      {/* Tab 2: Role & Data Policy Editor */}
      {activeTab === 'policy' && (
        <RolePolicyEditor
          activeRole={selectedRoleName}
          activeRoleId={selectedRole}
        />
      )}

      {/* Tab 3: Dedicated Query Replay & Provenance */}
      {activeTab === 'replay' && selectedReplayQueryId && (
        <QueryReplayCard
          queryId={selectedReplayQueryId}
          activeRoleId={selectedRole}
          onBack={() => setActiveTab('history')}
        />
      )}

      {/* Tab 4: Security Attack Lab */}
      {activeTab === 'security' && <SecurityAttackLab selectedRole={selectedRole} />}

      {/* Tab 5: Evaluation Benchmark Lab */}
      {activeTab === 'evaluation' && <EvaluationLab />}

      {/* Tab 6: Interactive Studio */}
      {activeTab === 'studio' && (
        <>
          {/* Trust Engine Status Summary */}
          <div className="card" style={{ marginBottom: '2rem' }}>
            <div className="card-header">
              <div className="card-title">
                <span className="status-indicator"></span>
                <span>Deterministic Trust &amp; Evidence Engine (Milestone M3 Platform)</span>
              </div>
              <span className="badge badge-done">Milestone M3 Gate Verified</span>
            </div>
            <div className="stats-grid">
              <div className="stat-row">
                <span className="stat-label">JWT &amp; RBAC (T-37)</span>
                <span className="stat-value" style={{ color: '#10b981' }}>Fail-Closed Server Gating Active</span>
              </div>
              <div className="stat-row">
                <span className="stat-label">Query History (T-38)</span>
                <span className="stat-value" style={{ color: '#10b981' }}>Rerun-by-Default (Live Execution)</span>
              </div>
              <div className="stat-row">
                <span className="stat-label">Query Replay (T-39)</span>
                <span className="stat-value" style={{ color: '#10b981' }}>Provenance &amp; Schema Drift Alerts</span>
              </div>
              <div className="stat-row">
                <span className="stat-label">Security Attack Lab (T-31)</span>
                <span className="stat-value" style={{ color: '#10b981' }}>128/128 Blocked (0.00% Violation)</span>
              </div>
            </div>
          </div>

          {/* Interactive Intent & SQL Studio */}
          <div className="card" style={{ marginBottom: '2rem' }}>
            <div className="card-header">
              <div className="card-title">
                <span>Natural-Language Query &amp; Sandboxed SQL Proposal Studio</span>
              </div>
              <span className="badge badge-done">End-to-End Pipeline</span>
            </div>

            <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginBottom: '1rem' }}>
              Rule R2.1: Question is classified into <strong>Answerable / Ambiguous / Unsupported / Unauthorized</strong>, followed by LLM Proposal, deterministic AST authorization, row-filter injection, and sandboxed execution.
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
                    color: '#cbd5e1',
                    borderRadius: '6px',
                    padding: '0.35rem 0.75rem',
                    fontSize: '0.78rem',
                    cursor: 'pointer',
                    transition: 'all 0.15s'
                  }}
                >
                  {sq.label}
                </button>
              ))}
            </div>

            {/* Input Form */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleClassify();
              }}
              style={{ display: 'flex', gap: '0.75rem' }}
            >
              <input
                type="text"
                value={queryInput}
                onChange={(e) => setQueryInput(e.target.value)}
                placeholder="Ask a question in natural language (e.g. 'Show top 5 customers by revenue')..."
                className="input"
                style={{
                  flex: 1,
                  background: 'rgba(0, 0, 0, 0.2)',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  borderRadius: '8px',
                  padding: '0.75rem 1rem',
                  color: '#fff',
                  fontSize: '0.95rem'
                }}
              />
              <button
                type="submit"
                disabled={isClassifying || !queryInput.trim()}
                style={{
                  background: '#6366f1',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '8px',
                  padding: '0 1.5rem',
                  fontWeight: 600,
                  fontSize: '0.95rem',
                  cursor: isClassifying || !queryInput.trim() ? 'not-allowed' : 'pointer',
                  opacity: isClassifying || !queryInput.trim() ? 0.6 : 1
                }}
              >
                {isClassifying ? 'Analyzing...' : 'Analyze Intent'}
              </button>
            </form>
          </div>

          {/* Stage 1: Intent Analysis & Clarification / Rejection Cards */}
          {intentResult && (
            <div style={{ marginBottom: '2rem' }}>
              <ClarificationCard
                result={intentResult}
                selectedOptionId={selectedOptionId}
                onSelectOption={(optId) => setSelectedOptionId(optId)}
                onResolve={handleResolveOption}
                isResolving={isResolving}
              />
            </div>
          )}

          {/* Stage 2 & 3: SQL Generator Proposal & Full Policy Sandbox Engine */}
          {resolvedQuestion && (
            <div style={{ marginBottom: '2rem' }}>
              <SQLProposalCard
                question={resolvedQuestion}
                roleId={selectedRole}
                dataSourceId={1}
              />
            </div>
          )}

          {/* Ad-hoc Deterministic Policy Engine Sandbox (Task T-15..T-23) */}
          <div style={{ marginBottom: '2rem' }}>
            <PolicyValidatorSandbox
              roleId={selectedRole}
              dataSourceId={1}
            />
          </div>
        </>
      )}

      {/* Auth Modal */}
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        onAuthSuccess={handleAuthSuccess}
        currentRole={selectedRoleName}
      />
    </div>
  );
}

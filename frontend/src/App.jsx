import React, { useState, useEffect } from 'react';
import ClarificationCard from './components/ClarificationCard.jsx';
import RefusalStateCard from './components/RefusalStateCard.jsx';
import RolePolicyEditor from './components/RolePolicyEditor.jsx';
import QueryHistoryView from './components/QueryHistoryView.jsx';
import QueryReplayCard from './components/QueryReplayCard.jsx';
import OptimizationCard from './components/OptimizationCard.jsx';
import SecurityAttackLab from './components/SecurityAttackLab.jsx';
import EvaluationLab from './components/EvaluationLab.jsx';
import FailureObservatory from './components/FailureObservatory.jsx';
import PlannerAgentCard from './components/PlannerAgentCard.jsx';
import AuthModal from './components/AuthModal.jsx';

import QueryComposer from './components/query/QueryComposer.jsx';
import EvidenceChainPanel from './components/query/EvidenceChainPanel.jsx';
import QueryResultView from './components/query/QueryResultView.jsx';
import Badge from './components/ui/Badge.jsx';
import Button from './components/ui/Button.jsx';

import { apiFetch } from './utils/api.js';

export default function App() {
  const [activeTab, setActiveTab] = useState('workspace'); // 'workspace' | 'planner' | 'history' | 'governance' | 'performance' | 'security' | 'evaluation' | 'observatory' | 'replay'
  const [health, setHealth] = useState({
    status: 'operational',
    environment: 'local',
    metadata_db_connected: true,
    business_db_connected: true,
    version: '1.2.0',
  });
  const [selectedRole, setSelectedRole] = useState(() => {
    const saved = localStorage.getItem('auth_role_id');
    return saved ? Number(saved) : (localStorage.getItem('access_token') ? 1 : null);
  });
  const [selectedRoleName, setSelectedRoleName] = useState(() => {
    const saved = localStorage.getItem('auth_role_name');
    return saved || (localStorage.getItem('access_token') ? 'admin' : 'Unauthenticated');
  });
  const [selectedDataSourceId, setSelectedDataSourceId] = useState(1);
  const [dataSources, setDataSources] = useState([
    { data_source_id: 1, name: 'PostgreSQL Primary', db_type: 'postgresql' }
  ]);
  const [activeUserEmail, setActiveUserEmail] = useState(() => localStorage.getItem('auth_user_email') || '');
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [selectedReplayQueryId, setSelectedReplayQueryId] = useState(null);

  // Workspace Studio State
  const [queryInput, setQueryInput] = useState('');
  const [isExecuting, setIsExecuting] = useState(false);
  const [intentResult, setIntentResult] = useState(null);
  const [selectedOptionId, setSelectedOptionId] = useState(null);
  const [resolvedQuestion, setResolvedQuestion] = useState(null);
  const [activeExecutionData, setActiveExecutionData] = useState(null);

  useEffect(() => {
    apiFetch('/api/health')
      .then((res) => res.json())
      .then((data) => setHealth(data))
      .catch(() => {});

    apiFetch('/api/schema/data-sources')
      .then((res) => res.json())
      .then((resData) => {
        if (resData?.success && Array.isArray(resData.data) && resData.data.length > 0) {
          setDataSources(resData.data);
        }
      })
      .catch(() => {});
  }, []);

  const handleExecuteStudioQuery = async (overrideQuestion) => {
    const q = overrideQuestion || queryInput;
    if (!q.trim()) return;

    setIsExecuting(true);
    setIntentResult(null);
    setSelectedOptionId(null);
    setResolvedQuestion(null);

    try {
      // Step 1: Classify intent
      const intentRes = await apiFetch('/api/intent/classify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: q,
          role_id: selectedRole,
          data_source_id: selectedDataSourceId,
        }),
      });
      const intentData = await intentRes.json();

      if (intentData?.success) {
        const result = intentData.data;
        setIntentResult(result);

        if (result.classification === 'answerable') {
          // Step 2: Generate & Execute SQL proposal
          const sqlRes = await apiFetch('/api/sql/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              question: result.resolved_question || q,
              role_id: selectedRole,
              data_source_id: selectedDataSourceId,
            }),
          });
          const sqlData = await sqlRes.json();

          if (sqlData?.success) {
            const proposal = sqlData.data.proposal;
            const policyVal = sqlData.data.policy_validation;

            if (sqlData.data.can_execute && policyVal?.is_allowed) {
              // Execute in sandbox
              const execRes = await apiFetch('/api/sql/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  sql: proposal.sql,
                  role_id: selectedRole,
                  data_source_id: selectedDataSourceId,
                  question: q,
                }),
              });
              const execData = await execRes.json();

              setActiveExecutionData({
                question: q,
                sql: proposal.sql,
                policyValidation: policyVal,
                criticAnalysis: sqlData.data.critic_analysis,
                reliabilityScore: sqlData.data.reliability_breakdown?.overall_score || null,
                execution: execData?.data || { success: false, rows: [], columns: [], error: 'No execution result' },
              });
            } else {
              setActiveExecutionData({
                question: q,
                sql: proposal.sql,
                policyValidation: policyVal,
                criticAnalysis: sqlData.data.critic_analysis,
                reliabilityScore: sqlData.data.reliability_breakdown?.overall_score || null,
                execution: { success: false, rows: [], columns: [], error: 'Execution blocked by policy engine' },
              });
            }
          }
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsExecuting(false);
    }
  };

  const handleResolveClarification = async () => {
    if (!intentResult || !selectedOptionId) return;
    const selectedOption = intentResult.clarification_options.find((o) => o.option_id === selectedOptionId);
    if (!selectedOption) return;

    try {
      const res = await apiFetch('/api/intent/resolve', {
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
      if (data?.success) {
        setResolvedQuestion(data.data);
        handleExecuteStudioQuery(data.data.resolved_question);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleRoleSelectChange = (roleId) => {
    const roleNames = { 1: 'admin', 2: 'analyst', 3: 'viewer' };
    const name = roleNames[roleId] || 'viewer';
    setSelectedRole(roleId);
    setSelectedRoleName(name);
    localStorage.setItem('auth_role_id', String(roleId));
    localStorage.setItem('auth_role_name', name);
  };

  const handleAuthSuccess = (userData, accessToken) => {
    if (userData) {
      setActiveUserEmail(userData.email || '');
      const rId = userData.role_id || 1;
      const rName = userData.role?.role_name || (rId === 1 ? 'admin' : rId === 2 ? 'analyst' : 'viewer');
      setSelectedRole(rId);
      setSelectedRoleName(rName);
      localStorage.setItem('auth_role_id', String(rId));
      localStorage.setItem('auth_role_name', rName);
      localStorage.setItem('auth_user_email', userData.email || '');
    }
    setIsAuthModalOpen(false);
  };

  const handleInspectReplay = (queryId) => {
    setSelectedReplayQueryId(queryId);
    setActiveTab('replay');
  };

  const sampleQueries = [
    'How many active employees are in the company?',
    'What was our total sales revenue by product category in 2025?',
    'Show top 5 customers ranked by total spending',
    'Compare 2024 and 2025 revenue variance',
  ];

  return (
    <div className="app-container">
      {/* Enterprise Navigation Header */}
      <header className="header-bar">
        <div className="brand-block">
          <div className="brand-badge">TE</div>
          <div>
            <div className="brand-title">TrustEngine Platform</div>
            <div className="brand-subtitle">Evidence-Grounded Natural Language Analytics</div>
          </div>
        </div>

        <nav className="nav-tabs">
          <button
            onClick={() => setActiveTab('workspace')}
            className={`nav-tab-btn ${activeTab === 'workspace' ? 'active' : ''}`}
          >
            Workspace
          </button>
          <button
            onClick={() => setActiveTab('planner')}
            className={`nav-tab-btn ${activeTab === 'planner' ? 'active' : ''}`}
          >
            Compound Planner
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`nav-tab-btn ${activeTab === 'history' || activeTab === 'replay' ? 'active' : ''}`}
          >
            History &amp; Replay
          </button>
          <button
            onClick={() => setActiveTab('governance')}
            className={`nav-tab-btn ${activeTab === 'governance' ? 'active' : ''}`}
          >
            Governance
          </button>
          <button
            onClick={() => setActiveTab('performance')}
            className={`nav-tab-btn ${activeTab === 'performance' ? 'active' : ''}`}
          >
            Performance
          </button>
          <button
            onClick={() => setActiveTab('security')}
            className={`nav-tab-btn ${activeTab === 'security' ? 'active' : ''}`}
          >
            Security Suite
          </button>
          <button
            onClick={() => setActiveTab('evaluation')}
            className={`nav-tab-btn ${activeTab === 'evaluation' ? 'active' : ''}`}
          >
            Evaluation Benchmark
          </button>
          <button
            onClick={() => setActiveTab('observatory')}
            className={`nav-tab-btn ${activeTab === 'observatory' ? 'active' : ''}`}
          >
            Observatory
          </button>
        </nav>

        <div className="telemetry-group">
          {/* Dynamic Data Source Selector */}
          <select
            value={selectedDataSourceId}
            onChange={(e) => setSelectedDataSourceId(Number(e.target.value))}
            style={{
              background: 'var(--bg-subtle)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '4px',
              padding: '0.25rem 0.5rem',
              fontSize: '11px',
              fontFamily: 'var(--font-mono)',
              outline: 'none',
              cursor: 'pointer',
            }}
            title="Active Data Source"
          >
            {dataSources.map((ds) => (
              <option key={ds.data_source_id} value={ds.data_source_id}>
                DS #{ds.data_source_id}: {ds.name}
              </option>
            ))}
          </select>

          {/* Role selector (Admin Simulation) */}
          <select
            value={selectedRole || 1}
            onChange={(e) => handleRoleSelectChange(Number(e.target.value))}
            style={{
              background: 'var(--bg-subtle)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '4px',
              padding: '0.25rem 0.5rem',
              fontSize: '11px',
              fontFamily: 'var(--font-mono)',
              outline: 'none',
              cursor: 'pointer',
            }}
            title="Simulated Role (Policy Gating)"
          >
            <option value={1}>Simulate: Admin</option>
            <option value={2}>Simulate: Analyst</option>
            <option value={3}>Simulate: Viewer</option>
          </select>

          <Button
            variant="secondary"
            size="sm"
            onClick={() => setIsAuthModalOpen(true)}
          >
            Session: {selectedRoleName}
          </Button>

          <span className="status-tag active">
            <span className="status-dot" />
            Sandbox: Read-Only
          </span>
        </div>
      </header>

      {/* Main Tab Content */}
      <main>
        {activeTab === 'workspace' && (
          <div>
            <QueryComposer
              queryInput={queryInput}
              setQueryInput={setQueryInput}
              onSubmit={handleExecuteStudioQuery}
              isLoading={isExecuting}
              selectedRoleName={selectedRoleName}
              sampleQueries={sampleQueries}
            />

            {/* Ambiguity Clarification */}
            {intentResult?.classification === 'ambiguous' && (
              <ClarificationCard
                intentResult={intentResult}
                selectedOptionId={selectedOptionId}
                setSelectedOptionId={setSelectedOptionId}
                onResolve={handleResolveClarification}
                isResolving={isExecuting}
              />
            )}

            {/* Refusal States: Unauthorized or Unsupported */}
            {(intentResult?.classification === 'unauthorized' || intentResult?.classification === 'unsupported') && (
              <RefusalStateCard
                intentResult={intentResult}
                selectedRoleName={selectedRoleName}
              />
            )}

            {/* Forensic Evidence Chain Hero */}
            {activeExecutionData && (
              <>
                <EvidenceChainPanel
                  queryResult={activeExecutionData}
                  policyValidation={activeExecutionData.policyValidation}
                  criticAnalysis={activeExecutionData.criticAnalysis}
                  reliabilityScore={activeExecutionData.reliabilityScore}
                />

                <QueryResultView
                  generatedSQL={activeExecutionData.sql}
                  executionResult={activeExecutionData.execution}
                  criticFindings={activeExecutionData.criticAnalysis?.findings || []}
                  policyViolations={activeExecutionData.policyValidation?.violations || []}
                />
              </>
            )}
          </div>
        )}

        {activeTab === 'planner' && (
          <PlannerAgentCard
            selectedRole={selectedRole}
            selectedRoleName={selectedRoleName}
            dataSourceId={selectedDataSourceId}
          />
        )}

        {activeTab === 'history' && (
          <QueryHistoryView
            dataSourceId={selectedDataSourceId}
            onRerunQuery={(q) => {
              setQueryInput(q);
              setActiveTab('workspace');
              handleExecuteStudioQuery(q);
            }}
            onInspectReplay={handleInspectReplay}
          />
        )}

        {activeTab === 'replay' && (
          <div>
            <div style={{ marginBottom: '1rem' }}>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setActiveTab('history')}
              >
                ← Back to History
              </Button>
            </div>
            <QueryReplayCard
              initialQueryId={selectedReplayQueryId}
              selectedRole={selectedRole}
              selectedRoleName={selectedRoleName}
              dataSourceId={selectedDataSourceId}
            />
          </div>
        )}

        {activeTab === 'governance' && (
          <RolePolicyEditor
            selectedRole={selectedRole}
            selectedRoleName={selectedRoleName}
            dataSourceId={selectedDataSourceId}
          />
        )}

        {activeTab === 'performance' && (
          <OptimizationCard
            selectedRole={selectedRole}
            selectedRoleName={selectedRoleName}
            dataSourceId={selectedDataSourceId}
          />
        )}

        {activeTab === 'security' && (
          <SecurityAttackLab
            selectedRole={selectedRole}
            selectedRoleName={selectedRoleName}
            dataSourceId={selectedDataSourceId}
          />
        )}

        {activeTab === 'evaluation' && (
          <EvaluationLab
            selectedRole={selectedRole}
            selectedRoleName={selectedRoleName}
            dataSourceId={selectedDataSourceId}
          />
        )}

        {activeTab === 'observatory' && (
          <FailureObservatory
            selectedRole={selectedRole}
            selectedRoleName={selectedRoleName}
            dataSourceId={selectedDataSourceId}
          />
        )}
      </main>

      {/* Auth Modal */}
      {isAuthModalOpen && (
        <AuthModal
          isOpen={isAuthModalOpen}
          onClose={() => setIsAuthModalOpen(false)}
          onAuthSuccess={handleAuthSuccess}
          currentRole={selectedRoleName}
        />
      )}
    </div>
  );
}

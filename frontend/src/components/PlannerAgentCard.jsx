import React, { useState } from 'react';
import { apiFetch } from '../utils/api.js';
import {
  Workflow,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Database,
  ArrowRight,
  ShieldCheck,
  ShieldAlert,
  ChevronDown,
  ChevronUp,
  Layers,
  FileCode,
  Table,
  Play
} from 'lucide-react';

export default function PlannerAgentCard({
  activeRole = 'admin',
  activeRoleId = 1,
  dataSourceId = 1,
  onApplyQuestion
}) {
  const [question, setQuestion] = useState('Compare revenue from 2023 vs 2024 and calculate growth');
  const [isRunning, setIsRunning] = useState(false);
  const [planResult, setPlanResult] = useState(null);
  const [error, setError] = useState(null);
  const [expandedSteps, setExpandedSteps] = useState({ 1: true, 2: true, 3: true });

  const sampleCompoundQueries = [
    'Compare revenue from 2023 vs 2024 and calculate growth',
    'Compare top 5 and bottom 5 customers by total spending',
    'Compare customer orders across regions and calculate delta'
  ];

  const handleRunPlanner = async (qToRun) => {
    const targetQ = qToRun || question;
    if (!targetQ.trim()) return;

    setIsRunning(true);
    setError(null);
    setPlanResult(null);

    try {
      const res = await apiFetch('/api/agent/execute', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': activeRole
        },
        body: JSON.stringify({
          question: targetQ,
          role_id: activeRoleId,
          data_source_id: dataSourceId
        })
      });

      if (!res.ok) {
        throw new Error('Failed to execute multi-step planner agent');
      }

      const json = await res.json();
      if (json.success && json.data) {
        setPlanResult(json.data);
      } else {
        throw new Error(json.message || 'Planner agent execution failed');
      }
    } catch (err) {
      console.error(err);
      setError(err.message || 'Error executing planner agent');
    } finally {
      setIsRunning(false);
    }
  };

  const toggleStep = (stepId) => {
    setExpandedSteps(prev => ({ ...prev, [stepId]: !prev[stepId] }));
  };

  return (
    <div className="space-y-6 text-slate-100" role="region" aria-label="Multi-Step Planner Agent">
      {/* Top Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 p-6 rounded-2xl border border-indigo-900/30 shadow-xl backdrop-blur-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="p-2 rounded-xl bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                <Workflow className="w-5 h-5" />
              </span>
              <h2 className="text-2xl font-bold text-slate-100 tracking-tight">Multi-Step Planner Agent</h2>
              <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/40">
                REQ-AGENT-01 &bull; P2
              </span>
            </div>
            <p className="mt-2 text-sm text-slate-400 max-w-3xl">
              Autonomous DAG decomposition for compound analytical questions. Deconstructs multi-period comparisons, cross-table ratio derivations, and entity cohorts with deterministic <strong>Policy Engine (Rule R6.1)</strong> verification on every single sub-step.
            </p>
          </div>
        </div>
      </div>

      {/* Input Form & Sample Chips */}
      <div className="bg-slate-900/80 p-5 rounded-2xl border border-slate-800/80 shadow-lg space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-slate-400">Sample Compound Inquiries:</span>
          {sampleCompoundQueries.map((sq, idx) => (
            <button
              key={idx}
              onClick={() => {
                setQuestion(sq);
                handleRunPlanner(sq);
              }}
              className="text-xs px-3 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 border border-slate-700 hover:border-slate-600 transition-colors"
            >
              {sq}
            </button>
          ))}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleRunPlanner();
          }}
          className="flex gap-3"
        >
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Enter compound analytical question (e.g. 'Compare 2023 vs 2024 revenue growth')..."
            className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
          />
          <button
            type="submit"
            disabled={isRunning || !question.trim()}
            className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold rounded-xl text-sm transition-colors flex items-center gap-2 shadow-lg shadow-indigo-600/30"
          >
            <Play className={`w-4 h-4 ${isRunning ? 'animate-spin' : ''}`} />
            <span>{isRunning ? 'Planning & Executing...' : 'Execute Multi-Step Plan'}</span>
          </button>
        </form>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-950/50 border border-red-800/50 text-red-300 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 flex-shrink-0 text-red-400" />
          <p className="text-sm">{error}</p>
        </div>
      )}

      {/* Plan Execution Results */}
      {planResult && (
        <div className="space-y-6">
          {/* Synthesized Response Banner */}
          <div className="bg-gradient-to-r from-emerald-950/30 via-slate-900 to-indigo-950/30 p-5 rounded-2xl border border-emerald-900/40 shadow-lg space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-emerald-400" />
                <h3 className="text-base font-bold text-slate-100">Synthesized Analytical Findings</h3>
              </div>
              <div className="flex items-center gap-2">
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase ${
                  planResult.overall_status === 'COMPLETED'
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                    : 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                }`}>
                  {planResult.overall_status}
                </span>
                <span className="text-xs font-mono text-slate-400">
                  {planResult.total_execution_ms}ms total
                </span>
              </div>
            </div>
            <p className="text-sm text-slate-200 leading-relaxed font-medium">
              {planResult.synthesized_answer}
            </p>
          </div>

          {/* Execution Plan DAG Steps */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-slate-200 flex items-center gap-2">
                <Layers className="w-4 h-4 text-indigo-400" />
                <span>Execution DAG Breakdown ({planResult.step_results?.length || 0} Sub-Tasks)</span>
              </h3>
              <span className="text-xs text-slate-400">
                Deterministic security checks active per step
              </span>
            </div>

            <div className="space-y-3">
              {(planResult.step_results || []).map((step) => {
                const isExpanded = !!expandedSteps[step.step_id];
                return (
                  <div
                    key={step.step_id}
                    className="bg-slate-900/80 rounded-2xl border border-slate-800 shadow-md overflow-hidden transition-all"
                  >
                    {/* Step Header */}
                    <div
                      onClick={() => toggleStep(step.step_id)}
                      className="p-4 flex items-center justify-between cursor-pointer hover:bg-slate-800/50 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <span className="w-7 h-7 rounded-xl bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 flex items-center justify-center text-xs font-bold font-mono">
                          {step.step_id}
                        </span>
                        <div>
                          <h4 className="text-sm font-semibold text-slate-200">{step.task_name}</h4>
                          <span className="text-xs text-slate-400 font-mono">
                            {step.execution_ms}ms &bull; {step.row_count} rows returned
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        {step.policy_allowed ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 text-xs font-medium">
                            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                            <span>Authorized</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-rose-500/10 text-rose-300 border border-rose-500/30 text-xs font-medium">
                            <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
                            <span>Policy Blocked</span>
                          </span>
                        )}

                        {isExpanded ? (
                          <ChevronUp className="w-4 h-4 text-slate-400" />
                        ) : (
                          <ChevronDown className="w-4 h-4 text-slate-400" />
                        )}
                      </div>
                    </div>

                    {/* Step Content */}
                    {isExpanded && (
                      <div className="p-4 pt-0 border-t border-slate-800/80 space-y-3 text-xs">
                        {/* Generated SQL */}
                        {step.generated_sql && (
                          <div>
                            <span className="text-slate-400 font-semibold block mb-1">Generated Sub-Query SQL</span>
                            <pre className="p-3 bg-slate-950 rounded-xl border border-slate-800/80 text-amber-300 font-mono overflow-x-auto whitespace-pre-wrap">
                              {step.generated_sql}
                            </pre>
                          </div>
                        )}

                        {/* Error Diagnostic if any */}
                        {step.error && (
                          <div className="p-3 bg-rose-950/30 rounded-xl border border-rose-900/40 text-rose-300 font-mono">
                            {step.error}
                          </div>
                        )}

                        {/* Intermediate Result Table Preview */}
                        {step.rows && step.rows.length > 0 && (
                          <div>
                            <span className="text-slate-400 font-semibold block mb-1">Intermediate Results</span>
                            <div className="overflow-x-auto rounded-xl border border-slate-800">
                              <table className="w-full text-left font-mono text-[11px] text-slate-300">
                                <thead className="bg-slate-950 text-slate-400 border-b border-slate-800">
                                  <tr>
                                    {(step.columns || Object.keys(step.rows[0])).map((col) => (
                                      <th key={col} className="py-2 px-3">{col}</th>
                                    ))}
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-800/50 bg-slate-900/40">
                                  {step.rows.slice(0, 5).map((row, rIdx) => (
                                    <tr key={rIdx} className="hover:bg-slate-800/40">
                                      {(step.columns || Object.keys(row)).map((col) => (
                                        <td key={col} className="py-2 px-3 text-slate-200">
                                          {String(row[col] ?? 'NULL')}
                                        </td>
                                      ))}
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

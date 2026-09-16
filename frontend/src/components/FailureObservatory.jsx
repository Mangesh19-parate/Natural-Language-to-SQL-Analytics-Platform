import React, { useState, useEffect, useCallback } from 'react';
import { apiFetch } from '../utils/api.js';
import {
  AlertTriangle,
  Flame,
  Search,
  RefreshCw,
  Filter,
  Layers,
  Sparkles,
  CheckCircle2,
  XCircle,
  Clock,
  ShieldAlert,
  HelpCircle,
  ChevronRight,
  Database,
  ExternalLink,
  Sliders,
  Copy,
  Check
} from 'lucide-react';

const FAILURE_CLASS_META = {
  syntax_error: {
    label: 'Syntax Error',
    color: 'bg-rose-500/20 text-rose-300 border-rose-500/30',
    barColor: 'bg-rose-500',
    icon: XCircle,
    desc: 'SQL dialect or parser generation errors'
  },
  schema_mismatch: {
    label: 'Schema Mismatch',
    color: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
    barColor: 'bg-amber-500',
    icon: Database,
    desc: 'Referenced nonexistent table or column names'
  },
  policy_violation: {
    label: 'Policy Violation',
    color: 'bg-red-600/20 text-red-300 border-red-600/30',
    barColor: 'bg-red-600',
    icon: ShieldAlert,
    desc: 'RBAC, DDL block, or security rule rejections'
  },
  semantic_drift: {
    label: 'Semantic Drift',
    color: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
    barColor: 'bg-purple-500',
    icon: Layers,
    desc: 'SQL generated deviates from user intent logic'
  },
  timeout_exhaustion: {
    label: 'Timeout Exhaustion',
    color: 'bg-orange-500/20 text-orange-300 border-orange-500/30',
    barColor: 'bg-orange-500',
    icon: Clock,
    desc: 'Query execution exceeded maximum budget'
  },
  empty_result_anomaly: {
    label: 'Empty Result Anomaly',
    color: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
    barColor: 'bg-yellow-500',
    icon: AlertTriangle,
    desc: 'Zero records returned where data was expected'
  },
  critic_rejection: {
    label: 'Critic Rejection',
    color: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',
    barColor: 'bg-indigo-500',
    icon: Sliders,
    desc: 'Critic score fell below acceptance threshold'
  },
  unsupported_intent: {
    label: 'Unsupported Intent',
    color: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
    barColor: 'bg-slate-500',
    icon: HelpCircle,
    desc: 'Request out of domain or conversational refusal'
  }
};

export default function FailureObservatory({ activeRole = 'admin' }) {
  const [stats, setStats] = useState(null);
  const [phrases, setPhrases] = useState([]);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedClass, setSelectedClass] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedLog, setSelectedLog] = useState(null);
  const [copiedId, setCopiedId] = useState(null);

  const fetchObservatoryData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const headers = { 'X-User-Role': activeRole };
      const [statsRes, phrasesRes, logsRes] = await Promise.all([
        apiFetch('/api/observatory/stats', { headers }),
        apiFetch('/api/observatory/phrases', { headers }),
        apiFetch('/api/observatory/logs?limit=50', { headers })
      ]);

      if (!statsRes.ok || !phrasesRes.ok || !logsRes.ok) {
        throw new Error('Failed to fetch failure observatory analytics');
      }

      const statsJson = await statsRes.json();
      const phrasesJson = await phrasesRes.json();
      const logsJson = await logsRes.json();

      setStats(statsJson.data || statsJson);
      setPhrases(phrasesJson.data || phrasesJson);
      setLogs(logsJson.data || logsJson);
    } catch (err) {
      console.error(err);
      setError(err.message || 'Error loading failure observatory');
    } finally {
      setLoading(false);
    }
  }, [activeRole]);

  useEffect(() => {
    fetchObservatoryData();
  }, [fetchObservatoryData]);

  const copyToClipboard = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const filteredLogs = logs.filter(log => {
    const matchesClass = selectedClass === 'all' || log.failure_class === selectedClass;
    const matchesSearch = !searchQuery || 
      (log.problematic_phrase && log.problematic_phrase.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (log.failure_class && log.failure_class.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (log.query_id && log.query_id.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesClass && matchesSearch;
  });

  return (
    <div className="space-y-6 text-slate-100" role="region" aria-label="Failure Observatory Analytics">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-rose-950/40 to-slate-900 p-6 rounded-2xl border border-rose-900/30 shadow-xl backdrop-blur-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="p-2 rounded-xl bg-rose-500/20 text-rose-400 border border-rose-500/30">
                <Flame className="w-5 h-5" />
              </span>
              <h2 className="text-2xl font-bold text-slate-100 tracking-tight">Failure Observatory</h2>
              <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/40">
                REQ-FAILOBS-01
              </span>
            </div>
            <p className="mt-2 text-sm text-slate-400 max-w-3xl">
              Real-time failure taxonomy aggregation across 8 diagnostic classes, automated bi-gram/tri-gram clustering of problematic phrases, and catalog intervention triggers for continuous accuracy tuning.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={fetchObservatoryData}
              disabled={loading}
              className="px-4 py-2 text-sm font-medium text-slate-300 bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 rounded-xl flex items-center gap-2 transition-all hover:border-slate-600 disabled:opacity-50"
              aria-label="Refresh Observatory Data"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-950/50 border border-red-800/50 text-red-300 flex items-center gap-3">
          <XCircle className="w-5 h-5 flex-shrink-0 text-red-400" />
          <p className="text-sm font-medium">{error}</p>
        </div>
      )}

      {/* Top Level Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800/80 shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Total Failures</span>
            <AlertTriangle className="w-4 h-4 text-rose-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-white tracking-tight">
              {stats?.total_failures ?? 0}
            </span>
            <span className="text-xs text-slate-400">logged events</span>
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800/80 shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Failure Rate</span>
            <Sliders className="w-4 h-4 text-amber-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-amber-400 tracking-tight">
              {stats?.failure_rate != null ? `${stats.failure_rate.toFixed(1)}%` : '0.0%'}
            </span>
            <span className="text-xs text-slate-400">of total executions</span>
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800/80 shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Dominant Class</span>
            <Layers className="w-4 h-4 text-purple-400" />
          </div>
          <div className="mt-3">
            <span className="text-lg font-bold text-purple-300 block truncate">
              {stats?.failure_classes?.[0] ? (FAILURE_CLASS_META[stats.failure_classes[0].failure_class]?.label || stats.failure_classes[0].failure_class) : 'None'}
            </span>
            <span className="text-xs text-slate-400">most frequent pattern</span>
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800/80 shadow-md">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">Catalog Interventions</span>
            <Sparkles className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-cyan-300 tracking-tight">
              {stats?.top_problematic_phrases?.length ?? 0}
            </span>
            <span className="text-xs text-slate-400">actionable fixes</span>
          </div>
        </div>
      </div>

      {/* Main Grid: Taxonomy Breakdown + Problematic Phrases + Interventions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Failure Taxonomy Breakdown */}
        <div className="lg:col-span-2 bg-slate-900/80 p-6 rounded-2xl border border-slate-800/80 shadow-lg space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-semibold text-slate-200">Failure Class Distribution</h3>
              <p className="text-xs text-slate-400">8 diagnostic failure categories defined in REQ-FAILOBS-01</p>
            </div>
            <button
              onClick={() => setSelectedClass('all')}
              className={`text-xs px-2.5 py-1 rounded-lg border transition-colors ${
                selectedClass === 'all' 
                  ? 'bg-rose-500/20 border-rose-500/40 text-rose-300 font-medium' 
                  : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-slate-200'
              }`}
            >
              Show All ({stats?.total_failures ?? 0})
            </button>
          </div>

          <div className="space-y-3 pt-2">
            {(stats?.failure_classes || stats?.failure_breakdown || []).map(item => {
              const meta = FAILURE_CLASS_META[item.failure_class] || {
                label: item.failure_class,
                color: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
                barColor: 'bg-slate-500',
                icon: AlertTriangle,
                desc: item.description || 'Unclassified failure'
              };
              const Icon = meta.icon;
              const isSelected = selectedClass === item.failure_class;

              return (
                <div
                  key={item.failure_class}
                  onClick={() => setSelectedClass(isSelected ? 'all' : item.failure_class)}
                  className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-slate-800/90 border-rose-500/50 shadow-md ring-1 ring-rose-500/30'
                      : 'bg-slate-950/40 border-slate-800/60 hover:bg-slate-800/50 hover:border-slate-700'
                  }`}
                  role="button"
                  tabIndex={0}
                  aria-pressed={isSelected}
                  onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') setSelectedClass(isSelected ? 'all' : item.failure_class); }}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2.5">
                      <span className={`p-1.5 rounded-lg border ${meta.color}`}>
                        <Icon className="w-4 h-4" />
                      </span>
                      <div>
                        <span className="text-sm font-semibold text-slate-200">{meta.label}</span>
                        <span className="ml-2 text-xs text-slate-400">({item.description || meta.desc})</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-bold text-slate-100">{item.count}</span>
                      <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 border border-slate-700 text-slate-300 font-mono">
                        {item.percentage.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  {/* Progress Bar */}
                  <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${meta.barColor} transition-all duration-500 rounded-full`}
                      style={{ width: `${Math.max(item.percentage, item.count > 0 ? 3 : 0)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: Problematic Phrases & Recommendations */}
        <div className="space-y-6">
          {/* Problematic Phrases Card */}
          <div className="bg-slate-900/80 p-5 rounded-2xl border border-slate-800/80 shadow-lg space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Search className="w-4 h-4 text-amber-400" />
                <h3 className="text-sm font-semibold text-slate-200">Problematic Phrases</h3>
              </div>
              <span className="text-xs text-slate-400">Bi-gram / Tri-gram Clusters</span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              N-grams frequently correlated with pipeline failures or low critic confidence:
            </p>

            <div className="space-y-2 pt-1 max-h-56 overflow-y-auto pr-1">
              {(phrases || []).length === 0 ? (
                <div className="p-4 rounded-xl bg-slate-950/40 text-center text-xs text-slate-400">
                  No problematic phrase clusters detected yet.
                </div>
              ) : (
                phrases.slice(0, 8).map((p, idx) => (
                  <div
                    key={idx}
                    className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/70 flex items-center justify-between text-xs hover:border-slate-700 transition-colors"
                  >
                    <span className="font-mono text-amber-300 font-medium">"{p.phrase}"</span>
                    <div className="flex items-center gap-2">
                      <span className="text-slate-400 text-[11px] truncate max-w-[90px]">
                        {p.affected_categories?.[0] || 'anomaly'}
                      </span>
                      <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold font-mono">
                        {p.occurrences || p.count || 1}x
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Recommended Interventions Card */}
          <div className="bg-slate-900/80 p-5 rounded-2xl border border-cyan-900/40 shadow-lg space-y-3">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-cyan-400" />
              <h3 className="text-sm font-semibold text-cyan-200">Recommended Interventions</h3>
            </div>
            <p className="text-xs text-slate-400">
              Automated suggestions generated from failure patterns to improve schema grounding:
            </p>

            <div className="space-y-2 pt-1 max-h-60 overflow-y-auto pr-1">
              {(stats?.top_problematic_phrases || []).length === 0 ? (
                <div className="p-4 rounded-xl bg-slate-950/40 text-center text-xs text-slate-400">
                  {stats?.top_recommended_intervention || "All systems operating within acceptable thresholds."}
                </div>
              ) : (
                (stats?.top_problematic_phrases || []).map((p, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-xl bg-cyan-950/20 border border-cyan-800/30 text-xs text-slate-300 space-y-1.5 hover:border-cyan-700/50 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-cyan-300">Fix for "{p.phrase}"</span>
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                        P1 Catalog Fix
                      </span>
                    </div>
                    <p className="text-slate-300 leading-relaxed">{p.recommended_intervention}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Live Failure Log Stream Table */}
      <div className="bg-slate-900/80 p-6 rounded-2xl border border-slate-800/80 shadow-lg space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-slate-200">Live Failure Stream</h3>
            <p className="text-xs text-slate-400">
              Showing {filteredLogs.length} events {selectedClass !== 'all' ? `filtered by ${FAILURE_CLASS_META[selectedClass]?.label || selectedClass}` : ''}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                placeholder="Search queries, errors..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="pl-9 pr-3 py-1.5 text-xs bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-rose-500 w-56 sm:w-64"
                aria-label="Filter failure stream"
              />
            </div>
          </div>
        </div>

        <div className="overflow-x-auto rounded-xl border border-slate-800">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950 text-slate-400 font-semibold border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Timestamp</th>
                <th className="py-3 px-4">Failure Class</th>
                <th className="py-3 px-4">Natural Language Query</th>
                <th className="py-3 px-4">Diagnostic Error</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 bg-slate-900/40">
              {filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-slate-500">
                    No failure records matching the current filters.
                  </td>
                </tr>
              ) : (
                filteredLogs.map(log => {
                  const meta = FAILURE_CLASS_META[log.failure_class] || {
                    label: log.failure_class,
                    color: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
                    icon: AlertTriangle
                  };
                  const Icon = meta.icon;

                  return (
                    <tr key={log.id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="py-3 px-4 font-mono text-slate-400 whitespace-nowrap">
                        {new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </td>
                      <td className="py-3 px-4 whitespace-nowrap">
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-medium ${meta.color}`}>
                          <Icon className="w-3.5 h-3.5" />
                          <span>{meta.label}</span>
                        </span>
                      </td>
                      <td className="py-3 px-4 max-w-xs truncate text-slate-200 font-medium">
                        {log.natural_query}
                      </td>
                      <td className="py-3 px-4 max-w-sm truncate text-rose-300 font-mono">
                        {log.error_message || 'N/A'}
                      </td>
                      <td className="py-3 px-4 text-right whitespace-nowrap">
                        <button
                          onClick={() => setSelectedLog(log)}
                          className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700 hover:border-slate-600 transition-colors"
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal / Inspector Dialog */}
      {selectedLog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full p-6 shadow-2xl space-y-5 text-slate-200 max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-rose-400" />
                <h3 className="text-lg font-bold">Failure Event Inspector</h3>
              </div>
              <button
                onClick={() => setSelectedLog(null)}
                className="text-slate-400 hover:text-slate-200 p-1 rounded-lg hover:bg-slate-800"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <label className="text-slate-400 font-semibold block mb-1">Failure Class</label>
                <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg border font-medium ${FAILURE_CLASS_META[selectedLog.failure_class]?.color || 'bg-slate-800 text-slate-300'}`}>
                  {FAILURE_CLASS_META[selectedLog.failure_class]?.label || selectedLog.failure_class}
                </span>
              </div>

              <div>
                <label className="text-slate-400 font-semibold block mb-1">Natural Query</label>
                <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 text-slate-100 font-medium">
                  {selectedLog.natural_query}
                </div>
              </div>

              {selectedLog.generated_sql && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-slate-400 font-semibold">Generated SQL</label>
                    <button
                      onClick={() => copyToClipboard(selectedLog.generated_sql, 'sql')}
                      className="text-[11px] text-slate-400 hover:text-slate-200 flex items-center gap-1"
                    >
                      {copiedId === 'sql' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      <span>{copiedId === 'sql' ? 'Copied' : 'Copy SQL'}</span>
                    </button>
                  </div>
                  <pre className="p-3 bg-slate-950 rounded-xl border border-slate-800 text-amber-300 font-mono overflow-x-auto whitespace-pre-wrap">
                    {selectedLog.generated_sql}
                  </pre>
                </div>
              )}

              <div>
                <label className="text-slate-400 font-semibold block mb-1">Error Diagnostics</label>
                <div className="p-3 bg-rose-950/30 rounded-xl border border-rose-900/40 text-rose-300 font-mono whitespace-pre-wrap">
                  {selectedLog.error_message || 'No additional error payload available'}
                </div>
              </div>

              {selectedLog.execution_context && Object.keys(selectedLog.execution_context).length > 0 && (
                <div>
                  <label className="text-slate-400 font-semibold block mb-1">Execution Context</label>
                  <pre className="p-3 bg-slate-950 rounded-xl border border-slate-800 text-slate-400 font-mono overflow-x-auto">
                    {JSON.stringify(selectedLog.execution_context, null, 2)}
                  </pre>
                </div>
              )}
            </div>

            <div className="flex justify-end pt-3 border-t border-slate-800">
              <button
                onClick={() => setSelectedLog(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl font-medium text-xs transition-colors"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

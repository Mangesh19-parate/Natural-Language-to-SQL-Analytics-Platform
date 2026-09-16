import React from 'react';
import {
  ShieldAlert,
  HelpCircle,
  AlertTriangle,
  ArrowRight,
  BookOpen,
  RefreshCw,
  Info,
  CheckCircle2,
  Lock
} from 'lucide-react';

/**
 * RefusalStateCard component implements calm, accessible refusal states for:
 * 1. Unsupported question / Out-of-Domain questions (§3.3)
 * 2. Policy rejection / RBAC restriction (§3.4)
 * 3. Ambiguous intent requiring safe refusal (§3.5)
 */
export default function RefusalStateCard({
  type = 'unsupported', // 'unsupported' | 'policy_violation' | 'ambiguous' | 'critic_rejection'
  title,
  reason,
  details,
  suggestions = [],
  policyRule,
  requiredRole,
  activeRole,
  onSelectSuggestion,
  onRetry
}) {
  const isPolicy = type === 'policy_violation';
  const isUnsupported = type === 'unsupported';
  const isAmbiguous = type === 'ambiguous';
  const isCritic = type === 'critic_rejection';

  const defaultTitle = isPolicy
    ? 'Query Restricted by Governance Policy'
    : isUnsupported
    ? 'Unable to Process Question'
    : isAmbiguous
    ? 'Ambiguous Query Request'
    : 'Query Rejected by Safety Critic';

  const defaultReason = isPolicy
    ? 'This query attempts to access restricted columns or perform operations prohibited for your active role.'
    : isUnsupported
    ? 'The question falls outside the semantic schema of the current database or requires data not available.'
    : isAmbiguous
    ? 'The intent contains multiple conflicting interpretations that cannot be safely resolved automatically.'
    : 'The generated SQL failed semantic validation and policy critic safety checks.';

  return (
    <div
      className={`rounded-2xl border p-6 transition-all shadow-xl backdrop-blur-md ${
        isPolicy
          ? 'bg-gradient-to-b from-slate-900 via-rose-950/20 to-slate-900 border-rose-900/40 text-slate-100'
          : isUnsupported
          ? 'bg-gradient-to-b from-slate-900 via-slate-800/40 to-slate-900 border-slate-700/60 text-slate-100'
          : isCritic
          ? 'bg-gradient-to-b from-slate-900 via-amber-950/20 to-slate-900 border-amber-900/40 text-slate-100'
          : 'bg-gradient-to-b from-slate-900 via-purple-950/20 to-slate-900 border-purple-900/40 text-slate-100'
      }`}
      role="alert"
      aria-live="polite"
      aria-labelledby="refusal-title"
    >
      {/* Header Icon + Title */}
      <div className="flex items-start gap-4">
        <div
          className={`p-3 rounded-2xl border flex-shrink-0 ${
            isPolicy
              ? 'bg-rose-500/20 text-rose-400 border-rose-500/30'
              : isUnsupported
              ? 'bg-slate-700/40 text-slate-300 border-slate-600/50'
              : isCritic
              ? 'bg-amber-500/20 text-amber-400 border-amber-500/30'
              : 'bg-purple-500/20 text-purple-400 border-purple-500/30'
          }`}
        >
          {isPolicy ? (
            <ShieldAlert className="w-6 h-6" aria-hidden="true" />
          ) : isUnsupported ? (
            <HelpCircle className="w-6 h-6" aria-hidden="true" />
          ) : isCritic ? (
            <Lock className="w-6 h-6" aria-hidden="true" />
          ) : (
            <AlertTriangle className="w-6 h-6" aria-hidden="true" />
          )}
        </div>

        <div className="space-y-1 flex-1">
          <div className="flex items-center gap-2.5 flex-wrap">
            <h3 id="refusal-title" className="text-lg font-bold text-slate-100 tracking-tight">
              {title || defaultTitle}
            </h3>
            <span
              className={`px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider border ${
                isPolicy
                  ? 'bg-rose-950/60 text-rose-300 border-rose-800/60'
                  : isUnsupported
                  ? 'bg-slate-800 text-slate-300 border-slate-700'
                  : 'bg-amber-950/60 text-amber-300 border-amber-800/60'
              }`}
            >
              {isPolicy ? 'Policy Guardrail' : isUnsupported ? 'Out of Scope' : 'Validation Error'}
            </span>
          </div>
          <p className="text-sm text-slate-300 leading-relaxed">
            {reason || defaultReason}
          </p>
        </div>
      </div>

      {/* Details Box */}
      {details && (
        <div className="mt-4 p-3.5 bg-slate-950/60 rounded-xl border border-slate-800/80 text-xs font-mono text-slate-300 break-words">
          <div className="flex items-center gap-2 mb-1 text-slate-400 font-sans font-semibold">
            <Info className="w-3.5 h-3.5 text-slate-400" />
            <span>Diagnostics</span>
          </div>
          {details}
        </div>
      )}

      {/* Policy Governance Context (for policy violations) */}
      {isPolicy && (policyRule || requiredRole) && (
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3 p-3.5 bg-slate-950/60 rounded-xl border border-rose-950/50 text-xs">
          {policyRule && (
            <div>
              <span className="text-slate-400 font-medium block">Rule Triggered</span>
              <span className="text-rose-300 font-mono font-semibold">{policyRule}</span>
            </div>
          )}
          {requiredRole && (
            <div>
              <span className="text-slate-400 font-medium block">Required Privilege</span>
              <span className="text-amber-300 font-semibold">
                {requiredRole.toUpperCase()} (Current: {activeRole?.toUpperCase() || 'ANONYMOUS'})
              </span>
            </div>
          )}
        </div>
      )}

      {/* Suggestions for Rephrasing or Alternative Queries */}
      {suggestions && suggestions.length > 0 && (
        <div className="mt-5 space-y-2.5">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-300 uppercase tracking-wider">
            <BookOpen className="w-3.5 h-3.5 text-slate-400" />
            <span>Recommended Alternatives</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {suggestions.map((sug, idx) => (
              <button
                key={idx}
                onClick={() => onSelectSuggestion && onSelectSuggestion(sug)}
                className="p-3 text-left bg-slate-950/50 hover:bg-slate-800/60 border border-slate-800 hover:border-slate-700 rounded-xl transition-all flex items-center justify-between group text-xs text-slate-200"
                aria-label={`Try suggested query: ${sug}`}
              >
                <span className="truncate pr-2 font-medium group-hover:text-cyan-300">{sug}</span>
                <ArrowRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-cyan-400 group-hover:translate-x-0.5 transition-all flex-shrink-0" />
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Footer Actions */}
      <div className="mt-5 pt-4 border-t border-slate-800 flex items-center justify-between gap-4">
        <p className="text-xs text-slate-400">
          Need help? Consult database catalog schema docs or reach out to your data administrator.
        </p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="px-3 py-1.5 text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-xl flex items-center gap-1.5 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Retry</span>
          </button>
        )}
      </div>
    </div>
  );
}

import { X, Shield, AlertTriangle, CheckCircle, Brain, GitBranch, MessageSquare, Zap, TrendingDown } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useState } from 'react'
import { cn, riskColor, formatAmount, formatDate, decisionColor } from '@/lib/utils'
import { RiskGauge } from './RiskGauge'
import { apiFeedbackSubmit } from '@/api/client'
import type { LiveTransaction } from '@/types'

interface InvestigationPanelProps {
  transaction: LiveTransaction | null
  onClose: () => void
}

export function InvestigationPanel({ transaction: t, onClose }: InvestigationPanelProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleFeedback = async (outcomeLabel: 'true_positive' | 'false_positive' | 'true_negative' | 'false_negative') => {
    if (!t || !t.decision) return;
    setIsSubmitting(true);
    try {
      await apiFeedbackSubmit({
        transaction_id: t.transaction_id,
        user_id: t.user_id,
        system_decision: t.decision.decision,
        system_risk_score: t.riskScore ?? 0,
        analyst_decision: (outcomeLabel === 'true_positive' || outcomeLabel === 'false_negative') ? 'block' : 'approve',
        outcome_label: outcomeLabel,
        device_id: t.device_id,
        merchant_id: t.merchant_id,
        notes: "Submitted via Analyst Dashboard",
        reviewer_id: "analyst_001"
      });
      alert(`Feedback submitted successfully! Row added to database.`);
    } catch (err) {
      console.error(err);
      alert("Failed to submit feedback.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AnimatePresence>
      {t && (
        <motion.div
          initial={{ x: '100%', opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: '100%', opacity: 0 }}
          transition={{ type: 'spring', damping: 28, stiffness: 300 }}
          className="fixed right-0 top-16 bottom-0 w-full sm:w-[480px] bg-gray-900 border-l border-gray-800 z-40 flex flex-col overflow-hidden"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800">
            <div>
              <h3 className="text-sm font-semibold text-white">Transaction Investigation</h3>
              <div className="text-xs text-gray-500 font-mono mt-0.5">{t.transaction_id}</div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto">
            {/* Risk overview */}
            <div className="px-5 py-4 border-b border-gray-800">
              <div className="flex items-center gap-6">
                <RiskGauge score={t.riskScore ?? 0} size={100} label="Risk" />
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <span className={cn(
                      'text-xs font-semibold px-2 py-0.5 rounded border',
                      t.decision ? decisionColor(t.decision.decision) : 'text-gray-400'
                    )}>
                      {t.decision?.decision.replace('_', ' ').toUpperCase() ?? 'PROCESSING'}
                    </span>
                    <span className="text-xs text-gray-500">
                      {t.decision?.risk_level?.toUpperCase()} RISK
                    </span>
                  </div>
                  <div className="text-2xl font-bold text-white mb-1">{formatAmount(t.amount)}</div>
                  <div className="text-xs text-gray-400">{t.merchant_name} · {t.merchant_category}</div>
                  <div className="text-xs text-gray-500 mt-0.5">{t.location_city}, {t.location_country}</div>
                  <div className="text-[10px] text-gray-600 mt-1">{formatDate(t.timestamp)}</div>
                </div>
              </div>
            </div>

            {/* Timeline */}
            <Section title="Transaction Timeline" icon={Zap}>
              <div className="space-y-2">
                {[
                  { t: 'T+0ms', label: 'Transaction received', ok: true },
                  { t: 'T+8ms', label: 'Feature store query', ok: true },
                  { t: 'T+19ms', label: 'Fast screening complete', ok: true, note: `Score: ${(t.decision?.pre_risk_score ?? 0).toFixed(1)}` },
                  { t: 'T+120ms', label: '5 AI agents dispatched in parallel', ok: true },
                  { t: 'T+240ms', label: 'Consensus engine aggregation', ok: true },
                  { t: t.decision && t.riskScore! > 45 ? 'T+420ms' : undefined, label: 'Deep investigation (if high-risk)', ok: (t.riskScore ?? 0) > 45, skip: (t.riskScore ?? 0) <= 45 },
                  { t: `T+${t.decision?.processing_time_ms?.toFixed(0) ?? '?'}ms`, label: 'Final decision issued', ok: true, note: t.decision?.decision },
                ].filter(s => !s.skip).map((step, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <div className={cn(
                      'w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0',
                      step.ok ? 'bg-green-400' : 'bg-gray-600'
                    )} />
                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-gray-300">{step.label}</div>
                      {step.note && <div className="text-[10px] text-gray-500">{step.note}</div>}
                    </div>
                    <div className="text-[10px] font-mono text-gray-600">{step.t}</div>
                  </div>
                ))}
              </div>
            </Section>

            {/* Agent Risks */}
            {t.decision?.agent_risks && t.decision.agent_risks.length > 0 && (
              <Section title="AI Agent Scores" icon={Brain}>
                <div className="space-y-2">
                  {t.decision.agent_risks.map(a => (
                    <div key={a.agent} className="flex items-center gap-3">
                      <div className="w-16 text-[10px] text-gray-500 capitalize font-medium">{a.agent}</div>
                      <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                        <div
                          className={cn('h-full rounded-full', a.risk_score >= 70 ? 'bg-red-500' : a.risk_score >= 45 ? 'bg-yellow-500' : 'bg-green-500')}
                          style={{ width: `${a.risk_score}%` }}
                        />
                      </div>
                      <div className={cn('text-xs font-mono w-8 text-right', riskColor(a.risk_score))}>
                        {a.risk_score.toFixed(0)}
                      </div>
                      <div className="text-[10px] text-gray-600 w-16 truncate">{a.verdict}</div>
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* Positive signals */}
            {t.decision?.positive_signals && t.decision.positive_signals.length > 0 && (
              <Section title="Positive Signals" icon={CheckCircle}>
                <div className="flex flex-wrap gap-1.5">
                  {t.decision.positive_signals.map(s => (
                    <span key={s} className="text-xs px-2 py-0.5 rounded-full bg-green-500/10 text-green-400 border border-green-500/20">
                      {s.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              </Section>
            )}

            {/* Negative signals */}
            {t.decision?.negative_signals && t.decision.negative_signals.length > 0 && (
              <Section title="Negative Signals" icon={AlertTriangle}>
                <div className="flex flex-wrap gap-1.5">
                  {t.decision.negative_signals.map(s => (
                    <span key={s} className="text-xs px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20">
                      {s.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              </Section>
            )}

            {/* Explanation */}
            {t.decision?.explanation && (
              <Section title="Explanation" icon={Shield}>
                <p className="text-xs text-gray-400 leading-relaxed">{t.decision.explanation}</p>
              </Section>
            )}

            {/* Counterfactual */}
            {t.decision?.counterfactual && (
              <Section title="Counterfactual Analysis" icon={TrendingDown}>
                <p className="text-xs text-gray-400 leading-relaxed italic">{t.decision.counterfactual}</p>
              </Section>
            )}

            {/* Narrative */}
            {t.decision?.story_narrative && (
              <Section title="Investigation Narrative" icon={MessageSquare}>
                <p className="text-xs text-gray-400 leading-relaxed">{t.decision.story_narrative}</p>
              </Section>
            )}

            {/* Recommended action */}
            {t.decision?.recommended_action && (
              <div className="px-5 py-3 border-t border-gray-800">
                <div className="text-[10px] uppercase tracking-wide text-gray-500 mb-1.5">Recommended Action</div>
                <div className={cn(
                  'text-sm font-semibold px-3 py-2 rounded-lg border',
                  t.decision.decision === 'block' ? 'bg-red-500/10 border-red-500/30 text-red-400' :
                  t.decision.decision === 'review' ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400' :
                  'bg-green-500/10 border-green-500/30 text-green-400'
                )}>
                  {t.decision.recommended_action}
                </div>
              </div>
            )}

            {/* Feedback buttons */}
            <div className="px-5 py-4 border-t border-gray-800">
              <div className="text-[10px] uppercase tracking-wide text-gray-500 mb-2">Submit Analyst Feedback</div>
              <div className="grid grid-cols-2 gap-2">
                <button 
                  disabled={isSubmitting}
                  onClick={() => handleFeedback('true_positive')}
                  className="text-[10px] py-2 px-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 transition-colors font-medium disabled:opacity-50">
                  ✓ Correct (Fraud)
                </button>
                <button 
                  disabled={isSubmitting}
                  onClick={() => handleFeedback('false_positive')}
                  className="text-[10px] py-2 px-2 rounded-lg bg-orange-500/10 border border-orange-500/30 text-orange-400 hover:bg-orange-500/20 transition-colors font-medium disabled:opacity-50">
                  ✗ False Positive
                </button>
                <button 
                  disabled={isSubmitting}
                  onClick={() => handleFeedback('true_negative')}
                  className="text-[10px] py-2 px-2 rounded-lg bg-green-500/10 border border-green-500/30 text-green-400 hover:bg-green-500/20 transition-colors font-medium disabled:opacity-50">
                  ✓ Correct (Approved)
                </button>
                <button 
                  disabled={isSubmitting}
                  onClick={() => handleFeedback('false_negative')}
                  className="text-[10px] py-2 px-2 rounded-lg bg-blue-500/10 border border-blue-500/30 text-blue-400 hover:bg-blue-500/20 transition-colors font-medium disabled:opacity-50">
                  ✗ Missed Fraud
                </button>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function Section({ title, icon: Icon, children }: { title: string; icon: React.ComponentType<{ className?: string }>; children: React.ReactNode }) {
  return (
    <div className="px-5 py-3 border-b border-gray-800/60">
      <div className="flex items-center gap-1.5 mb-2">
        <Icon className="w-3.5 h-3.5 text-gray-400" />
        <h4 className="text-xs font-semibold text-gray-300">{title}</h4>
      </div>
      {children}
    </div>
  )
}

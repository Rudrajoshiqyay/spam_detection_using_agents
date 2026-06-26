import { useQuery } from '@tanstack/react-query'
import { apiFeedbackStats } from '@/api/client'
import { MOCK_FEEDBACK_STATS } from '@/lib/mockData'

export function Feedback() {
  const { data } = useQuery({ queryKey: ['feedback-stats'], queryFn: apiFeedbackStats })
  const stats = data ?? MOCK_FEEDBACK_STATS

  const oc = stats.outcome_counts ?? {}
  const m = stats.metrics ?? {}
  const rows = [
    { label: 'Total Feedback Submissions', value: stats.total_feedback ?? 0 },
    { label: 'True Positives (confirmed fraud)', value: oc.true_positive ?? 0 },
    { label: 'False Positives (wrongly blocked)', value: oc.false_positive ?? 0 },
    { label: 'True Negatives (confirmed legit)', value: oc.true_negative ?? 0 },
    { label: 'False Negatives (missed fraud)', value: oc.false_negative ?? 0 },
    { label: 'Precision', value: m.precision != null ? `${(m.precision * 100).toFixed(2)}%` : '—' },
    { label: 'Recall', value: m.recall != null ? `${(m.recall * 100).toFixed(2)}%` : '—' },
    { label: 'F1 Score', value: m.f1_score != null ? m.f1_score.toFixed(4) : '—' },
  ]

  return (
    <div className="space-y-5">
      <h1 className="text-lg font-bold text-white">Feedback Loop</h1>
      <div className="bg-gray-900 border border-gray-800 rounded-xl divide-y divide-gray-800">
        {rows.map(r => (
          <div key={r.label} className="flex items-center justify-between px-5 py-3 text-sm">
            <span className="text-gray-400">{r.label}</span>
            <span className="text-white font-semibold font-mono">{r.value}</span>
          </div>
        ))}
      </div>
      <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl px-5 py-4 text-xs text-blue-300 leading-relaxed">
        The feedback loop automatically adjusts detection thresholds and fraud pattern weights based on analyst decisions.
        Confirmed fraud boosts device/merchant risk scores; false positives restore them. Patterns with 3+ misses trigger
        weight amplification and threshold reduction via the Pattern Evolution engine.
      </div>
    </div>
  )
}

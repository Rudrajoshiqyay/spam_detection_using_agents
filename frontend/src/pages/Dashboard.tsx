import { useState, useEffect, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { HeroCards } from '@/components/dashboard/HeroCards'
import { TransactionFeed } from '@/components/dashboard/TransactionFeed'
import { InvestigationPanel } from '@/components/dashboard/InvestigationPanel'
import { TransactionVolumeChart, RiskDistributionChart, FraudTypeChart, FraudTrendChart } from '@/components/dashboard/Charts'
import { SystemHealth } from '@/components/dashboard/SystemHealth'
import { apiFeedbackStats, apiDetect } from '@/api/client'
import { generateInitialTransactions, MOCK_FEEDBACK_STATS } from '@/lib/mockData'
import { generateMockTransaction, generateMockDecision } from '@/lib/utils'
import type { LiveTransaction } from '@/types'

const MAX_FEED_SIZE = 80

export function Dashboard() {
  const [transactions, setTransactions] = useState<LiveTransaction[]>(() => generateInitialTransactions(12))
  const [selected, setSelected] = useState<LiveTransaction | null>(null)
  const [avgLatency, setAvgLatency] = useState(187)
  const [liveMode] = useState(true)

  const { data: feedbackStats } = useQuery({
    queryKey: ['feedback-stats'],
    queryFn: apiFeedbackStats,
    refetchInterval: 60_000,
  })

  const stats = feedbackStats ?? MOCK_FEEDBACK_STATS

  const addTransaction = useCallback(async () => {
    const tx = generateMockTransaction()
    const live: LiveTransaction = { ...tx, status: 'processing', riskScore: undefined, decision: undefined }

    setTransactions(prev => [live, ...prev].slice(0, MAX_FEED_SIZE))

    let decision: ReturnType<typeof generateMockDecision>
    let riskScore: number
    try {
      const { result } = await apiDetect(tx, `analyst_${Math.random().toString(36).slice(2, 7)}`)
      decision = result
      riskScore = result.risk_score
    } catch {
      decision = generateMockDecision(tx)
      riskScore = decision.risk_score
    }

    const status: LiveTransaction['status'] =
      decision.decision === 'block' ? 'blocked' :
      decision.decision === 'review' ? 'review' : 'approved'

    setTransactions(prev =>
      prev.map(t =>
        t.transaction_id === tx.transaction_id
          ? { ...t, status, riskScore, decision } as LiveTransaction
          : t
      )
    )

    setAvgLatency(prev => Math.round(prev * 0.9 + (decision.processing_time_ms ?? 187) * 0.1))
  }, [])

  useEffect(() => {
    if (!liveMode) return
    const id = setInterval(addTransaction, 4000 + Math.random() * 3000)
    return () => clearInterval(id)
  }, [liveMode, addTransaction])

  return (
    <div className="space-y-5">
      {/* Hero metrics */}
      <HeroCards transactions={transactions} avgLatency={avgLatency} />

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-4 gap-4">
        <TransactionVolumeChart />
        <RiskDistributionChart />
        <FraudTypeChart />
        <FraudTrendChart />
      </div>

      {/* Main area: feed + health */}
      <div className="grid grid-cols-1 xl:grid-cols-[1fr_320px] gap-4">
        <TransactionFeed
          transactions={transactions}
          onSelect={setSelected}
          selected={selected}
        />

        <div className="space-y-4">
          <SystemHealth />

          {/* Feedback stats card */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <h3 className="text-sm font-semibold text-white mb-3">Feedback Loop Stats</h3>
            <div className="space-y-2">
              {[
                { label: 'Total Feedback', value: stats.total_feedback ?? 0 },
                { label: 'True Positives', value: stats.outcome_counts?.true_positive ?? 0 },
                { label: 'False Positives', value: stats.outcome_counts?.false_positive ?? 0 },
                { label: 'Precision', value: stats.metrics?.precision != null ? `${(stats.metrics.precision * 100).toFixed(1)}%` : '—' },
                { label: 'Recall', value: stats.metrics?.recall != null ? `${(stats.metrics.recall * 100).toFixed(1)}%` : '—' },
                { label: 'F1 Score', value: stats.metrics?.f1_score != null ? stats.metrics.f1_score.toFixed(4) : '—' },
              ].map(row => (
                <div key={row.label} className="flex items-center justify-between text-xs">
                  <span className="text-gray-500">{row.label}</span>
                  <span className="text-gray-200 font-medium font-mono">{row.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Investigation panel (slide-out) */}
      <InvestigationPanel transaction={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

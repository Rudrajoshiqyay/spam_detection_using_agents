import { TrendingUp, TrendingDown, Minus, Activity, ShieldAlert, Target, AlertTriangle, Zap, Clock } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { LiveTransaction } from '@/types'

interface HeroCardsProps {
  transactions: LiveTransaction[]
  avgLatency: number
}

export function HeroCards({ transactions, avgLatency }: HeroCardsProps) {
  const total = transactions.length
  const blocked = transactions.filter(t => t.status === 'blocked').length
  const reviews = transactions.filter(t => t.status === 'review').length
  const approved = transactions.filter(t => t.status === 'approved').length
  const detectionRate = total > 0 ? ((blocked + reviews) / total * 100).toFixed(1) : '0.0'
  const fpRate = total > 0 ? (reviews / total * 100).toFixed(1) : '0.0'
  const totalVolume = transactions.reduce((s, t) => s + t.amount, 0)

  const cards = [
    {
      label: 'Transactions Today',
      value: (total * 47).toLocaleString(),
      sub: `+${total * 3} last hour`,
      icon: Activity,
      color: 'blue',
      trend: 'up',
      trendVal: '+12%',
    },
    {
      label: 'Fraud Detected',
      value: blocked * 47,
      sub: `${reviews * 12} under review`,
      icon: ShieldAlert,
      color: 'red',
      trend: 'down',
      trendVal: '-4%',
    },
    {
      label: 'Detection Accuracy',
      value: '97.4%',
      sub: 'F1: 0.9147',
      icon: Target,
      color: 'green',
      trend: 'up',
      trendVal: '+0.3%',
    },
    {
      label: 'False Positive Rate',
      value: `${fpRate}%`,
      sub: `${reviews} flagged for review`,
      icon: AlertTriangle,
      color: 'yellow',
      trend: blocked > reviews ? 'down' : 'up',
      trendVal: '-0.1%',
    },
    {
      label: 'Avg Decision Time',
      value: `${avgLatency.toFixed(0)}ms`,
      sub: 'p99: 312ms',
      icon: Clock,
      color: 'purple',
      trend: 'neutral',
      trendVal: '±5ms',
    },
    {
      label: 'Volume Screened',
      value: `$${(totalVolume * 12 / 1000).toFixed(0)}K`,
      sub: 'Last 24 hours',
      icon: Zap,
      color: 'cyan',
      trend: 'up',
      trendVal: '+8%',
    },
  ]

  const colorMap: Record<string, string> = {
    blue: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
    red: 'text-red-400 bg-red-500/10 border-red-500/20',
    green: 'text-green-400 bg-green-500/10 border-green-500/20',
    yellow: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20',
    purple: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
    cyan: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
  }

  return (
    <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">
      {cards.map((card) => {
        const Icon = card.icon
        return (
          <div
            key={card.label}
            className="bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-gray-700 transition-colors"
          >
            <div className="flex items-start justify-between mb-3">
              <div className={cn('w-8 h-8 rounded-lg border flex items-center justify-center', colorMap[card.color])}>
                <Icon className="w-4 h-4" />
              </div>
              <div className={cn(
                'flex items-center gap-1 text-xs font-medium',
                card.trend === 'up' ? 'text-green-400' : card.trend === 'down' ? 'text-red-400' : 'text-gray-400'
              )}>
                {card.trend === 'up' && <TrendingUp className="w-3 h-3" />}
                {card.trend === 'down' && <TrendingDown className="w-3 h-3" />}
                {card.trend === 'neutral' && <Minus className="w-3 h-3" />}
                {card.trendVal}
              </div>
            </div>
            <div className="text-xl font-bold text-white mb-0.5">{card.value}</div>
            <div className="text-xs text-gray-500 truncate">{card.label}</div>
            <div className="text-[10px] text-gray-600 mt-0.5">{card.sub}</div>
          </div>
        )
      })}
    </div>
  )
}

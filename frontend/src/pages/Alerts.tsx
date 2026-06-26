import { AlertTriangle, Shield, Info } from 'lucide-react'

const MOCK_ALERTS = [
  { id: 1, severity: 'critical', title: 'FraudRing cluster detected', body: '12 accounts linked to device fingerprint ab:cd:ef', time: '2m ago' },
  { id: 2, severity: 'high', title: 'Velocity spike: user_9821', body: '8 transactions in 4 minutes exceeding velocity threshold', time: '7m ago' },
  { id: 3, severity: 'medium', title: 'New device login + high-value purchase', body: '$3,499 at Electronics Plus from previously unseen device', time: '14m ago' },
  { id: 4, severity: 'info', title: 'Pattern evolution triggered', body: 'velocity_burst pattern threshold lowered 0.65 → 0.61', time: '31m ago' },
  { id: 5, severity: 'info', title: 'Reputation update batch completed', body: '47 device reputations updated from analyst feedback', time: '1h ago' },
]

const SEVERITY: Record<string, { icon: typeof AlertTriangle; color: string; bg: string }> = {
  critical: { icon: AlertTriangle, color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/30' },
  high: { icon: Shield, color: 'text-orange-400', bg: 'bg-orange-500/10 border-orange-500/30' },
  medium: { icon: AlertTriangle, color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/30' },
  info: { icon: Info, color: 'text-blue-400', bg: 'bg-blue-500/10 border-blue-500/30' },
}

export function Alerts() {
  return (
    <div className="space-y-4">
      <h1 className="text-lg font-bold text-white">Alerts</h1>
      <div className="space-y-3">
        {MOCK_ALERTS.map(alert => {
          const s = SEVERITY[alert.severity]
          const Icon = s.icon
          return (
            <div key={alert.id} className={`flex items-start gap-3 p-4 rounded-xl border ${s.bg}`}>
              <Icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${s.color}`} />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-white">{alert.title}</div>
                <div className="text-xs text-gray-400 mt-0.5">{alert.body}</div>
              </div>
              <div className="text-[10px] text-gray-500 flex-shrink-0">{alert.time}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

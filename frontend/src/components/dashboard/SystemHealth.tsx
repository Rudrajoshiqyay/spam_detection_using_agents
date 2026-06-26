import { CheckCircle, XCircle, AlertCircle } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { apiHealth } from '@/api/client'
import { MOCK_SYSTEM_METRICS } from '@/lib/mockData'
import { cn } from '@/lib/utils'

export function SystemHealth() {
  const { data: health } = useQuery({ queryKey: ['health'], queryFn: apiHealth, refetchInterval: 30_000 })

  const metrics = MOCK_SYSTEM_METRICS
  const isUp = health?.status === 'ok'

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-white">System Health</h3>
        <div className={cn(
          'flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full border',
          isUp
            ? 'text-green-400 border-green-500/30 bg-green-500/10'
            : 'text-red-400 border-red-500/30 bg-red-500/10'
        )}>
          {isUp ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
          {isUp ? 'All Systems Operational' : health ? 'Degraded' : 'Demo Mode'}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {metrics.map(m => {
          const StatusIcon = m.status === 'ok' ? CheckCircle : m.status === 'warning' ? AlertCircle : XCircle
          const statusColor =
            m.status === 'ok' ? 'text-green-400' :
            m.status === 'warning' ? 'text-yellow-400' : 'text-red-400'

          return (
            <div key={m.label} className="bg-gray-800/50 rounded-lg p-2.5 border border-gray-700/40">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-gray-400 truncate pr-1">{m.label}</span>
                <StatusIcon className={cn('w-3 h-3 flex-shrink-0', statusColor)} />
              </div>
              <div className="text-xs font-medium text-gray-200">{m.value}</div>
              {m.trend !== undefined && (
                <div className={cn(
                  'text-[10px] mt-0.5',
                  m.trend < 0 ? 'text-green-500' : m.trend > 0 ? 'text-red-400' : 'text-gray-600'
                )}>
                  {m.trend > 0 ? '+' : ''}{m.trend}ms
                </div>
              )}
            </div>
          )
        })}
      </div>

      {health && (
        <div className="mt-3 pt-3 border-t border-gray-800/60 flex items-center justify-between text-[10px] text-gray-600">
          <span>{health.redis === 'connected' ? 'Redis ✓' : 'Redis —'}</span>
          <span>{health.timestamp ? new Date(health.timestamp).toLocaleTimeString() : '—'}</span>
        </div>
      )}
    </div>
  )
}

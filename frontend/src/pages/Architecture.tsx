import { CheckCircle, FileCode, TestTube, GitBranch } from 'lucide-react'
import { ARCHITECTURE_MODULES } from '@/lib/mockData'
import { cn } from '@/lib/utils'

const STATUS_COLOR: Record<string, string> = {
  production: 'text-green-400 bg-green-500/10 border-green-500/30',
  stable: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
  beta: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
  planned: 'text-gray-500 bg-gray-800 border-gray-700',
}

export function Architecture() {
  const totalLoc = ARCHITECTURE_MODULES.reduce((s, m) => s + (m.lines ?? 0), 0)
  const totalTests = ARCHITECTURE_MODULES.reduce((s, m) => s + (m.tests ?? 0), 0)
  const prodModules = ARCHITECTURE_MODULES.filter(m => m.status === 'production').length

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-bold text-white">Architecture Explorer</h1>
        <p className="text-xs text-gray-500 mt-0.5">System modules, test coverage, and production readiness</p>
      </div>

      {/* Summary row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { label: 'Total Modules', value: ARCHITECTURE_MODULES.length, icon: GitBranch, color: 'blue' },
          { label: 'Production Ready', value: prodModules, icon: CheckCircle, color: 'green' },
          { label: 'Lines of Code', value: totalLoc.toLocaleString(), icon: FileCode, color: 'purple' },
          { label: 'Test Cases', value: totalTests, icon: TestTube, color: 'cyan' },
        ].map(c => {
          const Icon = c.icon
          const colorMap: Record<string, string> = {
            blue: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
            green: 'text-green-400 bg-green-500/10 border-green-500/20',
            purple: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
            cyan: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
          }
          return (
            <div key={c.label} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <div className={cn('w-8 h-8 rounded-lg border flex items-center justify-center mb-3', colorMap[c.color])}>
                <Icon className="w-4 h-4" />
              </div>
              <div className="text-2xl font-bold text-white">{c.value}</div>
              <div className="text-xs text-gray-500">{c.label}</div>
            </div>
          )
        })}
      </div>

      {/* Module cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
        {ARCHITECTURE_MODULES.map(mod => (
          <div key={mod.id} className="bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-gray-700 transition-colors">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="text-sm font-semibold text-white">{mod.name}</h3>
                <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">{mod.purpose}</p>
              </div>
              <span className={cn(
                'text-[10px] font-semibold px-2 py-0.5 rounded-full border flex-shrink-0 ml-2',
                STATUS_COLOR[mod.status] ?? STATUS_COLOR.planned
              )}>
                {mod.status}
              </span>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-2 mb-3">
              <Stat label="LOC" value={mod.lines?.toLocaleString() ?? '—'} />
              <Stat label="Tests" value={mod.tests?.toString() ?? '—'} />
              <Stat label="Audit" value={mod.auditScore != null ? `${mod.auditScore}/100` : '—'} />
            </div>

            {/* Audit score bar */}
            {mod.auditScore != null && (
              <div>
                <div className="flex items-center justify-between text-[10px] text-gray-500 mb-1">
                  <span>Audit score</span>
                  <span className="font-medium text-gray-300">{mod.auditScore}/100</span>
                </div>
                <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className={cn(
                      'h-full rounded-full',
                      mod.auditScore >= 80 ? 'bg-green-500' : mod.auditScore >= 60 ? 'bg-yellow-500' : 'bg-red-500'
                    )}
                    style={{ width: `${mod.auditScore}%` }}
                  />
                </div>
              </div>
            )}

            {/* Dependencies */}
            {mod.dependencies && mod.dependencies.length > 0 && (
              <div className="mt-3 pt-3 border-t border-gray-800/60">
                <div className="text-[10px] uppercase tracking-wide text-gray-600 mb-1.5">Dependencies</div>
                <div className="flex flex-wrap gap-1">
                  {mod.dependencies.slice(0, 5).map((dep: string) => (
                    <span key={dep} className="text-[10px] font-mono text-gray-500 bg-gray-800/50 px-1.5 py-0.5 rounded">
                      {dep}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-gray-800/40 rounded-lg p-2 text-center">
      <div className="text-sm font-bold text-white">{value}</div>
      <div className="text-[10px] text-gray-500">{label}</div>
    </div>
  )
}

import { useState, useMemo } from 'react'
import { Search, Filter, ChevronDown, ChevronUp, Eye, ArrowUpDown } from 'lucide-react'
import { cn, riskColor, formatAmount, relativeTime } from '@/lib/utils'
import type { LiveTransaction, DecisionType } from '@/types'

interface TransactionFeedProps {
  transactions: LiveTransaction[]
  onSelect: (t: LiveTransaction) => void
  selected: LiveTransaction | null
}

type SortKey = 'timestamp' | 'amount' | 'riskScore'
type SortDir = 'asc' | 'desc'

const DECISION_BADGE: Record<DecisionType, string> = {
  block: 'bg-red-500/15 text-red-400 border-red-500/30',
  review: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  approve: 'bg-green-500/15 text-green-400 border-green-500/30',
  auto_approve: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
}

export function TransactionFeed({ transactions, onSelect, selected }: TransactionFeedProps) {
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<string>('all')
  const [sort, setSort] = useState<SortKey>('timestamp')
  const [dir, setDir] = useState<SortDir>('desc')
  const [page, setPage] = useState(0)
  const PAGE_SIZE = 8

  const filtered = useMemo(() => {
    let data = [...transactions]
    if (search) {
      const q = search.toLowerCase()
      data = data.filter(t =>
        t.merchant_name.toLowerCase().includes(q) ||
        t.user_id.toLowerCase().includes(q) ||
        t.location_city.toLowerCase().includes(q) ||
        t.transaction_id.toLowerCase().includes(q)
      )
    }
    if (filter !== 'all') {
      data = data.filter(t => t.status === filter)
    }
    data.sort((a, b) => {
      let va: number, vb: number
      if (sort === 'timestamp') {
        va = new Date(a.timestamp).getTime()
        vb = new Date(b.timestamp).getTime()
      } else if (sort === 'amount') {
        va = a.amount; vb = b.amount
      } else {
        va = a.riskScore ?? 0; vb = b.riskScore ?? 0
      }
      return dir === 'desc' ? vb - va : va - vb
    })
    return data
  }, [transactions, search, filter, sort, dir])

  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE)

  const toggleSort = (key: SortKey) => {
    if (sort === key) setDir(d => d === 'desc' ? 'asc' : 'desc')
    else { setSort(key); setDir('desc') }
    setPage(0)
  }

  const SortIcon = ({ k }: { k: SortKey }) => {
    if (sort !== k) return <ArrowUpDown className="w-3 h-3 text-gray-600" />
    return dir === 'desc'
      ? <ChevronDown className="w-3 h-3 text-blue-400" />
      : <ChevronUp className="w-3 h-3 text-blue-400" />
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-white">Live Transaction Feed</h2>
          <div className="relative w-1.5 h-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-green-400 live-dot" />
          </div>
          <span className="text-xs text-gray-500">{transactions.length} total</span>
        </div>

        <div className="flex items-center gap-2">
          {/* Filter */}
          <div className="flex items-center gap-1 text-xs">
            <Filter className="w-3 h-3 text-gray-500" />
            <select
              value={filter}
              onChange={e => { setFilter(e.target.value); setPage(0) }}
              className="bg-gray-800 border border-gray-700 rounded-md px-2 py-1 text-gray-300 text-xs focus:outline-none"
            >
              <option value="all">All</option>
              <option value="blocked">Blocked</option>
              <option value="review">Review</option>
              <option value="approved">Approved</option>
            </select>
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="px-4 py-2 border-b border-gray-800/50">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" />
          <input
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(0) }}
            placeholder="Search by merchant, user, city..."
            className="w-full bg-gray-800/60 border border-gray-700/50 rounded-lg pl-8 pr-3 py-1.5 text-xs text-gray-300 placeholder-gray-600 focus:outline-none focus:border-gray-600"
          />
        </div>
      </div>

      {/* Table header */}
      <div className="grid grid-cols-[1fr_1.2fr_0.7fr_0.7fr_0.7fr_0.6fr_40px] gap-2 px-4 py-2 text-[10px] uppercase tracking-wide text-gray-500 border-b border-gray-800/50">
        <button className="flex items-center gap-1 text-left" onClick={() => toggleSort('timestamp')}>
          Time <SortIcon k="timestamp" />
        </button>
        <div>Merchant · User</div>
        <button className="flex items-center gap-1" onClick={() => toggleSort('amount')}>
          Amount <SortIcon k="amount" />
        </button>
        <button className="flex items-center gap-1" onClick={() => toggleSort('riskScore')}>
          Risk <SortIcon k="riskScore" />
        </button>
        <div>Decision</div>
        <div>Confidence</div>
        <div />
      </div>

      {/* Rows */}
      <div className="flex-1 overflow-auto">
        {paged.length === 0 ? (
          <div className="flex items-center justify-center h-32 text-sm text-gray-500">
            No transactions match
          </div>
        ) : (
          paged.map((t) => (
            <button
              key={t.transaction_id}
              onClick={() => onSelect(t)}
              className={cn(
                'w-full grid grid-cols-[1fr_1.2fr_0.7fr_0.7fr_0.7fr_0.6fr_40px] gap-2 px-4 py-2.5',
                'text-left text-xs border-b border-gray-800/40 hover:bg-gray-800/40 transition-colors',
                selected?.transaction_id === t.transaction_id && 'bg-blue-500/5 border-blue-500/20'
              )}
            >
              {/* Time */}
              <div className="text-gray-400 font-mono">{relativeTime(t.timestamp)}</div>

              {/* Merchant */}
              <div>
                <div className="text-gray-200 font-medium truncate">{t.merchant_name}</div>
                <div className="text-gray-500 truncate">{t.user_id}</div>
              </div>

              {/* Amount */}
              <div className="text-gray-300 font-mono">{formatAmount(t.amount)}</div>

              {/* Risk score */}
              <div className={cn('font-bold', riskColor(t.riskScore ?? 0))}>
                {t.riskScore?.toFixed(0) ?? '–'}
              </div>

              {/* Decision badge */}
              <div>
                {t.decision ? (
                  <span className={cn(
                    'inline-flex items-center px-1.5 py-0.5 rounded border text-[10px] font-medium',
                    DECISION_BADGE[t.decision.decision]
                  )}>
                    {t.decision.decision.replace('_', ' ')}
                  </span>
                ) : (
                  <span className="text-gray-600">–</span>
                )}
              </div>

              {/* Confidence */}
              <div className="text-gray-400">
                {t.decision ? `${(t.decision.confidence * 100).toFixed(0)}%` : '–'}
              </div>

              {/* View */}
              <div className="flex items-center justify-center">
                <Eye className="w-3.5 h-3.5 text-gray-600 hover:text-blue-400" />
              </div>
            </button>
          ))
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-2 border-t border-gray-800/50 text-xs text-gray-500">
          <span>{filtered.length} results</span>
          <div className="flex items-center gap-1">
            <button
              disabled={page === 0}
              onClick={() => setPage(p => p - 1)}
              className="px-2 py-1 rounded hover:bg-gray-800 disabled:opacity-40"
            >
              ‹
            </button>
            <span className="px-2">
              {page + 1} / {totalPages}
            </span>
            <button
              disabled={page >= totalPages - 1}
              onClick={() => setPage(p => p + 1)}
              className="px-2 py-1 rounded hover:bg-gray-800 disabled:opacity-40"
            >
              ›
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

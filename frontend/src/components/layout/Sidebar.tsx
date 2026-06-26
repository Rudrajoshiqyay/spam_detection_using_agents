import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Activity, Search, Bell, BarChart3,
  MessageSquare, Settings, GitBranch, Shield, X,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const NAV = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard', end: true },
  { to: '/transactions', icon: Activity, label: 'Transactions' },
  { to: '/investigations', icon: Search, label: 'Investigations' },
  { to: '/alerts', icon: Bell, label: 'Alerts', badge: 3 },
  { to: '/analytics', icon: BarChart3, label: 'Analytics' },
  { to: '/feedback', icon: MessageSquare, label: 'Feedback' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

interface SidebarProps {
  open: boolean
  onClose: () => void
}

export function Sidebar({ open, onClose }: SidebarProps) {
  return (
    <>
      {/* Mobile overlay */}
      {open && (
        <div
          className="fixed inset-0 bg-black/60 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={cn(
          'fixed left-0 top-0 h-full w-64 z-50 flex flex-col',
          'bg-gray-900 border-r border-gray-800',
          'transition-transform duration-300',
          open ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        )}
      >
        {/* Logo */}
        <div className="flex items-center justify-between h-16 px-5 border-b border-gray-800">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-500 flex items-center justify-center">
              <Shield className="w-4 h-4 text-white" />
            </div>
            <div>
              <div className="text-sm font-bold text-white">FraudGuard</div>
              <div className="text-[10px] text-gray-400 leading-none">AI Platform</div>
            </div>
          </div>
          <button onClick={onClose} className="lg:hidden text-gray-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {NAV.map(({ to, icon: Icon, label, badge, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                    : 'text-gray-400 hover:text-white hover:bg-gray-800'
                )
              }
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span className="flex-1">{label}</span>
              {badge && (
                <span className="text-xs bg-red-500 text-white px-1.5 py-0.5 rounded-full">
                  {badge}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Pipeline button */}
        <div className="px-3 pb-4 border-t border-gray-800 pt-3">
          <NavLink
            to="/pipeline"
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors w-full',
                isActive
                  ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                  : 'text-gray-300 hover:text-white hover:bg-gray-800 border border-gray-700'
              )
            }
          >
            <GitBranch className="w-4 h-4 flex-shrink-0" />
            <span className="flex-1">Pipeline Viz</span>
            <span className="text-xs text-purple-400">→</span>
          </NavLink>
        </div>

        {/* System status */}
        <div className="px-4 pb-4">
          <div className="rounded-lg bg-gray-800/50 border border-gray-700 px-3 py-2.5">
            <div className="flex items-center gap-2 mb-1">
              <div className="relative w-2 h-2">
                <div className="w-2 h-2 rounded-full bg-green-400 live-dot" />
              </div>
              <span className="text-xs text-gray-300 font-medium">System Online</span>
            </div>
            <div className="text-[10px] text-gray-500">323 tests passing · 91/100</div>
          </div>
        </div>
      </aside>
    </>
  )
}

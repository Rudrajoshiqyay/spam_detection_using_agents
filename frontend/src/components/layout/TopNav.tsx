import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Menu, Bell, Sun, Moon, GitBranch, Wifi, WifiOff, RefreshCw } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { apiHealth } from '@/api/client'
import { cn } from '@/lib/utils'

interface TopNavProps {
  onMenuClick: () => void
  darkMode: boolean
  onToggleDark: () => void
}

export function TopNav({ onMenuClick, darkMode, onToggleDark }: TopNavProps) {
  const navigate = useNavigate()
  const [time, setTime] = useState(new Date())
  const [mockMode] = useState(true)

  const { data: health, isError, refetch } = useQuery({
    queryKey: ['health'],
    queryFn: apiHealth,
    refetchInterval: 30_000,
    retry: false,
  })

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  const isOnline = !isError && health?.status !== 'error'

  return (
    <header className="h-16 bg-gray-900 border-b border-gray-800 flex items-center px-4 gap-4 sticky top-0 z-30">
      {/* Mobile menu */}
      <button
        onClick={onMenuClick}
        className="lg:hidden text-gray-400 hover:text-white"
      >
        <Menu className="w-5 h-5" />
      </button>

      {/* Brand (mobile) */}
      <div className="lg:hidden flex items-center gap-2">
        <div className="w-6 h-6 rounded-md bg-blue-500 flex items-center justify-center">
          <span className="text-xs font-bold text-white">F</span>
        </div>
        <span className="text-sm font-bold text-white">FraudGuard</span>
      </div>

      {/* Left spacer */}
      <div className="hidden lg:block" />

      {/* Center / Status */}
      <div className="flex-1 flex items-center justify-center gap-6">
        {/* API Status */}
        <div className="flex items-center gap-1.5 text-xs">
          {isOnline ? (
            <Wifi className="w-3.5 h-3.5 text-green-400" />
          ) : (
            <WifiOff className="w-3.5 h-3.5 text-yellow-400" />
          )}
          <span className={cn(isOnline ? 'text-green-400' : 'text-yellow-400', 'font-medium')}>
            {isOnline ? 'API Live' : 'Demo Mode'}
          </span>
        </div>

        {/* Mode badge */}
        <div className={cn(
          'hidden sm:flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border',
          mockMode && !isOnline
            ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400'
            : 'bg-green-500/10 border-green-500/30 text-green-400'
        )}>
          <div className="relative w-1.5 h-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-current live-dot" />
          </div>
          {mockMode && !isOnline ? 'Mock Mode' : 'Live Mode'}
        </div>

        {/* Clock */}
        <div className="hidden md:block text-xs text-gray-400 font-mono">
          {time.toLocaleTimeString()}
        </div>
      </div>

      {/* Right actions */}
      <div className="flex items-center gap-2">
        {/* Refresh */}
        <button
          onClick={() => refetch()}
          className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
          title="Refresh status"
        >
          <RefreshCw className="w-4 h-4" />
        </button>

        {/* Notifications */}
        <button className="relative p-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors">
          <Bell className="w-4 h-4" />
          <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-red-500 rounded-full" />
        </button>

        {/* Dark mode */}
        <button
          onClick={onToggleDark}
          className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
        >
          {darkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>

        {/* Pipeline button */}
        <button
          onClick={() => navigate('/pipeline')}
          className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-purple-500/10 border border-purple-500/30 text-purple-400 text-xs font-medium hover:bg-purple-500/20 transition-colors"
        >
          <GitBranch className="w-3.5 h-3.5" />
          View AI Pipeline →
        </button>
      </div>
    </header>
  )
}

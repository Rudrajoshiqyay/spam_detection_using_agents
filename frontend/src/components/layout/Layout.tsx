import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { TopNav } from './TopNav'

interface LayoutProps {
  darkMode: boolean
  onToggleDark: () => void
}

export function Layout({ darkMode, onToggleDark }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="min-h-screen bg-gray-950 text-white flex">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Main content — offset by sidebar width on lg+ */}
      <div className="flex-1 lg:ml-64 flex flex-col min-h-screen">
        <TopNav
          onMenuClick={() => setSidebarOpen(true)}
          darkMode={darkMode}
          onToggleDark={onToggleDark}
        />
        <main className="flex-1 p-4 lg:p-6 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

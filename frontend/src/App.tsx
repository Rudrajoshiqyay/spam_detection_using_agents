import { useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from '@/components/layout/Layout'
import { Dashboard } from '@/pages/Dashboard'
import { Pipeline } from '@/pages/Pipeline'
import { Architecture } from '@/pages/Architecture'
import { Transactions } from '@/pages/Transactions'
import { Investigations } from '@/pages/Investigations'
import { Alerts } from '@/pages/Alerts'
import { Analytics } from '@/pages/Analytics'
import { Feedback } from '@/pages/Feedback'
import { Settings } from '@/pages/Settings'

export function App() {
  const [darkMode, setDarkMode] = useState(true)

  return (
    <div className={darkMode ? 'dark' : ''}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout darkMode={darkMode} onToggleDark={() => setDarkMode(d => !d)} />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/pipeline" element={<Pipeline />} />
            <Route path="/architecture" element={<Architecture />} />
            <Route path="/transactions" element={<Transactions />} />
            <Route path="/investigations" element={<Investigations />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/feedback" element={<Feedback />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </div>
  )
}

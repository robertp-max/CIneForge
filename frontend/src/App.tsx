import { useCallback, useState } from 'react'
import { AppShell, type PageId } from './components/AppShell'
import { Campaigns } from './pages/Campaigns'
import { Dashboard } from './pages/Dashboard'
import { Jobs } from './pages/Jobs'
import { Projects } from './pages/Projects'
import { Queue } from './pages/Queue'
import { Roadmap } from './pages/Roadmap'
import { Runtime } from './pages/Runtime'
import { SystemHealth } from './pages/SystemHealth'

function App() {
  const [activePage, setActivePage] = useState<PageId>('dashboard')
  const [backendStatus, setBackendStatus] = useState('checking')
  const handleBackendStatus = useCallback((status: string) => {
    setBackendStatus(status)
  }, [])

  return (
    <AppShell activePage={activePage} backendStatus={backendStatus} onNavigate={setActivePage}>
      {activePage === 'dashboard' ? <Dashboard onBackendStatus={handleBackendStatus} /> : null}
      {activePage === 'projects' ? <Projects /> : null}
      {activePage === 'campaigns' ? <Campaigns /> : null}
      {activePage === 'jobs' ? <Jobs /> : null}
      {activePage === 'queue' ? <Queue /> : null}
      {activePage === 'runtime' ? <Runtime /> : null}
      {activePage === 'health' ? <SystemHealth /> : null}
      {activePage === 'roadmap' ? <Roadmap /> : null}
    </AppShell>
  )
}

export default App

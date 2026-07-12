import { useCallback, useEffect, useState } from 'react'
import { api } from './api/client'
import { AppShell, type PageId } from './components/AppShell'
import { StoryboardStudio } from './pages/StoryboardStudio'

function normalizeBackendStatus(value: string | undefined): string {
  const status = (value ?? 'unknown').toLowerCase()
  if (status === 'ok' || status === 'healthy' || status === 'up' || status === 'ready') return 'ok'
  if (status === 'degraded' || status === 'partial') return 'degraded'
  if (status === 'disabled') return 'disabled'
  if (status === 'checking' || status === 'loading') return 'checking'
  return 'unavailable'
}

function App() {
  const [activePage, setActivePage] = useState<PageId>('overview')
  const [backendStatus, setBackendStatus] = useState('checking')

  const refreshBackendStatus = useCallback(async () => {
    try {
      const [root, runtime] = await Promise.all([api.rootStatus(), api.runtimeStatus()])
      const combined = runtime.status || root.status || 'unknown'
      setBackendStatus(normalizeBackendStatus(combined))
    } catch {
      setBackendStatus('unavailable')
    }
  }, [])

  useEffect(() => {
    const initial = window.setTimeout(() => void refreshBackendStatus(), 0)
    const timer = window.setInterval(() => {
      void refreshBackendStatus()
    }, 30_000)
    return () => {
      window.clearTimeout(initial)
      window.clearInterval(timer)
    }
  }, [refreshBackendStatus])

  return (
    <AppShell
      activePage={activePage}
      backendStatus={backendStatus}
      onNavigate={setActivePage}
      onRefreshStatus={() => void refreshBackendStatus()}
    >
      <StoryboardStudio
        page={activePage}
        backendStatus={backendStatus}
        onNavigate={setActivePage}
      />
    </AppShell>
  )
}

export default App
